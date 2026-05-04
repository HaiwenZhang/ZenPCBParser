from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


logger = logging.getLogger("aurora_translator.aedb.extractors.dotnet_padstacks")

_PADSTACK_EXTRACTOR_TYPE: Any | None = None
_PADSTACK_EXTRACTOR_ATTEMPTED = False
_PADSTACK_DEFINITION_EXTRACTOR_TYPE: Any | None = None
_PADSTACK_DEFINITION_EXTRACTOR_ATTEMPTED = False


@dataclass(frozen=True, slots=True)
class DotNetPadstackSnapshot:
    id: int | None
    name: str | None
    type: str | None
    net_name: str | None
    component_name: str | None
    placement_layer: str | None
    has_position: bool
    x: float
    y: float
    rotation: float
    start_layer: str | None
    stop_layer: str | None
    padstack_definition: str | None
    has_is_layout_pin: bool
    is_layout_pin: bool


@dataclass(frozen=True, slots=True)
class DotNetDisplayValue:
    tofloat: float | None
    tostring: str | None


@dataclass(frozen=True, slots=True)
class DotNetPadPropertySnapshot:
    layer_name: str
    pad_type: int
    geometry_type: int
    shape: str | None
    offset_x: str | None
    offset_y: str | None
    rotation: str | None
    parameters: tuple[DotNetDisplayValue, ...]
    raw_points: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class DotNetPadstackDefinitionSnapshot:
    name: str | None
    material: str | None
    hole_type: str | None
    hole_range: str | None
    hole_diameter: float | None
    hole_diameter_string: str | None
    hole_finished_size: float | None
    hole_offset_x: str | None
    hole_offset_y: str | None
    hole_rotation: str | None
    hole_plating_ratio: float | None
    hole_plating_thickness: float | None
    hole_properties: tuple[float, ...] | None
    via_layers: tuple[str, ...]
    via_start_layer: str | None
    via_stop_layer: str | None
    pad_by_layer: tuple[DotNetPadPropertySnapshot, ...]
    antipad_by_layer: tuple[DotNetPadPropertySnapshot, ...]
    thermalpad_by_layer: tuple[DotNetPadPropertySnapshot, ...]


