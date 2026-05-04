from __future__ import annotations

import json
from pathlib import Path

from .block import canonical_block_dict
from .reader import read_auroradb


def diff_auroradb(
    left: str | Path, right: str | Path, *, include_blocks: bool = False
) -> list[str]:
    left_package = read_auroradb(left)
    right_package = read_auroradb(right)
    differences: list[str] = []

    left_summary = left_package.summary().to_dict()
    right_summary = right_package.summary().to_dict()
    for key in sorted(left_summary):
        if left_summary[key] != right_summary.get(key):
            differences.append(
                f"summary.{key}: {left_summary[key]!r} != {right_summary.get(key)!r}"
            )

    if include_blocks:
        if _canonical(left_package.layout) != _canonical(right_package.layout):
            differences.append("layout.db block tree differs")
        if _canonical(left_package.parts) != _canonical(right_package.parts):
            differences.append("parts.db block tree differs")
        left_layers = set(left_package.layers)
        right_layers = set(right_package.layers)
        for layer in sorted(left_layers | right_layers):
            if layer not in left_layers:
                differences.append(f"layer {layer!r} missing on left")
            elif layer not in right_layers:
                differences.append(f"layer {layer!r} missing on right")
            elif _canonical(left_package.layers[layer]) != _canonical(
                right_package.layers[layer]
            ):
                differences.append(f"layer {layer!r} block tree differs")

    return differences


def _canonical(block: object) -> str:
    if block is None:
        return "null"
    return json.dumps(canonical_block_dict(block), sort_keys=True, ensure_ascii=False)
