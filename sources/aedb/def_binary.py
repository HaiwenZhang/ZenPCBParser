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
from aurora_translator.sources.aedb.errors import AEDBParserError
from aurora_translator.sources.aedb.def_models import AEDBDefBinaryLayout
from aurora_translator.sources.aedb.version import (
    AEDB_DEF_BINARY_JSON_SCHEMA_VERSION,
    AEDB_DEF_BINARY_PARSER_VERSION,
)
from aurora_translator.version import PROJECT_VERSION


logger = logging.getLogger("aurora_translator.aedb.def_binary")
NATIVE_MODULE_NAME = "aurora_aedb_native"


def parse_aedb_def_binary(
    source_path: str | Path,
    *,
    include_details: bool = True,
    rust_binary: str | Path | None = None,
) -> AEDBDefBinaryLayout:
    """Parse an AEDB `.def` file with the Rust binary parser."""

    source = resolve_def_source(source_path)
    native_module = None if rust_binary is not None else _load_native_module()
    if native_module is not None:
        return _parse_aedb_def_native(
            native_module, source, include_details=include_details
        )
    return _parse_aedb_def_cli(
        source, include_details=include_details, rust_binary=rust_binary
    )


def resolve_def_source(source_path: str | Path) -> Path:
    source = Path(source_path).expanduser()
    if not source.exists():
        raise AEDBParserError(f"AEDB DEF path does not exist: {source}")
    if source.is_file():
        if source.suffix.lower() != ".def":
            raise AEDBParserError(f"Expected a .def file, got: {source}")
        return source
    if not source.is_dir():
        raise AEDBParserError(f"AEDB DEF source must be a file or directory: {source}")
    candidates = sorted(source.glob("*.def"))
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise AEDBParserError(f"No .def file was found under: {source}")
    names = ", ".join(candidate.name for candidate in candidates[:10])
    raise AEDBParserError(
        f"Multiple .def files were found under {source}; pass one explicitly: {names}"
    )


def _parse_aedb_def_native(
    native_module: ModuleType,
    source: Path,
    *,
    include_details: bool,
) -> AEDBDefBinaryLayout:
    log_kv(
        logger,
        "AEDB DEF binary parser settings",
        source=source.resolve(),
        include_details=include_details,
        backend="rust-native",
        native_module=NATIVE_MODULE_NAME,
        project_version=PROJECT_VERSION,
        aedb_def_binary_parser_version=AEDB_DEF_BINARY_PARSER_VERSION,
        aedb_def_binary_json_schema_version=AEDB_DEF_BINARY_JSON_SCHEMA_VERSION,
    )
    try:
        with log_timing(
            logger, "run Rust AEDB DEF native parser", source=source.resolve()
        ):
            raw_payload = native_module.parse_aedb_def(
                str(source),
                include_details=include_details,
                project_version=PROJECT_VERSION,
                parser_version=AEDB_DEF_BINARY_PARSER_VERSION,
                schema_version=AEDB_DEF_BINARY_JSON_SCHEMA_VERSION,
            )
    except Exception as exc:
        raise AEDBParserError(f"Rust AEDB DEF native parser failed: {exc}") from exc
    with log_timing(logger, "validate AEDBDefBinaryLayout model"):
        return AEDBDefBinaryLayout.model_validate(raw_payload)


def _parse_aedb_def_cli(
    source: Path,
    *,
    include_details: bool,
    rust_binary: str | Path | None,
) -> AEDBDefBinaryLayout:
    binary = resolve_rust_binary(rust_binary)
    log_kv(
        logger,
        "AEDB DEF binary parser settings",
        source=source.resolve(),
        include_details=include_details,
        backend="rust-cli",
        rust_binary=binary,
        project_version=PROJECT_VERSION,
        aedb_def_binary_parser_version=AEDB_DEF_BINARY_PARSER_VERSION,
        aedb_def_binary_json_schema_version=AEDB_DEF_BINARY_JSON_SCHEMA_VERSION,
    )
    command = [
        str(binary),
        "parse",
        str(source),
        "--project-version",
        PROJECT_VERSION,
        "--parser-version",
        AEDB_DEF_BINARY_PARSER_VERSION,
        "--schema-version",
        AEDB_DEF_BINARY_JSON_SCHEMA_VERSION,
        "--compact",
    ]
    if not include_details:
        command.append("--summary-only")
    try:
        with log_timing(logger, "run Rust AEDB DEF parser", source=source.resolve()):
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
    except OSError as exc:
        raise AEDBParserError(
            f"Failed to execute Rust AEDB DEF parser {binary}: {exc}"
        ) from exc
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise AEDBParserError(
            "Rust AEDB DEF parser failed with exit code "
            f"{completed.returncode}: {stderr or completed.stdout.strip()}"
        )
    try:
        raw_payload: dict[str, Any] = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AEDBParserError(
            f"Rust AEDB DEF parser returned invalid JSON: {exc}"
        ) from exc
    with log_timing(logger, "validate AEDBDefBinaryLayout model"):
        return AEDBDefBinaryLayout.model_validate(raw_payload)


@lru_cache(maxsize=1)
def _load_native_module() -> ModuleType | None:
    try:
        return importlib.import_module(NATIVE_MODULE_NAME)
    except ImportError as exc:
        logger.debug(
            "AEDB DEF native module %s is not available: %s", NATIVE_MODULE_NAME, exc
        )
        return None


def resolve_rust_binary(rust_binary: str | Path | None = None) -> Path:
    candidates: list[Path] = []
    if rust_binary is not None:
        candidates.append(Path(rust_binary).expanduser())
    env_binary = os.environ.get("AURORA_AEDB_PARSER")
    if env_binary:
        candidates.append(Path(env_binary).expanduser())
    repo_root = Path(__file__).resolve().parents[2]
    executable_name = "aedb_parser.exe" if os.name == "nt" else "aedb_parser"
    candidates.extend(
        [
            repo_root
            / "crates"
            / "aedb_parser"
            / "target"
            / "release"
            / executable_name,
            repo_root
            / "crates"
            / "aedb_parser"
            / "target"
            / "debug"
            / executable_name,
            repo_root / "target" / "release" / executable_name,
            repo_root / "target" / "debug" / executable_name,
        ]
    )
    path_binary = shutil.which("aedb_parser")
    if path_binary:
        candidates.append(Path(path_binary))
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    searched = "\n  - ".join(str(candidate) for candidate in candidates)
    raise AEDBParserError(
        "Rust AEDB DEF parser executable was not found. Build it with "
        "`cargo build --release --manifest-path crates/aedb_parser/Cargo.toml`, "
        "or set AURORA_AEDB_PARSER to the executable path. Searched:\n  - "
        f"{searched}"
    )
