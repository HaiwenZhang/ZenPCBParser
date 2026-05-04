from __future__ import annotations

import logging
from typing import Any, Literal

from aurora_translator.sources.aedb.models import ComponentModel, PinModel
from aurora_translator.sources.aedb.normalizers import safe_getattr
from aurora_translator.shared.logging import log_timing

from .context import ComponentLayoutRecord, ExtractionContext
from .padstack_records import (
    PadstackInstanceRecord,
    _dotnet_name_or_none,
    _is_null_dotnet_object,
    _padstack_definition_name,
    _padstack_layer_fields,
    _padstack_position_and_rotation,
    _padstack_raw_object,
    padstack_record_to_pin_data,
)
from .precision import COORDINATE_DIGITS, ROTATION_DIGITS


logger = logging.getLogger("aurora_translator.aedb.extractors.components")

ComponentCenterSource = Literal["pin-bbox", "layout-instance"]

_COMPONENT_TYPE_NAMES = {
    0: "Other",
    1: "Resistor",
    2: "Inductor",
    3: "Capacitor",
    4: "IC",
    5: "IO",
}
_DISCRETE_COMPONENT_TYPES = {"Resistor", "Capacitor", "Inductor"}


def _component_raw_object(component: Any) -> Any:
    return safe_getattr(component, "edbcomponent") or safe_getattr(
        component, "_edb_object"
    )


def _component_id(raw_component: Any) -> int | None:
    if raw_component is None:
        return None
    try:
        return int(raw_component.GetId())
    except Exception:
        return None


def _component_instance(
    component: Any, raw_component: Any, component_instances_by_id: dict[int, Any] | None
) -> Any:
    if component_instances_by_id:
        component_id = _component_id(raw_component)
        if component_id is not None:
            component_instance = component_instances_by_id.get(component_id)
            if component_instance is not None:
                return component_instance
    return safe_getattr(component, "component_instance")


def _component_layout_record(
    raw_component: Any,
    component_layout_records_by_id: dict[int, ComponentLayoutRecord] | None,
) -> ComponentLayoutRecord | None:
    if not component_layout_records_by_id:
        return None
    component_id = _component_id(raw_component)
    if component_id is None:
        return None
    return component_layout_records_by_id.get(component_id)


def _point_xy_rounded(
    point: Any, digits: int = COORDINATE_DIGITS
) -> list[float] | None:
    if point is None:
        return None
    try:
        return [
            round(point.X.ToDouble(), digits),
            round(point.Y.ToDouble(), digits),
        ]
    except Exception:
        return None


def _component_location(raw_component: Any) -> list[Any] | None:
    if raw_component is None:
        return None
    try:
        valid, x, y = raw_component.GetLocation()
        if valid:
            return [x, y]
    except Exception:
        pass
    return None


def _component_center(component_instance: Any) -> list[float] | None:
    return _point_xy_rounded(_safe_call(component_instance, "GetCenter"))


def _component_bounding_box(component_instance: Any) -> list[float] | None:
    if component_instance is None:
        return None
    try:
        bbox = component_instance.GetBBox()
        return [
            round(bbox.Item1.X.ToDouble(), COORDINATE_DIGITS),
            round(bbox.Item1.Y.ToDouble(), COORDINATE_DIGITS),
            round(bbox.Item2.X.ToDouble(), COORDINATE_DIGITS),
            round(bbox.Item2.Y.ToDouble(), COORDINATE_DIGITS),
        ]
    except Exception:
        return None


