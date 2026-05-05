from __future__ import annotations

from math import cos, isfinite, radians, sin
from typing import Iterable

from aurora_translator.semantic.adapters.utils import (
    role_from_net_name,
    semantic_id,
    side_from_layer_name,
    source_ref,
    unique_append,
)
from aurora_translator.semantic.models import (
    SemanticArcGeometry,
    SemanticBoard,
    SemanticBoardOutlineGeometry,
    SemanticComponent,
    SemanticDiagnostic,
    SemanticFootprint,
    SemanticLayer,
    SemanticMaterial,
    SemanticMetadata,
    SemanticNet,
    SemanticPad,
    SemanticPadGeometry,
    SemanticPin,
    SemanticPoint,
    SemanticPolygonVoidGeometry,
    SemanticPrimitive,
    SemanticPrimitiveGeometry,
    SemanticShape,
    SemanticSummary,
    SemanticVia,
    SemanticViaGeometry,
    SemanticViaTemplate,
    SemanticViaTemplateGeometry,
    SemanticViaTemplateLayer,
)
from aurora_translator.semantic.passes import (
    build_connectivity_diagnostics,
    build_connectivity_edges,
)
from aurora_translator.sources.altium.models import (
    AltiumArc,
    AltiumClass,
    AltiumComponent,
    AltiumFill,
    AltiumLayout,
    AltiumLayer,
    AltiumPad,
    AltiumPoint,
    AltiumPolygon,
    AltiumRegion,
    AltiumText,
    AltiumTrack,
    AltiumVertex,
    AltiumVia,
)


ALTIUM_UNCONNECTED_INDEXES = {65535, 4294967295}
ALTIUM_NO_COMPONENT_INDEXES = {65535, 4294967295}
COPPER_MATERIAL_ID = semantic_id("material", "Copper")
DEFAULT_PAD_SIZE_MIL = 10.0
DEFAULT_VIA_DIAMETER_MIL = 16.0
DEFAULT_VIA_HOLE_MIL = 8.0
ALTIUM_INVALID_COORD_RAW_ABS = 2_147_000_000


def from_altium(
    payload: AltiumLayout, *, build_connectivity: bool = True
) -> SemanticBoard:
    diagnostics = _source_diagnostics(payload)
    layers = _semantic_layers(payload, diagnostics)
    materials = _semantic_materials(layers)
    metal_layer_names = [layer.name for layer in layers if _is_metal_layer(layer)]
    top_layer = _top_layer_name(layers)
    bottom_layer = _bottom_layer_name(layers)

    nets, net_ids_by_index = _semantic_nets(payload)
    nets_by_id = {net.id: net for net in nets}

    shapes: list[SemanticShape] = []
    shape_ids_by_key: dict[tuple[str, tuple[object, ...]], str] = {}

    components, footprints, component_ids_by_index, footprint_ids_by_component = (
        _semantic_components(payload, top_layer, bottom_layer)
    )
    components_by_id = {component.id: component for component in components}
    footprints_by_id = {footprint.id: footprint for footprint in footprints}

    pins: list[SemanticPin] = []
    pads: list[SemanticPad] = []
    _semantic_pads(
        payload,
        component_ids_by_index,
        footprint_ids_by_component,
        net_ids_by_index,
        top_layer,
        bottom_layer,
        shapes,
        shape_ids_by_key,
        pins,
        pads,
        components_by_id,
        footprints_by_id,
        nets_by_id,
    )

    via_templates, via_template_ids_by_key = _semantic_via_templates(
        payload, metal_layer_names, shapes, shape_ids_by_key
    )
    vias = _semantic_vias(
        payload,
        metal_layer_names,
        net_ids_by_index,
        via_template_ids_by_key,
        nets_by_id,
    )
    primitives = _semantic_primitives(
        payload,
        net_ids_by_index,
        nets_by_id,
        component_ids_by_index,
    )

    board = SemanticBoard(
        metadata=SemanticMetadata(
            source_format="altium",
            source=payload.metadata.source,
            source_parser_version=payload.metadata.parser_version,
            source_schema_version=payload.metadata.output_schema_version,
        ),
        units=_semantic_units(payload),
        summary=SemanticSummary(),
        layers=layers,
        materials=materials,
        shapes=shapes,
        via_templates=via_templates,
        nets=nets,
        components=list(components_by_id.values()),
        footprints=list(footprints_by_id.values()),
        pins=pins,
        pads=pads,
        vias=vias,
        primitives=primitives,
        diagnostics=diagnostics,
        board_outline=_board_outline(payload),
    )
    if build_connectivity:
        board.connectivity = build_connectivity_edges(board)
        board.diagnostics = [*board.diagnostics, *build_connectivity_diagnostics(board)]
    return board.with_computed_summary()


def _source_diagnostics(payload: AltiumLayout) -> list[SemanticDiagnostic]:
    return [
        SemanticDiagnostic(
            severity="warning",
            code="altium.source_diagnostic",
            message=message,
            source=source_ref("altium", "diagnostics"),
        )
        for message in payload.diagnostics
    ]


