from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import cos, degrees, radians, sin
import re
from typing import Iterable

from aurora_translator.semantic.adapters.utils import (
    role_from_net_name,
    semantic_id,
    source_ref,
    unique_append,
)
from aurora_translator.semantic.models import (
    SemanticBoard,
    SemanticComponent,
    SemanticDiagnostic,
    SemanticFootprint,
    SemanticArcGeometry,
    SemanticLayer,
    SemanticMetadata,
    SemanticNet,
    SemanticPad,
    SemanticPadGeometry,
    SemanticPrimitive,
    SemanticPrimitiveGeometry,
    SemanticPin,
    SemanticPolygonVoidGeometry,
    SemanticPoint,
    SemanticShape,
    SemanticSummary,
    SemanticVia,
    SemanticViaGeometry,
    SemanticViaTemplate,
    SemanticViaTemplateGeometry,
    SemanticViaTemplateLayer,
)
from aurora_translator.semantic.passes import (
    build_connectivity_diagnostics,
    build_connectivity_edges,
)
from aurora_translator.sources.brd.models import (
    BRDBlockSummary,
    BRDComponent,
    BRDComponentInstance,
    BRDFootprintInstance,
    BRDKeepout,
    BRDLayer,
    BRDLayout,
    BRDPadDefinition,
    BRDPadstack,
    BRDPadstackComponent,
    BRDPlacedPad,
    BRDSegment,
    BRDShape,
    BRDText,
)


BRD_UNKNOWN_MM_PER_RAW = 0.0001
DEFAULT_PAD_DIAMETER_MM = 0.1
ETCH_CLASS_CODE = 0x06
FOOTPRINT_INSTANCE_BLOCK = 0x2D
BOARD_GEOMETRY_CLASS_CODE = 0x01
BOARD_OUTLINE_SUBCLASS_CODE = 0xEA
_BLIND_VIA_NAME_RE = re.compile(
    r"^V(?P<start>[0-9T])(?P<end>[0-9T])S-(?P<drill>\d+)-(?P<pad>\d+)",
    re.IGNORECASE,
)
_POB_NAME_RE = re.compile(
    r"POB(?P<barrel_w>[0-9D]+)X(?P<barrel_h>[0-9D]+)"
    r"HOB(?P<pad_w>[0-9D]+)X(?P<pad_h>[0-9D]+)",
    re.IGNORECASE,
)
_POB_OFFSET_RE = re.compile(r"_OS(?P<x>[0-9D]+)X(?P<y>[0-9D]+)", re.IGNORECASE)
_CIRCLE_PADSTACK_NAME_RE = re.compile(r"^C(?P<diameter>[0-9D]+)(?:_|$)", re.IGNORECASE)
REF_DES_CLASS_CODE = 0x0D
REF_DES_BOTTOM_SUBCLASS_CODE = 0xFC
REF_DES_TOP_SUBCLASS_CODE = 0xFD


@dataclass(slots=True)
class _PadRecord:
    pad: BRDPlacedPad
    component_id: str
    footprint_id: str | None
    footprint_name: str
    part_name: str
    refdes: str
    net_id: str | None
    shape_id: str
    pin_name: str
    padstack_definition: str | None
    center: SemanticPoint
    layer_name: str | None
    side: str | None
    component_location: SemanticPoint | None
    component_rotation: float | None
    pad_rotation: float | None
    footprint_pad_rotation: float | None
    via_rotation: float | None
    via_position: SemanticPoint | None


@dataclass(slots=True)
class _ComponentInfo:
    key: int
    refdes: str
    part_name: str | None
    layer_name: str | None
    side: str | None
    location: SemanticPoint | None
    rotation: float | None


def from_brd(payload: BRDLayout, *, build_connectivity: bool = True) -> SemanticBoard:
    diagnostics = _source_diagnostics(payload)
    layers = _semantic_layers(payload)
    layer_names = [layer.name for layer in layers]
    top_layer = _top_layer_name(layers)
    bottom_layer = _bottom_layer_name(layers)

    nets, net_ids_by_assignment = _semantic_nets(payload)
    shapes: list[SemanticShape] = []
    shape_ids_by_key: dict[tuple[str, tuple[object, ...]], str] = {}

    pad_definitions_by_key = {pad.key: pad for pad in payload.pad_definitions or []}
    padstack_template_rotations = _padstack_template_rotations(payload)
    via_templates, via_template_ids_by_padstack = _semantic_via_templates(
        payload,
        layer_names,
        padstack_template_rotations,
        shapes,
        shape_ids_by_key,
    )
    instance_footprint_names = _instance_footprint_names(payload)
    texts_by_key = {text.key: text for text in payload.texts or []}
    component_infos = _component_infos(
        payload,
        layer_names,
        top_layer,
        bottom_layer,
        texts_by_key,
    )
    text_values_by_key = _text_values_by_key(payload.texts or [])
    padstacks_by_key = {padstack.key: padstack for padstack in payload.padstacks or []}
    padstack_names_by_key = {
        padstack.key: padstack.name or f"Padstack_{padstack.key}"
        for padstack in payload.padstacks or []
    }
    pad_records = _placed_pad_records(
        payload,
        top_layer,
        net_ids_by_assignment,
        instance_footprint_names,
        component_infos,
        text_values_by_key,
        pad_definitions_by_key,
        padstacks_by_key,
        padstack_names_by_key,
        shapes,
        shape_ids_by_key,
    )
    footprints = _semantic_footprints(payload, pad_records)
    components, pins, pads = _component_pin_pad_records(pad_records, top_layer)
    vias = _semantic_vias(
        payload,
        layer_names,
        net_ids_by_assignment,
        via_template_ids_by_padstack,
        pad_definitions_by_key,
        padstack_names_by_key,
    )
    primitives = _semantic_primitives(payload, layer_names, net_ids_by_assignment)

    board = SemanticBoard(
        metadata=SemanticMetadata(
            source_format="brd",
            source=payload.metadata.source,
            source_parser_version=payload.metadata.parser_version,
            source_schema_version=payload.metadata.output_schema_version,
        ),
        units=_semantic_units(payload),
        summary=SemanticSummary(),
        layers=layers,
        shapes=shapes,
        via_templates=via_templates,
        nets=nets,
        components=components,
        footprints=footprints,
        pins=pins,
        pads=pads,
        vias=vias,
        primitives=primitives,
        board_outline=_board_outline(payload),
        diagnostics=diagnostics,
    )
    if build_connectivity:
        board.connectivity = build_connectivity_edges(board)
        board.diagnostics = [*board.diagnostics, *build_connectivity_diagnostics(board)]
    return board.with_computed_summary()


def _source_diagnostics(payload: BRDLayout) -> list[SemanticDiagnostic]:
    return [
        SemanticDiagnostic(
            severity="warning",
            code="brd.source_diagnostic",
            message=message,
            source=source_ref("brd", "diagnostics"),
        )
        for message in payload.diagnostics
    ]


def _semantic_layers(payload: BRDLayout) -> list[SemanticLayer]:
    string_by_id = {entry.id: entry.value for entry in payload.strings or []}
    candidate_layers = _physical_etch_layer_lists(payload, string_by_id)
    layers: list[SemanticLayer] = []
    for layer_list_index, layer_list, names in candidate_layers:
        for name_index, raw_name in enumerate(names):
            layers.append(
                SemanticLayer(
                    id=semantic_id("layer", raw_name, len(layers)),
                    name=raw_name,
                    layer_type="ETCH",
                    role="signal",
                    side=_layer_side(
                        ETCH_CLASS_CODE,
                        name_index,
                        len(names),
                        raw_name,
                    ),
                    order_index=len(layers),
                    material="BRD_COPPER",
                    source=source_ref(
                        "brd", f"layers[{layer_list_index}].names[{name_index}]"
                    ),
                )
            )
    return layers


def _physical_etch_layer_lists(
    payload: BRDLayout, string_by_id: dict[int, str]
) -> list[tuple[int, BRDLayer, list[str]]]:
    etch_keys = {
        entry.layer_list_key
        for entry in payload.header.layer_map
        if entry.class_code == ETCH_CLASS_CODE and entry.layer_list_key
    }
    resolved: list[tuple[int, BRDLayer, list[str]]] = []
    for index, layer_list in enumerate(payload.layers or []):
        names = _layer_names(layer_list, string_by_id)
        if layer_list.key not in etch_keys or not names:
            continue
        resolved.append((index, layer_list, names))

    stackup_like = [
        item for item in resolved if len(item[2]) > 1 and _has_top_bottom_names(item[2])
    ]
    if stackup_like:
        return [max(stackup_like, key=lambda item: len(item[2]))]

    multi_layer = [item for item in resolved if len(item[2]) > 1]
    if multi_layer:
        return [max(multi_layer, key=lambda item: len(item[2]))]

    return [
        item
        for item in resolved
        if not any(_non_stackup_etch_name(name) for name in item[2])
    ]


