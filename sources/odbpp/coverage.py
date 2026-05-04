from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from aurora_translator.sources.auroradb.reader import read_auroradb
from aurora_translator.sources.odbpp.models import ODBLayout
from aurora_translator.semantic.models import SemanticBoard


def build_odbpp_coverage_report(
    payload: ODBLayout,
    semantic_board: SemanticBoard | None = None,
    *,
    aaf_dir: str | Path | None = None,
    auroradb_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Build an object-level coverage report for ODB++ conversion."""

    feature_rows = _feature_rows(payload)
    feature_net_keys = _feature_net_keys(payload)
    source = _source_section(payload, feature_rows, feature_net_keys)
    semantic = _semantic_section(semantic_board) if semantic_board is not None else None
    aaf = _aaf_section(aaf_dir) if aaf_dir is not None else None
    auroradb = _auroradb_section(auroradb_dir) if auroradb_dir is not None else None
    gaps = _gap_section(
        payload, feature_rows, feature_net_keys, semantic_board, aaf, auroradb
    )
    return {
        "metadata": {
            "source": payload.metadata.source,
            "selected_step": payload.metadata.selected_step,
            "project_version": payload.metadata.project_version,
            "odbpp_parser_version": payload.metadata.parser_version,
            "odbpp_schema_version": payload.metadata.output_schema_version,
            "semantic_parser_version": semantic_board.metadata.parser_version
            if semantic_board
            else None,
            "semantic_schema_version": semantic_board.metadata.output_schema_version
            if semantic_board
            else None,
        },
        "source": source,
        "semantic": semantic,
        "aaf": aaf,
        "auroradb": auroradb,
        "gaps": gaps,
    }


def _feature_rows(payload: ODBLayout) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for layer in payload.layers or []:
        symbols = layer.symbols or {}
        for feature in layer.features:
            symbol_name = symbols.get(str(feature.symbol), feature.symbol)
            contour_polarities = [contour.polarity for contour in feature.contours]
            rows.append(
                {
                    "layer_name": layer.layer_name,
                    "layer_key": layer.layer_name.casefold(),
                    "feature_index": feature.feature_index,
                    "kind": feature.kind,
                    "symbol": symbol_name,
                    "has_symbol": bool(symbol_name),
                    "symbol_resolved": not feature.symbol
                    or str(feature.symbol) in symbols
                    or feature.symbol == symbol_name,
                    "is_profile": layer.layer_name.casefold() == "profile",
                    "is_drill": layer.layer_name.casefold().startswith("drill"),
                    "has_contour_arcs": any(
                        vertex.record_type.upper() == "OC"
                        for contour in feature.contours
                        for vertex in contour.vertices
                    ),
                    "contour_polarities": contour_polarities,
                    "is_multi_island_surface": _surface_island_count(contour_polarities)
                    > 1,
                    "hole_contour_count": _surface_hole_count(contour_polarities),
                }
            )
    return rows


def _surface_island_count(polarities: list[str | None]) -> int:
    return sum(
        1
        for polarity in polarities
        if str(polarity or "").strip().casefold() in {"i", "island"}
    )


def _surface_hole_count(polarities: list[str | None]) -> int:
    return sum(
        1
        for polarity in polarities
        if str(polarity or "").strip().casefold() in {"h", "hole"}
    )


def _feature_net_keys(payload: ODBLayout) -> set[tuple[str, int]]:
    keys: set[tuple[str, int]] = set()
    for net in payload.nets or []:
        for ref in net.feature_refs:
            if ref.layer_name and ref.feature_index is not None:
                keys.add((ref.layer_name.casefold(), ref.feature_index))
    return keys


def _source_section(
    payload: ODBLayout,
    feature_rows: list[dict[str, Any]],
    feature_net_keys: set[tuple[str, int]],
) -> dict[str, Any]:
    by_kind = Counter(row["kind"] for row in feature_rows)
    by_layer = Counter(row["layer_name"] for row in feature_rows)
    net_by_kind = Counter(
        row["kind"]
        for row in feature_rows
        if (row["layer_key"], row["feature_index"]) in feature_net_keys
    )
    no_net_by_kind = Counter(
        row["kind"]
        for row in feature_rows
        if (row["layer_key"], row["feature_index"]) not in feature_net_keys
    )
    unresolved_symbols = [
        {
            "layer_name": row["layer_name"],
            "feature_index": row["feature_index"],
            "kind": row["kind"],
            "symbol": row["symbol"],
        }
        for row in feature_rows
        if row["has_symbol"] and not row["symbol_resolved"]
    ][:100]
    return {
        "summary": payload.summary.model_dump(mode="json"),
        "feature_count_by_kind": dict(sorted(by_kind.items())),
        "feature_count_by_layer": dict(sorted(by_layer.items())),
        "net_bound_feature_count_by_kind": dict(sorted(net_by_kind.items())),
        "no_net_feature_count_by_kind": dict(sorted(no_net_by_kind.items())),
        "profile_feature_count": sum(1 for row in feature_rows if row["is_profile"]),
        "profile_arc_feature_count": sum(
            1 for row in feature_rows if row["is_profile"] and row["kind"] == "A"
        ),
        "drill_feature_count": sum(1 for row in feature_rows if row["is_drill"]),
        "surface_with_contour_arc_count": sum(
            1 for row in feature_rows if row["has_contour_arcs"]
        ),
        "surface_multi_island_feature_count": sum(
            1 for row in feature_rows if row["is_multi_island_surface"]
        ),
        "surface_hole_contour_count": sum(
            row["hole_contour_count"] for row in feature_rows
        ),
        "unresolved_symbol_count": len(unresolved_symbols),
        "unresolved_symbol_examples": unresolved_symbols,
    }


def _semantic_section(board: SemanticBoard) -> dict[str, Any]:
    primitive_counts = Counter(primitive.kind for primitive in board.primitives)
    polygon_primitives_with_arcs = sum(
        1
        for primitive in board.primitives
        if primitive.kind in {"polygon", "zone"} and primitive.geometry.get("arcs")
    )
    polygons_with_void_arcs = sum(
        1
        for primitive in board.primitives
        if any(void.get("arcs") for void in primitive.geometry.get("voids") or [])
    )
    voids_with_arcs = sum(
        1
        for primitive in board.primitives
        for void in primitive.geometry.get("voids") or []
        if void.get("arcs")
    )
    footprints_with_body = sum(
        1 for footprint in board.footprints if footprint.geometry.get("outlines")
    )
    via_templates_with_tool = sum(
        1 for template in board.via_templates if template.geometry.get("tool")
    )
    via_templates_with_antipads = sum(
        1
        for template in board.via_templates
        if any(layer_pad.antipad_shape_id for layer_pad in template.layer_pads)
    )
    via_template_antipad_layer_count = sum(
        1
        for template in board.via_templates
        for layer_pad in template.layer_pads
        if layer_pad.antipad_shape_id
    )
    drawing_primitives = [
        primitive
        for primitive in board.primitives
        if not primitive.net_id
        and primitive.kind in {"trace", "arc", "polygon", "zone", "pad"}
    ]
    return {
        "summary": board.summary.model_dump(mode="json"),
        "primitive_count_by_kind": dict(sorted(primitive_counts.items())),
        "board_outline": {
            "present": bool(board.board_outline),
            "source": board.board_outline.get("source")
            if board.board_outline
            else None,
            "path_count": board.board_outline.get("path_count")
            if board.board_outline
            else None,
        },
        "polygon_primitives_with_arcs": polygon_primitives_with_arcs,
        "polygons_with_void_arcs": polygons_with_void_arcs,
        "voids_with_arcs": voids_with_arcs,
        "polygon_void_count": sum(
            len(primitive.geometry.get("voids") or [])
            for primitive in board.primitives
            if primitive.kind in {"polygon", "zone"}
        ),
        "split_surface_polygon_count": sum(
            1
            for primitive in board.primitives
            if primitive.kind in {"polygon", "zone"}
            and int(primitive.geometry.get("surface_group_count") or 0) > 1
        ),
        "arc_primitives": primitive_counts.get("arc", 0),
        "net_arc_primitives": sum(
            1
            for primitive in board.primitives
            if primitive.kind == "arc" and primitive.net_id
        ),
        "pads_with_shape": sum(1 for pad in board.pads if pad.geometry.get("shape_id")),
        "vias_with_template": sum(1 for via in board.vias if via.template_id),
        "via_templates_with_tool": via_templates_with_tool,
        "via_templates_with_antipads": via_templates_with_antipads,
        "via_template_antipad_layer_count": via_template_antipad_layer_count,
        "via_templates_with_matched_layer_pads": sum(
            1
            for via_template in board.via_templates
            if via_template.geometry.get("layer_pad_source")
            == "matched_signal_layer_pads"
        ),
        "layers_with_material": sum(1 for layer in board.layers if layer.material_id),
        "layers_with_thickness": sum(
            1 for layer in board.layers if layer.thickness not in {None, ""}
        ),
        "components_with_attributes": sum(
            1 for component in board.components if component.attributes
        ),
        "footprints_with_attributes": sum(
            1 for footprint in board.footprints if footprint.attributes
        ),
        "drawing_primitive_count": len(drawing_primitives),
        "drawing_primitive_count_by_kind": dict(
            sorted(Counter(primitive.kind for primitive in drawing_primitives).items())
        ),
        "footprints_with_body_geometry": footprints_with_body,
    }


def _aaf_section(aaf_dir: str | Path) -> dict[str, Any]:
    root = Path(aaf_dir).expanduser()
    layout_path = _resolve_aaf_file(root, "design.layout")
    part_path = _resolve_aaf_file(root, "design.part")
    layout_text = _read_text(layout_path)
    part_text = _read_text(part_path)
    return {
        "path": str(root.resolve()),
        "design_layout": {
            "path": str(layout_path.resolve())
            if layout_path.exists()
            else str(layout_path),
            "exists": bool(layout_text),
            "line_count": _line_count(layout_text),
            "line_geometry_count": layout_text.count(":Line"),
            "larc_geometry_count": layout_text.count(":Larc"),
            "polygon_geometry_count": layout_text.count(":Polygon"),
            "polygon_arc_vertex_count": len(_POLYGON_ARC_RE.findall(layout_text)),
            "profile_uses_polygon_arc": _profile_uses_polygon_arc(layout_text),
            "logic_geometry_count": len(
                re.findall(r"^layout add .*?-logic <", layout_text, flags=re.MULTILINE)
            ),
            "via_placement_count": len(
                re.findall(r"layout add .* -via <", layout_text)
            ),
            "component_placement_count": len(
                re.findall(
                    r"^layout add -component <[^>]+> -part <",
                    layout_text,
                    flags=re.MULTILINE,
                )
            ),
        },
        "design_part": {
            "path": str(part_path.resolve()) if part_path.exists() else str(part_path),
            "exists": bool(part_text),
            "line_count": _line_count(part_text),
            "footprint_count": len(
                re.findall(r"^library add -footprint ", part_text, flags=re.MULTILINE)
            ),
            "footprint_pad_count": len(
                re.findall(r"^library add -fpn ", part_text, flags=re.MULTILINE)
            ),
            "footprint_body_geometry_count": len(
                re.findall(
                    r"^library add -g <.* -layer <[^>]+> -footprint <",
                    part_text,
                    flags=re.MULTILINE,
                )
            ),
        },
    }


def _resolve_aaf_file(root: Path, filename: str) -> Path:
    direct = root / filename
    if direct.exists():
        return direct
    nested = root / "aaf" / filename
    if nested.exists():
        return nested
    return nested


def _auroradb_section(auroradb_dir: str | Path) -> dict[str, Any]:
    root = Path(auroradb_dir).expanduser()
    if not root.exists():
        return {"path": str(root), "exists": False}
    package = read_auroradb(root)
    geometry_counts: Counter[str] = Counter()
    layer_dir = root / "layers"
    if layer_dir.exists():
        for layer_file in layer_dir.glob("*.lyr"):
            text = _read_text(layer_file)
            for kind in ("Line", "Larc", "Pnt", "Parc", "PolygonHole"):
                geometry_counts[kind] += len(re.findall(rf"\b{kind}\b", text))
    return {
        "path": str(root.resolve()),
        "exists": True,
        "summary": package.summary().to_dict(),
        "layer_geometry_item_counts": dict(sorted(geometry_counts.items())),
        "diagnostics": list(package.diagnostics),
    }


def _gap_section(
    payload: ODBLayout,
    feature_rows: list[dict[str, Any]],
    feature_net_keys: set[tuple[str, int]],
    board: SemanticBoard | None,
    aaf: dict[str, Any] | None,
    auroradb: dict[str, Any] | None,
) -> dict[str, Any]:
    no_net_arcs = [
        row
        for row in feature_rows
        if row["kind"] == "A"
        and (row["layer_key"], row["feature_index"]) not in feature_net_keys
    ]
    text_count = sum(1 for row in feature_rows if row["kind"] == "T")
    boundary_count = sum(1 for row in feature_rows if row["kind"] == "B")
    source_packages = len(payload.packages or [])
    package_outlines = sum(1 for package in payload.packages or [] if package.outlines)
    semantic_footprint_bodies = (
        sum(1 for footprint in board.footprints if footprint.geometry.get("outlines"))
        if board is not None
        else None
    )
    semantic_drawing_primitives = (
        sum(
            1
            for primitive in board.primitives
            if not primitive.net_id
            and primitive.kind in {"trace", "arc", "polygon", "zone", "pad"}
        )
        if board is not None
        else None
    )
    aaf_body_count = None
    aaf_logic_geometry_count = None
    if aaf is not None:
        aaf_body_count = aaf["design_part"]["footprint_body_geometry_count"]
        aaf_logic_geometry_count = aaf["design_layout"]["logic_geometry_count"]
    auroradb_parc = None
    if auroradb and auroradb.get("exists"):
        auroradb_parc = auroradb.get("layer_geometry_item_counts", {}).get("Parc", 0)
    notes: list[str] = []
    if text_count or boundary_count:
        notes.append(
            "Text and boundary features are counted; geometry export is limited to known drawable primitives."
        )
    if no_net_arcs:
        notes.append(
            "Standalone ODB++ A arcs without a routable layer or positive round-symbol width may remain coverage-only."
        )
    if (
        semantic_footprint_bodies is not None
        and semantic_footprint_bodies < package_outlines
    ):
        notes.append(
            "Some source packages with outlines did not produce semantic footprint body geometry."
        )
    if semantic_drawing_primitives:
        notes.append(
            "Remaining no-net drawing primitives are non-routable or unsupported; routable positive trace/arc/polygon primitives are promoted to AuroraDB NoNet."
        )
    notes.append(
        "ODB++ drill tools are preserved on semantic via template geometry when they can be matched to drill symbols."
    )
    return {
        "standalone_arc_without_net_count": len(no_net_arcs),
        "standalone_arc_without_net_examples": [
            {
                "layer_name": row["layer_name"],
                "feature_index": row["feature_index"],
                "symbol": row["symbol"],
            }
            for row in no_net_arcs[:25]
        ],
        "text_feature_count": text_count,
        "boundary_feature_count": boundary_count,
        "package_count": source_packages,
        "packages_with_outline_count": package_outlines,
        "footprints_with_body_geometry": semantic_footprint_bodies,
        "aaf_footprint_body_geometry_count": aaf_body_count,
        "semantic_drawing_primitive_count": semantic_drawing_primitives,
        "aaf_logic_geometry_count": aaf_logic_geometry_count,
        "auroradb_parc_count": auroradb_parc,
        "notes": notes,
    }


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _line_count(text: str) -> int:
    return len(text.splitlines()) if text else 0


def _profile_uses_polygon_arc(layout_text: str) -> bool:
    for line in layout_text.splitlines():
        if " -profile " in line:
            return bool(_POLYGON_ARC_RE.search(line))
    return False


_POLYGON_ARC_RE = re.compile(r"\([^,()]+,[^,()]+,[^,()]+,[^,()]+,[YN]\)")
