from __future__ import annotations

import math
from typing import Any


def safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    try:
        return getattr(obj, name)
    except Exception:
        return default


def call_or_value(value: Any) -> Any:
    try:
        return value() if callable(value) else value
    except Exception:
        return None


def safe_len(value: Any) -> int:
    if value is None:
        return 0
    try:
        return len(value)
    except TypeError:
        return 0


def safe_zone_primitives(layout: Any) -> list[Any]:
    try:
        return list(layout.zone_primitives or [])
    except Exception:
        return []


def normalize_enum_text(value: Any) -> str | int | None:
    if value is None:
        return None
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    text = str(value)
    if text.startswith("<") and "object at" in text:
        return None
    return text


def normalize_number(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value

    tofloat = safe_getattr(value, "tofloat")
    if tofloat is not None:
        return normalize_number(tofloat)

    to_double = call_or_value(safe_getattr(value, "ToDouble"))
    if to_double is not None:
        return normalize_number(to_double)

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def normalize_point(value: Any) -> tuple[float | None, float | None] | None:
    if value is None:
        return None

    if isinstance(value, (list, tuple)) and len(value) >= 2:
        point = (normalize_number(value[0]), normalize_number(value[1]))
        return None if all(item is None for item in point) else point

    for x_name, y_name in (("x", "y"), ("X", "Y")):
        x = safe_getattr(value, x_name)
        y = safe_getattr(value, y_name)
        if x is not None or y is not None:
            point = (normalize_number(x), normalize_number(y))
            return None if all(item is None for item in point) else point

    try:
        items = list(value)
    except TypeError:
        return None

    if len(items) >= 2:
        point = (normalize_number(items[0]), normalize_number(items[1]))
        return None if all(item is None for item in point) else point
    return None


def normalize_point_list(values: Any) -> list[tuple[float | None, float | None]]:
    points: list[tuple[float | None, float | None]] = []
    if values is None:
        return points
    for value in values:
        point = normalize_point(value)
        if point is not None:
            points.append(point)
    return points


def normalize_numeric_list(value: Any) -> list[float | int | None] | None:
    if value is None:
        return None
    if isinstance(value, (str, bytes)):
        return None
    try:
        return [normalize_number(item) for item in value]
    except TypeError:
        numeric = normalize_number(value)
        return None if numeric is None else [numeric]


def normalize_value(value: Any) -> str | bool | int | float | dict[str, Any] | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return normalize_number(value)
    if isinstance(value, str):
        return value

    tofloat = safe_getattr(value, "tofloat")
    tostring = safe_getattr(value, "tostring")
    if tofloat is not None or tostring is not None:
        if tofloat is None and tostring is not None:
            return tostring
        return {
            "value": normalize_number(tofloat),
            "display": tostring,
        }

    to_double = call_or_value(safe_getattr(value, "ToDouble"))
    to_string = call_or_value(safe_getattr(value, "ToString"))
    if to_double is not None or to_string is not None:
        if to_double is None and to_string is not None:
            return to_string
        return {
            "value": normalize_number(to_double),
            "display": to_string,
        }

    enum_name = normalize_enum_text(value)
    if enum_name is not None:
        return enum_name

    return str(value)


def normalize_value_list(
    value: Any,
) -> list[str | bool | int | float | dict[str, Any] | None]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [normalize_value(value)]
    try:
        return [normalize_value(item) for item in value]
    except TypeError:
        return [normalize_value(value)]


def normalize_optional_value_list(
    value: Any,
) -> list[str | bool | int | float | dict[str, Any] | None] | None:
    if value is None:
        return None
    return normalize_value_list(value)


def normalize_int_list(value: Any) -> list[int | None]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return []
    try:
        return [None if item is None else int(item) for item in value]
    except TypeError:
        return []


def normalize_parameter_map(
    value: Any,
) -> dict[str, str | bool | int | float | dict[str, Any] | None]:
    if not value:
        return {}
    return {str(name): normalize_value(item) for name, item in value.items()}
