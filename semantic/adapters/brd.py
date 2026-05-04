from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from aurora_translator.semantic.adapters.utils import (
    role_from_net_name,
    semantic_id,
    source_ref,
    unique_append,
)
from aurora_translator.semantic.models import (
    SemanticBoard,
    SemanticComponent,
    SemanticDiagnostic,
    SemanticFootprint,
    SemanticArcGeometry,
    SemanticLayer,
    SemanticMetadata,
    SemanticNet,
    SemanticPad,
    SemanticPadGeometry,
    SemanticPrimitive,
    SemanticPrimitiveGeometry,
    SemanticPin,
    SemanticPolygonVoidGeometry,
    SemanticPoint,
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
from aurora_translator.sources.brd.models import (
    BRDBlockSummary,
    BRDKeepout,
    BRDLayer,
    BRDLayout,
    BRDPlacedPad,
    BRDSegment,
    BRDShape,
)


BRD_UNKNOWN_MM_PER_RAW = 0.0001
DEFAULT_PAD_DIAMETER_MM = 0.1
ETCH_CLASS_CODE = 0x06
FOOTPRINT_INSTANCE_BLOCK = 0x2D


@dataclass(slots=True)
class _PadRecord:
    pad: BRDPlacedPad
    component_id: str
    footprint_id: str | None
    footprint_name: str
    net_id: str | None
    shape_id: str
    pin_name: str
    center: SemanticPoint


def from_brd(payload: BRDLayout, *, build_connectivity: bool = True) -> SemanticBoard:
    diagnostics = _source_diagnostics(payload)
    layers = _semantic_layers(payload)
    layer_names = [layer.name for layer in layers]
    top_layer = _top_layer_name(layers)

    nets, net_ids_by_assignment = _semantic_nets(payload)
    shapes: list[SemanticShape] = []
    shape_ids_by_key: dict[tuple[str, tuple[float, ...]], str] = {}

    via_templates, via_template_ids_by_padstack = _semantic_via_templates(
        payload,
        layer_names,
        shapes,
        shape_ids_by_key,
    )
    instance_footprint_names = _instance_footprint_names(payload)
    pad_records = _placed_pad_records(
        payload,
        top_layer,
        net_ids_by_assignment,
        instance_footprint_names,
        shapes,
        shape_ids_by_key,
    )
    footprints = _semantic_footprints(payload, pad_records)
    components, pins, pads = _component_pin_pad_records(pad_records, top_layer)
    vias = _semantic_vias(
        payload,
        layer_names,
        net_ids_by_assignment,
        via_template_ids_by_padstack,
    )
    primitives = _semantic_primitives(payload, layer_names, net_ids_by_assignment)

    board = SemanticBoard(
        metadata=SemanticMetadata(
            source_format="brd",
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
        components=components,
        footprints=footprints,
        pins=pins,
        pads=pads,
        vias=vias,
        primitives=primitives,
        diagnostics=diagnostics,
    )
    if build_connectivity:
        board.connectivity = build_connectivity_edges(board)
        board.diagnostics = [*board.diagnostics, *build_connectivity_diagnostics(board)]
    return board.with_computed_summary()


def _source_diagnostics(payload: BRDLayout) -> list[SemanticDiagnostic]:
    return [
        SemanticDiagnostic(
            severity="warning",
            code="brd.source_diagnostic",
            message=message,
            source=source_ref("brd", "diagnostics"),
        )
        for message in payload.diagnostics
    ]


def _semantic_layers(payload: BRDLayout) -> list[SemanticLayer]:
    string_by_id = {entry.id: entry.value for entry in payload.strings or []}
    candidate_layers = _physical_etch_layer_lists(payload, string_by_id)
    layers: list[SemanticLayer] = []
    for layer_list_index, layer_list, names in candidate_layers:
        for name_index, raw_name in enumerate(names):
            layers.append(
                SemanticLayer(
                    id=semantic_id("layer", raw_name, len(layers)),
                    name=raw_name,
                    layer_type="ETCH",
                    role="signal",
                    side=_layer_side(
                        ETCH_CLASS_CODE,
                        name_index,
                        len(names),
                        raw_name,
                    ),
                    order_index=len(layers),
                    material="BRD_COPPER",
                    source=source_ref(
                        "brd", f"layers[{layer_list_index}].names[{name_index}]"
                    ),
                )
            )
    return layers


def _physical_etch_layer_lists(
    payload: BRDLayout, string_by_id: dict[int, str]
) -> list[tuple[int, BRDLayer, list[str]]]:
    etch_keys = {
        entry.layer_list_key
        for entry in payload.header.layer_map
        if entry.class_code == ETCH_CLASS_CODE and entry.layer_list_key
    }
    resolved: list[tuple[int, BRDLayer, list[str]]] = []
    for index, layer_list in enumerate(payload.layers or []):
        names = _layer_names(layer_list, string_by_id)
        if layer_list.key not in etch_keys or not names:
            continue
        resolved.append((index, layer_list, names))

    stackup_like = [
        item for item in resolved if len(item[2]) > 1 and _has_top_bottom_names(item[2])
    ]
    if stackup_like:
        return [max(stackup_like, key=lambda item: len(item[2]))]

    multi_layer = [item for item in resolved if len(item[2]) > 1]
    if multi_layer:
        return [max(multi_layer, key=lambda item: len(item[2]))]

    return [
        item
        for item in resolved
        if not any(_non_stackup_etch_name(name) for name in item[2])
    ]


def _has_top_bottom_names(names: Iterable[str]) -> bool:
    folded = {name.casefold() for name in names}
    has_top = any(name == "top" or "top" in name for name in folded)
    has_bottom = any(
        name == "bottom" or name == "bot" or "bottom" in name or "bot" in name
        for name in folded
    )
    return has_top and has_bottom


def _non_stackup_etch_name(name: str) -> bool:
    text = name.casefold()
    return "scratch" in text or "construction" in text


def _layer_names(layer: BRDLayer, string_by_id: dict[int, str]) -> list[str]:
    names: list[str] = []
    for value in layer.names:
        if value.startswith("string:"):
            try:
                string_id = int(value.split(":", 1)[1])
            except ValueError:
                names.append(value)
                continue
            names.append(string_by_id.get(string_id, value))
        else:
            names.append(value)
    return names


def _layer_side(class_code: int, index: int, count: int, name: str) -> str | None:
    text = name.casefold()
    if "top" in text or text in {"f_cu", "front"}:
        return "top"
    if "bottom" in text or "bot" in text or text in {"b_cu", "back"}:
        return "bottom"
    if class_code == ETCH_CLASS_CODE and count > 1:
        if index == 0:
            return "top"
        if index == count - 1:
            return "bottom"
        return "internal"
    return None


def _top_layer_name(layers: list[SemanticLayer]) -> str | None:
    for layer in layers:
        if layer.side == "top":
            return layer.name
    return layers[0].name if layers else None


def _semantic_nets(payload: BRDLayout) -> tuple[list[SemanticNet], dict[int, str]]:
    nets: list[SemanticNet] = []
    net_ids_by_assignment: dict[int, str] = {}
    for index, net in enumerate(payload.nets or []):
        net_id = semantic_id("net", net.name or net.key, index)
        nets.append(
            SemanticNet(
                id=net_id,
                name=net.name or f"Net_{net.key}",
                role=role_from_net_name(net.name),
                source=source_ref("brd", f"nets[{index}]", net.key),
            )
        )
        net_ids_by_assignment[net.assignment] = net_id
        net_ids_by_assignment[net.key] = net_id
    return nets, net_ids_by_assignment


def _semantic_via_templates(
    payload: BRDLayout,
    layer_names: list[str],
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[float, ...]], str],
) -> tuple[list[SemanticViaTemplate], dict[int, str]]:
    via_templates: list[SemanticViaTemplate] = []
    ids_by_padstack: dict[int, str] = {}
    for index, padstack in enumerate(payload.padstacks or []):
        diameter = _raw_length_to_semantic(payload, padstack.drill_size_raw)
        if diameter is None or diameter <= 0:
            diameter = DEFAULT_PAD_DIAMETER_MM
        barrel_shape_id = _shape_id(
            shapes,
            shape_ids_by_key,
            kind="circle",
            auroradb_type="Circle",
            values=[0.0, 0.0, diameter],
            source_path=f"padstacks[{index}].drill_size_raw",
            source_key=padstack.key,
        )
        template_id = semantic_id("via_template", padstack.name or padstack.key, index)
        via_templates.append(
            SemanticViaTemplate(
                id=template_id,
                name=padstack.name or f"Padstack_{padstack.key}",
                barrel_shape_id=barrel_shape_id,
                layer_pads=[
                    SemanticViaTemplateLayer(
                        layer_name=layer_name,
                        pad_shape_id=barrel_shape_id,
                    )
                    for layer_name in layer_names
                ],
                geometry=SemanticViaTemplateGeometry(
                    source="brd_padstack_drill",
                    symbol=padstack.name,
                ),
                source=source_ref("brd", f"padstacks[{index}]", padstack.key),
            )
        )
        ids_by_padstack[padstack.key] = template_id
    return via_templates, ids_by_padstack


