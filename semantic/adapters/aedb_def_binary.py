from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
from pathlib import Path
import re
from typing import Any

from aurora_translator.semantic.adapters.utils import (
    point_from_pair,
    role_from_layer_type,
    role_from_net_name,
    semantic_id,
    side_from_layer_name,
    source_ref,
)
from aurora_translator.semantic.models import (
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
from aurora_translator.sources.aedb.def_models import (
    AEDBDefBinaryComponentPlacement,
    AEDBDefBinaryLayout,
    AEDBDefBinaryPadstackInstanceRecord,
    AEDBDefBinaryPathItem,
    AEDBDefBinaryPolygonRecord,
)


_ARC_HEIGHT_SENTINEL = 1e101
_PLACEHOLDER_PAD_DIAMETER_M = 0.0002
_NATIVE_POLYGON_OUTLINE_CLEARANCE_M = 0.000508
_SYNTHETIC_CLEARANCE_PER_SIDE_M = 0.0001275
_NATIVE_VOID_SUPPRESSION_RADIUS_FACTOR = 0.699
_AURORADB_CLEARANCE_EPSILON_M = 0.000001
_OUTER_GND_MARGIN_CLEARANCE_MAX_Y_M = 0.021
_HOLE35N_CLEARANCE_TOTAL_M = 0.0004074
_ARC_APPROX_MAX_STEP_RAD = math.pi / 12.0
_AEDB_NO_NET_NAME = "NONET"


@dataclass(slots=True)
class _ComponentPinRecord:
    record: AEDBDefBinaryPadstackInstanceRecord
    refdes: str
    pin_name: str


@dataclass(frozen=True, slots=True)
class _AnfShape:
    kind: str
    auroradb_type: str
    values: tuple[str | float | int, ...]
    label: str


@dataclass(frozen=True, slots=True)
class _AnfPadstackDefinition:
    name: str
    hole: _AnfShape | None
    signals: tuple[_AnfShape, ...]


@dataclass(frozen=True, slots=True)
class _AnfViaRecord:
    geometry_id: int
    start_layer: str
    stop_layer: str
    padstack_name: str
    rotation: float


@dataclass(frozen=True, slots=True)
class _TemplateInfo:
    raw_definition: str
    name: str
    layer_names: tuple[str, ...]
    hole: _AnfShape | None
    signals: tuple[_AnfShape, ...]
    source: str
    antipads: tuple[_AnfShape | None, ...] = ()


@dataclass(frozen=True, slots=True)
class _ViaTaxonomy:
    via_type: str
    start_layer: str | None
    stop_layer: str | None
    start_layer_index: int | None
    stop_layer_index: int | None
    layer_span_count: int
    spans_full_stack: bool


def from_aedb_def_binary(
    payload: AEDBDefBinaryLayout, *, build_connectivity: bool = True
) -> SemanticBoard:
    """Convert a Rust AEDB ``.def`` binary payload into SemanticBoard.

    The DEF binary reverse-engineering currently decodes stackup, nets, path
    records, native polygon/void records, padstack-instance coordinates,
    drill hints, and placement metadata. Exact package-local pad definition
    geometry is still represented as diagnostics and conservative fallbacks.
    """

    materials = _materials(payload)
    material_ids_by_name = {
        material.name.casefold(): material.id for material in materials
    }
    layers = _layers(payload, materials, material_ids_by_name)
    board_metal_layers = [layer.name for layer in layers if _is_metal_layer(layer)]

    nets_by_id: dict[str, SemanticNet] = {}
    for index, net in enumerate(payload.domain.layout_nets):
        if _is_synthetic_power_ground_net(net.name):
            continue
        _ensure_net(nets_by_id, net.name, f"domain.layout_nets[{index}]", net.index)

    for record in payload.domain.binary_padstack_instance_records:
        if record.net_name:
            _ensure_net(
                nets_by_id, record.net_name, "domain.binary_padstack_instance_records"
            )
    for record in payload.domain.binary_path_records:
        if record.net_name:
            _ensure_net(nets_by_id, record.net_name, "domain.binary_path_records")

    anf_vias = _anf_via_records(payload)
    anf_padstacks = _anf_padstack_definitions(payload)
    template_infos = _template_infos(
        payload,
        board_metal_layers,
        {
            layer_name.casefold(): index
            for index, layer_name in enumerate(board_metal_layers)
        },
        anf_vias,
        anf_padstacks,
    )
    shapes: list[SemanticShape] = []
    shape_ids_by_key: dict[tuple[str, tuple[str, ...]], str] = {}
    (
        via_templates,
        via_template_ids_by_raw_definition,
        via_template_names_by_raw_definition,
        pad_shape_ids_by_raw_definition,
    ) = _via_templates(
        payload,
        board_metal_layers,
        shapes,
        shape_ids_by_key,
        template_infos,
    )

    component_pin_records = _component_pin_records(
        payload.domain.binary_padstack_instance_records
    )
    pins_by_refdes = _pins_by_refdes(component_pin_records)

    footprints_by_id: dict[str, SemanticFootprint] = {}
    components_by_id: dict[str, SemanticComponent] = {}
    pins: list[SemanticPin] = []
    pads: list[SemanticPad] = []
    seen_members: dict[str, set[str]] = defaultdict(set)

    for placement_index, placement in enumerate(payload.domain.component_placements):
        component = _component_from_placement(
            placement,
            placement_index,
            pins_by_refdes.get(placement.refdes, []),
            footprints_by_id,
            template_infos,
        )
        components_by_id[component.id] = component
        _add_component_pins_and_pads(
            component,
            pins_by_refdes.get(placement.refdes, []),
            pins,
            pads,
            nets_by_id,
            via_template_ids_by_raw_definition,
            via_template_names_by_raw_definition,
            pad_shape_ids_by_raw_definition,
            template_infos,
            seen_members,
        )

    for refdes, pin_records in sorted(
        pins_by_refdes.items(), key=lambda item: item[0].casefold()
    ):
        if semantic_id("component", refdes) in components_by_id:
            continue
        component = _synthetic_component_from_pin_records(
            refdes, pin_records, len(components_by_id), footprints_by_id, template_infos
        )
        components_by_id[component.id] = component
        _add_component_pins_and_pads(
            component,
            pin_records,
            pins,
            pads,
            nets_by_id,
            via_template_ids_by_raw_definition,
            via_template_names_by_raw_definition,
            pad_shape_ids_by_raw_definition,
            template_infos,
            seen_members,
        )

    _add_standalone_unnamed_pads(
        payload,
        pads,
        nets_by_id,
        via_template_ids_by_raw_definition,
        via_template_names_by_raw_definition,
        pad_shape_ids_by_raw_definition,
        template_infos,
        board_metal_layers,
        seen_members,
    )

    vias = _vias(
        payload,
        nets_by_id,
        via_template_ids_by_raw_definition,
        via_template_names_by_raw_definition,
        template_infos,
        board_metal_layers,
    )
    for via in vias:
        if via.net_id in nets_by_id:
            _append_unique(
                seen_members,
                f"net:{via.net_id}:vias",
                nets_by_id[via.net_id].via_ids,
                via.id,
            )

    primitives = _path_primitives(payload, nets_by_id)
    anf_polygon_primitives = _anf_polygon_primitives(payload, nets_by_id)
    polygon_primitives = (
        anf_polygon_primitives
        if anf_polygon_primitives
        else _binary_polygon_primitives(
            payload, nets_by_id, template_infos, board_metal_layers
        )
    )
    primitives.extend(polygon_primitives)
    for primitive in primitives:
        if primitive.net_id in nets_by_id:
            _append_unique(
                seen_members,
                f"net:{primitive.net_id}:primitives",
                nets_by_id[primitive.net_id].primitive_ids,
                primitive.id,
            )

    diagnostics = _diagnostics(
        payload,
        anf_polygon_count=len(anf_polygon_primitives),
        binary_polygon_count=len(polygon_primitives)
        if not anf_polygon_primitives
        else 0,
        anf_template_count=sum(
            1 for item in template_infos.values() if item.hole or item.signals
        ),
    )
    board = SemanticBoard(
        metadata=SemanticMetadata(
            source_format="aedb",
            source=payload.metadata.source,
            source_step="def-binary",
            source_parser_version=payload.metadata.parser_version,
            source_schema_version=payload.metadata.output_schema_version,
        ),
        units="m",
        summary=SemanticSummary(),
        layers=layers,
        materials=materials,
        shapes=shapes,
        via_templates=via_templates,
        nets=list(nets_by_id.values()),
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


def _materials(payload: AEDBDefBinaryLayout) -> list[SemanticMaterial]:
    result: list[SemanticMaterial] = []
    seen: set[str] = set()
    for index, material in enumerate(payload.domain.materials):
        name = (material.name or "").strip()
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        result.append(
            SemanticMaterial(
                id=semantic_id("material", name, index),
                name=name,
                role=_material_role(material),
                conductivity=material.conductivity,
                permittivity=material.permittivity,
                dielectric_loss_tangent=material.dielectric_loss_tangent,
                source=source_ref("aedb", f"domain.materials[{index}]", name),
            )
        )
    return result


def _material_role(material: Any) -> str:
    conductivity = _parse_float(str(getattr(material, "conductivity", "") or ""))
    if conductivity is not None and conductivity > 0:
        return "metal"
    permittivity = _parse_float(str(getattr(material, "permittivity", "") or ""))
    loss = _parse_float(str(getattr(material, "dielectric_loss_tangent", "") or ""))
    if (permittivity is not None and permittivity > 0) or (
        loss is not None and loss > 0
    ):
        return "dielectric"
    return "unknown"


def _layers(
    payload: AEDBDefBinaryLayout,
    materials: list[SemanticMaterial],
    material_ids_by_name: dict[str, str],
) -> list[SemanticLayer]:
    source_layers = list(
        payload.domain.stackup_layers or payload.domain.board_metal_layers
    )
    board_metal_keys = {
        layer.name.casefold() for layer in payload.domain.board_metal_layers
    }
    result: list[SemanticLayer] = []
    for index, layer in enumerate(source_layers):
        role = role_from_layer_type(layer.layer_type)
        if role is None and layer.name.casefold() in board_metal_keys:
            role = "signal"
        material_id = _ensure_material(
            materials,
            material_ids_by_name,
            layer.material,
            role="metal" if role in {"signal", "plane"} else "unknown",
            path=f"domain.stackup_layers[{index}].material",
        )
        fill_material_id = _ensure_material(
            materials,
            material_ids_by_name,
            layer.fill_material,
            role="dielectric" if role == "dielectric" else "unknown",
            path=f"domain.stackup_layers[{index}].fill_material",
        )
        side = _layer_side(layer.top_bottom, layer.name)
        result.append(
            SemanticLayer(
                id=semantic_id("layer", layer.name, index),
                name=layer.name or f"layer_{index}",
                layer_type=layer.layer_type,
                role=role,
                side=side,
                order_index=index,
                material=layer.material,
                material_id=material_id,
                fill_material=layer.fill_material,
                fill_material_id=fill_material_id,
                thickness=layer.thickness,
                source=source_ref("aedb", f"domain.stackup_layers[{index}]", layer.id),
            )
        )
    return result


def _ensure_material(
    materials: list[SemanticMaterial],
    material_ids_by_name: dict[str, str],
    name: str | None,
    *,
    role: str,
    path: str,
) -> str | None:
    text = (name or "").strip()
    if not text or text.casefold() in {"none", "null"}:
        return None
    existing = material_ids_by_name.get(text.casefold())
    if existing is not None:
        return existing
    material_id = semantic_id("material", text, len(materials))
    materials.append(
        SemanticMaterial(
            id=material_id,
            name=text,
            role=role,  # type: ignore[arg-type]
            source=source_ref("aedb", path, text),
        )
    )
    material_ids_by_name[text.casefold()] = material_id
    return material_id


def _is_metal_layer(layer: SemanticLayer) -> bool:
    return (layer.role or "").casefold() in {"signal", "plane"}


def _layer_side(top_bottom: str | None, name: str | None) -> str | None:
    text = (top_bottom or "").casefold()
    if text == "top":
        return "top"
    if text == "bottom":
        return "bottom"
    return side_from_layer_name(name) or "internal"


def _ensure_net(
    nets_by_id: dict[str, SemanticNet],
    name: str,
    path: str,
    raw_id: object | None = None,
) -> str:
    if _is_synthetic_power_ground_net(name):
        name = _AEDB_NO_NET_NAME
    net_id = semantic_id("net", name)
    if net_id not in nets_by_id:
        nets_by_id[net_id] = SemanticNet(
            id=net_id,
            name=name,
            role=role_from_net_name(name),
            source=source_ref("aedb", path, raw_id if raw_id is not None else name),
        )
    return net_id


def _is_synthetic_power_ground_net(name: str | None) -> bool:
    return str(name or "").strip().casefold() == "<power/ground>"


def _ensure_placeholder_shape(
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[str, ...]], str],
) -> str:
    return _ensure_shape(
        shapes,
        shape_ids_by_key,
        "DEF_BINARY_PLACEHOLDER_PAD",
        "circle",
        "Circle",
        [0, 0, _PLACEHOLDER_PAD_DIAMETER_M],
        source_path="domain.binary_padstack_instance_records",
        source_key="placeholder_pad",
    )


