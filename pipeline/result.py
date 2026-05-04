from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aurora_translator.semantic.models import SemanticBoard
from aurora_translator.targets.auroradb import SemanticAuroraExport

from .types import SourceFormat, TargetFormat


@dataclass(slots=True)
class SourceToSemanticResult:
    source_format: SourceFormat
    source_path: Path
    payload: object
    board: SemanticBoard


@dataclass(slots=True)
class SourceToTargetResult:
    source_format: SourceFormat
    target_format: TargetFormat
    source_path: Path
    payload: object
    board: SemanticBoard
    export: SemanticAuroraExport
