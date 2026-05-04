from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Literal

from aurora_translator.sources.aedb.models import (
    ArcModel,
    EndCapStyleModel,
    PathPrimitiveModel,
    PolygonPrimitiveModel,
    PolygonVoidModel,
    PrimitivesModel,
)
from aurora_translator.sources.aedb.normalizers import (
    call_or_value,
    normalize_enum_text,
    normalize_number,
    normalize_numeric_list,
    normalize_point,
    normalize_point_list,
    normalize_value,
    safe_len,
    safe_getattr,
)
from aurora_translator.shared.logging import (
    ProgressReporter,
    log_field_block,
    log_timing,
)

from .context import ExtractionContext
from .dotnet_points import (
    DotNetPathPrimitiveSnapshot,
    DotNetPolygonPrimitiveSnapshot,
    DotNetPrimitiveBaseSnapshot,
    DotNetPrimitiveGeometry,
    geometry_from_polygon_data_dotnet,
    geometry_from_primitive_with_voids_dotnet,
    path_snapshots_from_primitives_dotnet,
    points_from_polygon_data_dotnet,
    polygon_snapshots_from_primitives_dotnet,
)


logger = logging.getLogger("aurora_translator.aedb.extractors.primitives")

_ARC_HEIGHT_MARKER_Y_THRESHOLD = 1e300
_UNSET = object()
_OBJECT_SETATTR = object.__setattr__
_ARC_MODEL_FIELDS_SET = frozenset(
    {
        "start",
        "end",
        "center",
        "mid_point",
        "height",
        "radius",
        "length",
        "is_segment",
        "is_point",
        "is_ccw",
    }
)
_PATH_SNAPSHOT_BATCH_SIZE = 1024
_POLYGON_SNAPSHOT_BATCH_SIZE = 256
AEDBParseProfile = Literal["full", "auroradb-minimal"]


@dataclass(frozen=True, slots=True)
class PolygonGeometryRecord:
    """Geometry extracted from one EDB polygon object without keeping .NET references."""

    id: Any
    raw_points: list[tuple[float, float]]
    arcs: list[ArcModel]
    bbox: list[float] | None
    area: float | int | None


@dataclass(frozen=True, slots=True)
class MinimalPolygonGeometryRecord:
    """Geometry extracted without full arc models for direct conversion."""

    id: Any
    raw_points: list[tuple[float, float]]
    bbox: list[float] | None


@dataclass(frozen=True, slots=True)
class PolygonArcBuildResult:
    """Polygon arcs derived from AEDB raw point marker sequences."""

    arcs: list[ArcModel] | None


@dataclass(frozen=True, slots=True)
class PathAreaAnalysis:
    """Decision details for whether a path area can use the analytic fast path."""

    area: float | None
    reason: str
    vertex_count: int
    has_arc: bool


@dataclass(slots=True)
class PolygonProfile:
    """Aggregated timing counters for polygon extraction hotspots."""

    polygons: int = 0
    voids: int = 0
    raw_points: int = 0
    arcs: int = 0
    fallback_arc_data_calls: int = 0
    fallback_arcs: int = 0
    primitive_with_voids_snapshot_calls: int = 0
    primitive_with_voids_snapshot_fallbacks: int = 0
    primitive_with_voids_snapshot_voids: int = 0
    primitive_with_voids_snapshot_seconds: float = 0.0
    geometry_snapshot_seconds: float = 0.0
    get_polygon_data_seconds: float = 0.0
    get_void_objects_seconds: float = 0.0
    void_geometry_seconds: float = 0.0
    read_points_seconds: float = 0.0
    build_arcs_seconds: float = 0.0
    fallback_arc_data_seconds: float = 0.0
    fallback_arc_models_seconds: float = 0.0
    area_seconds: float = 0.0
    bbox_seconds: float = 0.0
    object_id_seconds: float = 0.0
    primitive_type_seconds: float = 0.0
    layer_seconds: float = 0.0
    net_seconds: float = 0.0
    component_seconds: float = 0.0
    aedt_name_seconds: float = 0.0
    is_void_seconds: float = 0.0
    flags_seconds: float = 0.0
    void_ids_seconds: float = 0.0
    primitive_base_seconds: float = 0.0
    base_normalize_seconds: float = 0.0
    model_build_seconds: float = 0.0


@dataclass(slots=True)
class PathProfile:
    """Aggregated timing counters for path extraction hotspots."""

    paths: int = 0
    center_points: int = 0
    fallback_center_lines: int = 0
    dotnet_length_fallbacks: int = 0
    analytic_area_paths: int = 0
    polygon_area_paths: int = 0
    path_area_reason_counts: dict[str, int] = field(default_factory=dict)
    path_area_reason_seconds: dict[str, float] = field(default_factory=dict)
    path_area_reason_center_points: dict[str, int] = field(default_factory=dict)
    polygon_area_reason_get_polygon_data_seconds: dict[str, float] = field(
        default_factory=dict
    )
    polygon_area_corner_style_counts: dict[str, int] = field(default_factory=dict)
    polygon_area_end_cap_style_counts: dict[str, int] = field(default_factory=dict)
    polygon_area_vertex_bucket_counts: dict[str, int] = field(default_factory=dict)
    raw_object_seconds: float = 0.0
    get_polygon_data_seconds: float = 0.0
    get_void_objects_seconds: float = 0.0
    get_center_line_seconds: float = 0.0
    get_end_cap_style_seconds: float = 0.0
    get_width_seconds: float = 0.0
    get_corner_style_seconds: float = 0.0
    read_center_line_seconds: float = 0.0
    center_line_bbox_seconds: float = 0.0
    fallback_center_line_seconds: float = 0.0
    length_raw_points_seconds: float = 0.0
    length_dotnet_seconds: float = 0.0
    fallback_length_seconds: float = 0.0
    analytic_area_seconds: float = 0.0
    width_normalize_seconds: float = 0.0
    length_normalize_seconds: float = 0.0
    corner_style_normalize_seconds: float = 0.0
    end_cap_model_seconds: float = 0.0
    object_id_seconds: float = 0.0
    primitive_type_seconds: float = 0.0
    layer_seconds: float = 0.0
    net_seconds: float = 0.0
    component_seconds: float = 0.0
    aedt_name_seconds: float = 0.0
    is_void_seconds: float = 0.0
    area_seconds: float = 0.0
    bbox_seconds: float = 0.0
    primitive_base_seconds: float = 0.0
    base_normalize_seconds: float = 0.0
    model_build_seconds: float = 0.0


@dataclass(slots=True)
class PathPrimitiveTiming:
    """Low-noise timing counters for regular path extraction logs."""

    primitives: int = 0
    center_points: int = 0
    raw_objects_seconds: float = 0.0
    dotnet_snapshot_seconds: float = 0.0
    extract_models_seconds: float = 0.0
    model_cache_seconds: float = 0.0
    snapshot_batches: int = 0
    snapshot_fallbacks: int = 0
    analytic_area_paths: int = 0
    polygon_area_paths: int = 0
    dotnet_length_fallbacks: int = 0
    center_line_fallbacks: int = 0


@dataclass(slots=True)
class PolygonPrimitiveTiming:
    """Low-noise timing counters for regular polygon extraction logs."""

    primitives: int = 0
    voids: int = 0
    outline_points: int = 0
    void_points: int = 0
    arcs: int = 0
    raw_objects_seconds: float = 0.0
    dotnet_snapshot_seconds: float = 0.0
    extract_models_seconds: float = 0.0
    build_arcs_seconds: float = 0.0
    model_cache_seconds: float = 0.0
    snapshot_batches: int = 0
    snapshot_fallbacks: int = 0
    fallback_arc_data_calls: int = 0
    fallback_arcs: int = 0


def _record_profile_time(profile: Any | None, field_name: str, start: float) -> None:
    if profile is not None:
        setattr(
            profile, field_name, getattr(profile, field_name) + perf_counter() - start
        )


def _record_timing_time(timing: Any | None, field_name: str, start: float) -> None:
    if timing is not None:
        setattr(
            timing, field_name, getattr(timing, field_name) + perf_counter() - start
        )


def _increment_count(values: dict[str, int], key: str, amount: int = 1) -> None:
    values[key] = values.get(key, 0) + amount


def _increment_seconds(values: dict[str, float], key: str, amount: float) -> None:
    values[key] = values.get(key, 0.0) + amount


def _log_primitives_summary(
    model: PrimitivesModel,
    path_timing: PathPrimitiveTiming | None = None,
    polygon_timing: PolygonPrimitiveTiming | None = None,
    zone_timing: PolygonPrimitiveTiming | None = None,
    *,
    parse_profile: AEDBParseProfile = "full",
) -> None:
    if (
        parse_profile == "auroradb-minimal"
        and path_timing is not None
        and polygon_timing is not None
    ):
        polygon_counts = {
            "primitives": len(model.polygons),
            "outline_points": polygon_timing.outline_points,
            "arcs": polygon_timing.arcs,
            "voids": polygon_timing.voids,
            "void_points": polygon_timing.void_points,
            "void_arcs": 0,
        }
        zone_counts = (
            {
                "primitives": len(model.zone_primitives),
                "outline_points": zone_timing.outline_points
                if zone_timing is not None
                else 0,
                "arcs": zone_timing.arcs if zone_timing is not None else 0,
                "voids": zone_timing.voids if zone_timing is not None else 0,
                "void_points": zone_timing.void_points
                if zone_timing is not None
                else 0,
                "void_arcs": 0,
            }
            if zone_timing is not None
            else _polygon_collection_counts(model.zone_primitives)
        )
        path_counts = {
            "primitives": len(model.paths),
            "center_points": path_timing.center_points,
        }
    else:
        path_counts = {
            "primitives": len(model.paths),
            "center_points": sum(len(path.center_line) for path in model.paths),
        }
        polygon_counts = _polygon_collection_counts(model.polygons)
        zone_counts = _polygon_collection_counts(model.zone_primitives)

    log_field_block(
        logger,
        "Parsed layout primitives",
        sections={
            "Paths": path_counts,
            "Polygons": polygon_counts,
            "Zone primitives": zone_counts,
        },
    )