def _placed_pad_records(
    payload: BRDLayout,
    top_layer: str | None,
    net_ids_by_assignment: dict[int, str],
    instance_footprint_names: dict[int, str],
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[float, ...]], str],
) -> list[_PadRecord]:
    if top_layer is None:
        return []
    records: list[_PadRecord] = []
    for index, placed_pad in enumerate(payload.placed_pads or []):
        bbox = _bbox_points(payload, placed_pad.coords_raw)
        if bbox is None:
            continue
        x_min, y_min, x_max, y_max = bbox
        width = abs(x_max - x_min)
        height = abs(y_max - y_min)
        if width <= 0 or height <= 0:
            continue
        center = SemanticPoint(x=(x_min + x_max) / 2.0, y=(y_min + y_max) / 2.0)
        shape_id = _shape_id(
            shapes,
            shape_ids_by_key,
            kind="rectangle",
            auroradb_type="Rectangle",
            values=[0.0, 0.0, width, height],
            source_path=f"placed_pads[{index}].coords_raw",
            source_key=placed_pad.key,
        )
        footprint_name = instance_footprint_names.get(
            placed_pad.parent_footprint, f"BRD_FOOTPRINT_{placed_pad.parent_footprint}"
        )
        footprint_id = semantic_id("footprint", footprint_name)
        records.append(
            _PadRecord(
                pad=placed_pad,
                component_id=semantic_id("component", placed_pad.parent_footprint),
                footprint_id=footprint_id,
                footprint_name=footprint_name,
                net_id=net_ids_by_assignment.get(placed_pad.net_assignment),
                shape_id=shape_id,
                pin_name=_pin_name(placed_pad),
                center=center,
            )
        )
    return records


