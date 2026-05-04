from __future__ import annotations

from aurora_translator.sources.auroradb.block import (
    AuroraBlock,
    AuroraItem,
    AuroraRawBlock,
)
from aurora_translator.targets.auroradb.aaf.geometry import parse_geometry_option
from aurora_translator.targets.auroradb.direct import (
    _AedbComponentPlacement,
    _AedbExportPlan,
    _DirectLayoutBuilder,
    _PartExportPlan,
    _TraceShape,
)
from aurora_translator.targets.auroradb.formatting import (
    _format_number,
    _format_rotation,
    _length_to_mil,
    _point_tuple,
    _truthy,
)
from aurora_translator.targets.auroradb.geometry import (
    _aaf_shape_ids,
    _aaf_trace_shape_ids,
    _aaf_via_template_ids,
    _arc_ccw_flag,
    _arc_center,
    _board_outline_payload,
    _component_flip_flags,
    _component_layer_name,
    _component_layer_side,
    _component_command,
    _component_layers,
    _component_metal_layer,
    _component_name,
    _component_pad_net_vias,
    _component_part_name,
    _direct_location_values,
    _net_via_key,
    _net_pin_command,
    _outline_command,
    _pad_flip_options,
    _pad_metal_layer,
    _pad_rotation,
    _pad_shape_id_for_layer,
    _pad_shape_ids_by_definition,
    _pad_shape_command,
    _pin_metal_layer,
    _pin_name,
    _point_coordinates,
    _polygon_vertex_parts,
    _primitive_layer_name,
    _primitive_commands,
    _semantic_layer_name,
    _shape_auroradb_type,
    _shape_code,
    _shape_command,
    _shape_geometry_payload,
    _trace_point_items,
    _trace_shape_command,
    _trace_shape_for_width,
    _via_template_command,
    _via_template_layer_rotation,
    _via_templates_for_export,
    _void_geometry_parts,
)
from aurora_translator.targets.auroradb.names import _net_type, _quote_aaf
from aurora_translator.targets.auroradb.parts import _pads_by_pin_id
from aurora_translator.targets.auroradb.plan import BoardExportIndex
from aurora_translator.targets.auroradb.stackup import _ExportLayer
from aurora_translator.semantic.models import (
    SemanticBoard,
    SemanticComponent,
    SemanticLayer,
    SemanticPad,
    SemanticPin,
    SemanticPrimitive,
    SemanticShape,
    SemanticViaTemplate,
)


_DEFAULT_SOURCE_UNIT = object()


def _layout_unit(board: SemanticBoard) -> str:
    return "mm" if _preserve_board_units(board) else "mil"


def _geometry_source_unit(board: SemanticBoard) -> str | None:
    return None if _preserve_board_units(board) else board.units


def _preserve_board_units(board: SemanticBoard) -> bool:
    source_format = (board.metadata.source_format or "").casefold()
    unit = (board.units or "").casefold()
    return source_format in {"alg", "brd"} and unit in {
        "mm",
        "millimeter",
        "millimeters",
        "millimetre",
        "millimetres",
    }


def _resolved_source_unit(
    board: SemanticBoard, source_unit: str | None | object
) -> str | None:
    return board.units if source_unit is _DEFAULT_SOURCE_UNIT else source_unit


