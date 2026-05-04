from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from aurora_translator.sources.aedb.models import (
    PadPropertyModel,
    PadstackDefinitionModel,
    PadstackInstanceModel,
    PadstacksModel,
)
from aurora_translator.sources.aedb.normalizers import safe_getattr
from aurora_translator.shared.logging import log_field_block, log_timing

from .context import ExtractionContext
from .dotnet_padstacks import (
    DotNetPadPropertySnapshot,
    snapshot_from_padstack_definition_dotnet,
)
from .padstack_records import (
    PadstackInstanceRecord,
    build_padstack_instance_record,
    padstack_record_to_instance_data,
)
from .precision import COORDINATE_DIGITS, ROTATION_DIGITS


logger = logging.getLogger("aurora_translator.aedb.extractors.padstacks")


@dataclass(slots=True)
class PadstackDefinitionProfile:
    """Aggregated timing counters for padstack definition extraction."""

    definitions: int = 0
    pad_by_layer_entries: int = 0
    antipad_by_layer_entries: int = 0
    thermalpad_by_layer_entries: int = 0
    pad_properties: int = 0
    snapshot_successes: int = 0
    snapshot_fallbacks: int = 0
    snapshot_seconds: float = 0.0
    basic_fields_seconds: float = 0.0
    hole_fields_seconds: float = 0.0
    via_fields_seconds: float = 0.0
    layer_map_lookup_seconds: float = 0.0
    pad_by_layer_seconds: float = 0.0
    antipad_by_layer_seconds: float = 0.0
    thermalpad_by_layer_seconds: float = 0.0
    pad_property_field_seconds: float = 0.0
    pad_property_model_seconds: float = 0.0
    definition_model_seconds: float = 0.0


def _record_profile_time(profile: Any | None, field_name: str, start: float) -> None:
    if profile is not None:
        setattr(
            profile, field_name, getattr(profile, field_name) + perf_counter() - start
        )


def _log_padstack_definition_summary(
    definitions: list[PadstackDefinitionModel],
) -> None:
    if not definitions:
        return

    log_field_block(
        logger,
        "Parsed padstack definitions",
        fields={
            "definitions": len(definitions),
            "pad_layers": sum(len(item.pad_by_layer) for item in definitions),
            "antipad_layers": sum(len(item.antipad_by_layer) for item in definitions),
            "thermalpad_layers": sum(
                len(item.thermalpad_by_layer) for item in definitions
            ),
        },
    )


def _log_padstack_instance_summary(instances: list[PadstackInstanceModel]) -> None:
    if not instances:
        return

    log_field_block(
        logger,
        "Parsed padstack instances",
        fields={"instances": len(instances)},
    )


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


def _dotnet_name_or_none(value: Any) -> str | None:
    if value is None or _is_null_dotnet_object(value):
        return None
    try:
        return value.GetName()
    except Exception:
        return None


def _padstack_raw_object(padstack: Any) -> Any:
    if callable(safe_getattr(padstack, "GetPositionAndRotationValue")):
        return padstack
    return safe_getattr(padstack, "_edb_padstackinstance") or safe_getattr(
        padstack, "core"
    )


def _padstack_definition_raw_object(padstack: Any) -> Any:
    if callable(safe_getattr(padstack, "GetData")):
        return padstack
    return safe_getattr(padstack, "edb_padstack") or safe_getattr(
        padstack, "_edb_object"
    )


def _padstack_definition_name(padstack: Any) -> str | None:
    raw_padstack = _padstack_raw_object(padstack)
    if raw_padstack is not None:
        definition_name = _dotnet_name_or_none(
            _call_or_none(raw_padstack, "GetPadstackDef")
        )
        if definition_name is not None:
            return definition_name

    return safe_getattr(safe_getattr(padstack, "definition"), "name") or safe_getattr(
        padstack,
        "padstack_definition",
    )