def _pin_name(placed_pad: BRDPlacedPad) -> str:
    if placed_pad.pin_number:
        return str(placed_pad.pin_number)
    return str(placed_pad.key)


def _semantic_footprints(
    payload: BRDLayout, pad_records: list[_PadRecord]
) -> list[SemanticFootprint]:
    names = {
        record.footprint_name: record.footprint_id
        for record in pad_records
        if record.footprint_id
    }
    for footprint in payload.footprints or []:
        if not footprint.name:
            continue
        names.setdefault(footprint.name, semantic_id("footprint", footprint.name))

    footprints: list[SemanticFootprint] = []
    pad_ids_by_footprint: dict[str, list[str]] = defaultdict(list)
    for record in pad_records:
        if record.footprint_id:
            unique_append(
                pad_ids_by_footprint[record.footprint_id],
                semantic_id("pad", record.pad.key),
            )

    for index, (name, footprint_id) in enumerate(sorted(names.items())):
        footprints.append(
            SemanticFootprint(
                id=footprint_id,
                name=name,
                pad_ids=pad_ids_by_footprint.get(footprint_id, []),
                source=source_ref("brd", "footprints", index),
            )
        )
    return footprints


def _component_pin_pad_records(
    pad_records: list[_PadRecord], top_layer: str | None
) -> tuple[list[SemanticComponent], list[SemanticPin], list[SemanticPad]]:
    pads_by_component: dict[str, list[_PadRecord]] = defaultdict(list)
    for record in pad_records:
        pads_by_component[record.component_id].append(record)

    components: list[SemanticComponent] = []
    pins: list[SemanticPin] = []
    pads: list[SemanticPad] = []
    for component_id, records in sorted(pads_by_component.items()):
        component_key = str(records[0].pad.parent_footprint)
        component_center = _average_point(record.center for record in records)
        pin_ids: list[str] = []
        pad_ids: list[str] = []
        footprint_name = records[0].footprint_name
        footprint_id = records[0].footprint_id

        for record in records:
            pin_id = semantic_id(
                "pin",
                f"{record.pad.parent_footprint}:{record.pin_name}:{record.pad.key}",
            )
            pad_id = semantic_id("pad", record.pad.key)
            unique_append(pin_ids, pin_id)
            unique_append(pad_ids, pad_id)
            pins.append(
                SemanticPin(
                    id=pin_id,
                    name=record.pin_name,
                    component_id=component_id,
                    net_id=record.net_id,
                    pad_ids=[pad_id],
                    layer_name=top_layer,
                    position=record.center,
                    source=source_ref("brd", "placed_pads.pin_number", record.pad.key),
                )
            )
            pads.append(
                SemanticPad(
                    id=pad_id,
                    name=record.pin_name,
                    footprint_id=footprint_id,
                    component_id=component_id,
                    pin_id=pin_id,
                    net_id=record.net_id,
                    layer_name=top_layer,
                    position=record.center,
                    padstack_definition=str(record.pad.pad or ""),
                    geometry=SemanticPadGeometry(
                        shape_id=record.shape_id,
                        source="brd_placed_pad_bbox",
                    ),
                    source=source_ref("brd", "placed_pads", record.pad.key),
                )
            )

        components.append(
            SemanticComponent(
                id=component_id,
                refdes=f"BRD_{component_key}",
                name=f"BRD_{component_key}",
                part_name=footprint_name,
                package_name=footprint_name,
                footprint_id=footprint_id,
                layer_name=top_layer,
                side="top",
                location=component_center,
                rotation=0,
                pin_ids=pin_ids,
                pad_ids=pad_ids,
                source=source_ref("brd", "placed_pads.parent_footprint", component_key),
            )
        )

    return components, pins, pads


