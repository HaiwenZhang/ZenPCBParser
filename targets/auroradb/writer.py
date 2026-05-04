from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from aurora_translator.shared.logging import log_kv, log_timing
from aurora_translator.sources.auroradb.block import AuroraBlock
from aurora_translator.sources.auroradb.block import write_block_file
from aurora_translator.sources.auroradb.models import AuroraDBPackage


logger = logging.getLogger("aurora_translator.targets.auroradb")


def write_auroradb(package: AuroraDBPackage, path: str | Path) -> Path:
    out_dir = Path(path).expanduser().resolve()
    log_kv(
        logger,
        "AuroraDB target writer settings",
        level=logging.DEBUG,
        output=out_dir,
        has_layout=package.layout is not None,
        has_parts=package.parts is not None,
        layer_count=len(package.layers),
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    if package.layout is not None:
        with log_timing(
            logger,
            "write AuroraDB layout block",
            output=out_dir / "layout.db",
            level=logging.DEBUG,
        ):
            write_block_file(package.layout, out_dir / "layout.db")
    if package.parts is not None:
        with log_timing(
            logger,
            "write AuroraDB parts block",
            output=out_dir / "parts.db",
            level=logging.DEBUG,
        ):
            write_block_file(package.parts, out_dir / "parts.db")
    if package.layers:
        layer_dir = out_dir / "layers"
        layer_dir.mkdir(parents=True, exist_ok=True)
        _write_layer_blocks(package.layers, layer_dir)
    logger.info("AuroraDB files written to %s", out_dir)
    return out_dir


def _write_layer_blocks(layers: dict[str, AuroraBlock], layer_dir: Path) -> None:
    worker_count = _layer_writer_count(len(layers))
    if worker_count <= 1:
        for layer_name, layer_block in layers.items():
            _write_layer_block(layer_name, layer_block, layer_dir)
        return

    log_kv(
        logger,
        "AuroraDB layer writer parallelism",
        level=logging.DEBUG,
        layer_count=len(layers),
        worker_count=worker_count,
    )
    with ThreadPoolExecutor(
        max_workers=worker_count, thread_name_prefix="auroradb-layer-writer"
    ) as executor:
        futures = [
            executor.submit(_write_layer_block, layer_name, layer_block, layer_dir)
            for layer_name, layer_block in layers.items()
        ]
        for future in futures:
            future.result()


def _write_layer_block(
    layer_name: str, layer_block: AuroraBlock, layer_dir: Path
) -> None:
    with log_timing(
        logger,
        "write AuroraDB metal layer block",
        output=layer_dir / f"{layer_name}.lyr",
        level=logging.DEBUG,
    ):
        write_block_file(layer_block, layer_dir / f"{layer_name}.lyr")


def _layer_writer_count(layer_count: int) -> int:
    if layer_count <= 1:
        return 1
    cpu_count = os.cpu_count() or 1
    return min(layer_count, max(1, min(8, cpu_count)))
