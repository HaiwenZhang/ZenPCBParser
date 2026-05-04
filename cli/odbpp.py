from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Sequence

from aurora_translator.shared.logging import log_run_complete
from aurora_translator.sources.odbpp.coverage import build_odbpp_coverage_report
from aurora_translator.sources.odbpp import ODBLayout, ODBPPParserError, parse_odbpp
from aurora_translator.sources.odbpp.schema import odbpp_json_schema
from aurora_translator.semantic.converter import to_semantic_board
from aurora_translator.targets.auroradb.exporter import write_aurora_conversion_package
from aurora_translator.semantic.models import SemanticBoard
from aurora_translator.shared.jsonio import write_json_file

from .common import start_cli_logging


logger = logging.getLogger("aurora_translator.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ODB++ parser backed by the Rust native module when available, with CLI fallback."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser(
        "parse", help="Parse an ODB++ directory or archive."
    )
    parse_parser.add_argument(
        "source", help="Path to an ODB++ directory, .zip, .tgz, .tar.gz, or .tar."
    )
    parse_parser.add_argument(
        "-o", "--output", help="Write the parsed ODB++ JSON payload to this file."
    )
    parse_parser.add_argument(
        "--step", help="ODB++ step to use for detailed layer/component/net extraction."
    )
    parse_parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Skip selected-step detail extraction.",
    )
    parse_parser.add_argument(
        "--stdout-json", action="store_true", help="Print the JSON payload to stdout."
    )
    parse_parser.add_argument(
        "--rust-binary",
        help="Explicit path to the compiled odbpp_parser executable. Providing this forces the CLI backend.",
    )
    parse_parser.add_argument(
        "--indent", type=int, default=2, help="JSON indentation width. Default: 2."
    )
    parse_parser.add_argument(
        "--log-file",
        help="Write parser logs to this file. Default: logs/aurora_translator.log",
    )
    parse_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level. Default: INFO.",
    )

    schema_parser = subparsers.add_parser(
        "schema", help="Print or write the ODB++ JSON schema."
    )
    schema_parser.add_argument(
        "-o", "--output", help="Write the schema to a file instead of stdout."
    )
    schema_parser.add_argument("--indent", type=int, default=2)

    coverage_parser = subparsers.add_parser(
        "coverage", help="Build an ODB++ conversion coverage report."
    )
    coverage_parser.add_argument(
        "source",
        help="Path to an ODB++ directory, archive, or parsed ODB++ JSON payload.",
    )
    coverage_parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Write the coverage report JSON to this file.",
    )
    coverage_parser.add_argument(
        "--step",
        help="ODB++ step to use for detailed extraction when source is not JSON.",
    )
    coverage_parser.add_argument(
        "--semantic-json",
        help="Optional existing Semantic JSON payload to include in the report.",
    )
    coverage_parser.add_argument(
        "--aaf-dir",
        help="Optional Aurora/AAF package directory with aaf/design.layout and aaf/design.part.",
    )
    coverage_parser.add_argument(
        "--auroradb-dir", help="Optional compiled AuroraDB directory."
    )
    coverage_parser.add_argument(
        "--rust-binary",
        help="Explicit path to the compiled odbpp_parser executable. Providing this forces the CLI backend.",
    )
    coverage_parser.add_argument(
        "--indent", type=int, default=2, help="JSON indentation width. Default: 2."
    )
    coverage_parser.add_argument(
        "--log-file",
        help="Write parser logs to this file. Default: logs/aurora_translator.log",
    )
    coverage_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level. Default: INFO.",
    )

    to_auroradb_parser = subparsers.add_parser(
        "to-auroradb",
        help="Parse ODB++, convert it through SemanticBoard, and write Aurora/AAF plus AuroraDB files.",
    )
    to_auroradb_parser.add_argument(
        "source", help="Path to an ODB++ directory, .zip, .tgz, .tar.gz, or .tar."
    )
    to_auroradb_parser.add_argument(
        "-o", "--out", required=True, help="Output directory."
    )
    to_auroradb_parser.add_argument(
        "--step", help="ODB++ step to use for detailed extraction."
    )
    to_auroradb_parser.add_argument(
        "--rust-binary",
        help="Explicit path to the compiled odbpp_parser executable. Providing this forces the CLI backend.",
    )
    to_auroradb_parser.add_argument(
        "--odbpp-output", help="Optional path for the intermediate ODB++ JSON payload."
    )
    to_auroradb_parser.add_argument(
        "--semantic-output",
        help="Optional path for the intermediate Semantic JSON payload.",
    )
    to_auroradb_parser.add_argument(
        "--coverage-output",
        help="Optional path for the ODB++ conversion coverage report.",
    )
    to_auroradb_parser.add_argument(
        "--export-aaf",
        action="store_true",
        help="Also keep aaf/design.layout and aaf/design.part in the output directory.",
    )
    to_auroradb_parser.add_argument(
        "--no-compile",
        action="store_true",
        help="Skip AuroraDB compilation and only write stackup.dat, stackup.json, and AAF files.",
    )
    to_auroradb_parser.add_argument(
        "--indent", type=int, default=2, help="JSON indentation width. Default: 2."
    )
    to_auroradb_parser.add_argument(
        "--log-file",
        help="Write parser logs to this file. Default: logs/aurora_translator.log",
    )
    to_auroradb_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level. Default: INFO.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "schema":
        schema_text = json.dumps(
            odbpp_json_schema(), ensure_ascii=False, indent=args.indent
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(schema_text, encoding="utf-8")
            print(f"Schema written to: {output}")
        else:
            print(schema_text)
        return 0

    if args.command == "parse":
        log_path = start_cli_logging(
            args,
            logger,
            "odbpp",
            command=args.command,
            source=Path(args.source).expanduser().resolve(),
            output=Path(args.output).expanduser().resolve() if args.output else None,
            step=args.step,
            summary_only=args.summary_only,
            rust_binary=args.rust_binary,
        )
        try:
            payload = parse_odbpp(
                args.source,
                step=args.step,
                include_details=not args.summary_only,
                rust_binary=args.rust_binary,
            )
        except ODBPPParserError as exc:
            logger.exception("ODB++ parse failed")
            print(f"Failed to parse ODB++: {exc}")
            print(f"Log written to: {log_path}")
            return 1

        if args.output:
            output_path = write_json_file(payload, args.output, indent=args.indent)
        else:
            output_path = None

        _print_summary(payload, output_path=output_path, log_path=log_path)

        if args.stdout_json:
            print(payload.model_dump_json(indent=args.indent))
        log_run_complete(logger, "odbpp")
        return 0

    if args.command == "coverage":
        log_path = start_cli_logging(
            args,
            logger,
            "odbpp",
            command=args.command,
            source=Path(args.source).expanduser().resolve(),
            output=Path(args.output).expanduser().resolve(),
            step=args.step,
            semantic_json=Path(args.semantic_json).expanduser().resolve()
            if args.semantic_json
            else None,
            aaf_dir=Path(args.aaf_dir).expanduser().resolve() if args.aaf_dir else None,
            auroradb_dir=Path(args.auroradb_dir).expanduser().resolve()
            if args.auroradb_dir
            else None,
        )
        try:
            payload = _load_or_parse_odbpp(
                args.source,
                step=args.step,
                rust_binary=args.rust_binary,
            )
            semantic_board = (
                _load_semantic_board(args.semantic_json) if args.semantic_json else None
            )
        except (ODBPPParserError, OSError, ValueError) as exc:
            logger.exception("ODB++ coverage report failed")
            print(f"Failed to build ODB++ coverage report: {exc}")
            print(f"Log written to: {log_path}")
            return 1
        report = build_odbpp_coverage_report(
            payload,
            semantic_board,
            aaf_dir=args.aaf_dir,
            auroradb_dir=args.auroradb_dir,
        )
        output = _write_json_report(report, args.output, indent=args.indent)
        print(f"Coverage report written to: {output}")
        print(f"Log written to: {log_path}")
        log_run_complete(logger, "odbpp")
        return 0

    if args.command == "to-auroradb":
        log_path = start_cli_logging(
            args,
            logger,
            "odbpp",
            command=args.command,
            source=Path(args.source).expanduser().resolve(),
            output=Path(args.out).expanduser().resolve(),
            step=args.step,
            odbpp_output=Path(args.odbpp_output).expanduser().resolve()
            if args.odbpp_output
            else None,
            semantic_output=Path(args.semantic_output).expanduser().resolve()
            if args.semantic_output
            else None,
            coverage_output=Path(args.coverage_output).expanduser().resolve()
            if args.coverage_output
            else None,
            export_aaf=args.export_aaf,
            no_compile=args.no_compile,
        )
        try:
            payload = parse_odbpp(
                args.source,
                step=args.step,
                include_details=True,
                rust_binary=args.rust_binary,
            )
        except ODBPPParserError as exc:
            logger.exception("ODB++ parse failed")
            print(f"Failed to parse ODB++: {exc}")
            print(f"Log written to: {log_path}")
            return 1

        semantic_board = to_semantic_board(payload)
        odbpp_output = (
            write_json_file(payload, args.odbpp_output, indent=args.indent)
            if args.odbpp_output
            else None
        )
        semantic_output = (
            write_json_file(semantic_board, args.semantic_output, indent=args.indent)
            if args.semantic_output
            else None
        )
        result = write_aurora_conversion_package(
            semantic_board,
            args.out,
            compile_auroradb=not args.no_compile,
            export_aaf=args.export_aaf,
        )
        coverage_output = None
        if args.coverage_output:
            report = build_odbpp_coverage_report(
                payload,
                semantic_board,
                aaf_dir=result.aaf,
                auroradb_dir=result.auroradb,
            )
            coverage_output = _write_json_report(
                report, args.coverage_output, indent=args.indent
            )
        _print_conversion_summary(
            payload,
            semantic_board,
            output_path=result.root,
            auroradb_path=result.auroradb,
            aaf_path=result.aaf,
            odbpp_output=odbpp_output,
            semantic_output=semantic_output,
            coverage_output=coverage_output,
            log_path=log_path,
        )
        log_run_complete(logger, "odbpp")
        return 0

    parser.error(f"Unknown command {args.command!r}")
    return 2


def _print_summary(
    payload: ODBLayout, *, output_path: Path | None, log_path: Path
) -> None:
    summary = payload.summary
    print(f"ODB++: {payload.metadata.source}")
    print(
        "Backend: "
        f"{payload.metadata.backend} "
        f"(Rust parser {payload.metadata.rust_parser_version}, selected_step={payload.metadata.selected_step})"
    )
    print(
        "Counts: "
        f"steps={summary.step_count}, "
        f"layers={summary.layer_count}, "
        f"feature_layers={summary.feature_layer_count}, "
        f"features={summary.feature_count}, "
        f"symbols={summary.symbol_count}, "
        f"tools={summary.drill_tool_count}, "
        f"packages={summary.package_count}, "
        f"components={summary.component_count}, "
        f"nets={summary.net_count}, "
        f"diagnostics={summary.diagnostic_count}"
    )
    if output_path is not None:
        print(f"JSON written to: {output_path}")
    print(f"Log written to: {log_path}")


def _print_conversion_summary(
    payload: ODBLayout,
    semantic_board: SemanticBoard,
    *,
    output_path: Path,
    auroradb_path: Path | None,
    aaf_path: Path | None,
    odbpp_output: Path | None,
    semantic_output: Path | None,
    coverage_output: Path | None,
    log_path: Path,
) -> None:
    _print_summary(payload, output_path=odbpp_output, log_path=log_path)
    summary = semantic_board.summary
    print(
        "Semantic: "
        f"layers={summary.layer_count}, "
        f"shapes={summary.shape_count}, "
        f"via_templates={summary.via_template_count}, "
        f"nets={summary.net_count}, "
        f"components={summary.component_count}, "
        f"pins={summary.pin_count}, "
        f"pads={summary.pad_count}, "
        f"vias={summary.via_count}, "
        f"primitives={summary.primitive_count}, "
        f"diagnostics={summary.diagnostic_count}"
    )
    if semantic_output is not None:
        print(f"Semantic JSON written to: {semantic_output}")
    if auroradb_path is not None:
        print(f"AuroraDB files written to: {auroradb_path}")
        print(f"Stackup files written to: {output_path}")
    else:
        print(f"AAF package written to: {output_path}")
    if aaf_path is not None:
        print(f"AAF files written to: {aaf_path}")
    if coverage_output is not None:
        print(f"Coverage report written to: {coverage_output}")


def _load_or_parse_odbpp(
    source: str, *, step: str | None, rust_binary: str | None
) -> ODBLayout:
    path = Path(source).expanduser()
    if path.suffix.casefold() == ".json" and path.exists():
        return ODBLayout.model_validate_json(path.read_text(encoding="utf-8-sig"))
    return parse_odbpp(source, step=step, include_details=True, rust_binary=rust_binary)


def _load_semantic_board(path: str) -> SemanticBoard:
    source = Path(path).expanduser()
    return SemanticBoard.model_validate_json(source.read_text(encoding="utf-8-sig"))


def _write_json_report(report: dict[str, object], output: str, *, indent: int) -> Path:
    output_path = Path(output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8"
    )
    return output_path
