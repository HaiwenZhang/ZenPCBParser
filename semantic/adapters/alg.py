from __future__ import annotations

from collections import defaultdict
from math import radians, sqrt
from typing import Iterable

from aurora_translator.semantic.adapters.utils import (
    role_from_net_name,
    semantic_id,
    side_from_layer_name,
    source_ref,
    unique_append,
)
from aurora_translator.semantic.models import (
    SemanticBoard,
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
    ALGPadstack,
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
    materials, material_ids_by_key = _semantic_materials(payload)
    layers = _semantic_layers(payload, material_ids_by_key)
    metal_layer_names = [layer.name for layer in layers if _is_metal_layer(layer)]
    layer_sides_by_name = _layer_sides_by_name(layers)
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
    padstacks_by_name = _padstacks_by_name(payload.padstacks or [], metal_layer_names)
    padstack_shapes_by_layer, padstack_shapes_by_name = _padstack_simple_pad_shapes(
        payload.pads or []
    )
    component_layers_by_refdes = _component_layers_by_refdes(
        payload,
        components_by_refdes,
        symbols_by_refdes,
        source_pads_by_refdes_pin,
        padstacks_by_name,
        metal_layer_names,
        top_layer,
        bottom_layer,
    )

    footprints = _semantic_footprints(components_by_refdes)
    footprint_ids_by_name = {footprint.name: footprint.id for footprint in footprints}
    components = _semantic_components(
        components_by_refdes,
        symbols_by_refdes,
        pins_by_refdes_pin,
        component_layers_by_refdes,
        layer_sides_by_name,
        footprint_ids_by_name,
        top_layer,
        bottom_layer,
    )
    components_by_id = {component.id: component for component in components}
    component_ids_by_refdes = {
        component.refdes or component.name or component.id: component.id
        for component in components
    }
    component_layers_by_refdes = {
        component.refdes: component.layer_name
        for component in components
        if component.refdes and component.layer_name
    }

    pins: list[SemanticPin] = []
    pads: list[SemanticPad] = []
    pin_ids_by_key: dict[tuple[str, str], str] = {}
    pin_ids_by_component: dict[str, list[str]] = defaultdict(list)
    component_pad_ids: dict[str, list[str]] = defaultdict(list)
    footprint_pad_ids: dict[str, list[str]] = defaultdict(list)
    _semantic_pins_and_pads(
        payload,
        pins_by_refdes_pin,
        source_pads_by_refdes_pin,
        padstack_shapes_by_layer,
        padstack_shapes_by_name,
        components_by_refdes,
        component_ids_by_refdes,
        component_layers_by_refdes,
        footprint_ids_by_name,
        net_ids_by_name,
        top_layer,
        shapes,
        shape_ids_by_key,
        pins,
        pads,
        pin_ids_by_key,
        pin_ids_by_component,
        component_pad_ids,
        footprint_pad_ids,
        diagnostics,
    )

    for component in components:
        component.pin_ids = pin_ids_by_component.get(component.id, [])
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
        materials=materials,
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


def _semantic_materials(
    payload: ALGLayout,
) -> tuple[list[SemanticMaterial], dict[tuple[str, str, str], str]]:
    materials: list[SemanticMaterial] = []
    material_ids_by_key: dict[tuple[str, str, str], str] = {}
    metal_index = 1
    dielectric_index = 0

    for index, layer in enumerate(payload.layers or []):
        if _is_ignored_stackup_layer(layer):
            continue
        if layer.conductor:
            conductivity = _conductivity_to_si(layer.electrical_conductivity)
            key = ("metal", _material_key_value(conductivity), "")
            if key in material_ids_by_key:
                continue
            material_name = f"Metal{metal_index}"
            metal_index += 1
            material_id = semantic_id("material", material_name)
            material_ids_by_key[key] = material_id
            materials.append(
                SemanticMaterial(
                    id=material_id,
                    name=material_name,
                    role="metal",
                    conductivity=conductivity,
                    source=source_ref(
                        "alg", f"layers[{index}].material", layer.material
                    ),
                )
            )
            continue

        if not _is_dielectric_layer(layer):
            continue
        permittivity = _number_text(layer.dielectric_constant)
        loss_tangent = _number_text(layer.loss_tangent)
        key = (
            "dielectric",
            _material_key_value(permittivity),
            _material_key_value(loss_tangent),
        )
        if key in material_ids_by_key:
            continue
        material_name = f"Dielectric{dielectric_index}"
        dielectric_index += 1
        material_id = semantic_id("material", material_name)
        material_ids_by_key[key] = material_id
        materials.append(
            SemanticMaterial(
                id=material_id,
                name=material_name,
                role="dielectric",
                permittivity=permittivity,
                dielectric_loss_tangent=loss_tangent,
                source=source_ref("alg", f"layers[{index}].material", layer.material),
            )
        )

    return materials, material_ids_by_key


def _semantic_layers(
    payload: ALGLayout, material_ids_by_key: dict[tuple[str, str, str], str]
) -> list[SemanticLayer]:
    layers: list[SemanticLayer] = []
    conductor_layers = [layer for layer in payload.layers or [] if layer.conductor]
    conductor_count = len(conductor_layers)
    conductor_index = 0
    dielectric_index = 0
    for index, layer in enumerate(payload.layers or []):
        if _is_ignored_stackup_layer(layer):
            continue
        if layer.conductor:
            if not layer.name:
                continue
            name = layer.name
            role = _layer_role(layer.layer_type, layer.use_kind, layer.shield_layer)
            side = side_from_layer_name(name)
            if side is None:
                if conductor_index == 0:
                    side = "top"
                elif conductor_index == conductor_count - 1:
                    side = "bottom"
                else:
                    side = "internal"
            material_key = (
                "metal",
                _material_key_value(_conductivity_to_si(layer.electrical_conductivity)),
                "",
            )
            conductor_index += 1
        elif _is_dielectric_layer(layer):
            name = layer.name or f"D{dielectric_index}"
            role = "dielectric"
            side = None
            material_key = (
                "dielectric",
                _material_key_value(_number_text(layer.dielectric_constant)),
                _material_key_value(_number_text(layer.loss_tangent)),
            )
            dielectric_index += 1
        else:
            continue

        layers.append(
            SemanticLayer(
                id=semantic_id("layer", name, index),
                name=name,
                layer_type=layer.layer_type,
                role=role,
                side=side,
                order_index=len(layers),
                material=layer.material,
                material_id=material_ids_by_key.get(material_key),
                thickness=layer.thickness,
                source=source_ref("alg", f"layers[{index}]", name),
            )
        )
    return layers


def _is_ignored_stackup_layer(layer) -> bool:
    layer_type = (layer.layer_type or "").casefold()
    material = (layer.material or "").casefold()
    thickness = _number_text(layer.thickness)
    return (
        layer_type == "surface"
        and material == "air"
        and (thickness is None or abs(thickness) <= 1e-12)
    )


def _is_dielectric_layer(layer) -> bool:
    return not layer.conductor and (layer.layer_type or "").casefold() == "dielectric"


def _material_key_value(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.12g}"


def _conductivity_to_si(value: str | None) -> float | None:
    number = _number_text(value)
    if number is None:
        return None
    text = (value or "").casefold()
    if "mho/cm" in text or "s/cm" in text:
        return number * 100.0
    return number


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


def _layer_sides_by_name(layers: Iterable[SemanticLayer]) -> dict[str, str | None]:
    return {
        layer.name.casefold(): layer.side for layer in layers if layer.name is not None
    }


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


def _padstack_simple_pad_shapes(
    pads: Iterable[ALGPad],
) -> tuple[dict[tuple[str, str], ALGShape], dict[str, ALGShape]]:
    shapes_by_layer: dict[
        tuple[str, str], dict[tuple[str, float, float], tuple[int, ALGShape]]
    ] = {}
    shapes_by_name: dict[str, dict[tuple[str, float, float], tuple[int, ALGShape]]] = {}
    for pad in pads:
        if not _is_regular_pad_type(pad.pad_type):
            continue
        padstack_name = (pad.pad_stack_name or "").casefold()
        if not padstack_name:
            continue
        signature = _simple_pad_shape_signature(pad.shape)
        if signature is None:
            continue
        if pad.layer_name:
            _record_padstack_shape(
                shapes_by_layer,
                (padstack_name, pad.layer_name.casefold()),
                signature,
                pad.shape,
            )
        _record_padstack_shape(shapes_by_name, padstack_name, signature, pad.shape)
    return (
        {
            key: _most_common_padstack_shape(candidates)
            for key, candidates in shapes_by_layer.items()
        },
        {
            key: _most_common_padstack_shape(candidates)
            for key, candidates in shapes_by_name.items()
        },
    )


def _record_padstack_shape(
    shapes: dict[object, dict[tuple[str, float, float], tuple[int, ALGShape]]],
    key: object,
    signature: tuple[str, float, float],
    shape: ALGShape,
) -> None:
    candidates = shapes.setdefault(key, {})
    count, first_shape = candidates.get(signature, (0, shape))
    candidates[signature] = (count + 1, first_shape)


def _most_common_padstack_shape(
    candidates: dict[tuple[str, float, float], tuple[int, ALGShape]],
) -> ALGShape:
    return max(
        candidates.items(),
        key=lambda item: (item[1][0], item[0]),
    )[1][1]


def _simple_pad_shape_signature(
    shape: ALGShape | None,
) -> tuple[str, float, float] | None:
    if shape is None:
        return None
    kind = (shape.kind or "").upper()
    if kind in {"", "LINE", "ARC"}:
        return None
    width = abs(shape.width or 0.0)
    height = abs(shape.height if shape.height is not None else width)
    if width <= 0.0 or height <= 0.0:
        return None
    if kind in {"SQUARE", "FIG_SQUARE"}:
        side = max(width, height)
        width = side
        height = side
    if kind in {"CIRCLE", "FIG_CIRCLE"}:
        height = width
    return kind, round(width, 9), round(height, 9)


def _component_layers_by_refdes(
    payload: ALGLayout,
    components_by_refdes: dict[str, ALGComponent],
    symbols_by_refdes: dict[str, ALGSymbol],
    source_pads_by_refdes_pin: dict[tuple[str, str], list[ALGPad]],
    padstacks_by_name: dict[str, ALGPadstack],
    metal_layer_names: list[str],
    top_layer: str | None,
    bottom_layer: str | None,
) -> dict[str, str | None]:
    pins_by_refdes: dict[str, list[ALGPin]] = defaultdict(list)
    for pin in payload.pins or []:
        if pin.refdes:
            pins_by_refdes[pin.refdes].append(pin)

    result: dict[str, str | None] = {}
    for refdes in components_by_refdes:
        initial_layer = _initial_component_layer(
            symbols_by_refdes.get(refdes),
            top_layer,
            bottom_layer,
        )
        result[refdes] = _component_layer_from_pin_pads(
            initial_layer,
            pins_by_refdes.get(refdes, []),
            source_pads_by_refdes_pin,
            padstacks_by_name,
            metal_layer_names,
        )
    return result


def _initial_component_layer(
    symbol: ALGSymbol | None,
    top_layer: str | None,
    bottom_layer: str | None,
) -> str | None:
    return bottom_layer if symbol and symbol.mirror else top_layer


def _component_layer_from_pin_pads(
    initial_layer: str | None,
    pins: Iterable[ALGPin],
    source_pads_by_refdes_pin: dict[tuple[str, str], list[ALGPad]],
    padstacks_by_name: dict[str, ALGPadstack],
    metal_layer_names: list[str],
) -> str | None:
    through_candidate: str | None = None
    for pin in pins:
        matching_pads = source_pads_by_refdes_pin.get((pin.refdes, pin.pin_number), [])
        pad_layers = _regular_pad_layers_for_pin(
            pin,
            matching_pads,
            padstacks_by_name,
            metal_layer_names,
        )
        if not pad_layers:
            continue
        if _pin_spans_multiple_metal_layers(pin, matching_pads, padstacks_by_name):
            if _same_layer(initial_layer, pad_layers[0]) or _same_layer(
                initial_layer, pad_layers[-1]
            ):
                through_candidate = initial_layer
                continue
            if through_candidate is None:
                through_candidate = pad_layers[0]
            continue
        return pad_layers[0]
    return through_candidate or initial_layer


def _regular_pad_layers_for_pin(
    pin: ALGPin,
    matching_pads: Iterable[ALGPad],
    padstacks_by_name: dict[str, ALGPadstack],
    metal_layer_names: list[str],
) -> list[str]:
    metal_layers_by_key = {
        layer_name.casefold(): layer_name for layer_name in metal_layer_names
    }
    result: list[str] = []
    for pad in matching_pads:
        if not _is_regular_pad_type(pad.pad_type):
            continue
        layer_name = metal_layers_by_key.get((pad.layer_name or "").casefold())
        if layer_name:
            unique_append(result, layer_name)
    if result:
        return result

    padstack = _pin_padstack(pin, matching_pads, padstacks_by_name)
    return (
        _via_template_layer_names(padstack, metal_layer_names, None) if padstack else []
    )


def _pin_spans_multiple_metal_layers(
    pin: ALGPin,
    matching_pads: Iterable[ALGPad],
    padstacks_by_name: dict[str, ALGPadstack],
) -> bool:
    padstack = _pin_padstack(pin, matching_pads, padstacks_by_name)
    if _padstack_spans_multiple_metal_layers(padstack):
        return True
    layer_keys = {
        (pad.layer_name or "").casefold()
        for pad in matching_pads
        if _is_regular_pad_type(pad.pad_type) and pad.layer_name
    }
    return len(layer_keys) > 1


def _pin_padstack(
    pin: ALGPin,
    matching_pads: Iterable[ALGPad],
    padstacks_by_name: dict[str, ALGPadstack],
) -> ALGPadstack | None:
    for padstack_name in [
        pin.pad_stack_name,
        *(pad.pad_stack_name for pad in matching_pads),
    ]:
        padstack = padstacks_by_name.get(padstack_name or "")
        if padstack is not None:
            return padstack
    return None


def _same_layer(left: str | None, right: str | None) -> bool:
    return bool(left and right and left.casefold() == right.casefold())


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
    component_layers_by_refdes: dict[str, str | None],
    layer_sides_by_name: dict[str, str | None],
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
        layer_name = component_layers_by_refdes.get(refdes)
        if layer_name is None:
            layer_name = bottom_layer if mirror else top_layer
        side = _component_side_for_layer(layer_name, layer_sides_by_name, mirror)
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


def _component_side_for_layer(
    layer_name: str | None,
    layer_sides_by_name: dict[str, str | None],
    mirror: bool,
) -> str | None:
    if layer_name:
        side = layer_sides_by_name.get(layer_name.casefold())
        if side:
            return side
        inferred_side = side_from_layer_name(layer_name)
        if inferred_side:
            return inferred_side
    return "bottom" if mirror else "top"


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


def _semantic_pad_records(
    matching_pads: Iterable[ALGPad],
    padstack_shapes_by_layer: dict[tuple[str, str], ALGShape],
    padstack_shapes_by_name: dict[str, ALGShape],
) -> list[tuple[ALGPad, ALGShape | None, str]]:
    groups: dict[tuple[str, str, str, str, str, str], list[ALGPad]] = {}
    for pad in matching_pads:
        groups.setdefault(_pad_geometry_group_key(pad), []).append(pad)

    result: list[tuple[ALGPad, ALGShape | None, str]] = []
    for group in groups.values():
        source_pad = group[0]
        shape = _effective_pad_shape(
            group,
            padstack_shapes_by_layer,
            padstack_shapes_by_name,
        )
        geometry_source = (
            "alg_full_geometry_pad"
            if shape is source_pad.shape
            else "alg_full_geometry_padstack_shape"
        )
        result.append((source_pad, shape, geometry_source))
    return result


def _pad_geometry_group_key(pad: ALGPad) -> tuple[str, str, str, str, str, str]:
    shape_kind = (pad.shape.kind if pad.shape else "").upper()
    record_group = (
        _track_group_id_fast(pad.record_tag)
        if shape_kind in {"LINE", "ARC"}
        else pad.record_tag
    )
    return (
        pad.layer_name or "",
        pad.pad_stack_name or "",
        pad.net_name or "",
        _coordinate_key(pad.x),
        _coordinate_key(pad.y),
        record_group or "",
    )


def _effective_pad_shape(
    group: list[ALGPad],
    padstack_shapes_by_layer: dict[tuple[str, str], ALGShape],
    padstack_shapes_by_name: dict[str, ALGShape],
) -> ALGShape | None:
    for pad in group:
        if _simple_pad_shape_signature(pad.shape) is not None:
            return pad.shape

    representative = group[0]
    padstack_shape = _padstack_lookup_shape(
        representative,
        padstack_shapes_by_layer,
        padstack_shapes_by_name,
    )
    if padstack_shape is not None:
        return padstack_shape
    return _custom_pad_shape_from_segments(group)


def _padstack_lookup_shape(
    pad: ALGPad,
    padstack_shapes_by_layer: dict[tuple[str, str], ALGShape],
    padstack_shapes_by_name: dict[str, ALGShape],
) -> ALGShape | None:
    padstack_name = (pad.pad_stack_name or "").casefold()
    if not padstack_name:
        return None
    if pad.layer_name:
        shape = padstack_shapes_by_layer.get((padstack_name, pad.layer_name.casefold()))
        if shape is not None:
            return shape
    return padstack_shapes_by_name.get(padstack_name)


def _custom_pad_shape_from_segments(group: list[ALGPad]) -> ALGShape | None:
    points: list[tuple[float, float]] = []
    for pad in group:
        shape = pad.shape
        if shape is None:
            continue
        kind = (shape.kind or "").upper()
        if kind not in {"LINE", "ARC"}:
            continue
        if (
            shape.x is not None
            and shape.y is not None
            and shape.width is not None
            and shape.height is not None
        ):
            points.append((shape.x, shape.y))
            points.append((shape.width, shape.height))
    if len(points) < 2:
        return None

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    if width <= 0.0 or height <= 0.0:
        return None
    if len(group) >= 4 and abs(width - height) <= max(width, height) * 0.05:
        side = max(width, height) / sqrt(2.0)
        return ALGShape(kind="SQUARE", width=side, height=side)
    return ALGShape(kind="FIG_RECTANGLE", width=width, height=height)


def _alg_shape_footprint_rotation(shape: ALGShape | None) -> float:
    if shape is None or shape.rotation is None:
        return 0.0
    return radians(float(shape.rotation))


def _coordinate_key(value: float | int | None) -> str:
    if value is None:
        return ""
    return f"{float(value):.6f}"


def _semantic_pins_and_pads(
    payload: ALGLayout,
    pins_by_refdes_pin: dict[tuple[str, str], ALGPin],
    source_pads_by_refdes_pin: dict[tuple[str, str], list[ALGPad]],
    padstack_shapes_by_layer: dict[tuple[str, str], ALGShape],
    padstack_shapes_by_name: dict[str, ALGShape],
    components_by_refdes: dict[str, ALGComponent],
    component_ids_by_refdes: dict[str, str],
    component_layers_by_refdes: dict[str, str],
    footprint_ids_by_name: dict[str, str],
    net_ids_by_name: dict[str, str],
    top_layer: str | None,
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[float, ...]], str],
    pins: list[SemanticPin],
    pads: list[SemanticPad],
    pin_ids_by_key: dict[tuple[str, str], str],
    pin_ids_by_component: dict[str, list[str]],
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
        pin_layer_name = component_layers_by_refdes.get(refdes) or top_layer
        net_id = net_ids_by_name.get(_alg_net_name(pin.net_name))
        pin_id = semantic_id("pin", f"{refdes}:{pin_number}", index)
        pin_ids_by_key[(refdes, pin_number)] = pin_id
        if component_id:
            unique_append(pin_ids_by_component[component_id], pin_id)
        matching_pads = source_pads_by_refdes_pin.get((refdes, pin_number), [])
        pad_ids: list[str] = []
        if matching_pads:
            semantic_pads = _semantic_pad_records(
                matching_pads,
                padstack_shapes_by_layer,
                padstack_shapes_by_name,
            )
            for pad_index, (source_pad, effective_shape, geometry_source) in enumerate(
                semantic_pads
            ):
                pad_id = semantic_id(
                    "pad", f"{refdes}:{pin_number}:{source_pad.layer_name}:{pad_index}"
                )
                shape_id = _shape_id_for_alg_shape(
                    effective_shape,
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
                    net_id=net_ids_by_name.get(_alg_net_name(source_pad.net_name))
                    or net_id,
                    layer_name=source_pad.layer_name or pin_layer_name or top_layer,
                    position=_xy_point(source_pad.x, source_pad.y)
                    or _xy_point(pin.x, pin.y),
                    padstack_definition=source_pad.pad_stack_name or pin.pad_stack_name,
                    geometry=SemanticPadGeometry(
                        shape_id=shape_id,
                        source=geometry_source,
                        footprint_rotation=_alg_shape_footprint_rotation(
                            effective_shape
                        ),
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
                    layer_name=pin_layer_name or top_layer,
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
                layer_name=pin_layer_name,
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
    via_layers_by_stack: dict[str, list[str]] = defaultdict(list)
    for via in payload.vias or []:
        padstack_name = via.pad_stack_name
        if not padstack_name:
            continue
        if via.shape is not None:
            via_shapes_by_stack.setdefault(padstack_name, via.shape)
        for layer_name in via.layer_names:
            unique_append(via_layers_by_stack[padstack_name], layer_name)

    pad_shapes_by_stack: dict[str, ALGShape] = {}
    for pad in payload.pads or []:
        if (
            pad.pad_stack_name
            and pad.shape is not None
            and _is_regular_pad_type(pad.pad_type)
        ):
            pad_shapes_by_stack.setdefault(pad.pad_stack_name, pad.shape)

    padstacks_by_name = _padstacks_by_name(payload.padstacks or [], metal_layer_names)
    padstack_names = _via_template_padstack_names(payload, padstacks_by_name)
    via_templates: list[SemanticViaTemplate] = []
    ids_by_name: dict[str, str] = {}
    for index, padstack_name in enumerate(padstack_names):
        if not padstack_name:
            continue
        padstack = padstacks_by_name.get(padstack_name)
        pad_shape = via_shapes_by_stack.get(padstack_name) or pad_shapes_by_stack.get(
            padstack_name
        )
        pad_shape_id = _shape_id_for_alg_shape(
            pad_shape,
            shapes,
            shape_ids_by_key,
            source_path="vias.shape",
            source_key=padstack_name,
            default_size=default_via_size,
        )
        barrel_shape_id = _shape_id_for_padstack_barrel(
            padstack,
            pad_shape,
            shapes,
            shape_ids_by_key,
            default_size=default_via_size,
        )
        layer_names = _via_template_layer_names(
            padstack,
            metal_layer_names,
            via_layers_by_stack.get(padstack_name),
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
                    for layer_name in layer_names
                ],
                geometry=SemanticViaTemplateGeometry(
                    source="alg_padstack",
                    symbol=padstack_name,
                ),
                source=source_ref("alg", "padstacks", padstack_name),
            )
        )
    return via_templates, ids_by_name


