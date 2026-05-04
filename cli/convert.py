from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from aurora_translator.pipeline import convert_source_to_target
from aurora_translator.shared.jsonio import write_json_file
from aurora_translator.shared.logging import log_run_complete
from aurora_translator.sources.aedb import AEDBParserError
from aurora_translator.sources.odbpp import ODBPPParserError
from aurora_translator.sources.odbpp.coverage import build_odbpp_coverage_report

from .common import (
    TARGET_FORMAT_CHOICES,
    add_logging_arguments,
    add_source_arguments,
    build_source_load_options,
    resolve_aedb_parse_profile_for_target,
    start_cli_logging,
)


logger = logging.getLogger("aurora_translator.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert source files through SemanticBoard into target formats."
    )
    parser.add_argument(
        "--from",
        dest="source_format",
        choices=["aedb", "auroradb", "odbpp"],
        required=True,
    )
    parser.add_argument(
        "--to", dest="target_format", choices=TARGET_FORMAT_CHOICES, required=True
    )
    add_source_arguments(parser)
    parser.add_argument("-o", "--out", required=True, help="Output directory.")
    parser.add_argument(
        "--source-output",
        help="Optional path for the intermediate source JSON payload.",
    )
    parser.add_argument(
        "--semantic-output",
        help="Optional path for the intermediate Semantic JSON payload.",
    )
    parser.add_argument(
        "--coverage-output",
        help="Optional path for the ODB++ conversion coverage report.",
    )
    parser.add_argument(
        "--export-aaf",
        action="store_true",
        help="For AuroraDB target, also keep aaf/design.layout and aaf/design.part in the output directory.",
    )
    parser.add_argument(
        "--no-compile",
        action="store_true",
        help="For AuroraDB target, skip AuroraDB compilation and only write stackup.dat, stackup.json, and AAF files.",
    )
    parser.add_argument(
        "--indent", type=int, default=2, help="JSON indentation width. Default: 2."
    )
    add_logging_arguments(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    log_path = start_cli_logging(
        args,
        logger,
        "convert",
        source_format=args.source_format,
        target_format=args.target_format,
        input=Path(args.input).expanduser().resolve(),
        output=Path(args.out).expanduser().resolve(),
        source_output=args.source_output,
        semantic_output=args.semantic_output,
        coverage_output=args.coverage_output,
        export_aaf=args.export_aaf,
        no_compile=args.no_compile,
    )

    try:
        options = build_source_load_options(args, include_details=True)
        options.aedb_parse_profile = resolve_aedb_parse_profile_for_target(
            args,
            source_format=args.source_format,
            target_format=args.target_format,
            source_output=args.source_output,
            semantic_output=args.semantic_output,
        )
        result = convert_source_to_target(
            args.source_format,
            args.input,
            args.target_format,
            args.out,
            options=options,
            compile_auroradb=not args.no_compile
            if args.target_format == "auroradb"
            else None,
            export_aaf=args.export_aaf if args.target_format == "auroradb" else False,
        )
    except (
        AEDBParserError,
        ODBPPParserError,
        OSError,
        ValidationError,
        ValueError,
    ) as exc:
        logger.exception("Semantic-centered conversion failed")
        print(f"Failed to convert source through SemanticBoard: {exc}")
        print(f"Log written to: {log_path}")
        return 1

    source_output = (
        write_json_file(result.payload, args.source_output, indent=args.indent)
        if args.source_output
        else None
    )
    semantic_output = (
        write_json_file(result.board, args.semantic_output, indent=args.indent)
        if args.semantic_output
        else None
    )

    coverage_output = None
    if args.coverage_output and args.source_format == "odbpp":
        report = build_odbpp_coverage_report(
            result.payload,
            result.board,
            aaf_dir=result.export.aaf,
            auroradb_dir=result.export.auroradb,
        )
        coverage_path = Path(args.coverage_output).expanduser().resolve()
        coverage_path.parent.mkdir(parents=True, exist_ok=True)
        coverage_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=args.indent) + "\n",
            encoding="utf-8",
        )
        coverage_output = coverage_path

    summary = result.board.summary
    print(f"Source format: {result.source_format}")
    if source_output is not None:
        print(f"Source JSON written to: {source_output}")
    print(
        "Semantic board: "
        f"layers={summary.layer_count}, "
        f"materials={summary.material_count}, "
        f"shapes={summary.shape_count}, "
        f"via_templates={summary.via_template_count}, "
        f"nets={summary.net_count}, "
        f"components={summary.component_count}, "
        f"footprints={summary.footprint_count}, "
        f"pins={summary.pin_count}, "
        f"pads={summary.pad_count}, "
        f"vias={summary.via_count}, "
        f"primitives={summary.primitive_count}, "
        f"diagnostics={summary.diagnostic_count}"
    )
    if semantic_output is not None:
        print(f"Semantic JSON written to: {semantic_output}")
    if result.export.auroradb is not None:
        print(f"AuroraDB written to: {result.export.auroradb}")
        print(f"Stackup files written to: {result.export.root}")
    else:
        print(f"AAF package written to: {result.export.root}")
    if result.export.aaf is not None:
        print(f"AAF files written to: {result.export.aaf}")
    if coverage_output is not None:
        print(f"Coverage report written to: {coverage_output}")
    print(f"Log written to: {log_path}")
    log_run_complete(logger, "convert")
    return 0