def _build_direct_layout_package(
    board: SemanticBoard,
    metal_layers: list[_ExportLayer],
    aedb_plan: _AedbExportPlan | None,
    part_export_plan: _PartExportPlan | None,
) -> _DirectLayoutBuilder:
    builder = _DirectLayoutBuilder()
    geometry_source_unit = _geometry_source_unit(board)
    layer_name_map = _metal_layer_name_map(metal_layers, board.layers)
    shape_ids = _aaf_shape_ids(board.shapes)
    trace_shape_ids = _aaf_trace_shape_ids(
        board, start_index=len(shape_ids) + 1, source_unit=geometry_source_unit
    )
    via_templates = _via_templates_for_export(board)
    via_template_ids = _aaf_via_template_ids(via_templates)
    pad_shape_ids = _pad_shape_ids_by_definition(board)

    builder.outline = _direct_outline_node(board, source_unit=geometry_source_unit)

    for layer in metal_layers:
        builder.add_metal_layer(layer.name, "signal")

    for component_layer, metal_layer in _component_layers(
        board, layer_name_map
    ).items():
        builder.add_component_layer(component_layer, metal_layer)

    for shape in board.shapes:
        _direct_add_shape(
            builder, shape, shape_ids[shape.id], source_unit=geometry_source_unit
        )
    for trace_shape in trace_shape_ids.values():
        _direct_add_trace_shape(builder, trace_shape)
    for via_template in via_templates:
        _direct_add_via_template(
            builder,
            via_template,
            via_template_ids[via_template.id],
            shape_ids,
            layer_name_map,
            source_format=board.metadata.source_format,
        )

    for net in board.nets:
        net_block = builder.find_or_create_net(net.name)
        net_block.add_item("Type", _net_type(net.role))
        net_block.add_item("Voltage", "")

    board_index = BoardExportIndex.from_board(board)
    net_names_by_id = board_index.net_names_by_id
    component_by_id = board_index.components_by_id
    pads_by_pin_id = board_index.pads_by_pin_id
    emitted_pad_ids: set[str] = set()

    for component in board.components:
        _direct_add_component(
            builder,
            component,
            layer_name_map,
            source_unit=geometry_source_unit,
            placement=(
                aedb_plan.placements_by_component_id.get(component.id)
                if aedb_plan is not None
                else None
            ),
            part_name_override=(
                part_export_plan.part_names_by_component_id.get(component.id)
                if part_export_plan is not None
                else None
            ),
            source_format=board.metadata.source_format,
        )

    for pin in board.pins:
        for pad in pads_by_pin_id.get(pin.id, []):
            if _direct_add_pad_shape(
                builder,
                pad,
                component_by_id,
                net_names_by_id,
                shape_ids,
                pad_shape_ids,
                layer_name_map,
                source_unit=geometry_source_unit,
                source_format=board.metadata.source_format,
            ):
                emitted_pad_ids.add(pad.id)
        _direct_add_net_pin(
            builder, pin, component_by_id, net_names_by_id, layer_name_map
        )

    for pad in board.pads:
        if pad.id in emitted_pad_ids:
            continue
        _direct_add_pad_shape(
            builder,
            pad,
            component_by_id,
            net_names_by_id,
            shape_ids,
            pad_shape_ids,
            layer_name_map,
            source_unit=geometry_source_unit,
            source_format=board.metadata.source_format,
        )

    _direct_add_primitives(
        builder,
        board,
        layer_name_map,
        net_names_by_id,
        trace_shape_ids,
        source_unit=geometry_source_unit,
    )

    emitted_net_vias: set[tuple[str, str, str, str, str]] = set()
    for via in board.vias:
        if not via.net_id or not via.template_id or via.position is None:
            continue
        net_name = net_names_by_id.get(via.net_id)
        via_template_id = via_template_ids.get(via.template_id)
        if net_name is None or via_template_id is None:
            continue
        x = _length_to_mil(via.position.x, source_unit=geometry_source_unit)
        y = _length_to_mil(via.position.y, source_unit=geometry_source_unit)
        if x is None or y is None:
            continue
        rotation = _format_rotation(
            via.geometry.get("rotation"), source_format=board.metadata.source_format
        )
        emitted_net_vias.add(_net_via_key(net_name, via_template_id, x, y, rotation))
        builder.add_net_via(
            net_name,
            [via_template_id, *_direct_location_values(x, y, rotation=rotation)],
        )
    for net_name, via_template_id, x, y, rotation in _component_pad_net_vias(
        board.pads,
        via_templates,
        via_template_ids,
        net_names_by_id,
        source_unit=geometry_source_unit,
        source_format=board.metadata.source_format,
        emitted_keys=emitted_net_vias,
    ):
        builder.add_net_via(
            net_name,
            [via_template_id, *_direct_location_values(x, y, rotation=rotation)],
        )
    return builder