def _polygon_collection_counts(polygons: list[PolygonPrimitiveModel]) -> dict[str, int]:
    return {
        "primitives": len(polygons),
        "outline_points": sum(len(polygon.raw_points) for polygon in polygons),
        "arcs": sum(len(polygon.arcs) for polygon in polygons),
        "voids": sum(len(polygon.voids) for polygon in polygons),
        "void_points": sum(
            len(void.raw_points) for polygon in polygons for void in polygon.voids
        ),
        "void_arcs": sum(
            len(void.arcs) for polygon in polygons for void in polygon.voids
        ),
    }


def _log_primitive_timing(
    path_timing: PathPrimitiveTiming,
    polygon_timing: PolygonPrimitiveTiming,
    zone_timing: PolygonPrimitiveTiming,
) -> None:
    polygon_sections: dict[str, dict[str, object]] = {
        "Paths": {
            "primitives": path_timing.primitives,
            "center_points": path_timing.center_points,
            "raw_objects": _format_seconds(path_timing.raw_objects_seconds),
            "dotnet_snapshot": _format_seconds(path_timing.dotnet_snapshot_seconds),
            "extract_models": _format_seconds(path_timing.extract_models_seconds),
            "model_build": _format_seconds(path_timing.model_cache_seconds),
            "snapshot_batches": path_timing.snapshot_batches,
            "snapshot_fallbacks": path_timing.snapshot_fallbacks,
            "analytic_area_paths": path_timing.analytic_area_paths,
            "polygon_area_paths": path_timing.polygon_area_paths,
            "length_fallbacks": path_timing.dotnet_length_fallbacks,
            "center_line_fallbacks": path_timing.center_line_fallbacks,
        },
        "Polygons": _polygon_timing_fields(polygon_timing),
    }
    if zone_timing.primitives:
        polygon_sections["Zone primitives"] = _polygon_timing_fields(zone_timing)
    log_field_block(logger, "Primitive extraction timing", sections=polygon_sections)


def _polygon_timing_fields(timing: PolygonPrimitiveTiming) -> dict[str, object]:
    return {
        "primitives": timing.primitives,
        "voids": timing.voids,
        "outline_points": timing.outline_points,
        "void_points": timing.void_points,
        "arcs": timing.arcs,
        "raw_objects": _format_seconds(timing.raw_objects_seconds),
        "dotnet_snapshot": _format_seconds(timing.dotnet_snapshot_seconds),
        "extract_models": _format_seconds(timing.extract_models_seconds),
        "build_arcs": _format_seconds(timing.build_arcs_seconds),
        "model_build": _format_seconds(timing.model_cache_seconds),
        "snapshot_batches": timing.snapshot_batches,
        "snapshot_fallbacks": timing.snapshot_fallbacks,
        "fallback_arc_data_calls": timing.fallback_arc_data_calls,
        "fallback_arcs": timing.fallback_arcs,
    }


def _format_seconds(value: float) -> str:
    return f"{value:.3f}s"


def _call_or_none(value: Any, method_name: str) -> Any:
    try:
        return getattr(value, method_name)()
    except Exception:
        return None


def _is_null_dotnet_object(value: Any) -> bool:
    try:
        return bool(value.IsNull())
    except Exception:
        return value is None


def _primitive_raw_object(primitive: Any) -> Any:
    if callable(safe_getattr(primitive, "GetPrimitiveType")):
        return primitive
    return (
        safe_getattr(primitive, "_edb_object")
        or safe_getattr(primitive, "primitive_object")
        or safe_getattr(primitive, "core")
    )


def _dotnet_name_or_none(value: Any) -> str | None:
    if value is None or _is_null_dotnet_object(value):
        return None
    try:
        return value.GetName()
    except Exception:
        return None


def _dotnet_name_or_empty(value: Any) -> str:
    name = _dotnet_name_or_none(value)
    return name or ""


def _point_to_xy(point: Any) -> list[float] | None:
    if point is None:
        return None
    try:
        return [point.X.ToDouble(), point.Y.ToDouble()]
    except Exception:
        return None


def _polygon_data_from_raw(raw_primitive: Any) -> Any:
    if raw_primitive is None:
        return None
    return _call_or_none(raw_primitive, "GetPolygonData")


def _void_objects_from_raw(raw_primitive: Any) -> list[Any]:
    if raw_primitive is None:
        return []
    try:
        return [
            item
            for item in raw_primitive.Voids
            if item is not None and not _is_null_dotnet_object(item)
        ]
    except Exception:
        return []


def _bbox_from_polygon_data(polygon_data: Any) -> list[float] | None:
    if polygon_data is None:
        return None
    try:
        bbox = polygon_data.GetBBox()
        return [
            round(bbox.Item1.X.ToDouble(), 9),
            round(bbox.Item1.Y.ToDouble(), 9),
            round(bbox.Item2.X.ToDouble(), 9),
            round(bbox.Item2.Y.ToDouble(), 9),
        ]
    except Exception:
        return None


def _area_from_geometry(
    polygon_data: Any,
    void_objects: list[Any],
    void_geometry_records: list[PolygonGeometryRecord] | None = None,
) -> float | None:
    if polygon_data is None:
        return None
    try:
        area = polygon_data.Area()
        if void_geometry_records is not None:
            for void_record in void_geometry_records:
                if void_record.area is None:
                    return None
                area -= void_record.area
        else:
            for void in void_objects:
                void_polygon = _call_or_none(void, "GetPolygonData")
                if void_polygon is not None:
                    area -= void_polygon.Area()
        return area
    except Exception:
        return None


def _area_with_void_records(
    polygon_area: float | int | None,
    void_geometry_records: list[PolygonGeometryRecord],
) -> float | int | None:
    if polygon_area is None:
        return None
    area = polygon_area
    for void_record in void_geometry_records:
        if void_record.area is None:
            return None
        area -= void_record.area
    return area


def _points_from_polygon_data(polygon_data: Any) -> list[tuple[float, float]] | None:
    if polygon_data is None:
        return None
    dotnet_points = points_from_polygon_data_dotnet(polygon_data)
    if dotnet_points is not None:
        return dotnet_points
    try:
        return [
            (point.X.ToDouble(), point.Y.ToDouble())
            for point in list(polygon_data.Points)
        ]
    except Exception:
        return None


def _geometry_from_polygon_data_dotnet(
    polygon_data: Any,
) -> tuple[list[tuple[float, float]], list[float] | None, float | None] | None:
    geometry = geometry_from_polygon_data_dotnet(polygon_data)
    if geometry is None:
        return None
    return geometry.raw_points, geometry.bbox, geometry.area


def _path_bbox_from_center_line(
    center_line_data: Any, width: Any
) -> list[float] | None:
    bbox = _bbox_from_polygon_data(center_line_data)
    return _path_bbox_from_center_line_bbox(bbox, width)


def _path_bbox_from_center_line_bbox(
    bbox: list[float] | None, width: Any
) -> list[float] | None:
    width_value = normalize_number(width)
    if bbox is None or width_value is None:
        return None
    half_width = width_value / 2
    return [
        round(bbox[0] - half_width, 9),
        round(bbox[1] - half_width, 9),
        round(bbox[2] + half_width, 9),
        round(bbox[3] + half_width, 9),
    ]


def _arc_objects_from_polygon_data(polygon_data: Any) -> list[Any] | None:
    if polygon_data is None:
        return None
    try:
        return list(polygon_data.GetArcData())
    except Exception:
        return None


def _is_arc_height_marker(point: tuple[float, float]) -> bool:
    return abs(point[1]) > _ARC_HEIGHT_MARKER_Y_THRESHOLD


def _arc_model_fast_construct(
    start: tuple[float, float],
    end: tuple[float, float],
    center: tuple[float, float] | None,
    mid_point: tuple[float, float],
    height: float,
    radius: float | None,
    length: float,
    is_segment: bool,
    is_point: bool,
    is_ccw: bool,
) -> ArcModel:
    model = ArcModel.__new__(ArcModel)
    object_setattr = _OBJECT_SETATTR
    object_setattr(
        model,
        "__dict__",
        {
            "start": start,
            "end": end,
            "center": center,
            "mid_point": mid_point,
            "height": height,
            "radius": radius,
            "length": length,
            "is_segment": is_segment,
            "is_point": is_point,
            "is_ccw": is_ccw,
        },
    )
    object_setattr(model, "__pydantic_fields_set__", _ARC_MODEL_FIELDS_SET)
    object_setattr(model, "__pydantic_extra__", None)
    object_setattr(model, "__pydantic_private__", None)
    return model


def _segment_arc_model(
    start: tuple[float, float],
    end: tuple[float, float],
) -> ArcModel:
    return _arc_model_fast_construct(
        start,
        end,
        None,
        ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2),
        0.0,
        None,
        math.hypot(end[0] - start[0], end[1] - start[1]),
        True,
        start == end,
        False,
    )


