from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


logger = logging.getLogger("aurora_translator.aedb.extractors.dotnet_points")

_POINT_EXTRACTOR_TYPE: Any | None = None
_POINT_EXTRACTOR_ATTEMPTED = False


@dataclass(frozen=True, slots=True)
class DotNetPolygonGeometry:
    raw_points: list[tuple[float, float]]
    bbox: list[float] | None
    area: float | None


@dataclass(frozen=True, slots=True)
class DotNetPrimitiveGeometry:
    id: int | None
    raw_points: list[tuple[float, float]]
    bbox: list[float] | None
    area: float | None


@dataclass(frozen=True, slots=True)
class DotNetPrimitiveWithVoidsGeometry:
    primitive: DotNetPrimitiveGeometry
    voids: list[DotNetPrimitiveGeometry]


@dataclass(frozen=True, slots=True)
class DotNetPrimitiveBaseSnapshot:
    id: int | None
    primitive_type: str | None
    layer_name: str | None
    net_name: str | None
    component_name: str | None
    has_is_void: bool
    is_void: bool


@dataclass(frozen=True, slots=True)
class DotNetEnumValue:
    name: str | None
    value: int | None

    @property
    def value__(self) -> int | None:
        return self.value


@dataclass(frozen=True, slots=True)
class DotNetPathPrimitiveSnapshot:
    base: DotNetPrimitiveBaseSnapshot
    center_line: list[tuple[float, float]] | None
    center_line_bbox: list[float] | None
    has_width: bool
    width: float | None
    has_end_cap_style: bool
    end_cap_start: DotNetEnumValue | None
    end_cap_end: DotNetEnumValue | None
    corner_style: str | None


@dataclass(frozen=True, slots=True)
class DotNetPolygonPrimitiveSnapshot:
    base: DotNetPrimitiveBaseSnapshot
    geometry: DotNetPrimitiveWithVoidsGeometry | None
    has_is_negative: bool
    is_negative: bool
    has_is_zone_primitive: bool
    is_zone_primitive: bool
    has_has_voids: bool
    has_voids: bool