def _semantic_layers(
    payload: AltiumLayout, diagnostics: list[SemanticDiagnostic]
) -> list[SemanticLayer]:
    layers: list[SemanticLayer] = []
    seen: set[str] = set()
    source_layers = _source_stackup_copper_layer_items(payload.layers or [])
    if not source_layers:
        source_layers = [
            (index, layer)
            for index, layer in enumerate(payload.layers or [])
            if _is_source_fallback_copper_layer(layer)
        ]

    for index, layer in source_layers:
        name = _layer_name(layer)
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        role = _source_copper_layer_role(layer)
        layers.append(
            SemanticLayer(
                id=semantic_id("layer", name, layer.layer_id),
                name=name,
                layer_type="copper",
                role=role,
                side=_layer_side(layer.layer_id, name),
                order_index=len(layers),
                material="Copper",
                material_id=COPPER_MATERIAL_ID,
                thickness=layer.copper_thickness,
                source=source_ref("altium", f"layers[{index}]", layer.layer_id),
            )
        )

    if layers:
        return layers

    synthesized = sorted(
        {
            name
            for name in _source_layer_names(payload)
            if name and _is_probable_copper_layer_name(name)
        },
        key=_layer_name_sort_key,
    )
    for index, name in enumerate(synthesized):
        layers.append(
            SemanticLayer(
                id=semantic_id("layer", name, index),
                name=name,
                layer_type="copper",
                role="signal",
                side=side_from_layer_name(name) or "internal",
                order_index=index,
                material="Copper",
                material_id=COPPER_MATERIAL_ID,
                source=source_ref("altium", "primitive.layer_name", name),
            )
        )

    if not layers:
        diagnostics.append(
            SemanticDiagnostic(
                severity="info",
                code="altium.no_copper_layers",
                message="No Altium copper layers were available in the source payload.",
                source=source_ref("altium", "layers"),
            )
        )
    return layers


def _semantic_materials(layers: list[SemanticLayer]) -> list[SemanticMaterial]:
    if not layers:
        return []
    return [
        SemanticMaterial(
            id=COPPER_MATERIAL_ID,
            name="Copper",
            role="metal",
            source=source_ref("altium", "layers.copper_thickness", "Copper"),
        )
    ]


def _semantic_nets(
    payload: AltiumLayout,
) -> tuple[list[SemanticNet], dict[int, str]]:
    referenced = _referenced_net_indexes(payload)
    needs_no_net = bool(referenced & ALTIUM_UNCONNECTED_INDEXES) or not (
        payload.nets or []
    )

    nets: list[SemanticNet] = []
    net_ids_by_index: dict[int, str] = {}
    net_ids_by_name: dict[str, str] = {}

    if needs_no_net:
        no_net = SemanticNet(
            id=semantic_id("net", "NoNet"),
            name="NoNet",
            role="unknown",
            source=source_ref("altium", "nets", "NoNet"),
        )
        nets.append(no_net)
        net_ids_by_name[no_net.name.casefold()] = no_net.id
        for index in ALTIUM_UNCONNECTED_INDEXES:
            net_ids_by_index[index] = no_net.id

    for index, net in enumerate(payload.nets or []):
        name = net.name or f"AltiumNet{net.index}"
        name_key = name.casefold()
        existing = net_ids_by_name.get(name_key)
        if existing is not None:
            net_ids_by_index[net.index] = existing
            continue
        semantic_net = SemanticNet(
            id=semantic_id("net", name, net.index),
            name=name,
            role=role_from_net_name(name),
            source=source_ref("altium", f"nets[{index}]", net.index),
        )
        nets.append(semantic_net)
        net_ids_by_index[net.index] = semantic_net.id
        net_ids_by_name[name_key] = semantic_net.id

    for net_index in sorted(referenced):
        if net_index in net_ids_by_index or _is_unconnected_net(net_index):
            continue
        name = f"AltiumNet{net_index}"
        semantic_net = SemanticNet(
            id=semantic_id("net", name, net_index),
            name=name,
            role="unknown",
            source=source_ref("altium", "net_reference", net_index),
        )
        nets.append(semantic_net)
        net_ids_by_index[net_index] = semantic_net.id

    return nets, net_ids_by_index


def _semantic_components(
    payload: AltiumLayout,
    top_layer: str | None,
    bottom_layer: str | None,
) -> tuple[
    list[SemanticComponent],
    list[SemanticFootprint],
    dict[int, str],
    dict[int, str],
]:
    components: list[SemanticComponent] = []
    footprints_by_name: dict[str, SemanticFootprint] = {}
    component_ids_by_index: dict[int, str] = {}
    footprint_ids_by_component: dict[int, str] = {}
    component_indices_with_pads = {
        pad.component
        for pad in payload.pads or []
        if pad.component not in ALTIUM_UNCONNECTED_INDEXES
        and not _is_unnamed_no_net_component_pad(pad)
    }
    designators_by_component_index = _component_designators_by_index(payload)
    part_names_by_component_index = _component_comment_texts_by_index(payload)

    for index, component in enumerate(payload.components or []):
        if component.index not in component_indices_with_pads:
            continue
        footprint_name = _footprint_name(component)
        part_name = _component_part_name(component, part_names_by_component_index)
        footprint = footprints_by_name.get(footprint_name)
        if footprint is None:
            footprint = SemanticFootprint(
                id=semantic_id("footprint", footprint_name),
                name=footprint_name,
                part_name=part_name,
                attributes=_component_library_attributes(component),
                source=source_ref("altium", f"components[{index}]", component.index),
            )
            footprints_by_name[footprint_name] = footprint

        refdes = _component_refdes(component, designators_by_component_index)
        layer_name = _component_layer_name(component, top_layer, bottom_layer)
        semantic_component = SemanticComponent(
            id=semantic_id("component", f"{refdes}:{component.index}"),
            refdes=refdes,
            name=refdes,
            part_name=part_name,
            package_name=footprint_name,
            footprint_id=footprint.id,
            layer_name=layer_name,
            side=side_from_layer_name(layer_name)
            or _layer_side(component.layer_id, layer_name),
            location=_point(component.position),
            rotation=radians(component.rotation),
            attributes=_component_attributes(component),
            source=source_ref("altium", f"components[{index}]", component.index),
        )
        components.append(semantic_component)
        component_ids_by_index[component.index] = semantic_component.id
        footprint_ids_by_component[component.index] = footprint.id

    return (
        components,
        list(footprints_by_name.values()),
        component_ids_by_index,
        footprint_ids_by_component,
    )