def _has_top_bottom_names(names: Iterable[str]) -> bool:
    folded = {name.casefold() for name in names}
    has_top = any(name == "top" or "top" in name for name in folded)
    has_bottom = any(
        name == "bottom" or name == "bot" or "bottom" in name or "bot" in name
        for name in folded
    )
    return has_top and has_bottom


def _non_stackup_etch_name(name: str) -> bool:
    text = name.casefold()
    return "scratch" in text or "construction" in text


def _layer_names(layer: BRDLayer, string_by_id: dict[int, str]) -> list[str]:
    names: list[str] = []
    for value in layer.names:
        if value.startswith("string:"):
            try:
                string_id = int(value.split(":", 1)[1])
            except ValueError:
                names.append(value)
                continue
            names.append(string_by_id.get(string_id, value))
        else:
            names.append(value)
    return names


def _layer_side(class_code: int, index: int, count: int, name: str) -> str | None:
    text = name.casefold()
    if "top" in text or text in {"f_cu", "front"}:
        return "top"
    if "bottom" in text or "bot" in text or text in {"b_cu", "back"}:
        return "bottom"
    if class_code == ETCH_CLASS_CODE and count > 1:
        if index == 0:
            return "top"
        if index == count - 1:
            return "bottom"
        return "internal"
    return None


def _top_layer_name(layers: list[SemanticLayer]) -> str | None:
    for layer in layers:
        if layer.side == "top":
            return layer.name
    return layers[0].name if layers else None


def _bottom_layer_name(layers: list[SemanticLayer]) -> str | None:
    for layer in layers:
        if layer.side == "bottom":
            return layer.name
    return layers[-1].name if layers else None


def _semantic_nets(payload: BRDLayout) -> tuple[list[SemanticNet], dict[int, str]]:
    nets: list[SemanticNet] = []
    net_ids_by_assignment: dict[int, str] = {}
    for index, net in enumerate(payload.nets or []):
        net_id = semantic_id("net", net.name or net.key, index)
        nets.append(
            SemanticNet(
                id=net_id,
                name=net.name or f"Net_{net.key}",
                role=role_from_net_name(net.name),
                source=source_ref("brd", f"nets[{index}]", net.key),
            )
        )
        net_ids_by_assignment[net.assignment] = net_id
        net_ids_by_assignment[net.key] = net_id
    if not any((net.name or "").casefold() == "nonet" for net in nets):
        no_net_id = _no_net_id(payload)
        nets.append(
            SemanticNet(
                id=no_net_id,
                name="NoNet",
                role="unknown",
                source=source_ref("brd", "implicit_no_net", "NoNet"),
            )
        )
    return nets, net_ids_by_assignment


def _no_net_id(payload: BRDLayout) -> str:
    return semantic_id("net", "NoNet", len(payload.nets or []))


def _semantic_via_templates(
    payload: BRDLayout,
    layer_names: list[str],
    padstack_template_rotations: dict[int, float],
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[object, ...]], str],
) -> tuple[list[SemanticViaTemplate], dict[int, str]]:
    via_templates: list[SemanticViaTemplate] = []
    ids_by_padstack: dict[int, str] = {}
    for index, padstack in enumerate(_ordered_padstacks_for_templates(payload)):
        layer_span = _padstack_layer_names(padstack, layer_names)
        barrel_diameter, pad_diameter = _via_name_diameters(padstack.name)
        if barrel_diameter is None:
            barrel_diameter = _raw_length_to_semantic(payload, padstack.drill_size_raw)
        if barrel_diameter is None or barrel_diameter <= 0:
            barrel_diameter = DEFAULT_PAD_DIAMETER_MM
        template_rotation = padstack_template_rotations.get(padstack.key)
        barrel_shape_id = _padstack_barrel_shape_id(
            payload,
            padstack,
            index,
            barrel_diameter,
            template_rotation,
            shapes,
            shape_ids_by_key,
        )
        pad_shape_id = _padstack_layer_pad_shape_id(
            payload,
            padstack,
            index,
            pad_diameter or barrel_diameter,
            barrel_shape_id,
            shapes,
            shape_ids_by_key,
            template_rotation=template_rotation,
        )
        template_id = semantic_id("via_template", padstack.name or padstack.key, index)
        layer_indices = _padstack_layer_indices(padstack, layer_names)
        layer_pads = [
            SemanticViaTemplateLayer(
                layer_name=layer_name,
                pad_shape_id=_padstack_layer_pad_shape_id(
                    payload,
                    padstack,
                    index,
                    pad_diameter or barrel_diameter,
                    barrel_shape_id,
                    shapes,
                    shape_ids_by_key,
                    layer_index=layer_index,
                    template_rotation=template_rotation,
                ),
            )
            for layer_name, layer_index in zip(layer_span, layer_indices)
        ]
        if not layer_pads:
            layer_pads = [
                SemanticViaTemplateLayer(
                    layer_name=layer_name,
                    pad_shape_id=pad_shape_id,
                )
                for layer_name in layer_span
            ]
        via_templates.append(
            SemanticViaTemplate(
                id=template_id,
                name=padstack.name or f"Padstack_{padstack.key}",
                barrel_shape_id=barrel_shape_id,
                layer_pads=layer_pads,
                geometry=SemanticViaTemplateGeometry(
                    source="brd_padstack_components"
                    if padstack.components
                    else "brd_padstack_drill",
                    symbol=padstack.name,
                    layer_pad_source="brd_padstack_components"
                    if padstack.components
                    else None,
                ),
                source=source_ref("brd", f"padstacks[{index}]", padstack.key),
            )
        )
        ids_by_padstack[padstack.key] = template_id
    return via_templates, ids_by_padstack


def _ordered_padstacks_for_templates(payload: BRDLayout):
    padstacks_by_key = {padstack.key: padstack for padstack in payload.padstacks or []}
    ordered_keys: list[int] = []
    seen: set[int] = set()
    for via in payload.vias or []:
        if via.padstack in seen:
            continue
        if via.padstack in padstacks_by_key:
            ordered_keys.append(via.padstack)
            seen.add(via.padstack)
    for padstack in payload.padstacks or []:
        if padstack.key in seen:
            continue
        ordered_keys.append(padstack.key)
        seen.add(padstack.key)
    return [padstacks_by_key[key] for key in ordered_keys]


def _padstack_layer_names(padstack, layer_names: list[str]) -> list[str]:
    if not layer_names:
        return []
    named_span = _padstack_name_layer_span(getattr(padstack, "name", None), layer_names)
    if named_span:
        return named_span
    if getattr(padstack, "layer_count", 0) > 1:
        return list(layer_names)
    return [layer_names[0]]


def _padstack_layer_indices(padstack, layer_names: list[str]) -> list[int]:
    if not layer_names:
        return []
    named_span = _padstack_name_layer_index_span(
        getattr(padstack, "name", None), layer_names
    )
    if named_span:
        return named_span
    if getattr(padstack, "layer_count", 0) > 1:
        return list(range(min(len(layer_names), int(padstack.layer_count))))
    return [0]


def _padstack_name_layer_span(
    padstack_name: str | None, layer_names: list[str]
) -> list[str]:
    indices = _padstack_name_layer_index_span(padstack_name, layer_names)
    return [layer_names[index] for index in indices]


def _padstack_name_layer_index_span(
    padstack_name: str | None, layer_names: list[str]
) -> list[int]:
    if not padstack_name:
        return []
    match = _BLIND_VIA_NAME_RE.match(padstack_name)
    if match is None:
        return []
    start = _via_layer_index(match.group("start"), layer_names)
    end = _via_layer_index(match.group("end"), layer_names)
    if start is None or end is None:
        return []
    low, high = sorted((start, end))
    return list(range(low, high + 1))


def _via_layer_index(value: str, layer_names: list[str]) -> int | None:
    token = value.upper()
    if token == "T":
        return len(layer_names) - 1
    try:
        number = int(token)
    except ValueError:
        return None
    if number <= 0:
        return None
    index = number - 1
    if index >= len(layer_names):
        return None
    return index


