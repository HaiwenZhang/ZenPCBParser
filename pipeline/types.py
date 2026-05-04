from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


SourceFormat = Literal["aedb", "auroradb", "odbpp", "brd", "alg", "altium"]
TargetFormat = Literal["aaf", "auroradb", "odbpp"]
AEDBParseProfile = Literal["full", "auroradb-minimal"]
AEDBBackend = Literal["pyedb", "def-binary"]


@dataclass(slots=True)
class SourceLoadOptions:
    aedb_backend: AEDBBackend = "pyedb"
    aedt_version: str | None = None
    component_center_source: Literal["pin-bbox", "layout-instance"] = "pin-bbox"
    aedb_parse_profile: AEDBParseProfile = "full"
    step: str | None = None
    rust_binary: str | Path | None = None
    include_details: bool = True
    include_raw_blocks: bool = False
    build_semantic_connectivity: bool = True
