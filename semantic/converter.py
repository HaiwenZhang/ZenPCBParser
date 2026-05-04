from __future__ import annotations

from pathlib import Path
from typing import Literal

from aurora_translator.sources.aedb.models import AEDBLayout
from aurora_translator.sources.auroradb.models import AuroraDBModel
from aurora_translator.sources.odbpp.models import ODBLayout
from aurora_translator.semantic.adapters import from_aedb, from_auroradb, from_odbpp
from aurora_translator.semantic.models import SemanticBoard

SourceFormat = Literal["aedb", "auroradb", "odbpp"]


def to_semantic_board(
    payload: AEDBLayout | AuroraDBModel | ODBLayout,
    *,
    build_connectivity: bool = True,
) -> SemanticBoard:
    """Convert a format-specific payload into a semantic board payload."""

    if isinstance(payload, AEDBLayout):
        return from_aedb(payload, build_connectivity=build_connectivity)
    if isinstance(payload, AuroraDBModel):
        return from_auroradb(payload)
    if isinstance(payload, ODBLayout):
        return from_odbpp(payload)
    raise TypeError(f"Unsupported semantic source payload: {type(payload)!r}")


def from_json_file(
    source_format: SourceFormat, path: str | Path, *, build_connectivity: bool = True
) -> SemanticBoard:
    """Load a format JSON payload from disk and convert it to a semantic board payload."""

    text = Path(path).expanduser().read_text(encoding="utf-8-sig")
    if source_format == "aedb":
        return from_aedb(
            AEDBLayout.model_validate_json(text), build_connectivity=build_connectivity
        )
    if source_format == "auroradb":
        return from_auroradb(AuroraDBModel.model_validate_json(text))
    if source_format == "odbpp":
        return from_odbpp(ODBLayout.model_validate_json(text))
    raise ValueError(f"Unsupported semantic source format: {source_format!r}")
