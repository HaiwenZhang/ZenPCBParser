from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from aurora_translator.pipeline import semantic_from_source
from aurora_translator.pipeline.loaders import load_source_payload
from aurora_translator.shared.jsonio import write_json_file
from aurora_translator.shared.logging import log_run_complete
from aurora_translator.sources.aedb import AEDBParserError
from aurora_translator.sources.odbpp import ODBPPParserError

from .common import (
    SOURCE_FORMAT_CHOICES,
    add_logging_arguments,
    add_source_arguments,
    build_source_load_options,
    resolve_aedb_parse_profile_for_target,
    start_cli_logging,
)


logger = logging.getLogger("aurora_translator.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dump source JSON or Semantic JSON payloads."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    source_json = subparsers.add_parser(
        "source-json", help="Write a source-format JSON payload from a source file."
    )
    source_json.add_argument(
        "--format", dest="source_format", choices=SOURCE_FORMAT_CHOICES, required=True
    )
    add_source_arguments(source_json)
    source_json.add_argument("-o", "--output", required=True)
    source_json.add_argument(
        "--summary-only",
        action="store_true",
        help="Skip source-detail extraction when supported.",
    )
    source_json.add_argument("--indent", type=int, default=2)
    add_logging_arguments(source_json)

    semantic_json = subparsers.add_parser(
        "semantic-json", help="Write a SemanticBoard JSON payload from a source file."
    )
    semantic_json.add_argument(
        "--from", dest="source_format", choices=SOURCE_FORMAT_CHOICES, required=True
    )
    add_source_arguments(semantic_json)
    semantic_json.add_argument("-o", "--output", required=True)
    semantic_json.add_argument("--indent", type=int, default=2)
    add_logging_arguments(semantic_json)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    log_path = start_cli_logging(
        args,
        logger,
        "dump",
        command=args.command,
        source_format=args.source_format,
        input=Path(args.input).expanduser().resolve(),
        output=Path(args.output).expanduser().resolve(),
    )

    if args.command == "source-json":
        try:
            options = build_source_load_options(
                args, include_details=not args.summary_only
            )
            options.aedb_parse_profile = resolve_aedb_parse_profile_for_target(
                args,
                source_format=args.source_format,
                target_format=None,
                source_output=args.output,
            )
            payload = load_source_payload(
                args.source_format,
                args.input,
                options=options,
            )
        except (
            AEDBParserError,
            ODBPPParserError,
            OSError,
            ValidationError,
            ValueError,
        ) as exc:
            logger.exception("Source JSON dump failed")
            print(f"Failed to build source JSON payload: {exc}")
            print(f"Log written to: {log_path}")
            return 1
        output = write_json_file(payload, args.output, indent=args.indent)
        print(f"Source JSON written to: {output}")
        print(f"Log written to: {log_path}")
        log_run_complete(logger, "dump")
        return 0

    try:
        options = build_source_load_options(args, include_details=True)
        options.aedb_parse_profile = resolve_aedb_parse_profile_for_target(
            args,
            source_format=args.source_format,
            target_format=None,
            semantic_output=args.output,
        )
        result = semantic_from_source(
            args.source_format,
            args.input,
            options=options,
        )
    except (
        AEDBParserError,
        ODBPPParserError,
        OSError,
        ValidationError,
        ValueError,
    ) as exc:
        logger.exception("Semantic JSON dump failed")
        print(f"Failed to build Semantic JSON payload: {exc}")
        print(f"Log written to: {log_path}")
        return 1
    output = write_json_file(result.board, args.output, indent=args.indent)
    print(f"Semantic JSON written to: {output}")
    print(f"Log written to: {log_path}")
    log_run_complete(logger, "dump")
    return 0