def _via_name_diameters(padstack_name: str | None) -> tuple[float | None, float | None]:
    if not padstack_name:
        return None, None
    match = _BLIND_VIA_NAME_RE.match(padstack_name)
    if match is None:
        return None, None
    drill = _via_name_dimension(match.group("drill"))
    pad = _via_name_dimension(match.group("pad"))
    return drill, pad


def _via_name_dimension(value: str) -> float | None:
    try:
        number = int(value)
    except ValueError:
        return None
    divisor = 100.0 if len(value) > 1 else 10.0
    return number / divisor


def _padstack_barrel_shape_id(
    payload: BRDLayout,
    padstack,
    padstack_index: int,
    fallback_diameter: float,
    template_rotation: float | None,
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[object, ...]], str],
) -> str:
    pob = _pob_dimensions(padstack.name)
    if pob is not None:
        barrel_width, barrel_height, _, _ = pob
        barrel_width, barrel_height = _rotate_dimensions_by_degrees(
            barrel_width,
            barrel_height,
            template_rotation,
        )
        return _rect_cut_corner_shape_id(
            shapes,
            shape_ids_by_key,
            width=barrel_width,
            height=barrel_height,
            source_path=f"padstacks[{padstack_index}].name",
            source_key=padstack.key,
        )
    diameter = _raw_length_to_semantic(payload, padstack.drill_size_raw)
    if diameter is None or diameter <= 0:
        diameter = fallback_diameter
    return _shape_id(
        shapes,
        shape_ids_by_key,
        kind="circle",
        auroradb_type="Circle",
        values=[0.0, 0.0, diameter],
        source_path=f"padstacks[{padstack_index}].drill_size_raw",
        source_key=padstack.key,
    )


def _padstack_layer_pad_shape_id(
    payload: BRDLayout,
    padstack,
    padstack_index: int,
    fallback_diameter: float,
    barrel_shape_id: str,
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[object, ...]], str],
    *,
    layer_index: int = 0,
    template_rotation: float | None = None,
) -> str:
    pob = _pob_dimensions(padstack.name)
    if pob is not None:
        _, _, pad_width, pad_height = pob
        pad_width, pad_height = _rotate_dimensions_by_degrees(
            pad_width,
            pad_height,
            template_rotation,
        )
        offset = _pob_offset_for_template(padstack.name)
        if offset:
            return _oblong_polygon_shape_id(
                shapes,
                shape_ids_by_key,
                width=pad_width,
                height=pad_height,
                offset=offset,
                source_path=f"padstacks[{padstack_index}].name",
                source_key=padstack.key,
            )
        return _rect_cut_corner_shape_id(
            shapes,
            shape_ids_by_key,
            width=pad_width,
            height=pad_height,
            source_path=f"padstacks[{padstack_index}].name",
            source_key=padstack.key,
        )

    component_shape_id = _padstack_component_shape_id(
        payload,
        _padstack_layer_component(padstack, layer_index, "pad"),
        padstack,
        fallback_width=fallback_diameter,
        fallback_height=fallback_diameter,
        shapes=shapes,
        shape_ids_by_key=shape_ids_by_key,
        source_path=f"padstacks[{padstack_index}].components",
        source_key=padstack.key,
    )
    if component_shape_id is not None:
        return component_shape_id
    if fallback_diameter <= 0:
        return barrel_shape_id
    return _shape_id(
        shapes,
        shape_ids_by_key,
        kind="circle",
        auroradb_type="Circle",
        values=[0.0, 0.0, fallback_diameter],
        source_path=f"padstacks[{padstack_index}].name",
        source_key=padstack.key,
    )


def _rect_cut_corner_shape_id(
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[object, ...]], str],
    *,
    width: float,
    height: float,
    radius: float | None = None,
    source_path: str,
    source_key: object,
) -> str:
    if radius is None or radius <= 0:
        radius = min(abs(width), abs(height)) / 2.0
    return _shape_id(
        shapes,
        shape_ids_by_key,
        kind="rounded_rectangle",
        auroradb_type="RectCutCorner",
        values=[0.0, 0.0, width, height, radius, "N", "Y", "Y", "Y", "Y"],
        source_path=source_path,
        source_key=source_key,
    )


def _pob_dimensions(
    padstack_name: str | None,
) -> tuple[float, float, float, float] | None:
    if not padstack_name:
        return None
    match = _POB_NAME_RE.search(padstack_name)
    if match is None:
        return None
    values = [
        _allegro_decimal(match.group(name))
        for name in ("barrel_w", "barrel_h", "pad_w", "pad_h")
    ]
    if any(value is None or value <= 0 for value in values):
        return None
    return tuple(float(value) for value in values)  # type: ignore[return-value]


def _allegro_decimal(value: str | None) -> float | None:
    if not value:
        return None
    text = value.upper().replace("D", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _circle_name_diameter(padstack_name: str | None) -> float | None:
    if not padstack_name:
        return None
    match = _CIRCLE_PADSTACK_NAME_RE.match(padstack_name)
    if match is None:
        return None
    return _allegro_decimal(match.group("diameter"))


def _padstack_layer_component(
    padstack: BRDPadstack | None,
    layer_index: int,
    role: str,
) -> BRDPadstackComponent | None:
    if padstack is None:
        return None
    for component in padstack.components or []:
        if component.layer_index == layer_index and component.role == role:
            return component
    return None


def _padstack_component_shape_id(
    payload: BRDLayout,
    component: BRDPadstackComponent | None,
    padstack: BRDPadstack,
    *,
    fallback_width: float,
    fallback_height: float,
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[object, ...]], str],
    source_path: str,
    source_key: object,
) -> str | None:
    if component is None or component.component_type == 0:
        return None
    width = _raw_length_to_semantic(payload, component.width_raw) or fallback_width
    height = _raw_length_to_semantic(payload, component.height_raw) or fallback_height
    if width <= 0 or height <= 0:
        return None

    type_name = component.type_name.casefold()
    if type_name == "circle":
        return _shape_id(
            shapes,
            shape_ids_by_key,
            kind="circle",
            auroradb_type="Circle",
            values=[0.0, 0.0, max(width, height)],
            source_path=source_path,
            source_key=source_key,
        )
    if type_name == "square":
        side = max(width, height)
        return _rectangle_shape_id(
            shapes,
            shape_ids_by_key,
            width=side,
            height=side,
            source_path=source_path,
            source_key=source_key,
        )
    if type_name == "rectangle":
        return _rectangle_shape_id(
            shapes,
            shape_ids_by_key,
            width=width,
            height=height,
            source_path=source_path,
            source_key=source_key,
        )
    if type_name in {"oblong_x", "oblong_y", "rounded_rectangle"}:
        radius = _raw_length_to_semantic(payload, component.z1_raw)
        if radius is None or radius <= 0:
            radius = min(width, height) / 2.0
        return _rect_cut_corner_shape_id(
            shapes,
            shape_ids_by_key,
            width=width,
            height=height,
            radius=radius,
            source_path=source_path,
            source_key=source_key,
        )
    if type_name == "shape_symbol":
        shape_id = _shape_symbol_shape_id(
            payload,
            component,
            shapes,
            shape_ids_by_key,
            source_path=source_path,
            source_key=source_key,
        )
        if shape_id is not None:
            return shape_id
        return _rectangle_shape_id(
            shapes,
            shape_ids_by_key,
            width=width,
            height=height,
            source_path=source_path,
            source_key=source_key,
        )
    return _rectangle_shape_id(
        shapes,
        shape_ids_by_key,
        width=width,
        height=height,
        source_path=source_path,
        source_key=source_key,
    )


def _rectangle_shape_id(
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[object, ...]], str],
    *,
    width: float,
    height: float,
    source_path: str,
    source_key: object,
) -> str:
    return _shape_id(
        shapes,
        shape_ids_by_key,
        kind="rectangle",
        auroradb_type="Rectangle",
        values=[0.0, 0.0, width, height],
        source_path=source_path,
        source_key=source_key,
    )


