from __future__ import annotations

from typing import Any

from .models import AuroraDBModel


def auroradb_json_schema() -> dict[str, Any]:
    return AuroraDBModel.model_json_schema()