_POINT_EXTRACTOR_SOURCE = r"""
using System;
using System.Collections.Generic;
using Ansys.Ansoft.Edb.Cell.Primitive;
using Ansys.Ansoft.Edb.Geometry;

namespace AuroraTranslator.DotNet
{
    public sealed class PolygonGeometrySnapshot
    {
        public double[] Points { get; set; }
        public double[] BBox { get; set; }
        public double Area { get; set; }
        public bool HasBBox { get; set; }
        public bool HasArea { get; set; }
    }

    public sealed class PrimitiveGeometrySnapshot
    {
        public bool HasId { get; set; }
        public ulong Id { get; set; }
        public double[] Points { get; set; }
        public double[] BBox { get; set; }
        public double Area { get; set; }
        public bool HasBBox { get; set; }
        public bool HasArea { get; set; }
    }

    public sealed class PrimitiveWithVoidsGeometrySnapshot
    {
        public PrimitiveGeometrySnapshot Primitive { get; set; }
        public PrimitiveGeometrySnapshot[] Voids { get; set; }
    }

    public sealed class PrimitiveBaseSnapshot
    {
        public bool HasId { get; set; }
        public ulong Id { get; set; }
        public string PrimitiveType { get; set; }
        public string LayerName { get; set; }
        public string NetName { get; set; }
        public string ComponentName { get; set; }
        public bool HasIsVoid { get; set; }
        public bool IsVoid { get; set; }
    }

    public sealed class PathPrimitiveSnapshot
    {
        public PrimitiveBaseSnapshot Base { get; set; }
        public PolygonGeometrySnapshot CenterLine { get; set; }
        public bool HasWidth { get; set; }
        public double Width { get; set; }
        public bool HasEndCapStyle { get; set; }
        public string EndCapStart { get; set; }
        public string EndCapEnd { get; set; }
        public int EndCapStartValue { get; set; }
        public int EndCapEndValue { get; set; }
        public string CornerStyle { get; set; }
    }

    public sealed class PolygonPrimitiveSnapshot
    {
        public PrimitiveBaseSnapshot Base { get; set; }
        public PrimitiveWithVoidsGeometrySnapshot Geometry { get; set; }
        public bool HasIsNegative { get; set; }
        public bool IsNegative { get; set; }
        public bool HasIsZonePrimitive { get; set; }
        public bool IsZonePrimitive { get; set; }
        public bool HasHasVoids { get; set; }
        public bool HasVoids { get; set; }
    }

    public static class PolygonPointExtractor
    {
        public static double[] GetPointToFlatArray(PolygonData polygon)
        {
            int count = polygon.Count;
            double[] values = new double[count * 2];
            int index = 0;
            for (int i = 0; i < count; i++)
            {
                PointData point = polygon.GetPoint((uint)i);
                values[index++] = point.X.ToDouble();
                values[index++] = point.Y.ToDouble();
            }
            return values;
        }

        public static PolygonGeometrySnapshot GetGeometrySnapshot(PolygonData polygon)
        {
            PolygonGeometrySnapshot snapshot = new PolygonGeometrySnapshot();
            snapshot.Points = GetPointToFlatArray(polygon);

            try
            {
                var bbox = polygon.GetBBox();
                snapshot.BBox = new double[]
                {
                    bbox.Item1.X.ToDouble(),
                    bbox.Item1.Y.ToDouble(),
                    bbox.Item2.X.ToDouble(),
                    bbox.Item2.Y.ToDouble()
                };
                snapshot.HasBBox = true;
            }
            catch
            {
                snapshot.BBox = null;
                snapshot.HasBBox = false;
            }

            try
            {
                snapshot.Area = polygon.Area();
                snapshot.HasArea = true;
            }
            catch
            {
                snapshot.Area = 0.0;
                snapshot.HasArea = false;
            }

            return snapshot;
        }

        public static PathPrimitiveSnapshot[] GetPathSnapshots(Array primitives)
        {
            if (primitives == null)
            {
                return new PathPrimitiveSnapshot[0];
            }

            PathPrimitiveSnapshot[] snapshots = new PathPrimitiveSnapshot[primitives.Length];
            for (int i = 0; i < primitives.Length; i++)
            {
                Primitive primitive = primitives.GetValue(i) as Primitive;
                snapshots[i] = GetPathSnapshot(primitive);
            }
            return snapshots;
        }

        public static PolygonPrimitiveSnapshot[] GetPolygonSnapshots(Array primitives)
        {
            if (primitives == null)
            {
                return new PolygonPrimitiveSnapshot[0];
            }

            PolygonPrimitiveSnapshot[] snapshots = new PolygonPrimitiveSnapshot[primitives.Length];
            for (int i = 0; i < primitives.Length; i++)
            {
                Primitive primitive = primitives.GetValue(i) as Primitive;
                snapshots[i] = GetPolygonSnapshot(primitive);
            }
            return snapshots;
        }

        public static PrimitiveWithVoidsGeometrySnapshot GetPrimitiveWithVoidsGeometrySnapshot(Primitive primitive)
        {
            PrimitiveWithVoidsGeometrySnapshot snapshot = new PrimitiveWithVoidsGeometrySnapshot();
            snapshot.Primitive = GetPrimitiveGeometrySnapshot(primitive);

            List<PrimitiveGeometrySnapshot> voids = new List<PrimitiveGeometrySnapshot>();
            try
            {
                foreach (Primitive voidPrimitive in primitive.Voids)
                {
                    if (voidPrimitive == null || voidPrimitive.IsNull())
                    {
                        continue;
                    }
                    voids.Add(GetPrimitiveGeometrySnapshot(voidPrimitive));
                }
            }
            catch
            {
            }

            snapshot.Voids = voids.ToArray();
            return snapshot;
        }

        private static PathPrimitiveSnapshot GetPathSnapshot(Primitive primitive)
        {
            PathPrimitiveSnapshot snapshot = new PathPrimitiveSnapshot();
            snapshot.Base = GetPrimitiveBaseSnapshot(primitive);

            Path path = primitive as Path;
            if (path == null)
            {
                return snapshot;
            }

            try
            {
                PolygonData centerLine = path.GetCenterLine();
                if (centerLine != null)
                {
                    snapshot.CenterLine = GetPointsAndBBoxSnapshot(centerLine);
                }
            }
            catch
            {
                snapshot.CenterLine = null;
            }

            try
            {
                snapshot.Width = path.GetWidth();
                snapshot.HasWidth = true;
            }
            catch
            {
                snapshot.HasWidth = false;
            }

            try
            {
                PathEndCapStyle startStyle;
                PathEndCapStyle endStyle;
                if (path.GetEndCapStyle(out startStyle, out endStyle))
                {
                    snapshot.HasEndCapStyle = true;
                    snapshot.EndCapStart = startStyle.ToString();
                    snapshot.EndCapEnd = endStyle.ToString();
                    snapshot.EndCapStartValue = (int)startStyle;
                    snapshot.EndCapEndValue = (int)endStyle;
                }
            }
            catch
            {
                snapshot.HasEndCapStyle = false;
            }

            try
            {
                snapshot.CornerStyle = path.GetCornerStyle().ToString();
            }
            catch
            {
                snapshot.CornerStyle = null;
            }

            return snapshot;
        }

        private static PolygonPrimitiveSnapshot GetPolygonSnapshot(Primitive primitive)
        {
            PolygonPrimitiveSnapshot snapshot = new PolygonPrimitiveSnapshot();
            snapshot.Base = GetPrimitiveBaseSnapshot(primitive);
            snapshot.Geometry = GetPrimitiveWithVoidsGeometrySnapshot(primitive);

            try
            {
                snapshot.IsNegative = (bool)InvokeNoArg(primitive, "GetIsNegative");
                snapshot.HasIsNegative = true;
            }
            catch
            {
                snapshot.HasIsNegative = false;
            }

            try
            {
                snapshot.IsZonePrimitive = (bool)InvokeNoArg(primitive, "IsZonePrimitive");
                snapshot.HasIsZonePrimitive = true;
            }
            catch
            {
                snapshot.HasIsZonePrimitive = false;
            }

            try
            {
                snapshot.HasVoids = (bool)InvokeNoArg(primitive, "HasVoids");
                snapshot.HasHasVoids = true;
            }
            catch
            {
                snapshot.HasHasVoids = false;
            }

            return snapshot;
        }

        private static PrimitiveBaseSnapshot GetPrimitiveBaseSnapshot(Primitive primitive)
        {
            PrimitiveBaseSnapshot snapshot = new PrimitiveBaseSnapshot();
            snapshot.NetName = "";
            snapshot.ComponentName = "";
            if (primitive == null)
            {
                return snapshot;
            }

            try
            {
                snapshot.Id = primitive.GetId();
                snapshot.HasId = true;
            }
            catch
            {
                snapshot.HasId = false;
            }

            try
            {
                snapshot.PrimitiveType = primitive.GetPrimitiveType().ToString();
            }
            catch
            {
                snapshot.PrimitiveType = null;
            }

            try
            {
                var layer = primitive.GetLayer();
                snapshot.LayerName = layer == null ? null : layer.GetName();
            }
            catch
            {
                snapshot.LayerName = null;
            }

            try
            {
                var net = primitive.GetNet();
                snapshot.NetName = IsNullEdbObject(net) ? "" : net.GetName();
            }
            catch
            {
                snapshot.NetName = "";
            }

            try
            {
                var component = primitive.GetComponent();
                snapshot.ComponentName = IsNullEdbObject(component) ? "" : component.GetName();
            }
            catch
            {
                snapshot.ComponentName = "";
            }

            try
            {
                snapshot.IsVoid = primitive.IsVoid();
                snapshot.HasIsVoid = true;
            }
            catch
            {
                snapshot.HasIsVoid = false;
            }

            return snapshot;
        }

        private static PolygonGeometrySnapshot GetPointsAndBBoxSnapshot(PolygonData polygon)
        {
            PolygonGeometrySnapshot snapshot = new PolygonGeometrySnapshot();
            snapshot.Points = GetPointToFlatArray(polygon);
            snapshot.HasArea = false;

            try
            {
                var bbox = polygon.GetBBox();
                snapshot.BBox = new double[]
                {
                    bbox.Item1.X.ToDouble(),
                    bbox.Item1.Y.ToDouble(),
                    bbox.Item2.X.ToDouble(),
                    bbox.Item2.Y.ToDouble()
                };
                snapshot.HasBBox = true;
            }
            catch
            {
                snapshot.BBox = null;
                snapshot.HasBBox = false;
            }

            return snapshot;
        }

        private static PrimitiveGeometrySnapshot GetPrimitiveGeometrySnapshot(Primitive primitive)
        {
            PrimitiveGeometrySnapshot snapshot = new PrimitiveGeometrySnapshot();

            try
            {
                snapshot.Id = primitive.GetId();
                snapshot.HasId = true;
            }
            catch
            {
                snapshot.HasId = false;
            }

            PolygonData polygon = GetPolygonDataOrNull(primitive);

            if (polygon == null)
            {
                snapshot.Points = new double[0];
                snapshot.BBox = null;
                snapshot.Area = 0.0;
                snapshot.HasBBox = false;
                snapshot.HasArea = false;
                return snapshot;
            }

            snapshot.Points = GetPointToFlatArray(polygon);

            try
            {
                var bbox = polygon.GetBBox();
                snapshot.BBox = new double[]
                {
                    bbox.Item1.X.ToDouble(),
                    bbox.Item1.Y.ToDouble(),
                    bbox.Item2.X.ToDouble(),
                    bbox.Item2.Y.ToDouble()
                };
                snapshot.HasBBox = true;
            }
            catch
            {
                snapshot.BBox = null;
                snapshot.HasBBox = false;
            }

            try
            {
                snapshot.Area = polygon.Area();
                snapshot.HasArea = true;
            }
            catch
            {
                snapshot.Area = 0.0;
                snapshot.HasArea = false;
            }

            return snapshot;
        }

        private static PolygonData GetPolygonDataOrNull(Primitive primitive)
        {
            if (primitive == null)
            {
                return null;
            }

            try
            {
                var method = primitive.GetType().GetMethod("GetPolygonData", Type.EmptyTypes);
                if (method == null)
                {
                    return null;
                }

                return method.Invoke(primitive, null) as PolygonData;
            }
            catch
            {
                return null;
            }
        }

        private static object InvokeNoArg(object value, string methodName)
        {
            if (value == null)
            {
                return null;
            }

            var method = value.GetType().GetMethod(methodName, Type.EmptyTypes);
            if (method == null)
            {
                return null;
            }

            return method.Invoke(value, null);
        }

        private static bool IsNullEdbObject(object value)
        {
            if (value == null)
            {
                return true;
            }

            try
            {
                var method = value.GetType().GetMethod("IsNull", Type.EmptyTypes);
                if (method != null)
                {
                    return (bool)method.Invoke(value, null);
                }
            }
            catch
            {
            }

            return false;
        }
    }
}
""".strip()