def _height_arc_model(
    start: tuple[float, float],
    end: tuple[float, float],
    height: float,
) -> ArcModel:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    chord_length = math.hypot(dx, dy)
    is_ccw = height < 0

    if chord_length == 0:
        radius = abs(height)
        return _arc_model_fast_construct(
            start,
            end,
            start,
            start,
            height,
            radius,
            2 * math.pi * radius,
            False,
            True,
            is_ccw,
        )

    chord_mid_x = (start[0] + end[0]) / 2
    chord_mid_y = (start[1] + end[1]) / 2
    center_factor = 0.125 * chord_length / height - 0.5 * height / chord_length
    center = (
        chord_mid_x + dy * center_factor,
        chord_mid_y - dx * center_factor,
    )
    mid_point = (
        chord_mid_x - height * dy / chord_length,
        chord_mid_y + height * dx / chord_length,
    )
    radius = (chord_length * chord_length) / (8 * abs(height)) + abs(height) / 2
    angle_ratio = max(-1.0, min(1.0, chord_length / (2 * radius)))
    length = 2 * radius * math.asin(angle_ratio)
    if abs(height) > radius:
        length = 2 * math.pi * radius - length

    return _arc_model_fast_construct(
        start,
        end,
        center,
        mid_point,
        height,
        radius,
        length,
        False,
        False,
        is_ccw,
    )


def _height_arc_center(
    start: tuple[float, float],
    end: tuple[float, float],
    height: float,
) -> tuple[float, float]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    chord_length = math.hypot(dx, dy)
    if chord_length == 0:
        return start

    chord_mid_x = (start[0] + end[0]) / 2
    chord_mid_y = (start[1] + end[1]) / 2
    center_factor = 0.125 * chord_length / height - 0.5 * height / chord_length
    return (
        chord_mid_x + dy * center_factor,
        chord_mid_y - dx * center_factor,
    )


def _arc_models_from_raw_points_result(
    raw_points: list[tuple[float, float]] | None,
) -> PolygonArcBuildResult:
    if raw_points is None:
        return PolygonArcBuildResult(None)

    arcs: list[ArcModel] = []
    first_vertex: tuple[float, float] | None = None
    previous_vertex: tuple[float, float] | None = None
    pending_height: float | None = None
    leading_height: float | None = None
    vertex_count = 0
    arc_height_marker_y_threshold = _ARC_HEIGHT_MARKER_Y_THRESHOLD
    append_arc = arcs.append
    height_arc_model = _height_arc_model
    arc_model_new = ArcModel.__new__
    object_setattr = _OBJECT_SETATTR
    arc_model_fields_set = _ARC_MODEL_FIELDS_SET
    hypot = math.hypot
    abs_ = abs

    for point in raw_points:
        if abs_(point[1]) > arc_height_marker_y_threshold:
            if previous_vertex is not None:
                pending_height = point[0]
            else:
                leading_height = point[0]
            continue

        if previous_vertex is None:
            first_vertex = point
            previous_vertex = point
            vertex_count = 1
            pending_height = None
            continue

        if pending_height is None or pending_height == 0:
            start_x, start_y = previous_vertex
            end_x, end_y = point
            model = arc_model_new(ArcModel)
            object_setattr(
                model,
                "__dict__",
                {
                    "start": previous_vertex,
                    "end": point,
                    "center": None,
                    "mid_point": ((start_x + end_x) / 2, (start_y + end_y) / 2),
                    "height": 0.0,
                    "radius": None,
                    "length": hypot(end_x - start_x, end_y - start_y),
                    "is_segment": True,
                    "is_point": previous_vertex == point,
                    "is_ccw": False,
                },
            )
            object_setattr(model, "__pydantic_fields_set__", arc_model_fields_set)
            object_setattr(model, "__pydantic_extra__", None)
            object_setattr(model, "__pydantic_private__", None)
            append_arc(model)
        else:
            append_arc(height_arc_model(previous_vertex, point, pending_height))
        previous_vertex = point
        vertex_count += 1
        pending_height = None

    if vertex_count < 2 or first_vertex is None or previous_vertex is None:
        return PolygonArcBuildResult([])

    closing_height = pending_height if pending_height is not None else leading_height
    if closing_height is None or closing_height == 0:
        start_x, start_y = previous_vertex
        end_x, end_y = first_vertex
        model = arc_model_new(ArcModel)
        object_setattr(
            model,
            "__dict__",
            {
                "start": previous_vertex,
                "end": first_vertex,
                "center": None,
                "mid_point": ((start_x + end_x) / 2, (start_y + end_y) / 2),
                "height": 0.0,
                "radius": None,
                "length": hypot(end_x - start_x, end_y - start_y),
                "is_segment": True,
                "is_point": previous_vertex == first_vertex,
                "is_ccw": False,
            },
        )
        object_setattr(model, "__pydantic_fields_set__", arc_model_fields_set)
        object_setattr(model, "__pydantic_extra__", None)
        object_setattr(model, "__pydantic_private__", None)
        append_arc(model)
    else:
        append_arc(height_arc_model(previous_vertex, first_vertex, closing_height))
    return PolygonArcBuildResult(arcs)


def _arc_models_from_raw_points(
    raw_points: list[tuple[float, float]] | None,
) -> list[ArcModel] | None:
    return _arc_models_from_raw_points_result(raw_points).arcs


def _end_cap_valid(end_cap_data: Any) -> bool:
    try:
        return bool(end_cap_data and end_cap_data[0])
    except Exception:
        return False


def _enum_value(value: Any) -> int | None:
    if value is None:
        return None
    raw_value = safe_getattr(value, "value__")
    if raw_value is not None:
        try:
            return int(raw_value)
        except Exception:
            return None
    try:
        return int(value)
    except Exception:
        return None


def _primitive_aedt_prefix(primitive_type: str | None) -> str | None:
    primitive_type_name = str(primitive_type or "").lower()
    if not primitive_type_name:
        return None
    return {
        "path": "line",
        "rectangle": "rect",
        "polygon": "poly",
        "bondwire": "bwr",
    }.get(primitive_type_name, primitive_type_name)


def _primitive_aedt_name(
    primitive: Any,
    raw_primitive: Any,
    primitive_id: Any,
    primitive_type: str | None,
) -> str | None:
    if raw_primitive is not None:
        try:
            from pyedb.dotnet.clr_module import String

            pedb = safe_getattr(primitive, "_pedb") or safe_getattr(primitive, "_app")
            edb = safe_getattr(pedb, "_edb")
            if edb is not None:
                _, name = raw_primitive.GetProductProperty(
                    edb.ProductId.Designer, 1, String("")
                )
                resolved_name = str(name).strip("'")
                if resolved_name:
                    return resolved_name
        except Exception:
            pass

        prefix = _primitive_aedt_prefix(primitive_type)
        if prefix and primitive_id is not None:
            return f"{prefix}__{primitive_id}"

    return safe_getattr(primitive, "aedt_name")


def _arc_length_from_height(
    start: tuple[float, float], end: tuple[float, float], height: float | None
) -> float:
    if height is None or height == 0:
        return math.hypot(end[0] - start[0], end[1] - start[1])

    chord_length = math.hypot(end[0] - start[0], end[1] - start[1])
    if chord_length == 0:
        return 2 * math.pi * abs(height)

    radius = (chord_length * chord_length) / (8 * abs(height)) + abs(height) / 2
    angle_ratio = max(-1.0, min(1.0, chord_length / (2 * radius)))
    length = 2 * radius * math.asin(angle_ratio)
    if abs(height) > radius:
        length = 2 * math.pi * radius - length
    return length


def _apply_end_cap_length(path_length: float, end_cap_data: Any, width: Any) -> float:
    width_value = normalize_number(width)
    if _end_cap_valid(end_cap_data) and width_value is not None:
        start_style = _enum_value(end_cap_data[1])
        end_style = _enum_value(end_cap_data[2])
        if start_style != 1:
            path_length += width_value / 2
        if end_style != 1:
            path_length += width_value / 2
    return path_length


def _end_cap_area(end_cap_data: Any, width: float) -> float | None:
    if not _end_cap_valid(end_cap_data):
        return None

    radius = width / 2
    area = 0.0
    for style in (end_cap_data[1], end_cap_data[2]):
        style_value = _enum_value(style)
        if style_value == 0:
            area += math.pi * radius * radius / 2
        elif style_value == 1:
            continue
        elif style_value == 2:
            area += width * radius
        else:
            return None
    return area


def _end_cap_style_key(end_cap_data: Any) -> str:
    if not _end_cap_valid(end_cap_data):
        return "invalid"
    return (
        f"start:{normalize_enum_text(end_cap_data[1]) or _enum_value(end_cap_data[1])} "
        f"end:{normalize_enum_text(end_cap_data[2]) or _enum_value(end_cap_data[2])}"
    )


def _corner_style_key(corner_style: Any) -> str:
    return str(
        normalize_enum_text(corner_style) or _enum_value(corner_style) or "unknown"
    )


def _vertex_count_bucket(vertex_count: int) -> str:
    if vertex_count <= 2:
        return str(vertex_count)
    if vertex_count <= 4:
        return "3-4"
    if vertex_count <= 8:
        return "5-8"
    if vertex_count <= 16:
        return "9-16"
    return "17+"