def _component_center_from_pins(pins: list[PinModel]) -> list[float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for pin in pins:
        position = pin.position
        if position is None or len(position) < 2:
            continue
        x, y = position[0], position[1]
        if x is None or y is None:
            continue
        xs.append(float(x))
        ys.append(float(y))

    if not xs or not ys:
        return None

    return [
        round((min(xs) + max(xs)) / 2.0, COORDINATE_DIGITS),
        round((min(ys) + max(ys)) / 2.0, COORDINATE_DIGITS),
    ]


def _component_rotation(raw_component: Any) -> float | None:
    if raw_component is None:
        return None
    try:
        return round(raw_component.GetTransform().Rotation.ToDouble(), ROTATION_DIGITS)
    except Exception:
        return None


def _component_refdes(raw_component: Any) -> str | None:
    return _dotnet_name_or_none(raw_component)


def _component_part_name(raw_component: Any) -> str | None:
    if raw_component is None:
        return None
    return _dotnet_name_or_none(_safe_call(raw_component, "GetComponentDef"))


def _component_placement_layer_name(raw_component: Any) -> str | None:
    if raw_component is None:
        return None
    try:
        layer = raw_component.GetPlacementLayer()
        if layer is not None and not _is_null_dotnet_object(layer):
            clone = _safe_call(layer, "Clone")
            return _dotnet_name_or_none(clone if clone is not None else layer)
    except Exception:
        pass
    return None


def _component_type_name(raw_component: Any) -> str | None:
    if raw_component is None:
        return None
    try:
        return _COMPONENT_TYPE_NAMES.get(int(raw_component.GetComponentType()))
    except Exception:
        return None


def _component_model_state(
    component: Any, component_type: str | None
) -> tuple[Any, str | None, Any]:
    component_property = safe_getattr(
        safe_getattr(component, "component_property"), "core"
    )
    safe_get_model = safe_getattr(component, "_safe_get_model")

    enabled = None
    if component_type in _DISCRETE_COMPONENT_TYPES and component_property is not None:
        enabled = _safe_call(component_property, "IsEnabled")

    if not callable(safe_get_model) or component_property is None:
        return None, None, enabled

    try:
        raw_model, type_name = safe_get_model(component_property)
    except Exception:
        return None, None, enabled

    if type_name == "PinPairModel":
        return raw_model, "RLC", enabled
    return raw_model, type_name, enabled


def _component_value_from_model(raw_model: Any, model_type: str | None) -> Any:
    if raw_model is None or not model_type or model_type == "NoModel":
        return None

    try:
        if model_type == "RLC":
            pin_pairs = list(raw_model.PinPairs)
            if not pin_pairs:
                return None
            rlc = raw_model.GetPinPairRlc(pin_pairs[0])
            enabled_flags = [bool(rlc.REnabled), bool(rlc.LEnabled), bool(rlc.CEnabled)]
            values = [rlc.R.ToDouble(), rlc.L.ToDouble(), rlc.C.ToDouble()]
            enabled_values = [
                value for value, enabled in zip(values, enabled_flags) if enabled
            ]
            return enabled_values[0] if len(enabled_values) == 1 else values

        if model_type == "SPICEModel":
            return _safe_call(raw_model, "GetSPICEFilePath")

        if model_type == "SParameterModel":
            return _safe_call(raw_model, "GetComponentModelName")

        if model_type == "NetlistModel":
            return _safe_call(raw_model, "GetNetlist")
    except Exception:
        return None

    return None


def _padstack_component_name(pin: Any) -> str:
    raw_pin = _padstack_raw_object(pin)
    if raw_pin is not None:
        component_name = _dotnet_name_or_none(_safe_call(raw_pin, "GetComponent"))
        if component_name is not None:
            return component_name
    return safe_getattr(pin, "component_name", "") or ""


def _padstack_is_layout_pin(pin: Any) -> bool:
    raw_pin = _padstack_raw_object(pin)
    if raw_pin is not None:
        try:
            return bool(raw_pin.IsLayoutPin())
        except Exception:
            pass
    return bool(safe_getattr(pin, "is_pin"))


def _padstack_pin_name(pin: Any) -> str:
    raw_pin = _padstack_raw_object(pin)
    if raw_pin is not None:
        try:
            return raw_pin.GetName()
        except Exception:
            pass
    return safe_getattr(pin, "name", "") or ""


def _padstack_placement_layer(pin: Any) -> str | None:
    raw_pin = _padstack_raw_object(pin)
    if raw_pin is not None:
        try:
            group = raw_pin.GetGroup()
            if group is not None and not _is_null_dotnet_object(group):
                placement_layer = _dotnet_name_or_none(group.GetPlacementLayer())
                if placement_layer is not None:
                    return placement_layer
        except Exception:
            pass
    return safe_getattr(pin, "placement_layer")


def _safe_call(value: Any, method_name: str) -> Any:
    try:
        return getattr(value, method_name)()
    except Exception:
        return None


def _component_pin_items_by_refdes(
    context: ExtractionContext,
) -> dict[str, list[tuple[str, PadstackInstanceRecord]]]:
    pins_by_refdes: dict[str, list[tuple[str, PadstackInstanceRecord]]] = {}
    for pin in context.padstack_instance_records:
        if not pin.is_layout_pin:
            continue
        component_name = pin.component_refdes
        if not component_name:
            continue
        pins_by_refdes.setdefault(component_name, []).append((pin.pin_name, pin))
    return pins_by_refdes


def extract_pin(name: str, pin: Any, signal_layer_names: list[str]) -> PinModel:
    if isinstance(pin, PadstackInstanceRecord):
        return PinModel.model_validate(padstack_record_to_pin_data(pin, name=name))

    position, rotation = _padstack_position_and_rotation(pin)
    start_layer, stop_layer, _ = _padstack_layer_fields(pin, signal_layer_names)

    return PinModel.model_validate(
        {
            "name": name or safe_getattr(pin, "name"),
            "id": safe_getattr(pin, "id"),
            "net_name": safe_getattr(pin, "net_name"),
            "position": position,
            "rotation": rotation,
            "placement_layer": _padstack_placement_layer(pin),
            "start_layer": start_layer,
            "stop_layer": stop_layer,
            "padstack_definition": _padstack_definition_name(pin),
            "is_pin": safe_getattr(pin, "is_pin"),
        }
    )


def extract_component(
    component: Any,
    component_pins: list[tuple[str, Any]],
    signal_layer_names: list[str],
    top_signal_layers: set[str],
    component_instances_by_id: dict[int, Any] | None = None,
    component_layout_records_by_id: dict[int, ComponentLayoutRecord] | None = None,
    include_layout_geometry: bool = True,
    component_center_source: ComponentCenterSource = "pin-bbox",
) -> ComponentModel:
    raw_component = _component_raw_object(component)
    component_layout_record = (
        _component_layout_record(raw_component, component_layout_records_by_id)
        if include_layout_geometry and component_center_source == "layout-instance"
        else None
    )
    component_instance = (
        None
        if (
            component_layout_record is not None
            or not include_layout_geometry
            or component_center_source != "layout-instance"
        )
        else _component_instance(component, raw_component, component_instances_by_id)
    )
    pins = [
        extract_pin(pin_name, pin, signal_layer_names)
        for pin_name, pin in component_pins
    ]
    pins.sort(key=lambda item: item.name or "")

    component_type = _component_type_name(raw_component)
    placement_layer = _component_placement_layer_name(raw_component)
    raw_model, model_type, enabled = _component_model_state(component, component_type)
    value = _component_value_from_model(raw_model, model_type)
    location = _component_location(raw_component)
    center = None
    bounding_box = None
    if include_layout_geometry:
        if component_center_source == "pin-bbox":
            center = _component_center_from_pins(pins)
        else:
            center = (
                component_layout_record.center
                if component_layout_record is not None
                else _component_center(component_instance)
            )
            bounding_box = (
                component_layout_record.bounding_box
                if component_layout_record is not None
                else _component_bounding_box(component_instance)
            )
    rotation = _component_rotation(raw_component)
    is_top_mounted = placement_layer in top_signal_layers if placement_layer else None
    resolved_model_type = (
        model_type if model_type is not None else safe_getattr(component, "model_type")
    )
    resolved_value = (
        value
        if resolved_model_type
        in {"RLC", "SPICEModel", "SParameterModel", "NetlistModel", "NoModel"}
        else (value if value is not None else safe_getattr(component, "value"))
    )

    return ComponentModel.model_validate(
        {
            "refdes": _component_refdes(raw_component)
            or safe_getattr(component, "refdes"),
            "component_name": safe_getattr(component, "component_name"),
            "part_name": _component_part_name(raw_component)
            or safe_getattr(component, "part_name")
            or safe_getattr(component, "partname"),
            "type": component_type
            if component_type is not None
            else safe_getattr(component, "type"),
            "value": resolved_value,
            "placement_layer": placement_layer
            if placement_layer is not None
            else safe_getattr(component, "placement_layer"),
            "location": location
            if location is not None
            else safe_getattr(component, "location"),
            "center": (
                center
                if include_layout_geometry and center is not None
                else (
                    safe_getattr(component, "center")
                    if include_layout_geometry
                    and component_center_source == "layout-instance"
                    else None
                )
            ),
            "rotation": rotation
            if rotation is not None
            else safe_getattr(component, "rotation"),
            "bounding_box": (
                bounding_box
                if include_layout_geometry and bounding_box is not None
                else (
                    safe_getattr(component, "bounding_box")
                    if include_layout_geometry
                    and component_center_source == "layout-instance"
                    else None
                )
            ),
            "is_top_mounted": (
                is_top_mounted
                if is_top_mounted is not None
                else safe_getattr(component, "is_top_mounted")
            ),
            "enabled": enabled
            if enabled is not None
            else safe_getattr(component, "enabled"),
            "model_type": resolved_model_type,
            "numpins": len(pins),
            "nets": sorted({pin.net_name for pin in pins if pin.net_name}),
            "pins": pins,
        }
    )


def extract_components(
    context: ExtractionContext,
    *,
    use_layout_object_index: bool = True,
    component_instances_by_id: dict[int, Any] | None = None,
    component_layout_records_by_id: dict[int, ComponentLayoutRecord] | None = None,
    include_layout_geometry: bool = True,
    component_center_source: ComponentCenterSource = "pin-bbox",
) -> list[ComponentModel]:
    component_values = context.components
    top_signal_layers = set(
        context.signal_layer_names[: len(context.signal_layer_names) // 2]
    )
    with log_timing(logger, "serialize components", count=len(component_values)):
        with log_timing(
            logger, "group component pins", count=len(context.padstack_instances)
        ):
            pins_by_refdes = _component_pin_items_by_refdes(context)

        if not include_layout_geometry:
            component_instances_by_id = None
            logger.info("Skip component layout geometry fields center and bounding_box")
        elif component_center_source == "pin-bbox":
            component_instances_by_id = None
            logger.info("Compute component center from pin bounding boxes")
        elif component_layout_records_by_id is not None:
            component_instances_by_id = None
        elif component_instances_by_id is not None:
            pass
        elif use_layout_object_index:
            with log_timing(
                logger, "build component instance map", count=len(component_values)
            ):
                component_instances_by_id = context.component_instances_by_id
        else:
            component_instances_by_id = None
            logger.info("Use component wrapper instances without layout object index")

        with log_timing(
            logger, "serialize component models", count=len(component_values)
        ):
            components = [
                extract_component(
                    component,
                    pins_by_refdes.get(safe_getattr(component, "refdes"), []),
                    context.signal_layer_names,
                    top_signal_layers,
                    component_instances_by_id,
                    component_layout_records_by_id,
                    include_layout_geometry,
                    component_center_source,
                )
                for component in component_values
            ]

        with log_timing(logger, "sort components"):
            return sorted(components, key=lambda item: item.refdes or "")