_PADSTACK_EXTRACTOR_SOURCE = r"""
using System;
using System.Collections.Generic;
using Ansys.Ansoft.Edb.Cell;
using Ansys.Ansoft.Edb.Cell.Primitive;
using Ansys.Ansoft.Edb.Definition;
using Ansys.Ansoft.Edb.Geometry;
using Ansys.Ansoft.Edb.Utility;

namespace AuroraTranslator.DotNet
{
    public sealed class PadstackInstanceSnapshot
    {
        public bool HasId { get; set; }
        public ulong Id { get; set; }
        public string Name { get; set; }
        public string Type { get; set; }
        public string NetName { get; set; }
        public string ComponentName { get; set; }
        public string PlacementLayer { get; set; }
        public bool HasPosition { get; set; }
        public double X { get; set; }
        public double Y { get; set; }
        public double Rotation { get; set; }
        public string StartLayer { get; set; }
        public string StopLayer { get; set; }
        public string PadstackDefinition { get; set; }
        public bool HasIsLayoutPin { get; set; }
        public bool IsLayoutPin { get; set; }
    }

    public sealed class DisplayValueSnapshot
    {
        public bool HasValue { get; set; }
        public double Value { get; set; }
        public string Display { get; set; }
    }

    public sealed class PadPropertySnapshot
    {
        public string LayerName { get; set; }
        public int PadType { get; set; }
        public int GeometryType { get; set; }
        public string Shape { get; set; }
        public string OffsetX { get; set; }
        public string OffsetY { get; set; }
        public string Rotation { get; set; }
        public DisplayValueSnapshot[] Parameters { get; set; }
        public double[] RawPoints { get; set; }
    }

    public sealed class PadstackDefinitionSnapshot
    {
        public string Name { get; set; }
        public string Material { get; set; }
        public string HoleType { get; set; }
        public string HoleRange { get; set; }
        public bool HasHoleDiameter { get; set; }
        public double HoleDiameter { get; set; }
        public string HoleDiameterString { get; set; }
        public bool HasHoleFinishedSize { get; set; }
        public double HoleFinishedSize { get; set; }
        public string HoleOffsetX { get; set; }
        public string HoleOffsetY { get; set; }
        public string HoleRotation { get; set; }
        public bool HasHolePlatingRatio { get; set; }
        public double HolePlatingRatio { get; set; }
        public bool HasHolePlatingThickness { get; set; }
        public double HolePlatingThickness { get; set; }
        public double[] HoleProperties { get; set; }
        public string[] ViaLayers { get; set; }
        public string ViaStartLayer { get; set; }
        public string ViaStopLayer { get; set; }
        public PadPropertySnapshot[] PadByLayer { get; set; }
        public PadPropertySnapshot[] AntiPadByLayer { get; set; }
        public PadPropertySnapshot[] ThermalPadByLayer { get; set; }
    }

    public static class PadstackInstanceExtractor
    {
        public static PadstackInstanceSnapshot GetSnapshot(PadstackInstance padstack)
        {
            PadstackInstanceSnapshot snapshot = new PadstackInstanceSnapshot();
            if (padstack == null)
            {
                return snapshot;
            }

            try
            {
                if (padstack.IsNull())
                {
                    return snapshot;
                }
            }
            catch
            {
            }

            try
            {
                snapshot.Id = padstack.GetId();
                snapshot.HasId = true;
            }
            catch
            {
                snapshot.HasId = false;
            }

            try
            {
                snapshot.Name = padstack.GetName();
            }
            catch
            {
                snapshot.Name = null;
            }

            try
            {
                snapshot.Type = padstack.GetType().ToString();
            }
            catch
            {
                snapshot.Type = null;
            }

            Ansys.Ansoft.Edb.Cell.Hierarchy.Component component = null;
            try
            {
                component = padstack.GetComponent();
                if (component != null && !component.IsNull())
                {
                    snapshot.ComponentName = component.GetName();
                }
            }
            catch
            {
                component = null;
                snapshot.ComponentName = null;
            }

            try
            {
                var net = padstack.GetNet();
                if (net != null && !net.IsNull())
                {
                    snapshot.NetName = net.GetName();
                }
            }
            catch
            {
                snapshot.NetName = null;
            }

            try
            {
                var group = padstack.GetGroup();
                if (group != null && !group.IsNull())
                {
                    var placementLayer = group.GetPlacementLayer();
                    if (placementLayer != null && !placementLayer.IsNull())
                    {
                        snapshot.PlacementLayer = placementLayer.GetName();
                    }
                }
            }
            catch
            {
                snapshot.PlacementLayer = null;
            }

            try
            {
                snapshot.IsLayoutPin = padstack.IsLayoutPin();
                snapshot.HasIsLayoutPin = true;
            }
            catch
            {
                snapshot.HasIsLayoutPin = false;
            }

            try
            {
                PointData point;
                Value rotation;
                bool valid = padstack.GetPositionAndRotationValue(out point, out rotation);
                if (valid)
                {
                    if (component != null && !component.IsNull())
                    {
                        var transform = component.GetTransform();
                        if (transform != null)
                        {
                            point = transform.TransformPoint(point);
                        }
                    }

                    snapshot.X = point.X.ToDouble();
                    snapshot.Y = point.Y.ToDouble();
                    snapshot.Rotation = rotation.ToDouble();
                    snapshot.HasPosition = true;
                }
            }
            catch
            {
                snapshot.HasPosition = false;
            }

            try
            {
                ILayerReadOnly startLayer;
                ILayerReadOnly stopLayer;
                bool valid = padstack.GetLayerRange(out startLayer, out stopLayer);
                if (valid)
                {
                    if (startLayer != null && !startLayer.IsNull())
                    {
                        snapshot.StartLayer = startLayer.GetName();
                    }
                    if (stopLayer != null && !stopLayer.IsNull())
                    {
                        snapshot.StopLayer = stopLayer.GetName();
                    }
                }
            }
            catch
            {
                snapshot.StartLayer = null;
                snapshot.StopLayer = null;
            }

            try
            {
                var definition = padstack.GetPadstackDef();
                if (definition != null && !definition.IsNull())
                {
                    snapshot.PadstackDefinition = definition.GetName();
                }
            }
            catch
            {
                snapshot.PadstackDefinition = null;
            }

            return snapshot;
        }

        public static PadstackInstanceSnapshot[] GetSnapshots(Array padstacks)
        {
            if (padstacks == null)
            {
                return new PadstackInstanceSnapshot[0];
            }

            PadstackInstanceSnapshot[] snapshots = new PadstackInstanceSnapshot[padstacks.Length];
            for (int i = 0; i < padstacks.Length; i++)
            {
                snapshots[i] = GetSnapshot(padstacks.GetValue(i) as PadstackInstance);
            }
            return snapshots;
        }
    }

    public static class PadstackDefinitionExtractor
    {
        public static PadstackDefinitionSnapshot GetSnapshot(PadstackDef padstack)
        {
            PadstackDefinitionSnapshot snapshot = new PadstackDefinitionSnapshot();
            snapshot.PadByLayer = new PadPropertySnapshot[0];
            snapshot.AntiPadByLayer = new PadPropertySnapshot[0];
            snapshot.ThermalPadByLayer = new PadPropertySnapshot[0];
            snapshot.HoleProperties = new double[0];
            snapshot.ViaLayers = new string[0];

            if (padstack == null || padstack.IsNull())
            {
                return snapshot;
            }

            try
            {
                snapshot.Name = padstack.GetName();
            }
            catch
            {
                snapshot.Name = null;
            }

            PadstackDefData data = null;
            try
            {
                data = new PadstackDefData(padstack.GetData());
            }
            catch
            {
                data = null;
            }

            if (data == null)
            {
                return snapshot;
            }

            try
            {
                snapshot.Material = data.GetMaterial();
            }
            catch
            {
                snapshot.Material = null;
            }

            List<string> layerNames = new List<string>();
            try
            {
                foreach (string layerName in data.GetLayerNames())
                {
                    layerNames.Add(layerName);
                }
            }
            catch
            {
            }
            snapshot.ViaLayers = layerNames.ToArray();
            if (layerNames.Count > 0)
            {
                snapshot.ViaStartLayer = layerNames[0];
                snapshot.ViaStopLayer = layerNames[layerNames.Count - 1];
            }

            try
            {
                snapshot.HoleRange = data.GetHoleRange().ToString();
            }
            catch
            {
                snapshot.HoleRange = null;
            }

            try
            {
                snapshot.HolePlatingRatio = data.GetHolePlatingPercentage();
                snapshot.HasHolePlatingRatio = true;
            }
            catch
            {
                snapshot.HasHolePlatingRatio = false;
            }

            PadGeometryType holeGeometryType;
            IList<Value> holeParameters;
            Value holeOffsetX;
            Value holeOffsetY;
            Value holeRotation;
            try
            {
                data.GetHoleParametersValue(
                    out holeGeometryType,
                    out holeParameters,
                    out holeOffsetX,
                    out holeOffsetY,
                    out holeRotation
                );
                snapshot.HoleType = holeGeometryType.ToString();
                snapshot.HoleOffsetX = ValueToString(holeOffsetX);
                snapshot.HoleOffsetY = ValueToString(holeOffsetY);
                snapshot.HoleRotation = ValueToString(holeRotation);
                snapshot.HoleProperties = ValueListToDoubles(holeParameters);
                if (holeParameters != null && holeParameters.Count > 0)
                {
                    Value diameter = holeParameters[0];
                    snapshot.HoleDiameter = ValueToDouble(diameter);
                    snapshot.HoleDiameterString = ValueToString(diameter);
                    snapshot.HasHoleDiameter = true;
                }
            }
            catch
            {
            }

            if (snapshot.HoleProperties.Length > 0)
            {
                double platingRatio = snapshot.HasHolePlatingRatio ? snapshot.HolePlatingRatio : 0.0;
                double platingThickness = (snapshot.HoleProperties[0] * platingRatio / 100.0) / 2.0;
                snapshot.HolePlatingThickness = platingThickness;
                snapshot.HasHolePlatingThickness = true;
                snapshot.HoleFinishedSize = snapshot.HoleProperties[0] - (platingThickness * 2.0);
                snapshot.HasHoleFinishedSize = true;
            }
            else
            {
                snapshot.HolePlatingThickness = 0.0;
                snapshot.HasHolePlatingThickness = true;
                snapshot.HoleFinishedSize = 0.0;
                snapshot.HasHoleFinishedSize = true;
            }

            snapshot.PadByLayer = BuildPadProperties(data, layerNames, PadType.RegularPad, 0);
            snapshot.AntiPadByLayer = BuildPadProperties(data, layerNames, PadType.AntiPad, 1);
            snapshot.ThermalPadByLayer = BuildPadProperties(data, layerNames, PadType.ThermalPad, 2);
            return snapshot;
        }

        private static PadPropertySnapshot[] BuildPadProperties(
            PadstackDefData data,
            List<string> layerNames,
            PadType padType,
            int padTypeNumber
        )
        {
            List<PadPropertySnapshot> snapshots = new List<PadPropertySnapshot>();
            foreach (string layerName in layerNames)
            {
                snapshots.Add(GetPadProperty(data, layerName, padType, padTypeNumber));
            }
            return snapshots.ToArray();
        }

        private static PadPropertySnapshot GetPadProperty(
            PadstackDefData data,
            string layerName,
            PadType padType,
            int padTypeNumber
        )
        {
            PadPropertySnapshot snapshot = new PadPropertySnapshot();
            snapshot.LayerName = layerName;
            snapshot.PadType = padTypeNumber;
            snapshot.Parameters = new DisplayValueSnapshot[0];
            snapshot.RawPoints = new double[0];

            PadGeometryType geometryType;
            IList<Value> parameters;
            Value offsetX;
            Value offsetY;
            Value rotation;
            try
            {
                data.GetPadParametersValue(
                    layerName,
                    padType,
                    out geometryType,
                    out parameters,
                    out offsetX,
                    out offsetY,
                    out rotation
                );
                snapshot.GeometryType = (int)geometryType;
                snapshot.Shape = geometryType.ToString();
                snapshot.OffsetX = ValueToString(offsetX);
                snapshot.OffsetY = ValueToString(offsetY);
                snapshot.Rotation = ValueToString(rotation);
                snapshot.Parameters = ValueListToDisplayValues(parameters);
            }
            catch
            {
            }

            TryPopulatePolygonalPad(data, layerName, padType, snapshot);

            return snapshot;
        }

        private static void TryPopulatePolygonalPad(
            PadstackDefData data,
            string layerName,
            PadType padType,
            PadPropertySnapshot snapshot
        )
        {
            PolygonData polygonData;
            double offsetX;
            double offsetY;
            double rotation;
            try
            {
                bool hasPolygon = data.GetPolygonalPadParameters(
                    layerName,
                    padType,
                    out polygonData,
                    out offsetX,
                    out offsetY,
                    out rotation
                );
                if (!hasPolygon || polygonData == null || polygonData.Count < 3)
                {
                    return;
                }
                snapshot.Shape = "Polygon";
                snapshot.OffsetX = offsetX.ToString("R", System.Globalization.CultureInfo.InvariantCulture);
                snapshot.OffsetY = offsetY.ToString("R", System.Globalization.CultureInfo.InvariantCulture);
                snapshot.Rotation = rotation.ToString("R", System.Globalization.CultureInfo.InvariantCulture);
                snapshot.RawPoints = PolygonToFlatArray(polygonData);
            }
            catch
            {
            }
        }

        private static double[] PolygonToFlatArray(PolygonData polygon)
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

        private static DisplayValueSnapshot[] ValueListToDisplayValues(IList<Value> values)
        {
            if (values == null)
            {
                return new DisplayValueSnapshot[0];
            }

            DisplayValueSnapshot[] snapshots = new DisplayValueSnapshot[values.Count];
            for (int i = 0; i < values.Count; i++)
            {
                snapshots[i] = ValueToDisplayValue(values[i]);
            }
            return snapshots;
        }

        private static double[] ValueListToDoubles(IList<Value> values)
        {
            if (values == null)
            {
                return new double[0];
            }

            double[] doubles = new double[values.Count];
            for (int i = 0; i < values.Count; i++)
            {
                doubles[i] = ValueToDouble(values[i]);
            }
            return doubles;
        }

        private static DisplayValueSnapshot ValueToDisplayValue(Value value)
        {
            DisplayValueSnapshot snapshot = new DisplayValueSnapshot();
            if (value == null)
            {
                snapshot.HasValue = false;
                snapshot.Display = null;
                return snapshot;
            }

            try
            {
                snapshot.Value = value.ToDouble();
                snapshot.HasValue = true;
            }
            catch
            {
                snapshot.HasValue = false;
            }

            snapshot.Display = ValueToString(value);
            return snapshot;
        }

        private static double ValueToDouble(Value value)
        {
            if (value == null)
            {
                return 0.0;
            }

            try
            {
                return value.ToDouble();
            }
            catch
            {
                return 0.0;
            }
        }

        private static string ValueToString(Value value)
        {
            if (value == null)
            {
                return null;
            }

            try
            {
                return value.ToString();
            }
            catch
            {
                return null;
            }
        }
    }
}
""".strip()