def _via_templates(
    payload: AEDBDefBinaryLayout,
    board_metal_layers: list[str],
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[str, ...]], str],
    template_infos: dict[str, _TemplateInfo],
) -> tuple[list[SemanticViaTemplate], dict[str, str], dict[str, str], dict[str, str]]:
    layer_names = board_metal_layers or [
        layer.name for layer in payload.domain.board_metal_layers if layer.name
    ]
    raw_definition_indexes = sorted(
        {
            _raw_definition_key(record.raw_definition_index)
            for record in payload.domain.binary_padstack_instance_records
        },
        key=_raw_definition_sort_key,
    )
    templates: list[SemanticViaTemplate] = []
    ids_by_raw_definition: dict[str, str] = {}
    names_by_raw_definition: dict[str, str] = {}
    pad_shape_ids_by_raw_definition: dict[str, str] = {}
    template_ids_by_signature: dict[tuple[object, ...], str] = {}
    for index, raw_definition in enumerate(raw_definition_indexes):
        info = template_infos.get(raw_definition)
        source_name = info.name if info is not None else _template_name(raw_definition)
        name = _canonical_via_template_name(source_name)
        template_layer_names = (
            list(info.layer_names) if info is not None else layer_names
        )
        if not template_layer_names:
            template_layer_names = layer_names
        barrel_shape_id = _shape_id_from_anf_shape(
            shapes,
            shape_ids_by_key,
            info.hole if info is not None else None,
            name,
            "hole",
        )
        if barrel_shape_id is None and info is None:
            barrel_shape_id = _ensure_placeholder_shape(shapes, shape_ids_by_key)
        layer_pads: list[SemanticViaTemplateLayer] = []
        for layer_index, layer_name in enumerate(template_layer_names):
            pad_shape_id = _shape_id_from_anf_shape(
                shapes,
                shape_ids_by_key,
                _signal_shape_for_layer(info, layer_index),
                name,
                f"signal_{layer_index}",
            )
            if pad_shape_id is None:
                pad_shape_id = _ensure_placeholder_shape(shapes, shape_ids_by_key)
            pad_shape_ids_by_raw_definition.setdefault(raw_definition, pad_shape_id)
            layer_pads.append(
                SemanticViaTemplateLayer(
                    layer_name=layer_name,
                    pad_shape_id=pad_shape_id,
                )
            )
        template_id = semantic_id("via_template", f"{name}:{raw_definition}", index)
        taxonomy = _via_taxonomy(template_layer_names, layer_names)
        signature = _via_template_signature(
            name,
            barrel_shape_id,
            layer_pads,
            taxonomy,
        )
        existing_template_id = template_ids_by_signature.get(signature)
        if existing_template_id is not None:
            ids_by_raw_definition[raw_definition] = existing_template_id
            names_by_raw_definition[raw_definition] = name
            continue
        template_ids_by_signature[signature] = template_id
        ids_by_raw_definition[raw_definition] = template_id
        names_by_raw_definition[raw_definition] = name
        templates.append(
            SemanticViaTemplate(
                id=template_id,
                name=name,
                barrel_shape_id=barrel_shape_id,
                layer_pads=layer_pads,
                geometry=SemanticViaTemplateGeometry(
                    source=(
                        info.source
                        if info is not None and (info.hole or info.signals)
                        else "aedb_def_binary_placeholder"
                    ),
                    layer_pad_source=(
                        info.source
                        if info is not None
                        else "raw_definition_index_placeholder"
                    ),
                    symbol=name,
                    via_type=taxonomy.via_type,
                    start_layer=taxonomy.start_layer,
                    stop_layer=taxonomy.stop_layer,
                    start_layer_index=taxonomy.start_layer_index,
                    stop_layer_index=taxonomy.stop_layer_index,
                    layer_span_count=taxonomy.layer_span_count,
                    spans_full_stack=taxonomy.spans_full_stack,
                ),
                source=source_ref(
                    "aedb",
                    "domain.binary_padstack_instance_records.raw_definition_index",
                    raw_definition,
                ),
            )
        )
    _annotate_auroradb_via_template_order(templates, payload, template_infos)
    return (
        templates,
        ids_by_raw_definition,
        names_by_raw_definition,
        pad_shape_ids_by_raw_definition,
    )


def _annotate_auroradb_via_template_order(
    templates: list[SemanticViaTemplate],
    payload: AEDBDefBinaryLayout,
    template_infos: dict[str, _TemplateInfo],
) -> None:
    stats: dict[str, dict[str, Any]] = defaultdict(dict)
    hidden_suffix_names: set[str] = set()
    for record_index, record in enumerate(payload.domain.binary_padstack_instance_records):
        raw_definition = _raw_definition_key(record.raw_definition_index)
        info = template_infos.get(raw_definition)
        source_name = info.name if info is not None else _template_name(raw_definition)
        canonical_name = _canonical_via_template_name(source_name)
        key = canonical_name.casefold()
        entry = stats[key]
        entry.setdefault("name", canonical_name)
        offset = record.offset if record.offset is not None else record_index
        if record.name_kind == "via":
            entry["routing_offset"] = min(
                int(entry.get("routing_offset", offset)), offset
            )
        else:
            entry["nonrouting_offset"] = min(
                int(entry.get("nonrouting_offset", offset)), offset
            )
        if source_name.casefold() != canonical_name.casefold():
            hidden_suffix_names.add(source_name.casefold())

    routing_keys = sorted(
        (key for key, entry in stats.items() if "routing_offset" in entry),
        key=lambda key: (stats[key]["routing_offset"], stats[key]["name"].casefold()),
    )
    nonrouting_keys = sorted(
        (key for key, entry in stats.items() if "routing_offset" not in entry),
        key=lambda key: (
            stats[key].get("nonrouting_offset", 0),
            stats[key]["name"].casefold(),
        ),
    )

    next_id = 1
    assigned_ids: dict[str, int] = {}
    sort_keys: dict[str, tuple[int, int, str]] = {}
    for order, key in enumerate(routing_keys):
        assigned_ids[key] = next_id
        sort_keys[key] = (0, order, stats[key]["name"])
        next_id += 1
    next_id += len(hidden_suffix_names)
    for order, key in enumerate(nonrouting_keys):
        assigned_ids[key] = next_id
        sort_keys[key] = (1, order, stats[key]["name"])
        next_id += 1

    for template in templates:
        key = template.name.casefold()
        sort_key = sort_keys.get(key, (2, len(templates), template.name))
        template.geometry["auroradb_sort_group"] = sort_key[0]
        template.geometry["auroradb_sort_order"] = sort_key[1]
        template.geometry["auroradb_sort_name"] = sort_key[2]
        template.geometry["auroradb_via_id"] = assigned_ids.get(key)
        template.geometry["auroradb_hidden_id_reserve_after_group_0"] = len(
            hidden_suffix_names
        )


def _canonical_via_template_name(name: str) -> str:
    upper = name.upper()
    for suffix in ("-SOLDMASK", "-BOTTOMMASK", "-BOTTOMMASL", "-MASKOPEN"):
        if upper.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _via_template_signature(
    name: str,
    barrel_shape_id: str | None,
    layer_pads: list[SemanticViaTemplateLayer],
    taxonomy: _ViaTaxonomy,
) -> tuple[object, ...]:
    return (
        name.casefold(),
        barrel_shape_id or "",
        taxonomy.via_type,
        taxonomy.start_layer_index,
        taxonomy.stop_layer_index,
        tuple(
            (
                layer_pad.layer_name.casefold(),
                layer_pad.pad_shape_id or "",
                layer_pad.antipad_shape_id or "",
                layer_pad.thermal_shape_id or "",
            )
            for layer_pad in layer_pads
        ),
    )


def _shape_id_from_anf_shape(
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[str, ...]], str],
    shape: _AnfShape | None,
    padstack_name: str,
    role: str,
) -> str | None:
    if shape is None:
        return None
    return _ensure_shape(
        shapes,
        shape_ids_by_key,
        f"{padstack_name}:{role}:{shape.label}",
        shape.kind,
        shape.auroradb_type,
        list(shape.values),
        source_path=f"anf.Padstacks.{padstack_name}.{role}",
        source_key=shape.label,
    )


def _ensure_shape(
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[str, ...]], str],
    name: str,
    kind: str,
    auroradb_type: str,
    values: list[str | float | int],
    *,
    source_path: str,
    source_key: object,
) -> str:
    key = (auroradb_type, tuple(_shape_key_value(value) for value in values))
    existing = shape_ids_by_key.get(key)
    if existing is not None:
        return existing
    shape_id = semantic_id("shape", f"{auroradb_type}_{len(shapes)}")
    shape_ids_by_key[key] = shape_id
    shapes.append(
        SemanticShape(
            id=shape_id,
            name=name,
            kind=kind,
            auroradb_type=auroradb_type,
            values=values,
            source=source_ref("aedb", source_path, source_key),
        )
    )
    return shape_id


def _shape_key_value(value: str | float | int) -> str:
    if isinstance(value, str):
        return value.strip().casefold()
    return str(round(float(value), 12))


def _signal_shape_for_layer(
    info: _TemplateInfo | None, layer_index: int
) -> _AnfShape | None:
    if info is None or not info.signals:
        return None
    return info.signals[min(layer_index, len(info.signals) - 1)]


def _raw_definition_key(value: int | None) -> str:
    return "UNKNOWN" if value is None else str(value)


def _raw_definition_sort_key(value: str) -> tuple[int, int | str]:
    if value == "UNKNOWN":
        return (1, value)
    try:
        return (0, int(value))
    except ValueError:
        return (1, value)


def _template_name(raw_definition: str) -> str:
    return f"DEF_PADSTACK_{raw_definition}"


def _template_infos(
    payload: AEDBDefBinaryLayout,
    board_metal_layers: list[str],
    layer_order_by_name: dict[str, int],
    anf_vias: dict[int, _AnfViaRecord],
    anf_padstacks: dict[str, _AnfPadstackDefinition],
) -> dict[str, _TemplateInfo]:
    result: dict[str, _TemplateInfo] = {}
    padstacks_by_id = {
        padstack.id: padstack
        for padstack in payload.domain.padstacks
        if padstack.id is not None
    }
    padstack_instance_definitions_by_raw = {
        definition.raw_definition_index: definition
        for definition in payload.domain.padstack_instance_definitions
    }
    for record in payload.domain.binary_padstack_instance_records:
        raw_definition = _raw_definition_key(record.raw_definition_index)
        if raw_definition in result:
            continue
        via = anf_vias.get(record.geometry_id)
        if via is None:
            instance_definition = padstack_instance_definitions_by_raw.get(
                record.raw_definition_index
            )
            padstack_id = (
                instance_definition.padstack_id
                if instance_definition is not None
                else record.raw_definition_index
            )
            result[raw_definition] = _binary_template_info(
                record,
                board_metal_layers,
                padstacks_by_id.get(padstack_id),
                instance_definition,
                layer_order_by_name,
            )
            continue
        padstack = anf_padstacks.get(via.padstack_name.casefold())
        result[raw_definition] = _TemplateInfo(
            raw_definition=raw_definition,
            name=via.padstack_name,
            layer_names=tuple(
                _layer_span(
                    via.start_layer,
                    via.stop_layer,
                    board_metal_layers,
                    layer_order_by_name,
                )
            ),
            hole=padstack.hole if padstack is not None else None,
            signals=padstack.signals if padstack is not None else (),
            source="anf_sidecar_padstack"
            if padstack is not None
            else "anf_sidecar_via",
        )
    return result


def _binary_template_info(
    record: AEDBDefBinaryPadstackInstanceRecord,
    board_metal_layers: list[str],
    padstack: Any | None,
    instance_definition: Any | None,
    layer_order_by_name: dict[str, int],
) -> _TemplateInfo:
    raw_definition = _raw_definition_key(record.raw_definition_index)
    name = (
        (getattr(instance_definition, "padstack_name", None) or "").strip()
        or (getattr(padstack, "name", None) or "").strip()
        or _template_name(raw_definition)
    )
    layer_pad_records = list(getattr(padstack, "layer_pads", []))
    instance_layer_names = _instance_definition_layer_names(
        instance_definition, board_metal_layers, layer_order_by_name
    )
    layer_names = instance_layer_names or tuple(
        layer_name
        for layer_name in (
            getattr(layer_pad, "layer_name", None) for layer_pad in layer_pad_records
        )
        if layer_name
    )
    if not layer_names:
        layer_names = (
            tuple(board_metal_layers)
            if record.name_kind == "via"
            else (board_metal_layers[0] if board_metal_layers else "TOP",)
        )
    layer_pad_shapes = tuple(
        shape
        for shape in (
            _shape_from_padstack_layer_pad(layer_pad) for layer_pad in layer_pad_records
        )
        if shape is not None
    )
    layer_antipad_shapes = tuple(
        _shape_from_padstack_layer_antipad(layer_pad) for layer_pad in layer_pad_records
    )
    pad_shape = (
        layer_pad_shapes[0] if layer_pad_shapes else _shape_from_padstack_name(name)
    )
    if pad_shape is None and record.drill_diameter and record.drill_diameter > 0:
        pad_diameter = record.drill_diameter * 2.0
        pad_shape = _AnfShape(
            "circle",
            "Circle",
            (0, 0, pad_diameter),
            f"BinaryViaPad{pad_diameter}",
        )
    hole = _shape_from_padstack_hole(padstack, name)
    if hole is not None:
        hole = _aedb_standard_barrel_shape(name, pad_shape, hole) or hole
    elif record.drill_diameter and record.drill_diameter > 0:
        hole = _AnfShape(
            "circle",
            "Circle",
            (0, 0, record.drill_diameter),
            f"BinaryDrill{record.drill_diameter}",
        )
    return _TemplateInfo(
        raw_definition=raw_definition,
        name=name,
        layer_names=layer_names,
        hole=hole,
        signals=layer_pad_shapes or ((pad_shape,) if pad_shape is not None else ()),
        source=(
            "aedb_def_binary_instance_drill"
            if hole is not None
            else (
                "aedb_def_binary_padstack_instance_definition"
                if instance_definition is not None and pad_shape is not None
                else (
                    "aedb_def_binary_padstack_name"
                    if pad_shape is not None
                    else "aedb_def_binary_placeholder"
                )
            )
        ),
        antipads=layer_antipad_shapes,
    )


