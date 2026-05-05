from __future__ import annotations

import ast
import math
import re
from functools import lru_cache
from typing import Any


MIL_PER_METER = 39370.07874015748
_NUMBER_UNIT_RE = re.compile(
    r"^([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*([A-Za-zμµ]*)"
)


def _length_to_mil(value: Any, *, source_unit: str | None) -> float | None:
    return _length_to_unit(value, source_unit=source_unit, target_unit="mil")


def _length_to_unit(
    value: Any, *, source_unit: str | None, target_unit: str | None
) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    target_scale = _unit_scale_to_mil(target_unit)
    if isinstance(value, (int, float)):
        scale = _unit_scale_to_mil(source_unit)
        if scale is None or target_scale in {None, 0}:
            return float(value)
        return float(value) * scale / target_scale
    number, unit = _number_and_unit(value)
    if number is None:
        return None
    unit = (unit or source_unit or target_unit or "mil").casefold()
    unit = unit.replace("μ", "u").replace("µ", "u")
    scale = _unit_scale_to_mil(unit)
    if scale is None or target_scale in {None, 0}:
        return number
    return number * scale / target_scale


@lru_cache(maxsize=128)
def _unit_scale_to_mil(unit: str | None) -> float | None:
    normalized = (unit or "mil").casefold()
    normalized = normalized.replace("μ", "u").replace("µ", "u")
    if normalized in {"m", "meter", "meters", "metre", "metres"}:
        return MIL_PER_METER
    if normalized in {"mm", "millimeter", "millimeters", "millimetre", "millimetres"}:
        return 39.37007874015748
    if normalized in {
        "um",
        "micron",
        "microns",
        "micrometer",
        "micrometers",
        "micrometre",
        "micrometres",
    }:
        return 0.03937007874015748
    if normalized in {"mil", "mils"}:
        return 1.0
    if normalized in {"in", "inch", "inches"}:
        return 1000.0
    return None


def _auroradb_output_unit(source_unit: str | None) -> str:
    normalized = (source_unit or "mil").casefold()
    normalized = normalized.replace("μ", "u").replace("µ", "u")
    if normalized in {"m", "meter", "meters", "metre", "metres"}:
        return "m"
    if normalized in {"mm", "millimeter", "millimeters", "millimetre", "millimetres"}:
        return "mm"
    if normalized in {
        "um",
        "micron",
        "microns",
        "micrometer",
        "micrometers",
        "micrometre",
        "micrometres",
    }:
        return "um"
    if normalized in {"inch", "inches", "in"}:
        return "inch"
    if normalized in {"mil", "mils"}:
        return "mils"
    return source_unit or "mils"


def _source_unit_for_auroradb_output(source_unit: str | None) -> str | None:
    output_unit = _auroradb_output_unit(source_unit)
    if _unit_scale_to_mil(source_unit) is None:
        return None
    output_scale = _unit_scale_to_mil(output_unit)
    source_scale = _unit_scale_to_mil(source_unit)
    if output_scale is not None and source_scale is not None:
        if math.isclose(output_scale, source_scale, rel_tol=0.0, abs_tol=1e-15):
            return None
    return source_unit


def _number(value: Any) -> float | None:
    number, _unit = _number_and_unit(value)
    return number


def _format_scalar(value: Any) -> str:
    number = _number(value)
    return _format_number(number) if number is not None else str(value)


def _number_and_unit(value: Any) -> tuple[float | None, str | None]:
    if isinstance(value, bool) or value is None:
        return None, None
    if isinstance(value, (int, float)):
        return float(value), None
    text = str(value).strip()
    if not text:
        return None, None
    if text.startswith("{") and "display" in text:
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            display = parsed.get("display")
            if display is not None:
                return _number_and_unit(display)
            raw_value = parsed.get("value")
            if raw_value is not None:
                return _number_and_unit(raw_value)
    match = _NUMBER_UNIT_RE.match(text)
    if not match:
        return None, None
    return float(match.group(1)), match.group(2) or None


def _point_tuple(value: Any, *, source_unit: str | None) -> tuple[float, float] | None:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        raw_x = value[0]
        raw_y = value[1]
    elif isinstance(value, dict):
        raw_x = value.get("x")
        raw_y = value.get("y")
    else:
        raw_x = getattr(value, "x", None)
        raw_y = getattr(value, "y", None)
        if raw_x is None or raw_y is None:
            return None
    if _is_plain_number(raw_x) and _is_plain_number(raw_y):
        scale = _unit_scale_to_mil(source_unit) or 1.0
        x = float(raw_x) * scale
        y = float(raw_y) * scale
        if (
            math.isfinite(x)
            and math.isfinite(y)
            and abs(x) <= 1e100
            and abs(y) <= 1e100
        ):
            return x, y
        return None
    x = _length_to_mil(raw_x, source_unit=source_unit)
    y = _length_to_mil(raw_y, source_unit=source_unit)
    if x is None or y is None or not _is_coordinate(x) or not _is_coordinate(y):
        return None
    return x, y


def _is_plain_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_finite(value: float | int | None) -> bool:
    return value is not None and math.isfinite(float(value))


def _is_coordinate(value: float | int | None) -> bool:
    return _is_finite(value) and abs(float(value)) <= 1e100


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}


def _format_rotation(value: Any, *, source_format: str | None = None) -> str:
    number = _number(value)
    if number is None or not _is_finite(number):
        return "0"
    angle_degree = _rotation_degrees(number)
    if _source_rotations_are_clockwise(source_format):
        return _format_number(_normalize_degree(angle_degree))
    return _format_number(_normalize_degree(360.0 - angle_degree))


def _rotation_degrees(value: float) -> float:
    angle = math.degrees(value)
    nearest = round(angle)
    if abs(angle - nearest) < 1e-6:
        return float(nearest)
    return angle


def _source_rotations_are_clockwise(source_format: str | None) -> bool:
    return (source_format or "").casefold() == "odbpp"


def _normalize_degree(value: float) -> float:
    return (float(value) + 180.0) % 360.0 - 180.0


@lru_cache(maxsize=262144)
def _format_number(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        return "0"
    return text