def snapshot_from_padstack_instance_dotnet(
    raw_padstack: Any,
) -> DotNetPadstackSnapshot | None:
    """Return a padstack instance field snapshot through a small .NET helper."""

    extractor = _padstack_extractor_type(raw_padstack)
    if extractor is None:
        return None

    try:
        snapshot = extractor.GetSnapshot(raw_padstack)
        return _dotnet_padstack_snapshot(snapshot)
    except Exception:
        logger.debug(
            "Failed to extract padstack instance snapshot through .NET helper",
            exc_info=True,
        )
        return None


def snapshots_from_padstack_instances_dotnet(
    raw_padstacks: list[Any],
) -> list[DotNetPadstackSnapshot] | None:
    """Return padstack instance snapshots through one .NET batch call."""

    if not raw_padstacks:
        return []

    first_padstack = next((item for item in raw_padstacks if item is not None), None)
    if first_padstack is None:
        return None

    extractor = _padstack_extractor_type(first_padstack)
    if extractor is None:
        return None

    try:
        import System

        array = System.Array.CreateInstance(
            first_padstack.GetType(), len(raw_padstacks)
        )
        for index, raw_padstack in enumerate(raw_padstacks):
            array.SetValue(raw_padstack, index)
        snapshots = extractor.GetSnapshots(array)
        return [_dotnet_padstack_snapshot(snapshot) for snapshot in snapshots]
    except Exception:
        logger.debug(
            "Failed to extract padstack instance snapshots through .NET batch helper",
            exc_info=True,
        )
        return None