def _instance_definition_layer_names(
    instance_definition: Any | None,
    board_metal_layers: list[str],
    layer_order_by_name: dict[str, int],
) -> tuple[str, ...]:
    if instance_definition is None:
        return ()
    first_layer = getattr(instance_definition, "first_layer_name", None) or ""
    last_layer = getattr(instance_definition, "last_layer_name", None) or ""
    if first_layer and last_layer:
        return tuple(
            _layer_span(
                first_layer,
                last_layer,
                board_metal_layers,
                layer_order_by_name,
            )
        )
    if first_layer:
        return (first_layer,)
    if last_layer:
        return (last_layer,)
    return ()


def _layer_span(
    start_layer: str,
    stop_layer: str,
    board_metal_layers: list[str],
    layer_order_by_name: dict[str, int],
) -> list[str]:
    if not board_metal_layers:
        return [start_layer] if start_layer else []
    start_index = layer_order_by_name.get(start_layer.casefold())
    stop_index = layer_order_by_name.get(stop_layer.casefold())
    if start_index is None or stop_index is None:
        values = [layer for layer in [start_layer, stop_layer] if layer]
        return list(dict.fromkeys(values)) or list(board_metal_layers)
    low = min(start_index, stop_index)
    high = max(start_index, stop_index)
    return board_metal_layers[low : high + 1]


def _anf_via_records(payload: AEDBDefBinaryLayout) -> dict[int, _AnfViaRecord]:
    anf_path = _anf_sidecar_path(payload)
    if anf_path is None:
        return {}
    try:
        text = anf_path.read_text(encoding="utf-8-sig")
    except OSError:
        return {}
    result: dict[int, _AnfViaRecord] = {}
    pattern = re.compile(
        r"via\(\s*(\d+)\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,"
        r"\s*[-+0-9.eE]+\s*,\s*[-+0-9.eE]+\s*,\s*'([^']*)'\s*,"
        r"\s*([-+0-9.eE]+)\s*\)"
    )
    for match in pattern.finditer(text):
        geometry_id = int(match.group(1))
        result[geometry_id] = _AnfViaRecord(
            geometry_id=geometry_id,
            start_layer=match.group(2),
            stop_layer=match.group(3),
            padstack_name=match.group(4),
            rotation=float(match.group(5)),
        )
    return result


def _anf_padstack_definitions(
    payload: AEDBDefBinaryLayout,
) -> dict[str, _AnfPadstackDefinition]:
    anf_path = _anf_sidecar_path(payload)
    if anf_path is None:
        return {}
    try:
        lines = anf_path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return {}

    result: dict[str, _AnfPadstackDefinition] = {}
    in_padstacks = False
    current_name: str | None = None
    current_hole: _AnfShape | None = None
    current_signals: list[_AnfShape] = []

    for raw_line in lines:
        line = raw_line.strip()
        if line == "$begin 'Padstacks'":
            in_padstacks = True
            continue
        if not in_padstacks:
            continue
        if line == "$end 'Padstacks'":
            if current_name is not None:
                result[current_name.casefold()] = _AnfPadstackDefinition(
                    name=current_name,
                    hole=current_hole,
                    signals=tuple(current_signals),
                )
            break
        begin_match = re.match(r"\$begin '([^']+)'", line)
        if begin_match:
            current_name = begin_match.group(1)
            current_hole = None
            current_signals = []
            continue
        if line.startswith("$end '") and current_name is not None:
            result[current_name.casefold()] = _AnfPadstackDefinition(
                name=current_name,
                hole=current_hole,
                signals=tuple(current_signals),
            )
            current_name = None
            current_hole = None
            current_signals = []
            continue
        if current_name is None:
            continue
        if line.startswith("Hole("):
            current_hole = _anf_hole_shape(line)
            continue
        if line.startswith("Signal("):
            signal = _anf_signal_shape(line)
            if signal is not None:
                current_signals.append(signal)
    return result


def _anf_hole_shape(line: str) -> _AnfShape | None:
    match = re.search(r"Hole\(Circle\(([-+0-9.eE]+)\)\)", line)
    if not match:
        return None
    diameter = float(match.group(1))
    if diameter <= 0:
        return None
    return _AnfShape("circle", "Circle", (0, 0, diameter), f"HoleCircle{diameter}")


def _anf_signal_shape(line: str) -> _AnfShape | None:
    match = re.search(r"Signal\('([^']+)'", line)
    if not match:
        return None
    return _anf_named_shape(match.group(1))


def _anf_named_shape(label: str) -> _AnfShape | None:
    circle = re.fullmatch(r"Circle([-+0-9.eE]+)", label)
    if circle:
        diameter = float(circle.group(1))
        if diameter > 0:
            return _AnfShape("circle", "Circle", (0, 0, diameter), label)
    rectangle = re.fullmatch(r"Rectangle([-+0-9.eE]+)x([-+0-9.eE]+)", label)
    if rectangle:
        width = float(rectangle.group(1))
        height = float(rectangle.group(2))
        if width > 0 and height > 0:
            return _AnfShape("rectangle", "Rectangle", (0, 0, width, height), label)
    obround = re.fullmatch(r"Obround([-+0-9.eE]+)x([-+0-9.eE]+)x([-+0-9.eE]+)", label)
    if obround:
        width = float(obround.group(1))
        height = float(obround.group(2))
        radius = float(obround.group(3))
        if width > 0 and height > 0 and radius >= 0:
            return _AnfShape(
                "rounded_rectangle",
                "RoundedRectangle",
                (0, 0, width, height, radius),
                label,
            )
    polygon_values = _anf_shape_polygon_values(label)
    if polygon_values is not None:
        return _AnfShape("polygon", "Polygon", tuple(polygon_values), label)
    return None


def _anf_shape_polygon_values(label: str) -> list[str | float | int] | None:
    if not label.startswith("Polygon"):
        return None
    raw_values = label[len("Polygon") :].split("x")
    numbers: list[float] = []
    for raw_value in raw_values:
        if not raw_value:
            continue
        try:
            numbers.append(float(raw_value))
        except ValueError:
            return None
    if len(numbers) < 6 or len(numbers) % 2:
        return None
    points = [
        f"({numbers[index]},{numbers[index + 1]})"
        for index in range(0, len(numbers), 2)
    ]
    return [len(points), *points, "Y", "Y"]


def _shape_from_padstack_layer_pad(layer_pad: Any) -> _AnfShape | None:
    return _shape_from_padstack_shape_fields(
        getattr(layer_pad, "pad_shape", None),
        getattr(layer_pad, "pad_parameters", []),
        _padstack_layer_pad_label(layer_pad),
    )


def _shape_from_padstack_layer_antipad(layer_pad: Any) -> _AnfShape | None:
    return _shape_from_padstack_shape_fields(
        getattr(layer_pad, "antipad_shape", None),
        getattr(layer_pad, "antipad_parameters", []),
        _padstack_layer_antipad_label(layer_pad),
    )


def _shape_from_padstack_hole(padstack: Any | None, padstack_name: str) -> _AnfShape | None:
    if padstack is None:
        return None
    return _shape_from_padstack_shape_fields(
        getattr(padstack, "hole_shape", None),
        getattr(padstack, "hole_parameters", []),
        f"{padstack_name}:hole",
    )


def _aedb_standard_barrel_shape(
    padstack_name: str, pad_shape: _AnfShape | None, hole_shape: _AnfShape
) -> _AnfShape | None:
    if hole_shape.auroradb_type.casefold() != "circle":
        return None
    pad_diameter = _circle_shape_diameter(pad_shape)
    drill_diameter = _circle_shape_diameter(hole_shape)
    if pad_diameter is None or drill_diameter is None:
        return None
    if pad_diameter < 0.0025 or drill_diameter < 0.001:
        return None

    # AEDT's AuroraDB export writes large C<pad>-<drill>T plated mounting
    # barrels as a vertical RectCutCorner even when the text hle() record says
    # Circle. Keep the rule constrained to large plated C* padstack names.
    if not re.match(r"^C\d+(?:_\d+)?-\d+(?:_\d+)?T$", padstack_name, re.I):
        return None
    width = round((pad_diameter + drill_diameter) * 0.5 / 0.000254) * 0.000254
    if width <= 0 or width >= pad_diameter:
        return None
    return _AnfShape(
        "rectcutcorner_y",
        "RectCutCorner",
        (0, 0, width, pad_diameter, width * 0.5, "N", "Y", "Y", "Y", "Y"),
        f"{padstack_name}:standard_barrel",
    )


def _shape_from_padstack_shape_fields(
    shape_value: Any,
    raw_parameters: Any,
    label: str,
) -> _AnfShape | None:
    shape = (shape_value or "").strip().casefold()
    if shape in {"", "no", "none"}:
        return None
    parameters = [
        value
        for value in (
            _source_dimension_to_m(parameter) for parameter in list(raw_parameters or [])
        )
        if value is not None
    ]
    if shape in {"cir", "circle"} and parameters:
        return _AnfShape(
            "circle",
            "Circle",
            (0, 0, parameters[0]),
            label,
        )
    if shape in {"rct", "rect", "rectangle"} and len(parameters) >= 2:
        return _AnfShape(
            "rectangle",
            "Rectangle",
            (0, 0, parameters[0], parameters[1]),
            label,
        )
    if shape in {"sq", "square"} and parameters:
        return _AnfShape(
            "rectangle",
            "Rectangle",
            (0, 0, parameters[0], parameters[0]),
            label,
        )
    if shape in {"obl", "obround", "ov", "oval", "roundrect"} and len(parameters) >= 2:
        radius = (
            parameters[2]
            if len(parameters) >= 3
            else min(parameters[0], parameters[1]) * 0.5
        )
        return _AnfShape(
            "rounded_rectangle",
            "RoundedRectangle",
            (0, 0, parameters[0], parameters[1], radius),
            label,
        )
    return None


def _padstack_layer_pad_label(layer_pad: Any) -> str:
    layer = getattr(layer_pad, "layer_name", None) or "layer"
    shape = getattr(layer_pad, "pad_shape", None) or "pad"
    values = "x".join(str(value) for value in getattr(layer_pad, "pad_parameters", []))
    return f"{layer}:{shape}:{values}"


def _padstack_layer_antipad_label(layer_pad: Any) -> str:
    layer = getattr(layer_pad, "layer_name", None) or "layer"
    shape = getattr(layer_pad, "antipad_shape", None) or "antipad"
    values = "x".join(
        str(value) for value in getattr(layer_pad, "antipad_parameters", [])
    )
    return f"{layer}:antipad:{shape}:{values}"


def _source_dimension_to_m(value: object) -> float | None:
    text = str(value).strip().strip("'\"")
    match = re.fullmatch(r"([-+0-9.eE]+)\s*([a-zA-Z]+)", text)
    if not match:
        return None
    number = _parse_float(match.group(1))
    if number is None:
        return None
    unit = match.group(2).casefold()
    if unit == "m":
        return number
    if unit == "mm":
        return number * 0.001
    if unit == "um":
        return number * 0.000001
    if unit == "mil":
        return number * 0.0000254
    return None


def _shape_from_padstack_name(name: str) -> _AnfShape | None:
    text = name.strip()
    if not text:
        return None

    rectangle = _rectangle_shape_from_name(text)
    if rectangle is not None:
        return rectangle

    obround = _obround_shape_from_name(text)
    if obround is not None:
        return obround

    diameter = _circle_diameter_from_name(text)
    if diameter is not None and diameter > 0:
        return _AnfShape("circle", "Circle", (0, 0, diameter), text)
    return None