def _component_refdes(
    component: AltiumComponent, designators_by_component_index: dict[int, str]
) -> str:
    return (
        component.source_designator
        or designators_by_component_index.get(component.index)
        or f"ALTIUM_COMP_{component.index}"
    )


def _component_part_name(
    component: AltiumComponent, part_names_by_component_index: dict[int, str]
) -> str | None:
    return (
        component.source_lib_reference
        or part_names_by_component_index.get(component.index)
        or component.properties.get("COMMENT")
        or component.properties.get("Comment")
    )


def _component_designators_by_index(payload: AltiumLayout) -> dict[int, str]:
    components = list(payload.components or [])
    if not components:
        return {}
    component_class = _component_designator_class(
        payload.classes or [], len(components)
    )
    if component_class is None:
        return {}
    result: dict[int, str] = {}
    for component, member in zip(components, component_class.members, strict=False):
        designator = member.strip()
        if designator:
            result[component.index] = designator
    return result


def _component_designator_class(
    classes: Iterable[AltiumClass], component_count: int
) -> AltiumClass | None:
    candidates = [item for item in classes if len(item.members) >= component_count]
    if not candidates:
        candidates = [item for item in classes if len(item.members) == component_count]
    if not candidates:
        return None
    for item in candidates:
        if item.name.casefold() == "inside board components":
            return item
    for item in candidates:
        if "component" in item.name.casefold():
            return item
    return candidates[0]


def _component_comment_texts_by_index(payload: AltiumLayout) -> dict[int, str]:
    result: dict[int, str] = {}
    for text in sorted(payload.texts or [], key=lambda item: item.index):
        component_index = text.component
        if component_index in ALTIUM_UNCONNECTED_INDEXES or component_index in result:
            continue
        value = _component_comment_text(text)
        if value:
            result[component_index] = value
    return result


def _component_comment_text(text: AltiumText) -> str | None:
    if not text.is_comment:
        return None
    value = text.text.strip()
    if not value or value.casefold() == ".designator":
        return None
    return value


def _semantic_pads(
    payload: AltiumLayout,
    component_ids_by_index: dict[int, str],
    footprint_ids_by_component: dict[int, str],
    net_ids_by_index: dict[int, str],
    top_layer: str | None,
    bottom_layer: str | None,
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[object, ...]], str],
    pins: list[SemanticPin],
    pads: list[SemanticPad],
    components_by_id: dict[str, SemanticComponent],
    footprints_by_id: dict[str, SemanticFootprint],
    nets_by_id: dict[str, SemanticNet],
) -> None:
    for index, pad in enumerate(payload.pads or []):
        if _is_unnamed_no_net_component_pad(pad):
            continue
        component_id = _component_id(pad.component, component_ids_by_index)
        footprint_id = (
            footprint_ids_by_component.get(pad.component) if component_id else None
        )
        net_id = _net_id(pad.net, net_ids_by_index)
        layer_name = _pad_layer_name(
            pad, component_id, components_by_id, top_layer, bottom_layer
        )
        shape_kind, size = _pad_shape_and_size(pad, layer_name, top_layer, bottom_layer)
        shape_id = _shape_id_for_size(
            shapes,
            shape_ids_by_key,
            shape_kind=shape_kind,
            width=size.x,
            height=size.y,
            source_path=f"pads[{index}]",
            source_key=pad.name or pad.index,
        )

        pad_id = semantic_id(
            "pad", f"{component_id or 'free'}:{pad.name or index}:{pad.index}"
        )
        pin_id = None
        if component_id is not None:
            pin_name = pad.name or str(index)
            pin_id = semantic_id("pin", f"{component_id}:{pin_name}:{pad.index}")
            pins.append(
                SemanticPin(
                    id=pin_id,
                    name=pin_name,
                    component_id=component_id,
                    net_id=net_id,
                    pad_ids=[pad_id],
                    layer_name=layer_name,
                    position=_point(pad.position),
                    source=source_ref("altium", f"pads[{index}].name", pad.name),
                )
            )
            unique_append(components_by_id[component_id].pin_ids, pin_id)

        pads.append(
            SemanticPad(
                id=pad_id,
                name=pad.name or str(index),
                footprint_id=footprint_id,
                component_id=component_id,
                pin_id=pin_id,
                net_id=net_id,
                layer_name=layer_name,
                position=_point(pad.position),
                padstack_definition=pad.pad_mode,
                geometry=SemanticPadGeometry(
                    shape_id=shape_id,
                    source="altium_pad",
                    rotation=radians(pad.direction),
                    shape_kind=shape_kind,
                ),
                source=source_ref("altium", f"pads[{index}]", pad.name or pad.index),
            )
        )

        if component_id is not None:
            unique_append(components_by_id[component_id].pad_ids, pad_id)
        if footprint_id is not None and footprint_id in footprints_by_id:
            unique_append(footprints_by_id[footprint_id].pad_ids, pad_id)
        if net_id is not None and net_id in nets_by_id:
            unique_append(nets_by_id[net_id].pad_ids, pad_id)
            if pin_id is not None:
                unique_append(nets_by_id[net_id].pin_ids, pin_id)