def _record_path_area_analysis(
    profile: PathProfile | None,
    analysis: PathAreaAnalysis,
    elapsed_seconds: float,
    corner_style: Any,
    end_cap_style: Any,
) -> None:
    if profile is None:
        return
    _increment_count(profile.path_area_reason_counts, analysis.reason)
    _increment_seconds(
        profile.path_area_reason_seconds, analysis.reason, elapsed_seconds
    )
    _increment_count(
        profile.path_area_reason_center_points, analysis.reason, analysis.vertex_count
    )
    if analysis.area is None:
        _increment_count(
            profile.polygon_area_corner_style_counts, _corner_style_key(corner_style)
        )
        _increment_count(
            profile.polygon_area_end_cap_style_counts, _end_cap_style_key(end_cap_style)
        )
        _increment_count(
            profile.polygon_area_vertex_bucket_counts,
            _vertex_count_bucket(analysis.vertex_count),
        )


def _straight_path_area_analysis(
    raw_points: list[tuple[float, float]] | None,
    end_cap_data: Any,
    width: Any,
) -> PathAreaAnalysis:
    if raw_points is None:
        return PathAreaAnalysis(
            area=None, reason="missing_center_line", vertex_count=0, has_arc=False
        )

    width_value = normalize_number(width)
    if width_value is None:
        return PathAreaAnalysis(
            area=None, reason="missing_width", vertex_count=0, has_arc=False
        )

    vertices: list[tuple[float, float]] = []
    has_arc = False
    for point in raw_points:
        if _is_arc_height_marker(point):
            has_arc = True
            continue
        vertices.append(point)

    if has_arc:
        return PathAreaAnalysis(
            area=None,
            reason="arc_center_line",
            vertex_count=len(vertices),
            has_arc=True,
        )

    if len(vertices) > 2:
        return PathAreaAnalysis(
            area=None,
            reason="multi_segment_center_line",
            vertex_count=len(vertices),
            has_arc=False,
        )

    if len(vertices) != 2:
        return PathAreaAnalysis(
            area=None,
            reason="degenerate_center_line",
            vertex_count=len(vertices),
            has_arc=False,
        )

    cap_area = _end_cap_area(end_cap_data, width_value)
    if cap_area is None:
        return PathAreaAnalysis(
            area=None,
            reason="unsupported_end_cap",
            vertex_count=len(vertices),
            has_arc=False,
        )

    segment_length = math.hypot(
        vertices[1][0] - vertices[0][0], vertices[1][1] - vertices[0][1]
    )
    return PathAreaAnalysis(
        area=segment_length * width_value + cap_area,
        reason="analytic_straight",
        vertex_count=len(vertices),
        has_arc=False,
    )


def _straight_path_area_from_raw_points(
    raw_points: list[tuple[float, float]] | None,
    end_cap_data: Any,
    width: Any,
) -> float | None:
    return _straight_path_area_analysis(raw_points, end_cap_data, width).area


def _path_length_from_raw_points(
    raw_points: list[tuple[float, float]] | None,
    end_cap_data: Any,
    width: Any,
) -> float | None:
    if raw_points is None:
        return None

    path_length = 0.0
    start: tuple[float, float] | None = None
    pending_height: float | None = None

    for point in raw_points:
        if _is_arc_height_marker(point):
            pending_height = point[0]
            continue

        if start is None:
            start = point
            continue

        path_length += _arc_length_from_height(start, point, pending_height)
        start = point
        pending_height = None

    return _apply_end_cap_length(path_length, end_cap_data, width)


def _path_length_from_dotnet(
    center_line_data: Any, end_cap_data: Any, width: Any
) -> float | None:
    if center_line_data is None:
        return None
    try:
        path_length = 0.0
        for arc in center_line_data.GetArcData():
            path_length += arc.GetLength()
        return _apply_end_cap_length(path_length, end_cap_data, width)
    except Exception:
        return None


def _object_id_or_none(value: Any) -> Any:
    return _call_or_none(value, "GetId")


def _normalized_point_tuple(point: Any) -> tuple[float | None, float | None] | None:
    if point is None:
        return None
    try:
        return point.X.ToDouble(), point.Y.ToDouble()
    except Exception:
        normalized_point = normalize_point(_point_to_xy(point))
        if normalized_point is None:
            return None
        return normalized_point[0], normalized_point[1]


def primitive_base_data(
    primitive: Any,
    raw_primitive: Any | None = None,
    base_snapshot: DotNetPrimitiveBaseSnapshot | None = None,
    polygon_data: Any | None = None,
    void_objects: list[Any] | None = None,
    void_geometry_records: list[PolygonGeometryRecord] | None = None,
    area_override: Any = _UNSET,
    bbox_override: Any = _UNSET,
    polygon_profile: PolygonProfile | None = None,
) -> dict[str, Any]:
    raw_primitive = raw_primitive or _primitive_raw_object(primitive)
    if polygon_data is None and (area_override is _UNSET or bbox_override is _UNSET):
        polygon_data = _polygon_data_from_raw(raw_primitive)
    if void_objects is None:
        void_objects = (
            _void_objects_from_raw(raw_primitive) if area_override is _UNSET else []
        )

    start = perf_counter() if polygon_profile is not None else 0.0
    primitive_id = (
        base_snapshot.id
        if base_snapshot is not None
        else (
            _call_or_none(raw_primitive, "GetId") if raw_primitive is not None else None
        )
    )
    _record_profile_time(polygon_profile, "object_id_seconds", start)

    start = perf_counter() if polygon_profile is not None else 0.0
    primitive_type = (
        base_snapshot.primitive_type
        if base_snapshot is not None
        else (
            _call_or_none(_call_or_none(raw_primitive, "GetPrimitiveType"), "ToString")
            if raw_primitive is not None
            else None
        )
    )
    _record_profile_time(polygon_profile, "primitive_type_seconds", start)

    start = perf_counter() if polygon_profile is not None else 0.0
    layer_name = (
        base_snapshot.layer_name
        if base_snapshot is not None
        else (
            _dotnet_name_or_none(_call_or_none(raw_primitive, "GetLayer"))
            if raw_primitive is not None
            else None
        )
    )
    _record_profile_time(polygon_profile, "layer_seconds", start)

    start = perf_counter() if polygon_profile is not None else 0.0
    net_name = (
        base_snapshot.net_name
        if base_snapshot is not None
        else (
            _dotnet_name_or_empty(_call_or_none(raw_primitive, "GetNet"))
            if raw_primitive is not None
            else None
        )
    )
    _record_profile_time(polygon_profile, "net_seconds", start)

    start = perf_counter() if polygon_profile is not None else 0.0
    component_name = (
        base_snapshot.component_name
        if base_snapshot is not None
        else (
            _dotnet_name_or_empty(_call_or_none(raw_primitive, "GetComponent"))
            if raw_primitive is not None
            else None
        )
    )
    _record_profile_time(polygon_profile, "component_seconds", start)

    if area_override is _UNSET:
        start = perf_counter() if polygon_profile is not None else 0.0
        area = _area_from_geometry(polygon_data, void_objects, void_geometry_records)
        _record_profile_time(polygon_profile, "area_seconds", start)
    else:
        area = area_override

    if bbox_override is _UNSET:
        start = perf_counter() if polygon_profile is not None else 0.0
        bbox = _bbox_from_polygon_data(polygon_data)
        _record_profile_time(polygon_profile, "bbox_seconds", start)
    else:
        bbox = bbox_override

    start = perf_counter() if polygon_profile is not None else 0.0
    is_void = (
        base_snapshot.is_void
        if base_snapshot is not None and base_snapshot.has_is_void
        else (
            _call_or_none(raw_primitive, "IsVoid")
            if raw_primitive is not None
            else None
        )
    )
    _record_profile_time(polygon_profile, "is_void_seconds", start)

    start = perf_counter() if polygon_profile is not None else 0.0
    aedt_name = _primitive_aedt_name(
        primitive,
        raw_primitive,
        primitive_id if primitive_id is not None else safe_getattr(primitive, "id"),
        primitive_type
        if primitive_type is not None
        else safe_getattr(primitive, "type"),
    )
    _record_profile_time(polygon_profile, "aedt_name_seconds", start)

    return {
        "id": primitive_id
        if primitive_id is not None
        else safe_getattr(primitive, "id"),
        "name": safe_getattr(primitive, "name"),
        "type": primitive_type
        if primitive_type is not None
        else safe_getattr(primitive, "type"),
        "aedt_name": aedt_name,
        "layer_name": layer_name
        if layer_name is not None
        else safe_getattr(primitive, "layer_name"),
        "net_name": net_name
        if net_name is not None
        else safe_getattr(primitive, "net_name"),
        "component_name": component_name
        if component_name is not None
        else safe_getattr(primitive, "component_name"),
        "area": area
        if area is not None
        else call_or_value(safe_getattr(primitive, "area")),
        "bbox": bbox
        if bbox is not None
        else call_or_value(safe_getattr(primitive, "bbox")),
        "is_void": is_void
        if is_void is not None
        else safe_getattr(primitive, "is_void"),
    }


