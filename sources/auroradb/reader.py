from __future__ import annotations

import logging
from pathlib import Path

from aurora_translator.shared.logging import log_kv, log_timing

from .block import AuroraBlockError, read_block_file
from .models import AuroraDBPackage


logger = logging.getLogger("aurora_translator.auroradb")


def read_auroradb(path: str | Path, *, strict: bool = False) -> AuroraDBPackage:
    root = Path(path).expanduser().resolve()
    log_kv(
        logger,
        "AuroraDB source reader settings",
        root=root,
        strict=strict,
    )
    package = AuroraDBPackage(root=root)

    layout_file = root / "layout.db"
    parts_file = root / "parts.db"

    if layout_file.exists():
        with log_timing(logger, "read AuroraDB layout block", source=layout_file):
            package.layout = read_block_file(layout_file, "CeLayout")
    elif strict:
        raise FileNotFoundError(f"layout.db was not found under {root}")
    else:
        package.diagnostics.append(f"layout.db was not found under {root}")

    if parts_file.exists():
        with log_timing(logger, "read AuroraDB parts block", source=parts_file):
            package.parts = read_block_file(parts_file, "CeParts")
    else:
        package.diagnostics.append(f"parts.db was not found under {root}")

    layer_names = _layer_names_from_layout(package)
    layer_folder = root / "layers"
    if layer_names:
        for layer_name in layer_names:
            layer_file = layer_folder / f"{layer_name}.lyr"
            if not layer_file.exists():
                message = f"Layer file is missing: {layer_file}"
                if strict:
                    raise FileNotFoundError(message)
                package.diagnostics.append(message)
                continue
            with log_timing(
                logger, "read AuroraDB metal layer block", source=layer_file
            ):
                package.layers[layer_name] = read_block_file(layer_file, "MetalLayer")
    elif layer_folder.exists():
        for layer_file in sorted(layer_folder.glob("*.lyr")):
            try:
                with log_timing(
                    logger, "read AuroraDB metal layer block", source=layer_file
                ):
                    layer = read_block_file(layer_file, "MetalLayer")
            except AuroraBlockError as exc:
                if strict:
                    raise
                package.diagnostics.append(str(exc))
                continue
            package.layers[layer_file.stem] = layer

    logger.info(
        "Read AuroraDB package with layout:%s parts:%s layers:%s diagnostics:%s",
        package.layout is not None,
        package.parts is not None,
        len(package.layers),
        len(package.diagnostics),
    )
    return package


def _layer_names_from_layout(package: AuroraDBPackage) -> list[str]:
    if package.layout is None:
        return []
    stack = package.layout.get_block("LayerStackup")
    if stack is None:
        return []
    item = stack.get_item("MetalLayers")
    return list(item.values) if item else []