def _semantic_vias(
    payload: BRDLayout,
    layer_names: list[str],
    net_ids_by_assignment: dict[int, str],
    via_template_ids_by_padstack: dict[int, str],
) -> list[SemanticVia]:
    vias: list[SemanticVia] = []
    if not layer_names:
        return vias
    for index, via in enumerate(payload.vias or []):
        x = _raw_coord_to_semantic(payload, via.x_raw)
        y = _raw_coord_to_semantic(payload, via.y_raw)
        if x is None or y is None:
            continue
        template_id = via_template_ids_by_padstack.get(via.padstack)
        net_id = net_ids_by_assignment.get(via.net_assignment)
        vias.append(
            SemanticVia(
                id=semantic_id("via", via.key, index),
                name=str(via.key),
                template_id=template_id,
                net_id=net_id,
                layer_names=layer_names,
                position=SemanticPoint(x=x, y=y),
                geometry=SemanticViaGeometry(rotation=0),
                source=source_ref("brd", f"vias[{index}]", via.key),
            )
        )
    return vias


def _semantic_primitives(
    payload: BRDLayout,
    layer_names: list[str],
    net_ids_by_assignment: dict[int, str],
) -> list[SemanticPrimitive]:
    segments_by_key = {segment.key: segment for segment in payload.segments or []}
    segment_indexes = {
        segment.key: index for index, segment in enumerate(payload.segments or [])
    }
    keepouts_by_key = {keepout.key: keepout for keepout in payload.keepouts or []}
    keepout_indexes = {
        keepout.key: index for index, keepout in enumerate(payload.keepouts or [])
    }
    conn_net_ids_by_item = _net_ids_by_connected_item(payload, net_ids_by_assignment)
    primitives: list[SemanticPrimitive] = []

    for track_index, track in enumerate(payload.tracks or []):
        layer_name = _layer_name_from_info(track.layer, layer_names)
        if layer_name is None:
            continue
        net_id = net_ids_by_assignment.get(
            track.net_assignment
        ) or conn_net_ids_by_item.get(track.key)
        for segment in _walk_segment_chain(
            track.first_segment, track.key, segments_by_key
        ):
            primitive = _segment_primitive(
                payload,
                segment,
                layer_name=layer_name,
                net_id=net_id,
                source_path=f"tracks[{track_index}].first_segment",
                source_index=segment_indexes.get(segment.key),
            )
            if primitive is not None:
                primitives.append(primitive)

    for shape_index, shape in enumerate(payload.shapes or []):
        primitive = _shape_primitive(
            payload,
            shape,
            shape_index=shape_index,
            layer_names=layer_names,
            segments_by_key=segments_by_key,
            keepouts_by_key=keepouts_by_key,
            net_id=conn_net_ids_by_item.get(shape.key),
            keepout_indexes=keepout_indexes,
            segment_indexes=segment_indexes,
        )
        if primitive is not None:
            primitives.append(primitive)

    return primitives