def _normalized_primitive_base_data(
    primitive: Any,
    raw_primitive: Any | None = None,
    base_snapshot: DotNetPrimitiveBaseSnapshot | None = None,
    polygon_data: Any | None = None,
    void_objects: list[Any] | None = None,
    void_geometry_records: list[PolygonGeometryRecord] | None = None,
    area_override: Any = _UNSET,
    bbox_override: Any = _UNSET,
    polygon_profile: PolygonProfile | None = None,
) -> dict[str, Any]:
    start = perf_counter() if polygon_profile is not None else 0.0
    data = primitive_base_data(
        primitive,
        raw_primitive=raw_primitive,
        base_snapshot=base_snapshot,
        polygon_data=polygon_data,
        void_objects=void_objects,
        void_geometry_records=void_geometry_records,
        area_override=area_override,
        bbox_override=bbox_override,
        polygon_profile=polygon_profile,
    )
    _record_profile_time(polygon_profile, "primitive_base_seconds", start)

    start = perf_counter() if polygon_profile is not None else 0.0
    primitive_id = data["id"]
    if primitive_id is not None:
        try:
            data["id"] = int(primitive_id)
        except Exception:
            pass
    data["area"] = normalize_number(data["area"])
    data["bbox"] = normalize_numeric_list(data["bbox"])
    _record_profile_time(polygon_profile, "base_normalize_seconds", start)
    return data


def extract_end_cap_style(end_cap_data: Any) -> EndCapStyleModel:
    if not end_cap_data:
        return EndCapStyleModel.model_construct(valid=None, start=None, end=None)
    return EndCapStyleModel.model_construct(
        valid=end_cap_data[0],
        start=normalize_enum_text(end_cap_data[1]),
        end=normalize_enum_text(end_cap_data[2]),
    )


def extract_arc(arc: Any) -> ArcModel:
    try:
        is_segment = _call_or_none(arc, "IsSegment")
        start = _normalized_point_tuple(arc.Start) or (None, None)
        end = _normalized_point_tuple(arc.End) or (None, None)
        if is_segment:
            mid_point = (
                (start[0] + end[0]) / 2
                if start[0] is not None and end[0] is not None
                else None,
                (start[1] + end[1]) / 2
                if start[1] is not None and end[1] is not None
                else None,
            )
            return ArcModel.model_construct(
                start=start,
                end=end,
                center=None,
                mid_point=mid_point,
                height=normalize_number(safe_getattr(arc, "Height")),
                radius=None,
                length=normalize_number(_call_or_none(arc, "GetLength")),
                is_segment=True,
                is_point=_call_or_none(arc, "IsPoint"),
                is_ccw=False,
            )

        return ArcModel.model_construct(
            start=start,
            end=end,
            center=_normalized_point_tuple(_call_or_none(arc, "GetCenter")),
            mid_point=_normalized_point_tuple(_call_or_none(arc, "GetMidPoint")),
            height=normalize_number(safe_getattr(arc, "Height")),
            radius=normalize_number(_call_or_none(arc, "GetRadius")),
            length=normalize_number(_call_or_none(arc, "GetLength")),
            is_segment=is_segment,
            is_point=_call_or_none(arc, "IsPoint"),
            is_ccw=_call_or_none(arc, "IsCCW"),
        )
    except Exception:
        start = _point_to_xy(safe_getattr(arc, "Start"))
        end = _point_to_xy(safe_getattr(arc, "End"))
        center = _point_to_xy(_call_or_none(arc, "GetCenter"))
        mid_point = _point_to_xy(_call_or_none(arc, "GetMidPoint"))
        radius = _call_or_none(arc, "GetRadius")
        length = _call_or_none(arc, "GetLength")
        is_segment = _call_or_none(arc, "IsSegment")
        is_point = _call_or_none(arc, "IsPoint")
        is_ccw = _call_or_none(arc, "IsCCW")

        return ArcModel.model_validate(
            {
                "start": start if start is not None else safe_getattr(arc, "start"),
                "end": end if end is not None else safe_getattr(arc, "end"),
                "center": center if center is not None else safe_getattr(arc, "center"),
                "mid_point": mid_point
                if mid_point is not None
                else safe_getattr(arc, "mid_point"),
                "height": safe_getattr(arc, "Height", safe_getattr(arc, "height")),
                "radius": radius if radius is not None else safe_getattr(arc, "radius"),
                "length": length if length is not None else safe_getattr(arc, "length"),
                "is_segment": is_segment
                if is_segment is not None
                else safe_getattr(arc, "is_segment"),
                "is_point": is_point
                if is_point is not None
                else safe_getattr(arc, "is_point"),
                "is_ccw": is_ccw if is_ccw is not None else safe_getattr(arc, "is_ccw"),
            }
        )


def _polygon_geometry_record(
    polygon: Any,
    polygon_profile: PolygonProfile | None = None,
) -> PolygonGeometryRecord:
    start = perf_counter()
    polygon_data = _polygon_data_from_raw(polygon)
    _record_profile_time(polygon_profile, "get_polygon_data_seconds", start)

    start = perf_counter()
    geometry_snapshot = _geometry_from_polygon_data_dotnet(polygon_data)
    _record_profile_time(polygon_profile, "geometry_snapshot_seconds", start)

    if geometry_snapshot is not None:
        raw_points, bbox, area = geometry_snapshot
    else:
        start = perf_counter()
        raw_points = _points_from_polygon_data(polygon_data)
        _record_profile_time(polygon_profile, "read_points_seconds", start)
        bbox = None
        area = None

    if polygon_profile is not None and raw_points is not None:
        polygon_profile.raw_points += len(raw_points)

    start = perf_counter()
    arc_build = _arc_models_from_raw_points_result(raw_points)
    arc_models = arc_build.arcs
    _record_profile_time(polygon_profile, "build_arcs_seconds", start)
    if polygon_profile is not None and arc_models is not None:
        polygon_profile.arcs += len(arc_models)

    if raw_points is None:
        raw_points = []

    if arc_models is None:
        start = perf_counter()
        arc_objects = _arc_objects_from_polygon_data(polygon_data) or []
        _record_profile_time(polygon_profile, "fallback_arc_data_seconds", start)
        if polygon_profile is not None:
            polygon_profile.fallback_arc_data_calls += 1
            polygon_profile.fallback_arcs += len(arc_objects)

        start = perf_counter()
        arc_models = [extract_arc(arc) for arc in arc_objects]
        _record_profile_time(polygon_profile, "fallback_arc_models_seconds", start)
        if polygon_profile is not None:
            polygon_profile.arcs += len(arc_models)

    if area is None and polygon_data is not None:
        start = perf_counter()
        try:
            area = polygon_data.Area()
        except Exception:
            area = None
        _record_profile_time(polygon_profile, "area_seconds", start)

    start = perf_counter()
    polygon_id = _object_id_or_none(polygon)
    _record_profile_time(polygon_profile, "object_id_seconds", start)

    if bbox is None:
        start = perf_counter()
        bbox = _bbox_from_polygon_data(polygon_data)
        _record_profile_time(polygon_profile, "bbox_seconds", start)

    return PolygonGeometryRecord(
        id=polygon_id,
        raw_points=raw_points,
        arcs=arc_models,
        bbox=bbox,
        area=normalize_number(area),
    )


def _polygon_geometry_record_from_dotnet_geometry(
    geometry: DotNetPrimitiveGeometry,
    polygon_profile: PolygonProfile | None = None,
    timing: PolygonPrimitiveTiming | None = None,
) -> PolygonGeometryRecord:
    raw_points = geometry.raw_points
    if polygon_profile is not None:
        polygon_profile.raw_points += len(raw_points)

    start = perf_counter() if polygon_profile is not None or timing is not None else 0.0
    arc_build = _arc_models_from_raw_points_result(raw_points)
    arc_models = arc_build.arcs
    _record_profile_time(polygon_profile, "build_arcs_seconds", start)
    _record_timing_time(timing, "build_arcs_seconds", start)
    if arc_models is None:
        arc_models = []
    if polygon_profile is not None:
        polygon_profile.arcs += len(arc_models)

    return PolygonGeometryRecord(
        id=geometry.id,
        raw_points=raw_points,
        arcs=arc_models,
        bbox=geometry.bbox,
        area=normalize_number(geometry.area),
    )


def _minimal_polygon_geometry_record_from_dotnet_geometry(
    geometry: DotNetPrimitiveGeometry,
    timing: PolygonPrimitiveTiming | None = None,
) -> MinimalPolygonGeometryRecord:
    raw_points = geometry.raw_points
    return MinimalPolygonGeometryRecord(
        id=geometry.id,
        raw_points=raw_points,
        bbox=geometry.bbox,
    )


def _minimal_polygon_geometry_record(
    polygon: Any,
    timing: PolygonPrimitiveTiming | None = None,
) -> MinimalPolygonGeometryRecord:
    polygon_data = _polygon_data_from_raw(polygon)
    geometry_snapshot = _geometry_from_polygon_data_dotnet(polygon_data)
    if geometry_snapshot is not None:
        raw_points, bbox, _area = geometry_snapshot
    else:
        raw_points = _points_from_polygon_data(polygon_data) or []
        bbox = _bbox_from_polygon_data(polygon_data)

    return MinimalPolygonGeometryRecord(
        id=_object_id_or_none(polygon),
        raw_points=raw_points,
        bbox=bbox,
    )


def _polygon_void_from_geometry_record(
    record: PolygonGeometryRecord,
) -> PolygonVoidModel:
    return PolygonVoidModel.model_construct(
        id=record.id,
        raw_points=record.raw_points,
        arcs=record.arcs,
        bbox=record.bbox,
        area=record.area,
    )