def _metal_layer_name_map(
    metal_layers: list[_ExportLayer],
    semantic_layers: list[SemanticLayer],
) -> dict[str, str]:
    layer_name_map = {
        layer.source_name.casefold(): layer.name
        for layer in metal_layers
        if layer.source_name
    }
    if not metal_layers:
        return layer_name_map

    top_metal = metal_layers[0].name
    bottom_metal = metal_layers[-1].name
    for alias in ("top", "toplayer", "top_layer"):
        layer_name_map.setdefault(alias.casefold(), top_metal)
    for alias in ("bottom", "bot", "bottomlayer", "bottom_layer"):
        layer_name_map.setdefault(alias.casefold(), bottom_metal)

    for layer in semantic_layers:
        layer_name = layer.name
        if not layer_name:
            continue
        role = (layer.role or "").casefold()
        layer_type = (layer.layer_type or "").casefold()
        if role != "component" and "component" not in layer_type:
            continue
        side = layer.side or _component_layer_side(layer_name)
        if side == "top":
            layer_name_map.setdefault(layer_name.casefold(), top_metal)
        elif side == "bottom":
            layer_name_map.setdefault(layer_name.casefold(), bottom_metal)
    return layer_name_map


def _direct_outline_node(
    board: SemanticBoard, *, source_unit: str | None | object = _DEFAULT_SOURCE_UNIT
) -> AuroraBlock | AuroraItem:
    payload = _board_outline_payload(
        board, source_unit=_resolved_source_unit(board, source_unit)
    )
    if payload is None:
        payload = (
            _outline_command(
                board, source_unit=_resolved_source_unit(board, source_unit)
            )
            .split("-g <", 1)[1]
            .split("> -profile", 1)[0]
        )
    geometry = parse_geometry_option([payload])
    if geometry is None:
        outline = AuroraBlock("Outline")
        outline.add_item("Solid", "Y")
        outline.add_item("CCW", "Y")
        return outline
    geometry.node.name = "Outline"
    return geometry.node


def _direct_add_shape(
    builder: _DirectLayoutBuilder,
    shape: SemanticShape,
    shape_id: str,
    *,
    source_unit: str | None,
) -> None:
    payload = _shape_geometry_payload(shape, shape_id, source_unit=source_unit)
    if payload is None:
        return
    geometry = parse_geometry_option([payload])
    if geometry is None:
        return
    builder.shape_list.add_item(
        "IdName", [shape_id, _shape_code(_shape_auroradb_type(shape))]
    )
    builder.shape_list.append(geometry.node)


def _direct_add_trace_shape(
    builder: _DirectLayoutBuilder, trace_shape: _TraceShape
) -> None:
    width = _format_number(trace_shape.width_mil)
    builder.shape_list.add_item("IdName", [trace_shape.shape_id, "0"])
    builder.shape_list.append(AuroraItem("Circle", ["0", "0", width]))


def _direct_add_via_template(
    builder: _DirectLayoutBuilder,
    via_template: SemanticViaTemplate,
    via_template_id: str,
    shape_ids: dict[str, str],
    layer_name_map: dict[str, str],
    *,
    source_format: str | None = None,
) -> None:
    barrel_shape_id = shape_ids.get(via_template.barrel_shape_id or "", "null")
    if len(via_template.layer_pads) == 0 and barrel_shape_id == "null":
        return
    via_block = AuroraBlock("Via")
    via_block.add_item("IdName", [via_template_id, via_template.name])
    via_block.add_item("Barrel", [barrel_shape_id, "0", "Y"])
    for layer_pad in via_template.layer_pads:
        layer_name = _semantic_layer_name(layer_pad.layer_name, layer_name_map)
        pad_shape = shape_ids.get(layer_pad.pad_shape_id or "", "null")
        anti_shape = shape_ids.get(layer_pad.antipad_shape_id or "", "null")
        pad_rotation, pad_ccw = _via_template_layer_rotation(
            via_template,
            layer_pad.layer_name,
            "pad",
            source_format=source_format,
        )
        values = [
            "-1" if pad_shape.casefold() == "null" else pad_shape,
            pad_rotation,
            pad_ccw,
        ]
        if anti_shape.casefold() != "null":
            antipad_rotation, antipad_ccw = _via_template_layer_rotation(
                via_template,
                layer_pad.layer_name,
                "antipad",
                source_format=source_format,
            )
            values.extend([anti_shape, antipad_rotation, antipad_ccw])
        via_block.add_item(layer_name, values)
    builder.via_list.append(via_block)