def _padstacks_by_name(
    padstacks: Iterable[ALGPadstack],
    metal_layer_names: list[str],
) -> dict[str, ALGPadstack]:
    result: dict[str, ALGPadstack] = {}
    scores: dict[str, int] = {}
    for padstack in padstacks:
        if not padstack.name:
            continue
        score = len(_via_template_layer_names(padstack, metal_layer_names, None))
        existing_score = scores.get(padstack.name, -1)
        if score > existing_score:
            result[padstack.name] = padstack
            scores[padstack.name] = score
    return result


def _via_template_padstack_names(
    payload: ALGLayout,
    padstacks_by_name: dict[str, ALGPadstack],
) -> list[str]:
    names: list[str] = []
    for via in payload.vias or []:
        unique_append(names, via.pad_stack_name)
    for pad in payload.pads or []:
        padstack_name = pad.pad_stack_name
        if not padstack_name:
            continue
        if _padstack_spans_multiple_metal_layers(padstacks_by_name.get(padstack_name)):
            unique_append(names, padstack_name)
    for pin in payload.pins or []:
        padstack_name = pin.pad_stack_name
        if not padstack_name:
            continue
        if _padstack_spans_multiple_metal_layers(padstacks_by_name.get(padstack_name)):
            unique_append(names, padstack_name)
    return names


