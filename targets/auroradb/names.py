from __future__ import annotations

import json
import re


def _standardize_name(name: str) -> str:
    result = str(name)
    for old in [" ", "/", "*", "(", ")", "-", "."]:
        result = result.replace(old, "_")
    result = result.replace("UNNAMED_", "D")
    result = re.sub(r"[^A-Za-z0-9_]", "_", result)
    result = re.sub(r"_+", "_", result).strip("_")
    return result or "Unnamed"


def _unique_name(name: str, seen: set[str]) -> str:
    candidate = name
    suffix = 2
    while candidate.casefold() in seen:
        candidate = f"{name}_{suffix}"
        suffix += 1
    seen.add(candidate.casefold())
    return candidate


def _net_type(role: str | None) -> str:
    text = (role or "signal").casefold()
    if text in {"power", "ground"}:
        return text
    return "signal"


def _auroradb_net_name(net_name: str) -> str:
    cleaned = str(net_name).strip()
    if len(cleaned) >= 2 and cleaned[0] == '"' and cleaned[-1] == '"':
        cleaned = cleaned[1:-1].replace('\\"', '"')
    if cleaned.casefold() == "nonet":
        return "NoNet"
    return cleaned.upper()


def _pin_sort_key(value: str) -> tuple[int, int | str, str]:
    if value.isdigit():
        return (0, int(value), value)
    return (1, value.casefold(), value)


def _tuple_value(value: str) -> str:
    text = str(value)
    if any(char in text for char in [",", " ", "(", ")", "<", ">", "{", "}"]):
        return _quote_aaf(text)
    return text


def _aaf_atom(value: str) -> str:
    text = str(value)
    if any(char in text for char in [" ", "<", ">", "{", "}"]):
        return _quote_aaf(text)
    return text


def _quote_aaf(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)
