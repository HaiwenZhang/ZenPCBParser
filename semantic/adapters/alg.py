from __future__ import annotations

from collections import defaultdict
from math import radians
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
    SemanticComponent,
    SemanticDiagnostic,
    SemanticFootprint,
    SemanticLayer,
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
from aurora_translator.sources.alg.models import (
    ALGComponent,
    ALGLayout,
    ALGPad,
    ALGPin,
    ALGPoint,
    ALGShape,
    ALGSymbol,
    ALGTrack,
)


DEFAULT_PAD_SIZE_MIL = 10.0
DEFAULT_VIA_SIZE_MIL = 16.0
MIL_TO_MM = 0.0254


def from_alg(payload: ALGLayout, *, build_connectivity: bool = True) -> SemanticBoard:
    diagnostics = _source_diagnostics(payload)
    layers = _semantic_layers(payload)
    metal_layer_names = [layer.name for layer in layers if _is_metal_layer(layer)]
    top_layer = _top_layer_name(layers)
    bottom_layer = _bottom_layer_name(layers)

    net_names = _net_names(payload)
    nets = [
        SemanticNet(
            id=semantic_id("net", name, index),
            name=name,
            role=role_from_net_name(name),
            source=source_ref("alg", "net_names", name),
        )
        for index, name in enumerate(net_names)
    ]
    net_ids_by_name = {net.name: net.id for net in nets}

    shapes: list[SemanticShape] = []
    shape_ids_by_key: dict[tuple[str, tuple[float, ...]], str] = {}

    components_by_refdes = _components_by_refdes(payload)
    symbols_by_refdes = _symbols_by_refdes(payload)
    pins_by_refdes_pin = _pins_by_refdes_pin(payload)
    source_pads_by_refdes_pin = _pads_by_refdes_pin(payload)

    footprints = _semantic_footprints(components_by_refdes)
    footprint_ids_by_name = {footprint.name: footprint.id for footprint in footprints}
    components = _semantic_components(
        components_by_refdes,
        symbols_by_refdes,
        pins_by_refdes_pin,
        footprint_ids_by_name,
        top_layer,
        bottom_layer,
    )
    components_by_id = {component.id: component for component in components}
    component_ids_by_refdes = {
        component.refdes or component.name or component.id: component.id
        for component in components
    }

    pins: list[SemanticPin] = []
    pads: list[SemanticPad] = []
    pin_ids_by_key: dict[tuple[str, str], str] = {}
    component_pad_ids: dict[str, list[str]] = defaultdict(list)
    footprint_pad_ids: dict[str, list[str]] = defaultdict(list)
    _semantic_pins_and_pads(
        payload,
        pins_by_refdes_pin,
        source_pads_by_refdes_pin,
        components_by_refdes,
        component_ids_by_refdes,
        footprint_ids_by_name,
        net_ids_by_name,
        top_layer,
        shapes,
        shape_ids_by_key,
        pins,
        pads,
        pin_ids_by_key,
        component_pad_ids,
        footprint_pad_ids,
        diagnostics,
    )

    for component in components:
        component.pin_ids = [pin.id for pin in pins if pin.component_id == component.id]
        component.pad_ids = component_pad_ids.get(component.id, [])
    for footprint in footprints:
        footprint.pad_ids = footprint_pad_ids.get(footprint.id, [])

    via_templates, via_template_ids = _semantic_via_templates(
        payload,
        metal_layer_names,
        shapes,
        shape_ids_by_key,
    )
    vias = _semantic_vias(payload, metal_layer_names, net_ids_by_name, via_template_ids)
    primitives = _semantic_primitives(payload, net_ids_by_name)

    board = SemanticBoard(
        metadata=SemanticMetadata(
            source_format="alg",
            source=payload.metadata.source,
            source_parser_version=payload.metadata.parser_version,
            source_schema_version=payload.metadata.output_schema_version,
        ),
        units=_semantic_units(payload),
        summary=SemanticSummary(),
        layers=layers,
        shapes=shapes,
        via_templates=via_templates,
        nets=nets,
        components=list(components_by_id.values()),
        footprints=footprints,
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


def _source_diagnostics(payload: ALGLayout) -> list[SemanticDiagnostic]:
    return [
        SemanticDiagnostic(
            severity="warning",
            code="alg.source_diagnostic",
            message=message,
            source=source_ref("alg", "diagnostics"),
        )
        for message in payload.diagnostics
    ]


def _semantic_layers(payload: ALGLayout) -> list[SemanticLayer]:
    layers: list[SemanticLayer] = []
    conductor_layers = [layer for layer in payload.layers or [] if layer.conductor]
    conductor_count = len(conductor_layers)
    conductor_index = 0
    for index, layer in enumerate(payload.layers or []):
        if not layer.conductor or not layer.name:
            continue
        role = _layer_role(layer.layer_type, layer.use_kind, layer.shield_layer)
        side = side_from_layer_name(layer.name)
        if side is None:
            if conductor_index == 0:
                side = "top"
            elif conductor_index == conductor_count - 1:
                side = "bottom"
            else:
                side = "internal"
        layers.append(
            SemanticLayer(
                id=semantic_id("layer", layer.name, index),
                name=layer.name,
                layer_type=layer.layer_type,
                role=role,
                side=side,
                order_index=len(layers),
                material=layer.material,
                thickness=layer.thickness,
                source=source_ref("alg", f"layers[{index}]", layer.name),
            )
        )
        conductor_index += 1
    return layers


def _layer_role(
    layer_type: str | None, use_kind: str | None, shield_layer: str | None
) -> str:
    text = " ".join(
        value or "" for value in [layer_type, use_kind, shield_layer]
    ).casefold()
    if "plane" in text or "shield" in text:
        return "plane"
    return "signal"


def _is_metal_layer(layer: SemanticLayer) -> bool:
    return (layer.role or "").casefold() in {"signal", "plane"}


def _top_layer_name(layers: list[SemanticLayer]) -> str | None:
    for layer in layers:
        if layer.side == "top":
            return layer.name
    return layers[0].name if layers else None


def _bottom_layer_name(layers: list[SemanticLayer]) -> str | None:
    for layer in layers:
        if layer.side == "bottom":
            return layer.name
    return layers[-1].name if layers else None


def _components_by_refdes(payload: ALGLayout) -> dict[str, ALGComponent]:
    result = {component.refdes: component for component in payload.components or []}
    for pin in payload.pins or []:
        if pin.refdes not in result:
            result[pin.refdes] = ALGComponent(refdes=pin.refdes)
    return result


def _symbols_by_refdes(payload: ALGLayout) -> dict[str, ALGSymbol]:
    return {
        symbol.refdes: symbol
        for symbol in payload.symbols or []
        if symbol.refdes and (symbol.sym_type or "").casefold() == "package"
    }


def _pins_by_refdes_pin(payload: ALGLayout) -> dict[tuple[str, str], ALGPin]:
    return {
        (pin.refdes, pin.pin_number): pin
        for pin in payload.pins or []
        if pin.refdes and pin.pin_number
    }


def _pads_by_refdes_pin(payload: ALGLayout) -> dict[tuple[str, str], list[ALGPad]]:
    result: dict[tuple[str, str], list[ALGPad]] = defaultdict(list)
    for pad in payload.pads or []:
        if pad.refdes and pad.pin_number:
            result[(pad.refdes, pad.pin_number)].append(pad)
    return result


def _semantic_footprints(
    components_by_refdes: dict[str, ALGComponent],
) -> list[SemanticFootprint]:
    names: dict[str, str] = {}
    for component in components_by_refdes.values():
        name = component.package or component.device_type or "ALG_FOOTPRINT"
        names.setdefault(name, semantic_id("footprint", name))
    return [
        SemanticFootprint(
            id=footprint_id,
            name=name,
            source=source_ref("alg", "components.package", name),
        )
        for name, footprint_id in sorted(names.items())
    ]


def _semantic_components(
    components_by_refdes: dict[str, ALGComponent],
    symbols_by_refdes: dict[str, ALGSymbol],
    pins_by_refdes_pin: dict[tuple[str, str], ALGPin],
    footprint_ids_by_name: dict[str, str],
    top_layer: str | None,
    bottom_layer: str | None,
) -> list[SemanticComponent]:
    components: list[SemanticComponent] = []
    pins_by_component: dict[str, list[ALGPin]] = defaultdict(list)
    for (refdes, _pin_number), pin in pins_by_refdes_pin.items():
        pins_by_component[refdes].append(pin)
    for index, (refdes, component) in enumerate(sorted(components_by_refdes.items())):
        symbol = symbols_by_refdes.get(refdes)
        mirror = bool(symbol and symbol.mirror)
        side = "bottom" if mirror else "top"
        layer_name = bottom_layer if mirror else top_layer
        footprint_name = component.package or component.device_type or "ALG_FOOTPRINT"
        components.append(
            SemanticComponent(
                id=semantic_id("component", refdes, index),
                refdes=refdes,
                name=refdes,
                part_name=component.device_type or component.package,
                package_name=footprint_name,
                footprint_id=footprint_ids_by_name.get(footprint_name),
                layer_name=layer_name,
                side=side,
                value=component.value,
                location=_point(symbol.location if symbol else None)
                or _average_pin_point(pins_by_component.get(refdes, [])),
                rotation=radians(symbol.rotation or 0.0) if symbol else 0.0,
                attributes=_component_attributes(component, symbol),
                source=source_ref("alg", "components", refdes),
            )
        )
    return components


def _component_attributes(
    component: ALGComponent, symbol: ALGSymbol | None
) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, value in {
        "class": component.class_name,
        "part_number": component.part_number,
        "room": component.room,
        "bom_ignore": component.bom_ignore,
        "symbol": symbol.sym_name if symbol else None,
        "mirror": "YES" if symbol and symbol.mirror else None,
        "library_path": symbol.library_path if symbol else None,
    }.items():
        if value not in {None, ""}:
            values[key] = str(value)
    return values


def _semantic_pins_and_pads(
    payload: ALGLayout,
    pins_by_refdes_pin: dict[tuple[str, str], ALGPin],
    source_pads_by_refdes_pin: dict[tuple[str, str], list[ALGPad]],
    components_by_refdes: dict[str, ALGComponent],
    component_ids_by_refdes: dict[str, str],
    footprint_ids_by_name: dict[str, str],
    net_ids_by_name: dict[str, str],
    top_layer: str | None,
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[float, ...]], str],
    pins: list[SemanticPin],
    pads: list[SemanticPad],
    pin_ids_by_key: dict[tuple[str, str], str],
    component_pad_ids: dict[str, list[str]],
    footprint_pad_ids: dict[str, list[str]],
    diagnostics: list[SemanticDiagnostic],
) -> None:
    for index, ((refdes, pin_number), pin) in enumerate(pins_by_refdes_pin.items()):
        component_id = component_ids_by_refdes.get(refdes)
        component = components_by_refdes.get(refdes)
        footprint_name = (
            component.package or component.device_type or "ALG_FOOTPRINT"
            if component
            else "ALG_FOOTPRINT"
        )
        footprint_id = footprint_ids_by_name.get(footprint_name)
        net_id = net_ids_by_name.get(pin.net_name or "")
        pin_id = semantic_id("pin", f"{refdes}:{pin_number}", index)
        pin_ids_by_key[(refdes, pin_number)] = pin_id
        matching_pads = source_pads_by_refdes_pin.get((refdes, pin_number), [])
        pad_ids: list[str] = []
        if matching_pads:
            for pad_index, source_pad in enumerate(matching_pads):
                pad_id = semantic_id(
                    "pad", f"{refdes}:{pin_number}:{source_pad.layer_name}:{pad_index}"
                )
                shape_id = _shape_id_for_alg_shape(
                    source_pad.shape,
                    shapes,
                    shape_ids_by_key,
                    source_path="pads.shape",
                    source_key=f"{refdes}:{pin_number}:{pad_index}",
                )
                pad = SemanticPad(
                    id=pad_id,
                    name=pin_number,
                    footprint_id=footprint_id,
                    component_id=component_id,
                    pin_id=pin_id,
                    net_id=net_ids_by_name.get(source_pad.net_name or "") or net_id,
                    layer_name=source_pad.layer_name or top_layer,
                    position=_xy_point(source_pad.x, source_pad.y)
                    or _xy_point(pin.x, pin.y),
                    padstack_definition=source_pad.pad_stack_name or pin.pad_stack_name,
                    geometry=SemanticPadGeometry(
                        shape_id=shape_id,
                        source="alg_full_geometry_pad",
                    ),
                    source=source_ref("alg", "pads", f"{refdes}:{pin_number}"),
                )
                pads.append(pad)
                pad_ids.append(pad_id)
                if component_id:
                    unique_append(component_pad_ids[component_id], pad_id)
                if footprint_id:
                    unique_append(footprint_pad_ids[footprint_id], pad_id)
        else:
            shape_id = _default_pad_shape_id(
                shapes,
                shape_ids_by_key,
                default_size=_default_size_from_mils(payload, DEFAULT_PAD_SIZE_MIL),
            )
            pad_id = semantic_id("pad", f"{refdes}:{pin_number}:default")
            pads.append(
                SemanticPad(
                    id=pad_id,
                    name=pin_number,
                    footprint_id=footprint_id,
                    component_id=component_id,
                    pin_id=pin_id,
                    net_id=net_id,
                    layer_name=top_layer,
                    position=_xy_point(pin.x, pin.y),
                    padstack_definition=pin.pad_stack_name,
                    geometry=SemanticPadGeometry(
                        shape_id=shape_id,
                        source="alg_component_pin_default",
                    ),
                    source=source_ref("alg", "pins", f"{refdes}:{pin_number}"),
                )
            )
            pad_ids.append(pad_id)
            if component_id:
                unique_append(component_pad_ids[component_id], pad_id)
            if footprint_id:
                unique_append(footprint_pad_ids[footprint_id], pad_id)
            diagnostics.append(
                SemanticDiagnostic(
                    severity="info",
                    code="alg.default_pad_geometry",
                    message=(
                        f"Pin {refdes}.{pin_number} did not have a matching copper pad "
                        "record; a default circular pad was used."
                    ),
                    source=source_ref("alg", "pins", f"{refdes}:{pin_number}"),
                )
            )

        pins.append(
            SemanticPin(
                id=pin_id,
                name=pin.pin_name or pin_number,
                component_id=component_id,
                net_id=net_id,
                pad_ids=pad_ids,
                layer_name=top_layer,
                position=_xy_point(pin.x, pin.y),
                source=source_ref("alg", "pins", f"{refdes}:{pin_number}"),
            )
        )
    _ = payload