def _oblong_polygon_shape_id(
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[object, ...]], str],
    *,
    width: float,
    height: float,
    offset: float,
    rotation_degrees: float | None = None,
    source_path: str,
    source_key: object,
) -> str:
    radius = min(abs(width), abs(height)) / 2.0
    if radius <= 0:
        return _rectangle_shape_id(
            shapes,
            shape_ids_by_key,
            width=width,
            height=height,
            source_path=source_path,
            source_key=source_key,
        )

    if abs(height) >= abs(width):
        half_straight = (abs(height) - abs(width)) / 2.0
        vertices = [
            (offset + radius, half_straight),
            (offset + radius, -half_straight),
            (offset - radius, -half_straight, offset, -half_straight, "N"),
            (offset - radius, half_straight),
            (offset + radius, half_straight, offset, half_straight, "N"),
        ]
    else:
        half_straight = (abs(width) - abs(height)) / 2.0
        vertices = [
            (offset - half_straight, radius),
            (offset + half_straight, radius),
            (offset + half_straight, -radius, offset + half_straight, 0, "N"),
            (offset - half_straight, -radius),
            (offset - half_straight, radius, offset - half_straight, 0, "N"),
        ]
    values = [
        5,
        *[
            _format_polygon_shape_vertex(vertex, rotation_degrees)
            for vertex in vertices
        ],
        "Y",
        "Y",
    ]

    return _shape_id(
        shapes,
        shape_ids_by_key,
        kind="polygon",
        auroradb_type="Polygon",
        values=values,
        source_path=source_path,
        source_key=source_key,
    )


def _shape_symbol_shape_id(
    payload: BRDLayout,
    component: BRDPadstackComponent,
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[object, ...]], str],
    *,
    source_path: str,
    source_key: object,
) -> str | None:
    shape_key = component.shape_key or component.z2_raw
    if not shape_key:
        return None
    source_shape = next(
        (shape for shape in payload.shapes or [] if shape.key == shape_key),
        None,
    )
    if source_shape is None:
        return None
    segments_by_key = {segment.key: segment for segment in payload.segments or []}
    _, values = _outline_chain_values(
        payload,
        source_shape.first_segment,
        source_shape.key,
        segments_by_key,
    )
    if len(values) < 3:
        return None
    return _shape_id(
        shapes,
        shape_ids_by_key,
        kind="polygon",
        auroradb_type="Polygon",
        values=[len(values), *values, "Y", "Y"],
        source_path=source_path,
        source_key=source_key,
    )


def _padstack_via_position(
    padstack_name: str | None,
    pad_definition: BRDPadDefinition | None,
    copper_center: SemanticPoint,
) -> SemanticPoint | None:
    if padstack_name is None or pad_definition is None:
        return None
    offset = _pob_offset(padstack_name)
    if offset is None:
        return None
    offset_x, offset_y = offset
    if offset_x == 0 and offset_y == 0:
        return None
    angle = radians(float(pad_definition.rotation_mdeg or 0) / 1000.0 - 90.0)
    dx = offset_x * cos(angle) - offset_y * sin(angle)
    dy = offset_x * sin(angle) + offset_y * cos(angle)
    return SemanticPoint(x=copper_center.x + dx, y=copper_center.y + dy)


def _pob_offset(padstack_name: str | None) -> tuple[float, float] | None:
    if not padstack_name:
        return None
    match = _POB_OFFSET_RE.search(padstack_name)
    if match is None:
        return None
    offset_x = _allegro_decimal(match.group("x"))
    offset_y = _allegro_decimal(match.group("y"))
    if offset_x is None or offset_y is None:
        return None
    return offset_x, offset_y


def _pob_offset_for_template(padstack_name: str | None) -> float:
    offset = _pob_offset(padstack_name)
    if offset is None:
        return 0.0
    offset_x, offset_y = offset
    if offset_x != 0:
        return offset_x
    return offset_y


def _rotate_dimensions_by_degrees(
    width: float,
    height: float,
    rotation_degrees: float | None,
) -> tuple[float, float]:
    if rotation_degrees is None:
        return width, height
    normalized = int(round(rotation_degrees)) % 180
    if normalized == 90:
        return height, width
    return width, height


def _rotate_point_degrees(
    x: float,
    y: float,
    rotation_degrees: float | None,
) -> tuple[float, float]:
    if rotation_degrees is None:
        return x, y
    normalized = float(rotation_degrees) % 360.0
    if abs(normalized) <= 1e-9 or abs(normalized - 360.0) <= 1e-9:
        return x, y
    angle = radians(rotation_degrees)
    return x * cos(angle) - y * sin(angle), x * sin(angle) + y * cos(angle)


def _format_polygon_shape_vertex(
    vertex: tuple[float, float] | tuple[float, float, float, float, str],
    rotation_degrees: float | None,
) -> str:
    x, y = _rotate_point_degrees(vertex[0], vertex[1], rotation_degrees)
    if len(vertex) == 2:
        return f"({_shape_coordinate_text(x)},{_shape_coordinate_text(y)})"
    center_x, center_y = _rotate_point_degrees(vertex[2], vertex[3], rotation_degrees)
    return (
        f"({_shape_coordinate_text(x)},{_shape_coordinate_text(y)},"
        f"{_shape_coordinate_text(center_x)},{_shape_coordinate_text(center_y)},"
        f"{vertex[4]})"
    )


def _shape_coordinate_text(value: float) -> str:
    if abs(value) <= 1e-12:
        value = 0.0
    text = f"{value:.12f}".rstrip("0").rstrip(".")
    return text or "0"


def _degrees(rotation: float) -> float:
    return degrees(rotation)


def _padstack_template_rotations(payload: BRDLayout) -> dict[int, float]:
    rotations_by_padstack: dict[int, set[int]] = defaultdict(set)
    for pad_definition in payload.pad_definitions or []:
        rotations_by_padstack[pad_definition.padstack].add(
            int(round(float(pad_definition.rotation_mdeg or 0) / 1000.0)) % 360
        )
    result: dict[int, float] = {}
    for padstack_key, rotations in rotations_by_padstack.items():
        if len(rotations) == 1:
            result[padstack_key] = float(next(iter(rotations)))
    return result


def _placed_pad_shape_id(
    payload: BRDLayout,
    pad_definition: BRDPadDefinition | None,
    padstack: BRDPadstack | None,
    *,
    width: float,
    height: float,
    placed_pad_index: int,
    placed_pad_key: int,
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[object, ...]], str],
    footprint_rotation_degrees: float | None = None,
) -> str:
    if padstack is not None:
        pob = _pob_dimensions(padstack.name)
        if pob is not None:
            _, _, pad_width, pad_height = pob
            rotation_degrees = (
                float(pad_definition.rotation_mdeg or 0) / 1000.0
                if pad_definition is not None
                else 0.0
            )
            pad_width, pad_height = _rotate_dimensions_by_degrees(
                pad_width,
                pad_height,
                rotation_degrees,
            )
            offset = _pob_offset_for_template(padstack.name)
            if offset:
                return _oblong_polygon_shape_id(
                    shapes,
                    shape_ids_by_key,
                    width=pad_width,
                    height=pad_height,
                    offset=offset,
                    rotation_degrees=(
                        -footprint_rotation_degrees
                        if footprint_rotation_degrees is not None
                        else None
                    ),
                    source_path="padstacks.name",
                    source_key=padstack.key,
                )
            pad_width, pad_height = _rotate_dimensions_by_degrees(
                pad_width,
                pad_height,
                -footprint_rotation_degrees
                if footprint_rotation_degrees is not None
                else None,
            )
            return _rect_cut_corner_shape_id(
                shapes,
                shape_ids_by_key,
                width=pad_width,
                height=pad_height,
                source_path="padstacks.name",
                source_key=padstack.key,
            )
        component = _padstack_layer_component(padstack, 0, "pad")
        shape_id = _padstack_component_shape_id(
            payload,
            component,
            padstack,
            fallback_width=width,
            fallback_height=height,
            shapes=shapes,
            shape_ids_by_key=shape_ids_by_key,
            source_path="padstacks.components",
            source_key=padstack.key,
        )
        if shape_id is not None:
            return shape_id
        circle_diameter = _circle_name_diameter(padstack.name)
        if circle_diameter is not None and circle_diameter > 0:
            return _shape_id(
                shapes,
                shape_ids_by_key,
                kind="circle",
                auroradb_type="Circle",
                values=[0.0, 0.0, circle_diameter],
                source_path="padstacks.name",
                source_key=padstack.key,
            )

    return _shape_id(
        shapes,
        shape_ids_by_key,
        kind="rectangle",
        auroradb_type="Rectangle",
        values=[0.0, 0.0, width, height],
        source_path=f"placed_pads[{placed_pad_index}].coords_raw",
        source_key=placed_pad_key,
    )