def _is_unnamed_no_net_component_pad(pad: AltiumPad) -> bool:
    return (
        not pad.name.strip()
        and pad.net in ALTIUM_UNCONNECTED_INDEXES
        and pad.component not in ALTIUM_NO_COMPONENT_INDEXES
    )


def _semantic_via_templates(
    payload: AltiumLayout,
    metal_layer_names: list[str],
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[object, ...]], str],
) -> tuple[list[SemanticViaTemplate], dict[tuple[object, ...], str]]:
    templates: list[SemanticViaTemplate] = []
    ids_by_key: dict[tuple[object, ...], str] = {}

    for index, via in enumerate(payload.vias or []):
        key = _via_template_key(via)
        if key in ids_by_key:
            continue
        template_id = semantic_id("via_template", f"altium:{len(templates)}:{key}")
        ids_by_key[key] = template_id

        hole = via.hole_size if via.hole_size > 0 else DEFAULT_VIA_HOLE_MIL
        diameter = via.diameter if via.diameter > 0 else DEFAULT_VIA_DIAMETER_MIL
        barrel_shape_id = _shape_id(
            shapes,
            shape_ids_by_key,
            kind="circle",
            auroradb_type="Circle",
            values=[0.0, 0.0, hole],
            source_path=f"vias[{index}].hole_size",
            source_key=via.index,
        )
        layer_pads = []
        span = _layer_span(metal_layer_names, via.start_layer_name, via.end_layer_name)
        for layer_index, layer_name in enumerate(span):
            pad_diameter = _via_layer_diameter(via, layer_index, diameter)
            pad_shape_id = _shape_id(
                shapes,
                shape_ids_by_key,
                kind="circle",
                auroradb_type="Circle",
                values=[0.0, 0.0, pad_diameter],
                source_path=f"vias[{index}].diameter",
                source_key=f"{via.index}:{layer_name}",
            )
            layer_pads.append(
                SemanticViaTemplateLayer(
                    layer_name=layer_name,
                    pad_shape_id=pad_shape_id,
                )
            )

        templates.append(
            SemanticViaTemplate(
                id=template_id,
                name=f"AltiumVia_{len(templates)}",
                barrel_shape_id=barrel_shape_id,
                layer_pads=layer_pads,
                geometry=SemanticViaTemplateGeometry(
                    source="altium_via",
                    drill_layer=f"{via.start_layer_name}:{via.end_layer_name}",
                ),
                source=source_ref("altium", f"vias[{index}]", via.index),
            )
        )
    return templates, ids_by_key


def _semantic_vias(
    payload: AltiumLayout,
    metal_layer_names: list[str],
    net_ids_by_index: dict[int, str],
    via_template_ids_by_key: dict[tuple[object, ...], str],
    nets_by_id: dict[str, SemanticNet],
) -> list[SemanticVia]:
    vias: list[SemanticVia] = []
    for index, via in enumerate(payload.vias or []):
        net_id = _net_id(via.net, net_ids_by_index)
        via_id = semantic_id("via", f"altium:{via.index}")
        vias.append(
            SemanticVia(
                id=via_id,
                name=f"Via{via.index}",
                template_id=via_template_ids_by_key.get(_via_template_key(via)),
                net_id=net_id,
                layer_names=_layer_span(
                    metal_layer_names, via.start_layer_name, via.end_layer_name
                ),
                position=_point(via.position),
                geometry=SemanticViaGeometry(rotation=0.0),
                source=source_ref("altium", f"vias[{index}]", via.index),
            )
        )
        if net_id is not None and net_id in nets_by_id:
            unique_append(nets_by_id[net_id].via_ids, via_id)
    return vias


