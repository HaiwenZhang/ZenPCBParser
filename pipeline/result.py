from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from aurora_translator.semantic.models import SemanticBoard
from aurora_translator.targets.auroradb import SemanticAuroraExport
from aurora_translator.targets.odbpp import SemanticOdbppExport

from .types import SourceFormat, TargetFormat


SemanticTargetExport: TypeAlias = SemanticAuroraExport | SemanticOdbppExport


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
    export: SemanticTargetExport
