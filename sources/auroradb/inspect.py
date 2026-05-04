from __future__ import annotations

import json
from pathlib import Path

from .models import AuroraDBMetadata, AuroraDBPackage
from .reader import read_auroradb


def inspect_auroradb(path: str | Path) -> dict[str, object]:
    return read_auroradb(path).to_dict(include_blocks=False)


def export_auroradb_json(
    path: str | Path,
    output: str | Path,
    *,
    indent: int = 2,
    include_raw_blocks: bool = False,
) -> Path:
    package = read_auroradb(path)
    output_path = Path(output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            package.to_model_dict(include_raw_blocks=include_raw_blocks),
            ensure_ascii=False,
            indent=indent,
        ),
        encoding="utf-8",
    )
    return output_path


def format_summary(package: AuroraDBPackage) -> str:
    summary = package.summary()
    metadata = AuroraDBMetadata()
    lines = [
        f"AuroraDB: {package.root}" if package.root else "AuroraDB: <in-memory>",
        (
            "Versions: "
            f"project={metadata.project_version}, "
            f"parser={metadata.parser_version}, "
            f"schema={metadata.output_schema_version}"
        ),
        (
            "Counts: "
            f"layers={summary.metal_layer_count}, "
            f"nets={summary.net_count}, "
            f"components={summary.component_count}, "
            f"parts={summary.part_count}, "
            f"shapes={summary.shape_count}, "
            f"vias={summary.via_template_count}, "
            f"net_geometries={summary.net_geometry_count}"
        ),
    ]
    if summary.units:
        lines.append(f"Units: {summary.units}")
    if summary.layer_names:
        lines.append(
            "Layers: "
            + ", ".join(summary.layer_names[:20])
            + (" ..." if len(summary.layer_names) > 20 else "")
        )
    if package.diagnostics:
        lines.append("Diagnostics:")
        lines.extend(f"  - {message}" for message in package.diagnostics[:50])
        if len(package.diagnostics) > 50:
            lines.append(f"  - ... {len(package.diagnostics) - 50} more")
    return "\n".join(lines)