def _semantic_primitives(
    payload: AltiumLayout,
    net_ids_by_index: dict[int, str],
    nets_by_id: dict[str, SemanticNet],
    component_ids_by_index: dict[int, str],
) -> list[SemanticPrimitive]:
    primitives: list[SemanticPrimitive] = []

    for index, track in enumerate(payload.tracks or []):
        primitive = _track_primitive(
            track, index, net_ids_by_index, component_ids_by_index
        )
        _append_primitive(primitive, primitives, nets_by_id)

    for index, arc in enumerate(payload.arcs or []):
        primitive = _arc_primitive(arc, index, net_ids_by_index, component_ids_by_index)
        _append_primitive(primitive, primitives, nets_by_id)

    for index, fill in enumerate(payload.fills or []):
        primitive = _fill_primitive(
            fill, index, net_ids_by_index, component_ids_by_index
        )
        _append_primitive(primitive, primitives, nets_by_id)

    for index, region in enumerate(payload.regions or []):
        primitive = _region_primitive(
            region, index, net_ids_by_index, component_ids_by_index
        )
        _append_primitive(primitive, primitives, nets_by_id)

    for index, polygon in enumerate(payload.polygons or []):
        primitive = _polygon_primitive(polygon, index, net_ids_by_index)
        _append_primitive(primitive, primitives, nets_by_id)

    return primitives


def _append_primitive(
    primitive: SemanticPrimitive | None,
    primitives: list[SemanticPrimitive],
    nets_by_id: dict[str, SemanticNet],
) -> None:
    if primitive is None:
        return
    primitives.append(primitive)
    if primitive.net_id is not None and primitive.net_id in nets_by_id:
        unique_append(nets_by_id[primitive.net_id].primitive_ids, primitive.id)


def _track_primitive(
    track: AltiumTrack,
    index: int,
    net_ids_by_index: dict[int, str],
    component_ids_by_index: dict[int, str],
) -> SemanticPrimitive | None:
    if not _is_valid_point(track.start) or not _is_valid_point(track.end):
        return None
    return SemanticPrimitive(
        id=semantic_id("primitive", f"track:{track.index}"),
        kind="keepout" if track.is_keepout else "trace",
        layer_name=track.layer_name,
        net_id=None if track.is_keepout else _net_id(track.net, net_ids_by_index),
        component_id=_component_id(track.component, component_ids_by_index),
        geometry=SemanticPrimitiveGeometry(
            record_kind="TRACK",
            width=track.width,
            center_line=[
                _point_values(track.start),
                _point_values(track.end),
            ],
            feature_id=track.polygon,
        ),
        source=source_ref("altium", f"tracks[{index}]", track.index),
    )


def _arc_primitive(
    arc: AltiumArc,
    index: int,
    net_ids_by_index: dict[int, str],
    component_ids_by_index: dict[int, str],
) -> SemanticPrimitive | None:
    geometry = _arc_geometry(arc.center, arc.radius, arc.start_angle, arc.end_angle)
    if geometry is None:
        return None
    return SemanticPrimitive(
        id=semantic_id("primitive", f"arc:{arc.index}"),
        kind="keepout" if arc.is_keepout else "arc",
        layer_name=arc.layer_name,
        net_id=None if arc.is_keepout else _net_id(arc.net, net_ids_by_index),
        component_id=_component_id(arc.component, component_ids_by_index),
        geometry=SemanticPrimitiveGeometry(
            record_kind="ARC",
            width=arc.width,
            start=geometry.start,
            end=geometry.end,
            center=geometry.center,
            radius=arc.radius,
            clockwise=geometry.get("clockwise"),
            is_ccw=geometry.is_ccw,
            feature_id=arc.polygon,
        ),
        source=source_ref("altium", f"arcs[{index}]", arc.index),
    )


def _fill_primitive(
    fill: AltiumFill,
    index: int,
    net_ids_by_index: dict[int, str],
    component_ids_by_index: dict[int, str],
) -> SemanticPrimitive | None:
    raw_points = _rotated_rectangle_points(
        fill.position1, fill.position2, fill.rotation
    )
    if len(raw_points) < 2:
        return None
    return SemanticPrimitive(
        id=semantic_id("primitive", f"fill:{fill.index}"),
        kind="keepout" if fill.is_keepout else "polygon",
        layer_name=fill.layer_name,
        net_id=None if fill.is_keepout else _net_id(fill.net, net_ids_by_index),
        component_id=_component_id(fill.component, component_ids_by_index),
        geometry=SemanticPrimitiveGeometry(
            record_kind="FILL",
            raw_points=raw_points,
            rotation=radians(fill.rotation),
            bbox=_bbox(raw_points),
        ),
        source=source_ref("altium", f"fills[{index}]", fill.index),
    )


def _region_primitive(
    region: AltiumRegion,
    index: int,
    net_ids_by_index: dict[int, str],
    component_ids_by_index: dict[int, str],
) -> SemanticPrimitive | None:
    raw_points = _vertex_points(region.outline)
    if len(raw_points) < 2:
        return None
    voids = [
        SemanticPolygonVoidGeometry(
            raw_points=_vertex_points(hole),
            arcs=_vertex_arcs(hole),
            source_contour_index=hole_index,
        )
        for hole_index, hole in enumerate(region.holes)
        if len(_vertex_points(hole)) >= 2
    ]
    return SemanticPrimitive(
        id=semantic_id("primitive", f"region:{region.index}"),
        kind="keepout" if region.is_keepout else "polygon",
        layer_name=region.layer_name,
        net_id=None if region.is_keepout else _net_id(region.net, net_ids_by_index),
        component_id=_component_id(region.component, component_ids_by_index),
        geometry=SemanticPrimitiveGeometry(
            record_kind="REGION",
            raw_points=raw_points,
            arcs=_vertex_arcs(region.outline),
            voids=voids,
            has_voids=bool(voids),
            feature_id=region.polygon,
            bbox=_bbox(raw_points),
        ),
        source=source_ref("altium", f"regions[{index}]", region.index),
    )


