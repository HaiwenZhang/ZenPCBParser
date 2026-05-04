from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Sequence

from aurora_translator.shared.logging import log_run_complete

from .common import (
    SOURCE_FORMAT_CHOICES,
    add_logging_arguments,
    add_source_arguments,
    start_cli_logging,
)


logger = logging.getLogger("aurora_translator.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect source files and intermediate AAF command files."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    source_parser = subparsers.add_parser(
        "source", help="Inspect an AEDB, ODB++, BRD, ALG, or AuroraDB source."
    )
    source_parser.add_argument(
        "--format", dest="source_format", choices=SOURCE_FORMAT_CHOICES, required=True
    )
    add_source_arguments(source_parser)
    source_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the summary payload as JSON when available.",
    )
    add_logging_arguments(source_parser)

    aaf_parser = subparsers.add_parser("aaf", help="Inspect AAF command files.")
    aaf_parser.add_argument("--layout", help="Path to design.layout.")
    aaf_parser.add_argument("--part", help="Path to design.part.")
    aaf_parser.add_argument("--indent", type=int, default=2)
    add_logging_arguments(aaf_parser)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    log_path = start_cli_logging(
        args,
        logger,
        "inspect",
        command=args.command,
        source_format=getattr(args, "source_format", None),
        input=Path(args.input).expanduser().resolve()
        if hasattr(args, "input")
        else None,
        layout=Path(args.layout).expanduser().resolve()
        if getattr(args, "layout", None)
        else None,
        part=Path(args.part).expanduser().resolve()
        if getattr(args, "part", None)
        else None,
    )

    if args.command == "aaf":
        from aurora_translator.targets.auroradb.aaf.parser import parse_command_file

        if not args.layout and not args.part:
            parser.error("inspect aaf requires --layout and/or --part.")
        payload: dict[str, object] = {}
        if args.part:
            payload["part"] = parse_command_file(args.part).summary()
        if args.layout:
            payload["layout"] = parse_command_file(args.layout).summary()
        print(json.dumps(payload, ensure_ascii=False, indent=args.indent))
        print(f"Log written to: {log_path}")
        log_run_complete(logger, "inspect")
        return 0

    if args.source_format == "aedb":
        from aurora_translator.sources.aedb import AEDBParserError, parse_aedb

        try:
            payload = parse_aedb(
                args.input,
                version=args.aedt_version,
                include_details=False,
                component_center_source=args.component_center_source,
            )
        except AEDBParserError as exc:
            logger.exception("AEDB inspection failed")
            print(f"Failed to inspect AEDB source: {exc}")
            print(f"Log written to: {log_path}")
            return 1
        summary = payload.summary.model_dump()
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(f"AEDB: {payload.metadata.source}")
            print(
                "Counts: "
                f"layers={summary['layer_count']}, "
                f"nets={summary['net_count']}, "
                f"components={summary['component_count']}, "
                f"paths={summary['path_count']}, "
                f"polygons={summary['polygon_count']}"
            )
        print(f"Log written to: {log_path}")
        log_run_complete(logger, "inspect")
        return 0

    if args.source_format == "odbpp":
        from aurora_translator.sources.odbpp import ODBPPParserError, parse_odbpp

        try:
            payload = parse_odbpp(
                args.input,
                step=args.step,
                include_details=False,
                rust_binary=args.rust_binary,
            )
        except ODBPPParserError as exc:
            logger.exception("ODB++ inspection failed")
            print(f"Failed to inspect ODB++ source: {exc}")
            print(f"Log written to: {log_path}")
            return 1
        summary = payload.summary.model_dump()
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(f"ODB++: {payload.metadata.source}")
            print(
                "Counts: "
                f"steps={summary['step_count']}, "
                f"layers={summary['layer_count']}, "
                f"components={summary['component_count']}, "
                f"nets={summary['net_count']}, "
                f"diagnostics={summary['diagnostic_count']}"
            )
        print(f"Log written to: {log_path}")
        log_run_complete(logger, "inspect")
        return 0

    if args.source_format == "brd":
        from aurora_translator.sources.brd import BRDParserError, parse_brd

        try:
            payload = parse_brd(
                args.input,
                include_details=False,
                rust_binary=args.rust_binary,
            )
        except BRDParserError as exc:
            logger.exception("BRD inspection failed")
            print(f"Failed to inspect BRD source: {exc}")
            print(f"Log written to: {log_path}")
            return 1
        summary = payload.summary.model_dump()
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(f"BRD: {payload.metadata.source}")
            print(
                "Counts: "
                f"format={summary['format_version']}, "
                f"strings={summary['string_count']}, "
                f"objects={summary['object_count_parsed']}/{summary['object_count_declared']}, "
                f"nets={summary['net_count']}, "
                f"padstacks={summary['padstack_count']}, "
                f"footprints={summary['footprint_count']}, "
                f"vias={summary['via_count']}, "
                f"diagnostics={summary['diagnostic_count']}"
            )
        print(f"Log written to: {log_path}")
        log_run_complete(logger, "inspect")
        return 0

    if args.source_format == "alg":
        from aurora_translator.sources.alg import ALGParserError, parse_alg

        try:
            payload = parse_alg(
                args.input,
                include_details=False,
                rust_binary=args.rust_binary,
            )
        except ALGParserError as exc:
            logger.exception("ALG inspection failed")
            print(f"Failed to inspect ALG source: {exc}")
            print(f"Log written to: {log_path}")
            return 1
        summary = payload.summary.model_dump()
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(f"ALG: {payload.metadata.source}")
            print(
                "Counts: "
                f"sections={summary['section_count']}, "
                f"layers={summary['metal_layer_count']}/{summary['layer_count']}, "
                f"components={summary['component_count']}, "
                f"pins={summary['pin_count']}, "
                f"pads={summary['pad_count']}, "
                f"vias={summary['via_count']}, "
                f"tracks={summary['track_count']}, "
                f"nets={summary['net_count']}, "
                f"diagnostics={summary['diagnostic_count']}"
            )
        print(f"Log written to: {log_path}")
        log_run_complete(logger, "inspect")
        return 0

    from aurora_translator.sources.auroradb.inspect import format_summary
    from aurora_translator.sources.auroradb.reader import read_auroradb

    try:
        package = read_auroradb(args.input)
    except OSError as exc:
        logger.exception("AuroraDB inspection failed")
        print(f"Failed to inspect AuroraDB source: {exc}")
        print(f"Log written to: {log_path}")
        return 1
    if args.json:
        print(
            json.dumps(
                package.to_dict(include_blocks=False), ensure_ascii=False, indent=2
            )
        )
    else:
        print(format_summary(package))
    print(f"Log written to: {log_path}")
    log_run_complete(logger, "inspect")
    return 0
