from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Sequence

from aurora_translator.shared.logging import (
    log_run_complete,
    log_section,
    log_timing,
)
from aurora_translator.shared.metrics import (
    RuntimeMetricsRecorder,
    runtime_metrics_context,
)
from aurora_translator.shared.jsonio import write_json_file

from .common import start_cli_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Aurora Translator command entrypoint. "
            "Without a subcommand, this keeps the legacy AEDB parser behavior."
        ),
        epilog=(
            "Semantic-centered commands:\n"
            "  main.py convert --from <aedb|auroradb|odbpp|brd|alg> --to <aaf|auroradb|odbpp> <input> -o <out>\n"
            "  main.py inspect source --format <aedb|auroradb|odbpp|brd|alg> <input>\n"
            "  main.py dump source-json --format <aedb|auroradb|odbpp|brd|alg> <input> -o <file>\n"
            "  main.py dump semantic-json --from <aedb|auroradb|odbpp|brd|alg> <input> -o <file>\n"
            "  main.py schema --format <aedb|auroradb|odbpp|brd|alg|semantic>\n"
            "Compatibility commands remain available under: auroradb, odbpp, semantic."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("edb_path", nargs="?", help="Path to the .aedb directory.")
    parser.add_argument(
        "-o",
        "--output",
        help="Write the parsed payload to a JSON file instead of only printing a summary.",
    )
    parser.add_argument(
        "--version",
        help="Explicit AEDT version for PyEDB, for example 2024.2.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Skip detailed layout sections and keep only metadata + summary.",
    )
    parser.add_argument(
        "--component-center-source",
        choices=["pin-bbox", "layout-instance"],
        default="pin-bbox",
        help=(
            "How to populate component.center. "
            "pin-bbox computes it from component pin positions; "
            "layout-instance uses the AEDB LayoutObjInstance interface. "
            "Default: pin-bbox."
        ),
    )
    parser.add_argument(
        "--stdout-json",
        action="store_true",
        help="Print the JSON payload to stdout.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation width. Default: 2.",
    )
    parser.add_argument(
        "--print-schema",
        action="store_true",
        help="Print the Pydantic JSON schema for the serialized AEDB structure.",
    )
    parser.add_argument(
        "--schema-output",
        help="Write the Pydantic JSON schema to a file.",
    )
    parser.add_argument(
        "--log-file",
        help="Write parser logs to this file. Default: logs/aurora_translator.log",
    )
    parser.add_argument(
        "--analysis-log-file",
        help=(
            "Write a timing and process-memory analysis log. "
            "Default: <output stem>_analysis.log, or next to the parser log when no JSON output is written."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level. Default: INFO.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "convert":
        from .convert import main as convert_main

        return convert_main(argv[1:])
    if argv and argv[0] == "inspect":
        from .inspect import main as inspect_main

        return inspect_main(argv[1:])
    if argv and argv[0] == "dump":
        from .dump import main as dump_main

        return dump_main(argv[1:])
    if argv and argv[0] == "schema":
        from .schema import main as schema_main

        return schema_main(argv[1:])
    if argv and argv[0] == "auroradb":
        from .auroradb import main as auroradb_main

        return auroradb_main(argv[1:])
    if argv and argv[0] == "odbpp":
        from .odbpp import main as odbpp_main

        return odbpp_main(argv[1:])
    if argv and argv[0] == "semantic":
        from .semantic import main as semantic_main

        return semantic_main(argv[1:])

    parser = build_parser()
    args = parser.parse_args(argv)
    logger = logging.getLogger("aurora_translator.cli")
    log_path = start_cli_logging(
        args,
        logger,
        "layout parser",
        edb_path=args.edb_path,
        output=args.output,
        version=args.version or "auto",
        component_center_source=args.component_center_source,
        summary_only=args.summary_only,
        stdout_json=args.stdout_json,
        indent=args.indent,
        schema_output=args.schema_output,
        print_schema=args.print_schema,
        analysis_log_file=args.analysis_log_file,
        log_level=args.log_level,
    )

    from aurora_translator.sources.aedb import AEDBParserError, AEDBLayout, parse_aedb
    from aurora_translator.sources.aedb.analysis import (
        default_analysis_log_path,
        write_aedb_analysis_log,
    )

    if args.print_schema or args.schema_output:
        with log_timing(logger, "build Pydantic JSON schema"):
            schema_text = json.dumps(
                AEDBLayout.model_json_schema(), ensure_ascii=False, indent=args.indent
            )
        logger.info("Pydantic JSON schema contains %s characters", len(schema_text))
        if args.schema_output:
            schema_path = Path(args.schema_output).expanduser()
            schema_path.parent.mkdir(parents=True, exist_ok=True)
            with log_timing(logger, "write schema file", output=schema_path.resolve()):
                schema_path.write_text(schema_text, encoding="utf-8")
            logger.info(
                "Schema file written to %s with %s bytes",
                schema_path.resolve(),
                schema_path.stat().st_size,
            )
        if args.print_schema:
            logger.info("Pydantic JSON schema printed to stdout")
            print(schema_text)
        if not args.edb_path:
            return 0

    if not args.edb_path:
        parser.error(
            "edb_path is required unless --print-schema or --schema-output is used."
        )

    metrics_recorder = RuntimeMetricsRecorder()
    output_path = None
    log_section(logger, "AEDB parsing")
    with runtime_metrics_context(metrics_recorder):
        try:
            payload = parse_aedb(
                args.edb_path,
                version=args.version,
                include_details=not args.summary_only,
                component_center_source=args.component_center_source,
            )
        except AEDBParserError as exc:
            logger.exception("AEDB parsing failed")
            print(f"Failed to parse AEDB: {exc}")
            return 1

        if args.output:
            with log_timing(
                logger,
                "write JSON output",
                output=Path(args.output).expanduser().resolve(),
            ):
                output_path = write_json_file(payload, args.output, indent=args.indent)
            logger.info(
                "AEDB JSON written to %s with %s bytes",
                output_path,
                output_path.stat().st_size,
            )

    log_section(logger, "Analysis output")
    analysis_log_path = (
        Path(args.analysis_log_file).expanduser().resolve()
        if args.analysis_log_file
        else (default_analysis_log_path(output_path=args.output, log_path=log_path))
    )
    analysis_log_path = write_aedb_analysis_log(
        payload,
        metrics_recorder,
        analysis_log_path,
        output_path=output_path,
        log_path=log_path,
    )
    logger.info(
        "Analysis log written to %s with %s bytes",
        analysis_log_path,
        analysis_log_path.stat().st_size,
    )

    log_section(logger, "Run summary")
    _print_summary(
        payload,
        output_path=output_path,
        log_path=log_path,
        analysis_log_path=analysis_log_path,
    )

    if args.stdout_json:
        logger.info("AEDB JSON printed to stdout")
        print(payload.model_dump_json(indent=args.indent))

    log_run_complete(logger, "layout parser")
    return 0


def _print_summary(
    payload: Any,
    output_path: Path | None,
    log_path: Path,
    analysis_log_path: Path | None,
) -> None:
    metadata = payload.metadata
    summary = payload.summary

    print(f"AEDB: {metadata.source}")
    print(
        "Backend: "
        f"{metadata.backend} via pyedb {metadata.pyedb_version} "
        f"(AEDT {metadata.aedt_version})"
    )
    print(
        "Counts: "
        f"layers={summary.layer_count}, "
        f"nets={summary.net_count}, "
        f"components={summary.component_count}, "
        f"paths={summary.path_count}, "
        f"polygons={summary.polygon_count}, "
        f"padstack_defs={summary.padstack_definition_count}, "
        f"padstack_instances={summary.padstack_instance_count}"
    )
    if output_path is not None:
        print(f"JSON written to: {output_path.resolve()}")
    print(f"Log written to: {log_path}")
    if analysis_log_path is not None:
        print(f"Analysis log written to: {analysis_log_path}")