def extract_path_primitive(
    path: Any,
    path_profile: PathProfile | None = None,
    *,
    raw_path: Any | None = None,
    snapshot: DotNetPathPrimitiveSnapshot | None = None,
    timing: PathPrimitiveTiming | None = None,
) -> PathPrimitiveModel:
    if path_profile is not None:
        path_profile.paths += 1
    if timing is not None:
        timing.primitives += 1

    start = perf_counter() if path_profile is not None else 0.0
    raw_path = raw_path if raw_path is not None else _primitive_raw_object(path)
    _record_profile_time(path_profile, "raw_object_seconds", start)

    center_line_data = None
    if snapshot is not None:
        center_line = snapshot.center_line
        center_line_bbox = snapshot.center_line_bbox
    else:
        start = perf_counter() if path_profile is not None else 0.0
        center_line_data = (
            _call_or_none(raw_path, "GetCenterLine") if raw_path is not None else None
        )
        _record_profile_time(path_profile, "get_center_line_seconds", start)
        center_line = None
        center_line_bbox = None

    if snapshot is not None and snapshot.has_end_cap_style:
        end_cap_style = (True, snapshot.end_cap_start, snapshot.end_cap_end)
    else:
        start = perf_counter() if path_profile is not None else 0.0
        end_cap_style = (
            _call_or_none(raw_path, "GetEndCapStyle") if raw_path is not None else None
        )
        _record_profile_time(path_profile, "get_end_cap_style_seconds", start)

    if snapshot is not None and snapshot.has_width:
        width = snapshot.width
    else:
        start = perf_counter() if path_profile is not None else 0.0
        width = _call_or_none(raw_path, "GetWidth") if raw_path is not None else None
        _record_profile_time(path_profile, "get_width_seconds", start)

    if snapshot is not None and snapshot.corner_style is not None:
        corner_style = snapshot.corner_style
    else:
        start = perf_counter() if path_profile is not None else 0.0
        corner_style = (
            _call_or_none(raw_path, "GetCornerStyle") if raw_path is not None else None
        )
        _record_profile_time(path_profile, "get_corner_style_seconds", start)

    if center_line is None:
        start = perf_counter() if path_profile is not None else 0.0
        center_line = _points_from_polygon_data(center_line_data)
        _record_profile_time(path_profile, "read_center_line_seconds", start)
    end_cap_getter = safe_getattr(path, "get_end_cap_style")

    has_raw_center_line = center_line is not None
    if center_line is None:
        if path_profile is not None:
            path_profile.fallback_center_lines += 1
        if timing is not None:
            timing.center_line_fallbacks += 1
        start = perf_counter() if path_profile is not None else 0.0
        center_line = (
            call_or_value(safe_getattr(path, "get_center_line"))
            or safe_getattr(path, "center_line")
            or []
        )
        _record_profile_time(path_profile, "fallback_center_line_seconds", start)
    if path_profile is not None:
        path_profile.center_points += safe_len(center_line)
    if timing is not None:
        timing.center_points += safe_len(center_line)

    if width is None:
        width = safe_getattr(path, "width")

    start = perf_counter() if path_profile is not None else 0.0
    path_bbox = _path_bbox_from_center_line_bbox(center_line_bbox, width)
    if path_bbox is None:
        if center_line_data is None and raw_path is not None:
            center_line_data = _call_or_none(raw_path, "GetCenterLine")
        path_bbox = _path_bbox_from_center_line(center_line_data, width)
    _record_profile_time(path_profile, "center_line_bbox_seconds", start)

    start = perf_counter() if path_profile is not None else 0.0
    length = _path_length_from_raw_points(
        center_line if has_raw_center_line else None, end_cap_style, width
    )
    _record_profile_time(path_profile, "length_raw_points_seconds", start)
    if length is None:
        if path_profile is not None:
            path_profile.dotnet_length_fallbacks += 1
        if timing is not None:
            timing.dotnet_length_fallbacks += 1
        start = perf_counter() if path_profile is not None else 0.0
        if center_line_data is None and raw_path is not None:
            center_line_data = _call_or_none(raw_path, "GetCenterLine")
        length = _path_length_from_dotnet(center_line_data, end_cap_style, width)
        _record_profile_time(path_profile, "length_dotnet_seconds", start)
    if length is None:
        start = perf_counter() if path_profile is not None else 0.0
        length = safe_getattr(path, "length")
        _record_profile_time(path_profile, "fallback_length_seconds", start)

    start = perf_counter()
    path_area_analysis = _straight_path_area_analysis(
        center_line if has_raw_center_line else None,
        end_cap_style,
        width,
    )
    path_area = path_area_analysis.area
    analytic_area_elapsed = perf_counter() - start
    if path_profile is not None:
        path_profile.analytic_area_seconds += analytic_area_elapsed
    _record_path_area_analysis(
        path_profile,
        path_area_analysis,
        analytic_area_elapsed,
        corner_style,
        end_cap_style,
    )

    polygon_data = None
    void_objects: list[Any] = []
    if path_area is None:
        if path_profile is not None:
            path_profile.polygon_area_paths += 1
        if timing is not None:
            timing.polygon_area_paths += 1
        start = perf_counter() if path_profile is not None else 0.0
        polygon_data = _polygon_data_from_raw(raw_path)
        polygon_data_elapsed = perf_counter() - start
        if path_profile is not None:
            path_profile.get_polygon_data_seconds += polygon_data_elapsed
            _increment_seconds(
                path_profile.polygon_area_reason_get_polygon_data_seconds,
                path_area_analysis.reason,
                polygon_data_elapsed,
            )

        start = perf_counter() if path_profile is not None else 0.0
        void_objects = _void_objects_from_raw(raw_path)
        _record_profile_time(path_profile, "get_void_objects_seconds", start)
    else:
        if path_profile is not None:
            path_profile.analytic_area_paths += 1
        if timing is not None:
            timing.analytic_area_paths += 1

    primitive_data = _normalized_primitive_base_data(
        path,
        raw_primitive=raw_path,
        base_snapshot=snapshot.base if snapshot is not None else None,
        polygon_data=polygon_data,
        void_objects=void_objects,
        area_override=path_area if path_area is not None else _UNSET,
        bbox_override=path_bbox if path_bbox is not None else _UNSET,
        polygon_profile=path_profile,
    )

    start = perf_counter() if path_profile is not None else 0.0
    width_value = normalize_value(width)
    _record_profile_time(path_profile, "width_normalize_seconds", start)

    start = perf_counter() if path_profile is not None else 0.0
    length_value = normalize_number(length)
    _record_profile_time(path_profile, "length_normalize_seconds", start)

    start = perf_counter() if path_profile is not None else 0.0
    corner_style_value = normalize_enum_text(
        corner_style if corner_style is not None else safe_getattr(path, "corner_style")
    )
    _record_profile_time(path_profile, "corner_style_normalize_seconds", start)

    start = perf_counter() if path_profile is not None else 0.0
    end_cap_model = extract_end_cap_style(
        end_cap_style
        if end_cap_style is not None
        else (end_cap_getter() if callable(end_cap_getter) else None)
    )
    _record_profile_time(path_profile, "end_cap_model_seconds", start)

    start = perf_counter() if path_profile is not None or timing is not None else 0.0
    data = {
        **primitive_data,
        "width": width_value,
        "length": length_value,
        "center_line": center_line,
        "corner_style": corner_style_value,
        "end_cap_style": end_cap_model,
    }
    if has_raw_center_line:
        result = PathPrimitiveModel.model_construct(**data)
        _record_profile_time(path_profile, "model_build_seconds", start)
        _record_timing_time(timing, "model_cache_seconds", start)
        return result
    result = PathPrimitiveModel.model_validate(data)
    _record_profile_time(path_profile, "model_build_seconds", start)
    _record_timing_time(timing, "model_cache_seconds", start)
    return result


