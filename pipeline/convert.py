from __future__ import annotations

import logging
from pathlib import Path

from aurora_translator.semantic.converter import to_semantic_board
from aurora_translator.targets.auroradb import (
    SemanticAuroraExport,
    write_aaf_from_semantic,
    write_aurora_conversion_package,
)
from aurora_translator.shared.logging import log_kv, log_timing

from .loaders import load_source_payload
from .result import SourceToSemanticResult, SourceToTargetResult
from .types import SourceFormat, SourceLoadOptions, TargetFormat


logger = logging.getLogger("aurora_translator.pipeline")


def semantic_from_source(
    source_format: SourceFormat,
    source_path: str | Path,
    *,
    options: SourceLoadOptions | None = None,
) -> SourceToSemanticResult:
    resolved_source = Path(source_path).expanduser().resolve()
    payload = load_source_payload(source_format, resolved_source, options=options)
    with log_timing(
        logger,
        "build semantic board",
        banner=True,
        source_format=source_format,
        source=resolved_source,
    ):
        board = to_semantic_board(
            payload,
            build_connectivity=True
            if options is None
            else options.build_semantic_connectivity,
        )
    return SourceToSemanticResult(
        source_format=source_format,
        source_path=resolved_source,
        payload=payload,
        board=board,
    )


def convert_semantic_to_target(
    board,
    target_format: TargetFormat,
    output_path: str | Path,
    *,
    compile_auroradb: bool | None = None,
    export_aaf: bool = False,
) -> SemanticAuroraExport:
    resolved_output = Path(output_path).expanduser().resolve()
    log_kv(
        logger,
        "Target exporter settings",
        target_format=target_format,
        output=resolved_output,
        compile_auroradb=compile_auroradb,
        export_aaf=export_aaf if target_format == "auroradb" else None,
    )

    if target_format == "aaf":
        with log_timing(
            logger,
            "export semantic board to Aurora AAF",
            banner=True,
            output=resolved_output,
        ):
            root = write_aaf_from_semantic(board, resolved_output)
        return SemanticAuroraExport(
            root=root,
            aaf=root / "aaf",
            layout=root / "aaf" / "design.layout",
            part=root / "aaf" / "design.part",
            stackup_dat=root / "stackup.dat",
            stackup_json=root / "stackup.json",
            auroradb=None,
        )

    if target_format == "auroradb":
        with log_timing(
            logger,
            "export semantic board to AuroraDB",
            banner=True,
            output=resolved_output,
            compile_auroradb=compile_auroradb if compile_auroradb is not None else True,
        ):
            return write_aurora_conversion_package(
                board,
                resolved_output,
                compile_auroradb=True if compile_auroradb is None else compile_auroradb,
                export_aaf=export_aaf,
            )

    raise ValueError(f"Unsupported target format: {target_format!r}")


def convert_source_to_target(
    source_format: SourceFormat,
    source_path: str | Path,
    target_format: TargetFormat,
    output_path: str | Path,
    *,
    options: SourceLoadOptions | None = None,
    compile_auroradb: bool | None = None,
    export_aaf: bool = False,
) -> SourceToTargetResult:
    semantic_result = semantic_from_source(source_format, source_path, options=options)
    export = convert_semantic_to_target(
        semantic_result.board,
        target_format,
        output_path,
        compile_auroradb=compile_auroradb,
        export_aaf=export_aaf,
    )
    return SourceToTargetResult(
        source_format=semantic_result.source_format,
        target_format=target_format,
        source_path=semantic_result.source_path,
        payload=semantic_result.payload,
        board=semantic_result.board,
        export=export,
    )