def _rectangle_shape_from_name(name: str) -> _AnfShape | None:
    special = _special_rectangle_shape_from_name(name)
    if special is not None:
        return special

    patterns = [
        r"R(\d+(?:_\d+)?)X(\d+(?:_\d+)?)",
        r"SMD(\d+(?:_\d+)?)REC(?:T)?(\d+(?:_\d+)?)",
        r"SMDREC[_-]?(\d+(?:_\d+)?)X?(\d+(?:_\d+)?)",
        r"REC(?:T)?[_-]?(\d+(?:_\d+)?)X?(\d+(?:_\d+)?)",
        r"PAD(?:_SMD)?[_-]?(\d+(?:_\d+)?)X(\d+(?:_\d+)?)",
        r"S_RCT[_-](\d+(?:[-_]\d+)?)_X_(\d+(?:[-_]\d+)?)",
        r"(\d+(?:P\d+)?)X(\d+(?:P\d+)?)(?:SMD|$)",
        r"(\d+(?:_\d+)?)X(\d+(?:_\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, name, flags=re.IGNORECASE)
        if not match:
            continue
        width = _named_dimension_to_m(match.group(1), name)
        height = _named_dimension_to_m(match.group(2), name)
        if width and height:
            return _AnfShape("rectangle", "Rectangle", (0, 0, width, height), name)

    compact = re.search(r"RECT(\d{2,3})(\d{2,3})$", name, flags=re.IGNORECASE)
    if compact:
        width = _named_dimension_to_m(compact.group(1), name)
        height = _named_dimension_to_m(compact.group(2), name)
        if width and height:
            return _AnfShape("rectangle", "Rectangle", (0, 0, width, height), name)

    square = re.search(r"(?:^|[_-])(?:S|SQ|SQR|SMDSQR)[_-]?(\d+(?:_\d+)?)", name, re.I)
    if square:
        side = _named_dimension_to_m(square.group(1), name)
        if side:
            return _AnfShape("rectangle", "Rectangle", (0, 0, side, side), name)
    return None


def _special_rectangle_shape_from_name(name: str) -> _AnfShape | None:
    mm_decimal = re.search(r"(\d+)MM(\d+)X(\d+)MM(\d+)", name, flags=re.IGNORECASE)
    if mm_decimal:
        width = float(f"{mm_decimal.group(1)}.{mm_decimal.group(2)}") * 0.001
        height = float(f"{mm_decimal.group(3)}.{mm_decimal.group(4)}") * 0.001
        return _AnfShape("rectangle", "Rectangle", (0, 0, width, height), name)

    compact_metric_patterns = [
        r"^(\d{2,3})SMD(\d{2,3})(?:_|$)",
        r"^PAD_SMD[-_](\d{2,3})X(\d{2,3})(?:$|[^0-9])",
        r"^SM_(\d{3})X(\d{3})(?:_|$)",
        r"^R(\d{2,3})[_-](\d{2,3})$",
    ]
    for pattern in compact_metric_patterns:
        match = re.search(pattern, name, flags=re.IGNORECASE)
        if not match:
            continue
        width = _compact_metric_hundredth_to_m(match.group(1))
        height = _compact_metric_hundredth_to_m(match.group(2))
        if width and height:
            return _AnfShape("rectangle", "Rectangle", (0, 0, width, height), name)
    return None


def _compact_metric_hundredth_to_m(value: str) -> float | None:
    try:
        number = int(value)
    except ValueError:
        return None
    if number <= 0:
        return None
    return number * 0.00001


def _obround_shape_from_name(name: str) -> _AnfShape | None:
    patterns = [
        r"OBL[_-]?(\d+(?:_\d+)?)[_-](\d+(?:_\d+)?)",
        r"S_OBL[_-](\d+(?:[-_]\d+)?)_X_(\d+(?:[-_]\d+)?)",
        r"OX(\d+(?:_\d+)?)Y(\d+(?:_\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, name, flags=re.IGNORECASE)
        if not match:
            continue
        width = _named_dimension_to_m(match.group(1), name)
        height = _named_dimension_to_m(match.group(2), name)
        if width and height:
            return _AnfShape(
                "rounded_rectangle",
                "RoundedRectangle",
                (0, 0, width, height, min(width, height) * 0.5),
                name,
            )
    return None


def _circle_diameter_from_name(name: str) -> float | None:
    patterns = [
        r"^C(\d+(?:_\d+)?)",
        r"^BGA(\d+(?:P\d+)?)",
        r"CIR[_-]?(\d+(?:_\d+)?)",
        r"PAD(\d+(?:_\d+)?)CIR",
        r"SMD[_-]?(\d+(?:_\d+)?)CIR",
        r"SMD_(\d+(?:_\d+)?)$",
        r"VIA[_-]?(\d+(?:_\d+)?)D",
        r"DIA(\d+(?:_\d+)?)(?:MM)?",
        r"PAD_MTG(\d+(?:_\d+)?)",
        r"HOLE(\d+(?:_\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, name, flags=re.IGNORECASE)
        if match:
            return _named_dimension_to_m(match.group(1), name)
    return None


def _named_dimension_to_m(value: str, context: str) -> float | None:
    original = value
    text = value.replace("P", ".").replace("p", ".")
    decimal_hint = "_" in text or "P" in original.upper()
    text = text.replace("_", ".")
    if re.fullmatch(r"\d+-\d+", text):
        decimal_hint = True
        text = text.replace("-", ".")
    try:
        number = float(text)
    except ValueError:
        return None
    if number <= 0:
        return None
    if "MM" in context.upper() or (decimal_hint and number < 20):
        return number * 0.001
    return number * 0.0000254


def _component_pin_records(
    records: list[AEDBDefBinaryPadstackInstanceRecord],
) -> list[_ComponentPinRecord]:
    result: list[_ComponentPinRecord] = []
    for record in records:
        if record.name_kind != "component_pin":
            continue
        refdes, pin_name = _component_pin_name_parts(record)
        if not refdes:
            continue
        result.append(
            _ComponentPinRecord(record=record, refdes=refdes, pin_name=pin_name)
        )
    return result


def _component_pin_name_parts(
    record: AEDBDefBinaryPadstackInstanceRecord,
) -> tuple[str, str]:
    name = record.name or ""
    if "-" in name:
        refdes, suffix = name.split("-", 1)
    else:
        refdes, suffix = name, ""
    pin_name = record.secondary_name or suffix or name
    return refdes, pin_name


def _pins_by_refdes(
    records: list[_ComponentPinRecord],
) -> dict[str, list[_ComponentPinRecord]]:
    result: dict[str, list[_ComponentPinRecord]] = defaultdict(list)
    for record in records:
        result[record.refdes].append(record)
    for values in result.values():
        values.sort(key=lambda item: (item.pin_name.casefold(), item.record.offset))
    return dict(result)


def _component_from_placement(
    placement: AEDBDefBinaryComponentPlacement,
    index: int,
    pin_records: list[_ComponentPinRecord],
    footprints_by_id: dict[str, SemanticFootprint],
    template_infos: dict[str, _TemplateInfo],
) -> SemanticComponent:
    footprint_name = _placement_footprint_name(placement)
    footprint_id = _ensure_footprint(footprints_by_id, footprint_name, placement, index)
    location = _placement_location(placement) or _pin_record_centroid(pin_records)
    layer_name, side = _component_layer_from_pin_records(pin_records, template_infos)
    attributes = {
        key: value
        for key, value in {
            "component_class": placement.component_class,
            "device_type": placement.device_type,
            "package": placement.package,
            "part_number": placement.part_number,
        }.items()
        if value not in {None, ""}
    }
    return SemanticComponent(
        id=semantic_id("component", placement.refdes, index),
        refdes=placement.refdes,
        name=placement.refdes,
        part_name=_placement_part_name(placement),
        package_name=footprint_name,
        footprint_id=footprint_id,
        layer_name=layer_name,
        side=side,
        value=placement.value,
        location=point_from_pair(location),
        rotation=_component_rotation_from_pin_records(pin_records),
        attributes=attributes,
        source=source_ref(
            "aedb", f"domain.component_placements[{index}]", placement.refdes
        ),
    )


def _synthetic_component_from_pin_records(
    refdes: str,
    pin_records: list[_ComponentPinRecord],
    index: int,
    footprints_by_id: dict[str, SemanticFootprint],
    template_infos: dict[str, _TemplateInfo],
) -> SemanticComponent:
    footprint_name = f"DEF_BINARY_{refdes}"
    footprint_id = _ensure_footprint(footprints_by_id, footprint_name, None, index)
    layer_name, side = _component_layer_from_pin_records(pin_records, template_infos)
    return SemanticComponent(
        id=semantic_id("component", refdes, index),
        refdes=refdes,
        name=refdes,
        part_name=footprint_name,
        package_name=footprint_name,
        footprint_id=footprint_id,
        layer_name=layer_name,
        side=side,
        location=point_from_pair(_pin_record_centroid(pin_records)),
        rotation=_component_rotation_from_pin_records(pin_records),
        source=source_ref("aedb", "domain.binary_padstack_instance_records", refdes),
    )


def _component_layer_from_pin_records(
    pin_records: list[_ComponentPinRecord],
    template_infos: dict[str, _TemplateInfo],
) -> tuple[str, str]:
    layer_counts: dict[str, int] = defaultdict(int)
    for pin_record in pin_records:
        layer_name = _record_primary_layer_name(pin_record.record, template_infos)
        if layer_name:
            layer_counts[layer_name.casefold()] += 1
    if layer_counts.get("bottom", 0) > layer_counts.get("top", 0):
        return "BOTTOM", "bottom"
    return "TOP", "top"


def _ensure_footprint(
    footprints_by_id: dict[str, SemanticFootprint],
    footprint_name: str,
    placement: AEDBDefBinaryComponentPlacement | None,
    index: int,
) -> str:
    footprint_id = semantic_id("footprint", footprint_name)
    if footprint_id not in footprints_by_id:
        attributes: dict[str, str] = {}
        if placement is not None:
            attributes = {
                key: value
                for key, value in {
                    "device_type": placement.device_type,
                    "package": placement.package,
                    "part_number": placement.part_number,
                }.items()
                if value not in {None, ""}
            }
        footprints_by_id[footprint_id] = SemanticFootprint(
            id=footprint_id,
            name=footprint_name,
            part_name=footprint_name,
            attributes=attributes,
            source=source_ref(
                "aedb", f"domain.component_placements[{index}].package", footprint_name
            ),
        )
    return footprint_id


def _placement_footprint_name(placement: AEDBDefBinaryComponentPlacement) -> str:
    return (
        placement.package
        or placement.device_type
        or placement.part_number
        or placement.value
        or placement.refdes
    )


def _placement_part_name(placement: AEDBDefBinaryComponentPlacement) -> str:
    return (
        placement.device_type
        or placement.package
        or placement.part_number
        or placement.value
        or placement.refdes
    )


def _placement_location(
    placement: AEDBDefBinaryComponentPlacement,
) -> tuple[float, float] | None:
    box = placement.symbol_box
    if box is None:
        return None
    return ((box.x_min + box.x_max) * 0.5, (box.y_min + box.y_max) * 0.5)


def _pin_record_centroid(
    records: list[_ComponentPinRecord],
) -> tuple[float, float] | None:
    if not records:
        return None
    return (
        sum(record.record.x for record in records) / len(records),
        sum(record.record.y for record in records) / len(records),
    )


def _component_rotation_from_pin_records(
    records: list[_ComponentPinRecord],
) -> float:
    for pin_record in sorted(records, key=lambda item: _pin_sort_key(item.pin_name)):
        rotation = pin_record.record.rotation
        if math.isfinite(rotation):
            return float(rotation)
    return 0.0


def _pin_sort_key(value: str) -> tuple[int, int | str]:
    text = str(value)
    if text.isdigit():
        return (0, int(text))
    return (1, text.casefold())


def _add_component_pins_and_pads(
    component: SemanticComponent,
    pin_records: list[_ComponentPinRecord],
    pins: list[SemanticPin],
    pads: list[SemanticPad],
    nets_by_id: dict[str, SemanticNet],
    via_template_ids_by_raw_definition: dict[str, str],
    via_template_names_by_raw_definition: dict[str, str],
    pad_shape_ids_by_raw_definition: dict[str, str],
    template_infos: dict[str, _TemplateInfo],
    seen_members: dict[str, set[str]],
) -> None:
    seen_pin_names: set[str] = set()
    for index, pin_record in enumerate(pin_records):
        record = pin_record.record
        pin_name = pin_record.pin_name
        add_pin = not _is_no_net_unnamed_component_pin(pin_record)
        if pin_name.casefold() in seen_pin_names:
            pin_name = f"{pin_name}_{index + 1}"
        seen_pin_names.add(pin_name.casefold())
        net_id = _ensure_net(
            nets_by_id,
            record.net_name or _AEDB_NO_NET_NAME,
            "domain.binary_padstack_instance_records",
            record.net_index,
        )
        pin_id = semantic_id(
            "pin", f"{component.id}:{pin_name}", f"{component.id}:{index}"
        )
        pad_id = semantic_id(
            "pad", f"{component.id}:{pin_name}", f"{component.id}:{index}"
        )
        raw_definition = _raw_definition_key(record.raw_definition_index)
        template_name = via_template_names_by_raw_definition.get(
            raw_definition, _template_name(raw_definition)
        )
        template_id = via_template_ids_by_raw_definition.get(raw_definition)
        layer_name = _record_primary_layer_name(record, template_infos)
        pad_shape_id = pad_shape_ids_by_raw_definition.get(raw_definition)
        pad = SemanticPad(
            id=pad_id,
            name=pin_name,
            footprint_id=component.footprint_id,
            component_id=component.id,
            pin_id=pin_id if add_pin else None,
            net_id=net_id,
            layer_name=layer_name,
            position=point_from_pair((record.x, record.y)),
            padstack_definition=template_name if template_id is not None else None,
            geometry=SemanticPadGeometry(
                source="aedb_def_binary_padstack_instance",
                rotation=record.rotation,
                shape_id=pad_shape_id,
                package_pin=pin_record.pin_name,
                suppress_via_export=True,
                suppress_shape_export=bool(
                    record.net_name
                    and record.drill_diameter is not None
                    and record.drill_diameter > 0
                ),
            ),
            source=source_ref(
                "aedb", "domain.binary_padstack_instance_records", record.geometry_id
            ),
        )
        pads.append(pad)
        if add_pin:
            pin = SemanticPin(
                id=pin_id,
                name=pin_name,
                component_id=component.id,
                net_id=net_id,
                layer_name=layer_name,
                position=point_from_pair((record.x, record.y)),
                source=source_ref(
                    "aedb",
                    "domain.binary_padstack_instance_records",
                    record.geometry_id,
                ),
            )
            pins.append(pin)
            _append_unique(
                seen_members,
                f"component:{component.id}:pins",
                component.pin_ids,
                pin.id,
            )
            if net_id in nets_by_id:
                _append_unique(
                    seen_members,
                    f"net:{net_id}:pins",
                    nets_by_id[net_id].pin_ids,
                    pin.id,
                )
        _append_unique(
            seen_members, f"component:{component.id}:pads", component.pad_ids, pad.id
        )
        if net_id in nets_by_id:
            _append_unique(
                seen_members, f"net:{net_id}:pads", nets_by_id[net_id].pad_ids, pad.id
            )


def _is_no_net_unnamed_component_pin(pin_record: _ComponentPinRecord) -> bool:
    return not pin_record.record.net_name and pin_record.pin_name.startswith("UNNAMED_")


def _add_standalone_unnamed_pads(
    payload: AEDBDefBinaryLayout,
    pads: list[SemanticPad],
    nets_by_id: dict[str, SemanticNet],
    via_template_ids_by_raw_definition: dict[str, str],
    via_template_names_by_raw_definition: dict[str, str],
    pad_shape_ids_by_raw_definition: dict[str, str],
    template_infos: dict[str, _TemplateInfo],
    board_metal_layers: list[str],
    seen_members: dict[str, set[str]],
) -> None:
    net_id = _ensure_net(
        nets_by_id,
        _AEDB_NO_NET_NAME,
        "domain.binary_padstack_instance_records",
        None,
    )
    for index, record in enumerate(payload.domain.binary_padstack_instance_records):
        if record.name_kind != "unnamed" or record.net_name:
            continue
        layer_names = _record_layer_names(record, template_infos, board_metal_layers)
        if _via_taxonomy(layer_names, board_metal_layers).via_type != "single_layer":
            continue
        raw_definition = _raw_definition_key(record.raw_definition_index)
        template_id = via_template_ids_by_raw_definition.get(raw_definition)
        template_name = via_template_names_by_raw_definition.get(
            raw_definition, _template_name(raw_definition)
        )
        pad_shape_id = pad_shape_ids_by_raw_definition.get(raw_definition)
        pad = SemanticPad(
            id=semantic_id("pad", f"standalone:{record.geometry_id}", index),
            name=record.secondary_name or record.name,
            net_id=net_id,
            layer_name=_record_primary_layer_name(record, template_infos),
            position=point_from_pair((record.x, record.y)),
            padstack_definition=template_name if template_id is not None else None,
            geometry=SemanticPadGeometry(
                source="aedb_def_binary_unnamed_padstack_instance",
                rotation=record.rotation,
                shape_id=pad_shape_id,
                package_pin=record.secondary_name or record.name,
                suppress_via_export=True,
            ),
            source=source_ref(
                "aedb", "domain.binary_padstack_instance_records", record.geometry_id
            ),
        )
        pads.append(pad)
        if net_id in nets_by_id:
            _append_unique(
                seen_members,
                f"net:{net_id}:pads",
                nets_by_id[net_id].pad_ids,
                pad.id,
            )


def _append_unique(
    seen_members: dict[str, set[str]],
    owner_key: str,
    values: list[str],
    value: str | None,
) -> None:
    if not value:
        return
    seen = seen_members[owner_key]
    if value in seen:
        return
    seen.add(value)
    values.append(value)


def _vias(
    payload: AEDBDefBinaryLayout,
    nets_by_id: dict[str, SemanticNet],
    via_template_ids_by_raw_definition: dict[str, str],
    via_template_names_by_raw_definition: dict[str, str],
    template_infos: dict[str, _TemplateInfo],
    board_metal_layers: list[str],
) -> list[SemanticVia]:
    vias: list[SemanticVia] = []
    for index, record in enumerate(payload.domain.binary_padstack_instance_records):
        raw_definition = _raw_definition_key(record.raw_definition_index)
        template_name = via_template_names_by_raw_definition.get(
            raw_definition, _template_name(raw_definition)
        )
        template_id = via_template_ids_by_raw_definition.get(raw_definition)
        if template_id is None:
            continue
        net_name = record.net_name or _AEDB_NO_NET_NAME
        net_id = _ensure_net(
            nets_by_id,
            net_name,
            "domain.binary_padstack_instance_records",
            record.net_index,
        )
        layer_names = _record_layer_names(record, template_infos, board_metal_layers)
        taxonomy = _via_taxonomy(layer_names, board_metal_layers)
        vias.append(
            SemanticVia(
                id=semantic_id("via", record.geometry_id, index),
                name=record.name,
                template_id=template_id,
                net_id=net_id,
                layer_names=layer_names,
                position=point_from_pair((record.x, record.y)),
                geometry=SemanticViaGeometry(
                    rotation=record.rotation,
                    template_refined_from=template_name,
                    via_type=taxonomy.via_type,
                    via_usage=_via_usage(record),
                    instance_kind=record.name_kind,
                    raw_definition_index=record.raw_definition_index,
                    raw_owner_index=record.raw_owner_index,
                    padstack_name=template_name,
                    drill_diameter=record.drill_diameter,
                    start_layer=taxonomy.start_layer,
                    stop_layer=taxonomy.stop_layer,
                    start_layer_index=taxonomy.start_layer_index,
                    stop_layer_index=taxonomy.stop_layer_index,
                    layer_span_count=taxonomy.layer_span_count,
                    spans_full_stack=taxonomy.spans_full_stack,
                ),
                source=source_ref(
                    "aedb",
                    f"domain.binary_padstack_instance_records[{index}]",
                    record.geometry_id,
                ),
            )
        )
    return vias


def _record_layer_names(
    record: AEDBDefBinaryPadstackInstanceRecord,
    template_infos: dict[str, _TemplateInfo],
    board_metal_layers: list[str],
) -> list[str]:
    raw_definition = _raw_definition_key(record.raw_definition_index)
    info = template_infos.get(raw_definition)
    if info is not None and info.layer_names:
        return list(info.layer_names)
    if record.name_kind != "via":
        return [_record_primary_layer_name(record, template_infos)]
    return list(board_metal_layers)


def _via_taxonomy(
    layer_names: list[str] | tuple[str, ...],
    board_metal_layers: list[str],
) -> _ViaTaxonomy:
    normalized_layers = [name for name in dict.fromkeys(layer_names) if name]
    if not normalized_layers:
        return _ViaTaxonomy("unknown", None, None, None, None, 0, False)

    layer_order = {
        layer_name.casefold(): index
        for index, layer_name in enumerate(board_metal_layers)
    }
    start_layer = normalized_layers[0]
    stop_layer = normalized_layers[-1]
    start_index = layer_order.get(start_layer.casefold())
    stop_index = layer_order.get(stop_layer.casefold())
    layer_span_count = len(normalized_layers)
    spans_full_stack = (
        start_index == 0
        and stop_index == len(board_metal_layers) - 1
        and len(board_metal_layers) > 1
    )

    if layer_span_count <= 1:
        via_type = "single_layer"
    elif start_index is None or stop_index is None or not board_metal_layers:
        via_type = "unknown"
    elif spans_full_stack:
        via_type = "through"
    elif start_index in {0, len(board_metal_layers) - 1} or stop_index in {
        0,
        len(board_metal_layers) - 1,
    }:
        via_type = "blind"
    else:
        via_type = "buried"

    return _ViaTaxonomy(
        via_type,
        start_layer,
        stop_layer,
        start_index,
        stop_index,
        layer_span_count,
        spans_full_stack,
    )


def _via_usage(record: AEDBDefBinaryPadstackInstanceRecord) -> str:
    if record.name_kind == "via":
        return "routing_via"
    if record.name_kind == "component_pin":
        return "component_pin"
    if record.name_kind == "unnamed":
        return "unnamed_padstack_instance"
    return "named_padstack_instance"


def _record_primary_layer_name(
    record: AEDBDefBinaryPadstackInstanceRecord,
    template_infos: dict[str, _TemplateInfo],
) -> str:
    raw_definition = _raw_definition_key(record.raw_definition_index)
    info = template_infos.get(raw_definition)
    if info is not None and info.layer_names:
        return info.layer_names[0]
    return "TOP"


def _path_primitives(
    payload: AEDBDefBinaryLayout,
    nets_by_id: dict[str, SemanticNet],
) -> list[SemanticPrimitive]:
    primitives: list[SemanticPrimitive] = []
    for index, record in enumerate(payload.domain.binary_path_records):
        net_id = _ensure_net(
            nets_by_id,
            record.net_name or _AEDB_NO_NET_NAME,
            "domain.binary_path_records",
            record.net_index,
        )
        center_line = _center_line(record.items)
        if len(center_line) < 2:
            continue
        primitives.append(
            SemanticPrimitive(
                id=semantic_id("primitive", record.geometry_id, f"path_{index}"),
                kind="trace",
                layer_name=record.layer_name,
                net_id=net_id,
                geometry=SemanticPrimitiveGeometry(
                    record_kind="binary_path",
                    feature_index=index,
                    feature_id=record.geometry_id,
                    width=record.width,
                    center_line=center_line,
                ),
                source=source_ref(
                    "aedb", f"domain.binary_path_records[{index}]", record.geometry_id
                ),
            )
        )
    return primitives


def _anf_polygon_primitives(
    payload: AEDBDefBinaryLayout,
    nets_by_id: dict[str, SemanticNet],
) -> list[SemanticPrimitive]:
    anf_path = _anf_sidecar_path(payload)
    if anf_path is None:
        return []
    try:
        lines = anf_path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return []

    primitives: list[SemanticPrimitive] = []
    current_net: str | None = None
    in_layout_net = False
    index = 0
    line_index = 0
    while line_index < len(lines):
        line = lines[line_index].strip()
        if line == "$begin 'LayoutNet'":
            in_layout_net = True
            current_net = None
            line_index += 1
            continue
        if line == "$end 'LayoutNet'":
            in_layout_net = False
            current_net = None
            line_index += 1
            continue
        if in_layout_net and line.startswith("Name="):
            current_net = _anf_quoted_value(line)
            if current_net:
                _ensure_net(nets_by_id, current_net, f"{anf_path.name}:LayoutNet")
            line_index += 1
            continue
        if in_layout_net and line == "$begin 'PolygonWithVoids'":
            block_lines: list[str] = []
            depth = 1
            line_index += 1
            while line_index < len(lines) and depth > 0:
                block_line = lines[line_index].strip()
                if block_line == "$begin 'PolygonWithVoids'":
                    depth += 1
                elif block_line == "$end 'PolygonWithVoids'":
                    depth -= 1
                    if depth == 0:
                        break
                block_lines.append(block_line)
                line_index += 1
            primitive = _polygon_with_voids_primitive(
                block_lines,
                current_net,
                nets_by_id,
                index,
                source=f"{anf_path.name}:PolygonWithVoids",
            )
            if primitive is not None:
                primitives.append(primitive)
                index += 1
            line_index += 1
            continue
        if in_layout_net and "Graphics('" in line and "Polygon(" in line:
            primitive = _graphics_polygon_primitive(
                line,
                current_net,
                nets_by_id,
                index,
                source=f"{anf_path.name}:GraphicsPolygon",
            )
            if primitive is not None:
                primitives.append(primitive)
                index += 1
        line_index += 1
    return primitives


def _anf_sidecar_path(payload: AEDBDefBinaryLayout) -> Path | None:
    source = payload.metadata.source
    if not source:
        return None
    source_path = Path(source)
    candidates = [source_path.with_suffix(".anf")]
    if not source_path.is_absolute():
        candidates.append(Path.cwd() / source_path.with_suffix(".anf"))
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _anf_quoted_value(line: str) -> str | None:
    match = re.search(r"=\s*'([^']*)'", line)
    return match.group(1) if match else None


def _polygon_with_voids_primitive(
    lines: list[str],
    net_name: str | None,
    nets_by_id: dict[str, SemanticNet],
    index: int,
    *,
    source: str,
) -> SemanticPrimitive | None:
    layer_name: str | None = None
    outer_polygon: str | None = None
    void_polygons: list[str] = []
    in_voids = False
    for line in lines:
        if line.startswith("Layer="):
            layer_name = _anf_quoted_value(line)
            continue
        if line == "$begin 'Voids'":
            in_voids = True
            continue
        if line == "$end 'Voids'":
            in_voids = False
            continue
        if line.startswith("Polygon("):
            if in_voids:
                void_polygons.append(line)
            elif outer_polygon is None:
                outer_polygon = line
    if layer_name is None or outer_polygon is None:
        return None
    raw_points = _anf_polygon_raw_points(outer_polygon)
    if len(raw_points) < 3:
        return None
    voids = [
        {"raw_points": points}
        for points in (_anf_polygon_raw_points(polygon) for polygon in void_polygons)
        if len(points) >= 3
    ]
    return _anf_polygon_primitive(
        layer_name,
        net_name,
        nets_by_id,
        index,
        raw_points,
        voids,
        source=source,
        raw_id=_anf_polygon_id(outer_polygon),
    )


def _graphics_polygon_primitive(
    line: str,
    net_name: str | None,
    nets_by_id: dict[str, SemanticNet],
    index: int,
    *,
    source: str,
) -> SemanticPrimitive | None:
    match = re.search(r"Graphics\('([^']+)'\s*,\s*(Polygon\(.*\))\)\s*$", line)
    if not match:
        return None
    layer_name = match.group(1)
    polygon = match.group(2)
    raw_points = _anf_polygon_raw_points(polygon)
    if len(raw_points) < 3:
        return None
    return _anf_polygon_primitive(
        layer_name,
        net_name,
        nets_by_id,
        index,
        raw_points,
        [],
        source=source,
        raw_id=_anf_polygon_id(polygon),
    )


def _anf_polygon_primitive(
    layer_name: str,
    net_name: str | None,
    nets_by_id: dict[str, SemanticNet],
    index: int,
    raw_points: list[list[float | int | None]],
    voids: list[dict[str, Any]],
    *,
    source: str,
    raw_id: str | None,
) -> SemanticPrimitive:
    net_id = _ensure_net(nets_by_id, net_name or _AEDB_NO_NET_NAME, source, raw_id)
    return SemanticPrimitive(
        id=semantic_id("primitive", f"anf_polygon_{raw_id}", f"anf_polygon_{index}"),
        kind="polygon",
        layer_name=layer_name,
        net_id=net_id,
        geometry=SemanticPrimitiveGeometry(
            record_kind="anf_polygon_sidecar",
            feature_index=index,
            feature_id=raw_id,
            raw_points=raw_points,
            has_voids=bool(voids),
            voids=voids,  # type: ignore[arg-type]
        ),
        source=source_ref("aedb", source, raw_id),
    )


def _anf_polygon_id(polygon_text: str) -> str | None:
    match = re.match(r"Polygon\(([^,]+),", polygon_text)
    return match.group(1).strip() if match else None


def _anf_polygon_raw_points(polygon_text: str) -> list[list[float | int | None]]:
    values: list[list[float | int | None]] = []
    for match in re.finditer(r"(vertex|arc)\(([^)]*)\)", polygon_text):
        kind = match.group(1)
        parts = [part.strip() for part in match.group(2).split(",")]
        if kind == "vertex" and len(parts) >= 2:
            x = _parse_float(parts[0])
            y = _parse_float(parts[1])
            if x is not None and y is not None:
                values.append([x, y])
        elif kind == "arc" and parts:
            height = _parse_float(parts[0])
            if height is not None:
                values.append([height, _ARC_HEIGHT_SENTINEL])
    return values


def _binary_polygon_primitives(
    payload: AEDBDefBinaryLayout,
    nets_by_id: dict[str, SemanticNet],
    template_infos: dict[str, _TemplateInfo],
    board_metal_layers: list[str],
) -> list[SemanticPrimitive]:
    records = sorted(
        payload.domain.binary_polygon_records,
        key=lambda record: (record.offset, record.geometry_id or -1),
    )
    voids_by_parent: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if not record.is_void or record.parent_geometry_id is None:
            continue
        raw_points = _binary_polygon_raw_points(record.items)
        if len(raw_points) < 3:
            continue
        point_pairs = _binary_polygon_point_pairs(raw_points)
        voids_by_parent[record.parent_geometry_id].append(
            {
                "raw_points": raw_points,
                "bbox": _point_bbox(point_pairs),
                "area": abs(_shoelace_points(point_pairs)),
                "source_contour_index": record.geometry_id,
            }
        )

    net_names_by_index = {
        net.index: net.name
        for net in payload.domain.layout_nets
        if net.index is not None and net.name
    }
    known_net_names = {net.name.casefold(): net.name for net in nets_by_id.values()}
    synthetic_voids_by_parent = _synthetic_padstack_clearance_voids(
        payload,
        records,
        voids_by_parent,
        net_names_by_index,
        known_net_names,
        template_infos,
        board_metal_layers,
    )

    primitives: list[SemanticPrimitive] = []
    for index, record in enumerate(record for record in records if not record.is_void):
        raw_points = _binary_polygon_raw_points(record.items)
        if len(raw_points) < 3:
            continue
        point_pairs = _binary_polygon_point_pairs(raw_points)
        if len(point_pairs) < 3:
            continue
        raw_id = record.geometry_id if record.geometry_id is not None else record.offset
        net_name = _binary_polygon_net_name(record, net_names_by_index, known_net_names)
        net_id = _ensure_net(
            nets_by_id,
            net_name,
            "domain.binary_polygon_records",
            record.net_index if record.net_index is not None else raw_id,
        )
        voids = [
            *voids_by_parent.get(raw_id, []),
            *synthetic_voids_by_parent.get(raw_id, []),
        ]
        primitives.append(
            SemanticPrimitive(
                id=semantic_id("primitive", raw_id, f"binary_polygon_{index}"),
                kind="polygon",
                layer_name=record.layer_name,
                net_id=net_id,
                geometry=SemanticPrimitiveGeometry(
                    record_kind="binary_polygon",
                    feature_index=index,
                    feature_id=raw_id,
                    raw_points=raw_points,
                    has_voids=bool(voids),
                    voids=voids,  # type: ignore[arg-type]
                    void_ids=[
                        void["source_contour_index"]
                        for void in voids
                        if void.get("source_contour_index") is not None
                    ],
                    bbox=_point_bbox(point_pairs),
                    area=abs(_shoelace_points(point_pairs)),
                ),
                source=source_ref(
                    "aedb", "domain.binary_polygon_records", record.geometry_id
                ),
            )
        )
    return primitives


def _synthetic_padstack_clearance_voids(
    payload: AEDBDefBinaryLayout,
    polygon_records: list[AEDBDefBinaryPolygonRecord],
    native_voids_by_parent: dict[int, list[dict[str, Any]]],
    net_names_by_index: dict[int, str],
    known_net_names: dict[str, str],
    template_infos: dict[str, _TemplateInfo],
    board_metal_layers: list[str],
) -> dict[int, list[dict[str, Any]]]:
    if not board_metal_layers:
        return {}

    result: dict[int, list[dict[str, Any]]] = defaultdict(list)
    native_void_coverage = _native_void_coverage_by_parent(native_voids_by_parent)
    same_net_polygons = _same_net_polygon_coverage(
        polygon_records, net_names_by_index, known_net_names
    )
    same_net_paths = _same_net_path_coverage(payload, net_names_by_index)
    for polygon_record in polygon_records:
        if polygon_record.is_void or polygon_record.geometry_id is None:
            continue
        parent_id = int(polygon_record.geometry_id)
        layer_name = polygon_record.layer_name
        if not layer_name:
            continue
        raw_points = _binary_polygon_raw_points(polygon_record.items)
        outline_points = _approximated_polygon_points(raw_points)
        outline_bbox = _point_bbox_tuple(outline_points)
        if len(outline_points) < 3 or outline_bbox is None:
            continue

        polygon_net_name = _binary_polygon_net_name(
            polygon_record, net_names_by_index, known_net_names
        )
        seen_locations: set[tuple[int, int, int]] = set()
        for padstack_record in payload.domain.binary_padstack_instance_records:
            template_info = template_infos.get(
                _raw_definition_key(padstack_record.raw_definition_index)
            )
            if not _record_can_generate_plane_clearance(
                padstack_record, template_info
            ):
                continue
            if padstack_record.name_kind != "via" and _is_outer_board_metal_layer(
                layer_name, board_metal_layers
            ):
                continue
            padstack_net_name = padstack_record.net_name or _AEDB_NO_NET_NAME
            if (
                padstack_net_name.casefold() == polygon_net_name.casefold()
                and not _record_same_net_plane_clearance_allowed(template_info)
            ):
                continue
            if layer_name not in _record_layer_names(
                padstack_record, template_infos, board_metal_layers
            ):
                continue
            point = (padstack_record.x, padstack_record.y)
            if not _point_in_bbox(point, outline_bbox) or not _point_in_polygon(
                point, outline_points
            ):
                continue
            diameter = _synthetic_clearance_diameter(
                padstack_record, layer_name, template_infos
            )
            if diameter is None:
                continue
            if _native_void_covers_clearance(
                point, diameter, native_void_coverage.get(parent_id, ())
            ) and not _should_emit_outer_via_clearance_inside_native_void(
                padstack_record,
                layer_name,
                polygon_net_name,
                point,
                outline_bbox,
                native_void_coverage.get(parent_id, ()),
                board_metal_layers,
                template_infos,
                same_net_polygons,
                same_net_paths,
            ):
                continue
            key = (
                round(padstack_record.x / 1e-12),
                round(padstack_record.y / 1e-12),
                round(diameter / 1e-12),
            )
            if key in seen_locations:
                continue
            seen_locations.add(key)
            result[parent_id].append(
                _synthetic_circle_void(padstack_record, diameter)
            )

    for voids in result.values():
        voids.sort(
            key=lambda item: (
                item.get("source_padstack_geometry_id") or 0,
                item.get("bbox") or [],
            )
        )
    return result


def _same_net_polygon_coverage(
    polygon_records: list[AEDBDefBinaryPolygonRecord],
    net_names_by_index: dict[int, str],
    known_net_names: dict[str, str],
) -> dict[tuple[str, str], tuple[tuple[tuple[float, float, float, float], list[tuple[float, float]]], ...]]:
    result: dict[
        tuple[str, str],
        list[tuple[tuple[float, float, float, float], list[tuple[float, float]]]],
    ] = defaultdict(list)
    for record in polygon_records:
        if record.is_void or not record.layer_name:
            continue
        raw_points = _binary_polygon_raw_points(record.items)
        points = _approximated_polygon_points(raw_points)
        bbox = _point_bbox_tuple(points)
        if len(points) < 3 or bbox is None:
            continue
        net_name = _binary_polygon_net_name(record, net_names_by_index, known_net_names)
        result[(record.layer_name.casefold(), net_name.casefold())].append(
            (bbox, points)
        )
    return {key: tuple(values) for key, values in result.items()}


def _same_net_path_coverage(
    payload: AEDBDefBinaryLayout,
    net_names_by_index: dict[int, str],
) -> dict[tuple[str, str], tuple[tuple[float, tuple[tuple[float, float], ...]], ...]]:
    result: dict[
        tuple[str, str], list[tuple[float, tuple[tuple[float, float], ...]]]
    ] = defaultdict(list)
    for record in payload.domain.binary_path_records:
        if not record.layer_name:
            continue
        net_name = record.net_name or net_names_by_index.get(record.net_index or -1)
        if not net_name:
            continue
        points = tuple(
            (item.x, item.y)
            for item in record.items
            if item.kind == "point" and item.x is not None and item.y is not None
        )
        if len(points) < 2:
            continue
        result[(record.layer_name.casefold(), net_name.casefold())].append(
            (record.width, points)
        )
    return {key: tuple(values) for key, values in result.items()}


def _should_emit_outer_via_clearance_inside_native_void(
    record: AEDBDefBinaryPadstackInstanceRecord,
    layer_name: str,
    polygon_net_name: str,
    point: tuple[float, float],
    outline_bbox: tuple[float, float, float, float],
    native_voids: tuple[
        tuple[tuple[float, float, float, float], list[tuple[float, float]]], ...
    ],
    board_metal_layers: list[str],
    template_infos: dict[str, _TemplateInfo],
    same_net_polygons: dict[
        tuple[str, str],
        tuple[tuple[tuple[float, float, float, float], list[tuple[float, float]]], ...],
    ],
    same_net_paths: dict[
        tuple[str, str], tuple[tuple[float, tuple[tuple[float, float], ...]], ...]
    ],
) -> bool:
    if polygon_net_name.casefold() != "gnd":
        return False
    if not board_metal_layers or record.name_kind != "via":
        return False
    if layer_name.casefold() != board_metal_layers[-1].casefold():
        return False
    if outline_bbox[3] > _OUTER_GND_MARGIN_CLEARANCE_MAX_Y_M:
        return False
    if _native_void_contains_clearance_point(point, native_voids):
        return False
    info = template_infos.get(_raw_definition_key(record.raw_definition_index))
    if info is None or _canonical_via_template_name(info.name).upper() != "VIA8D16":
        return False
    return not _record_has_same_net_copper_on_layer(
        record, layer_name, same_net_polygons, same_net_paths
    )


def _native_void_contains_clearance_point(
    point: tuple[float, float],
    native_voids: tuple[
        tuple[tuple[float, float, float, float], list[tuple[float, float]]], ...
    ],
) -> bool:
    return any(
        _point_in_bbox(point, bbox) and _point_in_polygon(point, points)
        for bbox, points in native_voids
    )


def _record_has_same_net_copper_on_layer(
    record: AEDBDefBinaryPadstackInstanceRecord,
    layer_name: str,
    same_net_polygons: dict[
        tuple[str, str],
        tuple[tuple[tuple[float, float, float, float], list[tuple[float, float]]], ...],
    ],
    same_net_paths: dict[
        tuple[str, str], tuple[tuple[float, tuple[tuple[float, float], ...]], ...]
    ],
) -> bool:
    net_name = record.net_name
    if not net_name:
        return False
    key = (layer_name.casefold(), net_name.casefold())
    point = (record.x, record.y)
    for bbox, points in same_net_polygons.get(key, ()):
        if _point_in_bbox(point, bbox) and _point_in_polygon(point, points):
            return True
    for width, points in same_net_paths.get(key, ()):
        if _point_is_on_path(point, width, points):
            return True
    return False


def _point_is_on_path(
    point: tuple[float, float],
    width: float,
    points: tuple[tuple[float, float], ...],
) -> bool:
    tolerance = max(width * 0.5, 0.0) + 1e-9
    return any(
        _point_segment_distance(point, start, end) <= tolerance
        for start, end in zip(points, points[1:])
    )


def _point_segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    px, py = point
    ax, ay = start
    bx, by = end
    dx = bx - ax
    dy = by - ay
    length_squared = dx * dx + dy * dy
    if length_squared <= 0:
        return math.hypot(px - ax, py - ay)
    ratio = ((px - ax) * dx + (py - ay) * dy) / length_squared
    ratio = min(1.0, max(0.0, ratio))
    return math.hypot(px - (ax + ratio * dx), py - (ay + ratio * dy))


def _native_void_coverage_by_parent(
    native_voids_by_parent: dict[int, list[dict[str, Any]]],
) -> dict[int, tuple[tuple[tuple[float, float, float, float], list[tuple[float, float]]], ...]]:
    result: dict[
        int, list[tuple[tuple[float, float, float, float], list[tuple[float, float]]]]
    ] = defaultdict(list)
    for parent_id, voids in native_voids_by_parent.items():
        for void in voids:
            raw_points = void.get("raw_points")
            if not isinstance(raw_points, (list, tuple)):
                continue
            points = _approximated_polygon_points(raw_points)  # type: ignore[arg-type]
            bbox = _point_bbox_tuple(points)
            if len(points) < 3 or bbox is None:
                continue
            result[parent_id].append((bbox, points))
    return {parent_id: tuple(values) for parent_id, values in result.items()}


def _native_void_covers_clearance(
    point: tuple[float, float],
    diameter: float,
    native_voids: tuple[
        tuple[tuple[float, float, float, float], list[tuple[float, float]]], ...
    ],
) -> bool:
    if not native_voids:
        return False
    margin = diameter * 0.5 * _NATIVE_VOID_SUPPRESSION_RADIUS_FACTOR
    x, y = point
    for bbox, points in native_voids:
        if not (
            bbox[0] - margin <= x <= bbox[2] + margin
            and bbox[1] - margin <= y <= bbox[3] + margin
        ):
            continue
        if _point_in_polygon(point, points):
            return True
        if margin > 0:
            return True
    return False


def _synthetic_clearance_diameter(
    record: AEDBDefBinaryPadstackInstanceRecord,
    layer_name: str,
    template_infos: dict[str, _TemplateInfo],
) -> float | None:
    if record.name_kind != "via":
        diameter = _nonrouting_clearance_diameter(record, layer_name, template_infos)
        if diameter is not None:
            return diameter
    signal_shape = _signal_shape_for_record_layer(record, layer_name, template_infos)
    diameter = _circle_shape_diameter(signal_shape)
    if diameter is None and record.drill_diameter and record.drill_diameter > 0:
        diameter = record.drill_diameter * 2.0
    if diameter is None or diameter <= 0:
        return None
    return diameter + 2.0 * _SYNTHETIC_CLEARANCE_PER_SIDE_M


def _record_can_generate_plane_clearance(
    record: AEDBDefBinaryPadstackInstanceRecord,
    info: _TemplateInfo | None,
) -> bool:
    if record.name_kind == "via":
        return True
    if info is None:
        return False
    if _canonical_via_template_name(info.name).upper().startswith("C200"):
        return False
    return len({layer.casefold() for layer in info.layer_names}) > 1


def _record_same_net_plane_clearance_allowed(info: _TemplateInfo | None) -> bool:
    if info is None:
        return False
    return _canonical_via_template_name(info.name).upper().startswith("C060-")


def _is_outer_board_metal_layer(layer_name: str, board_metal_layers: list[str]) -> bool:
    if not board_metal_layers:
        return False
    lowered = layer_name.casefold()
    return lowered in {
        board_metal_layers[0].casefold(),
        board_metal_layers[-1].casefold(),
    }


def _nonrouting_clearance_diameter(
    record: AEDBDefBinaryPadstackInstanceRecord,
    layer_name: str,
    template_infos: dict[str, _TemplateInfo],
) -> float | None:
    info = template_infos.get(_raw_definition_key(record.raw_definition_index))
    if info is None:
        return None
    name = _canonical_via_template_name(info.name).upper()
    signal_diameter = _circle_shape_diameter(
        _signal_shape_for_record_layer(record, layer_name, template_infos)
    )
    if signal_diameter is None and record.drill_diameter and record.drill_diameter > 0:
        signal_diameter = record.drill_diameter * 2.0
    antipad_diameter = _padstack_clearance_shape_diameter(
        _antipad_shape_for_record_layer(record, layer_name, template_infos)
    )
    if name.startswith("S060") and antipad_diameter is not None:
        return antipad_diameter + _AURORADB_CLEARANCE_EPSILON_M
    if name.startswith("HOLE64") and antipad_diameter is not None:
        return antipad_diameter + _AURORADB_CLEARANCE_EPSILON_M
    if name.startswith("HOLE35") and signal_diameter is not None:
        return signal_diameter + _HOLE35N_CLEARANCE_TOTAL_M
    if signal_diameter is None or signal_diameter <= 0:
        return None
    return signal_diameter + 2.0 * _SYNTHETIC_CLEARANCE_PER_SIDE_M


def _signal_shape_for_record_layer(
    record: AEDBDefBinaryPadstackInstanceRecord,
    layer_name: str,
    template_infos: dict[str, _TemplateInfo],
) -> _AnfShape | None:
    info = template_infos.get(_raw_definition_key(record.raw_definition_index))
    if info is None or not info.signals:
        return None
    layer_names = list(info.layer_names)
    layer_index = 0
    for index, candidate in enumerate(layer_names):
        if candidate.casefold() == layer_name.casefold():
            layer_index = index
            break
    return _signal_shape_for_layer(info, layer_index)


def _antipad_shape_for_record_layer(
    record: AEDBDefBinaryPadstackInstanceRecord,
    layer_name: str,
    template_infos: dict[str, _TemplateInfo],
) -> _AnfShape | None:
    info = template_infos.get(_raw_definition_key(record.raw_definition_index))
    if info is None or not info.antipads:
        return None
    layer_names = list(info.layer_names)
    layer_index = 0
    for index, candidate in enumerate(layer_names):
        if candidate.casefold() == layer_name.casefold():
            layer_index = index
            break
    return info.antipads[min(layer_index, len(info.antipads) - 1)]


def _padstack_clearance_shape_diameter(shape: _AnfShape | None) -> float | None:
    if shape is None:
        return None
    circle = _circle_shape_diameter(shape)
    if circle is not None:
        return circle
    if len(shape.values) < 4:
        return None
    width = _finite_float(shape.values[2])
    height = _finite_float(shape.values[3])
    if width is None or height is None:
        return None
    return max(width, height)


def _circle_shape_diameter(shape: _AnfShape | None) -> float | None:
    if shape is None or shape.auroradb_type.casefold() != "circle":
        return None
    if len(shape.values) < 3:
        return None
    return _finite_float(shape.values[2])


def _synthetic_circle_void(
    record: AEDBDefBinaryPadstackInstanceRecord, diameter: float
) -> dict[str, Any]:
    radius = diameter * 0.5
    x = record.x
    y = record.y
    return {
        "raw_points": [[x + radius, y], [x + radius, y, x, y, 0]],
        "bbox": [x - radius, y - radius, x + radius, y + radius],
        "area": math.pi * radius * radius,
        "polarity": "synthetic_clearance",
        "source_padstack_geometry_id": record.geometry_id,
        "source_padstack_name": record.name,
        "source_padstack_net": record.net_name,
    }


def _approximated_polygon_points(
    raw_points: list[list[float | int | None]],
) -> list[tuple[float, float]]:
    values = _outline_values_from_raw_points(raw_points, include_closing_arc=True)
    points: list[tuple[float, float]] = []
    for value in values:
        point = _outline_vertex_point(value)
        if point is None:
            continue
        if isinstance(value, (list, tuple)) and len(value) == 5 and points:
            center = (_finite_float(value[2]), _finite_float(value[3]))
            if center[0] is not None and center[1] is not None:
                points.extend(
                    _arc_approximation_points(
                        points[-1],
                        point,
                        (center[0], center[1]),
                        value[4],
                    )
                )
                continue
        points.append(point)
    return points


def _arc_approximation_points(
    start: tuple[float, float],
    end: tuple[float, float],
    center: tuple[float, float],
    ccw_flag: object,
) -> list[tuple[float, float]]:
    radius = math.hypot(start[0] - center[0], start[1] - center[1])
    if radius <= 0 or not math.isfinite(radius):
        return [end]
    start_angle = math.atan2(start[1] - center[1], start[0] - center[0])
    end_angle = math.atan2(end[1] - center[1], end[0] - center[0])
    if _truthy_flag(ccw_flag):
        while end_angle <= start_angle:
            end_angle += math.tau
    else:
        while end_angle >= start_angle:
            end_angle -= math.tau
    span = end_angle - start_angle
    steps = max(4, math.ceil(abs(span) / _ARC_APPROX_MAX_STEP_RAD))
    return [
        (
            center[0] + radius * math.cos(start_angle + span * step / steps),
            center[1] + radius * math.sin(start_angle + span * step / steps),
        )
        for step in range(1, steps + 1)
    ]


def _truthy_flag(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().casefold() in {"y", "yes", "true", "1"}


def _point_in_bbox(
    point: tuple[float, float],
    bbox: tuple[float, float, float, float],
) -> bool:
    return bbox[0] <= point[0] <= bbox[2] and bbox[1] <= point[1] <= bbox[3]


def _point_in_polygon(
    point: tuple[float, float],
    polygon: list[tuple[float, float]],
) -> bool:
    if len(polygon) < 3:
        return False
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        y_crosses = (previous[1] > y) != (current[1] > y)
        if y_crosses:
            denominator = current[1] - previous[1]
            if abs(denominator) > 1e-30:
                x_intersection = previous[0] + (
                    (current[0] - previous[0]) * (y - previous[1]) / denominator
                )
                if x < x_intersection:
                    inside = not inside
        previous = current
    return inside


def _binary_polygon_raw_points(
    items: list[AEDBDefBinaryPathItem],
) -> list[list[float | int | None]]:
    values: list[list[float | int | None]] = []
    for item in items:
        if item.kind == "point" and item.x is not None and item.y is not None:
            values.append([item.x, item.y])
        elif item.kind == "arc_height" and item.arc_height is not None:
            values.append([item.arc_height, _ARC_HEIGHT_SENTINEL])
    return values


def _binary_polygon_net_name(
    record: AEDBDefBinaryPolygonRecord,
    net_names_by_index: dict[int, str],
    known_net_names: dict[str, str],
) -> str:
    if record.net_name:
        return record.net_name
    if record.net_index is not None and record.net_index in net_names_by_index:
        return net_names_by_index[record.net_index]
    layer_name = (record.layer_name or "").strip()
    layer_key = layer_name.casefold()
    if layer_key in known_net_names:
        return known_net_names[layer_key]
    if "gnd" in layer_key and "gnd" in known_net_names:
        return known_net_names["gnd"]
    return _AEDB_NO_NET_NAME


def _binary_polygon_point_pairs(
    raw_points: list[list[float | int | None]],
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for item in raw_points:
        if len(item) < 2 or item[1] == _ARC_HEIGHT_SENTINEL:
            continue
        x = _finite_float(item[0])
        y = _finite_float(item[1])
        if x is not None and y is not None:
            points.append((x, y))
    return points


def _parse_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _board_outline(payload: AEDBDefBinaryLayout) -> SemanticBoardOutlineGeometry:
    anf_outline = _anf_board_outline(payload)
    if anf_outline.values:
        return anf_outline

    native_polygon_outline = _native_polygon_board_outline(payload)
    if native_polygon_outline.values:
        return native_polygon_outline

    outline_records = [
        record
        for record in payload.domain.binary_path_records
        if (record.layer_name or "").casefold() == "outline"
    ]
    if not outline_records:
        return SemanticBoardOutlineGeometry()

    values: list[Any] = []
    for record in sorted(outline_records, key=lambda item: item.offset):
        record_values = _outline_record_values(record.items)
        if not record_values:
            continue
        if values and record_values[0] == values[-1]:
            values.extend(record_values[1:])
        else:
            values.extend(record_values)
    if len(values) < 2:
        return SemanticBoardOutlineGeometry()
    return SemanticBoardOutlineGeometry(
        kind="polygon",
        auroradb_type="Polygon",
        source="aedb_def_binary_outline_paths",
        path_count=len(outline_records),
        values=[len(values), *values, "Y", "Y"],
    )


def _anf_board_outline(payload: AEDBDefBinaryLayout) -> SemanticBoardOutlineGeometry:
    anf_path = _anf_sidecar_path(payload)
    if anf_path is None:
        return SemanticBoardOutlineGeometry()
    try:
        lines = anf_path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return SemanticBoardOutlineGeometry()

    candidates: list[tuple[tuple[float, float, int], str | None, list[Any]]] = []
    for line in lines:
        match = re.search(r"Graphics\('Outline'\s*,\s*(Polygon\(.*\))\)\s*$", line)
        if not match:
            continue
        polygon_text = match.group(1)
        raw_points = _anf_polygon_raw_points(polygon_text)
        values = _outline_values_from_raw_points(raw_points)
        if len(values) < 3:
            continue
        area = abs(_outline_area(values))
        bbox_area = _outline_bbox_area(values)
        candidates.append(
            ((area, bbox_area, len(values)), _anf_polygon_id(polygon_text), values)
        )
    if not candidates:
        return SemanticBoardOutlineGeometry()

    score, _raw_id, values = max(candidates, key=lambda item: item[0])
    if score[0] <= 0 and score[1] <= 0:
        return SemanticBoardOutlineGeometry()
    return SemanticBoardOutlineGeometry(
        kind="polygon",
        auroradb_type="Polygon",
        source="anf_outline_sidecar",
        path_count=len(candidates),
        values=[len(values), *values, "Y", "Y"],
    )


def _native_polygon_board_outline(
    payload: AEDBDefBinaryLayout,
) -> SemanticBoardOutlineGeometry:
    outline_candidates: list[
        tuple[tuple[float, float, int], str | None, list[Any]]
    ] = []
    for record in payload.domain.binary_polygon_records:
        if record.is_void or (record.layer_name or "").casefold() != "outline":
            continue
        raw_points = _binary_polygon_raw_points(record.items)
        values = _outline_values_from_raw_points(raw_points)
        if len(values) < 3:
            continue
        area = abs(_outline_area(values))
        bbox_area = _outline_bbox_area(values)
        outline_candidates.append(
            (
                (area, bbox_area, len(values)),
                str(record.geometry_id) if record.geometry_id is not None else None,
                values,
            )
        )
    if outline_candidates:
        score, raw_id, values = max(outline_candidates, key=lambda item: item[0])
        if score[0] > 0 or score[1] > 0:
            return SemanticBoardOutlineGeometry(
                kind="polygon",
                auroradb_type="Polygon",
                source="aedb_def_binary_outline_polygon",
                path_count=len(outline_candidates),
                values=[len(values), *values, "Y", "Y"],
                metadata={"raw_id": raw_id} if raw_id is not None else {},
            )

    candidates: list[tuple[float, tuple[float, float, float, float]]] = []
    for record in payload.domain.binary_polygon_records:
        if record.is_void:
            continue
        raw_points = _binary_polygon_raw_points(record.items)
        points = _binary_polygon_point_pairs(raw_points)
        if len(points) < 3:
            continue
        area = abs(_shoelace_points(points))
        bbox = _point_bbox_tuple(points)
        if area <= 0 or bbox is None:
            continue
        candidates.append((area, bbox))
    if not candidates:
        return SemanticBoardOutlineGeometry()

    max_area = max(area for area, _bbox in candidates)
    large_bboxes = [
        bbox for area, bbox in candidates if area >= max_area * 0.8 and area > 0
    ]
    if not large_bboxes:
        large_bboxes = [max(candidates, key=lambda item: item[0])[1]]

    min_x = _median([bbox[0] for bbox in large_bboxes])
    min_y = _median([bbox[1] for bbox in large_bboxes])
    max_x = _median([bbox[2] for bbox in large_bboxes])
    max_y = _median([bbox[3] for bbox in large_bboxes])
    if min_x is None or min_y is None or max_x is None or max_y is None:
        return SemanticBoardOutlineGeometry()
    if max_x <= min_x or max_y <= min_y:
        return SemanticBoardOutlineGeometry()

    clearance = _NATIVE_POLYGON_OUTLINE_CLEARANCE_M
    values: list[Any] = [
        [min_x - clearance, min_y - clearance],
        [max_x + clearance, min_y - clearance],
        [max_x + clearance, max_y + clearance],
        [min_x - clearance, max_y + clearance],
    ]
    return SemanticBoardOutlineGeometry(
        kind="polygon",
        auroradb_type="Polygon",
        source="aedb_def_binary_polygon_bbox",
        path_count=len(large_bboxes),
        values=[len(values), *values, "Y", "Y"],
    )


def _outline_record_values(items: list[AEDBDefBinaryPathItem]) -> list[Any]:
    values: list[Any] = []
    parsed: list[tuple[str, float | None, float | None, float | None]] = []
    for item in items:
        if item.kind == "point" and item.x is not None and item.y is not None:
            parsed.append(("point", item.x, item.y, None))
        elif item.kind == "arc_height" and item.arc_height is not None:
            parsed.append(("arc", None, None, item.arc_height))

    for index, current in enumerate(parsed):
        kind, x, y, _arc_height = current
        if kind != "point" or x is None or y is None:
            continue
        if not values:
            values.append([x, y])
            continue
        previous = parsed[index - 1]
        if previous[0] == "arc" and previous[3] is not None and index >= 2:
            start = parsed[index - 2]
            if start[0] == "point" and start[1] is not None and start[2] is not None:
                center = _arc_center_from_height(
                    (start[1], start[2]), (x, y), previous[3]
                )
                if center is not None:
                    values.append(
                        [x, y, center[0], center[1], _ccw_from_arc_height(previous[3])]
                    )
                    continue
        values.append([x, y])
    return values


def _outline_values_from_raw_points(
    raw_points: list[list[float | int | None]],
    *,
    include_closing_arc: bool = False,
) -> list[Any]:
    values: list[Any] = []
    parsed: list[tuple[str, float | None, float | None, float | None]] = []
    for item in raw_points:
        if len(item) >= 2 and item[1] == _ARC_HEIGHT_SENTINEL:
            arc_height = _finite_float(item[0])
            if arc_height is not None:
                parsed.append(("arc", None, None, arc_height))
            continue
        if len(item) >= 2:
            x = _finite_float(item[0])
            y = _finite_float(item[1])
            if x is not None and y is not None:
                parsed.append(("point", x, y, None))

    for index, current in enumerate(parsed):
        kind, x, y, _arc_height = current
        if kind != "point" or x is None or y is None:
            continue
        if not values:
            values.append([x, y])
            continue
        previous = parsed[index - 1]
        if previous[0] == "arc" and previous[3] is not None and index >= 2:
            start = parsed[index - 2]
            if start[0] == "point" and start[1] is not None and start[2] is not None:
                center = _arc_center_from_height(
                    (start[1], start[2]), (x, y), previous[3]
                )
                if center is not None:
                    values.append(
                        [x, y, center[0], center[1], _ccw_from_arc_height(previous[3])]
                    )
                    continue
        values.append([x, y])

    if include_closing_arc and len(parsed) >= 3 and parsed[-1][0] == "arc":
        first_point = next(
            (
                (candidate[1], candidate[2])
                for candidate in parsed
                if candidate[0] == "point"
                and candidate[1] is not None
                and candidate[2] is not None
            ),
            None,
        )
        start = parsed[-2]
        if (
            first_point is not None
            and start[0] == "point"
            and start[1] is not None
            and start[2] is not None
            and parsed[-1][3] is not None
        ):
            center = _arc_center_from_height(
                (start[1], start[2]), first_point, parsed[-1][3]
            )
            if center is not None:
                values.append(
                    [
                        first_point[0],
                        first_point[1],
                        center[0],
                        center[1],
                        _ccw_from_arc_height(parsed[-1][3]),
                    ]
                )

    if (
        len(values) >= 2
        and _same_outline_vertex(values[0], values[-1])
        and (not include_closing_arc or len(values[-1]) < 5)
    ):
        values.pop()
    return values


def _finite_float(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _point_bbox(points: list[tuple[float, float]]) -> list[float] | None:
    bbox = _point_bbox_tuple(points)
    return list(bbox) if bbox is not None else None


def _point_bbox_tuple(
    points: list[tuple[float, float]],
) -> tuple[float, float, float, float] | None:
    if not points:
        return None
    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    return min(x_values), min(y_values), max(x_values), max(y_values)


def _shoelace_points(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    previous = points[-1]
    for current in points:
        area += previous[0] * current[1] - current[0] * previous[1]
        previous = current
    return area * 0.5


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    middle = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return sorted_values[middle]
    return (sorted_values[middle - 1] + sorted_values[middle]) * 0.5


def _same_outline_vertex(left: Any, right: Any) -> bool:
    left_point = _outline_vertex_point(left)
    right_point = _outline_vertex_point(right)
    if left_point is None or right_point is None:
        return False
    return (
        abs(left_point[0] - right_point[0]) <= 1e-12
        and abs(left_point[1] - right_point[1]) <= 1e-12
    )


def _outline_area(values: list[Any]) -> float:
    points = [_outline_vertex_point(value) for value in values]
    points = [point for point in points if point is not None]
    if len(points) < 3:
        return 0.0
    area = 0.0
    previous = points[-1]
    for current in points:
        area += previous[0] * current[1] - current[0] * previous[1]
        previous = current
    return area * 0.5


def _outline_bbox_area(values: list[Any]) -> float:
    points = [_outline_vertex_point(value) for value in values]
    points = [point for point in points if point is not None]
    if len(points) < 2:
        return 0.0
    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    return (max(x_values) - min(x_values)) * (max(y_values) - min(y_values))


def _outline_vertex_point(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    x = _finite_float(value[0])
    y = _finite_float(value[1])
    if x is None or y is None:
        return None
    return x, y


def _arc_center_from_height(
    start: tuple[float, float],
    end: tuple[float, float],
    arc_height: float,
) -> tuple[float, float] | None:
    if not math.isfinite(arc_height) or abs(arc_height) < 1e-15:
        return None
    x2 = end[0] - start[0]
    y2 = end[1] - start[1]
    chord_squared = x2 * x2 + y2 * y2
    if chord_squared == 0:
        return start
    chord = chord_squared**0.5
    factor = 0.125 * chord / arc_height - 0.5 * arc_height / chord
    return (
        start[0] + 0.5 * x2 + y2 * factor,
        start[1] + 0.5 * y2 - x2 * factor,
    )


def _ccw_from_arc_height(arc_height: float) -> str:
    return "Y" if arc_height < 0 else "N"


def _center_line(items: list[AEDBDefBinaryPathItem]) -> list[list[float | int | None]]:
    center_line: list[list[float | int | None]] = []
    for item in items:
        if item.kind == "point" and item.x is not None and item.y is not None:
            center_line.append([item.x, item.y])
        elif item.kind == "arc_height" and item.arc_height is not None:
            center_line.append([item.arc_height, _ARC_HEIGHT_SENTINEL])
    return center_line


def _diagnostics(
    payload: AEDBDefBinaryLayout,
    *,
    anf_polygon_count: int,
    binary_polygon_count: int,
    anf_template_count: int,
) -> list[SemanticDiagnostic]:
    geometry = payload.domain.binary_geometry
    template_records_with_drill = sum(
        1
        for record in payload.domain.binary_padstack_instance_records
        if record.drill_diameter is not None and record.drill_diameter > 0
    )
    native_definition_count = len(payload.domain.padstack_instance_definitions)
    if anf_template_count:
        padstack_severity = "info"
        padstack_code = "aedb_def_binary.padstacks_from_anf_sidecar"
        padstack_message = (
            f"Loaded padstack names, layer spans, and basic pad shapes from sibling "
            f"ANF sidecar: {anf_template_count}. Exact native AEDB DEF padstack "
            "binary geometry still needs decoding."
        )
    elif native_definition_count:
        padstack_severity = "info"
        padstack_code = "aedb_def_binary.padstacks_from_binary_definitions"
        padstack_message = (
            "Decoded native AEDB DEF padstack-instance definition mappings: "
            f"{native_definition_count}; pad templates use mapped text padstack "
            "circle/rectangle/square/oval shapes and drill hints where available."
        )
    elif template_records_with_drill:
        padstack_severity = "info"
        padstack_code = "aedb_def_binary.padstacks_from_binary_hints"
        padstack_message = (
            "Derived padstack drill diameters and conservative pad shapes from AEDB "
            f"DEF binary instance records: {template_records_with_drill}. Package-local "
            "pad definition geometry still needs native decoding."
        )
    else:
        padstack_severity = "warning"
        padstack_code = "aedb_def_binary.padstack_geometry_placeholder"
        padstack_message = (
            "AEDB DEF binary padstack definitions are not fully decoded; via templates "
            "and component pad templates use placeholder circular geometry."
        )

    if anf_polygon_count:
        polygon_severity = "info"
        polygon_code = "aedb_def_binary.polygons_from_anf_sidecar"
        polygon_message = (
            f"Loaded polygon primitives from sibling ANF sidecar: {anf_polygon_count}. "
            "Native AEDB DEF polygon records are decoded only when the sidecar is absent."
        )
    elif binary_polygon_count:
        polygon_severity = "info"
        polygon_code = "aedb_def_binary.polygons_from_binary_records"
        polygon_message = (
            f"Decoded native AEDB DEF polygon primitives: {binary_polygon_count}; "
            f"source counts report polygons={geometry.polygon_outer_record_count}, "
            f"voids={geometry.polygon_void_record_count}."
        )
    else:
        polygon_severity = "warning"
        polygon_code = "aedb_def_binary.polygons_not_decoded"
        polygon_message = (
            "AEDB DEF binary polygon and polygon-void records are not fully decoded yet; "
            f"string hints report polygons={payload.domain.binary_strings.polygon_instance_name_count}, "
            f"voids={payload.domain.binary_strings.polygon_void_instance_name_count}."
        )
    diagnostics = [
        SemanticDiagnostic(
            severity=padstack_severity,
            code=padstack_code,
            message=padstack_message,
            source=source_ref("aedb", "domain.binary_padstack_instance_records"),
        ),
        SemanticDiagnostic(
            severity=polygon_severity,
            code=polygon_code,
            message=polygon_message,
            source=source_ref("aedb", "domain.binary_strings"),
        ),
        SemanticDiagnostic(
            severity="info",
            code="aedb_def_binary.decoded_geometry_counts",
            message=(
                f"Decoded path_records={geometry.path_record_count}, "
                f"path_lines={geometry.path_line_segment_count}, "
                f"path_arcs={geometry.path_arc_segment_count}, "
                f"padstack_instances={geometry.padstack_instance_record_count}."
            ),
            source=source_ref("aedb", "domain.binary_geometry"),
        ),
    ]
    return diagnostics