def _padstack_position_and_rotation(padstack: Any) -> tuple[Any, Any]:
    raw_padstack = _padstack_raw_object(padstack)
    if raw_padstack is not None:
        try:
            valid, point, rotation = raw_padstack.GetPositionAndRotationValue()
            if not valid:
                return [], 0.0

            component = raw_padstack.GetComponent()
            if component is not None and not _is_null_dotnet_object(component):
                transform = component.GetTransform()
                if transform is not None:
                    point = transform.TransformPoint(point)

            return [
                round(point.X.ToDouble(), COORDINATE_DIGITS),
                round(point.Y.ToDouble(), COORDINATE_DIGITS),
            ], round(rotation.ToDouble(), ROTATION_DIGITS)
        except Exception:
            pass

    position_and_rotation = safe_getattr(padstack, "position_and_rotation")
    try:
        if position_and_rotation and len(position_and_rotation) >= 3:
            return [
                position_and_rotation[0],
                position_and_rotation[1],
            ], position_and_rotation[2]
    except TypeError:
        pass

    return safe_getattr(padstack, "position"), safe_getattr(padstack, "rotation")


_PAD_PARAMETER_NAMES_BY_SHAPE = {
    "Circle": ("Diameter",),
    "Square": ("Size",),
    "Rectangle": ("XSize", "YSize"),
    "Oval": ("XSize", "YSize", "CornerRadius"),
    "Bullet": ("XSize", "YSize", "CornerRadius"),
    "NSidedPolygon": ("Size", "NumSides"),
    "Round45": ("Inner", "ChannelWidth", "IsolationGap"),
    "Round90": ("Inner", "ChannelWidth", "IsolationGap"),
}


def _pascal_to_snake(value: str | None) -> str | None:
    if not value:
        return value
    chars: list[str] = []
    for index, char in enumerate(value):
        if char.isupper() and index > 0:
            previous = value[index - 1]
            next_char = value[index + 1] if index + 1 < len(value) else ""
            if not previous.isupper() or (next_char and next_char.islower()):
                chars.append("_")
        chars.append(char.lower())
    return "".join(chars)


def _pad_parameters_from_snapshot(
    pad_property: DotNetPadPropertySnapshot,
) -> dict[str, Any]:
    parameter_names = _PAD_PARAMETER_NAMES_BY_SHAPE.get(pad_property.shape or "", ())
    return {
        parameter_name: pad_property.parameters[index]
        for index, parameter_name in enumerate(parameter_names)
        if index < len(pad_property.parameters)
    }


