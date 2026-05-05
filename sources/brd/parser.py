from __future__ import annotations

import importlib
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from functools import lru_cache
from types import ModuleType
from typing import Any

from aurora_translator.shared.logging import log_kv, log_timing
from aurora_translator.sources.brd.errors import BRDParserError
from aurora_translator.sources.brd.models import (
    BRDBlockSummary,
    BRDComponent,
    BRDComponentInstance,
    BRDFootprint,
    BRDFootprintInstance,
    BRDHeader,
    BRDKeepout,
    BRDLayer,
    BRDLayerInfo,
    BRDLayerMapEntry,
    BRDLayout,
    BRDLinkedList,
    BRDMetadata,
    BRDNet,
    BRDNetAssignment,
    BRDPadDefinition,
    BRDPadstack,
    BRDPadstackComponent,
    BRDPlacedPad,
    BRDSegment,
    BRDShape,
    BRDStringEntry,
    BRDSummary,
    BRDText,
    BRDTrack,
    BRDVia,
)
from aurora_translator.sources.brd.version import (
    BRD_JSON_SCHEMA_VERSION,
    BRD_PARSER_VERSION,
)
from aurora_translator.version import PROJECT_VERSION


logger = logging.getLogger("aurora_translator.brd")
NATIVE_MODULE_NAME = "aurora_brd_native"


def parse_brd(
    source_path: str | Path,
    *,
    include_details: bool = True,
    rust_binary: str | Path | None = None,
) -> BRDLayout:
    source = Path(source_path).expanduser()
    if not source.exists():
        raise BRDParserError(f"BRD path does not exist: {source}")
    if not source.is_file():
        raise BRDParserError(f"BRD source must be a file: {source}")

    native_module = None if rust_binary is not None else _load_native_module()
    if native_module is not None:
        return _parse_brd_native(native_module, source, include_details=include_details)
    return _parse_brd_cli(
        source, include_details=include_details, rust_binary=rust_binary
    )


def _parse_brd_native(
    native_module: ModuleType,
    source: Path,
    *,
    include_details: bool,
) -> BRDLayout:
    log_kv(
        logger,
        "BRD parser settings",
        source=source.resolve(),
        include_details=include_details,
        backend="rust-native",
        native_module=NATIVE_MODULE_NAME,
        project_version=PROJECT_VERSION,
        brd_parser_version=BRD_PARSER_VERSION,
        brd_json_schema_version=BRD_JSON_SCHEMA_VERSION,
    )
    try:
        with log_timing(logger, "run Rust BRD native parser", source=source.resolve()):
            raw_payload = native_module.parse_brd(
                str(source),
                include_details=include_details,
                project_version=PROJECT_VERSION,
                parser_version=BRD_PARSER_VERSION,
                schema_version=BRD_JSON_SCHEMA_VERSION,
            )
    except Exception as exc:
        raise BRDParserError(f"Rust BRD native parser failed: {exc}") from exc
    with log_timing(logger, "construct BRDLayout model"):
        return _construct_brd_layout(raw_payload)


def _parse_brd_cli(
    source: Path,
    *,
    include_details: bool,
    rust_binary: str | Path | None,
) -> BRDLayout:
    binary = resolve_rust_binary(rust_binary)
    log_kv(
        logger,
        "BRD parser settings",
        source=source.resolve(),
        include_details=include_details,
        backend="rust-cli",
        rust_binary=binary,
        project_version=PROJECT_VERSION,
        brd_parser_version=BRD_PARSER_VERSION,
        brd_json_schema_version=BRD_JSON_SCHEMA_VERSION,
    )
    command = [
        str(binary),
        str(source),
        "--project-version",
        PROJECT_VERSION,
        "--parser-version",
        BRD_PARSER_VERSION,
        "--schema-version",
        BRD_JSON_SCHEMA_VERSION,
        "--compact",
    ]
    if not include_details:
        command.append("--summary-only")
    with tempfile.TemporaryDirectory(prefix="aurora_brd_") as temp_dir:
        json_output = Path(temp_dir) / "payload.json"
        command.extend(["--output", str(json_output)])
        try:
            with log_timing(logger, "run Rust BRD parser", source=source.resolve()):
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
        except OSError as exc:
            raise BRDParserError(
                f"Failed to execute Rust BRD parser {binary}: {exc}"
            ) from exc
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            raise BRDParserError(
                f"Rust BRD parser failed with exit code {completed.returncode}: {stderr or completed.stdout.strip()}"
            )
        try:
            with json_output.open("r", encoding="utf-8") as handle:
                raw_payload: dict[str, Any] = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise BRDParserError(
                f"Rust BRD parser returned invalid JSON output: {exc}"
            ) from exc
        with log_timing(logger, "construct BRDLayout model"):
            return _construct_brd_layout(raw_payload)