def _semantic_via_templates(
    payload: ALGLayout,
    metal_layer_names: list[str],
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[float, ...]], str],
) -> tuple[list[SemanticViaTemplate], dict[str, str]]:
    default_via_size = _default_size_from_mils(payload, DEFAULT_VIA_SIZE_MIL)
    via_shapes_by_stack: dict[str, ALGShape] = {}
    for via in payload.vias or []:
        if via.pad_stack_name and via.shape is not None:
            via_shapes_by_stack.setdefault(via.pad_stack_name, via.shape)

    padstacks_by_name = {
        padstack.name: padstack for padstack in payload.padstacks or [] if padstack.name
    }
    via_templates: list[SemanticViaTemplate] = []
    ids_by_name: dict[str, str] = {}
    for index, padstack_name in enumerate(
        sorted({via.pad_stack_name for via in payload.vias or [] if via.pad_stack_name})
    ):
        if not padstack_name:
            continue
        pad_shape_id = _shape_id_for_alg_shape(
            via_shapes_by_stack.get(padstack_name),
            shapes,
            shape_ids_by_key,
            source_path="vias.shape",
            source_key=padstack_name,
            default_size=default_via_size,
        )
        barrel_shape_id = _shape_id_for_padstack_barrel(
            padstacks_by_name.get(padstack_name),
            via_shapes_by_stack.get(padstack_name),
            shapes,
            shape_ids_by_key,
            default_size=default_via_size,
        )
        template_id = semantic_id("via_template", padstack_name, index)
        ids_by_name[padstack_name] = template_id
        via_templates.append(
            SemanticViaTemplate(
                id=template_id,
                name=padstack_name,
                barrel_shape_id=barrel_shape_id,
                layer_pads=[
                    SemanticViaTemplateLayer(
                        layer_name=layer_name,
                        pad_shape_id=pad_shape_id,
                    )
                    for layer_name in metal_layer_names
                ],
                geometry=SemanticViaTemplateGeometry(
                    source="alg_via_class",
                    symbol=padstack_name,
                ),
                source=source_ref("alg", "padstacks", padstack_name),
            )
        )
    return via_templates, ids_by_name


