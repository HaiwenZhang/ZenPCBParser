from __future__ import annotations

from aurora_translator.sources.brd.models import BRDLayout


def brd_json_schema() -> dict:
    return BRDLayout.model_json_schema()