def _via_template_layer_names(
    padstack: ALGPadstack | None,
    metal_layer_names: list[str],
    fallback_layer_names: Iterable[str] | None,
) -> list[str]:
    layer_index = {
        layer_name.casefold(): index
        for index, layer_name in enumerate(metal_layer_names)
    }
    if padstack:
        start_index = layer_index.get((padstack.start_layer or "").casefold())
        end_index = layer_index.get((padstack.end_layer or "").casefold())
        if start_index is not None and end_index is not None:
            first = min(start_index, end_index)
            last = max(start_index, end_index)
            return metal_layer_names[first : last + 1]

    fallback = {layer_name.casefold() for layer_name in fallback_layer_names or []}
    if fallback:
        layer_names = [
            layer_name
            for layer_name in metal_layer_names
            if layer_name.casefold() in fallback
        ]
        if layer_names:
            return layer_names
    return list(metal_layer_names)


def _padstack_spans_multiple_metal_layers(padstack: ALGPadstack | None) -> bool:
    if padstack is None:
        return False
    start_layer = (padstack.start_layer or "").casefold()
    end_layer = (padstack.end_layer or "").casefold()
    return bool(start_layer and end_layer and start_layer != end_layer)


def _is_regular_pad_type(pad_type: str | None) -> bool:
    return not pad_type or pad_type.casefold() == "regular"