def _polygon_primitive(
    polygon: AltiumPolygon,
    index: int,
    net_ids_by_index: dict[int, str],
) -> SemanticPrimitive | None:
    raw_points = _vertex_points(polygon.vertices)
    if len(raw_points) < 2:
        return None
    return SemanticPrimitive(
        id=semantic_id("primitive", f"polygon:{polygon.index}"),
        kind="polygon",
        layer_name=polygon.layer_name,
        net_id=_net_id(polygon.net, net_ids_by_index),
        geometry=SemanticPrimitiveGeometry(
            record_kind="POLYGON",
            raw_points=raw_points,
            arcs=_vertex_arcs(polygon.vertices),
            feature_id=polygon.pour_index,
            bbox=_bbox(raw_points),
        ),
        source=source_ref("altium", f"polygons[{index}]", polygon.index),
    )


def _board_outline(payload: AltiumLayout) -> SemanticBoardOutlineGeometry:
    if payload.board is None or not payload.board.outline:
        return SemanticBoardOutlineGeometry()
    values = [
        _point_tuple_value(point) for point in _vertex_points(payload.board.outline)
    ]
    if len(values) < 2:
        return SemanticBoardOutlineGeometry()
    return SemanticBoardOutlineGeometry(
        kind="polygon",
        auroradb_type="Polygon",
        source="altium_board_outline",
        path_count=len(payload.board.outline),
        values=[len(values), *values, "Y", "Y"],
    )


def _shape_id_for_size(
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[object, ...]], str],
    *,
    shape_kind: str,
    width: float,
    height: float,
    source_path: str,
    source_key: object,
) -> str:
    kind, auroradb_type, values = _shape_geometry(shape_kind, width, height)
    return _shape_id(
        shapes,
        shape_ids_by_key,
        kind=kind,
        auroradb_type=auroradb_type,
        values=values,
        source_path=source_path,
        source_key=source_key,
    )


def _shape_geometry(
    shape_kind: str,
    width: float,
    height: float,
) -> tuple[str, str, list[object]]:
    shape_text = (shape_kind or "").casefold()
    width = abs(width or DEFAULT_PAD_SIZE_MIL)
    height = abs(height or width)
    if "circle" in shape_text or "round" in shape_text and "rect" not in shape_text:
        return ("circle", "Circle", [0.0, 0.0, max(width, height)])
    if "oval" in shape_text or "rounded" in shape_text:
        radius = min(width, height) / 2.0
        return (
            "rounded_rectangle",
            "RoundedRectangle",
            [0.0, 0.0, width, height, radius],
        )
    return ("rectangle", "Rectangle", [0.0, 0.0, width, height])


def _shape_id(
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[object, ...]], str],
    *,
    kind: str,
    auroradb_type: str,
    values: list[object],
    source_path: str,
    source_key: object,
) -> str:
    key = (
        auroradb_type,
        tuple(
            round(float(value), 9) if isinstance(value, (float, int)) else value
            for value in values
        ),
    )
    existing = shape_ids_by_key.get(key)
    if existing is not None:
        return existing
    shape_id = semantic_id("shape", f"{auroradb_type}_{len(shapes)}")
    shape_ids_by_key[key] = shape_id
    shapes.append(
        SemanticShape(
            id=shape_id,
            kind=kind,
            auroradb_type=auroradb_type,
            values=values,
            source=source_ref("altium", source_path, source_key),
        )
    )
    return shape_id


def _pad_shape_and_size(
    pad: AltiumPad,
    layer_name: str | None,
    top_layer: str | None,
    bottom_layer: str | None,
):
    side = side_from_layer_name(layer_name)
    if side == "bottom" or (bottom_layer and layer_name == bottom_layer):
        return pad.bottom_shape, pad.bottom_size
    if side == "top" or (top_layer and layer_name == top_layer):
        return pad.top_shape, pad.top_size
    return pad.mid_shape, pad.mid_size


def _pad_layer_name(
    pad: AltiumPad,
    component_id: str | None,
    components_by_id: dict[str, SemanticComponent],
    top_layer: str | None,
    bottom_layer: str | None,
) -> str | None:
    text = pad.layer_name
    if text and "multi" not in text.casefold():
        return text
    if component_id is not None:
        component = components_by_id.get(component_id)
        if component and component.side == "bottom":
            return bottom_layer or component.layer_name or text
    return top_layer or text


def _component_layer_name(
    component: AltiumComponent,
    top_layer: str | None,
    bottom_layer: str | None,
) -> str:
    if component.layer_name and "multi" not in component.layer_name.casefold():
        return component.layer_name
    side = _layer_side(component.layer_id, component.layer_name)
    if side == "bottom":
        return bottom_layer or component.layer_name
    return top_layer or component.layer_name


def _footprint_name(component: AltiumComponent) -> str:
    return (
        component.pattern
        or component.source_lib_reference
        or component.source_footprint_library
        or f"AltiumFootprint{component.index}"
    )


def _component_attributes(component: AltiumComponent) -> dict[str, str]:
    attributes = _component_library_attributes(component)
    for key, value in {
        "source_unique_id": component.source_unique_id,
        "source_hierarchical_path": component.source_hierarchical_path,
    }.items():
        if value:
            attributes[key] = value
    for key, value in component.properties.items():
        if value:
            attributes[f"property.{key}"] = value
    return attributes


