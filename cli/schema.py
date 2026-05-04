from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Sequence

from aurora_translator.semantic.schema import semantic_json_schema
from aurora_translator.shared.logging import log_run_complete
from aurora_translator.sources.aedb.models import AEDBLayout
from aurora_translator.sources.alg.schema import alg_json_schema
from aurora_translator.sources.auroradb.schema import auroradb_json_schema
from aurora_translator.sources.brd.schema import brd_json_schema
from aurora_translator.sources.odbpp.schema import odbpp_json_schema

from .common import add_logging_arguments, start_cli_logging


logger = logging.getLogger("aurora_translator.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write machine-readable JSON schemas for project formats."
    )
    parser.add_argument(
        "--format",
        choices=["aedb", "auroradb", "odbpp", "brd", "alg", "semantic"],
        required=True,
    )
    parser.add_argument(
        "-o", "--output", help="Write the schema to a file instead of stdout."
    )
    parser.add_argument("--indent", type=int, default=2)
    add_logging_arguments(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    log_path = start_cli_logging(
        args,
        logger,
        "schema",
        format=args.format,
        output=Path(args.output).expanduser().resolve() if args.output else None,
    )

    if args.format == "aedb":
        schema = AEDBLayout.model_json_schema()
    elif args.format == "auroradb":
        schema = auroradb_json_schema()
    elif args.format == "odbpp":
        schema = odbpp_json_schema()
    elif args.format == "brd":
        schema = brd_json_schema()
    elif args.format == "alg":
        schema = alg_json_schema()
    else:
        schema = semantic_json_schema()

    schema_text = json.dumps(schema, ensure_ascii=False, indent=args.indent)
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(schema_text, encoding="utf-8")
        print(f"Schema written to: {output}")
    else:
        print(schema_text)
    print(f"Log written to: {log_path}")
    log_run_complete(logger, "schema")
    return 0
