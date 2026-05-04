from __future__ import annotations

from pathlib import Path
from typing import Literal

from aurora_translator.sources.aedb.models import AEDBLayout
from aurora_translator.sources.alg.models import ALGLayout
from aurora_translator.sources.altium.models import AltiumLayout
from aurora_translator.sources.auroradb.models import AuroraDBModel
from aurora_translator.sources.brd.models import BRDLayout
from aurora_translator.sources.odbpp.models import ODBLayout
from aurora_translator.semantic.adapters import (
    from_aedb,
    from_alg,
    from_altium,
    from_auroradb,
    from_brd,
    from_odbpp,
)
from aurora_translator.semantic.models import SemanticBoard

SourceFormat = Literal["aedb", "auroradb", "odbpp", "brd", "alg", "altium"]


def to_semantic_board(
    payload: AEDBLayout
    | AuroraDBModel
    | ODBLayout
    | BRDLayout
    | ALGLayout
    | AltiumLayout,
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
    if isinstance(payload, BRDLayout):
        return from_brd(payload)
    if isinstance(payload, ALGLayout):
        return from_alg(payload, build_connectivity=build_connectivity)
    if isinstance(payload, AltiumLayout):
        return from_altium(payload, build_connectivity=build_connectivity)
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
    if source_format == "brd":
        return from_brd(BRDLayout.model_validate_json(text))
    if source_format == "alg":
        return from_alg(
            ALGLayout.model_validate_json(text),
            build_connectivity=build_connectivity,
        )
    if source_format == "altium":
        return from_altium(
            AltiumLayout.model_validate_json(text),
            build_connectivity=build_connectivity,
        )
    raise ValueError(f"Unsupported semantic source format: {source_format!r}")
