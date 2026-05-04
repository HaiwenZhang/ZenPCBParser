from __future__ import annotations

from aurora_translator.sources.alg.models import ALGLayout


def alg_json_schema() -> dict:
    return ALGLayout.model_json_schema()