def _direct_add_component(
    builder: _DirectLayoutBuilder,
    component: SemanticComponent,
    layer_name_map: dict[str, str],
    *,
    source_unit: str | None,
    placement: _AedbComponentPlacement | None = None,
    part_name_override: str | None = None,
    source_format: str | None = None,
) -> None:
    metal_layer = _component_metal_layer(component, layer_name_map)
    if metal_layer is None:
        return
    x, y = _point_coordinates(component.location, source_unit=source_unit)
    component_layer_name = _component_layer_name(metal_layer)
    layer = builder.find_layer_by_component_layer(component_layer_name)
    if layer.components is None:
        builder.add_component_layer(component_layer_name, metal_layer)
        layer = builder.find_layer_by_component_layer(component_layer_name)
    rotation = _format_rotation(
        placement.rotation if placement is not None else component.rotation,
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
        part_name,
        component_layer_name,
        *_direct_location_values(
            x,
            y,
            rotation=rotation,
            flip_x=flip_x,
            flip_y=flip_y,
        ),
    ]
    if component.value not in {None, ""}:
        values.append(str(component.value))
    layer.components.add_item(_component_name(component), values)


def _direct_add_net_pin(
    builder: _DirectLayoutBuilder,
    pin: SemanticPin,
    components_by_id: dict[str, SemanticComponent],
    net_names_by_id: dict[str, str],
    layer_name_map: dict[str, str],
) -> None:
    if not pin.net_id or not pin.component_id:
        return
    component = components_by_id.get(pin.component_id)
    net_name = net_names_by_id.get(pin.net_id)
    if component is None or net_name is None:
        return

    component_metal_layer = _component_metal_layer(component, layer_name_map)
    pin_metal_layer = _pin_metal_layer(pin, component, layer_name_map)
    if component_metal_layer is None or pin_metal_layer is None:
        return
    metal = pin_metal_layer if component_metal_layer != pin_metal_layer else ""
    builder.add_net_pin(
        net_name,
        [
            _component_layer_name(component_metal_layer),
            _component_name(component),
            _pin_name(pin),
            metal,
        ],
    )


def _direct_add_pad_shape(
    builder: _DirectLayoutBuilder,
    pad: SemanticPad,
    components_by_id: dict[str, SemanticComponent],
    net_names_by_id: dict[str, str],
    shape_ids: dict[str, str],
    pad_shape_ids: dict[tuple[str, str], str],
    layer_name_map: dict[str, str],
    *,
    source_unit: str | None,
    source_format: str | None = None,
) -> bool:
    if not pad.net_id or pad.position is None:
        return False
    component = components_by_id.get(pad.component_id or "")
    net_name = net_names_by_id.get(pad.net_id)
    layer_name = _pad_metal_layer(pad, component, layer_name_map)
    semantic_shape_id = _pad_shape_id_for_layer(pad, pad_shape_ids, layer_name)
    shape_id = shape_ids.get(semantic_shape_id or "")
    if net_name is None or layer_name is None or shape_id is None:
        return False
    x, y = _point_coordinates(pad.position, source_unit=source_unit)
    block = AuroraBlock("NetGeom")
    block.add_item("SymbolID", shape_id)
    block.add_item(
        "Location",
        _direct_location_values(
            x,
            y,
            rotation=_format_rotation(_pad_rotation(pad), source_format=source_format),
            flip_x="-flipX" in _pad_flip_options(pad),
            flip_y="-flipY" in _pad_flip_options(pad),
        ),
    )
    builder.add_net_geometry(net_name, layer_name, block)
    return True


