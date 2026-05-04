from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from aurora_translator.pipeline import (
    convert_semantic_to_target,
    convert_source_to_target,
    semantic_from_source,
)
from aurora_translator.semantic.converter import from_json_file
from aurora_translator.semantic.models import SemanticBoard
from aurora_translator.semantic.schema import semantic_json_schema
from aurora_translator.shared.jsonio import write_json_file
from aurora_translator.shared.logging import log_run_complete
from aurora_translator.sources.aedb import AEDBParserError
from aurora_translator.sources.alg import ALGParserError
from aurora_translator.sources.altium import AltiumParserError
from aurora_translator.sources.brd import BRDParserError
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
        description="Semantic board conversion and schema tools."
    )
    add_logging_arguments(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    from_json_parser = subparsers.add_parser(
        "from-json",
        help="Convert a format-specific JSON payload into the semantic board model.",
    )
    from_json_parser.add_argument("source_format", choices=SOURCE_FORMAT_CHOICES)
    from_json_parser.add_argument("input", help="Path to the source JSON payload.")
    from_json_parser.add_argument(
        "-o", "--out", help="Base output directory for optional generated files."
    )
    from_json_parser.add_argument(
        "--semantic-output",
        help="Optional semantic JSON filename or path. Relative paths are resolved under --out.",
    )
    from_json_parser.add_argument(
        "--stdout-json",
        action="store_true",
        help="Print the semantic JSON payload to stdout.",
    )
    from_json_parser.add_argument(
        "--indent", type=int, default=2, help="JSON indentation width. Default: 2."
    )
    add_logging_arguments(from_json_parser)

    from_source_parser = subparsers.add_parser(
        "from-source",
        help="Build a semantic board directly from an AEDB, AuroraDB, or ODB++ source path.",
    )
    from_source_parser.add_argument("source_format", choices=SOURCE_FORMAT_CHOICES)
    add_source_arguments(from_source_parser)
    from_source_parser.add_argument(
        "-o", "--out", help="Base output directory for optional generated files."
    )
    from_source_parser.add_argument(
        "--semantic-output",
        help="Optional semantic JSON filename or path. Relative paths are resolved under --out.",
    )
    from_source_parser.add_argument(
        "--stdout-json",
        action="store_true",
        help="Print the semantic JSON payload to stdout.",
    )
    from_source_parser.add_argument(
        "--indent", type=int, default=2, help="JSON indentation width. Default: 2."
    )
    add_logging_arguments(from_source_parser)

    schema_parser = subparsers.add_parser(
        "schema", help="Print or write the semantic JSON schema."
    )
    schema_parser.add_argument(
        "-o", "--output", help="Write the schema to a file instead of stdout."
    )
    schema_parser.add_argument("--indent", type=int, default=2)
    add_logging_arguments(schema_parser)

    to_auroradb_parser = subparsers.add_parser(
        "to-auroradb",
        help="Convert a semantic board JSON payload into an Aurora/AAF package and AuroraDB files.",
    )
    to_auroradb_parser.add_argument(
        "input", help="Path to the semantic board JSON payload."
    )
    to_auroradb_parser.add_argument(
        "-o", "--out", required=True, help="Output directory."
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
    add_logging_arguments(to_auroradb_parser)

    to_aaf_parser = subparsers.add_parser(
        "to-aaf",
        help="Convert a semantic board JSON payload into Aurora/AAF package files.",
    )
    to_aaf_parser.add_argument("input", help="Path to the semantic board JSON payload.")
    to_aaf_parser.add_argument(
        "-o", "--out", required=True, help="Output AAF package directory."
    )
    add_logging_arguments(to_aaf_parser)

    source_to_aaf_parser = subparsers.add_parser(
        "source-to-aaf",
        help="Convert an AEDB, AuroraDB, or ODB++ source path into Aurora/AAF package files.",
    )
    source_to_aaf_parser.add_argument("source_format", choices=SOURCE_FORMAT_CHOICES)
    add_source_arguments(source_to_aaf_parser)
    source_to_aaf_parser.add_argument(
        "-o", "--out", required=True, help="Output AAF package directory."
    )
    source_to_aaf_parser.add_argument(
        "--semantic-output",
        help="Optional semantic JSON filename or path. Relative paths are resolved under --out.",
    )
    source_to_aaf_parser.add_argument(
        "--indent", type=int, default=2, help="JSON indentation width. Default: 2."
    )
    add_logging_arguments(source_to_aaf_parser)

    source_to_auroradb_parser = subparsers.add_parser(
        "source-to-auroradb",
        help="Convert an AEDB, AuroraDB, or ODB++ source path into Aurora/AAF and AuroraDB files.",
    )
    source_to_auroradb_parser.add_argument(
        "source_format", choices=SOURCE_FORMAT_CHOICES
    )
    add_source_arguments(source_to_auroradb_parser)
    source_to_auroradb_parser.add_argument(
        "-o", "--out", required=True, help="Output directory."
    )
    source_to_auroradb_parser.add_argument(
        "--export-aaf",
        action="store_true",
        help="Also keep aaf/design.layout and aaf/design.part in the output directory.",
    )
    source_to_auroradb_parser.add_argument(
        "--semantic-output",
        help="Optional semantic JSON filename or path. Relative paths are resolved under --out.",
    )
    source_to_auroradb_parser.add_argument(
        "--indent", type=int, default=2, help="JSON indentation width. Default: 2."
    )
    add_logging_arguments(source_to_auroradb_parser)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    log_path = start_cli_logging(
        args,
        logger,
        "semantic",
        command=args.command,
        source_format=getattr(args, "source_format", None),
        input=Path(args.input).expanduser().resolve()
        if getattr(args, "input", None)
        else None,
        output=Path(getattr(args, "out", None)).expanduser().resolve()
        if getattr(args, "out", None)
        else (
            Path(getattr(args, "output", None)).expanduser().resolve()
            if getattr(args, "output", None)
            else None
        ),
        semantic_output=getattr(args, "semantic_output", None),
        export_aaf=getattr(args, "export_aaf", None),
        no_compile=getattr(args, "no_compile", None),
    )

    if args.command == "schema":
        schema_text = json.dumps(
            semantic_json_schema(), ensure_ascii=False, indent=args.indent
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(schema_text, encoding="utf-8")
            print(f"Schema written to: {output}")
        else:
            print(schema_text)
        print(f"Log written to: {log_path}")
        log_run_complete(logger, "semantic")
        return 0

    if args.command == "from-json":
        try:
            payload = from_json_file(args.source_format, args.input)
        except (
            AEDBParserError,
            ALGParserError,
            AltiumParserError,
            ODBPPParserError,
            BRDParserError,
            OSError,
            ValidationError,
            ValueError,
        ) as exc:
            logger.exception("Semantic payload build failed")
            print(f"Failed to build semantic payload: {exc}")
            return 1

        semantic_output = _resolve_output_path(args.out, args.semantic_output)
        output_path = (
            write_json_file(payload, semantic_output, indent=args.indent)
            if semantic_output
            else None
        )
        _print_summary(
            payload.summary.model_dump(), output_path=output_path, log_path=log_path
        )
        if args.stdout_json:
            print(payload.model_dump_json(indent=args.indent))
        log_run_complete(logger, "semantic")
        return 0

    if args.command == "from-source":
        try:
            options = build_source_load_options(args, include_details=True)
            options.aedb_parse_profile = resolve_aedb_parse_profile_for_target(
                args,
                source_format=args.source_format,
                target_format=None,
                semantic_output=args.semantic_output
                or ("stdout" if args.stdout_json else None),
            )
            result = semantic_from_source(
                args.source_format,
                args.input,
                options=options,
            )
        except (
            AEDBParserError,
            ALGParserError,
            AltiumParserError,
            ODBPPParserError,
            BRDParserError,
            OSError,
            ValidationError,
            ValueError,
        ) as exc:
            logger.exception("Semantic payload build failed")
            print(f"Failed to build semantic payload: {exc}")
            return 1

        semantic_output = _resolve_output_path(args.out, args.semantic_output)
        output_path = (
            write_json_file(result.board, semantic_output, indent=args.indent)
            if semantic_output
            else None
        )
        _print_summary(
            result.board.summary.model_dump(),
            output_path=output_path,
            log_path=log_path,
        )
        if args.stdout_json:
            print(result.board.model_dump_json(indent=args.indent))
        log_run_complete(logger, "semantic")
        return 0

    if args.command in {"to-aaf", "to-auroradb"}:
        try:
            payload = SemanticBoard.model_validate_json(
                Path(args.input).expanduser().read_text(encoding="utf-8-sig")
            )
        except (OSError, ValidationError) as exc:
            logger.exception("Semantic payload load failed")
            print(f"Failed to load semantic payload: {exc}")
            return 1

        target_format = "aaf" if args.command == "to-aaf" else "auroradb"
        export = convert_semantic_to_target(
            payload,
            target_format,
            args.out,
            compile_auroradb=False
            if args.command == "to-auroradb" and args.no_compile
            else None,
            export_aaf=args.export_aaf if args.command == "to-auroradb" else False,
        )
        _print_export_summary(
            payload,
            output_path=export.root,
            auroradb_path=export.auroradb,
            aaf_path=export.aaf,
            semantic_output=None,
            log_path=log_path,
        )
        log_run_complete(logger, "semantic")
        return 0

    try:
        target_format = "aaf" if args.command == "source-to-aaf" else "auroradb"
        options = build_source_load_options(args, include_details=True)
        options.aedb_parse_profile = resolve_aedb_parse_profile_for_target(
            args,
            source_format=args.source_format,
            target_format=target_format,
            semantic_output=getattr(args, "semantic_output", None),
        )
        result = convert_source_to_target(
            args.source_format,
            args.input,
            target_format,
            args.out,
            options=options,
            export_aaf=args.export_aaf
            if args.command == "source-to-auroradb"
            else False,
        )
    except (
        AEDBParserError,
        ALGParserError,
        AltiumParserError,
        ODBPPParserError,
        BRDParserError,
        OSError,
        ValidationError,
        ValueError,
    ) as exc:
        logger.exception("Semantic payload build failed")
        print(f"Failed to build semantic payload: {exc}")
        return 1

    semantic_output_path = _resolve_output_path(args.out, args.semantic_output)
    semantic_output = (
        write_json_file(result.board, semantic_output_path, indent=args.indent)
        if semantic_output_path
        else None
    )
    _print_export_summary(
        result.board,
        output_path=result.export.root,
        auroradb_path=result.export.auroradb,
        aaf_path=result.export.aaf,
        semantic_output=semantic_output,
        log_path=log_path,
    )
    log_run_complete(logger, "semantic")
    return 0


def _resolve_output_path(base_dir: str | None, output_path: str | None) -> str | None:
    if not output_path:
        return None
    candidate = Path(output_path).expanduser()
    if candidate.is_absolute() or not base_dir:
        return str(candidate)
    return str((Path(base_dir).expanduser() / candidate).resolve())


def _print_summary(
    summary: dict[str, int], *, output_path: Path | None, log_path: Path
) -> None:
    print(
        "Semantic board: "
        f"layers={summary['layer_count']}, "
        f"materials={summary.get('material_count', 0)}, "
        f"shapes={summary.get('shape_count', 0)}, "
        f"via_templates={summary.get('via_template_count', 0)}, "
        f"nets={summary['net_count']}, "
        f"components={summary['component_count']}, "
        f"footprints={summary['footprint_count']}, "
        f"pins={summary['pin_count']}, "
        f"pads={summary['pad_count']}, "
        f"vias={summary['via_count']}, "
        f"primitives={summary['primitive_count']}, "
        f"edges={summary['edge_count']}, "
        f"diagnostics={summary['diagnostic_count']}"
    )
    if output_path is not None:
        print(f"Semantic JSON written to: {output_path}")
    print(f"Log written to: {log_path}")


def _print_export_summary(
    payload: SemanticBoard,
    *,
    output_path: Path,
    auroradb_path: Path | None,
    aaf_path: Path | None = None,
    semantic_output: Path | None,
    log_path: Path,
) -> None:
    _print_summary(
        payload.summary.model_dump(), output_path=semantic_output, log_path=log_path
    )
    if auroradb_path is not None:
        print(f"AuroraDB files written to: {auroradb_path}")
        print(f"Stackup files written to: {output_path}")
    else:
        print(f"AAF package written to: {output_path}")
    if aaf_path is not None:
        print(f"AAF files written to: {aaf_path}")