def points_from_polygon_data_dotnet(
    polygon_data: Any,
) -> list[tuple[float, float]] | None:
    """Return polygon points through a tiny .NET helper, or None if unavailable."""

    extractor = _point_extractor_type(polygon_data)
    if extractor is None:
        return None

    try:
        flat_points = extractor.GetPointToFlatArray(polygon_data)
        return _flat_points_to_tuples(flat_points)
    except Exception:
        logger.debug(
            "Failed to extract polygon points through .NET helper", exc_info=True
        )
        return None


def geometry_from_polygon_data_dotnet(
    polygon_data: Any,
) -> DotNetPolygonGeometry | None:
    """Return polygon points, bbox, and area through the .NET helper."""

    extractor = _point_extractor_type(polygon_data)
    if extractor is None:
        return None

    try:
        snapshot = extractor.GetGeometrySnapshot(polygon_data)
        raw_points = _flat_points_to_tuples(snapshot.Points)
        bbox = None
        if bool(snapshot.HasBBox) and snapshot.BBox is not None:
            bbox_values = snapshot.BBox
            bbox = [
                round(bbox_values[0], 9),
                round(bbox_values[1], 9),
                round(bbox_values[2], 9),
                round(bbox_values[3], 9),
            ]
        area = snapshot.Area if bool(snapshot.HasArea) else None
        return DotNetPolygonGeometry(raw_points=raw_points, bbox=bbox, area=area)
    except Exception:
        logger.debug(
            "Failed to extract polygon geometry through .NET helper", exc_info=True
        )
        return None


