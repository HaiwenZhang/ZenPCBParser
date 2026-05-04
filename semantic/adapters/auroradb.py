from __future__ import annotations

import math

from aurora_translator.sources.auroradb.models import (
    AuroraDBModel,
    AuroraLocationModel,
    AuroraPartModel,
    AuroraPartPadModel,
    AuroraShapeSymbolModel,
    AuroraStoredNodeModel,
)
from aurora_translator.semantic.adapters.utils import (
    point_from_pair,
    role_from_layer_type,
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
    SemanticMetadata,
    SemanticNet,
    SemanticPad,
    SemanticPin,
    SemanticPrimitive,
    SemanticShape,
    SemanticSummary,
    SemanticVia,
)
from aurora_translator.semantic.passes import (
    build_connectivity_diagnostics,
    build_connectivity_edges,
)


def from_auroradb(payload: AuroraDBModel) -> SemanticBoard:
    nets_by_id: dict[str, SemanticNet] = {}
    components_by_id: dict[str, SemanticComponent] = {}
    footprints_by_id: dict[str, SemanticFootprint] = {}
    component_part_by_id: dict[str, str | None] = {}
    component_footprint_symbol_by_id: dict[str, str | None] = {}
    pins: list[SemanticPin] = []
    pads: list[SemanticPad] = []
    vias: list[SemanticVia] = []
    primitives: list[SemanticPrimitive] = []
    shapes: list[SemanticShape] = []
    shape_ids_by_symbol_id: dict[str, str] = {}
    shape_nodes_by_symbol_id: dict[str, AuroraStoredNodeModel] = {}

    parts = payload.parts.parts if payload.parts else []
    parts_by_name = {part.info.name: part for part in parts if part.info.name}
    part_index_by_name = {
        part.info.name: index for index, part in enumerate(parts) if part.info.name
    }

    def ensure_footprint(
        symbol_id: str | None,
        *,
        part_name: str | None = None,
        source_path: str | None = None,
        raw_id: object | None = None,
    ) -> str | None:
        if not symbol_id:
            return None
        footprint_id = semantic_id("footprint", symbol_id)
        if footprint_id not in footprints_by_id:
            footprints_by_id[footprint_id] = SemanticFootprint(
                id=footprint_id,
                name=symbol_id,
                part_name=part_name,
                source=source_ref("auroradb", source_path, raw_id or symbol_id),
            )
        elif part_name and footprints_by_id[footprint_id].part_name is None:
            footprints_by_id[footprint_id].part_name = part_name
        return footprint_id

    footprint_pad_templates: dict[
        tuple[str, str], tuple[AuroraPartPadModel, str | None, str]
    ] = {}
    if payload.parts is not None:
        for footprint_index, footprint in enumerate(payload.parts.footprints):
            ensure_footprint(
                footprint.symbol_id,
                source_path=f"parts.footprints[{footprint_index}]",
                raw_id=footprint.symbol_id,
            )
            for metal_index, metal_layer in enumerate(footprint.metal_layers):
                for pad_index, pad in enumerate(metal_layer.part_pads):
                    _record_footprint_pad_template(
                        footprint_pad_templates,
                        footprint.symbol_id,
                        pad,
                        metal_layer.name,
                        f"parts.footprints[{footprint_index}].metal_layers[{metal_index}].part_pads[{pad_index}]",
                    )
                for logic_index, logic_layer in enumerate(metal_layer.logic_layers):
                    for pad_index, pad in enumerate(logic_layer.part_pads):
                        _record_footprint_pad_template(
                            footprint_pad_templates,
                            footprint.symbol_id,
                            pad,
                            logic_layer.name or metal_layer.name,
                            (
                                f"parts.footprints[{footprint_index}].metal_layers[{metal_index}]"
                                f".logic_layers[{logic_index}].part_pads[{pad_index}]"
                            ),
                        )

    stack_order = (
        payload.layout.layer_stackup.metal_layers
        if payload.layout and payload.layout.layer_stackup
        else []
    )
    order_by_name = {name: index for index, name in enumerate(stack_order)}

    layers: list[SemanticLayer] = []
    for index, layer in enumerate(payload.layers):
        order_index = order_by_name.get(layer.name, index)
        layers.append(
            SemanticLayer(
                id=semantic_id("layer", layer.name, index),
                name=layer.name,
                layer_type=layer.type,
                role=role_from_layer_type(layer.type),
                side=side_from_layer_name(layer.name),
                order_index=order_index,
                source=source_ref(
                    "auroradb", f"layers[{index}]", layer.id or layer.name
                ),
            )
        )

    if payload.layout is not None:
        for shape_index, shape in enumerate(payload.layout.shapes):
            semantic_shape = _semantic_shape_from_aurora(shape, shape_index)
            if semantic_shape is None:
                continue
            shapes.append(semantic_shape)
            shape_ids_by_symbol_id[shape.id] = semantic_shape.id
            if shape.geometry is not None:
                shape_nodes_by_symbol_id[shape.id] = shape.geometry

    if payload.layout is not None:
        for net_index, net in enumerate(payload.layout.nets):
            net_id = semantic_id("net", net.name, net_index)
            nets_by_id[net_id] = SemanticNet(
                id=net_id,
                name=net.name,
                role=role_from_net_name(net.name, net.type),
                source=source_ref("auroradb", f"layout.nets[{net_index}]", net.name),
            )

    for layer_index, layer in enumerate(payload.layers):
        for component_index, component in enumerate(layer.components):
            component_id = semantic_id(
                "component", component.name, f"{layer_index}_{component_index}"
            )
            part = parts_by_name.get(component.part_name or "")
            part_index = part_index_by_name.get(component.part_name or "")
            footprint_symbol = _footprint_symbol_for_part(part) or component.part_name
            footprint_source_path = (
                f"parts.parts[{part_index}].footprint_symbols[0]"
                if part_index is not None and _footprint_symbol_for_part(part)
                else f"layers[{layer_index}].components[{component_index}]"
            )
            footprint_id = ensure_footprint(
                footprint_symbol,
                part_name=component.part_name,
                source_path=footprint_source_path,
                raw_id=footprint_symbol,
            )
            components_by_id[component_id] = SemanticComponent(
                id=component_id,
                refdes=component.name,
                name=component.name,
                part_name=component.part_name,
                package_name=footprint_symbol or component.part_name,
                footprint_id=footprint_id,
                layer_name=layer.name,
                side=side_from_layer_name(layer.name),
                value=component.value,
                location=point_from_pair(component.location),
                rotation=component.location.rotation if component.location else None,
                source=source_ref(
                    "auroradb",
                    f"layers[{layer_index}].components[{component_index}]",
                    component.name,
                ),
            )
            component_part_by_id[component_id] = component.part_name
            component_footprint_symbol_by_id[component_id] = footprint_symbol
        for net_geometry_index, net_geometry in enumerate(layer.net_geometries):
            net_id = semantic_id("net", net_geometry.net_name)
            for geometry_index, geometry in enumerate(net_geometry.geometries):
                primitive_kind, primitive_geometry = _net_geometry_payload(
                    geometry.symbol_id,
                    geometry.location,
                    geometry.geometry,
                    shape_ids_by_symbol_id,
                    shape_nodes_by_symbol_id,
                )
                if primitive_geometry is None:
                    continue
                primitive_id = semantic_id(
                    "primitive",
                    f"{layer.name}:{net_geometry.net_name}:{geometry.symbol_id}",
                    f"{layer_index}_{net_geometry_index}_{geometry_index}",
                )
                primitives.append(
                    SemanticPrimitive(
                        id=primitive_id,
                        kind=primitive_kind,
                        layer_name=layer.name,
                        net_id=net_id,
                        geometry=primitive_geometry,
                        source=source_ref(
                            "auroradb",
                            f"layers[{layer_index}].net_geometries[{net_geometry_index}].geometries[{geometry_index}]",
                            geometry.symbol_id,
                        ),
                    )
                )
                if net_id in nets_by_id:
                    unique_append(nets_by_id[net_id].primitive_ids, primitive_id)

    if payload.layout is not None:
        for net_index, net in enumerate(payload.layout.nets):
            net_id = semantic_id("net", net.name, net_index)
            for pin_index, pin in enumerate(net.pins):
                component_id = (
                    semantic_id("component", pin.component) if pin.component else None
                )
                pin_owner = component_id or pin.component or net.name
                pin_id = semantic_id(
                    "pin",
                    f"{pin_owner}:{pin.pin}" if pin.pin else None,
                    f"{net_index}_{pin_index}",
                )
                footprint_symbol = component_footprint_symbol_by_id.get(
                    component_id or ""
                )
                footprint_id = (
                    semantic_id("footprint", footprint_symbol)
                    if footprint_symbol
                    else None
                )
                part = parts_by_name.get(
                    component_part_by_id.get(component_id or "") or ""
                )
                mapped_pad_name = _mapped_pad_name(part, pin.pin, footprint_symbol)
                pad_name = mapped_pad_name or pin.pin
                template = (
                    footprint_pad_templates.get((footprint_symbol, pad_name))
                    if footprint_symbol and pad_name
                    else None
                )
                resolved_layer_name = _resolved_net_pin_layer(
                    pin,
                    components_by_id.get(component_id or ""),
                    template,
                )
                semantic_pin = SemanticPin(
                    id=pin_id,
                    name=pin.pin,
                    component_id=component_id,
                    net_id=net_id,
                    layer_name=resolved_layer_name,
                    source=source_ref(
                        "auroradb",
                        f"layout.nets[{net_index}].pins[{pin_index}]",
                        pin.pin,
                    ),
                )
                pins.append(semantic_pin)
                if component_id in components_by_id:
                    unique_append(components_by_id[component_id].pin_ids, pin_id)
                if net_id in nets_by_id:
                    unique_append(nets_by_id[net_id].pin_ids, pin_id)

                pad_id = semantic_id(
                    "pad",
                    f"{pin_owner}:{pad_name}" if pad_name else None,
                    f"{net_index}_{pin_index}",
                )
                semantic_pad = SemanticPad(
                    id=pad_id,
                    name=pad_name,
                    footprint_id=footprint_id,
                    component_id=component_id,
                    pin_id=pin_id,
                    net_id=net_id,
                    layer_name=resolved_layer_name,
                    padstack_definition=template[0].template_id if template else None,
                    geometry={
                        "source_pin_raw": list(pin.raw),
                        "footprint_pad_source": template[2] if template else None,
                        "footprint_pad_location": (
                            template[0].location.model_dump(mode="json")
                            if template and template[0].location
                            else None
                        ),
                    },
                    source=source_ref(
                        "auroradb",
                        f"layout.nets[{net_index}].pins[{pin_index}]",
                        pin.pin,
                    ),
                )
                pads.append(semantic_pad)
                unique_append(semantic_pin.pad_ids, pad_id)
                if component_id in components_by_id:
                    unique_append(components_by_id[component_id].pad_ids, pad_id)
                if footprint_id in footprints_by_id:
                    unique_append(footprints_by_id[footprint_id].pad_ids, pad_id)
                if net_id in nets_by_id:
                    unique_append(nets_by_id[net_id].pad_ids, pad_id)
            for via_index, via in enumerate(net.vias):
                via_id = semantic_id(
                    "via", f"{net.name}:{via.via_id}", f"{net_index}_{via_index}"
                )
                vias.append(
                    SemanticVia(
                        id=via_id,
                        net_id=net_id,
                        position=point_from_pair(via.location),
                        source=source_ref(
                            "auroradb",
                            f"layout.nets[{net_index}].vias[{via_index}]",
                            via.via_id,
                        ),
                    )
                )
                if net_id in nets_by_id:
                    unique_append(nets_by_id[net_id].via_ids, via_id)

    diagnostics = [
        SemanticDiagnostic(
            severity="warning",
            code="auroradb.source_diagnostic",
            message=message,
            source=source_ref("auroradb", "diagnostics"),
        )
        for message in payload.diagnostics
    ]

    board = SemanticBoard(
        metadata=SemanticMetadata(
            source_format="auroradb",
            source=payload.root,
            source_parser_version=payload.metadata.parser_version,
            source_schema_version=payload.metadata.output_schema_version,
        ),
        units=payload.layout.units if payload.layout else payload.summary.units,
        summary=SemanticSummary(),
        layers=layers,
        shapes=shapes,
        nets=list(nets_by_id.values()),
        components=list(components_by_id.values()),
        footprints=list(footprints_by_id.values()),
        pins=pins,
        pads=pads,
        vias=vias,
        primitives=primitives,
        diagnostics=diagnostics,
    )
    board = board.model_copy(update={"connectivity": build_connectivity_edges(board)})
    board = board.model_copy(
        update={
            "diagnostics": [*board.diagnostics, *build_connectivity_diagnostics(board)]
        }
    )
    return board.with_computed_summary()


