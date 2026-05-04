from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any

from aurora_translator.sources.auroradb.block import AuroraBlock, AuroraItem
from aurora_translator.sources.auroradb.models import AuroraDBPackage
from aurora_translator.targets.auroradb.names import _auroradb_net_name, _tuple_value
from aurora_translator.semantic.models import SemanticPad, SemanticPin, SemanticShape


@dataclass(slots=True)
class _TraceShape:
    shape_id: str
    width_mil: float


@dataclass(slots=True)
class _TracePoint:
    x: float = 0.0
    y: float = 0.0
    is_arc: bool = False
    arc_height: float = 0.0


@dataclass(slots=True)
class _AedbPinFeature:
    x: float
    y: float
    rotation: float = 0.0


@dataclass(slots=True)
class _AedbComponentPlacement:
    export_part_name: str
    footprint_name: str
    rotation: float
    flip_x: bool = False
    flip_y: bool = False


@dataclass(slots=True)
class _AedbPartVariant:
    export_part_name: str
    footprint_name: str
    representative_component_id: str
    canonical_rotation: float
    pin_features: dict[str, _AedbPinFeature]


@dataclass(slots=True)
class _AedbExportPlan:
    placements_by_component_id: dict[str, _AedbComponentPlacement]
    variants: list[_AedbPartVariant]


@dataclass(slots=True)
class _PartExportVariant:
    export_part_name: str
    source_part_name: str
    footprint_name: str
    representative_component_id: str
    component_ids: list[str]
    source_footprint_name: str | None = None


@dataclass(slots=True)
class _PartExportPlan:
    part_names_by_component_id: dict[str, str]
    variants: list[_PartExportVariant]


@dataclass(slots=True)
class _DirectPartIndexes:
    pads_by_id: dict[str, SemanticPad]
    pins_by_id: dict[str, SemanticPin]
    shapes_by_id: dict[str, SemanticShape]
    footprints_by_name: dict[str, Any]


@dataclass(slots=True)
class _SelectedFootprintPad:
    pin_name: str
    pad: SemanticPad
    semantic_shape_id: str


@dataclass(slots=True)
class _DirectLayerState:
    name: str
    layer_type: str
    layer_id: int
    components: AuroraBlock | None = None
    logic_layers: dict[str, AuroraBlock] = field(default_factory=dict)
    net_geometry: AuroraBlock = field(
        default_factory=lambda: AuroraBlock("NetGeometry")
    )
    net_geometry_by_name: dict[str, AuroraBlock] = field(default_factory=dict)

    def to_block(self) -> AuroraBlock:
        block = AuroraBlock("MetalLayer")
        block.add_item("Type", self.layer_type)
        block.add_item("NameID", [self.name, self.layer_id])
        if self.components is not None:
            block.append(self.components)
        for logic_layer in self.logic_layers.values():
            block.append(logic_layer)
        block.append(self.net_geometry)
        return block