def extract_polygon_primitive(
    polygon: Any,
    polygon_profile: PolygonProfile | None = None,
    *,
    raw_polygon: Any | None = None,
    snapshot: DotNetPolygonPrimitiveSnapshot | None = None,
    timing: PolygonPrimitiveTiming | None = None,
) -> PolygonPrimitiveModel:
    if polygon_profile is not None:
        polygon_profile.polygons += 1
    if timing is not None:
        timing.primitives += 1

    raw_polygon = (
        raw_polygon if raw_polygon is not None else _primitive_raw_object(polygon)
    )

    start = perf_counter() if polygon_profile is not None else 0.0
    if snapshot is not None:
        dotnet_geometry = snapshot.geometry
    else:
        dotnet_geometry = (
            geometry_from_primitive_with_voids_dotnet(raw_polygon)
            if raw_polygon is not None
            else None
        )
    _record_profile_time(
        polygon_profile, "primitive_with_voids_snapshot_seconds", start
    )

    if dotnet_geometry is not None:
        if polygon_profile is not None:
            polygon_profile.primitive_with_voids_snapshot_calls += 1
            polygon_profile.primitive_with_voids_snapshot_voids += len(
                dotnet_geometry.voids
            )
            polygon_profile.voids += len(dotnet_geometry.voids)
        polygon_data = None
        void_objects: list[Any] = []
        start = perf_counter()
        void_geometry_records = [
            _polygon_geometry_record_from_dotnet_geometry(
                void_geometry, polygon_profile, timing
            )
            for void_geometry in dotnet_geometry.voids
        ]
        _record_profile_time(polygon_profile, "void_geometry_seconds", start)

        main_geometry_record = _polygon_geometry_record_from_dotnet_geometry(
            dotnet_geometry.primitive,
            polygon_profile,
            timing,
        )
        raw_points = main_geometry_record.raw_points
        bbox = main_geometry_record.bbox
        polygon_area = main_geometry_record.area
        arcs = main_geometry_record.arcs
        has_raw_points = True
        has_raw_arcs = True
        if timing is not None:
            timing.voids += len(void_geometry_records)
            timing.outline_points += len(raw_points)
            timing.void_points += sum(
                len(record.raw_points) for record in void_geometry_records
            )
            timing.arcs += len(arcs) + sum(
                len(record.arcs) for record in void_geometry_records
            )
    else:
        if polygon_profile is not None:
            polygon_profile.primitive_with_voids_snapshot_fallbacks += 1
        if timing is not None:
            timing.snapshot_fallbacks += 1

        start = perf_counter()
        polygon_data = _polygon_data_from_raw(raw_polygon)
        _record_profile_time(polygon_profile, "get_polygon_data_seconds", start)

        start = perf_counter()
        void_objects = _void_objects_from_raw(raw_polygon)
        _record_profile_time(polygon_profile, "get_void_objects_seconds", start)
        if polygon_profile is not None:
            polygon_profile.voids += len(void_objects)

        start = perf_counter()
        void_geometry_records = [
            _polygon_geometry_record(void, polygon_profile) for void in void_objects
        ]
        _record_profile_time(polygon_profile, "void_geometry_seconds", start)

        start = perf_counter()
        geometry_snapshot = _geometry_from_polygon_data_dotnet(polygon_data)
        _record_profile_time(polygon_profile, "geometry_snapshot_seconds", start)

        if geometry_snapshot is not None:
            raw_points, bbox, polygon_area = geometry_snapshot
        else:
            start = perf_counter()
            raw_points = _points_from_polygon_data(polygon_data)
            _record_profile_time(polygon_profile, "read_points_seconds", start)
            bbox = None
            polygon_area = None

        if polygon_profile is not None and raw_points is not None:
            polygon_profile.raw_points += len(raw_points)

        start = perf_counter()
        arc_build = _arc_models_from_raw_points_result(raw_points)
        arc_models = arc_build.arcs
        _record_profile_time(polygon_profile, "build_arcs_seconds", start)
        if polygon_profile is not None and arc_models is not None:
            polygon_profile.arcs += len(arc_models)

        if arc_models is None:
            start = perf_counter()
            arc_objects = _arc_objects_from_polygon_data(polygon_data)
            _record_profile_time(polygon_profile, "fallback_arc_data_seconds", start)
        else:
            arc_objects = None
        if polygon_profile is not None and arc_objects is not None:
            polygon_profile.fallback_arc_data_calls += 1
            polygon_profile.fallback_arcs += len(arc_objects)
        if timing is not None and arc_objects is not None:
            timing.fallback_arc_data_calls += 1
            timing.fallback_arcs += len(arc_objects)

        has_raw_points = raw_points is not None
        has_raw_arcs = arc_models is not None or arc_objects is not None
        if raw_points is None:
            raw_points = call_or_value(
                safe_getattr(polygon, "points_raw")
            ) or safe_getattr(polygon, "points_raw", [])

        if arc_models is not None:
            arcs = arc_models
        else:
            if arc_objects is None:
                arc_objects = safe_getattr(polygon, "arcs") or []
            start = perf_counter()
            arcs = [extract_arc(arc) for arc in arc_objects]
            _record_profile_time(polygon_profile, "fallback_arc_models_seconds", start)
        if polygon_profile is not None and arc_models is None:
            polygon_profile.arcs += len(arcs)
        if timing is not None:
            timing.voids += len(void_geometry_records)
            timing.outline_points += len(raw_points)
            timing.void_points += sum(
                len(record.raw_points) for record in void_geometry_records
            )
            timing.arcs += len(arcs) + sum(
                len(record.arcs) for record in void_geometry_records
            )

    if snapshot is not None:
        is_negative = snapshot.is_negative if snapshot.has_is_negative else None
        is_zone_primitive = (
            snapshot.is_zone_primitive if snapshot.has_is_zone_primitive else None
        )
        has_voids = snapshot.has_voids if snapshot.has_has_voids else None
    else:
        start = perf_counter()
        is_negative = (
            _call_or_none(raw_polygon, "GetIsNegative")
            if raw_polygon is not None
            else None
        )
        is_zone_primitive = (
            _call_or_none(raw_polygon, "IsZonePrimitive")
            if raw_polygon is not None
            else None
        )
        has_voids = (
            _call_or_none(raw_polygon, "HasVoids") if raw_polygon is not None else None
        )
        _record_profile_time(polygon_profile, "flags_seconds", start)

    start = perf_counter() if polygon_profile is not None else 0.0
    void_ids = [
        item_id
        if (item_id := _object_id_or_none(item)) is not None
        else safe_getattr(item, "id")
        for item in void_objects
    ]
    _record_profile_time(polygon_profile, "void_ids_seconds", start)

    primitive_data = _normalized_primitive_base_data(
        polygon,
        raw_primitive=raw_polygon,
        base_snapshot=snapshot.base if snapshot is not None else None,
        polygon_data=polygon_data,
        void_objects=void_objects,
        void_geometry_records=void_geometry_records,
        area_override=(
            _area_with_void_records(polygon_area, void_geometry_records)
            if polygon_area is not None
            else _UNSET
        ),
        bbox_override=bbox if bbox is not None else _UNSET,
        polygon_profile=polygon_profile,
    )

    start = perf_counter() if polygon_profile is not None or timing is not None else 0.0
    void_models = [
        _polygon_void_from_geometry_record(record) for record in void_geometry_records
    ]
    data = {
        **primitive_data,
        "raw_points": raw_points,
        "arcs": arcs,
        "is_negative": is_negative
        if is_negative is not None
        else safe_getattr(polygon, "is_negative"),
        "is_zone_primitive": (
            is_zone_primitive
            if is_zone_primitive is not None
            else safe_getattr(polygon, "is_zone_primitive")
        ),
        "has_voids": has_voids
        if has_voids is not None
        else safe_getattr(polygon, "has_voids"),
        "void_ids": [record.id for record in void_geometry_records]
        if void_geometry_records
        else void_ids,
        "voids": void_models,
    }
    if has_raw_points and has_raw_arcs:
        result = PolygonPrimitiveModel.model_construct(**data)
        _record_profile_time(polygon_profile, "model_build_seconds", start)
        _record_timing_time(timing, "model_cache_seconds", start)
        return result
    data["raw_points"] = normalize_point_list(data["raw_points"])
    result = PolygonPrimitiveModel.model_validate(data)
    _record_profile_time(polygon_profile, "model_build_seconds", start)
    _record_timing_time(timing, "model_cache_seconds", start)
    return result


def extract_polygon_void(void: Any) -> PolygonVoidModel:
    if isinstance(void, PolygonGeometryRecord):
        return _polygon_void_from_geometry_record(void)

    polygon_data = _polygon_data_from_raw(void)
    geometry_snapshot = _geometry_from_polygon_data_dotnet(polygon_data)
    if geometry_snapshot is not None:
        raw_points, bbox, area = geometry_snapshot
    else:
        raw_points = _points_from_polygon_data(polygon_data) or []
        bbox = _bbox_from_polygon_data(polygon_data)
        area = None
    arc_models = _arc_models_from_raw_points(raw_points)
    arc_objects = (
        []
        if arc_models is not None
        else (_arc_objects_from_polygon_data(polygon_data) or [])
    )
    if area is None and polygon_data is not None:
        try:
            area = polygon_data.Area()
        except Exception:
            area = None
    data = {
        "id": _object_id_or_none(void),
        "raw_points": raw_points,
        "arcs": arc_models
        if arc_models is not None
        else [extract_arc(arc) for arc in arc_objects],
        "bbox": bbox,
        "area": normalize_number(area),
    }
    return PolygonVoidModel.model_construct(**data)


def extract_path_primitive_minimal(
    path: Any,
    *,
    raw_path: Any | None = None,
    snapshot: DotNetPathPrimitiveSnapshot | None = None,
    timing: PathPrimitiveTiming | None = None,
) -> PathPrimitiveModel:
    if timing is not None:
        timing.primitives += 1

    raw_path = raw_path if raw_path is not None else _primitive_raw_object(path)
    center_line_data = None
    if snapshot is not None:
        center_line = snapshot.center_line
        center_line_bbox = snapshot.center_line_bbox
        width = snapshot.width if snapshot.has_width else None
        corner_style = snapshot.corner_style
        end_cap_style = (
            (True, snapshot.end_cap_start, snapshot.end_cap_end)
            if snapshot.has_end_cap_style
            else None
        )
    else:
        center_line_data = (
            _call_or_none(raw_path, "GetCenterLine") if raw_path is not None else None
        )
        center_line = _points_from_polygon_data(center_line_data)
        center_line_bbox = _bbox_from_polygon_data(center_line_data)
        width = _call_or_none(raw_path, "GetWidth") if raw_path is not None else None
        corner_style = (
            _call_or_none(raw_path, "GetCornerStyle") if raw_path is not None else None
        )
        end_cap_style = (
            _call_or_none(raw_path, "GetEndCapStyle") if raw_path is not None else None
        )

    if center_line is None:
        if timing is not None:
            timing.center_line_fallbacks += 1
        center_line = (
            call_or_value(safe_getattr(path, "get_center_line"))
            or safe_getattr(path, "center_line")
            or []
        )
    if timing is not None:
        timing.center_points += safe_len(center_line)

    if width is None:
        width = safe_getattr(path, "width")

    path_bbox = _path_bbox_from_center_line_bbox(center_line_bbox, width)
    if path_bbox is None:
        if center_line_data is None and raw_path is not None:
            center_line_data = _call_or_none(raw_path, "GetCenterLine")
        path_bbox = _path_bbox_from_center_line(center_line_data, width)

    primitive_data = _normalized_primitive_base_data(
        path,
        raw_primitive=raw_path,
        base_snapshot=snapshot.base if snapshot is not None else None,
        area_override=None,
        bbox_override=path_bbox,
    )

    start = perf_counter() if timing is not None else 0.0
    result = PathPrimitiveModel.model_construct(
        **primitive_data,
        width=normalize_value(width),
        length=None,
        center_line=center_line,
        corner_style=normalize_enum_text(
            corner_style
            if corner_style is not None
            else safe_getattr(path, "corner_style")
        ),
        end_cap_style=extract_end_cap_style(end_cap_style),
    )
    _record_timing_time(timing, "model_cache_seconds", start)
    return result


