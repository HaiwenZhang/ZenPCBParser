from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from aurora_translator.shared.logging import log_kv, log_timing
from aurora_translator.sources.auroradb.models import AuroraDBPackage
from aurora_translator.targets.auroradb.aaf.translator import (
    translate_aaf_to_auroradb,
    translate_exported_aaf_lines_stream_to_auroradb,
)
from aurora_translator.targets.auroradb.layout import (
    _build_direct_layout_package,
    _design_layout_lines,
)
from aurora_translator.targets.auroradb.parts import (
    _aedb_export_plan,
    _build_direct_parts_block,
    _design_part_lines,
    _part_export_plan,
)
from aurora_translator.targets.auroradb.stackup import (
    _export_layers,
    _stackup_dat,
    _stackup_json,
    _with_generated_dielectrics,
)
from aurora_translator.targets.auroradb.writer import write_auroradb
from aurora_translator.semantic.models import (
    SemanticBoard,
)

AAF_DIRNAME = "aaf"


logger = logging.getLogger("aurora_translator.targets.auroradb")


@dataclass(slots=True)
class SemanticAuroraExport:
    root: Path
    aaf: Path | None
    layout: Path | None
    part: Path | None
    stackup_dat: Path
    stackup_json: Path
    auroradb: Path | None = None


def write_aaf_from_semantic(board: SemanticBoard, path: str | Path) -> Path:
    """Write an Aurora/AAF conversion package from a semantic board."""

    out_dir = Path(path).expanduser().resolve()
    log_kv(
        logger,
        "Aurora target export settings",
        output=out_dir,
        source_format=board.metadata.source_format,
        unit=board.units,
        layers=board.summary.layer_count,
        nets=board.summary.net_count,
        components=board.summary.component_count,
        primitives=board.summary.primitive_count,
    )
    with log_timing(logger, "write Aurora AAF package", banner=True, output=out_dir):
        _cleanup_output_root(out_dir, keep_aaf=True)
        _write_aurora_intermediate_files(
            board,
            stackup_root=out_dir,
            aaf_root=out_dir / AAF_DIRNAME,
        )
    logger.info("Wrote Aurora AAF package to %s", out_dir)
    return out_dir


def write_aurora_conversion_package(
    board: SemanticBoard,
    path: str | Path,
    *,
    compile_auroradb: bool = True,
    export_aaf: bool = False,
) -> SemanticAuroraExport:
    """Write stackup files and optionally compile them into AuroraDB files."""

    root = Path(path).expanduser().resolve()
    keep_aaf = export_aaf or not compile_auroradb
    log_kv(
        logger,
        "Aurora target export settings",
        output=root,
        source_format=board.metadata.source_format,
        unit=board.units,
        layers=board.summary.layer_count,
        nets=board.summary.net_count,
        components=board.summary.component_count,
        primitives=board.summary.primitive_count,
        compile_auroradb=compile_auroradb,
        export_aaf=keep_aaf,
    )
    root.mkdir(parents=True, exist_ok=True)
    _cleanup_output_root(root, keep_aaf=keep_aaf)

    auroradb_dir: Path | None = root if compile_auroradb else None
    aaf_dir: Path | None = root / AAF_DIRNAME if keep_aaf else None
    layout_path: Path | None = None
    part_path: Path | None = None

    if keep_aaf:
        with log_timing(
            logger,
            "prepare Aurora export intermediates",
            output=root,
            level=logging.INFO if export_aaf or not compile_auroradb else logging.DEBUG,
        ):
            layout_path, part_path = _write_aurora_intermediate_files(
                board,
                stackup_root=root,
                aaf_root=root / AAF_DIRNAME,
            )
        if compile_auroradb:
            with log_timing(logger, "write AuroraDB output", banner=True, output=root):
                translate_aaf_to_auroradb(
                    layout=layout_path,
                    part=part_path,
                    output=root,
                )
    else:
        if board.metadata.source_format == "aedb":
            with log_timing(
                logger,
                "prepare AuroraDB package directly",
                output=root,
                level=logging.DEBUG,
            ):
                package = _write_stackup_and_build_auroradb_package(
                    board, stackup_root=root
                )
            with log_timing(logger, "write AuroraDB output", banner=True, output=root):
                write_auroradb(package, root)
        else:
            with log_timing(
                logger,
                "prepare Aurora export intermediates",
                output=root,
                level=logging.DEBUG,
            ):
                layout_lines, part_lines = _write_stackup_and_build_aaf_lines(
                    board, stackup_root=root
                )
            with log_timing(logger, "write AuroraDB output", banner=True, output=root):
                translate_exported_aaf_lines_stream_to_auroradb(
                    layout_lines=layout_lines,
                    part_lines=part_lines,
                    output=root,
                )

    if not keep_aaf:
        layout_path = None
        part_path = None

    return SemanticAuroraExport(
        root=root,
        aaf=aaf_dir,
        layout=layout_path,
        part=part_path,
        stackup_dat=root / "stackup.dat",
        stackup_json=root / "stackup.json",
        auroradb=auroradb_dir,
    )