def snapshot_from_padstack_definition_dotnet(
    raw_padstack_definition: Any,
) -> DotNetPadstackDefinitionSnapshot | None:
    """Return a padstack definition field snapshot through the .NET helper."""

    extractor = _padstack_definition_extractor_type(raw_padstack_definition)
    if extractor is None:
        return None

    try:
        snapshot = extractor.GetSnapshot(raw_padstack_definition)
        return DotNetPadstackDefinitionSnapshot(
            name=snapshot.Name,
            material=snapshot.Material,
            hole_type=snapshot.HoleType,
            hole_range=snapshot.HoleRange,
            hole_diameter=snapshot.HoleDiameter
            if bool(snapshot.HasHoleDiameter)
            else None,
            hole_diameter_string=snapshot.HoleDiameterString,
            hole_finished_size=snapshot.HoleFinishedSize
            if bool(snapshot.HasHoleFinishedSize)
            else None,
            hole_offset_x=snapshot.HoleOffsetX,
            hole_offset_y=snapshot.HoleOffsetY,
            hole_rotation=snapshot.HoleRotation,
            hole_plating_ratio=snapshot.HolePlatingRatio
            if bool(snapshot.HasHolePlatingRatio)
            else None,
            hole_plating_thickness=snapshot.HolePlatingThickness
            if bool(snapshot.HasHolePlatingThickness)
            else None,
            hole_properties=tuple(snapshot.HoleProperties)
            if snapshot.HoleProperties is not None
            else None,
            via_layers=tuple(snapshot.ViaLayers)
            if snapshot.ViaLayers is not None
            else (),
            via_start_layer=snapshot.ViaStartLayer,
            via_stop_layer=snapshot.ViaStopLayer,
            pad_by_layer=_pad_property_snapshots(snapshot.PadByLayer),
            antipad_by_layer=_pad_property_snapshots(snapshot.AntiPadByLayer),
            thermalpad_by_layer=_pad_property_snapshots(snapshot.ThermalPadByLayer),
        )
    except Exception:
        logger.debug(
            "Failed to extract padstack definition snapshot through .NET helper",
            exc_info=True,
        )
        return None


