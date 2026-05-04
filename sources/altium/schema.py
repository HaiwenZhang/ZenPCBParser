from __future__ import annotations

from aurora_translator.sources.altium.models import AltiumLayout


def altium_json_schema() -> dict:
    return AltiumLayout.model_json_schema()
