from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from aurora_translator.sources.auroradb.block import (
    AuroraBlock,
    AuroraItem,
    split_reserved,
    strip_wrapping_pair,
)


@dataclass(slots=True)
class GeometryParseResult:
    geometry_id: str | None
    geometry_type: str
    node: AuroraBlock | AuroraItem
    diagnostics: list[str]


def parse_geometry_option(
    raw_values: list[str],
    *,
    container: dict[str, AuroraBlock | AuroraItem] | None = None,
    copy_container_nodes: bool = True,
) -> GeometryParseResult | None:
    if not raw_values:
        return None
    raw = " ".join(raw_values).strip()
    raw = strip_wrapping_pair(raw, "{", "}")
    if not raw:
        return None

    fast = _fast_geometry_result(
        raw, container=container, copy_container_nodes=copy_container_nodes
    )
    if fast is not None:
        return fast

    geom_id, geom_type, rest = _split_geometry_header(raw)
    values = _split_geometry_payload(rest)
    node, diagnostics = geometry_node_from_values(
        geom_type,
        values,
        container=container,
        copy_container_nodes=copy_container_nodes,
    )
    return GeometryParseResult(geom_id, geom_type, node, diagnostics)


def geometry_node_from_values(
    geometry_type: str,
    values: list[str],
    *,
    container: dict[str, AuroraBlock | AuroraItem] | None = None,
    copy_container_nodes: bool = True,
) -> tuple[AuroraBlock | AuroraItem, list[str]]:
    normalized = geometry_type.casefold()
    diagnostics: list[str] = []
    if normalized in {
        "circle",
        "line",
        "larc",
        "parc",
        "rectangle",
        "rectcutcorner",
        "roundedrectangle",
        "oval",
        "box2d",
        "pnt",
    }:
        return AuroraItem(_canonical_type(geometry_type), values), diagnostics
    if normalized in {"polygon", "polygonhole"}:
        if normalized == "polygonhole" and container:
            polygon_hole = _polygon_hole_from_container(
                values, container, copy_nodes=copy_container_nodes
            )
            if polygon_hole is not None:
                return polygon_hole, diagnostics
        return _polygon_block(_canonical_type(geometry_type), values)
    if normalized == "surface":
        block = AuroraBlock("Surface")
        if container:
            for value in values:
                geom = container.get(value)
                if geom is not None:
                    block.append(deepcopy(geom))
        if not block.children:
            for value in values:
                nested = parse_geometry_option([f"{{0:{value}}}"], container=container)
                if nested:
                    block.append(nested.node)
                    diagnostics.extend(nested.diagnostics)
        if not block.children:
            block.add_item("Data", values)
            diagnostics.append("Surface geometry was preserved as raw data.")
        return block, diagnostics
    diagnostics.append(
        f"Unsupported geometry type {geometry_type!r}; preserved as raw item."
    )
    return AuroraItem(_canonical_type(geometry_type), values), diagnostics


def location_values(
    raw_values: list[str],
    *,
    rotation: str | float | int | None = None,
    flip_x: bool = False,
    flip_y: bool = False,
) -> list[str]:
    x = "0"
    y = "0"
    if raw_values:
        items = split_reserved(
            strip_wrapping_pair(" ".join(raw_values), "(", ")"), delimiters=" ,"
        )
        if len(items) >= 2:
            x, y = items[0], items[1]
    rot = "0" if rotation is None or rotation == "" else str(rotation)
    return [x, y, "Y", rot, "1", _bool_text(flip_x), _bool_text(flip_y)]


def split_tuple(value: str) -> list[str]:
    return split_reserved(strip_wrapping_pair(value, "(", ")"), delimiters=" ,")


def _polygon_block(name: str, values: list[str]) -> tuple[AuroraBlock, list[str]]:
    block = AuroraBlock(name)
    diagnostics: list[str] = []
    if not values:
        diagnostics.append(f"{name} geometry has no values.")
        return block, diagnostics

    try:
        count = int(values[0])
    except ValueError:
        block.add_item("Data", values)
        diagnostics.append(
            f"{name} geometry point count is not numeric; preserved as raw data."
        )
        return block, diagnostics

    point_values = values[1 : 1 + count]
    ccw = values[1 + count] if len(values) > 1 + count else "Y"
    solid = values[2 + count] if len(values) > 2 + count else "Y"
    block.add_item("Solid", solid)
    block.add_item("CCW", ccw)
    for point_value in point_values:
        parts = split_tuple(point_value)
        if len(parts) == 2:
            block.add_item("Pnt", parts)
        elif len(parts) == 5:
            block.add_item("Parc", parts)
        else:
            diagnostics.append(
                f"Unsupported polygon vertex {point_value!r}; preserved as raw point."
            )
            block.add_item("Pnt", parts)
    return block, diagnostics


