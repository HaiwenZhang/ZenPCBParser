from __future__ import annotations

from typing import Any

from aurora_translator.targets.auroradb.direct import (
    _AedbComponentPlacement,
    _TracePoint,
    _TraceShape,
)
from aurora_translator.targets.auroradb.formatting import (
    _format_number,
    _format_rotation,
    _format_scalar,
    _is_coordinate,
    _is_finite,
    _length_to_mil,
    _normalize_degree,
    _number,
    _point_tuple,
    _rotation_degrees,
    _source_rotations_are_clockwise,
    _truthy,
)
from aurora_translator.targets.auroradb.names import (
    _aaf_atom,
    _auroradb_net_name,
    _quote_aaf,
    _standardize_name,
)
from aurora_translator.semantic.models import (
    SemanticBoard,
    SemanticComponent,
    SemanticPad,
    SemanticPin,
    SemanticPoint,
    SemanticPrimitive,
    SemanticShape,
    SemanticVia,
    SemanticViaTemplate,
)


_DEFAULT_SOURCE_UNIT = object()


def _direct_location_values(
    x: float,
    y: float,
    *,
    rotation: str | float | int | None = None,
    flip_x: bool = False,
    flip_y: bool = False,
) -> list[str]:
    rot = "0" if rotation is None or rotation == "" else str(rotation)
    return [
        _format_number(x),
        _format_number(y),
        "Y",
        rot,
        "1",
        _bool_aaf(flip_x),
        _bool_aaf(flip_y),
    ]


def _bool_aaf(value: bool) -> str:
    return "Y" if value else "N"


def _geometry_signature(
    shape: dict[str, Any], *, source_unit: str | None
) -> tuple[str, tuple[str, ...]] | None:
    geometry_type = str(shape.get("auroradb_type") or shape.get("kind") or "")
    values = shape.get("values")
    if not geometry_type or not isinstance(values, list):
        return None
    formatted_values = _format_geometry_shape_values(
        geometry_type, values, source_unit=source_unit
    )
    if not formatted_values:
        return None
    return geometry_type, tuple(formatted_values)


def _footprint_geometry_commands(
    footprint: Any,
    footprint_name: str,
    *,
    source_unit: str | None,
) -> list[str]:
    if footprint is None:
        return []
    geometry = getattr(footprint, "geometry", None)
    if not geometry:
        return []
    outlines = geometry.get("outlines")
    if not isinstance(outlines, list):
        return []
    commands: list[str] = []
    for index, outline in enumerate(outlines, start=1):
        if not isinstance(outline, dict):
            continue
        payload = _outline_geometry_payload(
            outline, f"B{index}", source_unit=source_unit
        )
        if payload is None:
            continue
        commands.append(
            "library add "
            f"-g <{payload}> "
            "-layer <top:1> "
            f"-footprint <{_quote_aaf(footprint_name)}>"
        )
    return commands


def _outline_geometry_payload(
    outline: dict[str, Any],
    geometry_id: str,
    *,
    source_unit: str | None,
) -> str | None:
    geometry_type = str(outline.get("auroradb_type") or outline.get("kind") or "")
    values = outline.get("values")
    if not geometry_type or not isinstance(values, list) or not values:
        return None
    formatted_values = _format_geometry_shape_values(
        geometry_type, values, source_unit=source_unit
    )
    if not formatted_values:
        return None
    return f"{{{geometry_id}:{geometry_type},({','.join(formatted_values)})}}"


def _shape_command(
    shape: SemanticShape, shape_id: str, *, source_unit: str | None
) -> str | None:
    payload = _shape_geometry_payload(shape, shape_id, source_unit=source_unit)
    if payload is None:
        return None
    shape_code = _shape_code_for_shape(shape)
    return f"layout add -g <{payload}> -id <{shape_id}> -shape <{shape_code}>"


def _shape_geometry_payload(
    shape: SemanticShape, geometry_id: str, *, source_unit: str | None
) -> str | None:
    geometry_type = _shape_auroradb_type(shape)
    values = _format_geometry_shape_values(
        geometry_type, shape.values, source_unit=source_unit
    )
    if not geometry_type or not values:
        return None
    return f"{{{geometry_id}:{geometry_type},({','.join(values)})}}"


def _trace_shape_command(trace_shape: _TraceShape) -> str:
    width = _format_number(trace_shape.width_mil)
    return (
        "layout add "
        f"-g <{{{trace_shape.shape_id}:Circle,(0,0,{width})}}> "
        f"-id <{trace_shape.shape_id}> "
        "-shape <0>"
    )


def _via_template_command(
    via_template: SemanticViaTemplate,
    via_template_id: str,
    shape_ids: dict[str, str],
    layer_name_map: dict[str, str],
    *,
    source_format: str | None = None,
) -> str | None:
    barrel_shape_id = shape_ids.get(via_template.barrel_shape_id or "", "null")
    values = [via_template_id, barrel_shape_id]
    for layer_pad in via_template.layer_pads:
        layer_name = _semantic_layer_name(layer_pad.layer_name, layer_name_map)
        pad_shape_id = shape_ids.get(layer_pad.pad_shape_id or "", "null")
        antipad_shape_id = shape_ids.get(layer_pad.antipad_shape_id or "", "null")
        pad_rotation, pad_ccw = _via_template_layer_rotation(
            via_template,
            layer_pad.layer_name,
            "pad",
            source_format=source_format,
        )
        antipad_rotation, antipad_ccw = _via_template_layer_rotation(
            via_template,
            layer_pad.layer_name,
            "antipad",
            source_format=source_format,
        )
        values.append(
            f"{layer_name}:{pad_shape_id}:{pad_rotation}:{pad_ccw}:{antipad_shape_id}:{antipad_rotation}:{antipad_ccw}"
        )
    if len(values) <= 2 and barrel_shape_id == "null":
        return None
    return (
        f"layout add -via <{','.join(values)}> -name <{_quote_aaf(via_template.name)}>"
    )


def _component_layers(
    board: SemanticBoard, layer_name_map: dict[str, str]
) -> dict[str, str]:
    result: dict[str, str] = {}
    for component in board.components:
        metal_layer = _component_metal_layer(component, layer_name_map)
        if metal_layer is None:
            continue
        result.setdefault(_component_layer_name(metal_layer), metal_layer)
    return result


def _component_command(
    component: SemanticComponent,
    layer_name_map: dict[str, str],
    *,
    source_unit: str | None,
    placement: _AedbComponentPlacement | None = None,
    part_name_override: str | None = None,
    source_format: str | None = None,
) -> str | None:
    metal_layer = _component_metal_layer(component, layer_name_map)
    if metal_layer is None:
        return None

    x, y = _point_coordinates(component.location, source_unit=source_unit)
    rotation = _format_rotation(
        _component_rotation_for_export(
            component, placement=placement, source_format=source_format
        ),
        source_format=source_format,
    )
    flip_x, flip_y = _component_flip_flags(
        component, placement=placement, source_format=source_format
    )
    part_name = (
        placement.export_part_name
        if placement is not None
        else (part_name_override or _component_part_name(component))
    )
    values = [
        "layout add",
        f"-component <{_aaf_atom(_component_name(component))}>",
        f"-part <{_quote_aaf(part_name)}>",
        f"-layer <{_component_layer_name(metal_layer)}>",
        f"-location <({_format_number(x)},{_format_number(y)})>",
        f"-rotation <{rotation}>",
    ]
    if flip_x:
        values.append("-flipX")
    if flip_y:
        values.append("-flipY")
    if component.value not in {None, ""}:
        values.append(f"-value <{_quote_aaf(str(component.value))}>")
    return " ".join(values)