def geometry_from_primitive_with_voids_dotnet(
    raw_primitive: Any,
) -> DotNetPrimitiveWithVoidsGeometry | None:
    """Return primitive and void geometry through one .NET helper call."""

    extractor = _point_extractor_type(raw_primitive)
    if extractor is None:
        return None

    try:
        snapshot = extractor.GetPrimitiveWithVoidsGeometrySnapshot(raw_primitive)
        return _primitive_with_voids_snapshot_to_geometry(snapshot)
    except Exception:
        logger.debug(
            "Failed to extract primitive and void geometry through .NET helper",
            exc_info=True,
        )
        return None


def path_snapshots_from_primitives_dotnet(
    raw_primitives: list[Any],
) -> list[DotNetPathPrimitiveSnapshot] | None:
    """Return path primitive snapshots through one .NET batch call."""

    if not raw_primitives:
        return []

    first_primitive = next((item for item in raw_primitives if item is not None), None)
    if first_primitive is None:
        return None

    extractor = _point_extractor_type(first_primitive)
    if extractor is None:
        return None

    try:
        array = _dotnet_primitive_array(raw_primitives, first_primitive)
        snapshots = extractor.GetPathSnapshots(array)
        return [_dotnet_path_snapshot(snapshot) for snapshot in snapshots]
    except Exception:
        logger.debug(
            "Failed to extract path primitive snapshots through .NET batch helper",
            exc_info=True,
        )
        return None