def _dotnet_padstack_snapshot(snapshot: Any) -> DotNetPadstackSnapshot:
    return DotNetPadstackSnapshot(
        id=int(snapshot.Id) if bool(snapshot.HasId) else None,
        name=snapshot.Name,
        type=snapshot.Type,
        net_name=snapshot.NetName,
        component_name=snapshot.ComponentName,
        placement_layer=snapshot.PlacementLayer,
        has_position=bool(snapshot.HasPosition),
        x=snapshot.X,
        y=snapshot.Y,
        rotation=snapshot.Rotation,
        start_layer=snapshot.StartLayer,
        stop_layer=snapshot.StopLayer,
        padstack_definition=snapshot.PadstackDefinition,
        has_is_layout_pin=bool(snapshot.HasIsLayoutPin),
        is_layout_pin=bool(snapshot.IsLayoutPin),
    )


def _pad_property_snapshots(values: Any) -> tuple[DotNetPadPropertySnapshot, ...]:
    if values is None:
        return ()
    return tuple(_pad_property_snapshot(value) for value in values)


def _pad_property_snapshot(value: Any) -> DotNetPadPropertySnapshot:
    return DotNetPadPropertySnapshot(
        layer_name=value.LayerName,
        pad_type=int(value.PadType),
        geometry_type=int(value.GeometryType),
        shape=value.Shape,
        offset_x=value.OffsetX,
        offset_y=value.OffsetY,
        rotation=value.Rotation,
        parameters=tuple(
            DotNetDisplayValue(
                tofloat=parameter.Value if bool(parameter.HasValue) else None,
                tostring=parameter.Display,
            )
            for parameter in value.Parameters
        )
        if value.Parameters is not None
        else (),
        raw_points=_point_pairs_from_flat_array(value.RawPoints),
    )