def _semantic_shape_from_aurora(
    shape: AuroraShapeSymbolModel, shape_index: int
) -> SemanticShape | None:
    if shape.geometry is None:
        return None
    values = _shape_values_from_node(shape.geometry)
    if not values:
        return None
    auroradb_type = shape.geometry.name
    return SemanticShape(
        id=semantic_id("shape", shape.id, shape_index),
        name=shape.name or shape.id,
        kind=_semantic_shape_kind(auroradb_type),
        auroradb_type=auroradb_type,
        values=values,
        source=source_ref("auroradb", f"layout.shapes[{shape_index}]", shape.id),
    )


def _shape_values_from_node(
    node: AuroraStoredNodeModel,
) -> list[str | float | int]:
    if node.name.casefold() == "polygon":
        return _polygon_values_from_node(node)
    return list(node.values)


def _semantic_shape_kind(auroradb_type: str | None) -> str:
    text = (auroradb_type or "").replace("_", "").casefold()
    if text == "circle":
        return "circle"
    if text in {"rectangle", "square"}:
        return "rectangle"
    if text in {"roundedrectangle", "oval"}:
        return "rounded_rectangle"
    if text == "rectcutcorner":
        return "rect_cut_corner"
    if text == "polygon":
        return "polygon"
    return text or "unknown"


