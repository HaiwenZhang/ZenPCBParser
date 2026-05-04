from __future__ import annotations

from typing import Any

from aurora_translator.sources.odbpp.models import ODBLayout


def odbpp_json_schema() -> dict[str, Any]:
    """Return the Pydantic JSON schema for ODB++ JSON payloads."""

    return ODBLayout.model_json_schema()