def _shape_id_for_padstack_barrel(
    padstack,
    via_shape: ALGShape | None,
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[float, ...]], str],
    *,
    default_size: float,
) -> str:
    width = _number_text(padstack.drill_hole_name) if padstack else None
    height = width
    if padstack and padstack.drill_figure_width and padstack.drill_figure_height:
        width = padstack.drill_figure_width
        height = padstack.drill_figure_height
    if width is None or width <= 0:
        width = via_shape.width if via_shape and via_shape.width else default_size
        height = via_shape.height if via_shape and via_shape.height else width
    shape = ALGShape(kind="CIRCLE", width=width, height=height)
    return _shape_id_for_alg_shape(
        shape,
        shapes,
        shape_ids_by_key,
        source_path="padstacks.drill",
        source_key=padstack.name if padstack else None,
    )


def _semantic_vias(
    payload: ALGLayout,
    metal_layer_names: list[str],
    net_ids_by_name: dict[str, str],
    via_template_ids: dict[str, str],
) -> list[SemanticVia]:
    vias: list[SemanticVia] = []
    for index, via in enumerate(payload.vias or []):
        template_id = via_template_ids.get(via.pad_stack_name or "")
        vias.append(
            SemanticVia(
                id=semantic_id("via", via.key, index),
                name=via.pad_stack_name,
                template_id=template_id,
                net_id=net_ids_by_name.get(via.net_name or ""),
                layer_names=via.layer_names or metal_layer_names,
                position=SemanticPoint(x=via.x, y=via.y),
                geometry=SemanticViaGeometry(rotation=0),
                source=source_ref("alg", "vias", via.key),
            )
        )
    return vias