def _fast_geometry_result(
    raw: str,
    *,
    container: dict[str, AuroraBlock | AuroraItem] | None = None,
    copy_container_nodes: bool = True,
) -> GeometryParseResult | None:
    geom_id, geom_type, rest = _split_geometry_header(raw)
    normalized = geom_type.casefold()
    if normalized in {
        "circle",
        "line",
        "larc",
        "parc",
        "rectangle",
        "rectcutcorner",
        "roundedrectangle",
        "oval",
        "box2d",
        "pnt",
    }:
        values = _fast_tuple_values(rest)
        if values is None:
            return None
        return GeometryParseResult(
            geom_id, geom_type, AuroraItem(_canonical_type(geom_type), values), []
        )

    if normalized == "polygon":
        values = _fast_tuple_values(rest)
        if values is None:
            return None
        block = _fast_polygon_block("Polygon", values)
        if block is None:
            return None
        return GeometryParseResult(geom_id, geom_type, block, [])

    if normalized == "polygonhole" and container:
        values = _fast_tuple_values(rest)
        if values is None:
            return None
        polygon_hole = _polygon_hole_from_container(
            values, container, copy_nodes=copy_container_nodes
        )
        if polygon_hole is None:
            return None
        return GeometryParseResult(geom_id, geom_type, polygon_hole, [])

    return None


def _fast_polygon_block(name: str, values: list[str]) -> AuroraBlock | None:
    if not values:
        return None
    try:
        count = int(values[0])
    except ValueError:
        return None

    if len(values) < 1 + count:
        return None
    point_values = values[1 : 1 + count]
    ccw = values[1 + count] if len(values) > 1 + count else "Y"
    solid = values[2 + count] if len(values) > 2 + count else "Y"
    block = AuroraBlock(name)
    block.add_item("Solid", solid)
    block.add_item("CCW", ccw)
    for point_value in point_values:
        parts = _fast_tuple_values(point_value)
        if parts is None:
            return None
        if len(parts) == 2:
            block.add_item("Pnt", parts)
        elif len(parts) == 5:
            block.add_item("Parc", parts)
        else:
            return None
    return block


def _fast_tuple_values(value: str) -> list[str] | None:
    text = value.strip()
    if not text.startswith("(") or not text.endswith(")"):
        return None
    return _split_top_level(text[1:-1], delimiter=",")


def _split_top_level(text: str, *, delimiter: str) -> list[str]:
    values: list[str] = []
    start = 0
    stack: list[str] = []
    in_quote = False
    escaped = False
    opener_to_closer = {"(": ")", "[": "]", "{": "}"}
    closers = set(opener_to_closer.values())

    for index, char in enumerate(text):
        if in_quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_quote = False
            continue
        if char == '"':
            in_quote = True
            continue
        if char in opener_to_closer:
            stack.append(opener_to_closer[char])
            continue
        if char in closers:
            if stack and char == stack[-1]:
                stack.pop()
            continue
        if char == delimiter and not stack:
            values.append(text[start:index].strip())
            start = index + 1

    values.append(text[start:].strip())
    return [value for value in values if value != ""]


def _split_geometry_values(rest: str) -> list[str]:
    if not rest:
        return []
    return split_reserved(
        rest,
        delimiters=" ,",
        reserve_pairs=(("(", ")"), ("[", "]"), ("{", "}"), ('"', '"')),
    )


def _split_geometry_header(raw: str) -> tuple[str | None, str, str]:
    if ":" not in raw:
        pieces = raw.split(maxsplit=1)
        return None, pieces[0], pieces[1] if len(pieces) > 1 else ""

    geom_id, payload = raw.split(":", 1)
    payload = payload.strip()
    end = 0
    while end < len(payload) and (payload[end].isalnum() or payload[end] == "_"):
        end += 1
    geom_type = payload[:end].strip()
    rest = payload[end:].strip()
    if rest.startswith(","):
        rest = rest[1:].strip()
    return geom_id.strip(), geom_type, rest


def _split_geometry_payload(rest: str) -> list[str]:
    rest = rest.strip()
    if not rest:
        return []
    if rest.startswith("(") and rest.endswith(")"):
        return split_tuple(rest)
    return _split_geometry_values(rest)


def _polygon_hole_from_container(
    values: list[str],
    container: dict[str, AuroraBlock | AuroraItem],
    *,
    copy_nodes: bool,
) -> AuroraBlock | None:
    if not values:
        return None
    outline_id = values[0]
    outline = container.get(outline_id)
    if not isinstance(outline, AuroraBlock) or outline.name.casefold() != "polygon":
        return None

    polygon_hole = deepcopy(outline) if copy_nodes else outline
    polygon_hole.name = "PolygonHole"
    holes = AuroraBlock("Holes")
    for geom_id, geom in container.items():
        if geom_id == outline_id:
            continue
        if isinstance(geom, AuroraBlock) and geom.name.casefold() == "polygon":
            holes.append(deepcopy(geom) if copy_nodes else geom)
    polygon_hole.append(holes)
    return polygon_hole


def _canonical_type(value: str) -> str:
    mapping = {
        "larc": "Larc",
        "parc": "Parc",
        "pnt": "Pnt",
        "box2d": "Box2d",
        "rectcutcorner": "RectCutCorner",
        "roundedrectangle": "RoundedRectangle",
        "polygonhole": "PolygonHole",
    }
    return mapping.get(value.casefold(), value[:1].upper() + value[1:])


def _bool_text(value: bool) -> str:
    return "Y" if value else "N"