def polygon_snapshots_from_primitives_dotnet(
    raw_primitives: list[Any],
) -> list[DotNetPolygonPrimitiveSnapshot] | None:
    """Return polygon primitive snapshots through one .NET batch call."""

    if not raw_primitives:
        return []

    first_primitive = next((item for item in raw_primitives if item is not None), None)
    if first_primitive is None:
        return None

    extractor = _point_extractor_type(first_primitive)
    if extractor is None:
        return None

    try:
        array = _dotnet_primitive_array(raw_primitives, first_primitive)
        snapshots = extractor.GetPolygonSnapshots(array)
        return [_dotnet_polygon_snapshot(snapshot) for snapshot in snapshots]
    except Exception:
        logger.debug(
            "Failed to extract polygon primitive snapshots through .NET batch helper",
            exc_info=True,
        )
        return None


def _flat_points_to_tuples(flat_points: Any) -> list[tuple[float, float]]:
    return [
        (flat_points[index], flat_points[index + 1])
        for index in range(0, len(flat_points), 2)
    ]


def _primitive_snapshot_to_geometry(snapshot: Any) -> DotNetPrimitiveGeometry:
    raw_points = _flat_points_to_tuples(snapshot.Points)
    bbox = None
    if bool(snapshot.HasBBox) and snapshot.BBox is not None:
        bbox_values = snapshot.BBox
        bbox = [
            round(bbox_values[0], 9),
            round(bbox_values[1], 9),
            round(bbox_values[2], 9),
            round(bbox_values[3], 9),
        ]
    return DotNetPrimitiveGeometry(
        id=int(snapshot.Id) if bool(snapshot.HasId) else None,
        raw_points=raw_points,
        bbox=bbox,
        area=snapshot.Area if bool(snapshot.HasArea) else None,
    )