def _semantic_primitives(
    payload: ALGLayout, net_ids_by_name: dict[str, str]
) -> list[SemanticPrimitive]:
    primitives: list[SemanticPrimitive] = []
    shape_groups: dict[str, dict[str, object]] = {}
    void_groups: dict[str, dict[str, list[tuple[int, ALGTrack]]]] = defaultdict(dict)

    for index, track in enumerate(payload.tracks or []):
        geometry_role = (track.geometry_role or "").strip().upper()

        if geometry_role == "SHAPE" and track.kind in {"line", "arc"}:
            group_id = _track_group_id(track.record_tag)
            if group_id is not None:
                group = shape_groups.setdefault(
                    group_id,
                    {
                        "first_index": index,
                        "layer_name": track.layer_name,
                        "net_name": _alg_net_name(track.net_name),
                        "record_tag": track.record_tag,
                        "segments": [],
                    },
                )
                segments = group["segments"]
                if isinstance(segments, list):
                    segments.append((index, track))
            continue

        if geometry_role == "VOID" and track.kind in {"line", "arc"}:
            group_id = _track_group_id(track.record_tag)
            region_id = _track_region_id(track.record_tag)
            if group_id is not None and region_id is not None:
                void_groups[group_id].setdefault(region_id, []).append((index, track))
            continue

        net_name = _alg_net_name(track.net_name)
        net_id = net_ids_by_name.get(net_name)
        if track.kind == "line" and track.start and track.end:
            primitives.append(
                SemanticPrimitive(
                    id=semantic_id("primitive", f"track:{index}"),
                    kind="trace",
                    layer_name=track.layer_name,
                    net_id=net_id,
                    geometry=SemanticPrimitiveGeometry(
                        record_kind="LINE",
                        width=track.width,
                        center_line=[
                            [track.start.x, track.start.y],
                            [track.end.x, track.end.y],
                        ],
                    ),
                    source=source_ref("alg", f"tracks[{index}]", track.record_tag),
                )
            )
        elif track.kind == "arc" and track.start and track.end and track.center:
            primitives.append(
                SemanticPrimitive(
                    id=semantic_id("primitive", f"arc:{index}"),
                    kind="arc",
                    layer_name=track.layer_name,
                    net_id=net_id,
                    geometry=SemanticPrimitiveGeometry(
                        record_kind="ARC",
                        width=track.width,
                        start=[track.start.x, track.start.y],
                        end=[track.end.x, track.end.y],
                        center=[track.center.x, track.center.y],
                        clockwise=track.clockwise,
                        is_ccw=False if track.clockwise else True,
                    ),
                    source=source_ref("alg", f"tracks[{index}]", track.record_tag),
                )
            )
        elif track.kind == "rectangle" and track.bbox:
            bbox = track.bbox
            primitives.append(
                SemanticPrimitive(
                    id=semantic_id("primitive", f"rect:{index}"),
                    kind="polygon",
                    layer_name=track.layer_name,
                    net_id=net_id,
                    geometry=SemanticPrimitiveGeometry(
                        record_kind="RECTANGLE",
                        raw_points=[
                            [bbox.x1, bbox.y1],
                            [bbox.x2, bbox.y1],
                            [bbox.x2, bbox.y2],
                            [bbox.x1, bbox.y2],
                        ],
                        bbox=[bbox.x1, bbox.y1, bbox.x2, bbox.y2],
                    ),
                    source=source_ref("alg", f"tracks[{index}]", track.record_tag),
                )
            )

    for group_id, group in shape_groups.items():
        segments = group.get("segments")
        if not isinstance(segments, list):
            continue
        arcs, raw_points = _polygon_track_geometry(segments)
        if len(raw_points) < 2:
            continue

        voids: list[SemanticPolygonVoidGeometry] = []
        for region_id, region_segments in sorted(
            void_groups.get(group_id, {}).items(),
            key=lambda item: _numeric_key(item[0]),
        ):
            void_arcs, void_raw_points = _polygon_track_geometry(region_segments)
            if len(void_raw_points) < 2:
                continue
            voids.append(
                SemanticPolygonVoidGeometry(
                    raw_points=void_raw_points,
                    arcs=void_arcs,
                    polarity="VOID",
                    source_contour_index=_int_value(region_id),
                )
            )

        first_index = group.get("first_index")
        primitives.append(
            SemanticPrimitive(
                id=semantic_id("primitive", f"shape:{group_id}"),
                kind="polygon",
                layer_name=group.get("layer_name")
                if isinstance(group.get("layer_name"), str)
                else None,
                net_id=net_ids_by_name.get(
                    group.get("net_name")
                    if isinstance(group.get("net_name"), str)
                    else ""
                ),
                geometry=SemanticPrimitiveGeometry(
                    record_kind="SHAPE",
                    feature_id=group_id,
                    raw_points=raw_points,
                    arcs=arcs,
                    voids=voids,
                    has_voids=bool(voids),
                ),
                source=source_ref(
                    "alg",
                    f"tracks[{first_index}]"
                    if isinstance(first_index, int)
                    else "tracks",
                    group.get("record_tag"),
                ),
            )
        )
    return primitives


