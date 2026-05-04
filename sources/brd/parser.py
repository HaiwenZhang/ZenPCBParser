from __future__ import annotations

import importlib
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
from functools import lru_cache
from types import ModuleType
from typing import Any

from aurora_translator.shared.logging import log_kv, log_timing
from aurora_translator.sources.brd.errors import BRDParserError
from aurora_translator.sources.brd.models import BRDLayout
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
    with log_timing(logger, "validate BRDLayout model"):
        return BRDLayout.model_validate(raw_payload)


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
        raw_payload: dict[str, Any] = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise BRDParserError(f"Rust BRD parser returned invalid JSON: {exc}") from exc
    with log_timing(logger, "validate BRDLayout model"):
        return BRDLayout.model_validate(raw_payload)


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