def _placed_pad_records(
    payload: BRDLayout,
    top_layer: str | None,
    net_ids_by_assignment: dict[int, str],
    instance_footprint_names: dict[int, str],
    component_infos: dict[int, _ComponentInfo],
    text_values_by_key: dict[int, str],
    pad_definitions_by_key: dict[int, BRDPadDefinition],
    padstacks_by_key: dict[int, BRDPadstack],
    padstack_names_by_key: dict[int, str],
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[object, ...]], str],
) -> list[_PadRecord]:
    if top_layer is None:
        return []
    records: list[_PadRecord] = []
    for index, placed_pad in enumerate(payload.placed_pads or []):
        actual_pin_name = _pin_name(placed_pad, text_values_by_key)
        if not _placed_pad_has_logical_pin(placed_pad, actual_pin_name):
            continue
        bbox = _bbox_points(payload, placed_pad.coords_raw)
        if bbox is None:
            continue
        x_min, y_min, x_max, y_max = bbox
        width = abs(x_max - x_min)
        height = abs(y_max - y_min)
        if width <= 0 or height <= 0:
            continue
        copper_center = SemanticPoint(
            x=(x_min + x_max) / 2.0,
            y=(y_min + y_max) / 2.0,
        )
        pad_definition = pad_definitions_by_key.get(placed_pad.pad)
        padstack = (
            padstacks_by_key.get(pad_definition.padstack)
            if pad_definition is not None
            else None
        )
        footprint_name = instance_footprint_names.get(
            placed_pad.parent_footprint, f"BRD_FOOTPRINT_{placed_pad.parent_footprint}"
        )
        component_info = component_infos.get(placed_pad.parent_footprint)
        shape_id = _placed_pad_shape_id(
            payload,
            pad_definition,
            padstack,
            width=width,
            height=height,
            placed_pad_index=index,
            placed_pad_key=placed_pad.key,
            footprint_rotation_degrees=(
                _degrees(component_info.rotation) if component_info else None
            ),
            shapes=shapes,
            shape_ids_by_key=shape_ids_by_key,
        )
        component_key = (
            component_info.key if component_info else placed_pad.parent_footprint
        )
        refdes = (
            component_info.refdes
            if component_info and component_info.refdes
            else f"BRD_{placed_pad.parent_footprint}"
        )
        part_name = (
            component_info.part_name
            if component_info and component_info.part_name
            else footprint_name
        )
        padstack_definition = (
            padstack_names_by_key.get(pad_definition.padstack)
            if pad_definition
            else None
        )
        via_position = _padstack_via_position(
            padstack_definition,
            pad_definition,
            copper_center,
        )
        center = via_position or copper_center
        footprint_pad_rotation = _pad_local_rotation_for_footprint(
            pad_definition, padstack
        )
        pad_rotation = (
            component_info.rotation if component_info else 0.0
        ) + footprint_pad_rotation
        via_rotation = _pad_rotation_for_shape(pad_definition, padstack_definition)
        footprint_id = semantic_id("footprint", footprint_name)
        records.append(
            _PadRecord(
                pad=placed_pad,
                component_id=semantic_id("component", component_key),
                footprint_id=footprint_id,
                footprint_name=footprint_name,
                part_name=part_name,
                refdes=refdes,
                net_id=net_ids_by_assignment.get(placed_pad.net_assignment),
                shape_id=shape_id,
                pin_name=actual_pin_name,
                padstack_definition=padstack_definition,
                center=center,
                layer_name=(component_info.layer_name if component_info else None)
                or top_layer,
                side=(component_info.side if component_info else None) or "top",
                component_location=component_info.location if component_info else None,
                component_rotation=component_info.rotation if component_info else None,
                pad_rotation=pad_rotation,
                footprint_pad_rotation=footprint_pad_rotation,
                via_rotation=via_rotation,
                via_position=via_position,
            )
        )
    return records


def _pad_rotation_for_shape(
    pad_definition: BRDPadDefinition | None,
    padstack_name: str | None,
) -> float:
    if padstack_name and padstack_name.upper().startswith("POB"):
        return 0.0
    return radians(
        float(pad_definition.rotation_mdeg if pad_definition else 0) / 1000.0
    )


def _pad_local_rotation_for_footprint(
    pad_definition: BRDPadDefinition | None,
    padstack: BRDPadstack | None,
) -> float:
    if padstack is not None and _pob_dimensions(padstack.name) is not None:
        return 0.0
    rotation_degrees = float(pad_definition.rotation_mdeg if pad_definition else 0)
    rotation_degrees /= 1000.0
    if _pad_shape_is_half_turn_symmetric(padstack):
        rotation_degrees %= 180.0
        if abs(rotation_degrees - 180.0) < 1e-9:
            rotation_degrees = 0.0
    return radians(rotation_degrees)


def _pad_shape_is_half_turn_symmetric(padstack: BRDPadstack | None) -> bool:
    if padstack is None:
        return True
    if _circle_name_diameter(padstack.name) is not None:
        return True
    component = _padstack_layer_component(padstack, 0, "pad")
    if component is None or component.component_type == 0:
        return True
    return component.type_name.casefold() in {
        "circle",
        "square",
        "rectangle",
        "oblong_x",
        "oblong_y",
        "rounded_rectangle",
    }


def _placed_pad_has_logical_pin(placed_pad: BRDPlacedPad, pin_name: str) -> bool:
    if placed_pad.pin_number:
        return True
    return bool(pin_name and pin_name != str(placed_pad.key))


def _pin_name(
    placed_pad: BRDPlacedPad, text_values_by_key: dict[int, str] | None = None
) -> str:
    if text_values_by_key:
        name = text_values_by_key.get(placed_pad.name_text)
        if name:
            return name
    if placed_pad.pin_number:
        return str(placed_pad.pin_number)
    return str(placed_pad.key)


def _semantic_footprints(
    payload: BRDLayout, pad_records: list[_PadRecord]
) -> list[SemanticFootprint]:
    names = {
        record.footprint_name: record.footprint_id
        for record in pad_records
        if record.footprint_id
    }
    for footprint in payload.footprints or []:
        if not footprint.name:
            continue
        names.setdefault(footprint.name, semantic_id("footprint", footprint.name))

    footprints: list[SemanticFootprint] = []
    pad_ids_by_footprint: dict[str, list[str]] = defaultdict(list)
    for record in pad_records:
        if record.footprint_id:
            unique_append(
                pad_ids_by_footprint[record.footprint_id],
                semantic_id("pad", record.pad.key),
            )

    for index, (name, footprint_id) in enumerate(sorted(names.items())):
        footprints.append(
            SemanticFootprint(
                id=footprint_id,
                name=name,
                pad_ids=pad_ids_by_footprint.get(footprint_id, []),
                source=source_ref("brd", "footprints", index),
            )
        )
    return footprints


def _component_pin_pad_records(
    pad_records: list[_PadRecord], top_layer: str | None
) -> tuple[list[SemanticComponent], list[SemanticPin], list[SemanticPad]]:
    pads_by_component: dict[str, list[_PadRecord]] = defaultdict(list)
    for record in pad_records:
        pads_by_component[record.component_id].append(record)

    components: list[SemanticComponent] = []
    pins: list[SemanticPin] = []
    pads: list[SemanticPad] = []
    for component_id, records in sorted(pads_by_component.items()):
        first_record = records[0]
        component_key = str(first_record.pad.parent_footprint)
        component_center = first_record.component_location or _average_point(
            record.center for record in records
        )
        pin_ids: list[str] = []
        pad_ids: list[str] = []
        footprint_name = first_record.footprint_name
        footprint_id = first_record.footprint_id

        for record in records:
            pin_id = semantic_id(
                "pin",
                f"{record.pad.parent_footprint}:{record.pin_name}:{record.pad.key}",
            )
            pad_id = semantic_id("pad", record.pad.key)
            unique_append(pin_ids, pin_id)
            unique_append(pad_ids, pad_id)
            pins.append(
                SemanticPin(
                    id=pin_id,
                    name=record.pin_name,
                    component_id=component_id,
                    net_id=record.net_id,
                    pad_ids=[pad_id],
                    layer_name=record.layer_name or top_layer,
                    position=record.center,
                    source=source_ref("brd", "placed_pads.pin_number", record.pad.key),
                )
            )
            pads.append(
                SemanticPad(
                    id=pad_id,
                    name=record.pin_name,
                    footprint_id=footprint_id,
                    component_id=component_id,
                    pin_id=pin_id,
                    net_id=record.net_id,
                    layer_name=record.layer_name or top_layer,
                    position=record.center,
                    padstack_definition=record.padstack_definition
                    or str(record.pad.pad or ""),
                    geometry=SemanticPadGeometry(
                        shape_id=record.shape_id,
                        source="brd_padstack_component"
                        if record.padstack_definition
                        else "brd_placed_pad_bbox",
                        rotation=record.pad_rotation,
                        footprint_rotation=record.footprint_pad_rotation,
                        via_rotation=record.via_rotation,
                        via_position=record.via_position.model_dump(mode="json")
                        if record.via_position is not None
                        else None,
                    ),
                    source=source_ref("brd", "placed_pads", record.pad.key),
                )
            )

        components.append(
            SemanticComponent(
                id=component_id,
                refdes=first_record.refdes or f"BRD_{component_key}",
                name=first_record.refdes or f"BRD_{component_key}",
                part_name=first_record.part_name or footprint_name,
                package_name=footprint_name,
                footprint_id=footprint_id,
                layer_name=first_record.layer_name or top_layer,
                side=first_record.side or "top",
                location=component_center,
                rotation=first_record.component_rotation or 0,
                pin_ids=pin_ids,
                pad_ids=pad_ids,
                source=source_ref("brd", "placed_pads.parent_footprint", component_key),
            )
        )

    return components, pins, pads