def _net_names(payload: ALGLayout) -> list[str]:
    names: list[str] = ["NoNet"]
    for pin in payload.pins or []:
        unique_append(names, pin.net_name)
    for pad in payload.pads or []:
        unique_append(names, pad.net_name)
    for via in payload.vias or []:
        unique_append(names, via.net_name)
    for track in payload.tracks or []:
        unique_append(names, _alg_net_name(track.net_name))
    return names


def _alg_net_name(name: str | None) -> str:
    return name if name else "NoNet"


def _track_group_id(record_tag: str | None) -> str | None:
    parts = _record_tag_parts(record_tag)
    return parts[0] if parts else None


def _track_region_id(record_tag: str | None) -> str | None:
    parts = _record_tag_parts(record_tag)
    if len(parts) < 3:
        return None
    return parts[-1]


def _record_tag_parts(record_tag: str | None) -> list[str]:
    return (record_tag or "").split()


def _polygon_track_geometry(
    segments: Iterable[tuple[int, ALGTrack]],
) -> tuple[list[SemanticArcGeometry], list[list[float | int | None]]]:
    arcs: list[SemanticArcGeometry] = []
    raw_points: list[list[float | int | None]] = []
    for _index, track in segments:
        geometry = _track_arc_geometry(track)
        if geometry is None:
            continue
        arcs.append(geometry)
        if track.end is not None:
            raw_points.append([track.end.x, track.end.y])
    if arcs and arcs[0].start is not None:
        raw_points.insert(0, list(arcs[0].start))
    return arcs, raw_points