def _primitive_with_voids_snapshot_to_geometry(
    snapshot: Any,
) -> DotNetPrimitiveWithVoidsGeometry:
    primitive = _primitive_snapshot_to_geometry(snapshot.Primitive)
    voids = [
        _primitive_snapshot_to_geometry(void_snapshot)
        for void_snapshot in (snapshot.Voids or [])
    ]
    return DotNetPrimitiveWithVoidsGeometry(primitive=primitive, voids=voids)


def _dotnet_path_snapshot(snapshot: Any) -> DotNetPathPrimitiveSnapshot:
    center_line = None
    center_line_bbox = None
    if snapshot.CenterLine is not None:
        center_line = _flat_points_to_tuples(snapshot.CenterLine.Points)
        if bool(snapshot.CenterLine.HasBBox) and snapshot.CenterLine.BBox is not None:
            bbox_values = snapshot.CenterLine.BBox
            center_line_bbox = [
                round(bbox_values[0], 9),
                round(bbox_values[1], 9),
                round(bbox_values[2], 9),
                round(bbox_values[3], 9),
            ]

    end_cap_start = None
    end_cap_end = None
    if bool(snapshot.HasEndCapStyle):
        end_cap_start = DotNetEnumValue(
            name=snapshot.EndCapStart, value=int(snapshot.EndCapStartValue)
        )
        end_cap_end = DotNetEnumValue(
            name=snapshot.EndCapEnd, value=int(snapshot.EndCapEndValue)
        )

    return DotNetPathPrimitiveSnapshot(
        base=_dotnet_primitive_base_snapshot(snapshot.Base),
        center_line=center_line,
        center_line_bbox=center_line_bbox,
        has_width=bool(snapshot.HasWidth),
        width=snapshot.Width if bool(snapshot.HasWidth) else None,
        has_end_cap_style=bool(snapshot.HasEndCapStyle),
        end_cap_start=end_cap_start,
        end_cap_end=end_cap_end,
        corner_style=snapshot.CornerStyle,
    )


def _dotnet_polygon_snapshot(snapshot: Any) -> DotNetPolygonPrimitiveSnapshot:
    geometry = None
    if snapshot.Geometry is not None and snapshot.Geometry.Primitive is not None:
        geometry = _primitive_with_voids_snapshot_to_geometry(snapshot.Geometry)
    return DotNetPolygonPrimitiveSnapshot(
        base=_dotnet_primitive_base_snapshot(snapshot.Base),
        geometry=geometry,
        has_is_negative=bool(snapshot.HasIsNegative),
        is_negative=bool(snapshot.IsNegative),
        has_is_zone_primitive=bool(snapshot.HasIsZonePrimitive),
        is_zone_primitive=bool(snapshot.IsZonePrimitive),
        has_has_voids=bool(snapshot.HasHasVoids),
        has_voids=bool(snapshot.HasVoids),
    )


def _dotnet_primitive_base_snapshot(snapshot: Any) -> DotNetPrimitiveBaseSnapshot:
    return DotNetPrimitiveBaseSnapshot(
        id=int(snapshot.Id) if snapshot is not None and bool(snapshot.HasId) else None,
        primitive_type=snapshot.PrimitiveType if snapshot is not None else None,
        layer_name=snapshot.LayerName if snapshot is not None else None,
        net_name=snapshot.NetName if snapshot is not None else None,
        component_name=snapshot.ComponentName if snapshot is not None else None,
        has_is_void=bool(snapshot.HasIsVoid) if snapshot is not None else False,
        is_void=bool(snapshot.IsVoid) if snapshot is not None else False,
    )