def _segment_primitive(
    payload: BRDLayout,
    segment: BRDSegment,
    *,
    layer_name: str,
    net_id: str | None,
    source_path: str,
    source_index: int | None,
) -> SemanticPrimitive | None:
    start = _raw_point_to_semantic(payload, segment.start_raw)
    end = _raw_point_to_semantic(payload, segment.end_raw)
    width = _raw_length_to_semantic(payload, segment.width_raw)
    if start is None or end is None or width is None:
        return None

    path = f"segments[{source_index}]" if source_index is not None else source_path
    if segment.kind == "line":
        return SemanticPrimitive(
            id=semantic_id("primitive", f"brd-line:{segment.key}"),
            kind="trace",
            layer_name=layer_name,
            net_id=net_id,
            geometry=SemanticPrimitiveGeometry(
                record_kind="LINE",
                feature_id=segment.key,
                width=width,
                center_line=[start, end],
            ),
            source=source_ref("brd", path, segment.key),
        )

    center = _raw_point_to_semantic(payload, segment.center_raw)
    if segment.kind != "arc" or center is None:
        return None
    return SemanticPrimitive(
        id=semantic_id("primitive", f"brd-arc:{segment.key}"),
        kind="arc",
        layer_name=layer_name,
        net_id=net_id,
        geometry=SemanticPrimitiveGeometry(
            record_kind="ARC",
            feature_id=segment.key,
            width=width,
            start=start,
            end=end,
            center=center,
            radius=_raw_length_to_semantic(payload, segment.radius_raw),
            clockwise=segment.clockwise,
            is_ccw=False if segment.clockwise else True,
        ),
        source=source_ref("brd", path, segment.key),
    )