def _direct_add_primitives(
    builder: _DirectLayoutBuilder,
    board: SemanticBoard,
    layer_name_map: dict[str, str],
    net_names_by_id: dict[str, str],
    trace_shape_ids: dict[str, _TraceShape],
    *,
    source_unit: str | None,
) -> None:
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
            geometry_index += _direct_add_trace_geometries(
                builder,
                primitive,
                net_name,
                layer_name,
                trace_shape_ids,
                start_index=geometry_index,
                source_unit=source_unit,
            )
        elif kind == "arc":
            if _direct_add_arc_geometry(
                builder,
                primitive,
                net_name,
                layer_name,
                trace_shape_ids,
                geometry_id=f"A{geometry_index}",
                source_unit=source_unit,
            ):
                geometry_index += 1
        elif kind in {"polygon", "zone"}:
            if _direct_add_polygon_geometry(
                builder,
                primitive,
                net_name,
                layer_name,
                source_format=board.metadata.source_format,
                source_unit=source_unit,
            ):
                geometry_index += 1


def _direct_add_arc_geometry(
    builder: _DirectLayoutBuilder,
    primitive: SemanticPrimitive,
    net_name: str,
    layer_name: str,
    trace_shape_ids: dict[str, _TraceShape],
    *,
    geometry_id: str,
    source_unit: str | None,
) -> bool:
    start = _point_tuple(primitive.geometry.get("start"), source_unit=source_unit)
    end = _point_tuple(primitive.geometry.get("end"), source_unit=source_unit)
    center = _point_tuple(primitive.geometry.get("center"), source_unit=source_unit)
    if start is None or end is None or center is None:
        return False
    trace_shape = _trace_shape_for_width(
        primitive.geometry.get("width"), trace_shape_ids, source_unit=source_unit
    )
    if trace_shape is None:
        return False
    block = AuroraBlock("NetGeom")
    block.add_item("SymbolID", trace_shape.shape_id)
    block.append(
        AuroraItem(
            "Larc",
            [
                _format_number(start[0]),
                _format_number(start[1]),
                _format_number(end[0]),
                _format_number(end[1]),
                _format_number(center[0]),
                _format_number(center[1]),
                _arc_ccw_flag(primitive.geometry),
            ],
        )
    )
    builder.add_net_geometry(net_name, layer_name, block)
    return True


def _direct_add_trace_geometries(
    builder: _DirectLayoutBuilder,
    primitive: SemanticPrimitive,
    net_name: str,
    layer_name: str,
    trace_shape_ids: dict[str, _TraceShape],
    *,
    start_index: int,
    source_unit: str | None,
) -> int:
    trace_shape = _trace_shape_for_width(
        primitive.geometry.get("width"), trace_shape_ids, source_unit=source_unit
    )
    if trace_shape is None:
        return 0

    raw_points = primitive.geometry.get("center_line")
    if not isinstance(raw_points, (list, tuple)):
        return 0
    points = _trace_point_items(raw_points, source_unit=source_unit)
    if len(points) < 2:
        return 0

    emitted = 0
    geometry_index = start_index
    for index in range(1, len(points)):
        current = points[index]
        previous = points[index - 1]
        if current.is_arc:
            continue
        block = AuroraBlock("NetGeom")
        block.add_item("SymbolID", trace_shape.shape_id)
        if previous.is_arc:
            if index < 2 or points[index - 2].is_arc:
                continue
            start = points[index - 2]
            center = _arc_center(start, current, previous.arc_height)
            if center is None:
                continue
            x0, y0, ccw = center
            block.append(
                AuroraItem(
                    "Larc",
                    [
                        _format_number(start.x),
                        _format_number(start.y),
                        _format_number(current.x),
                        _format_number(current.y),
                        _format_number(x0),
                        _format_number(y0),
                        ccw,
                    ],
                )
            )
        else:
            block.append(
                AuroraItem(
                    "Line",
                    [
                        _format_number(previous.x),
                        _format_number(previous.y),
                        _format_number(current.x),
                        _format_number(current.y),
                    ],
                )
            )
        builder.add_net_geometry(net_name, layer_name, block)
        geometry_index += 1
        emitted += 1
    return emitted