def _semantic_vias(
    payload: BRDLayout,
    layer_names: list[str],
    net_ids_by_assignment: dict[int, str],
    via_template_ids_by_padstack: dict[int, str],
    pad_definitions_by_key: dict[int, BRDPadDefinition],
    padstack_names_by_key: dict[int, str],
) -> list[SemanticVia]:
    vias: list[SemanticVia] = []
    if not layer_names:
        return vias
    padstacks_by_key = {padstack.key: padstack for padstack in payload.padstacks or []}
    for index, via in enumerate(payload.vias or []):
        x = _raw_coord_to_semantic(payload, via.x_raw)
        y = _raw_coord_to_semantic(payload, via.y_raw)
        if x is None or y is None:
            continue
        template_id = via_template_ids_by_padstack.get(via.padstack)
        net_id = net_ids_by_assignment.get(via.net_assignment)
        padstack = padstacks_by_key.get(via.padstack)
        vias.append(
            SemanticVia(
                id=semantic_id("via", via.key, index),
                name=str(via.key),
                template_id=template_id,
                net_id=net_id,
                layer_names=_padstack_layer_names(padstack, layer_names)
                if padstack is not None
                else layer_names,
                position=SemanticPoint(x=x, y=y),
                geometry=SemanticViaGeometry(rotation=0),
                source=source_ref("brd", f"vias[{index}]", via.key),
            )
        )
    vias.extend(
        _semantic_pad_definition_hole_vias(
            payload,
            layer_names,
            net_ids_by_assignment,
            via_template_ids_by_padstack,
            pad_definitions_by_key,
            padstack_names_by_key,
            start_index=len(vias),
        )
    )
    return vias


def _semantic_pad_definition_hole_vias(
    payload: BRDLayout,
    layer_names: list[str],
    net_ids_by_assignment: dict[int, str],
    via_template_ids_by_padstack: dict[int, str],
    pad_definitions_by_key: dict[int, BRDPadDefinition],
    padstack_names_by_key: dict[int, str],
    *,
    start_index: int,
) -> list[SemanticVia]:
    padstacks_by_key = {padstack.key: padstack for padstack in payload.padstacks or []}
    text_values_by_key = _text_values_by_key(payload.texts or [])
    no_net_id = _no_net_id(payload)
    vias: list[SemanticVia] = []
    seen: set[tuple[int, float, float, str | None]] = set()
    for placed_pad in payload.placed_pads or []:
        pin_name = _pin_name(placed_pad, text_values_by_key)
        if _placed_pad_has_logical_pin(placed_pad, pin_name):
            continue
        pad_definition = pad_definitions_by_key.get(placed_pad.pad)
        if pad_definition is None:
            continue
        padstack = padstacks_by_key.get(pad_definition.padstack)
        if padstack is None or padstack.layer_count <= 1:
            continue
        template_id = via_template_ids_by_padstack.get(pad_definition.padstack)
        if template_id is None:
            continue
        bbox = _bbox_points(payload, placed_pad.coords_raw)
        if bbox is None:
            continue
        x_min, y_min, x_max, y_max = bbox
        x = (x_min + x_max) / 2.0
        y = (y_min + y_max) / 2.0
        net_id = no_net_id
        key = (pad_definition.padstack, round(x, 9), round(y, 9), net_id)
        if key in seen:
            continue
        seen.add(key)
        index = start_index + len(vias)
        vias.append(
            SemanticVia(
                id=semantic_id("via", f"pad:{placed_pad.key}:{index}"),
                name=padstack_names_by_key.get(pad_definition.padstack),
                template_id=template_id,
                net_id=net_id,
                layer_names=_padstack_layer_names(padstack, layer_names),
                position=SemanticPoint(x=x, y=y),
                geometry=SemanticViaGeometry(
                    rotation=radians(float(pad_definition.rotation_mdeg or 0) / 1000.0)
                ),
                source=source_ref("brd", "pad_definitions", pad_definition.key),
            )
        )
    return vias


def _semantic_primitives(
    payload: BRDLayout,
    layer_names: list[str],
    net_ids_by_assignment: dict[int, str],
) -> list[SemanticPrimitive]:
    segments_by_key = {segment.key: segment for segment in payload.segments or []}
    segment_indexes = {
        segment.key: index for index, segment in enumerate(payload.segments or [])
    }
    keepouts_by_key = {keepout.key: keepout for keepout in payload.keepouts or []}
    keepout_indexes = {
        keepout.key: index for index, keepout in enumerate(payload.keepouts or [])
    }
    conn_net_ids_by_item = _net_ids_by_connected_item(payload, net_ids_by_assignment)
    primitives: list[SemanticPrimitive] = []

    for track_index, track in enumerate(payload.tracks or []):
        layer_name = _layer_name_from_info(track.layer, layer_names)
        if layer_name is None:
            continue
        net_id = net_ids_by_assignment.get(
            track.net_assignment
        ) or conn_net_ids_by_item.get(track.key)
        for segment in _walk_segment_chain(
            track.first_segment, track.key, segments_by_key
        ):
            primitive = _segment_primitive(
                payload,
                segment,
                layer_name=layer_name,
                net_id=net_id,
                source_path=f"tracks[{track_index}].first_segment",
                source_index=segment_indexes.get(segment.key),
            )
            if primitive is not None:
                primitives.append(primitive)

    for shape_index, shape in enumerate(payload.shapes or []):
        primitive = _shape_primitive(
            payload,
            shape,
            shape_index=shape_index,
            layer_names=layer_names,
            segments_by_key=segments_by_key,
            keepouts_by_key=keepouts_by_key,
            net_id=conn_net_ids_by_item.get(shape.key),
            keepout_indexes=keepout_indexes,
            segment_indexes=segment_indexes,
        )
        if primitive is not None:
            primitives.append(primitive)

    return primitives


def _board_outline(payload: BRDLayout):
    segments_by_key = {segment.key: segment for segment in payload.segments or []}
    candidates = []
    for shape_index, shape in enumerate(payload.shapes or []):
        layer = shape.layer
        if layer.class_code != BOARD_GEOMETRY_CLASS_CODE:
            continue
        arcs, values = _outline_chain_values(
            payload, shape.first_segment, shape.key, segments_by_key
        )
        if len(values) < 3:
            continue
        bbox = _outline_values_bbox(values)
        if bbox is None:
            continue
        x_min, y_min, x_max, y_max = bbox
        area = abs((x_max - x_min) * (y_max - y_min))
        is_named_outline = (layer.subclass_name or "").casefold() == "bgeom_outline"
        is_outline_code = layer.subclass_code == BOARD_OUTLINE_SUBCLASS_CODE
        candidates.append(
            (
                1 if is_named_outline or is_outline_code else 0,
                area,
                len(arcs),
                -shape_index,
                values,
            )
        )
    if not candidates:
        return {}
    _, _, path_count, _, values = max(candidates)
    return {
        "kind": "polygon",
        "auroradb_type": "Polygon",
        "source": "brd_board_geometry_outline",
        "path_count": path_count,
        "values": [len(values), *values, "Y", "Y"],
    }


def _outline_chain_values(
    payload: BRDLayout,
    first_segment: int,
    tail_key: int,
    segments_by_key: dict[int, BRDSegment],
) -> tuple[list[BRDSegment], list[str]]:
    segments = list(_walk_segment_chain(first_segment, tail_key, segments_by_key))
    if not segments:
        return [], []
    first_start = _raw_point_to_semantic(payload, segments[0].start_raw)
    if first_start is None:
        return [], []
    values = [_outline_point_value(first_start)]
    for index, segment in enumerate(segments):
        end = _raw_point_to_semantic(payload, segment.end_raw)
        if end is None:
            continue
        closing = index == len(segments) - 1 and _same_point_list(end, first_start)
        if segment.kind == "arc":
            center = _raw_point_to_semantic(payload, segment.center_raw)
            if center is None:
                continue
            values.append(
                _outline_arc_value(
                    end,
                    center,
                    "N" if segment.clockwise else "Y",
                )
            )
        elif not closing:
            values.append(_outline_point_value(end))
    return segments, values