def _shape_primitive(
    payload: BRDLayout,
    shape: BRDShape,
    *,
    shape_index: int,
    layer_names: list[str],
    segments_by_key: dict[int, BRDSegment],
    keepouts_by_key: dict[int, BRDKeepout],
    net_id: str | None,
    keepout_indexes: dict[int, int],
    segment_indexes: dict[int, int],
) -> SemanticPrimitive | None:
    if net_id is None:
        return None
    layer_name = _layer_name_from_info(shape.layer, layer_names)
    if layer_name is None:
        return None

    arcs, raw_points = _polygon_chain_geometry(
        payload, shape.first_segment, shape.key, segments_by_key
    )
    if len(raw_points) < 2:
        return None

    voids: list[SemanticPolygonVoidGeometry] = []
    for keepout in _walk_keepout_chain(shape.first_keepout, keepouts_by_key):
        void_arcs, void_raw_points = _polygon_chain_geometry(
            payload, keepout.first_segment, keepout.key, segments_by_key
        )
        if len(void_raw_points) < 2:
            continue
        keepout_index = keepout_indexes.get(keepout.key)
        voids.append(
            SemanticPolygonVoidGeometry(
                raw_points=void_raw_points,
                arcs=void_arcs,
                source_contour_index=keepout_index,
            )
        )

    bbox = _bbox_points(payload, shape.coords_raw)
    return SemanticPrimitive(
        id=semantic_id("primitive", f"brd-shape:{shape.key}"),
        kind="polygon",
        layer_name=layer_name,
        net_id=net_id,
        geometry=SemanticPrimitiveGeometry(
            record_kind="SHAPE",
            feature_id=shape.key,
            raw_points=raw_points,
            arcs=arcs,
            voids=voids,
            bbox=list(bbox) if bbox is not None else None,
            has_voids=bool(voids),
        ),
        source=source_ref("brd", f"shapes[{shape_index}]", shape.key),
    )


def _polygon_chain_geometry(
    payload: BRDLayout,
    first_segment: int,
    tail_key: int,
    segments_by_key: dict[int, BRDSegment],
) -> tuple[list[SemanticArcGeometry], list[list[float | int | None]]]:
    arcs: list[SemanticArcGeometry] = []
    raw_points: list[list[float | int | None]] = []
    for segment in _walk_segment_chain(first_segment, tail_key, segments_by_key):
        geometry = _segment_arc_geometry(payload, segment)
        if geometry is None:
            continue
        arcs.append(geometry)
        end = _raw_point_to_semantic(payload, segment.end_raw)
        if end is not None:
            raw_points.append(end)

    if arcs:
        first_start = arcs[0].start
        if first_start is not None:
            raw_points.insert(0, list(first_start))
    return arcs, raw_points


def _segment_arc_geometry(
    payload: BRDLayout, segment: BRDSegment
) -> SemanticArcGeometry | None:
    start = _raw_point_to_semantic(payload, segment.start_raw)
    end = _raw_point_to_semantic(payload, segment.end_raw)
    if start is None or end is None:
        return None
    if segment.kind == "line":
        return SemanticArcGeometry(start=start, end=end, is_segment=True)

    center = _raw_point_to_semantic(payload, segment.center_raw)
    if center is None:
        return None
    return SemanticArcGeometry(
        start=start,
        end=end,
        center=center,
        radius=_raw_length_to_semantic(payload, segment.radius_raw),
        clockwise=segment.clockwise,
        is_ccw=False if segment.clockwise else True,
    )


def _walk_segment_chain(
    first_key: int, tail_key: int, segments_by_key: dict[int, BRDSegment]
) -> Iterable[BRDSegment]:
    current = first_key
    seen: set[int] = set()
    while current and current not in seen:
        seen.add(current)
        segment = segments_by_key.get(current)
        if segment is None:
            break
        yield segment
        next_key = segment.next
        if not next_key or next_key == tail_key:
            break
        current = next_key


def _walk_keepout_chain(
    first_key: int, keepouts_by_key: dict[int, BRDKeepout]
) -> Iterable[BRDKeepout]:
    current = first_key
    seen: set[int] = set()
    while current and current not in seen:
        seen.add(current)
        keepout = keepouts_by_key.get(current)
        if keepout is None:
            break
        yield keepout
        current = keepout.next


def _net_ids_by_connected_item(
    payload: BRDLayout, net_ids_by_assignment: dict[int, str]
) -> dict[int, str]:
    next_by_key = {
        block.key: block.next
        for block in payload.blocks or []
        if block.key is not None and block.next is not None
    }
    result: dict[int, str] = {}
    for assignment in payload.net_assignments or []:
        net_id = net_ids_by_assignment.get(assignment.net) or net_ids_by_assignment.get(
            assignment.key
        )
        if net_id is None:
            continue
        current = assignment.conn_item
        seen: set[int] = set()
        while current and current not in seen:
            seen.add(current)
            result.setdefault(current, net_id)
            next_key = next_by_key.get(current)
            if not next_key or next_key == assignment.key:
                break
            current = next_key
    return result