def _extract_pad_property_from_snapshot(
    pad_property: DotNetPadPropertySnapshot,
    profile: PadstackDefinitionProfile | None = None,
) -> PadPropertyModel:
    if profile is not None:
        profile.pad_properties += 1

    start = perf_counter() if profile is not None else 0.0
    data = {
        "pad_type": pad_property.pad_type,
        "geometry_type": pad_property.geometry_type,
        "shape": pad_property.shape,
        "offset_x": pad_property.offset_x,
        "offset_y": pad_property.offset_y,
        "rotation": pad_property.rotation,
        "parameters": _pad_parameters_from_snapshot(pad_property),
        "raw_points": list(pad_property.raw_points),
    }
    _record_profile_time(profile, "pad_property_field_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    model = PadPropertyModel.model_validate(data)
    _record_profile_time(profile, "pad_property_model_seconds", start)
    return model


def _extract_snapshot_pad_property_map(
    values: tuple[DotNetPadPropertySnapshot, ...],
    profile: PadstackDefinitionProfile | None = None,
) -> dict[str, PadPropertyModel]:
    return {
        pad_property.layer_name: _extract_pad_property_from_snapshot(
            pad_property, profile
        )
        for pad_property in values
    }


def _padstack_layer_fields(
    padstack: Any, signal_layer_names: list[str]
) -> tuple[Any, Any, Any]:
    raw_padstack = _padstack_raw_object(padstack)
    if raw_padstack is not None:
        try:
            _, start_layer, stop_layer = raw_padstack.GetLayerRange()
            start_layer_name = _dotnet_name_or_none(start_layer)
            stop_layer_name = _dotnet_name_or_none(stop_layer)
            if start_layer_name is not None and stop_layer_name is not None:
                return (
                    start_layer_name,
                    stop_layer_name,
                    _layer_range_names(
                        signal_layer_names, start_layer_name, stop_layer_name
                    ),
                )
            return (
                start_layer_name,
                stop_layer_name,
                safe_getattr(padstack, "layer_range_names"),
            )
        except Exception:
            pass

    return (
        safe_getattr(padstack, "start_layer"),
        safe_getattr(padstack, "stop_layer"),
        safe_getattr(padstack, "layer_range_names"),
    )


def _layer_range_names(
    signal_layer_names: list[str], start_layer_name: str, stop_layer_name: str
) -> list[str]:
    layer_names: list[str] = []
    started = False
    for layer_name in signal_layer_names:
        if started:
            layer_names.append(layer_name)
            if layer_name == stop_layer_name or layer_name == start_layer_name:
                break
        elif layer_name == start_layer_name:
            started = True
            layer_names.append(layer_name)
            if layer_name == stop_layer_name:
                break
        elif layer_name == stop_layer_name:
            started = True
            layer_names.append(layer_name)
            if layer_name == start_layer_name:
                break
    return layer_names


def extract_pad_property(
    pad_property: Any,
    profile: PadstackDefinitionProfile | None = None,
) -> PadPropertyModel:
    if profile is not None:
        profile.pad_properties += 1

    start = perf_counter() if profile is not None else 0.0
    data = {
        "pad_type": safe_getattr(pad_property, "pad_type"),
        "geometry_type": safe_getattr(pad_property, "geometry_type"),
        "shape": safe_getattr(pad_property, "shape"),
        "offset_x": safe_getattr(pad_property, "offset_x"),
        "offset_y": safe_getattr(pad_property, "offset_y"),
        "rotation": safe_getattr(pad_property, "rotation"),
        "parameters": safe_getattr(pad_property, "parameters", {}) or {},
        "raw_points": safe_getattr(pad_property, "raw_points", []) or [],
    }
    _record_profile_time(profile, "pad_property_field_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    model = PadPropertyModel.model_validate(data)
    _record_profile_time(profile, "pad_property_model_seconds", start)
    return model


def _extract_pad_property_map(
    values: dict[Any, Any],
    profile: PadstackDefinitionProfile | None = None,
) -> dict[str, PadPropertyModel]:
    return {
        str(layer_name): extract_pad_property(pad_property, profile)
        for layer_name, pad_property in values.items()
    }


def _extract_padstack_definition_from_snapshot(
    snapshot: Any,
    profile: PadstackDefinitionProfile | None = None,
) -> PadstackDefinitionModel:
    if profile is not None:
        profile.pad_by_layer_entries += len(snapshot.pad_by_layer)
        profile.antipad_by_layer_entries += len(snapshot.antipad_by_layer)
        profile.thermalpad_by_layer_entries += len(snapshot.thermalpad_by_layer)

    start = perf_counter() if profile is not None else 0.0
    basic_data = {
        "name": snapshot.name,
        "material": snapshot.material,
    }
    _record_profile_time(profile, "basic_fields_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    hole_properties = (
        list(snapshot.hole_properties) if snapshot.hole_properties is not None else None
    )
    hole_finished_size: Any = snapshot.hole_finished_size
    hole_plating_thickness: Any = snapshot.hole_plating_thickness
    if hole_properties == []:
        hole_finished_size = 0
        hole_plating_thickness = 0
    hole_data = {
        "hole_type": snapshot.hole_type,
        "hole_range": _pascal_to_snake(snapshot.hole_range),
        "hole_diameter": snapshot.hole_diameter,
        "hole_diameter_string": snapshot.hole_diameter_string,
        "hole_finished_size": hole_finished_size,
        "hole_offset_x": snapshot.hole_offset_x,
        "hole_offset_y": snapshot.hole_offset_y,
        "hole_rotation": snapshot.hole_rotation,
        "hole_plating_ratio": snapshot.hole_plating_ratio,
        "hole_plating_thickness": hole_plating_thickness,
        "hole_properties": hole_properties,
    }
    _record_profile_time(profile, "hole_fields_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    via_data = {
        "via_layers": list(snapshot.via_layers),
        "via_start_layer": snapshot.via_start_layer,
        "via_stop_layer": snapshot.via_stop_layer,
    }
    _record_profile_time(profile, "via_fields_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    pad_by_layer = _extract_snapshot_pad_property_map(snapshot.pad_by_layer, profile)
    _record_profile_time(profile, "pad_by_layer_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    antipad_by_layer = _extract_snapshot_pad_property_map(
        snapshot.antipad_by_layer, profile
    )
    _record_profile_time(profile, "antipad_by_layer_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    thermalpad_by_layer = _extract_snapshot_pad_property_map(
        snapshot.thermalpad_by_layer, profile
    )
    _record_profile_time(profile, "thermalpad_by_layer_seconds", start)

    data = {
        **basic_data,
        **hole_data,
        **via_data,
        "pad_by_layer": pad_by_layer,
        "antipad_by_layer": antipad_by_layer,
        "thermalpad_by_layer": thermalpad_by_layer,
    }
    start = perf_counter() if profile is not None else 0.0
    model = PadstackDefinitionModel.model_validate(data)
    _record_profile_time(profile, "definition_model_seconds", start)
    return model


def extract_padstack_definition(
    padstack: Any,
    profile: PadstackDefinitionProfile | None = None,
) -> PadstackDefinitionModel:
    if profile is not None:
        profile.definitions += 1

    raw_definition = _padstack_definition_raw_object(padstack)
    if raw_definition is not None:
        start = perf_counter() if profile is not None else 0.0
        snapshot = snapshot_from_padstack_definition_dotnet(raw_definition)
        _record_profile_time(profile, "snapshot_seconds", start)
        if snapshot is not None:
            if profile is not None:
                profile.snapshot_successes += 1
            return _extract_padstack_definition_from_snapshot(snapshot, profile)
        if profile is not None:
            profile.snapshot_fallbacks += 1

    start = perf_counter() if profile is not None else 0.0
    basic_data = {
        "name": safe_getattr(padstack, "name"),
        "material": safe_getattr(padstack, "material"),
    }
    _record_profile_time(profile, "basic_fields_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    hole_data = {
        "hole_type": safe_getattr(padstack, "hole_type"),
        "hole_range": safe_getattr(padstack, "hole_range"),
        "hole_diameter": safe_getattr(padstack, "hole_diameter"),
        "hole_diameter_string": safe_getattr(padstack, "hole_diameter_string"),
        "hole_finished_size": safe_getattr(padstack, "hole_finished_size"),
        "hole_offset_x": safe_getattr(padstack, "hole_offset_x"),
        "hole_offset_y": safe_getattr(padstack, "hole_offset_y"),
        "hole_rotation": safe_getattr(padstack, "hole_rotation"),
        "hole_plating_ratio": safe_getattr(padstack, "hole_plating_ratio"),
        "hole_plating_thickness": safe_getattr(padstack, "hole_plating_thickness"),
        "hole_properties": safe_getattr(padstack, "hole_properties"),
    }
    _record_profile_time(profile, "hole_fields_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    via_data = {
        "via_layers": safe_getattr(padstack, "via_layers"),
        "via_start_layer": safe_getattr(padstack, "via_start_layer"),
        "via_stop_layer": safe_getattr(padstack, "via_stop_layer"),
    }
    _record_profile_time(profile, "via_fields_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    pad_by_layer_values = safe_getattr(padstack, "pad_by_layer") or {}
    antipad_by_layer_values = safe_getattr(padstack, "antipad_by_layer") or {}
    thermalpad_by_layer_values = safe_getattr(padstack, "thermalpad_by_layer") or {}
    _record_profile_time(profile, "layer_map_lookup_seconds", start)
    if profile is not None:
        profile.pad_by_layer_entries += len(pad_by_layer_values)
        profile.antipad_by_layer_entries += len(antipad_by_layer_values)
        profile.thermalpad_by_layer_entries += len(thermalpad_by_layer_values)

    start = perf_counter() if profile is not None else 0.0
    pad_by_layer = _extract_pad_property_map(pad_by_layer_values, profile)
    _record_profile_time(profile, "pad_by_layer_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    antipad_by_layer = _extract_pad_property_map(antipad_by_layer_values, profile)
    _record_profile_time(profile, "antipad_by_layer_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    thermalpad_by_layer = _extract_pad_property_map(thermalpad_by_layer_values, profile)
    _record_profile_time(profile, "thermalpad_by_layer_seconds", start)

    data = {
        **basic_data,
        **hole_data,
        **via_data,
        "pad_by_layer": pad_by_layer,
        "antipad_by_layer": antipad_by_layer,
        "thermalpad_by_layer": thermalpad_by_layer,
    }
    start = perf_counter() if profile is not None else 0.0
    model = PadstackDefinitionModel.model_validate(data)
    _record_profile_time(profile, "definition_model_seconds", start)
    return model


def extract_padstack_instance(
    padstack: Any, signal_layer_names: list[str]
) -> PadstackInstanceModel:
    if isinstance(padstack, PadstackInstanceRecord):
        return PadstackInstanceModel.model_validate(
            padstack_record_to_instance_data(padstack)
        )

    if _padstack_raw_object(padstack) is padstack:
        record = build_padstack_instance_record(padstack, signal_layer_names)
        return PadstackInstanceModel.model_validate(
            padstack_record_to_instance_data(record)
        )

    position, rotation = _padstack_position_and_rotation(padstack)
    start_layer, stop_layer, layer_range_names = _padstack_layer_fields(
        padstack, signal_layer_names
    )

    return PadstackInstanceModel.model_validate(
        {
            "id": safe_getattr(padstack, "id"),
            "name": safe_getattr(padstack, "name"),
            "type": safe_getattr(padstack, "type"),
            "net_name": safe_getattr(padstack, "net_name"),
            "component_name": safe_getattr(padstack, "component_name"),
            "placement_layer": safe_getattr(padstack, "placement_layer"),
            "position": position,
            "rotation": rotation,
            "start_layer": start_layer,
            "stop_layer": stop_layer,
            "layer_range_names": layer_range_names,
            "padstack_definition": _padstack_definition_name(padstack),
            "is_pin": safe_getattr(padstack, "is_pin"),
        }
    )


def extract_padstacks(context: ExtractionContext) -> PadstacksModel:
    definition_values = context.padstack_definitions
    instance_values = context.padstack_instance_records
    with log_timing(
        logger,
        "serialize padstacks",
        definitions=len(definition_values),
        instances=len(instance_values),
    ):
        with log_timing(
            logger, "serialize padstack definitions", count=len(definition_values)
        ):
            definitions = [
                extract_padstack_definition(item, None) for item in definition_values
            ]
        _log_padstack_definition_summary(definitions)

        with log_timing(
            logger, "serialize padstack instances", count=len(instance_values)
        ):
            instances = [
                extract_padstack_instance(item, context.signal_layer_names)
                for item in instance_values
            ]
        _log_padstack_instance_summary(instances)

        with log_timing(logger, "sort padstacks"):
            definitions.sort(key=lambda item: item.name or "")
            instances.sort(
                key=lambda item: (item.component_name or "", item.name or "")
            )

        with log_timing(logger, "validate padstacks model"):
            model = PadstacksModel.model_validate(
                {
                    "definitions": definitions,
                    "instances": instances,
                }
            )
    return model