def _outline_values_bbox(values: list[str]) -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for value in values:
        parts = value.strip("()").split(",")
        if len(parts) < 2:
            continue
        try:
            xs.append(float(parts[0]))
            ys.append(float(parts[1]))
            if len(parts) >= 4:
                xs.append(float(parts[2]))
                ys.append(float(parts[3]))
        except ValueError:
            continue
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _outline_point_value(point: list[float]) -> str:
    return f"({point[0]},{point[1]})"


def _outline_arc_value(end: list[float], center: list[float], direction: str) -> str:
    return f"({end[0]},{end[1]},{center[0]},{center[1]},{direction})"


def _same_point_list(left: list[float], right: list[float]) -> bool:
    return abs(left[0] - right[0]) <= 1e-9 and abs(left[1] - right[1]) <= 1e-9


def _segment_primitive(
    payload: BRDLayout,
    segment: BRDSegment,
    *,
    layer_name: str,
    net_id: str | None,
    source_path: str,
    source_index: int | None,
) -> SemanticPrimitive | None:
    start = _raw_point_to_semantic(payload, segment.start_raw)
    end = _raw_point_to_semantic(payload, segment.end_raw)
    width = _raw_length_to_semantic(payload, segment.width_raw)
    if start is None or end is None or width is None:
        return None

    path = f"segments[{source_index}]" if source_index is not None else source_path
    if segment.kind == "line":
        return SemanticPrimitive(
            id=semantic_id("primitive", f"brd-line:{segment.key}"),
            kind="trace",
            layer_name=layer_name,
            net_id=net_id,
            geometry=SemanticPrimitiveGeometry(
                record_kind="LINE",
                feature_id=segment.key,
                width=width,
                center_line=[start, end],
            ),
            source=source_ref("brd", path, segment.key),
        )

    center = _raw_point_to_semantic(payload, segment.center_raw)
    if segment.kind != "arc" or center is None:
        return None
    return SemanticPrimitive(
        id=semantic_id("primitive", f"brd-arc:{segment.key}"),
        kind="arc",
        layer_name=layer_name,
        net_id=net_id,
        geometry=SemanticPrimitiveGeometry(
            record_kind="ARC",
            feature_id=segment.key,
            width=width,
            start=start,
            end=end,
            center=center,
            radius=_raw_length_to_semantic(payload, segment.radius_raw),
            clockwise=segment.clockwise,
            is_ccw=False if segment.clockwise else True,
        ),
        source=source_ref("brd", path, segment.key),
    )


def _shape_primitive(
    payload: BRDLayout,
    shape: BRDShape,
    *,
    shape_index: int,
    layer_names: list[str],
    segments_by_key: dict[int, BRDSegment],
    keepouts_by_key: dict[int, BRDKeepout],
    net_id: str | None,
    keepout_indexes: dict[int, int],
    segment_indexes: dict[int, int],
) -> SemanticPrimitive | None:
    if net_id is None:
        return None
    layer_name = _layer_name_from_info(shape.layer, layer_names)
    if layer_name is None:
        return None

    arcs, raw_points = _polygon_chain_geometry(
        payload, shape.first_segment, shape.key, segments_by_key
    )
    if len(raw_points) < 2:
        return None

    voids: list[SemanticPolygonVoidGeometry] = []
    for keepout in _walk_keepout_chain(shape.first_keepout, keepouts_by_key):
        void_arcs, void_raw_points = _polygon_chain_geometry(
            payload, keepout.first_segment, keepout.key, segments_by_key
        )
        if len(void_raw_points) < 2:
            continue
        keepout_index = keepout_indexes.get(keepout.key)
        voids.append(
            SemanticPolygonVoidGeometry(
                raw_points=void_raw_points,
                arcs=void_arcs,
                source_contour_index=keepout_index,
            )
        )

    bbox = _bbox_points(payload, shape.coords_raw)
    return SemanticPrimitive(
        id=semantic_id("primitive", f"brd-shape:{shape.key}"),
        kind="polygon",
        layer_name=layer_name,
        net_id=net_id,
        geometry=SemanticPrimitiveGeometry(
            record_kind="SHAPE",
            feature_id=shape.key,
            raw_points=raw_points,
            arcs=arcs,
            voids=voids,
            bbox=list(bbox) if bbox is not None else None,
            has_voids=bool(voids),
        ),
        source=source_ref("brd", f"shapes[{shape_index}]", shape.key),
    )


def _polygon_chain_geometry(
    payload: BRDLayout,
    first_segment: int,
    tail_key: int,
    segments_by_key: dict[int, BRDSegment],
) -> tuple[list[SemanticArcGeometry], list[list[float | int | None]]]:
    arcs: list[SemanticArcGeometry] = []
    raw_points: list[list[float | int | None]] = []
    for segment in _walk_segment_chain(first_segment, tail_key, segments_by_key):
        geometry = _segment_arc_geometry(payload, segment)
        if geometry is None:
            continue
        arcs.append(geometry)
        end = _raw_point_to_semantic(payload, segment.end_raw)
        if end is not None:
            raw_points.append(end)

    if arcs:
        first_start = arcs[0].start
        if first_start is not None:
            raw_points.insert(0, list(first_start))
    return arcs, raw_points


def _segment_arc_geometry(
    payload: BRDLayout, segment: BRDSegment
) -> SemanticArcGeometry | None:
    start = _raw_point_to_semantic(payload, segment.start_raw)
    end = _raw_point_to_semantic(payload, segment.end_raw)
    if start is None or end is None:
        return None
    if segment.kind == "line":
        return SemanticArcGeometry(start=start, end=end, is_segment=True)

    center = _raw_point_to_semantic(payload, segment.center_raw)
    if center is None:
        return None
    return SemanticArcGeometry(
        start=start,
        end=end,
        center=center,
        radius=_raw_length_to_semantic(payload, segment.radius_raw),
        clockwise=segment.clockwise,
        is_ccw=False if segment.clockwise else True,
    )


def _walk_segment_chain(
    first_key: int, tail_key: int, segments_by_key: dict[int, BRDSegment]
) -> Iterable[BRDSegment]:
    current = first_key
    seen: set[int] = set()
    while current and current not in seen:
        seen.add(current)
        segment = segments_by_key.get(current)
        if segment is None:
            break
        yield segment
        next_key = segment.next
        if not next_key or next_key == tail_key:
            break
        current = next_key


def _walk_keepout_chain(
    first_key: int, keepouts_by_key: dict[int, BRDKeepout]
) -> Iterable[BRDKeepout]:
    current = first_key
    seen: set[int] = set()
    while current and current not in seen:
        seen.add(current)
        keepout = keepouts_by_key.get(current)
        if keepout is None:
            break
        yield keepout
        current = keepout.next


def _net_ids_by_connected_item(
    payload: BRDLayout, net_ids_by_assignment: dict[int, str]
) -> dict[int, str]:
    next_by_key = {
        block.key: block.next
        for block in payload.blocks or []
        if block.key is not None and block.next is not None
    }
    result: dict[int, str] = {}
    for assignment in payload.net_assignments or []:
        net_id = net_ids_by_assignment.get(assignment.net) or net_ids_by_assignment.get(
            assignment.key
        )
        if net_id is None:
            continue
        current = assignment.conn_item
        seen: set[int] = set()
        while current and current not in seen:
            seen.add(current)
            result.setdefault(current, net_id)
            next_key = next_by_key.get(current)
            if not next_key or next_key == assignment.key:
                break
            current = next_key
    return result


def _layer_name_from_info(layer: object, layer_names: list[str]) -> str | None:
    class_code = getattr(layer, "class_code", None)
    if class_code != ETCH_CLASS_CODE:
        return None
    subclass_name = getattr(layer, "subclass_name", None)
    if isinstance(subclass_name, str) and subclass_name in layer_names:
        return subclass_name

    subclass_code = getattr(layer, "subclass_code", None)
    if isinstance(subclass_code, int):
        if 0 <= subclass_code < len(layer_names):
            return layer_names[subclass_code]
        if 1 <= subclass_code <= len(layer_names):
            return layer_names[subclass_code - 1]
    return None