def _net_geometry_payload(
    symbol_id: str | None,
    location: AuroraLocationModel | None,
    inline_geometry: AuroraStoredNodeModel | None,
    shape_ids_by_symbol_id: dict[str, str],
    shape_nodes_by_symbol_id: dict[str, AuroraStoredNodeModel],
) -> tuple[str, dict[str, object] | None]:
    shape_id = shape_ids_by_symbol_id.get(symbol_id or "")
    geometry_node = inline_geometry or shape_nodes_by_symbol_id.get(symbol_id or "")
    location_payload = location.model_dump(mode="json") if location else None

    if geometry_node is not None and geometry_node.name.casefold() in {
        "polygon",
        "polygonhole",
    }:
        raw_points = _polygon_points_from_node(geometry_node)
        if len(raw_points) < 3:
            return "polygon", None
        transformed_points = _transform_polygon_points(raw_points, location)
        _, solid = _polygon_flags_from_node(geometry_node)
        payload: dict[str, object] = {
            "symbol_id": symbol_id,
            "raw_points": transformed_points,
            "is_negative": solid is False,
        }
        voids = _polygon_voids_from_node(geometry_node, location)
        if voids:
            payload["voids"] = voids
        if shape_id:
            payload["shape_id"] = shape_id
        if location_payload:
            payload["location"] = location_payload
        return "polygon", payload

    if geometry_node is not None and geometry_node.name.casefold() == "line":
        points = _line_points_from_node(geometry_node)
        if points is None:
            return "trace", None
        return (
            "trace",
            {
                "symbol_id": symbol_id,
                "center_line": points,
                "width": _shape_trace_width(shape_nodes_by_symbol_id.get(symbol_id or "")),
            },
        )

    if geometry_node is not None and geometry_node.name.casefold() == "larc":
        arc = _arc_geometry_from_node(geometry_node)
        if arc is None:
            return "arc", None
        arc["symbol_id"] = symbol_id
        arc["width"] = _shape_trace_width(shape_nodes_by_symbol_id.get(symbol_id or ""))
        return "arc", arc

    if shape_id and location is not None:
        return (
            "net_geometry",
            {
                "symbol_id": symbol_id,
                "shape_id": shape_id,
                "location": location_payload,
            },
        )

    return "net_geometry", None


