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
from aurora_translator.sources.odbpp.errors import ODBPPParserError
from aurora_translator.sources.odbpp.models import ODBLayout
from aurora_translator.sources.odbpp.version import (
    ODBPP_JSON_SCHEMA_VERSION,
    ODBPP_PARSER_VERSION,
)
from aurora_translator.version import PROJECT_VERSION


logger = logging.getLogger("aurora_translator.odbpp")
NATIVE_MODULE_NAME = "aurora_odbpp_native"


def parse_odbpp(
    source_path: str | Path,
    *,
    step: str | None = None,
    include_details: bool = True,
    rust_binary: str | Path | None = None,
) -> ODBLayout:
    """Parse an ODB++ source through the native Rust module when available, else the Rust CLI."""

    source = Path(source_path).expanduser()
    if not source.exists():
        raise ODBPPParserError(f"ODB++ path does not exist: {source}")

    native_module = None if rust_binary is not None else _load_native_module()
    if native_module is not None:
        return _parse_odbpp_native(
            native_module,
            source,
            step=step,
            include_details=include_details,
        )

    return _parse_odbpp_cli(
        source,
        step=step,
        include_details=include_details,
        rust_binary=rust_binary,
    )


def _parse_odbpp_native(
    native_module: ModuleType,
    source: Path,
    *,
    step: str | None,
    include_details: bool,
) -> ODBLayout:
    log_kv(
        logger,
        "ODB++ parser settings",
        source=source.resolve(),
        step=step or "auto",
        include_details=include_details,
        backend="rust-native",
        native_module=NATIVE_MODULE_NAME,
        project_version=PROJECT_VERSION,
        odbpp_parser_version=ODBPP_PARSER_VERSION,
        odbpp_json_schema_version=ODBPP_JSON_SCHEMA_VERSION,
    )

    try:
        with log_timing(
            logger, "run Rust ODB++ native parser", source=source.resolve()
        ):
            raw_payload = native_module.parse_odbpp(
                str(source),
                step=step,
                include_details=include_details,
                project_version=PROJECT_VERSION,
                parser_version=ODBPP_PARSER_VERSION,
                schema_version=ODBPP_JSON_SCHEMA_VERSION,
            )
    except Exception as exc:
        raise ODBPPParserError(f"Rust ODB++ native parser failed: {exc}") from exc

    with log_timing(logger, "validate ODBLayout model"):
        payload = ODBLayout.model_validate(raw_payload)

    logger.info(
        "Parsed ODB++ with steps:%s layers:%s features:%s components:%s nets:%s diagnostics:%s",
        payload.summary.step_count,
        payload.summary.layer_count,
        payload.summary.feature_count,
        payload.summary.component_count,
        payload.summary.net_count,
        payload.summary.diagnostic_count,
    )
    return payload


def _parse_odbpp_cli(
    source: Path,
    *,
    step: str | None,
    include_details: bool,
    rust_binary: str | Path | None,
) -> ODBLayout:
    binary = resolve_rust_binary(rust_binary)
    log_kv(
        logger,
        "ODB++ parser settings",
        source=source.resolve(),
        step=step or "auto",
        include_details=include_details,
        backend="rust-cli",
        rust_binary=binary,
        project_version=PROJECT_VERSION,
        odbpp_parser_version=ODBPP_PARSER_VERSION,
        odbpp_json_schema_version=ODBPP_JSON_SCHEMA_VERSION,
    )

    command = [
        str(binary),
        str(source),
        "--project-version",
        PROJECT_VERSION,
        "--parser-version",
        ODBPP_PARSER_VERSION,
        "--schema-version",
        ODBPP_JSON_SCHEMA_VERSION,
        "--compact",
    ]
    if step:
        command.extend(["--step", step])
    if not include_details:
        command.append("--summary-only")

    try:
        with log_timing(logger, "run Rust ODB++ parser", source=source.resolve()):
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
    except OSError as exc:
        raise ODBPPParserError(
            f"Failed to execute Rust ODB++ parser {binary}: {exc}"
        ) from exc

    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise ODBPPParserError(
            f"Rust ODB++ parser failed with exit code {completed.returncode}: {stderr or completed.stdout.strip()}"
        )

    try:
        raw_payload: dict[str, Any] = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ODBPPParserError(
            f"Rust ODB++ parser returned invalid JSON: {exc}"
        ) from exc

    with log_timing(logger, "validate ODBLayout model"):
        payload = ODBLayout.model_validate(raw_payload)

    logger.info(
        "Parsed ODB++ with steps:%s layers:%s features:%s components:%s nets:%s diagnostics:%s",
        payload.summary.step_count,
        payload.summary.layer_count,
        payload.summary.feature_count,
        payload.summary.component_count,
        payload.summary.net_count,
        payload.summary.diagnostic_count,
    )
    return payload


@lru_cache(maxsize=1)
def _load_native_module() -> ModuleType | None:
    try:
        return importlib.import_module(NATIVE_MODULE_NAME)
    except ImportError as exc:
        logger.debug(
            "ODB++ native module %s is not available: %s", NATIVE_MODULE_NAME, exc
        )
        return None


def resolve_rust_binary(rust_binary: str | Path | None = None) -> Path:
    """Resolve the odbpp_parser executable from an explicit path, env var, repo build, or PATH."""

    candidates: list[Path] = []
    if rust_binary is not None:
        candidates.append(Path(rust_binary).expanduser())

    env_binary = os.environ.get("AURORA_ODBPP_PARSER")
    if env_binary:
        candidates.append(Path(env_binary).expanduser())

    repo_root = Path(__file__).resolve().parents[2]
    executable_name = "odbpp_parser.exe" if os.name == "nt" else "odbpp_parser"
    candidates.extend(
        [
            repo_root
            / "crates"
            / "odbpp_parser"
            / "target"
            / "release"
            / executable_name,
            repo_root
            / "crates"
            / "odbpp_parser"
            / "target"
            / "debug"
            / executable_name,
            repo_root / "target" / "release" / executable_name,
            repo_root / "target" / "debug" / executable_name,
        ]
    )

    path_binary = shutil.which("odbpp_parser")
    if path_binary:
        candidates.append(Path(path_binary))

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

    searched = "\n  - ".join(str(candidate) for candidate in candidates)
    raise ODBPPParserError(
        "Rust ODB++ parser executable was not found. Build it with "
        "`cargo build --release --manifest-path crates/odbpp_parser/Cargo.toml`, "
        "or set AURORA_ODBPP_PARSER to the executable path. Searched:\n  - "
        f"{searched}"
    )
