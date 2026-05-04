from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Sequence

from aurora_translator.shared.logging import log_run_complete
from aurora_translator.sources.auroradb.diff import diff_auroradb
from aurora_translator.sources.auroradb.inspect import (
    export_auroradb_json,
    format_summary,
)
from aurora_translator.sources.auroradb.reader import read_auroradb
from aurora_translator.sources.auroradb.schema import auroradb_json_schema
from aurora_translator.targets.auroradb.aaf.parser import parse_command_file
from aurora_translator.targets.auroradb.aaf.translator import translate_aaf_to_auroradb

from .common import start_cli_logging


logger = logging.getLogger("aurora_translator.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AuroraDB reader/writer and ASIV AAF command translator."
    )
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
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect", help="Read an AuroraDB directory and print a summary."
    )
    inspect_parser.add_argument("db_dir")
    inspect_parser.add_argument(
        "--json", action="store_true", help="Print the summary payload as JSON."
    )
    inspect_parser.add_argument(
        "--log-file",
        help="Write logs to this file. Default: logs/aurora_translator.log",
    )
    inspect_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level. Default: INFO.",
    )

    export_parser = subparsers.add_parser(
        "export-json", help="Export an AuroraDB directory to JSON."
    )
    export_parser.add_argument("db_dir")
    export_parser.add_argument("-o", "--output", required=True)
    export_parser.add_argument("--indent", type=int, default=2)
    export_parser.add_argument(
        "--include-raw-blocks",
        action="store_true",
        help="Also include the original AuroraDB block trees under raw_blocks.",
    )
    export_parser.add_argument(
        "--log-file",
        help="Write logs to this file. Default: logs/aurora_translator.log",
    )
    export_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level. Default: INFO.",
    )

    schema_parser = subparsers.add_parser(
        "schema", help="Print or write the AuroraDB JSON schema."
    )
    schema_parser.add_argument(
        "-o", "--output", help="Write the schema to a file instead of stdout."
    )
    schema_parser.add_argument("--indent", type=int, default=2)
    schema_parser.add_argument(
        "--log-file",
        help="Write logs to this file. Default: logs/aurora_translator.log",
    )
    schema_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level. Default: INFO.",
    )

    diff_parser = subparsers.add_parser(
        "diff", help="Compare two AuroraDB directories."
    )
    diff_parser.add_argument("left")
    diff_parser.add_argument("right")
    diff_parser.add_argument(
        "--include-blocks", action="store_true", help="Also compare full block trees."
    )
    diff_parser.add_argument(
        "--log-file",
        help="Write logs to this file. Default: logs/aurora_translator.log",
    )
    diff_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level. Default: INFO.",
    )

    parse_aaf_parser = subparsers.add_parser(
        "parse-aaf", help="Parse ASIV AAF command files."
    )
    parse_aaf_parser.add_argument("--layout", help="Path to design.layout.")
    parse_aaf_parser.add_argument("--part", help="Path to design.part.")
    parse_aaf_parser.add_argument("--indent", type=int, default=2)
    parse_aaf_parser.add_argument(
        "--log-file",
        help="Write logs to this file. Default: logs/aurora_translator.log",
    )
    parse_aaf_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level. Default: INFO.",
    )

    from_aaf_parser = subparsers.add_parser(
        "from-aaf", help="Compile ASIV AAF command files into AuroraDB."
    )
    from_aaf_parser.add_argument("--layout", help="Path to design.layout.")
    from_aaf_parser.add_argument("--part", help="Path to design.part.")
    from_aaf_parser.add_argument(
        "-o", "--out", required=True, help="Output AuroraDB directory."
    )
    from_aaf_parser.add_argument("--fail-on-unsupported", action="store_true")
    from_aaf_parser.add_argument(
        "--log-file",
        help="Write logs to this file. Default: logs/aurora_translator.log",
    )
    from_aaf_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level. Default: INFO.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    log_path = start_cli_logging(
        args,
        logger,
        "auroradb",
        command=args.command,
        db_dir=Path(args.db_dir).expanduser().resolve()
        if getattr(args, "db_dir", None)
        else None,
        output=Path(getattr(args, "output", None)).expanduser().resolve()
        if getattr(args, "output", None)
        else (
            Path(getattr(args, "out", None)).expanduser().resolve()
            if getattr(args, "out", None)
            else None
        ),
        left=Path(args.left).expanduser().resolve()
        if getattr(args, "left", None)
        else None,
        right=Path(args.right).expanduser().resolve()
        if getattr(args, "right", None)
        else None,
        layout=Path(args.layout).expanduser().resolve()
        if getattr(args, "layout", None)
        else None,
        part=Path(args.part).expanduser().resolve()
        if getattr(args, "part", None)
        else None,
    )

    if args.command == "inspect":
        package = read_auroradb(args.db_dir)
        if args.json:
            print(
                json.dumps(
                    package.to_dict(include_blocks=False), ensure_ascii=False, indent=2
                )
            )
        else:
            print(format_summary(package))
        print(f"Log written to: {log_path}")
        log_run_complete(logger, "auroradb")
        return 0

    if args.command == "export-json":
        output = export_auroradb_json(
            args.db_dir,
            args.output,
            indent=args.indent,
            include_raw_blocks=args.include_raw_blocks,
        )
        print(f"JSON written to: {output}")
        print(f"Log written to: {log_path}")
        log_run_complete(logger, "auroradb")
        return 0

    if args.command == "schema":
        schema_text = json.dumps(
            auroradb_json_schema(), ensure_ascii=False, indent=args.indent
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(schema_text, encoding="utf-8")
            print(f"Schema written to: {output}")
        else:
            print(schema_text)
        print(f"Log written to: {log_path}")
        log_run_complete(logger, "auroradb")
        return 0

    if args.command == "diff":
        differences = diff_auroradb(
            args.left, args.right, include_blocks=args.include_blocks
        )
        if not differences:
            print("No AuroraDB differences found.")
            print(f"Log written to: {log_path}")
            log_run_complete(logger, "auroradb")
            return 0
        print("AuroraDB differences:")
        for difference in differences:
            print(f"  - {difference}")
        print(f"Log written to: {log_path}")
        log_run_complete(logger, "auroradb")
        return 1

    if args.command == "parse-aaf":
        if not args.layout and not args.part:
            parser.error("parse-aaf requires --layout and/or --part.")
        payload: dict[str, object] = {}
        if args.part:
            payload["part"] = parse_command_file(args.part).summary()
        if args.layout:
            payload["layout"] = parse_command_file(args.layout).summary()
        print(json.dumps(payload, ensure_ascii=False, indent=args.indent))
        print(f"Log written to: {log_path}")
        log_run_complete(logger, "auroradb")
        return 0

    if not args.layout and not args.part:
        parser.error("from-aaf requires --layout and/or --part.")
    result = translate_aaf_to_auroradb(
        layout=args.layout, part=args.part, output=args.out
    )
    print(f"AuroraDB written to: {Path(args.out).expanduser().resolve()}")
    print(
        f"Commands: supported={result.supported_commands}, unsupported={result.unsupported_commands}"
    )
    print(format_summary(result.package))
    print(f"Log written to: {log_path}")
    log_run_complete(logger, "auroradb")
    return 1 if args.fail_on_unsupported and result.unsupported_commands else 0