def _polygon_values_from_node(
    node: AuroraStoredNodeModel,
) -> list[str | float | int]:
    points = _polygon_points_from_node(node)
    if len(points) < 3:
        return []
    ccw, solid = _polygon_flags_from_node(node)
    return [
        len(points),
        *[_polygon_point_value(x, y) for x, y in points],
        "Y" if ccw else "N",
        "Y" if solid else "N",
    ]


def _polygon_points_from_node(node: AuroraStoredNodeModel) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    arc_hints: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for child in node.children:
        name = child.name.casefold()
        if name == "pnt" and len(child.values) >= 2:
            try:
                points.append((float(child.values[0]), float(child.values[1])))
            except ValueError:
                continue
        elif name == "parc" and len(child.values) >= 4:
            try:
                endpoint = (float(child.values[0]), float(child.values[1]))
                center = (float(child.values[2]), float(child.values[3]))
            except ValueError:
                continue
            arc_hints.append((endpoint, center))
            if not points or not _same_point(points[-1], endpoint):
                points.append(endpoint)
    if len(points) >= 2 and _same_point(points[0], points[-1]):
        points.pop()
    if len(points) < 3:
        circular_points = _arc_only_polygon_points(points, arc_hints)
        if circular_points:
            return circular_points
    return points


def _arc_only_polygon_points(
    points: list[tuple[float, float]],
    arc_hints: list[tuple[tuple[float, float], tuple[float, float]]],
) -> list[tuple[float, float]]:
    if not arc_hints:
        return []
    start = points[0] if points else arc_hints[0][0]
    endpoint, center = arc_hints[0]
    if not _same_point(start, endpoint):
        return []
    radius = math.hypot(start[0] - center[0], start[1] - center[1])
    if radius <= 0:
        return []
    return [
        (
            center[0] + math.cos((2.0 * math.pi * index) / 16.0) * radius,
            center[1] + math.sin((2.0 * math.pi * index) / 16.0) * radius,
        )
        for index in range(16)
    ]