def _layer_name_from_info(layer: object, layer_names: list[str]) -> str | None:
    class_code = getattr(layer, "class_code", None)
    if class_code != ETCH_CLASS_CODE:
        return None
    subclass_name = getattr(layer, "subclass_name", None)
    if isinstance(subclass_name, str) and subclass_name in layer_names:
        return subclass_name

    subclass_code = getattr(layer, "subclass_code", None)
    if isinstance(subclass_code, int):
        if 0 <= subclass_code < len(layer_names):
            return layer_names[subclass_code]
        if 1 <= subclass_code <= len(layer_names):
            return layer_names[subclass_code - 1]
    return None


def _instance_footprint_names(payload: BRDLayout) -> dict[int, str]:
    instance_next_by_key = {
        block.key: block.next
        for block in payload.blocks or []
        if _is_footprint_instance_block(block)
    }
    result: dict[int, str] = {}
    for footprint in payload.footprints or []:
        if not footprint.name or not footprint.first_instance:
            continue
        current = footprint.first_instance
        seen: set[int] = set()
        while current and current not in seen:
            seen.add(current)
            result[current] = footprint.name
            next_key = instance_next_by_key.get(current)
            if not next_key or next_key == footprint.key:
                break
            current = next_key
    return result


def _is_footprint_instance_block(block: BRDBlockSummary) -> bool:
    return (
        block.block_type == FOOTPRINT_INSTANCE_BLOCK
        and block.key is not None
        and block.next is not None
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
            source=source_ref("brd", source_path, source_key),
        )
    )
    return shape_id


def _bbox_points(payload: BRDLayout, coords_raw: list[int]) -> tuple[float, ...] | None:
    if len(coords_raw) < 4:
        return None
    values = [_raw_coord_to_semantic(payload, value) for value in coords_raw[:4]]
    if any(value is None for value in values):
        return None
    x0, y0, x1, y1 = [float(value) for value in values]
    if x0 == x1 or y0 == y1:
        return None
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def _average_point(points: Iterable[SemanticPoint]) -> SemanticPoint:
    x_total = 0.0
    y_total = 0.0
    count = 0
    for point in points:
        x_total += point.x
        y_total += point.y
        count += 1
    if count == 0:
        return SemanticPoint(x=0.0, y=0.0)
    return SemanticPoint(x=x_total / count, y=y_total / count)


def _raw_coord_to_semantic(
    payload: BRDLayout, value: int | float | None
) -> float | None:
    if value is None:
        return None
    scale_nm = payload.header.coordinate_scale_nm
    if scale_nm is not None and scale_nm > 0:
        return float(value) * scale_nm / 1_000_000.0
    unit = payload.header.board_units.casefold()
    if unit in {"millimeters", "millimeter", "mm"}:
        divisor = payload.header.units_divisor or 10_000
        return float(value) / divisor
    if unit in {"mils", "mil"}:
        divisor = payload.header.units_divisor or 1
        return float(value) / divisor * 0.0254
    return float(value) * BRD_UNKNOWN_MM_PER_RAW


def _raw_length_to_semantic(
    payload: BRDLayout, value: int | float | None
) -> float | None:
    if value is None:
        return None
    return abs(_raw_coord_to_semantic(payload, value) or 0.0)


def _raw_point_to_semantic(
    payload: BRDLayout, values: list[int | float] | tuple[int | float, ...] | None
) -> list[float] | None:
    if values is None or len(values) < 2:
        return None
    x = _raw_coord_to_semantic(payload, values[0])
    y = _raw_coord_to_semantic(payload, values[1])
    if x is None or y is None:
        return None
    return [x, y]


def _semantic_units(payload: BRDLayout) -> str:
    _ = payload
    return "mm"