def _track_arc_geometry(track: ALGTrack) -> SemanticArcGeometry | None:
    if track.start is None or track.end is None:
        return None
    start = [track.start.x, track.start.y]
    end = [track.end.x, track.end.y]
    if track.kind == "line":
        return SemanticArcGeometry(start=start, end=end, is_segment=True)
    if track.kind != "arc" or track.center is None:
        return None
    return SemanticArcGeometry(
        start=start,
        end=end,
        center=[track.center.x, track.center.y],
        clockwise=track.clockwise,
        is_ccw=False if track.clockwise else True,
    )


def _numeric_key(value: str) -> tuple[int, str]:
    number = _int_value(value)
    return (number if number is not None else 2**31 - 1, value)


def _int_value(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _shape_id_for_alg_shape(
    shape: ALGShape | None,
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[float, ...]], str],
    *,
    source_path: str,
    source_key: object,
    default_size: float = DEFAULT_PAD_SIZE_MIL,
) -> str:
    kind = (shape.kind if shape else "CIRCLE").upper()
    width = abs(shape.width or default_size) if shape else default_size
    height = abs(shape.height or width) if shape else width
    if kind in {"CIRCLE", "FIG_CIRCLE"}:
        return _shape_id(
            shapes,
            shape_ids_by_key,
            kind="circle",
            auroradb_type="Circle",
            values=[0.0, 0.0, width],
            source_path=source_path,
            source_key=source_key,
        )
    return _shape_id(
        shapes,
        shape_ids_by_key,
        kind="rectangle",
        auroradb_type="Rectangle",
        values=[0.0, 0.0, width, height],
        source_path=source_path,
        source_key=source_key,
    )