def _polygon_flags_from_node(node: AuroraStoredNodeModel) -> tuple[bool, bool]:
    ccw = True
    solid = True
    for child in node.children:
        name = child.name.casefold()
        value = child.values[0] if child.values else None
        if name == "ccw":
            ccw = _aurora_bool(value, default=True)
        elif name == "solid":
            solid = _aurora_bool(value, default=True)
    return ccw, solid


def _transform_polygon_points(
    points: list[tuple[float, float]], location: AuroraLocationModel | None
) -> list[list[float]]:
    if location is None:
        return [[x, y] for x, y in points]

    origin_x = location.x or 0.0
    origin_y = location.y or 0.0
    scale = location.scale if location.scale not in {None, 0} else 1.0
    angle = location.rotation or 0.0
    if location.ccw is False:
        angle = -angle
    cos_angle = math.cos(angle)
    sin_angle = math.sin(angle)

    transformed: list[list[float]] = []
    for x, y in points:
        local_x = -x if location.flip_x else x
        local_y = -y if location.flip_y else y
        local_x *= scale
        local_y *= scale
        transformed.append(
            [
                origin_x + local_x * cos_angle - local_y * sin_angle,
                origin_y + local_x * sin_angle + local_y * cos_angle,
            ]
        )
    return transformed


def _line_points_from_node(node: AuroraStoredNodeModel) -> list[list[float]] | None:
    values = _float_values(node.values)
    if len(values) < 4:
        return None
    return [[values[0], values[1]], [values[2], values[3]]]