class _DirectLayoutBuilder:
    def __init__(self) -> None:
        self.units = "mils"
        self.outline: AuroraBlock | AuroraItem | None = None
        self.shape_list = AuroraBlock("ShapeList")
        self.via_list = AuroraBlock("ViaList")
        self.nets = AuroraBlock("Nets")
        self.layers: dict[str, _DirectLayerState] = {}
        self.layers_by_key: dict[str, _DirectLayerState] = {}
        self.layer_name_ids: dict[str, int] = {}
        self.layer_name_ids_by_key: dict[str, int] = {}
        self.component_layers_by_key: dict[str, _DirectLayerState] = {}
        self.nets_by_key: dict[str, AuroraBlock] = {}
        self.net_pins_by_key: dict[str, AuroraBlock] = {}
        self.net_vias_by_key: dict[str, AuroraBlock] = {}
        self.next_layer_id = 0

    def add_layer_id(self, name: str) -> int:
        key = name.casefold()
        existing = self.layer_name_ids_by_key.get(key)
        if existing is not None:
            return existing
        layer_id = self.next_layer_id
        self.layer_name_ids[name] = layer_id
        self.layer_name_ids_by_key[key] = layer_id
        self.next_layer_id += 1
        return layer_id

    def add_metal_layer(self, name: str, layer_type: str) -> _DirectLayerState:
        if not name:
            name = f"Layer_{len(self.layers)}"
        key = name.casefold()
        existing = self.layers_by_key.get(key)
        if existing is not None:
            return existing
        state = _DirectLayerState(
            name=name,
            layer_type=layer_type or "Signal",
            layer_id=self.add_layer_id(name),
        )
        self.layers[name] = state
        self.layers_by_key[key] = state
        return state

    def get_layer(self, name: str) -> _DirectLayerState:
        if name:
            existing = self.layers_by_key.get(name.casefold())
            if existing is not None:
                return existing
        return self.add_metal_layer(name or f"Layer_{len(self.layers)}", "Signal")

    def add_component_layer(self, component_layer: str, metal_layer: str) -> None:
        layer = self.get_layer(metal_layer)
        layer_id = self.add_layer_id(component_layer)
        block = AuroraBlock("Components")
        block.add_item("Type", "Component")
        block.add_item("NameID", [component_layer, layer_id])
        layer.components = block
        self.component_layers_by_key[component_layer.casefold()] = layer

    def find_layer_by_component_layer(
        self, component_layer_name: str
    ) -> _DirectLayerState:
        existing = self.component_layers_by_key.get(component_layer_name.casefold())
        if existing is not None:
            return existing
        return self.get_layer(
            component_layer_name.replace("COMP_", "") if component_layer_name else ""
        )

    def find_or_create_net(self, net_name: str) -> AuroraBlock:
        normalized = _auroradb_net_name(net_name)
        key = normalized.casefold()
        block = self.nets_by_key.get(key)
        if block is None:
            block = AuroraBlock(normalized)
            self.nets.append(block)
            self.nets_by_key[key] = block
        return block

    def add_net_pin(self, net_name: str, values: list[str]) -> None:
        net = self.find_or_create_net(net_name)
        net_key = _auroradb_net_name(net_name).casefold()
        pins = self.net_pins_by_key.get(net_key)
        if pins is None:
            pins = net.add_block("NetPins")
            self.net_pins_by_key[net_key] = pins
        pins.add_item("Pin", values)

    def add_net_via(self, net_name: str, values: list[str]) -> None:
        net = self.find_or_create_net(net_name)
        net_key = _auroradb_net_name(net_name).casefold()
        vias = self.net_vias_by_key.get(net_key)
        if vias is None:
            vias = net.add_block("NetVias")
            self.net_vias_by_key[net_key] = vias
        vias.add_item("Via", values)

    def add_net_geometry(
        self, net_name: str, layer_name: str, geom_block: AuroraBlock
    ) -> None:
        layer = self.get_layer(layer_name)
        normalized_net = _auroradb_net_name(net_name)
        net_key = normalized_net.casefold()
        net_block = layer.net_geometry_by_name.get(net_key)
        if net_block is None:
            net_block = AuroraBlock(normalized_net)
            layer.net_geometry.append(net_block)
            layer.net_geometry_by_name[net_key] = net_block
        net_block.append(geom_block)

    def package(
        self,
        *,
        parts: AuroraBlock | None,
        root: Path | None,
        diagnostics: list[str] | None = None,
    ) -> AuroraDBPackage:
        return AuroraDBPackage(
            root=root,
            layout=self._layout_block(),
            parts=parts,
            layers={name: state.to_block() for name, state in self.layers.items()},
            diagnostics=list(diagnostics or []),
        )

    def _layout_block(self) -> AuroraBlock:
        layout = AuroraBlock("CeLayout")
        layout.add_item("Units", self.units)
        if self.outline is not None:
            layout.append(self.outline)
        else:
            outline = AuroraBlock("Outline")
            outline.add_item("Solid", "Y")
            outline.add_item("CCW", "Y")
            layout.append(outline)

        symbols = AuroraBlock("GeomSymbols")
        symbols.append(self.shape_list)
        symbols.append(self.via_list)
        layout.append(symbols)
        layout.append(self.nets)

        stack = AuroraBlock("LayerStackup")
        stack.add_item("MetalLayers", list(self.layers.keys()))
        stack.add_item("NextLayerID", self.next_layer_id)
        layer_pairs: list[str] = []
        for name, layer_id in sorted(
            self.layer_name_ids.items(), key=lambda item: item[1]
        ):
            layer_pairs.extend([name, str(layer_id)])
        stack.add_item("LayerNameIDs", layer_pairs)
        layout.append(stack)
        return layout


