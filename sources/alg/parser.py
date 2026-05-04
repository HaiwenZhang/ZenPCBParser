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
from aurora_translator.sources.alg.errors import ALGParserError
from aurora_translator.sources.alg.models import ALGLayout
from aurora_translator.sources.alg.version import (
    ALG_JSON_SCHEMA_VERSION,
    ALG_PARSER_VERSION,
)
from aurora_translator.version import PROJECT_VERSION


logger = logging.getLogger("aurora_translator.alg")
NATIVE_MODULE_NAME = "aurora_alg_native"


def parse_alg(
    source_path: str | Path,
    *,
    include_details: bool = True,
    rust_binary: str | Path | None = None,
) -> ALGLayout:
    source = Path(source_path).expanduser()
    if not source.exists():
        raise ALGParserError(f"ALG path does not exist: {source}")
    if not source.is_file():
        raise ALGParserError(f"ALG source must be a file: {source}")

    native_module = None if rust_binary is not None else _load_native_module()
    if native_module is not None:
        return _parse_alg_native(native_module, source, include_details=include_details)
    return _parse_alg_cli(
        source, include_details=include_details, rust_binary=rust_binary
    )


def _parse_alg_native(
    native_module: ModuleType,
    source: Path,
    *,
    include_details: bool,
) -> ALGLayout:
    log_kv(
        logger,
        "ALG parser settings",
        source=source.resolve(),
        include_details=include_details,
        backend="rust-native",
        native_module=NATIVE_MODULE_NAME,
        project_version=PROJECT_VERSION,
        alg_parser_version=ALG_PARSER_VERSION,
        alg_json_schema_version=ALG_JSON_SCHEMA_VERSION,
    )
    try:
        with log_timing(logger, "run Rust ALG native parser", source=source.resolve()):
            raw_payload = native_module.parse_alg(
                str(source),
                include_details=include_details,
                project_version=PROJECT_VERSION,
                parser_version=ALG_PARSER_VERSION,
                schema_version=ALG_JSON_SCHEMA_VERSION,
            )
    except Exception as exc:
        raise ALGParserError(f"Rust ALG native parser failed: {exc}") from exc
    with log_timing(logger, "validate ALGLayout model"):
        return ALGLayout.model_validate(raw_payload)


def _parse_alg_cli(
    source: Path,
    *,
    include_details: bool,
    rust_binary: str | Path | None,
) -> ALGLayout:
    binary = resolve_rust_binary(rust_binary)
    log_kv(
        logger,
        "ALG parser settings",
        source=source.resolve(),
        include_details=include_details,
        backend="rust-cli",
        rust_binary=binary,
        project_version=PROJECT_VERSION,
        alg_parser_version=ALG_PARSER_VERSION,
        alg_json_schema_version=ALG_JSON_SCHEMA_VERSION,
    )
    command = [
        str(binary),
        str(source),
        "--project-version",
        PROJECT_VERSION,
        "--parser-version",
        ALG_PARSER_VERSION,
        "--schema-version",
        ALG_JSON_SCHEMA_VERSION,
        "--compact",
    ]
    if not include_details:
        command.append("--summary-only")
    try:
        with log_timing(logger, "run Rust ALG parser", source=source.resolve()):
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
    except OSError as exc:
        raise ALGParserError(
            f"Failed to execute Rust ALG parser {binary}: {exc}"
        ) from exc
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise ALGParserError(
            f"Rust ALG parser failed with exit code {completed.returncode}: {stderr or completed.stdout.strip()}"
        )
    try:
        raw_payload: dict[str, Any] = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ALGParserError(f"Rust ALG parser returned invalid JSON: {exc}") from exc
    with log_timing(logger, "validate ALGLayout model"):
        return ALGLayout.model_validate(raw_payload)


@lru_cache(maxsize=1)
def _load_native_module() -> ModuleType | None:
    try:
        return importlib.import_module(NATIVE_MODULE_NAME)
    except ImportError as exc:
        logger.debug(
            "ALG native module %s is not available: %s", NATIVE_MODULE_NAME, exc
        )
        return None


def resolve_rust_binary(rust_binary: str | Path | None = None) -> Path:
    candidates: list[Path] = []
    if rust_binary is not None:
        candidates.append(Path(rust_binary).expanduser())
    env_binary = os.environ.get("AURORA_ALG_PARSER")
    if env_binary:
        candidates.append(Path(env_binary).expanduser())
    repo_root = Path(__file__).resolve().parents[2]
    executable_name = "alg_parser.exe" if os.name == "nt" else "alg_parser"
    candidates.extend(
        [
            repo_root
            / "crates"
            / "alg_parser"
            / "target"
            / "release"
            / executable_name,
            repo_root / "crates" / "alg_parser" / "target" / "debug" / executable_name,
            repo_root / "target" / "release" / executable_name,
            repo_root / "target" / "debug" / executable_name,
        ]
    )
    path_binary = shutil.which("alg_parser")
    if path_binary:
        candidates.append(Path(path_binary))
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    searched = "\n  - ".join(str(candidate) for candidate in candidates)
    raise ALGParserError(
        "Rust ALG parser executable was not found. Build it with "
        "`cargo build --release --manifest-path crates/alg_parser/Cargo.toml`, "
        "or set AURORA_ALG_PARSER to the executable path. Searched:\n  - "
        f"{searched}"
    )