def _net_pin_command(
    pin: SemanticPin,
    components_by_id: dict[str, SemanticComponent],
    net_names_by_id: dict[str, str],
    layer_name_map: dict[str, str],
) -> str | None:
    if not pin.net_id or not pin.component_id:
        return None
    component = components_by_id.get(pin.component_id)
    net_name = net_names_by_id.get(pin.net_id)
    if component is None or net_name is None:
        return None

    component_metal_layer = _component_metal_layer(component, layer_name_map)
    pin_metal_layer = _pin_metal_layer(pin, component, layer_name_map)
    if component_metal_layer is None or pin_metal_layer is None:
        return None
    metal_option = ""
    if component_metal_layer != pin_metal_layer:
        metal_option = f" -metal <{component_metal_layer}>"
    return (
        "layout add "
        f"-component <{_aaf_atom(_component_name(component))}> "
        f"-layer <{_component_layer_name(component_metal_layer)}> "
        f"-pin <{_aaf_atom(_pin_name(pin))}> "
        f"-net <{_quote_aaf(net_name)}>"
        f"{metal_option}"
    )


def _pad_shape_command(
    pad: SemanticPad,
    components_by_id: dict[str, SemanticComponent],
    net_names_by_id: dict[str, str],
    shape_ids: dict[str, str],
    pad_shape_ids: dict[tuple[str, str], str],
    layer_name_map: dict[str, str],
    *,
    source_unit: str | None,
    source_format: str | None = None,
) -> str | None:
    if pad.geometry.get("suppress_shape_export"):
        return None
    if not pad.net_id or pad.position is None:
        return None
    component = components_by_id.get(pad.component_id or "")
    net_name = net_names_by_id.get(pad.net_id)
    layer_name = _pad_metal_layer(pad, component, layer_name_map)
    semantic_shape_id = _pad_shape_id_for_layer(pad, pad_shape_ids, layer_name)
    shape_id = shape_ids.get(semantic_shape_id or "")
    if net_name is None or layer_name is None or shape_id is None:
        return None

    x, y = _point_coordinates(pad.position, source_unit=source_unit)
    rotation = _format_rotation(_pad_rotation(pad), source_format=source_format)
    flip_options = _pad_flip_options(pad)
    return (
        "layout add "
        f"-shape <{shape_id}> "
        f"-location <({_format_number(x)},{_format_number(y)})> "
        f"-rotation <{rotation}> "
        f"{flip_options}"
        f"-layer <{layer_name}> "
        f"-net <{_quote_aaf(net_name)}>"
    )


def _primitive_commands(
    board: SemanticBoard,
    layer_name_map: dict[str, str],
    net_names_by_id: dict[str, str],
    trace_shape_ids: dict[str, _TraceShape],
    *,
    source_unit: str | None | object = _DEFAULT_SOURCE_UNIT,
) -> list[str]:
    source_unit = board.units if source_unit is _DEFAULT_SOURCE_UNIT else source_unit
    commands: list[str] = []
    geometry_index = 1
    for primitive in board.primitives:
        if not primitive.net_id:
            continue
        net_name = net_names_by_id.get(primitive.net_id)
        layer_name = _primitive_layer_name(primitive, layer_name_map)
        if net_name is None or layer_name is None:
            continue
        kind = primitive.kind.casefold()
        if kind == "trace":
            trace_commands = _trace_commands(
                primitive,
                net_name,
                layer_name,
                trace_shape_ids,
                start_index=geometry_index,
                source_unit=source_unit,
            )
            geometry_index += len(trace_commands)
            commands.extend(trace_commands)
        elif kind == "arc":
            arc_command = _arc_command(
                primitive,
                net_name,
                layer_name,
                trace_shape_ids,
                geometry_id=f"A{geometry_index}",
                source_unit=source_unit,
            )
            if arc_command is not None:
                geometry_index += 1
                commands.append(arc_command)
        elif kind in {"polygon", "zone"}:
            polygon_commands = _polygon_commands(
                primitive,
                net_name,
                layer_name,
                geometry_id=f"G{geometry_index}",
                source_unit=source_unit,
            )
            if polygon_commands:
                geometry_index += 1
                commands.extend(polygon_commands)
    return commands


def _arc_command(
    primitive: SemanticPrimitive,
    net_name: str,
    layer_name: str,
    trace_shape_ids: dict[str, _TraceShape],
    *,
    geometry_id: str,
    source_unit: str | None,
) -> str | None:
    start = _point_tuple(primitive.geometry.get("start"), source_unit=source_unit)
    end = _point_tuple(primitive.geometry.get("end"), source_unit=source_unit)
    center = _point_tuple(primitive.geometry.get("center"), source_unit=source_unit)
    if start is None or end is None or center is None:
        return None
    trace_shape = _trace_shape_for_width(
        primitive.geometry.get("width"),
        trace_shape_ids,
        source_unit=source_unit,
    )
    if trace_shape is None:
        return None
    ccw = _arc_ccw_flag(primitive.geometry)
    return (
        "layout add "
        f"-g <{{{geometry_id}:Larc,({_format_number(start[0])},{_format_number(start[1])},"
        f"{_format_number(end[0])},{_format_number(end[1])},{_format_number(center[0])},"
        f"{_format_number(center[1])},{ccw})}}> "
        f"-shape <{trace_shape.shape_id}> "
        f"-layer <{layer_name}> "
        f"-net <{_quote_aaf(net_name)}>"
    )


def _trace_commands(
    primitive: SemanticPrimitive,
    net_name: str,
    layer_name: str,
    trace_shape_ids: dict[str, _TraceShape],
    *,
    start_index: int,
    source_unit: str | None,
) -> list[str]:
    raw_points = primitive.geometry.get("center_line")
    if not isinstance(raw_points, (list, tuple)):
        return []
    points = _trace_point_items(raw_points, source_unit=source_unit)
    if len(points) < 2:
        return []
    trace_shape = _trace_shape_for_width(
        primitive.geometry.get("width"),
        trace_shape_ids,
        source_unit=source_unit,
    )
    if trace_shape is None:
        return []

    commands: list[str] = []
    geometry_index = start_index
    for index in range(1, len(points)):
        current = points[index]
        previous = points[index - 1]
        if current.is_arc:
            continue
        if previous.is_arc:
            if index < 2 or points[index - 2].is_arc:
                continue
            start = points[index - 2]
            center = _arc_center(start, current, previous.arc_height)
            if center is None:
                continue
            x0, y0, ccw = center
            commands.append(
                "layout add "
                f"-g <{{A{geometry_index}:Larc,({_format_number(start.x)},{_format_number(start.y)},"
                f"{_format_number(current.x)},{_format_number(current.y)},{_format_number(x0)},"
                f"{_format_number(y0)},{ccw})}}> "
                f"-shape <{trace_shape.shape_id}> "
                f"-layer <{layer_name}> "
                f"-net <{_quote_aaf(net_name)}>"
            )
        else:
            commands.append(
                "layout add "
                f"-g <{{L{geometry_index}:Line,({_format_number(previous.x)},{_format_number(previous.y)},"
                f"{_format_number(current.x)},{_format_number(current.y)})}}> "
                f"-shape <{trace_shape.shape_id}> "
                f"-layer <{layer_name}> "
                f"-net <{_quote_aaf(net_name)}>"
            )
        geometry_index += 1
    return commands


