from __future__ import annotations

import ast
from functools import lru_cache
from typing import Any

from aurora_translator.semantic.models import SemanticPoint, SourceRef

_ALLOWED_ID_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.:+-"
)


def source_ref(
    source_format: str, path: str | None = None, raw_id: object | None = None
) -> SourceRef:
    return SourceRef.model_construct(
        source_format=source_format,
        path=path,
        raw_id=None if raw_id is None else str(raw_id),
    )


def semantic_id(
    prefix: str, value: object | None, fallback: object | None = None
) -> str:
    raw = value if not _is_blank(value) else fallback
    text = str(raw if not _is_blank(raw) else "unknown")
    text = _normalize_semantic_id_text(text)
    return f"{prefix}:{text or 'unknown'}"


def _is_blank(value: object | None) -> bool:
    return value is None or value == ""


def unique_append(values: list[str], value: str | None) -> None:
    if value and value not in values:
        values.append(value)


def point_from_pair(value: object | None) -> SemanticPoint | None:
    if value is None:
        return None
    if isinstance(value, SemanticPoint):
        return value
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            if value[0] is None or value[1] is None:
                return None
            return SemanticPoint.model_construct(x=float(value[0]), y=float(value[1]))
        except (TypeError, ValueError):
            return None
    x = getattr(value, "x", None)
    y = getattr(value, "y", None)
    if x is not None and y is not None:
        try:
            return SemanticPoint.model_construct(x=float(x), y=float(y))
        except (TypeError, ValueError):
            return None
    return None


@lru_cache(maxsize=131072)
def _normalize_semantic_id_text(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    normalized: list[str] = []
    saw_whitespace = False
    for char in stripped:
        if char.isspace():
            if not saw_whitespace:
                normalized.append("_")
                saw_whitespace = True
            continue
        saw_whitespace = False
        normalized.append(char if char in _ALLOWED_ID_CHARS else "_")
    return "".join(normalized)


def text_value(value: Any) -> str | None:
    if value is None:
        return None
    display = getattr(value, "display", None)
    if display is not None:
        return str(display)
    if isinstance(value, dict):
        display = value.get("display")
        if display is not None:
            return str(display)
        raw_value = value.get("value")
        if raw_value is not None:
            return str(raw_value)
    if isinstance(value, str):
        mapped_display = _mapping_text_value(value)
        return mapped_display if mapped_display is not None else value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return str(value)


def _mapping_text_value(value: str) -> str | None:
    text = value.strip()
    if not text.startswith("{") or "display" not in text:
        return None
    try:
        parsed = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    display = parsed.get("display")
    if display is not None:
        return str(display)
    raw_value = parsed.get("value")
    return None if raw_value is None else str(raw_value)


def role_from_net_name(name: str | None, explicit: str | None = None) -> str:
    explicit_text = (explicit or "").casefold()
    if explicit_text in {"power", "ground", "signal"}:
        return explicit_text
    net = (name or "").casefold()
    if net in {"gnd", "ground", "dgnd", "agnd"} or "gnd" in net:
        return "ground"
    if net.startswith(("vcc", "vdd", "vss", "vref", "vbat")) or net in {"power", "pwr"}:
        return "power"
    return "signal" if name else "unknown"


def role_from_layer_type(
    layer_type: str | None, *, is_via_layer: bool | None = None
) -> str | None:
    if is_via_layer:
        return "drill"
    text = (layer_type or "").casefold()
    if "dielectric" in text:
        return "dielectric"
    if "signal" in text or "routing" in text:
        return "signal"
    if "power" in text or "plane" in text:
        return "plane"
    if "solder" in text:
        return "mask"
    if "component" in text:
        return "component"
    return layer_type


def side_from_layer_name(name: str | None, *, is_top: bool | None = None) -> str | None:
    if is_top is True:
        return "top"
    if is_top is False:
        return "bottom"
    text = (name or "").casefold()
    if text in {"top", "toplayer", "top_layer"} or "top" in text:
        return "top"
    if (
        text in {"bottom", "bot", "bottomlayer", "bottom_layer"}
        or "bottom" in text
        or "bot" in text
        or text.startswith("bot")
    ):
        return "bottom"
    return None