def _point_pairs_from_flat_array(values: Any) -> tuple[tuple[float, float], ...]:
    if values is None:
        return ()
    raw_values = list(values)
    points: list[tuple[float, float]] = []
    for index in range(0, len(raw_values) - 1, 2):
        points.append((float(raw_values[index]), float(raw_values[index + 1])))
    return tuple(points)


def _padstack_extractor_type(raw_padstack: Any) -> Any | None:
    global _PADSTACK_EXTRACTOR_ATTEMPTED, _PADSTACK_EXTRACTOR_TYPE

    if _PADSTACK_EXTRACTOR_ATTEMPTED:
        return _PADSTACK_EXTRACTOR_TYPE
    _PADSTACK_EXTRACTOR_ATTEMPTED = True

    assembly_location = _edb_assembly_location(raw_padstack)
    if assembly_location is None:
        return None

    csc_path = _csc_path()
    if csc_path is None:
        logger.debug("C# compiler not found; using Python padstack extraction")
        return None

    try:
        import clr

        helper_path = _compile_padstack_extractor(csc_path, assembly_location)
        clr.AddReference(str(assembly_location))
        clr.AddReference(str(helper_path))
        from AuroraTranslator.DotNet import PadstackInstanceExtractor

        _PADSTACK_EXTRACTOR_TYPE = PadstackInstanceExtractor
        return _PADSTACK_EXTRACTOR_TYPE
    except Exception:
        logger.debug(
            "Failed to load .NET padstack instance extractor; using Python fallback",
            exc_info=True,
        )
        _PADSTACK_EXTRACTOR_TYPE = None
        return None