def _polygon_commands(
    primitive: SemanticPrimitive,
    net_name: str,
    layer_name: str,
    *,
    geometry_id: str,
    source_unit: str | None,
) -> list[str]:
    point_values = _polygon_vertex_values(primitive.geometry, source_unit=source_unit)
    if len(point_values) < 3:
        return []

    solid = (
        "N"
        if _truthy(primitive.geometry.get("is_negative"))
        or _truthy(primitive.geometry.get("is_void"))
        else "Y"
    )
    polygon_geometry = f"{{{geometry_id}:Polygon,({len(point_values)},{','.join(point_values)},Y,{solid})}}"
    void_geometries = _void_geometry_values(primitive, source_unit=source_unit)
    if not void_geometries:
        return [
            (
                "layout add "
                f"-net <{_quote_aaf(net_name)}> "
                f"-g <{polygon_geometry}> "
                f"-layer <{layer_name}>"
            )
        ]

    outline_id = f"{geometry_id}_OUTLINE"
    commands = [
        f"layout add -container <{geometry_id}> "
        f"-g <{{{outline_id}:Polygon,({len(point_values)},{','.join(point_values)},Y,{solid})}}>"
    ]
    for void_index, void_values in enumerate(void_geometries, start=1):
        commands.append(
            f"layout add -container <{geometry_id}> "
            f"-g <{{{geometry_id}_VOID_{void_index}:Polygon,({len(void_values)},{','.join(void_values)},Y,Y)}}>"
        )
    commands.append(
        "layout add "
        f"-net <{_quote_aaf(net_name)}> "
        f"-g <{{{geometry_id}:PolygonHole,({outline_id})}}> "
        f"-layer <{layer_name}>"
    )
    return commands


def _void_geometry_values(
    primitive: SemanticPrimitive, *, source_unit: str | None
) -> list[list[str]]:
    raw_voids = primitive.geometry.get("voids")
    if not isinstance(raw_voids, (list, tuple)):
        return []
    voids: list[list[str]] = []
    for raw_void in raw_voids:
        point_parts = _polygon_vertex_parts(raw_void, source_unit=source_unit)
        if _polygon_parts_have_min_points(point_parts, 3):
            voids.append(_polygon_parts_values(point_parts))
    return voids


def _polygon_vertex_values(geometry: Any, *, source_unit: str | None) -> list[str]:
    return _polygon_parts_values(
        _polygon_vertex_parts(geometry, source_unit=source_unit)
    )


def _void_geometry_parts(
    primitive: SemanticPrimitive, *, source_unit: str | None, min_points: int = 3
) -> list[list[list[str]]]:
    raw_voids = primitive.geometry.get("voids")
    if not isinstance(raw_voids, (list, tuple)):
        return []
    voids: list[list[list[str]]] = []
    for raw_void in raw_voids:
        point_parts = _polygon_vertex_parts(
            raw_void, source_unit=source_unit, min_points=min_points
        )
        if _polygon_parts_have_min_points(point_parts, min_points):
            voids.append(point_parts)
    return voids


def _polygon_vertex_parts(
    geometry: Any, *, source_unit: str | None, min_points: int = 3
) -> list[list[str]]:
    parts = _polygon_vertex_parts_from_arcs(
        _geometry_field(geometry, "arcs"), source_unit=source_unit
    )
    if _polygon_parts_have_min_points(parts, min_points):
        return _auroradb_ccw_polygon_parts(parts)

    parts = _polygon_vertex_parts_from_raw_points(
        _geometry_field(geometry, "raw_points"), source_unit=source_unit
    )
    if _polygon_parts_have_min_points(parts, min_points):
        return _auroradb_ccw_polygon_parts(parts)

    points = _polygon_points(geometry, source_unit=source_unit)
    return _auroradb_ccw_polygon_parts([_polygon_point_parts(point) for point in points])


def _polygon_parts_have_min_points(parts: list[list[str]], min_points: int) -> bool:
    if len(parts) >= min_points:
        return True
    return _polygon_parts_are_full_circle(parts)


def _polygon_parts_are_full_circle(parts: list[list[str]]) -> bool:
    if len(parts) != 2 or len(parts[0]) != 2 or len(parts[1]) != 5:
        return False
    start_x = _number(parts[0][0])
    start_y = _number(parts[0][1])
    end_x = _number(parts[1][0])
    end_y = _number(parts[1][1])
    center_x = _number(parts[1][2])
    center_y = _number(parts[1][3])
    if None in {start_x, start_y, end_x, end_y, center_x, center_y}:
        return False
    start = (float(start_x), float(start_y))
    end = (float(end_x), float(end_y))
    center = (float(center_x), float(center_y))
    return _is_full_circle_arc(start, end, center)


def _auroradb_ccw_polygon_parts(parts: list[list[str]]) -> list[list[str]]:
    area = _polygon_parts_signed_area(parts)
    if area is None or area <= 0:
        return parts
    return _reverse_polygon_parts(parts)


def _polygon_parts_signed_area(parts: list[list[str]]) -> float | None:
    points: list[tuple[float, float]] = []
    for part in parts:
        if len(part) < 2:
            continue
        x = _number(part[0])
        y = _number(part[1])
        if x is None or y is None or not _is_finite(x) or not _is_finite(y):
            return None
        points.append((float(x), float(y)))
    if len(points) < 3:
        return None
    if _same_xy(points[0], points[-1]):
        points = points[:-1]
    if len(points) < 3:
        return None
    area = 0.0
    previous = points[-1]
    for current in points:
        area += previous[0] * current[1] - current[0] * previous[1]
        previous = current
    return area * 0.5


def _reverse_polygon_parts(parts: list[list[str]]) -> list[list[str]]:
    if len(parts) < 2:
        return parts
    closed = _same_part_point(parts[0], parts[-1])
    edges = [(parts[index - 1], parts[index]) for index in range(1, len(parts))]
    reversed_parts = [list(parts[0])]
    if not closed:
        reversed_parts.append([parts[-1][0], parts[-1][1]])
    for old_start, old_end in reversed(edges):
        if not closed and _same_part_point(old_start, parts[0]):
            continue
        new_part = [old_start[0], old_start[1]]
        if len(old_end) == 5:
            new_part.extend([old_end[2], old_end[3], _opposite_ccw_flag(old_end[4])])
        reversed_parts.append(new_part)
    return reversed_parts