def _instance_footprint_names(payload: BRDLayout) -> dict[int, str]:
    instance_next_by_key = {
        block.key: block.next
        for block in payload.blocks or []
        if _is_footprint_instance_block(block)
    }
    result: dict[int, str] = {}
    for footprint in payload.footprints or []:
        if not footprint.name or not footprint.first_instance:
            continue
        current = footprint.first_instance
        seen: set[int] = set()
        while current and current not in seen:
            seen.add(current)
            result[current] = footprint.name
            next_key = instance_next_by_key.get(current)
            if not next_key or next_key == footprint.key:
                break
            current = next_key
    return result


def _component_infos(
    payload: BRDLayout,
    layer_names: list[str],
    top_layer: str | None,
    bottom_layer: str | None,
    texts_by_key: dict[int, BRDText],
) -> dict[int, _ComponentInfo]:
    component_instances_by_key = {
        instance.key: instance for instance in payload.component_instances or []
    }
    component_instances_by_footprint = {
        instance.footprint_instance: instance
        for instance in payload.component_instances or []
        if instance.footprint_instance
    }
    part_names_by_instance = _part_names_by_component_instance(
        payload.components or [], component_instances_by_key
    )

    result: dict[int, _ComponentInfo] = {}
    for footprint_instance in payload.footprint_instances or []:
        component_instance = component_instances_by_key.get(
            footprint_instance.component_instance
        ) or component_instances_by_footprint.get(footprint_instance.key)
        component_key = (
            component_instance.key if component_instance else footprint_instance.key
        )
        refdes = (
            component_instance.refdes
            if component_instance and component_instance.refdes
            else f"BRD_{footprint_instance.key}"
        )
        text_layer = (
            texts_by_key.get(footprint_instance.text).layer
            if texts_by_key.get(footprint_instance.text) is not None
            else None
        )
        layer_name = _component_layer_from_refdes_text(
            text_layer,
            layer_names,
            top_layer,
            bottom_layer,
        )
        if layer_name is None:
            side = "bottom" if footprint_instance.layer != 0 else "top"
            layer_name = bottom_layer if side == "bottom" else top_layer
        else:
            side = _component_side_from_layer(layer_name, top_layer, bottom_layer)
        result[footprint_instance.key] = _ComponentInfo(
            key=component_key,
            refdes=refdes,
            part_name=part_names_by_instance.get(component_key),
            layer_name=layer_name,
            side=side,
            location=_footprint_instance_location(payload, footprint_instance),
            rotation=radians(_footprint_instance_rotation_degrees(footprint_instance)),
        )
    return result


def _component_layer_from_refdes_text(
    layer: object,
    layer_names: list[str],
    top_layer: str | None,
    bottom_layer: str | None,
) -> str | None:
    if layer is None or getattr(layer, "class_code", None) != REF_DES_CLASS_CODE:
        return None
    subclass_code = getattr(layer, "subclass_code", None)
    if subclass_code == REF_DES_TOP_SUBCLASS_CODE:
        return top_layer
    if subclass_code == REF_DES_BOTTOM_SUBCLASS_CODE:
        return bottom_layer
    if not isinstance(subclass_code, int):
        return None
    if subclass_code % 2 != 0:
        return None
    layer_index = subclass_code // 2 + 1
    if 0 < layer_index < len(layer_names):
        return layer_names[layer_index]
    return None


def _component_side_from_layer(
    layer_name: str | None,
    top_layer: str | None,
    bottom_layer: str | None,
) -> str | None:
    if layer_name is None:
        return None
    if top_layer is not None and layer_name == top_layer:
        return "top"
    if bottom_layer is not None and layer_name == bottom_layer:
        return "bottom"
    return "internal"


def _part_names_by_component_instance(
    components: Iterable[BRDComponent],
    component_instances_by_key: dict[int, BRDComponentInstance],
) -> dict[int, str]:
    result: dict[int, str] = {}
    for component in components:
        part_name = component.device_type or component.symbol_name
        if not part_name or not component.first_instance:
            continue
        current = component.first_instance
        seen: set[int] = set()
        while current and current not in seen:
            seen.add(current)
            instance = component_instances_by_key.get(current)
            if instance is None:
                break
            result.setdefault(instance.key, part_name)
            next_key = instance.next
            if not next_key or next_key == component.key:
                break
            current = next_key
    return result


def _footprint_instance_location(
    payload: BRDLayout, footprint_instance: BRDFootprintInstance
) -> SemanticPoint | None:
    x = _raw_coord_to_semantic(payload, footprint_instance.x_raw)
    y = _raw_coord_to_semantic(payload, footprint_instance.y_raw)
    if x is None or y is None:
        return None
    return SemanticPoint(x=x, y=y)


def _footprint_instance_rotation_degrees(
    footprint_instance: BRDFootprintInstance,
) -> float:
    rotation = float(footprint_instance.rotation_mdeg or 0) / 1000.0
    if footprint_instance.layer != 0:
        rotation = 180.0 - rotation
    return rotation


def _text_values_by_key(texts: Iterable[BRDText]) -> dict[int, str]:
    result: dict[int, str] = {}
    direct: dict[int, str] = {}
    wrappers: list[BRDText] = []
    for text in texts:
        if text.text:
            direct[text.key] = text.text
            result[text.key] = text.text
            if text.string_graphic_key:
                result[text.string_graphic_key] = text.text
        else:
            wrappers.append(text)

    for text in wrappers:
        if not text.string_graphic_key:
            continue
        value = direct.get(text.string_graphic_key)
        if value:
            result[text.key] = value
    return result


def _is_footprint_instance_block(block: BRDBlockSummary) -> bool:
    return (
        block.block_type == FOOTPRINT_INSTANCE_BLOCK
        and block.key is not None
        and block.next is not None
    )


def _shape_id(
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[object, ...]], str],
    *,
    kind: str,
    auroradb_type: str,
    values: list[float | int | str],
    source_path: str,
    source_key: object,
) -> str:
    key = (auroradb_type, tuple(_shape_key_value(value) for value in values))
    existing = shape_ids_by_key.get(key)
    if existing is not None:
        return existing
    shape_id = semantic_id("shape", f"{auroradb_type}_{len(shapes)}")
    shape_ids_by_key[key] = shape_id
    shapes.append(
        SemanticShape(
            id=shape_id,
            kind=kind,
            auroradb_type=auroradb_type,
            values=values,
            source=source_ref("brd", source_path, source_key),
        )
    )
    return shape_id


def _shape_key_value(value: float | int | str) -> object:
    if isinstance(value, str):
        return value
    return round(float(value), 9)


def _bbox_points(payload: BRDLayout, coords_raw: list[int]) -> tuple[float, ...] | None:
    if len(coords_raw) < 4:
        return None
    values = [_raw_coord_to_semantic(payload, value) for value in coords_raw[:4]]
    if any(value is None for value in values):
        return None
    x0, y0, x1, y1 = [float(value) for value in values]
    if x0 == x1 or y0 == y1:
        return None
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def _average_point(points: Iterable[SemanticPoint]) -> SemanticPoint:
    x_total = 0.0
    y_total = 0.0
    count = 0
    for point in points:
        x_total += point.x
        y_total += point.y
        count += 1
    if count == 0:
        return SemanticPoint(x=0.0, y=0.0)
    return SemanticPoint(x=x_total / count, y=y_total / count)


def _raw_coord_to_semantic(
    payload: BRDLayout, value: int | float | None
) -> float | None:
    if value is None:
        return None
    unit = payload.header.board_units.casefold()
    if unit in {"millimeters", "millimeter", "mm"}:
        divisor = payload.header.units_divisor or 10_000
        return float(value) / divisor
    if unit in {"mils", "mil"}:
        divisor = payload.header.units_divisor or 1
        return float(value) / divisor * 0.0254
    scale_nm = payload.header.coordinate_scale_nm
    if scale_nm is not None and scale_nm > 0:
        return float(value) * scale_nm / 1_000_000.0
    return float(value) * BRD_UNKNOWN_MM_PER_RAW


def _raw_length_to_semantic(
    payload: BRDLayout, value: int | float | None
) -> float | None:
    if value is None:
        return None
    return abs(_raw_coord_to_semantic(payload, value) or 0.0)


def _raw_point_to_semantic(
    payload: BRDLayout, values: list[int | float] | tuple[int | float, ...] | None
) -> list[float] | None:
    if values is None or len(values) < 2:
        return None
    x = _raw_coord_to_semantic(payload, values[0])
    y = _raw_coord_to_semantic(payload, values[1])
    if x is None or y is None:
        return None
    return [x, y]


def _semantic_units(payload: BRDLayout) -> str:
    _ = payload
    return "mm"