def _shape_id_for_padstack_barrel(
    padstack: ALGPadstack | None,
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
                net_id=net_ids_by_name.get(_alg_net_name(via.net_name)),
                layer_names=via.layer_names or metal_layer_names,
                position=SemanticPoint(x=via.x, y=via.y),
                geometry=SemanticViaGeometry(rotation=0),
                source=source_ref("alg", "vias", via.key),
            )
        )
    vias.extend(
        _semantic_padstack_hole_vias(
            payload,
            metal_layer_names,
            net_ids_by_name,
            via_template_ids,
            start_index=len(vias),
        )
    )
    return vias


def _semantic_padstack_hole_vias(
    payload: ALGLayout,
    metal_layer_names: list[str],
    net_ids_by_name: dict[str, str],
    via_template_ids: dict[str, str],
    *,
    start_index: int,
) -> list[SemanticVia]:
    padstacks_by_name = _padstacks_by_name(payload.padstacks or [], metal_layer_names)
    seen: set[tuple[str, str, str, float, float]] = set()
    vias: list[SemanticVia] = []
    for pad in payload.pads or []:
        if (
            not pad.pad_stack_name
            or pad.pin_number
            or pad.x is None
            or pad.y is None
            or not _is_regular_pad_type(pad.pad_type)
        ):
            continue
        padstack = padstacks_by_name.get(pad.pad_stack_name)
        if not _padstack_spans_multiple_metal_layers(padstack):
            continue
        template_id = via_template_ids.get(pad.pad_stack_name)
        if not template_id:
            continue
        net_name = _alg_net_name(pad.net_name)
        net_id = net_ids_by_name.get(net_name)
        key = (
            pad.pad_stack_name,
            pad.refdes or "",
            net_name,
            round(pad.x, 9),
            round(pad.y, 9),
        )
        if key in seen:
            continue
        seen.add(key)
        index = start_index + len(vias)
        vias.append(
            SemanticVia(
                id=semantic_id("via", f"pad:{pad.pad_stack_name}:{index}"),
                name=pad.pad_stack_name,
                template_id=template_id,
                net_id=net_id,
                layer_names=_via_template_layer_names(
                    padstack,
                    metal_layer_names,
                    None,
                ),
                position=SemanticPoint(x=pad.x, y=pad.y),
                geometry=SemanticViaGeometry(rotation=0),
                source=source_ref(
                    "alg",
                    "pads",
                    f"{pad.refdes or ''}:{pad.pad_stack_name}:{pad.x}:{pad.y}",
                ),
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
            group_id = _track_group_id_fast(track.record_tag)
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
            group_id, region_id = _track_group_region_id(track.record_tag)
            if group_id is not None and region_id is not None:
                void_groups[group_id].setdefault(region_id, []).append((index, track))
            continue

        net_name = _alg_net_name(track.net_name)
        net_id = net_ids_by_name.get(net_name)
        if track.kind == "line" and track.start and track.end:
            primitives.append(
                SemanticPrimitive.model_construct(
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
                SemanticPrimitive.model_construct(
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
                SemanticPrimitive.model_construct(
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

        voids: list[dict[str, object]] = []
        for region_id, region_segments in sorted(
            void_groups.get(group_id, {}).items(),
            key=lambda item: _numeric_key(item[0]),
        ):
            void_arcs, void_raw_points = _polygon_track_geometry(region_segments)
            if len(void_raw_points) < 2:
                continue
            voids.append(
                _polygon_void_geometry(
                    raw_points=void_raw_points,
                    arcs=void_arcs,
                    polarity="VOID",
                    source_contour_index=_int_value(region_id),
                )
            )

        first_index = group.get("first_index")
        primitives.append(
            SemanticPrimitive.model_construct(
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
                geometry=_primitive_geometry(
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


def _record_tag_parts(record_tag: str | None) -> list[str]:
    return (record_tag or "").split()


def _track_group_id_fast(record_tag: str | None) -> str | None:
    if not record_tag:
        return None
    return record_tag.split(maxsplit=1)[0]


def _track_group_region_id(record_tag: str | None) -> tuple[str | None, str | None]:
    parts = _record_tag_parts(record_tag)
    if len(parts) < 3:
        return (parts[0], None) if parts else (None, None)
    return parts[0], parts[-1]


def _polygon_track_geometry(
    segments: Iterable[tuple[int, ALGTrack]],
) -> tuple[list[dict[str, object]], list[list[float | int | None]]]:
    arcs: list[dict[str, object]] = []
    raw_points: list[list[float | int | None]] = []
    first_start: list[float | int | None] | None = None
    for _index, track in segments:
        if track.start is None or track.end is None:
            continue
        start = [track.start.x, track.start.y]
        end = [track.end.x, track.end.y]
        if first_start is None:
            first_start = start
        if track.kind == "line":
            arcs.append({"start": start, "end": end, "is_segment": True})
            raw_points.append(end)
            continue
        if track.kind != "arc" or track.center is None:
            continue
        arcs.append(
            {
                "start": start,
                "end": end,
                "center": [track.center.x, track.center.y],
                "clockwise": track.clockwise,
                "is_ccw": False if track.clockwise else True,
            }
        )
        raw_points.append(end)
    if first_start is not None:
        raw_points.insert(0, first_start)
    return arcs, raw_points


def _polygon_void_geometry(**fields) -> dict[str, object]:
    return fields


def _primitive_geometry(**fields) -> SemanticPrimitiveGeometry:
    field_names = set(fields)
    values = {
        "record_kind": None,
        "feature_index": None,
        "feature_id": None,
        "line_number": None,
        "tokens": [],
        "polarity": None,
        "symbol": None,
        "shape_id": None,
        "dcode": None,
        "orientation": None,
        "rotation": None,
        "mirror_x": None,
        "mirror_y": None,
        "start": None,
        "end": None,
        "center": None,
        "location": None,
        "width": None,
        "center_line": [],
        "raw_points": [],
        "arcs": [],
        "voids": [],
        "has_voids": None,
        "void_ids": [],
        "surface_group_index": None,
        "surface_group_count": None,
        "is_negative": None,
        "is_void": None,
        "bbox": None,
        "area": None,
        "clockwise": None,
        "is_ccw": None,
    }
    values.update(fields)
    return SemanticPrimitiveGeometry.model_construct(
        _fields_set=field_names,
        **values,
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
    if kind in {"OBLONG_X", "OBLONG_Y", "OVAL", "FIG_OBLONG"}:
        radius = min(width, height) / 2.0
        return _shape_id(
            shapes,
            shape_ids_by_key,
            kind="rounded_rectangle",
            auroradb_type="RoundedRectangle",
            values=[0.0, 0.0, width, height, radius],
            source_path=source_path,
            source_key=source_key,
        )
    if kind in {"SQUARE", "FIG_SQUARE"}:
        side = max(width, height)
        width = side
        height = side
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
    selected = _selected_outline_group(payload.outlines or [])
    if selected:
        values = _outline_group_values(selected)
        if values:
            return {
                "kind": "polygon",
                "auroradb_type": "Polygon",
                "source": "alg_board_geometry_outline",
                "values": [len(values), *values, "Y", "Y"],
            }
    return _board_extents_outline(payload)


def _selected_outline_group(outlines) -> list:
    groups: dict[str, list] = defaultdict(list)
    first_index: dict[str, int] = {}
    for index, outline in enumerate(outlines):
        if outline.kind not in {"line", "arc"}:
            continue
        if outline.start is None or outline.end is None:
            continue
        group_id = _track_group_id(outline.record_tag)
        if group_id is None:
            continue
        groups[group_id].append(outline)
        first_index.setdefault(group_id, index)
    candidates = [
        group for group in groups.values() if len(group) >= 3 and _outline_bbox(group)
    ]
    if not candidates:
        return []
    return max(
        candidates,
        key=lambda group: (
            _outline_area(group),
            len(group),
            -first_index.get(_track_group_id(group[0].record_tag) or "", 0),
        ),
    )


def _outline_group_values(group: list) -> list[str]:
    first = group[0].start
    if first is None:
        return []
    values = [_outline_point_value(first)]
    for index, outline in enumerate(group):
        end = outline.end
        if end is None:
            continue
        closing = index == len(group) - 1 and _same_alg_point(end, first)
        if outline.kind == "arc" and outline.center is not None:
            values.append(
                _outline_arc_value(
                    end,
                    outline.center,
                    "N" if outline.clockwise else "Y",
                )
            )
        elif not closing:
            values.append(_outline_point_value(end))
    return values


def _outline_bbox(group: list) -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for outline in group:
        for point in [outline.start, outline.end, outline.center]:
            if point is None:
                continue
            xs.append(point.x)
            ys.append(point.y)
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _outline_area(group: list) -> float:
    bbox = _outline_bbox(group)
    if bbox is None:
        return 0.0
    x_min, y_min, x_max, y_max = bbox
    return abs((x_max - x_min) * (y_max - y_min))


def _same_alg_point(left: ALGPoint, right: ALGPoint) -> bool:
    return abs(left.x - right.x) <= 1e-9 and abs(left.y - right.y) <= 1e-9


def _outline_point_value(point: ALGPoint) -> str:
    return f"({point.x},{point.y})"


def _outline_arc_value(end: ALGPoint, center: ALGPoint, direction: str) -> str:
    return f"({end.x},{end.y},{center.x},{center.y},{direction})"


def _board_extents_outline(payload: ALGLayout):
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