def _same_part_point(left: list[str], right: list[str]) -> bool:
    if len(left) < 2 or len(right) < 2:
        return False
    left_x = _number(left[0])
    left_y = _number(left[1])
    right_x = _number(right[0])
    right_y = _number(right[1])
    if None in {left_x, left_y, right_x, right_y}:
        return False
    return _same_xy((float(left_x), float(left_y)), (float(right_x), float(right_y)))


def _same_xy(left: tuple[float, float], right: tuple[float, float]) -> bool:
    return abs(left[0] - right[0]) <= 1e-9 and abs(left[1] - right[1]) <= 1e-9


def _opposite_ccw_flag(value: str) -> str:
    return "N" if str(value).strip().upper() == "Y" else "Y"


def _polygon_vertex_values_from_arcs(
    raw_arcs: Any, *, source_unit: str | None
) -> list[str]:
    return _polygon_parts_values(
        _polygon_vertex_parts_from_arcs(raw_arcs, source_unit=source_unit)
    )


def _polygon_vertex_parts_from_arcs(
    raw_arcs: Any, *, source_unit: str | None
) -> list[list[str]]:
    if not isinstance(raw_arcs, (list, tuple)) or not raw_arcs:
        return []

    first_start: tuple[float, float] | None = None
    for arc in raw_arcs:
        first_start = _arc_point(arc, "start", source_unit=source_unit)
        if first_start is not None:
            break
    if first_start is None:
        return []

    parts = [_polygon_point_parts(first_start)]
    last_index = len(raw_arcs) - 1
    for index, arc in enumerate(raw_arcs):
        start = _arc_point(arc, "start", source_unit=source_unit)
        end = _arc_point(arc, "end", source_unit=source_unit)
        if end is None:
            continue
        is_closing_segment = index == last_index and _same_point(end, first_start)
        if _arc_is_curved(arc, source_unit=source_unit):
            center = _arc_point(arc, "center", source_unit=source_unit)
            if center is None:
                start = _arc_point(arc, "start", source_unit=source_unit)
                height = _length_to_mil(
                    _geometry_field(arc, "height"), source_unit=source_unit
                )
                if start is None or height is None:
                    if not is_closing_segment:
                        parts.append(_polygon_point_parts(end))
                    continue
                computed = _arc_center(
                    _TracePoint(x=start[0], y=start[1]),
                    _TracePoint(x=end[0], y=end[1]),
                    height,
                )
                if computed is None:
                    if not is_closing_segment:
                        parts.append(_polygon_point_parts(end))
                    continue
                center = (computed[0], computed[1])
            if start is not None and _is_full_circle_arc(start, end, center):
                parts.extend(
                    _full_circle_arc_parts(
                        start,
                        center,
                        _arc_direction_flag(arc, source_unit=source_unit),
                    )
                )
                continue
            parts.append(
                _polygon_arc_parts(
                    end, center, _arc_direction_flag(arc, source_unit=source_unit)
                )
            )
        elif not is_closing_segment:
            parts.append(_polygon_point_parts(end))
    return parts


def _polygon_vertex_values_from_raw_points(
    raw_points: Any, *, source_unit: str | None
) -> list[str]:
    return _polygon_parts_values(
        _polygon_vertex_parts_from_raw_points(raw_points, source_unit=source_unit)
    )


def _polygon_vertex_parts_from_raw_points(
    raw_points: Any, *, source_unit: str | None
) -> list[list[str]]:
    if not isinstance(raw_points, (list, tuple)):
        return []
    explicit_parts = _polygon_vertex_parts_from_explicit_raw_path(
        raw_points, source_unit=source_unit
    )
    if explicit_parts:
        return explicit_parts
    items = _trace_point_items(raw_points, source_unit=source_unit)
    if not items:
        return []

    leading_arc_height: float | None = None
    if items[0].is_arc:
        leading_arc_height = items[0].arc_height
        items = items[1:]
    if not items or items[0].is_arc:
        return []

    parts = [_polygon_point_parts((items[0].x, items[0].y))]
    for index in range(1, len(items)):
        current = items[index]
        previous = items[index - 1]
        if current.is_arc:
            continue
        end = (current.x, current.y)
        if previous.is_arc:
            if index < 2 or items[index - 2].is_arc:
                continue
            start = items[index - 2]
            center = _arc_center(start, current, previous.arc_height)
            if center is None:
                continue
            parts.append(_polygon_arc_parts(end, (center[0], center[1]), center[2]))
        else:
            parts.append(_polygon_point_parts(end))

    if leading_arc_height is not None and not items[-1].is_arc:
        center = _arc_center(items[-1], items[0], leading_arc_height)
        if center is not None:
            parts.append(
                _polygon_arc_parts(
                    (items[0].x, items[0].y), (center[0], center[1]), center[2]
                )
            )
    elif len(items) >= 2 and items[-1].is_arc and not items[-2].is_arc:
        center = _arc_center(items[-2], items[0], items[-1].arc_height)
        if center is not None:
            parts.append(
                _polygon_arc_parts(
                    (items[0].x, items[0].y), (center[0], center[1]), center[2]
                )
            )

    if len(parts) >= 2 and parts[0] == parts[-1]:
        parts.pop()
    return parts


def _polygon_vertex_parts_from_explicit_raw_path(
    raw_points: list[Any], *, source_unit: str | None
) -> list[list[str]]:
    has_explicit_arc = False
    parts: list[list[str]] = []
    for raw_point in raw_points:
        arc_parts = _explicit_polygon_arc_parts(raw_point, source_unit=source_unit)
        if arc_parts is not None:
            has_explicit_arc = True
            if parts:
                parts.append(arc_parts)
            continue
        point = _point_tuple(raw_point, source_unit=source_unit)
        if point is not None:
            parts.append(_polygon_point_parts(point))
    if not has_explicit_arc:
        return []
    if len(parts) >= 2 and parts[0] == parts[-1]:
        parts.pop()
    return parts


def _explicit_polygon_arc_parts(
    value: Any, *, source_unit: str | None
) -> list[str] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 5:
        return None
    parsed = [_length_to_mil(part, source_unit=source_unit) for part in value[:4]]
    if not all(part is not None and _is_finite(part) for part in parsed):
        return None
    end_x, end_y, center_x, center_y = [float(part) for part in parsed]
    flag = value[4]
    if isinstance(flag, bool):
        direction = _bool_aaf(flag)
    elif isinstance(flag, (int, float)) and flag in {0, 1}:
        direction = "Y" if flag else "N"
    else:
        direction = str(flag)
    return _polygon_arc_parts((end_x, end_y), (center_x, center_y), direction)


