from __future__ import annotations

from typing import Any

from aurora_translator.semantic.models import SemanticBoard


def semantic_json_schema() -> dict[str, Any]:
    """Return the Pydantic JSON schema for semantic board payloads."""

    return SemanticBoard.model_json_schema()