def write_auroradb_from_semantic(board: SemanticBoard, path: str | Path) -> Path:
    """Write compiled AuroraDB files directly to the output directory."""

    return write_aurora_conversion_package(board, path, compile_auroradb=True).root


def _write_aurora_intermediate_files(
    board: SemanticBoard,
    *,
    stackup_root: Path,
    aaf_root: Path,
) -> tuple[Path, Path]:
    aaf_root.mkdir(parents=True, exist_ok=True)
    layout_text, part_text = _write_stackup_and_build_aaf_texts(
        board, stackup_root=stackup_root
    )

    layout_path = aaf_root / "design.layout"
    part_path = aaf_root / "design.part"
    layout_path.write_text(layout_text, encoding="utf-8", newline="\n")
    part_path.write_text(part_text, encoding="utf-8", newline="\n")
    return layout_path, part_path


def _write_stackup_and_build_aaf_texts(
    board: SemanticBoard, *, stackup_root: Path
) -> tuple[str, str]:
    layout_lines, part_lines = _write_stackup_and_build_aaf_lines(
        board, stackup_root=stackup_root
    )
    return _aaf_text(layout_lines), _aaf_text(part_lines)


def _write_stackup_and_build_aaf_lines(
    board: SemanticBoard, *, stackup_root: Path
) -> tuple[list[str], list[str]]:
    stackup_root.mkdir(parents=True, exist_ok=True)

    stackup_layers = _with_generated_dielectrics(_export_layers(board))
    metal_layers = [
        layer
        for layer in stackup_layers
        if layer.kind == "Metal" and not layer.generated
    ]
    aedb_plan = _aedb_export_plan(board)
    part_export_plan = None if aedb_plan is not None else _part_export_plan(board)

    (stackup_root / "stackup.dat").write_text(
        _stackup_dat(stackup_layers, design_name=_stackup_design_name(board)),
        encoding="utf-8",
        newline="\n",
    )
    (stackup_root / "stackup.json").write_text(
        json.dumps(_stackup_json(stackup_layers), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    layout_lines = _design_layout_lines(
        board, metal_layers, aedb_plan, part_export_plan
    )
    part_lines = _design_part_lines(board, aedb_plan, part_export_plan)
    return layout_lines, part_lines


def _write_stackup_and_build_auroradb_package(
    board: SemanticBoard, *, stackup_root: Path
) -> AuroraDBPackage:
    stackup_root.mkdir(parents=True, exist_ok=True)

    stackup_layers = _with_generated_dielectrics(_export_layers(board))
    metal_layers = [
        layer
        for layer in stackup_layers
        if layer.kind == "Metal" and not layer.generated
    ]
    aedb_plan = _aedb_export_plan(board)
    part_export_plan = None if aedb_plan is not None else _part_export_plan(board)

    (stackup_root / "stackup.dat").write_text(
        _stackup_dat(stackup_layers, design_name=_stackup_design_name(board)),
        encoding="utf-8",
        newline="\n",
    )
    (stackup_root / "stackup.json").write_text(
        json.dumps(_stackup_json(stackup_layers), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    builder = _build_direct_layout_package(
        board, metal_layers, aedb_plan, part_export_plan
    )
    parts = _build_direct_parts_block(board, aedb_plan, part_export_plan)
    return builder.package(parts=parts, root=stackup_root.resolve())


def _aaf_text(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def _cleanup_output_root(root: Path, *, keep_aaf: bool) -> None:
    for stale_path in [
        root / "design.layout",
        root / "design.part",
        root / "layout.db",
        root / "parts.db",
    ]:
        if stale_path.exists():
            stale_path.unlink()
    stale_layers_dir = root / "layers"
    if stale_layers_dir.exists():
        shutil.rmtree(stale_layers_dir)
    stale_aaf_dir = root / AAF_DIRNAME
    if stale_aaf_dir.exists() and not keep_aaf:
        shutil.rmtree(stale_aaf_dir)


def _stackup_design_name(board: SemanticBoard) -> str | None:
    if not board.metadata.source:
        return None
    return Path(board.metadata.source).name