def _polygon_points(
    geometry: Any, *, source_unit: str | None
) -> list[tuple[float, float]]:
    raw_points = _geometry_field(geometry, "raw_points")
    points: list[tuple[float, float]] = []
    if isinstance(raw_points, (list, tuple)):
        points = [
            point
            for point in (
                _point_tuple(raw_point, source_unit=source_unit)
                for raw_point in raw_points
            )
            if point is not None
        ]
    points = _dedupe_consecutive(points)
    if len(points) >= 2 and points[0] == points[-1]:
        points.pop()
    if len(points) >= 3:
        return points

    bbox = _geometry_field(geometry, "bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        parsed = [_length_to_mil(value, source_unit=source_unit) for value in bbox[:4]]
        if all(value is not None and _is_coordinate(value) for value in parsed):
            x_min, y_min, x_max, y_max = [float(value) for value in parsed]
            return [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]
    return []


def _polygon_point_value(point: tuple[float, float]) -> str:
    return _polygon_parts_value(_polygon_point_parts(point))


def _polygon_arc_value(
    end: tuple[float, float], center: tuple[float, float], direction: str
) -> str:
    return _polygon_parts_value(_polygon_arc_parts(end, center, direction))


def _full_circle_arc_values(
    start: tuple[float, float], center: tuple[float, float], direction: str
) -> list[str]:
    return _polygon_parts_values(_full_circle_arc_parts(start, center, direction))


def _polygon_point_parts(point: tuple[float, float]) -> list[str]:
    return [_format_number(point[0]), _format_number(point[1])]


def _polygon_arc_parts(
    end: tuple[float, float], center: tuple[float, float], direction: str
) -> list[str]:
    return [
        _format_number(end[0]),
        _format_number(end[1]),
        _format_number(center[0]),
        _format_number(center[1]),
        direction,
    ]


def _polygon_parts_value(parts: list[str]) -> str:
    return f"({','.join(parts)})"


def _polygon_parts_values(parts: list[list[str]]) -> list[str]:
    return [_polygon_parts_value(part) for part in parts]


def _full_circle_arc_parts(
    start: tuple[float, float], center: tuple[float, float], direction: str
) -> list[list[str]]:
    opposite = (2 * center[0] - start[0], 2 * center[1] - start[1])
    return [
        _polygon_arc_parts(opposite, center, direction),
        _polygon_arc_parts(start, center, direction),
    ]


def _is_full_circle_arc(
    start: tuple[float, float],
    end: tuple[float, float],
    center: tuple[float, float],
) -> bool:
    return _same_point(start, end) and not _same_point(start, center)


def _arc_point(
    arc: Any, field_name: str, *, source_unit: str | None
) -> tuple[float, float] | None:
    return _point_tuple(_geometry_field(arc, field_name), source_unit=source_unit)


def _same_point(left: tuple[float, float], right: tuple[float, float]) -> bool:
    return abs(left[0] - right[0]) <= 1e-6 and abs(left[1] - right[1]) <= 1e-6


def _arc_is_curved(arc: Any, *, source_unit: str | None) -> bool:
    if _truthy(_geometry_field(arc, "is_segment")):
        return False

    height = _length_to_mil(_geometry_field(arc, "height"), source_unit=source_unit)
    if height is not None and _is_finite(height):
        return abs(height) > 1e-12

    center = _arc_point(arc, "center", source_unit=source_unit)
    if center is not None:
        return True

    radius = _length_to_mil(_geometry_field(arc, "radius"), source_unit=source_unit)
    return radius is not None and _is_finite(radius) and abs(radius) > 1e-12


def _arc_direction_flag(arc: Any, *, source_unit: str | None) -> str:
    is_ccw = _geometry_field(arc, "is_ccw")
    if is_ccw is not None:
        return "Y" if _truthy(is_ccw) else "N"

    clockwise = _geometry_field(arc, "clockwise")
    if clockwise is not None:
        return "N" if _truthy(clockwise) else "Y"

    height = _length_to_mil(_geometry_field(arc, "height"), source_unit=source_unit)
    if height is not None and _is_finite(height) and abs(height) > 1e-12:
        return _ccw_flag_from_arc_height(height)
    return "N"


def _arc_ccw_flag(geometry: dict[str, Any]) -> str:
    if "is_ccw" in geometry:
        return "Y" if _truthy(geometry.get("is_ccw")) else "N"
    if "clockwise" in geometry:
        return "N" if _truthy(geometry.get("clockwise")) else "Y"
    return "N"


def _ccw_flag_from_arc_height(arc_height: float) -> str:
    # AEDB raw-point arc markers use a negative height for CCW arcs.
    return "Y" if arc_height < 0 else "N"


def _outline_command(
    board: SemanticBoard, *, source_unit: str | None | object = _DEFAULT_SOURCE_UNIT
) -> str:
    source_unit = board.units if source_unit is _DEFAULT_SOURCE_UNIT else source_unit
    outline_payload = _board_outline_payload(board, source_unit=source_unit)
    if outline_payload is not None:
        return f"layout set -g <{outline_payload}> -profile null"

    points = _board_points(board, source_unit=source_unit)
    if not points:
        x_min, y_min, x_max, y_max = 0.0, 0.0, 1.0, 1.0
    else:
        x_values = [point[0] for point in points]
        y_values = [point[1] for point in points]
        x_min, x_max = min(x_values), max(x_values)
        y_min, y_max = min(y_values), max(y_values)
        pad = max((x_max - x_min) * 0.01, (y_max - y_min) * 0.01, 1.0)
        x_min -= pad
        y_min -= pad
        x_max += pad
        y_max += pad
    polygon = ",".join(
        f"({_format_number(x)},{_format_number(y)})"
        for x, y in [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]
    )
    return f"layout set -g <{{0:Polygon,(4,{polygon},Y,Y)}}> -profile null"


def _board_outline_payload(
    board: SemanticBoard, *, source_unit: str | None | object = _DEFAULT_SOURCE_UNIT
) -> str | None:
    source_unit = board.units if source_unit is _DEFAULT_SOURCE_UNIT else source_unit
    outline = board.board_outline or {}
    geometry_type = str(
        outline.get("auroradb_type") or outline.get("kind") or "Polygon"
    )
    values = outline.get("values")
    if geometry_type.casefold() != "polygon" or not isinstance(values, list):
        return None
    formatted = _format_polygon_shape_values(values, source_unit=source_unit)
    if not formatted:
        return None
    return f"{{0:Polygon,({','.join(formatted)})}}"


def _board_points(
    board: SemanticBoard, *, source_unit: str | None | object = _DEFAULT_SOURCE_UNIT
) -> list[tuple[float, float]]:
    source_unit = board.units if source_unit is _DEFAULT_SOURCE_UNIT else source_unit
    points: list[tuple[float, float]] = []
    for primitive in board.primitives:
        bbox = primitive.geometry.get("bbox")
        if isinstance(bbox, list) and len(bbox) >= 4:
            parsed = [
                _length_to_mil(value, source_unit=source_unit) for value in bbox[:4]
            ]
            if all(value is not None and _is_coordinate(value) for value in parsed):
                x_min, y_min, x_max, y_max = [float(value) for value in parsed]
                points.extend(
                    [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]
                )
    for point in [component.location for component in board.components]:
        _append_point(points, point, source_unit)
    for point in [pin.position for pin in board.pins]:
        _append_point(points, point, source_unit)
    for point in [pad.position for pad in board.pads]:
        _append_point(points, point, source_unit)
    for point in [via.position for via in board.vias]:
        _append_point(points, point, source_unit)
    return points


def _append_point(
    points: list[tuple[float, float]],
    point: SemanticPoint | None,
    source_unit: str | None,
) -> None:
    if point is None:
        return
    x = _length_to_mil(point.x, source_unit=source_unit)
    y = _length_to_mil(point.y, source_unit=source_unit)
    if x is not None and y is not None and _is_coordinate(x) and _is_coordinate(y):
        points.append((x, y))


def _aaf_shape_ids(shapes: list[SemanticShape]) -> dict[str, str]:
    return {shape.id: str(index + 1) for index, shape in enumerate(shapes)}


def _aaf_trace_shape_ids(
    board: SemanticBoard,
    *,
    start_index: int,
    source_unit: str | None | object = _DEFAULT_SOURCE_UNIT,
) -> dict[str, _TraceShape]:
    source_unit = board.units if source_unit is _DEFAULT_SOURCE_UNIT else source_unit
    result: dict[str, _TraceShape] = {}
    next_index = start_index
    for primitive in board.primitives:
        if primitive.kind.casefold() not in {"trace", "arc"}:
            continue
        width = _trace_width_mil(
            primitive.geometry.get("width"), source_unit=source_unit
        )
        if width is None:
            continue
        key = _trace_width_key(width)
        if key in result:
            continue
        result[key] = _TraceShape(shape_id=str(next_index), width_mil=width)
        next_index += 1
    return result


def _aaf_via_template_ids(via_templates: list[SemanticViaTemplate]) -> dict[str, str]:
    if any("auroradb_sort_group" in via_template.geometry for via_template in via_templates):
        return _aaf_sorted_via_template_ids(via_templates)

    result: dict[str, str] = {}
    used_ids: set[str] = set()
    next_id = 1
    for via_template in via_templates:
        preferred = via_template.geometry.get("auroradb_via_id")
        preferred_id = _positive_integer_text(preferred)
        if preferred_id is not None and preferred_id not in used_ids:
            result[via_template.id] = preferred_id
            used_ids.add(preferred_id)
            continue
        while str(next_id) in used_ids:
            next_id += 1
        result[via_template.id] = str(next_id)
        used_ids.add(str(next_id))
        next_id += 1
    return result


def _aaf_sorted_via_template_ids(
    via_templates: list[SemanticViaTemplate],
) -> dict[str, str]:
    result: dict[str, str] = {}
    next_id = 1
    previous_group: int | None = None
    reserve_after_group_0 = max(
        (
            _integer_value(
                via_template.geometry.get("auroradb_hidden_id_reserve_after_group_0")
            )
            or 0
            for via_template in via_templates
        ),
        default=0,
    )
    for via_template in via_templates:
        group = _integer_value(via_template.geometry.get("auroradb_sort_group"))
        if previous_group == 0 and group != 0:
            next_id += reserve_after_group_0
        result[via_template.id] = str(next_id)
        next_id += 1
        previous_group = group
    return result


def _positive_integer_text(value: Any) -> str | None:
    if value in {None, ""}:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return str(number)


def _via_templates_for_export(board: SemanticBoard) -> list[SemanticViaTemplate]:
    used_template_ids = {
        via.template_id
        for via in board.vias
        if _semantic_via_can_emit_as_net_via(via)
        and via.template_id
        and via.net_id
        and via.position is not None
    }
    multi_layer_template_ids_by_name = _multi_layer_via_template_ids_by_name(
        board.via_templates
    )
    for pad in board.pads:
        if not _component_pad_can_emit_as_via(pad):
            continue
        template_id = multi_layer_template_ids_by_name.get(
            str(pad.padstack_definition).casefold()
        )
        if template_id:
            used_template_ids.add(template_id)
    templates = [
        via_template
        for via_template in board.via_templates
        if via_template.id in used_template_ids
    ]
    return sorted(templates, key=_via_template_export_sort_key)


def _via_template_export_sort_key(
    via_template: SemanticViaTemplate,
) -> tuple[int, int, str]:
    group = _integer_value(via_template.geometry.get("auroradb_sort_group"))
    order = _integer_value(via_template.geometry.get("auroradb_sort_order"))
    return (
        group if group is not None else 2,
        order if order is not None else 0,
        via_template.name.casefold(),
    )


def _integer_value(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _semantic_via_can_emit_as_net_via(via: SemanticVia) -> bool:
    via_usage = via.geometry.get("via_usage")
    if via_usage in {None, "routing_via"}:
        return True
    return via.geometry.get("via_type") == "through"


def _multi_layer_via_template_ids_by_name(
    via_templates: list[SemanticViaTemplate],
) -> dict[str, str]:
    return {
        via_template.name.casefold(): via_template.id
        for via_template in via_templates
        if _via_template_spans_multiple_layers(via_template)
    }


def _via_template_spans_multiple_layers(via_template: SemanticViaTemplate) -> bool:
    return (
        len({layer_pad.layer_name.casefold() for layer_pad in via_template.layer_pads})
        > 1
    )


def _component_pad_can_emit_as_via(pad: SemanticPad) -> bool:
    if pad.geometry.get("suppress_via_export"):
        return False
    return bool(
        pad.component_id
        and pad.pin_id
        and pad.net_id
        and pad.position is not None
        and pad.padstack_definition
    )


def _component_pad_net_vias(
    pads: list[SemanticPad],
    via_templates: list[SemanticViaTemplate],
    via_template_ids: dict[str, str],
    net_names_by_id: dict[str, str],
    *,
    source_unit: str | None,
    source_format: str | None,
    emitted_keys: set[tuple[str, str, str, str, str]],
) -> list[tuple[str, str, float, float, str]]:
    template_ids_by_name = {
        via_template.name.casefold(): via_template_ids[via_template.id]
        for via_template in via_templates
        if via_template.id in via_template_ids
        and _via_template_spans_multiple_layers(via_template)
    }
    result: list[tuple[str, str, float, float, str]] = []
    for pad in pads:
        if not _component_pad_can_emit_as_via(pad):
            continue
        net_name = net_names_by_id.get(pad.net_id or "")
        via_template_id = template_ids_by_name.get(
            str(pad.padstack_definition).casefold()
        )
        if net_name is None or via_template_id is None or pad.position is None:
            continue
        via_position = _pad_via_position(pad) or pad.position
        x = _length_to_mil(via_position.x, source_unit=source_unit)
        y = _length_to_mil(via_position.y, source_unit=source_unit)
        if x is None or y is None:
            continue
        rotation = _format_rotation(_pad_via_rotation(pad), source_format=source_format)
        key = _net_via_key(net_name, via_template_id, x, y, rotation)
        if key in emitted_keys:
            continue
        emitted_keys.add(key)
        result.append((net_name, via_template_id, x, y, rotation))
    return result


def _net_via_key(
    net_name: str,
    via_template_id: str,
    x: float,
    y: float,
    rotation: str | float | int | None,
) -> tuple[str, str, str, str, str]:
    return (
        _auroradb_net_name(net_name).casefold(),
        str(via_template_id),
        _format_number(x),
        _format_number(y),
        "0" if rotation is None or rotation == "" else str(rotation),
    )


def _shape_auroradb_type(shape: SemanticShape) -> str:
    if shape.auroradb_type:
        return shape.auroradb_type
    mapping = {
        "circle": "Circle",
        "rectangle": "Rectangle",
        "rounded_rectangle": "RoundedRectangle",
        "polygon": "Polygon",
    }
    return mapping.get(shape.kind.casefold(), shape.kind)


def _shape_code(geometry_type: str) -> str:
    text = geometry_type.casefold()
    if text == "circle":
        return "0"
    if text in {"rectangle", "square"}:
        return "1"
    if text in {"roundedrectangle", "rectcutcorner", "oval"}:
        return "2"
    if text in {"roundedrectangle_y", "rectcutcorner_y", "oval_y"}:
        return "3"
    if text == "polygon":
        return "3"
    return "0"


def _shape_code_for_shape(shape: SemanticShape) -> str:
    kind = (shape.kind or "").casefold()
    if kind in {"rounded_rectangle_y", "rectcutcorner_y", "oval_y"}:
        return "3"
    return _shape_code(_shape_auroradb_type(shape))


def _format_shape_value(value: str | float | int, *, source_unit: str | None) -> str:
    numeric = _length_to_mil(value, source_unit=source_unit)
    if numeric is not None:
        return _format_number(numeric)
    return str(value)


def _pad_via_position(pad: SemanticPad) -> SemanticPoint | None:
    value = pad.geometry.get("via_position")
    if value is None:
        return None
    if isinstance(value, SemanticPoint):
        return value
    if isinstance(value, dict):
        x = _number(value.get("x"))
        y = _number(value.get("y"))
    elif isinstance(value, (list, tuple)) and len(value) >= 2:
        x = _number(value[0])
        y = _number(value[1])
    else:
        return None
    if x is None or y is None:
        return None
    return SemanticPoint(x=x, y=y)


def _format_geometry_shape_values(
    geometry_type: str,
    values: list[Any],
    *,
    source_unit: str | None,
) -> list[str]:
    if geometry_type.casefold() == "polygon":
        return _format_polygon_shape_values(values, source_unit=source_unit)
    formatted_values = [
        _format_shape_value(value, source_unit=source_unit) for value in values
    ]
    if geometry_type.casefold() == "roundedrectangle":
        formatted_values = _frontend_rounded_rectangle_values(formatted_values)
    return formatted_values


def _frontend_rounded_rectangle_values(values: list[str]) -> list[str]:
    if len(values) < 5:
        return values
    result = list(values)
    if len(result) == 5:
        result.append("N")
    while len(result) < 10:
        result.append("Y")
    return result


def _format_polygon_shape_values(
    values: list[Any], *, source_unit: str | None
) -> list[str]:
    if len(values) < 4:
        return [_format_shape_value(value, source_unit=source_unit) for value in values]
    result = [_format_scalar(values[0])]
    coordinate_values = values[1:]
    tail: list[Any] = []
    if len(coordinate_values) >= 2 and all(
        str(value).upper() in {"Y", "N"} for value in coordinate_values[-2:]
    ):
        tail = coordinate_values[-2:]
        coordinate_values = coordinate_values[:-2]
    result.extend(
        _format_polygon_shape_vertex(value, source_unit=source_unit)
        for value in coordinate_values
    )
    result.extend(str(value) for value in tail)
    return result


def _format_polygon_shape_vertex(value: Any, *, source_unit: str | None) -> str:
    if isinstance(value, dict):
        point = _point_tuple(value, source_unit=source_unit)
        if point is not None:
            return f"({_format_number(point[0])},{_format_number(point[1])})"
    if isinstance(value, (list, tuple)) and len(value) in {2, 5}:
        numeric_count = 4 if len(value) == 5 else 2
        formatted = [
            _format_shape_value(part, source_unit=source_unit)
            for part in value[:numeric_count]
        ]
        if len(value) == 5:
            flag = value[4]
            formatted.append(_bool_aaf(flag) if isinstance(flag, bool) else str(flag))
        return f"({','.join(formatted)})"
    if (
        not isinstance(value, str)
        or not value.startswith("(")
        or not value.endswith(")")
    ):
        return _format_shape_value(value, source_unit=source_unit)
    parts = [part.strip() for part in value.strip()[1:-1].split(",")]
    if len(parts) not in {2, 5}:
        return _format_shape_value(value, source_unit=source_unit)
    numeric_count = 4 if len(parts) == 5 else 2
    formatted = [
        _format_shape_value(part, source_unit=source_unit)
        for part in parts[:numeric_count]
    ]
    if len(parts) == 5:
        formatted.append(parts[4])
    return f"({','.join(formatted)})"


def _pad_shape_ids_by_definition(board: SemanticBoard) -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    for via_template in board.via_templates:
        template_key = via_template.name.casefold()
        first_shape_id: str | None = None
        for layer_pad in via_template.layer_pads:
            if not layer_pad.pad_shape_id:
                continue
            layer_key = layer_pad.layer_name.casefold()
            result[(template_key, layer_key)] = layer_pad.pad_shape_id
            if first_shape_id is None:
                first_shape_id = layer_pad.pad_shape_id
        if first_shape_id is not None:
            result[(template_key, "")] = first_shape_id
    return result


def _pad_shape_id_for_layer(
    pad: SemanticPad,
    pad_shape_ids: dict[tuple[str, str], str],
    mapped_layer_name: str | None,
) -> str | None:
    direct_shape_id = pad.geometry.get("shape_id")
    if direct_shape_id:
        return str(direct_shape_id)
    if not pad.padstack_definition:
        return None
    template_key = pad.padstack_definition.casefold()
    layer_candidates = [
        pad.layer_name.casefold() if pad.layer_name else "",
        mapped_layer_name.casefold() if mapped_layer_name else "",
        "",
    ]
    for layer_key in layer_candidates:
        shape_id = pad_shape_ids.get((template_key, layer_key))
        if shape_id is not None:
            return shape_id
    return None


def _semantic_layer_name(layer_name: str, layer_name_map: dict[str, str]) -> str:
    return layer_name_map.get(layer_name.casefold(), _standardize_name(layer_name))


def _mapped_layer_name(
    layer_name: str | None, layer_name_map: dict[str, str]
) -> str | None:
    if not layer_name:
        return None
    return layer_name_map.get(layer_name.casefold())


def _component_metal_layer(
    component: SemanticComponent, layer_name_map: dict[str, str]
) -> str | None:
    mapped = _mapped_layer_name(component.layer_name, layer_name_map)
    if mapped is not None:
        return mapped
    if component.side == "top":
        return _mapped_layer_name("TOP", layer_name_map)
    if component.side == "bottom":
        return _mapped_layer_name("BOTTOM", layer_name_map)
    return None


def _component_layer_side(layer_name: str | None) -> str | None:
    text = (layer_name or "").casefold()
    if text in {"top", "toplayer", "top_layer"} or "top" in text:
        return "top"
    if (
        text in {"bottom", "bot", "bottomlayer", "bottom_layer"}
        or "bottom" in text
        or "bot" in text
        or text.startswith("bot")
    ):
        return "bottom"
    return None


def _pin_metal_layer(
    pin: SemanticPin,
    component: SemanticComponent,
    layer_name_map: dict[str, str],
) -> str | None:
    mapped = _mapped_layer_name(pin.layer_name, layer_name_map)
    if mapped is not None:
        return mapped
    return _component_metal_layer(component, layer_name_map)


def _pad_metal_layer(
    pad: SemanticPad,
    component: SemanticComponent | None,
    layer_name_map: dict[str, str],
) -> str | None:
    _ = component
    return _mapped_layer_name(pad.layer_name, layer_name_map)


def _primitive_layer_name(
    primitive: SemanticPrimitive, layer_name_map: dict[str, str]
) -> str | None:
    return _mapped_layer_name(primitive.layer_name, layer_name_map)


def _component_layer_name(metal_layer_name: str) -> str:
    return f"COMP_{_standardize_name(metal_layer_name)}"


def _component_flip_flags(
    component: SemanticComponent,
    *,
    placement: _AedbComponentPlacement | None = None,
    source_format: str | None = None,
) -> tuple[bool, bool]:
    if placement is not None:
        return placement.flip_x, placement.flip_y
    if _odbpp_component_needs_bottom_flip(component, source_format=source_format):
        return False, True
    if (source_format or "").casefold() == "aedb" and component.side == "bottom":
        return False, True
    return False, False


def _component_rotation_for_export(
    component: SemanticComponent,
    *,
    placement: _AedbComponentPlacement | None = None,
    source_format: str | None = None,
) -> Any:
    rotation = placement.rotation if placement is not None else component.rotation
    if (
        placement is None
        and _source_rotations_are_clockwise(source_format)
        and component.side == "bottom"
    ):
        number = _number(rotation)
        if number is not None and _is_finite(number):
            return -number
    return rotation


def _odbpp_component_needs_bottom_flip(
    component: SemanticComponent,
    *,
    source_format: str | None,
) -> bool:
    if (source_format or "").casefold() == "alg":
        mirror = component.attributes.get("mirror", "")
        return component.side == "bottom" or _truthy(mirror)
    return _source_rotations_are_clockwise(source_format) and component.side == "bottom"


def _component_name(component: SemanticComponent) -> str:
    return str(component.refdes or component.name or component.id)


def _component_part_name(component: SemanticComponent) -> str:
    return str(component.part_name or component.package_name or "Unknown")


def _pin_name(pin: SemanticPin) -> str:
    return str(pin.name or pin.id)


def _pad_rotation(pad: SemanticPad) -> Any:
    return pad.geometry.get("rotation")


def _pad_via_rotation(pad: SemanticPad) -> Any:
    return pad.geometry.get("via_rotation", _pad_rotation(pad))


def _via_template_layer_rotation(
    via_template: SemanticViaTemplate,
    layer_name: str,
    key: str,
    *,
    source_format: str | None,
) -> tuple[str, str]:
    rotations = via_template.geometry.get("layer_pad_rotations")
    if not isinstance(rotations, dict):
        return "0", "Y"
    rotation = None
    values = rotations.get(layer_name)
    if isinstance(values, dict):
        rotation = values.get(key)
    if rotation is None:
        layer_key = layer_name.casefold()
        for candidate_layer, candidate_values in rotations.items():
            if str(candidate_layer).casefold() == layer_key and isinstance(
                candidate_values, dict
            ):
                rotation = candidate_values.get(key)
                break
    number = _number(rotation)
    if number is None or not _is_finite(number):
        return "0", "Y"
    angle_degree = _rotation_degrees(number)
    if _source_rotations_are_clockwise(source_format):
        angle_degree = 360.0 - angle_degree
    return _format_number(_normalize_degree(angle_degree)), "Y"


def _pad_flip_options(pad: SemanticPad) -> str:
    if not pad.geometry:
        return ""
    options: list[str] = []
    if _truthy(pad.geometry.get("mirror_x")):
        options.append("-flipX")
    if _truthy(pad.geometry.get("mirror_y")):
        options.append("-flipY")
    return "".join(f"{option} " for option in options)


def _point_coordinates(
    point: SemanticPoint | None, *, source_unit: str | None
) -> tuple[float, float]:
    if point is None:
        return 0.0, 0.0
    x = _length_to_mil(point.x, source_unit=source_unit)
    y = _length_to_mil(point.y, source_unit=source_unit)
    if x is None or y is None or not _is_coordinate(x) or not _is_coordinate(y):
        return 0.0, 0.0
    return x, y


def _geometry_field(record: Any, field_name: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(field_name, default)
    getter = getattr(record, "get", None)
    if callable(getter):
        return getter(field_name, default)
    data = getattr(record, "__dict__", None)
    if isinstance(data, dict):
        return data.get(field_name, default)
    return getattr(record, field_name, default)


def _trace_point_items(
    raw_points: list[Any], *, source_unit: str | None
) -> list[_TracePoint]:
    result: list[_TracePoint] = []
    for raw_point in raw_points:
        arc_height = _arc_marker_height(raw_point, source_unit=source_unit)
        if arc_height is not None:
            result.append(_TracePoint(is_arc=True, arc_height=arc_height))
            continue
        point = _point_tuple(raw_point, source_unit=source_unit)
        if point is None:
            continue
        result.append(_TracePoint(x=point[0], y=point[1]))
    return result


def _arc_marker_height(value: Any, *, source_unit: str | None) -> float | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    sentinel = _number(value[1])
    if sentinel is None or (_is_finite(sentinel) and abs(float(sentinel)) <= 1e100):
        return None
    height = _length_to_mil(value[0], source_unit=source_unit)
    if height is None or not _is_finite(height):
        return None
    return height


def _arc_center(
    start: _TracePoint, end: _TracePoint, arc_height: float
) -> tuple[float, float, str] | None:
    if not _is_finite(arc_height) or abs(arc_height) < 1e-12:
        return None
    x1 = 0.0
    y1 = 0.0
    x2 = end.x - start.x
    y2 = end.y - start.y
    if abs(x2) < 1e-9:
        x2 = 0.0
    if abs(y2) < 1e-9:
        y2 = 0.0
    ab2 = (x2 - x1) ** 2 + (y2 - y1) ** 2
    if ab2 == 0:
        return start.x, start.y, _ccw_flag_from_arc_height(arc_height)
    ab = ab2**0.5
    try:
        factor = 0.125 * ab / arc_height - 0.5 * arc_height / ab
    except ZeroDivisionError:
        return start.x + ab, start.y + ab, _ccw_flag_from_arc_height(arc_height)
    x = 0.5 * (x1 + x2) + (y2 - y1) * factor
    y = 0.5 * (y1 + y2) - (x2 - x1) * factor
    return x + start.x, y + start.y, _ccw_flag_from_arc_height(arc_height)


def _trace_shape_for_width(
    value: Any,
    trace_shape_ids: dict[str, _TraceShape],
    *,
    source_unit: str | None,
) -> _TraceShape | None:
    width = _trace_width_mil(value, source_unit=source_unit)
    if width is None:
        return None
    return trace_shape_ids.get(_trace_width_key(width))


def _trace_width_mil(value: Any, *, source_unit: str | None) -> float | None:
    width = _length_to_mil(value, source_unit=source_unit)
    if width is None or not _is_coordinate(width) or width <= 0:
        return None
    return width


def _trace_width_key(width_mil: float) -> str:
    return _format_number(width_mil)


def _dedupe_consecutive(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for point in points:
        if result and result[-1] == point:
            continue
        result.append(point)
    return result


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]
