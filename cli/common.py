from __future__ import annotations

import argparse
import logging
from pathlib import Path

from aurora_translator.pipeline.types import SourceLoadOptions
from aurora_translator.shared.logging import configure_logging, log_run_start


SOURCE_FORMAT_CHOICES = ["aedb", "auroradb", "odbpp", "brd", "alg"]
TARGET_FORMAT_CHOICES = ["aaf", "auroradb", "odbpp"]


def add_logging_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--log-file",
        help="Write logs to this file. Default: logs/aurora_translator.log",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level. Default: INFO.",
    )


def start_cli_logging(
    args: argparse.Namespace,
    logger: logging.Logger,
    title: str,
    **fields: object,
) -> Path:
    log_path = configure_logging(log_file=args.log_file, level=args.log_level)
    log_run_start(logger, title, log_path=log_path, **fields)
    return log_path


def add_source_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("input", help="Path to the source file or directory.")
    parser.add_argument(
        "--aedt-version",
        help="Explicit AEDT version for AEDB parsing, for example 2026.1.",
    )
    parser.add_argument(
        "--component-center-source",
        choices=["pin-bbox", "layout-instance"],
        default="pin-bbox",
        help="How to populate AEDB component.center. Default: pin-bbox.",
    )
    parser.add_argument(
        "--aedb-parse-profile",
        choices=["auto", "full", "auroradb-minimal"],
        default="auto",
        help=(
            "AEDB parse profile. Default: auto. "
            "The convert AEDB->AuroraDB path uses auroradb-minimal only when no intermediate JSON is requested."
        ),
    )
    parser.add_argument("--step", help="ODB++ step to use for detailed extraction.")
    parser.add_argument(
        "--rust-binary",
        help="Explicit path to the compiled Rust source parser executable. Providing this forces the CLI backend.",
    )
    parser.add_argument(
        "--include-raw-blocks",
        action="store_true",
        help="Include raw AuroraDB block trees when loading AuroraDB source JSON payloads.",
    )
    parser.add_argument(
        "--skip-semantic-connectivity",
        action="store_true",
        help="Skip AEDB SemanticBoard connectivity edge/diagnostic construction when it is not needed.",
    )


def build_source_load_options(
    args: argparse.Namespace,
    *,
    include_details: bool,
) -> SourceLoadOptions:
    aedb_parse_profile = getattr(args, "aedb_parse_profile", "full")
    if aedb_parse_profile == "auto":
        aedb_parse_profile = "full"
    return SourceLoadOptions(
        aedt_version=getattr(args, "aedt_version", None),
        component_center_source=getattr(args, "component_center_source", "pin-bbox"),
        aedb_parse_profile=aedb_parse_profile,
        step=getattr(args, "step", None),
        rust_binary=getattr(args, "rust_binary", None),
        include_details=include_details,
        include_raw_blocks=getattr(args, "include_raw_blocks", False),
        build_semantic_connectivity=not getattr(
            args, "skip_semantic_connectivity", False
        ),
    )


def resolve_aedb_parse_profile_for_target(
    args: argparse.Namespace,
    *,
    source_format: str,
    target_format: str | None,
    source_output: str | None = None,
    semantic_output: str | None = None,
) -> str:
    requested_profile = getattr(args, "aedb_parse_profile", "auto")
    if source_format != "aedb":
        return "full"
    if requested_profile != "auto":
        if requested_profile == "auroradb-minimal":
            if target_format != "auroradb":
                raise ValueError(
                    "AEDB auroradb-minimal profile is only valid for AEDB to AuroraDB conversion."
                )
            if source_output or semantic_output:
                raise ValueError(
                    "AEDB auroradb-minimal profile cannot be used with --source-output or --semantic-output."
                )
        return requested_profile
    if target_format == "auroradb" and not source_output and not semantic_output:
        return "auroradb-minimal"
    return "full"