def extract_polygon_primitive_minimal(
    polygon: Any,
    *,
    raw_polygon: Any | None = None,
    snapshot: DotNetPolygonPrimitiveSnapshot | None = None,
    timing: PolygonPrimitiveTiming | None = None,
) -> PolygonPrimitiveModel:
    if timing is not None:
        timing.primitives += 1

    raw_polygon = (
        raw_polygon if raw_polygon is not None else _primitive_raw_object(polygon)
    )
    if snapshot is not None:
        dotnet_geometry = snapshot.geometry
    else:
        dotnet_geometry = (
            geometry_from_primitive_with_voids_dotnet(raw_polygon)
            if raw_polygon is not None
            else None
        )

    if dotnet_geometry is not None:
        void_geometry_records = [
            _minimal_polygon_geometry_record_from_dotnet_geometry(void_geometry, timing)
            for void_geometry in dotnet_geometry.voids
        ]
        main_geometry_record = _minimal_polygon_geometry_record_from_dotnet_geometry(
            dotnet_geometry.primitive, timing
        )
    else:
        void_objects = _void_objects_from_raw(raw_polygon)
        void_geometry_records = [
            _minimal_polygon_geometry_record(void, timing) for void in void_objects
        ]
        main_geometry_record = _minimal_polygon_geometry_record(raw_polygon, timing)

    raw_points = main_geometry_record.raw_points
    if timing is not None:
        timing.voids += len(void_geometry_records)
        timing.outline_points += len(raw_points)
        timing.void_points += sum(
            len(record.raw_points) for record in void_geometry_records
        )

    if snapshot is not None:
        is_negative = snapshot.is_negative if snapshot.has_is_negative else None
        is_zone_primitive = (
            snapshot.is_zone_primitive if snapshot.has_is_zone_primitive else None
        )
        has_voids = snapshot.has_voids if snapshot.has_has_voids else None
    else:
        is_negative = (
            _call_or_none(raw_polygon, "GetIsNegative")
            if raw_polygon is not None
            else None
        )
        is_zone_primitive = (
            _call_or_none(raw_polygon, "IsZonePrimitive")
            if raw_polygon is not None
            else None
        )
        has_voids = (
            _call_or_none(raw_polygon, "HasVoids") if raw_polygon is not None else None
        )

    primitive_data = _normalized_primitive_base_data(
        polygon,
        raw_primitive=raw_polygon,
        base_snapshot=snapshot.base if snapshot is not None else None,
        area_override=None,
        bbox_override=main_geometry_record.bbox,
    )

    start = perf_counter() if timing is not None else 0.0
    result = PolygonPrimitiveModel.model_construct(
        **primitive_data,
        raw_points=raw_points,
        arcs=[],
        is_negative=is_negative
        if is_negative is not None
        else safe_getattr(polygon, "is_negative"),
        is_zone_primitive=(
            is_zone_primitive
            if is_zone_primitive is not None
            else safe_getattr(polygon, "is_zone_primitive")
        ),
        has_voids=has_voids if has_voids is not None else bool(void_geometry_records),
        void_ids=[
            record.id for record in void_geometry_records if record.id is not None
        ],
        voids=[
            PolygonVoidModel.model_construct(
                id=record.id,
                raw_points=record.raw_points,
                arcs=[],
                bbox=record.bbox,
                area=None,
            )
            for record in void_geometry_records
        ],
    )
    _record_timing_time(timing, "model_cache_seconds", start)
    return result


def _extract_path_primitives(
    values: list[Any],
    timing: PathPrimitiveTiming,
    *,
    parse_profile: AEDBParseProfile = "full",
) -> list[PathPrimitiveModel]:
    if not values:
        return []

    results: list[PathPrimitiveModel] = []
    reporter = ProgressReporter(logger, "Serialize path primitives", total=len(values))
    processed = 0
    batch_enabled = True

    for chunk in _chunked(values, _PATH_SNAPSHOT_BATCH_SIZE):
        start = perf_counter()
        raw_values = [_primitive_raw_object(path) for path in chunk]
        timing.raw_objects_seconds += perf_counter() - start

        if batch_enabled:
            timing.snapshot_batches += 1
            start = perf_counter()
            snapshots = path_snapshots_from_primitives_dotnet(raw_values)
            timing.dotnet_snapshot_seconds += perf_counter() - start
        else:
            snapshots = None
        if snapshots is None or len(snapshots) != len(raw_values):
            batch_enabled = False
            timing.snapshot_fallbacks += len(raw_values)
            snapshots = [None] * len(raw_values)

        start = perf_counter()
        for path, raw_path, snapshot in zip(chunk, raw_values, snapshots, strict=False):
            if parse_profile == "auroradb-minimal":
                results.append(
                    extract_path_primitive_minimal(
                        path, raw_path=raw_path, snapshot=snapshot, timing=timing
                    )
                )
            else:
                results.append(
                    extract_path_primitive(
                        path, None, raw_path=raw_path, snapshot=snapshot, timing=timing
                    )
                )
            processed += 1
            reporter.update(processed)
        timing.extract_models_seconds += perf_counter() - start

    return results


def _extract_polygon_primitives(
    values: list[Any],
    operation: str,
    timing: PolygonPrimitiveTiming,
    *,
    parse_profile: AEDBParseProfile = "full",
) -> list[PolygonPrimitiveModel]:
    if not values:
        return []

    results: list[PolygonPrimitiveModel] = []
    reporter = ProgressReporter(
        logger, operation[:1].upper() + operation[1:], total=len(values)
    )
    processed = 0
    batch_enabled = True

    for chunk in _chunked(values, _POLYGON_SNAPSHOT_BATCH_SIZE):
        start = perf_counter()
        raw_values = [_primitive_raw_object(polygon) for polygon in chunk]
        timing.raw_objects_seconds += perf_counter() - start

        if batch_enabled:
            timing.snapshot_batches += 1
            start = perf_counter()
            snapshots = polygon_snapshots_from_primitives_dotnet(raw_values)
            timing.dotnet_snapshot_seconds += perf_counter() - start
        else:
            snapshots = None
        if snapshots is None or len(snapshots) != len(raw_values):
            batch_enabled = False
            timing.snapshot_fallbacks += len(raw_values)
            snapshots = [None] * len(raw_values)

        start = perf_counter()
        for polygon, raw_polygon, snapshot in zip(
            chunk, raw_values, snapshots, strict=False
        ):
            if parse_profile == "auroradb-minimal":
                results.append(
                    extract_polygon_primitive_minimal(
                        polygon,
                        raw_polygon=raw_polygon,
                        snapshot=snapshot,
                        timing=timing,
                    )
                )
            else:
                results.append(
                    extract_polygon_primitive(
                        polygon,
                        None,
                        raw_polygon=raw_polygon,
                        snapshot=snapshot,
                        timing=timing,
                    )
                )
            processed += 1
            reporter.update(processed)
        timing.extract_models_seconds += perf_counter() - start

    return results


def _chunked(values: list[Any], chunk_size: int):
    for start in range(0, len(values), chunk_size):
        yield values[start : start + chunk_size]


def extract_primitives(
    context: ExtractionContext,
    *,
    parse_profile: AEDBParseProfile = "full",
) -> PrimitivesModel:
    path_values = context.layout_paths
    polygon_values = context.layout_polygons
    zone_values = context.zone_primitives
    path_timing = PathPrimitiveTiming()
    polygon_timing = PolygonPrimitiveTiming()
    zone_timing = PolygonPrimitiveTiming()
    with log_timing(
        logger,
        "serialize layout primitives",
        heartbeat=False,
        paths=len(path_values),
        polygons=len(polygon_values),
        zones=len(zone_values),
        parse_profile=parse_profile,
    ):
        with log_timing(
            logger, "serialize path primitives", heartbeat=False, count=len(path_values)
        ):
            paths = _extract_path_primitives(
                path_values, path_timing, parse_profile=parse_profile
            )

        with log_timing(
            logger,
            "serialize polygon primitives",
            heartbeat=False,
            count=len(polygon_values),
        ):
            polygons = _extract_polygon_primitives(
                polygon_values,
                "serialize polygon primitives",
                polygon_timing,
                parse_profile=parse_profile,
            )

        with log_timing(
            logger, "serialize zone primitives", heartbeat=False, count=len(zone_values)
        ):
            zone_primitives = _extract_polygon_primitives(
                zone_values,
                "serialize zone primitives",
                zone_timing,
                parse_profile=parse_profile,
            )

        with log_timing(logger, "build primitives model"):
            model = PrimitivesModel.model_construct(
                paths=paths,
                polygons=polygons,
                zone_primitives=zone_primitives,
            )
    _log_primitives_summary(
        model, path_timing, polygon_timing, zone_timing, parse_profile=parse_profile
    )
    _log_primitive_timing(path_timing, polygon_timing, zone_timing)
    return model