def _padstack_definition_extractor_type(raw_padstack_definition: Any) -> Any | None:
    global _PADSTACK_DEFINITION_EXTRACTOR_ATTEMPTED, _PADSTACK_DEFINITION_EXTRACTOR_TYPE

    if _PADSTACK_DEFINITION_EXTRACTOR_ATTEMPTED:
        return _PADSTACK_DEFINITION_EXTRACTOR_TYPE
    _PADSTACK_DEFINITION_EXTRACTOR_ATTEMPTED = True

    assembly_location = _edb_assembly_location(raw_padstack_definition)
    if assembly_location is None:
        return None

    csc_path = _csc_path()
    if csc_path is None:
        logger.debug(
            "C# compiler not found; using Python padstack definition extraction"
        )
        return None

    try:
        import clr

        helper_path = _compile_padstack_extractor(csc_path, assembly_location)
        clr.AddReference(str(assembly_location))
        clr.AddReference(str(helper_path))
        from AuroraTranslator.DotNet import PadstackDefinitionExtractor

        _PADSTACK_DEFINITION_EXTRACTOR_TYPE = PadstackDefinitionExtractor
        return _PADSTACK_DEFINITION_EXTRACTOR_TYPE
    except Exception:
        logger.debug(
            "Failed to load .NET padstack definition extractor; using Python fallback",
            exc_info=True,
        )
        _PADSTACK_DEFINITION_EXTRACTOR_TYPE = None
        return None


def _edb_assembly_location(raw_padstack: Any) -> Path | None:
    try:
        location = raw_padstack.GetType().Assembly.Location
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


def _compile_padstack_extractor(csc_path: Path, edb_assembly: Path) -> Path:
    cache_dir = Path(tempfile.gettempdir()) / "aurora_translator_dotnet"
    cache_dir.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256(
        (
            str(edb_assembly.resolve()).casefold() + "\n" + _PADSTACK_EXTRACTOR_SOURCE
        ).encode("utf-8")
    ).hexdigest()[:16]
    source_path = cache_dir / f"PadstackInstanceExtractor_{digest}.cs"
    helper_path = cache_dir / f"PadstackInstanceExtractor_{digest}.dll"

    if helper_path.exists():
        return helper_path

    source_path.write_text(_PADSTACK_EXTRACTOR_SOURCE, encoding="utf-8")
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
            "Failed to compile .NET padstack instance extractor: "
            f"{completed.stdout.strip()} {completed.stderr.strip()}".strip()
        )
    return helper_path