def _direct_add_polygon_geometry(
    builder: _DirectLayoutBuilder,
    primitive: SemanticPrimitive,
    net_name: str,
    layer_name: str,
    *,
    source_format: str | None,
    source_unit: str | None,
) -> bool:
    min_points = _polygon_min_points(primitive, source_format)
    point_parts = _polygon_vertex_parts(
        primitive.geometry, source_unit=source_unit, min_points=min_points
    )
    if len(point_parts) < min_points:
        return False
    solid = (
        "N"
        if _truthy(primitive.geometry.get("is_negative"))
        or _truthy(primitive.geometry.get("is_void"))
        else "Y"
    )
    void_geometries = _void_geometry_parts(
        primitive, source_unit=source_unit, min_points=min_points
    )
    builder.add_net_geometry(
        net_name,
        layer_name,
        _direct_polygon_netgeom_block(point_parts, void_geometries, solid=solid),
    )
    return True


def _polygon_min_points(primitive: SemanticPrimitive, source_format: str | None) -> int:
    if (source_format or "").casefold() in {"alg", "brd"} and str(
        primitive.geometry.get("record_kind") or ""
    ).casefold() == "shape":
        return 2
    return 3


def _direct_polygon_netgeom_block(
    point_parts: list[list[str]],
    void_geometries: list[list[list[str]]],
    *,
    solid: str,
) -> AuroraRawBlock:
    lines = ["NetGeom {", "\tSymbolID -1"]
    if void_geometries:
        _append_direct_polygon_lines(
            lines,
            "PolygonHole",
            point_parts,
            solid=solid,
            indent=1,
            holes=void_geometries,
        )
    else:
        _append_direct_polygon_lines(
            lines, "Polygon", point_parts, solid=solid, indent=1
        )
    lines.append("}")
    return AuroraRawBlock("NetGeom", lines)


def _append_direct_polygon_lines(
    lines: list[str],
    name: str,
    point_parts: list[list[str]],
    *,
    solid: str,
    indent: int,
    holes: list[list[list[str]]] | None = None,
) -> None:
    prefix = "\t" * indent
    child_prefix = f"{prefix}\t"
    lines.append(f"{prefix}{name} {{")
    lines.append(f"{child_prefix}Solid {solid}")
    lines.append(f"{child_prefix}CCW Y")
    for parts in point_parts:
        lines.append(
            f"{child_prefix}{'Parc' if len(parts) == 5 else 'Pnt'} {' '.join(parts)}"
        )
    if holes:
        lines.append(f"{child_prefix}Holes {{")
        for void_parts in holes:
            _append_direct_polygon_lines(
                lines, "Polygon", void_parts, solid="Y", indent=indent + 2
            )
        lines.append(f"{child_prefix}}}")
    lines.append(f"{prefix}}}")