def _construct_brd_layout(raw_payload: dict[str, Any]) -> BRDLayout:
    """Construct the BRD source model from trusted Rust parser JSON.

    The Rust parser owns schema-shaped BRD JSON. For large boards, revalidating
    hundreds of thousands of nested Pydantic models dominates Python wall time,
    so the Python integration uses Pydantic's trusted construction path here.
    """

    return BRDLayout.model_construct(
        metadata=BRDMetadata.model_construct(**raw_payload["metadata"]),
        summary=BRDSummary.model_construct(**raw_payload["summary"]),
        header=_construct_header(raw_payload["header"]),
        strings=_construct_many(BRDStringEntry, raw_payload.get("strings")),
        layers=_construct_many(BRDLayer, raw_payload.get("layers")),
        nets=_construct_many(BRDNet, raw_payload.get("nets")),
        padstacks=_construct_padstacks(raw_payload.get("padstacks")),
        components=_construct_many(BRDComponent, raw_payload.get("components")),
        component_instances=_construct_many(
            BRDComponentInstance, raw_payload.get("component_instances")
        ),
        footprints=_construct_many(BRDFootprint, raw_payload.get("footprints")),
        footprint_instances=_construct_many(
            BRDFootprintInstance, raw_payload.get("footprint_instances")
        ),
        pad_definitions=_construct_many(
            BRDPadDefinition, raw_payload.get("pad_definitions")
        ),
        placed_pads=_construct_layered_many(
            BRDPlacedPad, raw_payload.get("placed_pads")
        ),
        vias=_construct_layered_many(BRDVia, raw_payload.get("vias")),
        tracks=_construct_layered_many(BRDTrack, raw_payload.get("tracks")),
        segments=_construct_many(BRDSegment, raw_payload.get("segments")),
        shapes=_construct_layered_many(BRDShape, raw_payload.get("shapes")),
        keepouts=_construct_layered_many(BRDKeepout, raw_payload.get("keepouts")),
        net_assignments=_construct_many(
            BRDNetAssignment, raw_payload.get("net_assignments")
        ),
        texts=_construct_texts(raw_payload.get("texts")),
        blocks=_construct_many(BRDBlockSummary, raw_payload.get("blocks")),
        block_counts=raw_payload.get("block_counts") or {},
        diagnostics=raw_payload.get("diagnostics") or [],
    )


def _construct_header(raw: dict[str, Any]) -> BRDHeader:
    data = dict(raw)
    data["linked_lists"] = {
        key: BRDLinkedList.model_construct(**value)
        for key, value in (raw.get("linked_lists") or {}).items()
    }
    data["layer_map"] = _construct_many(BRDLayerMapEntry, raw.get("layer_map")) or []
    return BRDHeader.model_construct(**data)


def _construct_many(model_type, rows: list[dict[str, Any]] | None):
    if rows is None:
        return None
    return [model_type.model_construct(**row) for row in rows]


def _construct_layer_info(
    raw: dict[str, Any] | BRDLayerInfo | None,
) -> BRDLayerInfo | None:
    if raw is None or isinstance(raw, BRDLayerInfo):
        return raw
    return BRDLayerInfo.model_construct(**raw)


def _construct_layered_many(model_type, rows: list[dict[str, Any]] | None):
    if rows is None:
        return None
    result = []
    for row in rows:
        data = dict(row)
        data["layer"] = _construct_layer_info(row.get("layer"))
        result.append(model_type.model_construct(**data))
    return result


def _construct_padstacks(
    rows: list[dict[str, Any]] | None,
) -> list[BRDPadstack] | None:
    if rows is None:
        return None
    result: list[BRDPadstack] = []
    for row in rows:
        data = dict(row)
        data["components"] = (
            _construct_many(BRDPadstackComponent, row.get("components")) or []
        )
        result.append(BRDPadstack.model_construct(**data))
    return result


def _construct_texts(rows: list[dict[str, Any]] | None) -> list[BRDText] | None:
    if rows is None:
        return None
    result: list[BRDText] = []
    for row in rows:
        data = dict(row)
        data["layer"] = _construct_layer_info(row.get("layer"))
        result.append(BRDText.model_construct(**data))
    return result


@lru_cache(maxsize=1)
def _load_native_module() -> ModuleType | None:
    try:
        return importlib.import_module(NATIVE_MODULE_NAME)
    except ImportError as exc:
        logger.debug(
            "BRD native module %s is not available: %s", NATIVE_MODULE_NAME, exc
        )
        return None


def resolve_rust_binary(rust_binary: str | Path | None = None) -> Path:
    candidates: list[Path] = []
    if rust_binary is not None:
        candidates.append(Path(rust_binary).expanduser())
    env_binary = os.environ.get("AURORA_BRD_PARSER")
    if env_binary:
        candidates.append(Path(env_binary).expanduser())
    repo_root = Path(__file__).resolve().parents[2]
    executable_name = "brd_parser.exe" if os.name == "nt" else "brd_parser"
    candidates.extend(
        [
            repo_root
            / "crates"
            / "brd_parser"
            / "target"
            / "release"
            / executable_name,
            repo_root / "crates" / "brd_parser" / "target" / "debug" / executable_name,
            repo_root / "target" / "release" / executable_name,
            repo_root / "target" / "debug" / executable_name,
        ]
    )
    path_binary = shutil.which("brd_parser")
    if path_binary:
        candidates.append(Path(path_binary))
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    searched = "\n  - ".join(str(candidate) for candidate in candidates)
    raise BRDParserError(
        "Rust BRD parser executable was not found. Build it with "
        "`cargo build --release --manifest-path crates/brd_parser/Cargo.toml`, "
        "or set AURORA_BRD_PARSER to the executable path. Searched:\n  - "
        f"{searched}"
    )
