from __future__ import annotations

from dataclasses import dataclass
import logging
from time import perf_counter
from typing import Any

from aurora_translator.sources.aedb.normalizers import safe_getattr
from aurora_translator.shared.logging import log_field_block

from .dotnet_padstacks import (
    DotNetPadstackSnapshot,
    snapshot_from_padstack_instance_dotnet,
    snapshots_from_padstack_instances_dotnet,
)
from .precision import COORDINATE_DIGITS, ROTATION_DIGITS


logger = logging.getLogger("aurora_translator.aedb.extractors.padstack_records")


@dataclass(frozen=True, slots=True)
class PadstackInstanceRecord:
    """Cached fields shared by component-pin and padstack-instance serialization."""

    source: Any
    id: Any
    name: Any
    type: Any
    net_name: Any
    count_net_name: Any
    component_name: Any
    component_refdes: str
    placement_layer: Any
    pin_placement_layer: Any
    position: Any
    rotation: Any
    start_layer: Any
    stop_layer: Any
    layer_range_names: Any
    padstack_definition: Any
    is_pin: Any
    is_layout_pin: bool
    pin_name: str


@dataclass(slots=True)
class PadstackRecordProfile:
    """Aggregated timing for padstack instance record extraction."""

    instances: int = 0
    snapshot_successes: int = 0
    snapshot_fallbacks: int = 0
    snapshot_seconds: float = 0.0
    snapshot_record_build_seconds: float = 0.0
    batch_snapshot_successes: int = 0
    batch_snapshot_fallbacks: int = 0
    batch_snapshot_seconds: float = 0.0
    batch_snapshot_record_build_seconds: float = 0.0
    raw_object_seconds: float = 0.0
    pin_name_seconds: float = 0.0
    net_name_seconds: float = 0.0
    component_refdes_seconds: float = 0.0
    placement_layer_seconds: float = 0.0
    is_layout_pin_seconds: float = 0.0
    position_rotation_seconds: float = 0.0
    position_get_value_seconds: float = 0.0
    position_component_seconds: float = 0.0
    position_transform_seconds: float = 0.0
    position_transform_point_seconds: float = 0.0
    position_point_convert_seconds: float = 0.0
    layer_fields_seconds: float = 0.0
    layer_range_seconds: float = 0.0
    layer_name_seconds: float = 0.0
    layer_range_names_seconds: float = 0.0
    id_seconds: float = 0.0
    type_seconds: float = 0.0
    definition_seconds: float = 0.0
    record_build_seconds: float = 0.0


def _record_profile_time(
    profile: PadstackRecordProfile | None, field_name: str, start: float
) -> None:
    if profile is not None:
        setattr(
            profile, field_name, getattr(profile, field_name) + perf_counter() - start
        )


