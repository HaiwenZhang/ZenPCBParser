from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from aurora_translator.sources.aedb.models import (
    ComponentModel,
    LayerModel,
    LayoutSummary,
    MaterialModel,
    NetModel,
    PadstacksModel,
    PrimitivesModel,
    SummaryStatistics,
)
from aurora_translator.sources.aedb.normalizers import normalize_number, safe_getattr
from aurora_translator.shared.logging import log_timing

from .context import ExtractionContext


logger = logging.getLogger("aurora_translator.aedb.extractors.summary")

_COMPONENT_TYPE_NAMES = {
    0: "Other",
    1: "Resistor",
    2: "Inductor",
    3: "Capacitor",
    4: "IC",
    5: "IO",
}


def _component_raw_object(component: Any) -> Any:
    return safe_getattr(component, "edbcomponent") or safe_getattr(
        component, "_edb_object"
    )


def _component_type_id(component: Any) -> int | None:
    raw_component = _component_raw_object(component)
    if raw_component is None:
        return None
    try:
        return int(raw_component.GetComponentType())
    except Exception:
        return None


def _component_type_counts(components: list[Any]) -> Counter[int]:
    counts: Counter[int] = Counter()
    for component in components:
        component_type_id = _component_type_id(component)
        if component_type_id is not None:
            counts[component_type_id] += 1
    return counts


def _call_or_none(value: Any, method_name: str) -> Any:
    try:
        return getattr(value, method_name)()
    except Exception:
        return None


def _primitive_type_name(primitive: Any) -> str:
    primitive_type = _call_or_none(primitive, "GetPrimitiveType")
    if primitive_type is not None:
        return str(_call_or_none(primitive_type, "ToString") or primitive_type)
    return str(safe_getattr(primitive, "type", "Unknown"))


def _layout_size(context: ExtractionContext) -> list[float] | None:
    try:
        bbox = context.pedb._hfss.get_layout_bounding_box(context.pedb.active_layout)
        return [
            round(bbox[2] - bbox[0], 6),
            round(bbox[3] - bbox[1], 6),
        ]
    except Exception:
        bbox = safe_getattr(context.pedb, "layout_bbox")
        try:
            return [
                round(bbox[1][0] - bbox[0][0], 6),
                round(bbox[1][1] - bbox[0][1], 6),
            ]
        except Exception:
            return None


def _stackup_thickness(context: ExtractionContext) -> float | None:
    try:
        return round(context.pedb.stackup.get_layout_thickness(), 6)
    except Exception:
        return None


def _serialized_number(value: Any) -> float | int | None:
    if isinstance(value, dict):
        return normalize_number(value.get("value"))
    return normalize_number(value)