def _aaf_text(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def _design_layout(
    board: SemanticBoard,
    metal_layers: list[_ExportLayer],
    aedb_plan: _AedbExportPlan | None = None,
    part_export_plan: _PartExportPlan | None = None,
) -> str:
    return _aaf_text(
        _design_layout_lines(board, metal_layers, aedb_plan, part_export_plan)
    )


def _design_layout_lines(
    board: SemanticBoard,
    metal_layers: list[_ExportLayer],
    aedb_plan: _AedbExportPlan | None = None,
    part_export_plan: _PartExportPlan | None = None,
) -> list[str]:
    geometry_source_unit = _geometry_source_unit(board)
    lines = [
        f"layout set -unit <{_layout_unit(board)}>",
        _outline_command(board, source_unit=geometry_source_unit),
    ]
    layer_name_map = _metal_layer_name_map(metal_layers, board.layers)
    shape_ids = _aaf_shape_ids(board.shapes)
    trace_shape_ids = _aaf_trace_shape_ids(
        board, start_index=len(shape_ids) + 1, source_unit=geometry_source_unit
    )
    via_templates = _via_templates_for_export(board)
    via_template_ids = _aaf_via_template_ids(via_templates)
    pad_shape_ids = _pad_shape_ids_by_definition(board)

    layerstack = ",".join(
        f"({layer.name},signal,{_format_number(layer.thickness_mil)})"
        for layer in metal_layers
    )
    lines.append(f"layout set -layerstack <{layerstack}>")

    component_layers = _component_layers(board, layer_name_map)
    for component_layer, metal_layer in component_layers.items():
        lines.append(
            f"layout add -complayer <{component_layer}> -layer <{metal_layer}>"
        )

    for shape in board.shapes:
        command = _shape_command(
            shape, shape_ids[shape.id], source_unit=geometry_source_unit
        )
        if command is not None:
            lines.append(command)

    for trace_shape in trace_shape_ids.values():
        lines.append(_trace_shape_command(trace_shape))

    for via_template in via_templates:
        command = _via_template_command(
            via_template,
            via_template_ids[via_template.id],
            shape_ids,
            layer_name_map,
            source_format=board.metadata.source_format,
        )
        if command is not None:
            lines.append(command)

    for net in board.nets:
        lines.append(
            f"layout add -net <{_quote_aaf(net.name)}> -t <{_net_type(net.role)}>"
        )

    net_names_by_id = {net.id: net.name for net in board.nets}
    component_by_id = {component.id: component for component in board.components}
    pads_by_pin_id = _pads_by_pin_id(board.pads)
    emitted_pad_ids: set[str] = set()

    for component in board.components:
        command = _component_command(
            component,
            layer_name_map,
            source_unit=geometry_source_unit,
            placement=(
                aedb_plan.placements_by_component_id.get(component.id)
                if aedb_plan is not None
                else None
            ),
            part_name_override=(
                part_export_plan.part_names_by_component_id.get(component.id)
                if part_export_plan is not None
                else None
            ),
            source_format=board.metadata.source_format,
        )
        if command is not None:
            lines.append(command)

    for pin in board.pins:
        for pad in pads_by_pin_id.get(pin.id, []):
            command = _pad_shape_command(
                pad,
                component_by_id,
                net_names_by_id,
                shape_ids,
                pad_shape_ids,
                layer_name_map,
                source_unit=geometry_source_unit,
                source_format=board.metadata.source_format,
            )
            if command is not None:
                lines.append(command)
                emitted_pad_ids.add(pad.id)
        command = _net_pin_command(
            pin,
            component_by_id,
            net_names_by_id,
            layer_name_map,
        )
        if command is not None:
            lines.append(command)

    for pad in board.pads:
        if pad.id in emitted_pad_ids:
            continue
        command = _pad_shape_command(
            pad,
            component_by_id,
            net_names_by_id,
            shape_ids,
            pad_shape_ids,
            layer_name_map,
            source_unit=geometry_source_unit,
            source_format=board.metadata.source_format,
        )
        if command is not None:
            lines.append(command)

    for command in _primitive_commands(
        board,
        layer_name_map,
        net_names_by_id,
        trace_shape_ids,
        source_unit=geometry_source_unit,
    ):
        lines.append(command)

    emitted_net_vias: set[tuple[str, str, str, str, str]] = set()
    for via in board.vias:
        if not via.net_id or not via.template_id or via.position is None:
            continue
        net_name = net_names_by_id.get(via.net_id)
        via_template_id = via_template_ids.get(via.template_id)
        if net_name is None or via_template_id is None:
            continue
        x = _length_to_mil(via.position.x, source_unit=geometry_source_unit)
        y = _length_to_mil(via.position.y, source_unit=geometry_source_unit)
        if x is None or y is None:
            continue
        rotation = _format_rotation(
            via.geometry.get("rotation"), source_format=board.metadata.source_format
        )
        rotation_option = "" if rotation == "0" else f" -rotation <{rotation}>"
        emitted_net_vias.add(_net_via_key(net_name, via_template_id, x, y, rotation))
        lines.append(
            "layout add "
            f"-net <{_quote_aaf(net_name)}> "
            f"-via <{via_template_id}> "
            f"-location <({_format_number(x)},{_format_number(y)})>"
            f"{rotation_option}"
        )
    for net_name, via_template_id, x, y, rotation in _component_pad_net_vias(
        board.pads,
        via_templates,
        via_template_ids,
        net_names_by_id,
        source_unit=geometry_source_unit,
        source_format=board.metadata.source_format,
        emitted_keys=emitted_net_vias,
    ):
        rotation_option = "" if rotation == "0" else f" -rotation <{rotation}>"
        lines.append(
            "layout add "
            f"-net <{_quote_aaf(net_name)}> "
            f"-via <{via_template_id}> "
            f"-location <({_format_number(x)},{_format_number(y)})>"
            f"{rotation_option}"
        )
    return lines