def _default_pad_shape_id(
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[float, ...]], str],
    *,
    default_size: float,
) -> str:
    return _shape_id(
        shapes,
        shape_ids_by_key,
        kind="circle",
        auroradb_type="Circle",
        values=[0.0, 0.0, default_size],
        source_path="pins",
        source_key="default_pad",
    )


def _shape_id(
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[float, ...]], str],
    *,
    kind: str,
    auroradb_type: str,
    values: list[float],
    source_path: str,
    source_key: object,
) -> str:
    key = (auroradb_type, tuple(round(float(value), 9) for value in values))
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
            source=source_ref("alg", source_path, source_key),
        )
    )
    return shape_id


def _board_outline(payload: ALGLayout):
    board = payload.board
    if board is None or board.extents is None:
        return {}
    bbox = board.extents
    return {
        "kind": "polygon",
        "auroradb_type": "Polygon",
        "source": "alg_board_extents",
        "values": [
            4,
            f"({bbox.x1},{bbox.y1})",
            f"({bbox.x2},{bbox.y1})",
            f"({bbox.x2},{bbox.y2})",
            f"({bbox.x1},{bbox.y2})",
            "Y",
            "Y",
        ],
    }


def _average_pin_point(pins: Iterable[ALGPin]) -> SemanticPoint | None:
    x_total = 0.0
    y_total = 0.0
    count = 0
    for pin in pins:
        if pin.x is None or pin.y is None:
            continue
        x_total += pin.x
        y_total += pin.y
        count += 1
    if count == 0:
        return None
    return SemanticPoint(x=x_total / count, y=y_total / count)


def _point(point: ALGPoint | None) -> SemanticPoint | None:
    if point is None:
        return None
    return SemanticPoint(x=point.x, y=point.y)


def _xy_point(x: float | None, y: float | None) -> SemanticPoint | None:
    if x is None or y is None:
        return None
    return SemanticPoint(x=x, y=y)


def _number_text(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.split()[0])
    except (ValueError, IndexError):
        return None


def _semantic_units(payload: ALGLayout) -> str:
    unit = payload.board.units if payload.board else payload.summary.units
    text = (unit or "mil").casefold()
    if text in {"mils", "mil"}:
        return "mil"
    if text in {"millimeters", "millimeter", "mm"}:
        return "mm"
    if text in {"inches", "inch", "in"}:
        return "inch"
    return unit or "mil"


def _default_size_from_mils(payload: ALGLayout, value_mils: float) -> float:
    unit = _semantic_units(payload).casefold()
    if unit == "mm":
        return value_mils * MIL_TO_MM
    if unit == "inch":
        return value_mils / 1000.0
    return value_mils