def _component_library_attributes(component: AltiumComponent) -> dict[str, str]:
    return {
        key: value
        for key, value in {
            "source_footprint_library": component.source_footprint_library,
            "source_component_library": component.source_component_library,
            "source_lib_reference": component.source_lib_reference,
        }.items()
        if value
    }


def _via_template_key(via: AltiumVia) -> tuple[object, ...]:
    fallback = via.diameter if via.diameter > 0 else DEFAULT_VIA_DIAMETER_MIL
    return (
        round(via.diameter, 9),
        round(via.hole_size, 9),
        via.start_layer_name,
        via.end_layer_name,
        via.via_mode,
        tuple(
            round(_normalized_via_layer_diameter(value, fallback), 9)
            for value in via.diameter_by_layer
        ),
    )


def _via_layer_diameter(via: AltiumVia, layer_index: int, fallback: float) -> float:
    if layer_index < len(via.diameter_by_layer):
        return _normalized_via_layer_diameter(
            via.diameter_by_layer[layer_index],
            fallback,
        )
    return fallback


def _normalized_via_layer_diameter(value: float, fallback: float) -> float:
    if value <= 0 or not isfinite(value):
        return fallback
    scaled = value / 256.0
    if fallback > 0 and abs(scaled - fallback) <= max(0.01, fallback * 0.05):
        return fallback
    if value > max(500.0, fallback * 10.0):
        if fallback <= 0 or fallback * 0.5 <= scaled <= fallback * 2.0:
            return scaled
        return fallback
    return value


def _layer_span(
    metal_layer_names: list[str], start_layer: str, end_layer: str
) -> list[str]:
    if start_layer in metal_layer_names and end_layer in metal_layer_names:
        start = metal_layer_names.index(start_layer)
        end = metal_layer_names.index(end_layer)
        low, high = sorted((start, end))
        return metal_layer_names[low : high + 1]
    values: list[str] = []
    unique_append(values, start_layer)
    unique_append(values, end_layer)
    return values


def _arc_geometry(
    center: AltiumPoint, radius: float, start_angle: float, end_angle: float
) -> SemanticArcGeometry | None:
    if not _is_valid_point(center):
        return None
    start = _arc_point(center, radius, start_angle)
    end = _arc_point(center, radius, end_angle)
    span = (end_angle - start_angle) % 360.0
    clockwise = span > 0.0
    center_values = _point_values(center)
    return SemanticArcGeometry(
        start=start,
        end=end,
        center=center_values,
        radius=radius,
        clockwise=clockwise,
        is_ccw=not clockwise,
    )


def _arc_point(center: AltiumPoint, radius: float, angle: float) -> list[float]:
    angle_radians = radians(angle)
    center_x, center_y = _point_values(center)
    return [
        center_x + radius * cos(angle_radians),
        center_y + radius * sin(angle_radians),
    ]


def _vertex_points(vertices: Iterable[AltiumVertex]) -> list[list[float]]:
    return [
        _point_values(vertex.position)
        for vertex in vertices
        if _is_valid_point(vertex.position)
    ]


def _point_tuple_value(point: list[float]) -> str:
    return f"({point[0]:.12g},{point[1]:.12g})"


def _vertex_arcs(vertices: Iterable[AltiumVertex]) -> list[SemanticArcGeometry]:
    arcs: list[SemanticArcGeometry] = []
    for vertex in vertices:
        if (
            not vertex.is_round
            or vertex.center is None
            or not _is_valid_point(vertex.position)
        ):
            continue
        geometry = _arc_geometry(
            vertex.center,
            vertex.radius,
            vertex.start_angle,
            vertex.end_angle,
        )
        if geometry is not None:
            arcs.append(geometry)
    return arcs


def _rotated_rectangle_points(
    position1: AltiumPoint, position2: AltiumPoint, rotation: float
) -> list[list[float]]:
    if not _is_valid_point(position1) or not _is_valid_point(position2):
        return []
    point1 = _point_values(position1)
    point2 = _point_values(position2)
    x1, x2 = sorted((point1[0], point2[0]))
    y1, y2 = sorted((point1[1], point2[1]))
    points = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    if abs(rotation) < 1e-9:
        return points
    center_x = (x1 + x2) / 2.0
    center_y = (y1 + y2) / 2.0
    angle = radians(rotation)
    result = []
    for x, y in points:
        dx = x - center_x
        dy = y - center_y
        result.append(
            [
                center_x + dx * cos(angle) - dy * sin(angle),
                center_y + dx * sin(angle) + dy * cos(angle),
            ]
        )
    return result


def _bbox(points: list[list[float | int | None]]) -> list[float] | None:
    clean = [(float(x), float(y)) for x, y in points if x is not None and y is not None]
    if not clean:
        return None
    xs = [point[0] for point in clean]
    ys = [point[1] for point in clean]
    return [min(xs), min(ys), max(xs), max(ys)]


def _point(point: AltiumPoint) -> SemanticPoint:
    x, y = _point_values(point)
    return SemanticPoint(x=x, y=y)