def log_padstack_record_profile(profile: PadstackRecordProfile) -> None:
    if profile.instances == 0:
        return

    log_field_block(
        logger,
        "Parsed padstack instance records",
        fields={"instances": profile.instances},
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


def _padstack_id(padstack: Any, raw_padstack: Any | None = None) -> Any:
    raw_padstack = (
        raw_padstack if raw_padstack is not None else _padstack_raw_object(padstack)
    )
    if raw_padstack is not None:
        padstack_id = _call_or_none(raw_padstack, "GetId")
        if padstack_id is not None:
            return padstack_id
    return safe_getattr(padstack, "id")


def _padstack_type(padstack: Any, raw_padstack: Any | None = None) -> Any:
    raw_padstack = (
        raw_padstack if raw_padstack is not None else _padstack_raw_object(padstack)
    )
    if raw_padstack is not None:
        padstack_type = _call_or_none(raw_padstack, "GetType")
        if padstack_type is not None:
            return str(padstack_type)
    return safe_getattr(padstack, "type")


def _padstack_definition_name(
    padstack: Any, raw_padstack: Any | None = None
) -> str | None:
    raw_padstack = (
        raw_padstack if raw_padstack is not None else _padstack_raw_object(padstack)
    )
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


def _padstack_position_and_rotation(
    padstack: Any,
    raw_padstack: Any | None = None,
    profile: PadstackRecordProfile | None = None,
) -> tuple[Any, Any]:
    raw_padstack = (
        raw_padstack if raw_padstack is not None else _padstack_raw_object(padstack)
    )
    if raw_padstack is not None:
        try:
            start = perf_counter() if profile is not None else 0.0
            valid, point, rotation = raw_padstack.GetPositionAndRotationValue()
            _record_profile_time(profile, "position_get_value_seconds", start)
            if not valid:
                return [], 0.0

            start = perf_counter() if profile is not None else 0.0
            component = raw_padstack.GetComponent()
            _record_profile_time(profile, "position_component_seconds", start)
            if component is not None and not _is_null_dotnet_object(component):
                start = perf_counter() if profile is not None else 0.0
                transform = component.GetTransform()
                _record_profile_time(profile, "position_transform_seconds", start)
                if transform is not None:
                    start = perf_counter() if profile is not None else 0.0
                    point = transform.TransformPoint(point)
                    _record_profile_time(
                        profile, "position_transform_point_seconds", start
                    )

            start = perf_counter() if profile is not None else 0.0
            position = [
                round(point.X.ToDouble(), COORDINATE_DIGITS),
                round(point.Y.ToDouble(), COORDINATE_DIGITS),
            ]
            rotation_value = round(rotation.ToDouble(), ROTATION_DIGITS)
            _record_profile_time(profile, "position_point_convert_seconds", start)
            return position, rotation_value
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


def _padstack_layer_fields(
    padstack: Any,
    signal_layer_names: list[str],
    raw_padstack: Any | None = None,
    profile: PadstackRecordProfile | None = None,
) -> tuple[Any, Any, Any]:
    raw_padstack = (
        raw_padstack if raw_padstack is not None else _padstack_raw_object(padstack)
    )
    if raw_padstack is not None:
        try:
            start = perf_counter() if profile is not None else 0.0
            _, start_layer, stop_layer = raw_padstack.GetLayerRange()
            _record_profile_time(profile, "layer_range_seconds", start)
            start = perf_counter() if profile is not None else 0.0
            start_layer_name = _dotnet_name_or_none(start_layer)
            stop_layer_name = _dotnet_name_or_none(stop_layer)
            _record_profile_time(profile, "layer_name_seconds", start)
            if start_layer_name is not None and stop_layer_name is not None:
                start = perf_counter() if profile is not None else 0.0
                layer_range_names = _layer_range_names(
                    signal_layer_names, start_layer_name, stop_layer_name
                )
                _record_profile_time(profile, "layer_range_names_seconds", start)
                return (
                    start_layer_name,
                    stop_layer_name,
                    layer_range_names,
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


def _record_from_snapshot(
    padstack: Any,
    snapshot: DotNetPadstackSnapshot,
    signal_layer_names: list[str],
) -> PadstackInstanceRecord:
    padstack_name = snapshot.name or ""
    net_name = snapshot.net_name or ""
    component_refdes = snapshot.component_name or ""
    placement_layer = snapshot.placement_layer or ""
    is_layout_pin = (
        snapshot.is_layout_pin
        if snapshot.has_is_layout_pin
        else bool(safe_getattr(padstack, "is_pin"))
    )
    position: Any
    rotation: Any
    if snapshot.has_position:
        position = [
            round(snapshot.x, COORDINATE_DIGITS),
            round(snapshot.y, COORDINATE_DIGITS),
        ]
        rotation = round(snapshot.rotation, ROTATION_DIGITS)
    else:
        position = []
        rotation = 0.0

    layer_range_names = None
    if snapshot.start_layer is not None and snapshot.stop_layer is not None:
        layer_range_names = _layer_range_names(
            signal_layer_names, snapshot.start_layer, snapshot.stop_layer
        )

    return PadstackInstanceRecord(
        source=padstack,
        id=snapshot.id,
        name=padstack_name,
        type=snapshot.type,
        net_name=net_name,
        count_net_name=net_name,
        component_name=component_refdes,
        component_refdes=component_refdes,
        placement_layer=placement_layer,
        pin_placement_layer=placement_layer,
        position=position,
        rotation=rotation,
        start_layer=snapshot.start_layer,
        stop_layer=snapshot.stop_layer,
        layer_range_names=layer_range_names,
        padstack_definition=snapshot.padstack_definition,
        is_pin=is_layout_pin,
        is_layout_pin=is_layout_pin,
        pin_name=padstack_name,
    )


def _padstack_component_refdes(padstack: Any, raw_padstack: Any | None = None) -> str:
    raw_padstack = (
        raw_padstack if raw_padstack is not None else _padstack_raw_object(padstack)
    )
    if raw_padstack is not None:
        component_name = _dotnet_name_or_none(
            _call_or_none(raw_padstack, "GetComponent")
        )
        if component_name is not None:
            return component_name
    return safe_getattr(padstack, "component_name", "") or ""


def _padstack_net_name(padstack: Any, raw_padstack: Any | None = None) -> str:
    raw_padstack = (
        raw_padstack if raw_padstack is not None else _padstack_raw_object(padstack)
    )
    if raw_padstack is not None:
        net_name = _dotnet_name_or_none(_call_or_none(raw_padstack, "GetNet"))
        if net_name is not None:
            return net_name
    return safe_getattr(padstack, "net_name", "") or ""


def _padstack_is_layout_pin(padstack: Any, raw_padstack: Any | None = None) -> bool:
    raw_padstack = (
        raw_padstack if raw_padstack is not None else _padstack_raw_object(padstack)
    )
    if raw_padstack is not None:
        try:
            return bool(raw_padstack.IsLayoutPin())
        except Exception:
            pass
    return bool(safe_getattr(padstack, "is_pin"))


def _padstack_pin_name(padstack: Any, raw_padstack: Any | None = None) -> str:
    raw_padstack = (
        raw_padstack if raw_padstack is not None else _padstack_raw_object(padstack)
    )
    if raw_padstack is not None:
        try:
            return raw_padstack.GetName()
        except Exception:
            pass
    return safe_getattr(padstack, "name", "") or ""


def _padstack_placement_layer(padstack: Any, raw_padstack: Any | None = None) -> str:
    raw_padstack = (
        raw_padstack if raw_padstack is not None else _padstack_raw_object(padstack)
    )
    if raw_padstack is not None:
        try:
            group = raw_padstack.GetGroup()
            if group is not None and not _is_null_dotnet_object(group):
                placement_layer = _dotnet_name_or_none(group.GetPlacementLayer())
                if placement_layer is not None:
                    return placement_layer
        except Exception:
            pass
    return safe_getattr(padstack, "placement_layer", "") or ""


def build_padstack_instance_records(
    padstacks: list[Any],
    signal_layer_names: list[str],
    profile: PadstackRecordProfile | None = None,
) -> list[PadstackInstanceRecord]:
    """Build padstack records through a batch .NET snapshot when available."""

    if not padstacks:
        return []

    start = perf_counter() if profile is not None else 0.0
    raw_padstacks = [_padstack_raw_object(padstack) for padstack in padstacks]
    _record_profile_time(profile, "raw_object_seconds", start)

    if all(raw_padstack is not None for raw_padstack in raw_padstacks):
        start = perf_counter() if profile is not None else 0.0
        snapshots = snapshots_from_padstack_instances_dotnet(raw_padstacks)
        snapshot_seconds = perf_counter() - start if profile is not None else 0.0
        if snapshots is not None and len(snapshots) == len(padstacks):
            if profile is not None:
                profile.instances += len(padstacks)
                profile.snapshot_successes += len(snapshots)
                profile.snapshot_seconds += snapshot_seconds
                profile.batch_snapshot_successes += len(snapshots)
                profile.batch_snapshot_seconds += snapshot_seconds

            start = perf_counter() if profile is not None else 0.0
            records = [
                _record_from_snapshot(padstack, snapshot, signal_layer_names)
                for padstack, snapshot in zip(padstacks, snapshots, strict=True)
            ]
            record_build_seconds = (
                perf_counter() - start if profile is not None else 0.0
            )
            if profile is not None:
                profile.snapshot_record_build_seconds += record_build_seconds
                profile.batch_snapshot_record_build_seconds += record_build_seconds
            return records

        if profile is not None:
            profile.batch_snapshot_fallbacks += len(padstacks)

    return [
        build_padstack_instance_record(padstack, signal_layer_names, profile)
        for padstack in padstacks
    ]


def build_padstack_instance_record(
    padstack: Any,
    signal_layer_names: list[str],
    profile: PadstackRecordProfile | None = None,
) -> PadstackInstanceRecord:
    if profile is not None:
        profile.instances += 1
    start = perf_counter() if profile is not None else 0.0
    raw_padstack = _padstack_raw_object(padstack)
    _record_profile_time(profile, "raw_object_seconds", start)

    if raw_padstack is not None:
        start = perf_counter() if profile is not None else 0.0
        snapshot = snapshot_from_padstack_instance_dotnet(raw_padstack)
        _record_profile_time(profile, "snapshot_seconds", start)
        if snapshot is not None:
            if profile is not None:
                profile.snapshot_successes += 1
            start = perf_counter() if profile is not None else 0.0
            record = _record_from_snapshot(padstack, snapshot, signal_layer_names)
            _record_profile_time(profile, "snapshot_record_build_seconds", start)
            return record
        if profile is not None:
            profile.snapshot_fallbacks += 1

    start = perf_counter() if profile is not None else 0.0
    padstack_name = _padstack_pin_name(padstack, raw_padstack)
    _record_profile_time(profile, "pin_name_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    net_name = _padstack_net_name(padstack, raw_padstack)
    _record_profile_time(profile, "net_name_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    component_refdes = _padstack_component_refdes(padstack, raw_padstack)
    _record_profile_time(profile, "component_refdes_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    placement_layer = _padstack_placement_layer(padstack, raw_padstack)
    _record_profile_time(profile, "placement_layer_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    is_layout_pin = _padstack_is_layout_pin(padstack, raw_padstack)
    _record_profile_time(profile, "is_layout_pin_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    position, rotation = _padstack_position_and_rotation(
        padstack, raw_padstack, profile
    )
    _record_profile_time(profile, "position_rotation_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    start_layer, stop_layer, layer_range_names = _padstack_layer_fields(
        padstack,
        signal_layer_names,
        raw_padstack,
        profile,
    )
    _record_profile_time(profile, "layer_fields_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    padstack_id = _padstack_id(padstack, raw_padstack)
    _record_profile_time(profile, "id_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    padstack_type = _padstack_type(padstack, raw_padstack)
    _record_profile_time(profile, "type_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    padstack_definition = _padstack_definition_name(padstack, raw_padstack)
    _record_profile_time(profile, "definition_seconds", start)

    start = perf_counter() if profile is not None else 0.0
    record = PadstackInstanceRecord(
        source=padstack,
        id=padstack_id,
        name=padstack_name,
        type=padstack_type,
        net_name=net_name,
        count_net_name=net_name,
        component_name=component_refdes,
        component_refdes=component_refdes,
        placement_layer=placement_layer,
        pin_placement_layer=placement_layer,
        position=position,
        rotation=rotation,
        start_layer=start_layer,
        stop_layer=stop_layer,
        layer_range_names=layer_range_names,
        padstack_definition=padstack_definition,
        is_pin=is_layout_pin,
        is_layout_pin=is_layout_pin,
        pin_name=padstack_name,
    )
    _record_profile_time(profile, "record_build_seconds", start)
    return record


def padstack_record_to_instance_data(record: PadstackInstanceRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "type": record.type,
        "net_name": record.net_name,
        "component_name": record.component_name,
        "placement_layer": record.placement_layer,
        "position": record.position,
        "rotation": record.rotation,
        "start_layer": record.start_layer,
        "stop_layer": record.stop_layer,
        "layer_range_names": record.layer_range_names,
        "padstack_definition": record.padstack_definition,
        "is_pin": record.is_pin,
    }


def padstack_record_to_pin_data(
    record: PadstackInstanceRecord, *, name: str | None = None
) -> dict[str, Any]:
    return {
        "name": name or record.pin_name or record.name,
        "id": record.id,
        "net_name": record.net_name,
        "position": record.position,
        "rotation": record.rotation,
        "placement_layer": record.pin_placement_layer,
        "start_layer": record.start_layer,
        "stop_layer": record.stop_layer,
        "padstack_definition": record.padstack_definition,
        "is_pin": record.is_pin,
    }