def _dotnet_primitive_array(raw_primitives: list[Any], first_primitive: Any) -> Any:
    import System

    array_type = _dotnet_primitive_array_type(first_primitive)
    array = System.Array.CreateInstance(array_type, len(raw_primitives))
    for index, raw_primitive in enumerate(raw_primitives):
        array.SetValue(raw_primitive, index)
    return array


def _dotnet_primitive_array_type(first_primitive: Any) -> Any:
    try:
        current_type = first_primitive.GetType()
    except Exception:
        return first_primitive.GetType()

    fallback_type = current_type
    while current_type is not None:
        try:
            if (
                str(current_type.FullName)
                == "Ansys.Ansoft.Edb.Cell.Primitive.Primitive"
            ):
                return current_type
            current_type = current_type.BaseType
        except Exception:
            break
    return fallback_type


def _point_extractor_type(polygon_data: Any) -> Any | None:
    global _POINT_EXTRACTOR_ATTEMPTED, _POINT_EXTRACTOR_TYPE

    if _POINT_EXTRACTOR_ATTEMPTED:
        return _POINT_EXTRACTOR_TYPE
    _POINT_EXTRACTOR_ATTEMPTED = True

    assembly_location = _edb_assembly_location(polygon_data)
    if assembly_location is None:
        return None

    csc_path = _csc_path()
    if csc_path is None:
        logger.debug("C# compiler not found; using Python polygon point extraction")
        return None

    try:
        import clr

        helper_path = _compile_point_extractor(csc_path, assembly_location)
        clr.AddReference(str(assembly_location))
        clr.AddReference(str(helper_path))
        from AuroraTranslator.DotNet import PolygonPointExtractor

        _POINT_EXTRACTOR_TYPE = PolygonPointExtractor
        return _POINT_EXTRACTOR_TYPE
    except Exception:
        logger.debug(
            "Failed to load .NET polygon point extractor; using Python fallback",
            exc_info=True,
        )
        _POINT_EXTRACTOR_TYPE = None
        return None


def _edb_assembly_location(polygon_data: Any) -> Path | None:
    try:
        location = polygon_data.GetType().Assembly.Location
    except Exception:
        return None
    if not location:
        return None
    path = Path(str(location))
    return path if path.exists() else None


def _csc_path() -> Path | None:
    windir = os.environ.get("WINDIR")
    if windir:
        framework_csc = (
            Path(windir) / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe"
        )
        if framework_csc.exists():
            return framework_csc
    return None


def _compile_point_extractor(csc_path: Path, edb_assembly: Path) -> Path:
    cache_dir = Path(tempfile.gettempdir()) / "aurora_translator_dotnet"
    cache_dir.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256(
        (
            str(edb_assembly.resolve()).casefold() + "\n" + _POINT_EXTRACTOR_SOURCE
        ).encode("utf-8")
    ).hexdigest()[:16]
    source_path = cache_dir / f"PolygonPointExtractor_{digest}.cs"
    helper_path = cache_dir / f"PolygonPointExtractor_{digest}.dll"

    if helper_path.exists():
        return helper_path

    source_path.write_text(_POINT_EXTRACTOR_SOURCE, encoding="utf-8")
    completed = subprocess.run(
        [
            str(csc_path),
            "/target:library",
            "/nologo",
            f"/out:{helper_path}",
            f"/reference:{edb_assembly}",
            str(source_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Failed to compile .NET polygon point extractor: "
            f"{completed.stdout.strip()} {completed.stderr.strip()}".strip()
        )
    return helper_path