def _point_values(point: AltiumPoint) -> list[float]:
    return [_clean_coordinate(point.x), _clean_coordinate(-point.y)]


def _is_valid_point(point: AltiumPoint) -> bool:
    return (
        abs(point.x_raw) < ALTIUM_INVALID_COORD_RAW_ABS
        and abs(point.y_raw) < ALTIUM_INVALID_COORD_RAW_ABS
        and isfinite(point.x)
        and isfinite(point.y)
    )


def _clean_coordinate(value: float) -> float:
    return 0.0 if abs(value) < 1e-12 else value


def _semantic_units(payload: AltiumLayout) -> str:
    units = (payload.summary.units or "").strip().casefold()
    if units in {"mil", "mils"}:
        return "mil"
    if units in {"mm", "millimeter", "millimeters"}:
        return "mm"
    return "mil"


def _net_id(net_index: int, net_ids_by_index: dict[int, str]) -> str | None:
    if _is_unconnected_net(net_index):
        return net_ids_by_index.get(net_index) or semantic_id("net", "NoNet")
    return net_ids_by_index.get(net_index)


def _component_id(
    component_index: int, component_ids_by_index: dict[int, str]
) -> str | None:
    if component_index in ALTIUM_NO_COMPONENT_INDEXES:
        return None
    return component_ids_by_index.get(component_index)


def _referenced_net_indexes(payload: AltiumLayout) -> set[int]:
    referenced: set[int] = set()
    for pad in payload.pads or []:
        referenced.add(pad.net)
    for via in payload.vias or []:
        referenced.add(via.net)
    for track in payload.tracks or []:
        referenced.add(track.net)
    for arc in payload.arcs or []:
        referenced.add(arc.net)
    for fill in payload.fills or []:
        referenced.add(fill.net)
    for region in payload.regions or []:
        referenced.add(region.net)
    for polygon in payload.polygons or []:
        referenced.add(polygon.net)
    return referenced


def _is_unconnected_net(net_index: int) -> bool:
    return net_index in ALTIUM_UNCONNECTED_INDEXES


def _source_stackup_copper_layer_items(
    layers: list[AltiumLayer],
) -> list[tuple[int, AltiumLayer]]:
    indexed_by_id: dict[int, tuple[int, AltiumLayer]] = {
        layer.layer_id: (index, layer) for index, layer in enumerate(layers)
    }
    current_id = 1
    seen_ids: set[int] = set()
    stackup: list[tuple[int, AltiumLayer]] = []

    while current_id and current_id not in seen_ids:
        seen_ids.add(current_id)
        item = indexed_by_id.get(current_id)
        if item is None:
            break
        _index, layer = item
        if _is_source_stackup_copper_layer(layer):
            stackup.append(item)
        next_id = layer.next_id or 0
        if next_id == 0:
            break
        current_id = next_id

    if stackup and stackup[-1][1].layer_id == 32:
        return stackup
    return []


def _is_source_stackup_copper_layer(layer: AltiumLayer) -> bool:
    return (
        _is_altium_signal_layer_id(layer.layer_id)
        or _is_altium_plane_layer_id(layer.layer_id)
    ) and not layer.mechanical_enabled


def _is_source_fallback_copper_layer(layer: AltiumLayer) -> bool:
    return 1 <= layer.layer_id <= 32 and not layer.mechanical_enabled


def _is_altium_signal_layer_id(layer_id: int) -> bool:
    return 1 <= layer_id <= 32


def _is_altium_plane_layer_id(layer_id: int) -> bool:
    return 39 <= layer_id <= 54


def _source_copper_layer_role(layer: AltiumLayer) -> str:
    if _is_altium_plane_layer_id(layer.layer_id):
        return "plane"
    return "signal"


def _is_metal_layer(layer: SemanticLayer) -> bool:
    return layer.role in {"signal", "plane"} and layer.material_id == COPPER_MATERIAL_ID


def _layer_name(layer: AltiumLayer) -> str:
    return layer.name or f"Layer{layer.layer_id}"


def _layer_side(layer_id: int, name: str | None) -> str:
    if layer_id == 1:
        return "top"
    if layer_id == 32:
        return "bottom"
    return side_from_layer_name(name) or "internal"


def _source_layer_names(payload: AltiumLayout) -> Iterable[str]:
    for collection_name in ("pads", "tracks", "arcs", "fills", "regions", "polygons"):
        for item in getattr(payload, collection_name) or []:
            layer_name = getattr(item, "layer_name", None)
            if layer_name:
                yield layer_name


def _is_probable_copper_layer_name(name: str) -> bool:
    text = name.casefold()
    if "multi" in text:
        return False
    return any(token in text for token in ("top", "bottom", "mid", "signal", "layer"))


def _layer_name_sort_key(name: str) -> tuple[int, str]:
    side = side_from_layer_name(name)
    if side == "top":
        return (0, name)
    if side == "bottom":
        return (999, name)
    return (100, name)


def _top_layer_name(layers: list[SemanticLayer]) -> str | None:
    for layer in layers:
        if layer.side == "top":
            return layer.name
    return layers[0].name if layers else None


def _bottom_layer_name(layers: list[SemanticLayer]) -> str | None:
    for layer in reversed(layers):
        if layer.side == "bottom":
            return layer.name
    return layers[-1].name if layers else None