def _arc_geometry_from_node(node: AuroraStoredNodeModel) -> dict[str, object] | None:
    values = _float_values(node.values[:6])
    if len(values) < 6:
        return None
    is_ccw = _aurora_bool(node.values[6] if len(node.values) > 6 else None, default=True)
    return {
        "start": [values[0], values[1]],
        "end": [values[2], values[3]],
        "center": [values[4], values[5]],
        "is_ccw": is_ccw,
    }


def _polygon_voids_from_node(
    node: AuroraStoredNodeModel, location: AuroraLocationModel | None
) -> list[dict[str, object]]:
    voids: list[dict[str, object]] = []
    for child in node.children:
        if child.name.casefold() != "holes":
            continue
        for hole in child.children:
            if hole.name.casefold() not in {"polygon", "polygonhole"}:
                continue
            points = _polygon_points_from_node(hole)
            if len(points) < 3:
                continue
            voids.append(
                {"raw_points": _transform_polygon_points(points, location)}
            )
    return voids


def _shape_trace_width(node: AuroraStoredNodeModel | None) -> float | None:
    if node is None or node.name.casefold() != "circle" or len(node.values) < 3:
        return None
    try:
        return float(node.values[2])
    except ValueError:
        return None


def _float_values(values: list[str]) -> list[float]:
    result: list[float] = []
    for value in values:
        try:
            result.append(float(value))
        except ValueError:
            break
    return result


def _resolved_net_pin_layer(
    pin,
    component: SemanticComponent | None,
    template: tuple[AuroraPartPadModel, str | None, str] | None,
) -> str | None:
    return (
        _canonical_metal_layer_name(pin.metal_layer)
        or _canonical_metal_layer_name(template[1] if template else None)
        or _metal_layer_from_component_layer(pin.component_layer)
        or (component.layer_name if component is not None else None)
    )


def _metal_layer_from_component_layer(layer_name: str | None) -> str | None:
    if not layer_name:
        return None
    text = layer_name.strip()
    upper = text.upper()
    if upper.startswith("COMP_+_"):
        return text[7:]
    if upper.startswith("COMP_"):
        value = text[5:]
        if value.upper() == "BOT":
            return "BOTTOM"
        return _canonical_metal_layer_name(value)
    return _canonical_metal_layer_name(text)


def _canonical_metal_layer_name(layer_name: str | None) -> str | None:
    if not layer_name:
        return None
    text = layer_name.strip()
    folded = text.casefold()
    if folded == "top":
        return "TOP"
    if folded in {"bot", "bottom"}:
        return "BOTTOM"
    return text


def _polygon_point_value(x: float, y: float) -> str:
    return f"({_shape_number(x)},{_shape_number(y)})"


def _shape_number(value: float) -> str:
    return f"{value:.12g}"


def _same_point(left: tuple[float, float], right: tuple[float, float]) -> bool:
    return abs(left[0] - right[0]) <= 1e-9 and abs(left[1] - right[1]) <= 1e-9


def _aurora_bool(value: object | None, *, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}


def _record_footprint_pad_template(
    templates: dict[tuple[str, str], tuple[AuroraPartPadModel, str | None, str]],
    footprint_symbol: str | None,
    pad: AuroraPartPadModel,
    layer_name: str | None,
    source_path: str,
) -> None:
    if footprint_symbol and pad.pad_id:
        templates.setdefault(
            (footprint_symbol, pad.pad_id), (pad, layer_name, source_path)
        )


def _footprint_symbol_for_part(part: AuroraPartModel | None) -> str | None:
    if part is None:
        return None
    for symbol_id in part.footprint_symbols:
        if symbol_id:
            return symbol_id
    return None


def _mapped_pad_name(
    part: AuroraPartModel | None, pin_name: str | None, footprint_symbol: str | None
) -> str | None:
    if part is None or not pin_name:
        return None
    for part_pin in part.pins:
        if pin_name not in {part_pin.number, part_pin.name}:
            continue
        if footprint_symbol:
            for mapping in part_pin.footprint_pad_map:
                if mapping.footprint == footprint_symbol:
                    return mapping.pad_id
        for mapping in part_pin.footprint_pad_map:
            if mapping.pad_id:
                return mapping.pad_id
    return None