def _component_type_label(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return _COMPONENT_TYPE_NAMES.get(value, str(value))
    if isinstance(value, dict):
        display = value.get("display")
        if isinstance(display, str):
            return display
        normalized_value = _serialized_number(value)
        if normalized_value is not None:
            return _COMPONENT_TYPE_NAMES.get(
                int(normalized_value), str(int(normalized_value))
            )
    return None


def _component_type_counts_from_models(
    components: list[ComponentModel],
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for component in components:
        component_type = _component_type_label(component.type)
        if component_type:
            counts[component_type] += 1
    return counts


def _unique_primitives(primitives: PrimitivesModel) -> list[Any]:
    unique_by_id: dict[int, Any] = {}
    anonymous: list[Any] = []

    for primitive in [
        *primitives.paths,
        *primitives.polygons,
        *primitives.zone_primitives,
    ]:
        if primitive.id is None:
            anonymous.append(primitive)
        else:
            unique_by_id.setdefault(primitive.id, primitive)

    return [*unique_by_id.values(), *anonymous]


def _primitive_type_counts_from_models(primitives: PrimitivesModel) -> Counter[str]:
    counts: Counter[str] = Counter()
    for primitive in _unique_primitives(primitives):
        primitive_type = primitive.type or "Unknown"
        counts[str(primitive_type)] += 1
    return counts


def _layout_size_from_models(primitives: PrimitivesModel) -> list[float] | None:
    bboxes = [
        primitive.bbox
        for primitive in [
            *primitives.paths,
            *primitives.polygons,
            *primitives.zone_primitives,
        ]
        if primitive.bbox
    ]
    if not bboxes:
        return None

    min_x = min(bbox[0] for bbox in bboxes if bbox[0] is not None)
    min_y = min(bbox[1] for bbox in bboxes if bbox[1] is not None)
    max_x = max(bbox[2] for bbox in bboxes if bbox[2] is not None)
    max_y = max(bbox[3] for bbox in bboxes if bbox[3] is not None)
    return [
        round(max_x - min_x, 6),
        round(max_y - min_y, 6),
    ]


def _stackup_thickness_from_models(layers: list[LayerModel]) -> float | None:
    elevations = [
        (
            _serialized_number(layer.lower_elevation),
            _serialized_number(layer.upper_elevation),
        )
        for layer in layers
    ]
    resolved_elevations = [
        (lower, upper)
        for lower, upper in elevations
        if lower is not None and upper is not None
    ]
    if resolved_elevations:
        min_lower = min(lower for lower, _ in resolved_elevations)
        max_upper = max(upper for _, upper in resolved_elevations)
        return round(max_upper - min_lower, 6)

    thickness_values = [
        thickness
        for thickness in (_serialized_number(layer.thickness) for layer in layers)
        if thickness is not None
    ]
    if thickness_values:
        return round(sum(thickness_values), 6)
    return None


def extract_summary_statistics(
    context: ExtractionContext,
    component_type_counts: Counter[int],
) -> SummaryStatistics:
    return SummaryStatistics.model_validate(
        {
            "layout_size": _layout_size(context),
            "stackup_thickness": _stackup_thickness(context),
            "num_layers": len(context.layers),
            "num_nets": len(context.nets),
            "num_traces": len(context.layout_paths),
            "num_polygons": len(context.layout_polygons),
            "num_vias": len(context.padstack_instances),
            "num_discrete_components": (
                component_type_counts.get(0, 0)
                + component_type_counts.get(4, 0)
                + component_type_counts.get(5, 0)
            ),
            "num_inductors": component_type_counts.get(2, 0),
            "num_resistors": component_type_counts.get(1, 0),
            "num_capacitors": component_type_counts.get(3, 0),
        }
    )


def build_layout_summary_from_sections(
    *,
    context: ExtractionContext,
    materials: list[MaterialModel],
    layers: list[LayerModel],
    nets: list[NetModel],
    components: list[ComponentModel],
    padstacks: PadstacksModel,
    primitives: PrimitivesModel,
) -> LayoutSummary:
    with log_timing(logger, "collect layout summary from extracted sections"):
        with log_timing(logger, "count component types", count=len(components)):
            component_type_counts = _component_type_counts_from_models(components)

        with log_timing(
            logger,
            "count primitive types",
            count=len(primitives.paths)
            + len(primitives.polygons)
            + len(primitives.zone_primitives),
        ):
            primitive_type_counts = _primitive_type_counts_from_models(primitives)
            unique_primitives = _unique_primitives(primitives)

        with log_timing(logger, "compute layout size"):
            layout_size = _layout_size_from_models(primitives)

        with log_timing(logger, "compute stackup thickness"):
            stackup_thickness = _stackup_thickness_from_models(layers)

        with log_timing(logger, "validate layout summary"):
            model = LayoutSummary.model_validate(
                {
                    "material_count": len(materials),
                    "layer_count": len(layers),
                    "net_count": len(nets),
                    "component_count": len(components),
                    "padstack_definition_count": len(padstacks.definitions),
                    "padstack_instance_count": len(padstacks.instances),
                    "primitive_count": len(unique_primitives),
                    "primitive_type_counts": dict(
                        sorted(primitive_type_counts.items())
                    ),
                    "path_count": len(primitives.paths),
                    "polygon_count": len(primitives.polygons),
                    "zone_primitive_count": len(primitives.zone_primitives),
                    "statistics": SummaryStatistics.model_validate(
                        {
                            "layout_size": layout_size,
                            "stackup_thickness": stackup_thickness,
                            "num_layers": len(layers),
                            "num_nets": len(nets),
                            "num_traces": len(primitives.paths),
                            "num_polygons": len(primitives.polygons),
                            "num_vias": len(padstacks.instances),
                            "num_discrete_components": (
                                component_type_counts.get("Other", 0)
                                + component_type_counts.get("IC", 0)
                                + component_type_counts.get("IO", 0)
                            ),
                            "num_inductors": component_type_counts.get("Inductor", 0),
                            "num_resistors": component_type_counts.get("Resistor", 0),
                            "num_capacitors": component_type_counts.get("Capacitor", 0),
                        }
                    ),
                }
            )
    return model


def extract_layout_summary(context: ExtractionContext) -> LayoutSummary:
    with log_timing(logger, "collect layout summary"):
        component_values = context.components
        with log_timing(
            logger, "build summary statistics", components=len(component_values)
        ):
            with log_timing(
                logger, "count component types", count=len(component_values)
            ):
                component_type_counts = _component_type_counts(component_values)

        primitives = context.layout_primitives
        with log_timing(logger, "count primitive types", count=len(primitives)):
            primitive_type_counts = Counter(
                _primitive_type_name(primitive) for primitive in primitives
            )

        with log_timing(logger, "validate layout summary"):
            model = LayoutSummary.model_validate(
                {
                    "material_count": len(context.materials),
                    "layer_count": len(context.layers),
                    "net_count": len(context.nets),
                    "component_count": len(context.components),
                    "padstack_definition_count": len(context.padstack_definitions),
                    "padstack_instance_count": len(context.padstack_instances),
                    "primitive_count": len(primitives),
                    "primitive_type_counts": dict(
                        sorted(primitive_type_counts.items())
                    ),
                    "path_count": len(context.layout_paths),
                    "polygon_count": len(context.layout_polygons),
                    "zone_primitive_count": len(context.zone_primitives),
                    "statistics": extract_summary_statistics(
                        context, component_type_counts
                    ),
                }
            )
    return model