class _DirectPartsBuilder:
    def __init__(self) -> None:
        self.part_list = AuroraBlock("PartList")
        self.symbol_list = AuroraBlock("SymbolList")
        self.footprint_list = AuroraBlock("FootprintList")
        self.parts_by_name: dict[str, AuroraBlock] = {}
        self.footprints_by_name: dict[str, AuroraBlock] = {}

    def find_or_create_part(self, part_name: str) -> AuroraBlock:
        key = part_name.casefold()
        part = self.parts_by_name.get(key)
        if part is not None:
            return part
        part = AuroraBlock("Part")
        info = part.add_block("PartInfo")
        info.add_item("Name", part_name)
        info.add_item("Vendor", "Unknown")
        info.add_item("Type", "")
        info.add_item("Description", "")
        info.add_item("Attributes", [])
        part.append(AuroraBlock("PinList"))
        self.part_list.append(part)
        self.parts_by_name[key] = part
        return part

    def find_or_create_footprint(self, footprint_name: str) -> AuroraBlock:
        key = footprint_name.casefold()
        footprint = self.footprints_by_name.get(key)
        if footprint is not None:
            return footprint
        footprint = AuroraBlock("FootPrintSymbol")
        footprint.add_item("SymbolID", footprint_name)
        self.footprint_list.append(footprint)
        self.footprints_by_name[key] = footprint
        return footprint

    def find_or_create_pad_template(
        self, footprint: AuroraBlock, pad_id: str
    ) -> AuroraBlock:
        for child in footprint.iter_blocks():
            if child.name.casefold() != "padtemplate":
                continue
            template_item = child.get_item("TemplateID")
            if (
                template_item
                and template_item.values
                and template_item.values[0].casefold() == pad_id.casefold()
            ):
                return child
        pad_template = AuroraBlock("PadTemplate")
        pad_template.add_item("TemplateID", pad_id)
        pad_template.add_block("GeometryList")
        _direct_insert_before_first_named_block(
            footprint, pad_template, {"MetalLayer", "DrillHole", "Outline"}
        )
        return pad_template

    def find_or_create_footprint_metal_layer(
        self, footprint: AuroraBlock, layer_name: str, layer_position: str
    ) -> AuroraBlock:
        for child in footprint.iter_blocks():
            if child.name.casefold() != "metallayer":
                continue
            name_type = child.get_item("NameType")
            if (
                name_type
                and len(name_type.values) >= 2
                and name_type.values[0].casefold() == layer_name.casefold()
                and name_type.values[1].casefold() == layer_position.casefold()
            ):
                return child
        metal_layer = AuroraBlock("MetalLayer")
        metal_layer.add_item("NameType", [layer_name, layer_position])
        footprint.append(metal_layer)
        return metal_layer

    def block(self) -> AuroraBlock:
        parts = AuroraBlock("CeParts")
        parts.append(self.part_list)
        if self.symbol_list.children:
            parts.append(self.symbol_list)
        if self.footprint_list.children:
            parts.append(self.footprint_list)
        return parts


def _direct_attribute_values(attributes: dict[str, str]) -> list[str]:
    return [
        f"{_tuple_value(key)}={_tuple_value(value)}"
        for key, value in sorted(attributes.items())
    ]


def _direct_replace_item_before_block(
    block: AuroraBlock, item_name: str, values: list[str], before_block: str
) -> None:
    lowered_item = item_name.casefold()
    block.children = [
        child
        for child in block.children
        if not (isinstance(child, AuroraItem) and child.name.casefold() == lowered_item)
    ]
    item = AuroraItem(item_name, values)
    before_lowered = before_block.casefold()
    for index, child in enumerate(block.children):
        if isinstance(child, AuroraBlock) and child.name.casefold() == before_lowered:
            block.children.insert(index, item)
            return
    block.append(item)


def _direct_insert_before_first_named_block(
    block: AuroraBlock, node: AuroraBlock, before_names: set[str]
) -> None:
    lowered_names = {name.casefold() for name in before_names}
    for index, child in enumerate(block.children):
        if isinstance(child, AuroraBlock) and child.name.casefold() in lowered_names:
            block.children.insert(index, node)
            return
    block.append(node)
