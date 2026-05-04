from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field as ModelField

from aurora_translator.shared.logging import log_timing
from aurora_translator.sources.auroradb.block import split_reserved, strip_wrapping_pair
from aurora_translator.version import PROJECT_VERSION

from .block import AuroraBlock, AuroraItem, AuroraNode, AuroraRawBlock
from .version import AURORADB_JSON_SCHEMA_VERSION, AURORADB_PARSER_VERSION


logger = logging.getLogger("aurora_translator.auroradb")


class SchemaModel(BaseModel):
    """Base model for serialized AuroraDB structures."""

    model_config = ConfigDict(extra="forbid")


class AuroraDBMetadata(SchemaModel):
    project_version: str = ModelField(
        default=PROJECT_VERSION,
        description="Aurora Translator project version that produced this AuroraDB payload.",
    )
    parser_version: str = ModelField(
        default=AURORADB_PARSER_VERSION,
        description="AuroraDB parser version that produced this payload.",
    )
    output_schema_version: str = ModelField(
        default=AURORADB_JSON_SCHEMA_VERSION,
        description="AuroraDB JSON schema version for this payload.",
    )

    def to_dict(self) -> dict[str, str]:
        return self.model_dump(mode="json")


class AuroraStoredNodeModel(SchemaModel):
    kind: Literal["block", "item"] = ModelField(
        ..., description="Original AuroraDB node kind."
    )
    name: str = ModelField(..., description="Original block or item name.")
    values: list[str] = ModelField(
        default_factory=list, description="Item values. Empty for block nodes."
    )
    children: list["AuroraStoredNodeModel"] = ModelField(
        default_factory=list,
        description="Child nodes. Empty for item nodes.",
    )


class AuroraLocationModel(SchemaModel):
    x: float | None = ModelField(default=None, description="X coordinate.")
    y: float | None = ModelField(default=None, description="Y coordinate.")
    ccw: bool | None = ModelField(
        default=None, description="Whether rotation is counter-clockwise."
    )
    rotation: float | None = ModelField(default=None, description="Rotation angle.")
    scale: float | None = ModelField(default=None, description="Scale factor.")
    flip_x: bool | None = ModelField(
        default=None, description="Whether X mirror is enabled."
    )
    flip_y: bool | None = ModelField(
        default=None, description="Whether Y mirror is enabled."
    )
    raw: list[str] = ModelField(
        default_factory=list, description="Original AuroraDB location values."
    )


class AuroraAttributeModel(SchemaModel):
    name: str = ModelField(..., description="Attribute name.")
    value: str = ModelField(default="", description="Attribute value.")


class AuroraLayerStackupModel(SchemaModel):
    metal_layers: list[str] = ModelField(
        default_factory=list, description="Metal layer names in stack order."
    )
    next_layer_id: int | None = ModelField(
        default=None, description="Next layer id recorded by AuroraDB."
    )
    layer_name_ids: dict[str, int] = ModelField(
        default_factory=dict, description="Layer name to layer id map."
    )


class AuroraShapeSymbolModel(SchemaModel):
    id: str = ModelField(..., description="Shape id.")
    name: str = ModelField(..., description="Shape symbol name.")
    geometry: AuroraStoredNodeModel | None = ModelField(
        default=None, description="Shape geometry node."
    )


class AuroraViaLayerPadModel(SchemaModel):
    layer_name: str = ModelField(..., description="Layer name.")
    pad_shape_id: str | None = ModelField(default=None, description="Pad shape id.")
    pad_rotation: str | None = ModelField(
        default=None, description="Pad rotation value."
    )
    pad_ccw: bool | None = ModelField(
        default=None, description="Pad counter-clockwise flag."
    )
    antipad_shape_id: str | None = ModelField(
        default=None, description="Anti-pad shape id."
    )
    antipad_rotation: str | None = ModelField(
        default=None, description="Anti-pad rotation value."
    )
    antipad_ccw: bool | None = ModelField(
        default=None, description="Anti-pad counter-clockwise flag."
    )
    raw: list[str] = ModelField(
        default_factory=list, description="Original via layer values."
    )


class AuroraViaTemplateModel(SchemaModel):
    id: str = ModelField(..., description="Via template id.")
    name: str | None = ModelField(default=None, description="Via template name.")
    barrel: list[str] = ModelField(
        default_factory=list, description="Barrel shape data."
    )
    layer_pads: list[AuroraViaLayerPadModel] = ModelField(
        default_factory=list, description="Layer pad stack data."
    )


class AuroraNetPinModel(SchemaModel):
    component_layer: str | None = ModelField(
        default=None, description="Component layer name."
    )
    component: str | None = ModelField(
        default=None, description="Component reference designator."
    )
    pin: str | None = ModelField(default=None, description="Component pin id.")
    metal_layer: str | None = ModelField(
        default=None, description="Explicit metal layer name."
    )
    raw: list[str] = ModelField(
        default_factory=list, description="Original NetPins/Pin values."
    )


class AuroraNetViaModel(SchemaModel):
    via_id: str | None = ModelField(default=None, description="Via template id.")
    location: AuroraLocationModel | None = ModelField(
        default=None, description="Via placement location."
    )
    raw: list[str] = ModelField(
        default_factory=list, description="Original NetVias/Via values."
    )


class AuroraNetModel(SchemaModel):
    name: str = ModelField(..., description="Net name.")
    type: str | None = ModelField(default=None, description="Net type.")
    voltage: str | None = ModelField(default=None, description="Net voltage value.")
    pins: list[AuroraNetPinModel] = ModelField(
        default_factory=list, description="Pins connected to this net."
    )
    vias: list[AuroraNetViaModel] = ModelField(
        default_factory=list, description="Vias connected to this net."
    )


class AuroraGeometryReferenceModel(SchemaModel):
    symbol_id: str | None = ModelField(
        default=None, description="Referenced geometry symbol id."
    )
    location: AuroraLocationModel | None = ModelField(
        default=None, description="Reference placement location."
    )
    geometry: AuroraStoredNodeModel | None = ModelField(
        default=None, description="Inline geometry node."
    )
    raw: AuroraStoredNodeModel = ModelField(
        ..., description="Original geometry reference block."
    )


class AuroraComponentModel(SchemaModel):
    name: str = ModelField(..., description="Component instance name.")
    part_name: str | None = ModelField(
        default=None, description="Referenced part name."
    )
    component_layer: str | None = ModelField(
        default=None, description="Component layer name."
    )
    location: AuroraLocationModel | None = ModelField(
        default=None, description="Component placement location."
    )
    value: str | None = ModelField(default=None, description="Component value string.")
    raw: list[str] = ModelField(
        default_factory=list, description="Original component item values."
    )


class AuroraLogicLayerModel(SchemaModel):
    name: str | None = ModelField(default=None, description="Logic layer name.")
    id: int | None = ModelField(default=None, description="Logic layer id.")
    type: str | None = ModelField(default=None, description="Logic layer type.")
    geometries: list[AuroraGeometryReferenceModel] = ModelField(
        default_factory=list, description="Layer geometries."
    )
    part_pads: list["AuroraPartPadModel"] = ModelField(
        default_factory=list, description="Footprint pads on this logic layer."
    )
    raw: AuroraStoredNodeModel | None = ModelField(
        default=None, description="Original logic layer block."
    )


class AuroraNetGeometryModel(SchemaModel):
    net_name: str = ModelField(..., description="Net name.")
    geometries: list[AuroraGeometryReferenceModel] = ModelField(
        default_factory=list, description="Net geometries on the layer."
    )


class AuroraMetalLayerModel(SchemaModel):
    name: str = ModelField(..., description="Metal layer name.")
    id: int | None = ModelField(default=None, description="Metal layer id.")
    type: str | None = ModelField(default=None, description="Metal layer type.")
    components: list[AuroraComponentModel] = ModelField(
        default_factory=list, description="Component instances on this layer."
    )
    logic_layers: list[AuroraLogicLayerModel] = ModelField(
        default_factory=list, description="Logic layers attached to this metal layer."
    )
    net_geometries: list[AuroraNetGeometryModel] = ModelField(
        default_factory=list, description="Net geometries grouped by net."
    )
    raw: AuroraStoredNodeModel | None = ModelField(
        default=None, description="Original metal layer block."
    )


class AuroraPartInfoModel(SchemaModel):
    name: str = ModelField(..., description="Part name.")
    vendor: str | None = ModelField(default=None, description="Vendor name.")
    type: str | None = ModelField(default=None, description="Part type.")
    description: str | None = ModelField(default=None, description="Part description.")
    attributes: list[AuroraAttributeModel] = ModelField(
        default_factory=list, description="Part attributes."
    )


class AuroraSymbolPinMapModel(SchemaModel):
    symbol_group: str = ModelField(..., description="Symbol group id.")
    symbol_identifier: str = ModelField(..., description="Symbol identifier id.")
    symbol_pin: str = ModelField(..., description="Symbol pin number.")


class AuroraFootprintPadMapModel(SchemaModel):
    footprint: str = ModelField(..., description="Footprint symbol id.")
    pad_id: str = ModelField(..., description="Footprint pad id.")


class AuroraPartPinModel(SchemaModel):
    number: str | None = ModelField(default=None, description="Pin number.")
    name: str | None = ModelField(default=None, description="Pin name.")
    type: str | None = ModelField(default=None, description="Pin mount/type string.")
    swap_group: str | None = ModelField(default=None, description="Pin swap group.")
    symbol_pin_map: list[AuroraSymbolPinMapModel] = ModelField(
        default_factory=list, description="Schematic symbol pin mappings."
    )
    footprint_pad_map: list[AuroraFootprintPadMapModel] = ModelField(
        default_factory=list, description="Footprint pad mappings."
    )
    raw_def_data: str | None = ModelField(
        default=None, description="Original DefData string."
    )


class AuroraPartModel(SchemaModel):
    info: AuroraPartInfoModel = ModelField(..., description="PartInfo block.")
    footprint_symbols: list[str] = ModelField(
        default_factory=list, description="Referenced footprint symbols."
    )
    symbol_groups: list[list[str]] = ModelField(
        default_factory=list, description="Symbol group data rows."
    )
    pins: list[AuroraPartPinModel] = ModelField(
        default_factory=list, description="Part pins."
    )
    raw: AuroraStoredNodeModel | None = ModelField(
        default=None, description="Original Part block."
    )


class AuroraSymbolPinTemplateModel(SchemaModel):
    id: str = ModelField(..., description="Symbol pin template id.")
    geometries: list[AuroraStoredNodeModel] = ModelField(
        default_factory=list, description="Template geometries."
    )


class AuroraSymbolPinModel(SchemaModel):
    number: str | None = ModelField(default=None, description="Symbol pin number.")
    template_id: str | None = ModelField(
        default=None, description="Referenced symbol pin template id."
    )
    location: AuroraLocationModel | None = ModelField(
        default=None, description="Symbol pin location."
    )
    raw: list[str] = ModelField(
        default_factory=list, description="Original SymbolPin values."
    )


class AuroraSchematicSymbolModel(SchemaModel):
    symbol_id: str = ModelField(..., description="Schematic symbol id.")
    pin_templates: list[AuroraSymbolPinTemplateModel] = ModelField(
        default_factory=list, description="Pin templates."
    )
    pins: list[AuroraSymbolPinModel] = ModelField(
        default_factory=list, description="Symbol pins."
    )
    geometries: list[AuroraStoredNodeModel] = ModelField(
        default_factory=list, description="Symbol body geometries."
    )
    raw: AuroraStoredNodeModel | None = ModelField(
        default=None, description="Original SchematicSymbol block."
    )


class AuroraPadTemplateModel(SchemaModel):
    template_id: str = ModelField(..., description="Footprint pad template id.")
    geometries: list[AuroraStoredNodeModel] = ModelField(
        default_factory=list, description="Pad template geometries."
    )


class AuroraPartPadModel(SchemaModel):
    pad_id: str | None = ModelField(default=None, description="Pad id.")
    template_id: str | None = ModelField(
        default=None, description="Referenced pad template id."
    )
    location: AuroraLocationModel | None = ModelField(
        default=None, description="Pad placement location."
    )
    raw: AuroraStoredNodeModel | None = ModelField(
        default=None, description="Original PartPad block."
    )


class AuroraFootprintMetalLayerModel(SchemaModel):
    name: str | None = ModelField(default=None, description="Footprint layer name.")
    position: str | None = ModelField(
        default=None, description="Footprint layer position, for example top or bottom."
    )
    geometries: list[AuroraStoredNodeModel] = ModelField(
        default_factory=list, description="Metal-layer geometries."
    )
    part_pads: list[AuroraPartPadModel] = ModelField(
        default_factory=list, description="Footprint pads on this metal layer."
    )
    logic_layers: list[AuroraLogicLayerModel] = ModelField(
        default_factory=list,
        description="Logic layers under this footprint metal layer.",
    )
    raw: AuroraStoredNodeModel | None = ModelField(
        default=None, description="Original footprint MetalLayer block."
    )


class AuroraFootprintSymbolModel(SchemaModel):
    symbol_id: str = ModelField(..., description="Footprint symbol id.")
    pad_templates: list[AuroraPadTemplateModel] = ModelField(
        default_factory=list, description="Pad templates."
    )
    metal_layers: list[AuroraFootprintMetalLayerModel] = ModelField(
        default_factory=list, description="Footprint metal layers."
    )
    drill_holes: list[AuroraStoredNodeModel] = ModelField(
        default_factory=list, description="DrillHole blocks."
    )
    outline_geometry_type: str | None = ModelField(
        default=None, description="Outline geometry type."
    )
    outline: AuroraStoredNodeModel | None = ModelField(
        default=None, description="Outline geometry block."
    )
    raw: AuroraStoredNodeModel | None = ModelField(
        default=None, description="Original FootPrintSymbol block."
    )


class AuroraPartsModel(SchemaModel):
    parts: list[AuroraPartModel] = ModelField(
        default_factory=list, description="PartList contents."
    )
    schematic_symbols: list[AuroraSchematicSymbolModel] = ModelField(
        default_factory=list, description="SymbolList contents."
    )
    footprints: list[AuroraFootprintSymbolModel] = ModelField(
        default_factory=list, description="FootprintList contents."
    )


class AuroraLayoutModel(SchemaModel):
    units: str | None = ModelField(default=None, description="Layout units.")
    outline: AuroraStoredNodeModel | None = ModelField(
        default=None, description="Board outline block."
    )
    layer_stackup: AuroraLayerStackupModel | None = ModelField(
        default=None, description="Layer stackup data."
    )
    shapes: list[AuroraShapeSymbolModel] = ModelField(
        default_factory=list, description="Geometry shape symbols."
    )
    via_templates: list[AuroraViaTemplateModel] = ModelField(
        default_factory=list, description="Via templates."
    )
    nets: list[AuroraNetModel] = ModelField(
        default_factory=list, description="Nets defined in layout.db."
    )


class AuroraDBSummaryModel(SchemaModel):
    has_layout: bool = ModelField(..., description="Whether layout.db was read.")
    has_parts: bool = ModelField(..., description="Whether parts.db was read.")
    units: str | None = ModelField(default=None, description="Layout units.")
    metal_layer_count: int = ModelField(..., description="Metal layer count.")
    layer_count: int = ModelField(..., description="Layer id count.")
    logic_layer_count: int = ModelField(..., description="Logic layer count.")
    component_count: int = ModelField(..., description="Component count.")
    net_count: int = ModelField(..., description="Net count.")
    net_pin_count: int = ModelField(..., description="Net pin binding count.")
    net_via_count: int = ModelField(..., description="Net via binding count.")
    net_geometry_count: int = ModelField(..., description="Net geometry count.")
    shape_count: int = ModelField(..., description="Shape symbol count.")
    via_template_count: int = ModelField(..., description="Via template count.")
    part_count: int = ModelField(..., description="Part count.")
    symbol_count: int = ModelField(..., description="Schematic symbol count.")
    footprint_count: int = ModelField(..., description="Footprint symbol count.")
    layer_names: list[str] = ModelField(
        default_factory=list, description="Metal layer names."
    )
    net_names: list[str] = ModelField(default_factory=list, description="Net names.")
    part_names: list[str] = ModelField(default_factory=list, description="Part names.")


class AuroraRawBlocksModel(SchemaModel):
    layout: AuroraStoredNodeModel | None = ModelField(
        default=None, description="Raw CeLayout block tree."
    )
    parts: AuroraStoredNodeModel | None = ModelField(
        default=None, description="Raw CeParts block tree."
    )
    layers: dict[str, AuroraStoredNodeModel] = ModelField(
        default_factory=dict, description="Raw MetalLayer block trees."
    )


class AuroraDBModel(SchemaModel):
    """Structured, AEDB-model-style view of directly stored AuroraDB data."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"https://aurora-translator.local/schemas/auroradb-{AURORADB_JSON_SCHEMA_VERSION}.json",
        },
    )

    metadata: AuroraDBMetadata = ModelField(..., description="Version metadata.")
    root: str | None = ModelField(default=None, description="AuroraDB directory path.")
    summary: AuroraDBSummaryModel = ModelField(
        ..., description="High-level AuroraDB summary."
    )
    layout: AuroraLayoutModel | None = ModelField(
        default=None, description="Structured layout.db contents."
    )
    layers: list[AuroraMetalLayerModel] = ModelField(
        default_factory=list, description="Structured layer file contents."
    )
    parts: AuroraPartsModel | None = ModelField(
        default=None, description="Structured parts.db contents."
    )
    diagnostics: list[str] = ModelField(
        default_factory=list, description="Non-fatal diagnostics."
    )
    raw_blocks: AuroraRawBlocksModel | None = ModelField(
        default=None, description="Optional raw block tree payload."
    )


@dataclass(slots=True)
class AuroraDBPackage:
    root: Path | None = None
    layout: AuroraBlock | None = None
    parts: AuroraBlock | None = None
    layers: dict[str, AuroraBlock] = field(default_factory=dict)
    diagnostics: list[str] = field(default_factory=list)

    def summary(self) -> "AuroraDBSummary":
        return summarize_package(self)

    def to_model(self, *, include_raw_blocks: bool = False) -> AuroraDBModel:
        return build_auroradb_model(self, include_raw_blocks=include_raw_blocks)

    def to_model_dict(self, *, include_raw_blocks: bool = False) -> dict[str, object]:
        return self.to_model(include_raw_blocks=include_raw_blocks).model_dump(
            mode="json"
        )

    def to_dict(self, include_blocks: bool = True) -> dict[str, object]:
        summary = self.summary().to_dict()
        payload: dict[str, object] = {
            "metadata": AuroraDBMetadata().to_dict(),
            "root": str(self.root) if self.root else None,
            "summary": summary,
            "diagnostics": list(self.diagnostics),
        }
        if include_blocks:
            payload["layout"] = self.layout.to_dict() if self.layout else None
            payload["parts"] = self.parts.to_dict() if self.parts else None
            payload["layers"] = {
                name: block.to_dict() for name, block in self.layers.items()
            }
        return payload


@dataclass(slots=True)
class AuroraDBSummary:
    has_layout: bool = False
    has_parts: bool = False
    units: str | None = None
    metal_layer_count: int = 0
    layer_count: int = 0
    logic_layer_count: int = 0
    component_count: int = 0
    net_count: int = 0
    net_pin_count: int = 0
    net_via_count: int = 0
    net_geometry_count: int = 0
    shape_count: int = 0
    via_template_count: int = 0
    part_count: int = 0
    symbol_count: int = 0
    footprint_count: int = 0
    layer_names: list[str] = field(default_factory=list)
    net_names: list[str] = field(default_factory=list)
    part_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "has_layout": self.has_layout,
            "has_parts": self.has_parts,
            "units": self.units,
            "metal_layer_count": self.metal_layer_count,
            "layer_count": self.layer_count,
            "logic_layer_count": self.logic_layer_count,
            "component_count": self.component_count,
            "net_count": self.net_count,
            "net_pin_count": self.net_pin_count,
            "net_via_count": self.net_via_count,
            "net_geometry_count": self.net_geometry_count,
            "shape_count": self.shape_count,
            "via_template_count": self.via_template_count,
            "part_count": self.part_count,
            "symbol_count": self.symbol_count,
            "footprint_count": self.footprint_count,
            "layer_names": list(self.layer_names),
            "net_names": list(self.net_names),
            "part_names": list(self.part_names),
        }


def summarize_package(package: AuroraDBPackage) -> AuroraDBSummary:
    summary = AuroraDBSummary(
        has_layout=package.layout is not None,
        has_parts=package.parts is not None,
    )
    if package.layout is not None:
        _summarize_layout(summary, package.layout, package.layers)
    if package.parts is not None:
        _summarize_parts(summary, package.parts)
    return summary


def _summarize_layout(
    summary: AuroraDBSummary, layout: AuroraBlock, layers: dict[str, AuroraBlock]
) -> None:
    units_item = layout.get_item("Units")
    if units_item and units_item.values:
        summary.units = units_item.values[0]

    layer_stack = layout.get_block("LayerStackup")
    if layer_stack:
        metal_layers = _item_values(layer_stack, "MetalLayers")
        summary.layer_names = metal_layers
        summary.metal_layer_count = len(metal_layers)
        layer_name_ids = _item_values(layer_stack, "LayerNameIDs")
        summary.layer_count = max(len(layer_name_ids) // 2, summary.metal_layer_count)

    nets = layout.get_block("Nets")
    if nets:
        for net_block in nets.iter_blocks():
            summary.net_names.append(net_block.name)
            vias = net_block.get_block("NetVias")
            pins = net_block.get_block("NetPins")
            if vias:
                summary.net_via_count += sum(
                    1 for item in vias.iter_items() if item.name.casefold() == "via"
                )
            if pins:
                summary.net_pin_count += sum(
                    1 for item in pins.iter_items() if item.name.casefold() == "pin"
                )
        summary.net_count = len(summary.net_names)
        summary.net_names.sort(key=str.casefold)

    symbols = layout.get_block("GeomSymbols")
    if symbols:
        shape_list = symbols.get_block("ShapeList")
        via_list = symbols.get_block("ViaList")
        if shape_list:
            summary.shape_count = sum(
                1
                for item in shape_list.iter_items()
                if item.name.casefold() == "idname"
            )
        if via_list:
            summary.via_template_count = sum(1 for _ in via_list.get_blocks("Via"))

    for layer_block in layers.values():
        components = layer_block.get_block("Components")
        if components:
            summary.component_count += sum(
                1
                for item in components.iter_items()
                if item.name.casefold() not in {"type", "nameid"}
            )
        summary.logic_layer_count += len(layer_block.get_blocks("LogicLayer"))
        net_geometry = layer_block.get_block("NetGeometry")
        if net_geometry:
            for net_block in net_geometry.iter_blocks():
                summary.net_geometry_count += len(net_block.get_blocks("NetGeom"))


def _summarize_parts(summary: AuroraDBSummary, parts: AuroraBlock) -> None:
    part_list = parts.get_block("PartList")
    if part_list:
        for part in part_list.get_blocks("Part"):
            info = part.get_block("PartInfo")
            name_values = _item_values(info, "Name") if info else []
            summary.part_names.append(name_values[0] if name_values else "Unknown")
        summary.part_count = len(summary.part_names)
        summary.part_names.sort(key=str.casefold)

    symbol_list = parts.get_block("SymbolList")
    footprint_list = parts.get_block("FootprintList")
    if symbol_list:
        summary.symbol_count = len(list(symbol_list.iter_blocks()))
    if footprint_list:
        summary.footprint_count = len(list(footprint_list.iter_blocks()))


def _item_values(block: AuroraBlock | None, name: str) -> list[str]:
    if block is None:
        return []
    item = block.get_item(name)
    return list(item.values) if item else []


def build_auroradb_model(
    package: AuroraDBPackage, *, include_raw_blocks: bool = False
) -> AuroraDBModel:
    with log_timing(
        logger,
        "build AuroraDB structured model",
        root=package.root,
        include_raw_blocks=include_raw_blocks,
    ):
        model = AuroraDBModel(
            metadata=AuroraDBMetadata(),
            root=str(package.root) if package.root else None,
            summary=AuroraDBSummaryModel.model_validate(package.summary().to_dict()),
            layout=_layout_model(package.layout),
            layers=[
                _metal_layer_model(name, block)
                for name, block in package.layers.items()
            ],
            parts=_parts_model(package.parts),
            diagnostics=list(package.diagnostics),
            raw_blocks=_raw_blocks_model(package) if include_raw_blocks else None,
        )
    logger.info(
        "Built AuroraDB structured model with layers:%s nets:%s components:%s parts:%s shapes:%s vias:%s",
        model.summary.layer_count,
        model.summary.net_count,
        model.summary.component_count,
        model.summary.part_count,
        model.summary.shape_count,
        model.summary.via_template_count,
    )
    return model


def _raw_blocks_model(package: AuroraDBPackage) -> AuroraRawBlocksModel:
    return AuroraRawBlocksModel(
        layout=_node_model(package.layout) if package.layout else None,
        parts=_node_model(package.parts) if package.parts else None,
        layers={name: _node_model(block) for name, block in package.layers.items()},
    )


def _layout_model(layout: AuroraBlock | None) -> AuroraLayoutModel | None:
    if layout is None:
        return None
    symbols = layout.get_block("GeomSymbols")
    shape_list = symbols.get_block("ShapeList") if symbols else None
    via_list = symbols.get_block("ViaList") if symbols else None
    return AuroraLayoutModel(
        units=_first_value(layout, "Units"),
        outline=_node_model(layout.get_block("Outline"))
        if layout.get_block("Outline")
        else None,
        layer_stackup=_layer_stackup_model(layout.get_block("LayerStackup")),
        shapes=_shape_symbol_models(shape_list),
        via_templates=_via_template_models(via_list),
        nets=_net_models(layout.get_block("Nets")),
    )


def _layer_stackup_model(stackup: AuroraBlock | None) -> AuroraLayerStackupModel | None:
    if stackup is None:
        return None
    values = _item_values(stackup, "LayerNameIDs")
    layer_name_ids: dict[str, int] = {}
    for index in range(0, len(values) - 1, 2):
        layer_name_ids[values[index]] = _parse_int(values[index + 1]) or 0
    return AuroraLayerStackupModel(
        metal_layers=_item_values(stackup, "MetalLayers"),
        next_layer_id=_parse_int(_first_value(stackup, "NextLayerID")),
        layer_name_ids=layer_name_ids,
    )


def _shape_symbol_models(
    shape_list: AuroraBlock | None,
) -> list[AuroraShapeSymbolModel]:
    if shape_list is None:
        return []
    shapes: list[AuroraShapeSymbolModel] = []
    children = list(shape_list.children)
    for index, child in enumerate(children):
        if not isinstance(child, AuroraItem) or child.name.casefold() != "idname":
            continue
        values = list(child.values)
        geometry = (
            _node_model(children[index + 1]) if index + 1 < len(children) else None
        )
        shapes.append(
            AuroraShapeSymbolModel(
                id=_value_at(values, 0) or "",
                name=_value_at(values, 1) or "",
                geometry=geometry,
            )
        )
    return shapes


def _via_template_models(via_list: AuroraBlock | None) -> list[AuroraViaTemplateModel]:
    if via_list is None:
        return []
    vias: list[AuroraViaTemplateModel] = []
    for via in via_list.get_blocks("Via"):
        id_name = _item_values(via, "IdName")
        layer_pads: list[AuroraViaLayerPadModel] = []
        for item in via.iter_items():
            if item.name.casefold() in {"idname", "barrel"}:
                continue
            layer_pads.append(
                AuroraViaLayerPadModel(
                    layer_name=item.name,
                    pad_shape_id=_value_at(item.values, 0),
                    pad_rotation=_value_at(item.values, 1),
                    pad_ccw=_parse_bool(_value_at(item.values, 2)),
                    antipad_shape_id=_value_at(item.values, 3),
                    antipad_rotation=_value_at(item.values, 4),
                    antipad_ccw=_parse_bool(_value_at(item.values, 5)),
                    raw=list(item.values),
                )
            )
        vias.append(
            AuroraViaTemplateModel(
                id=_value_at(id_name, 0) or "",
                name=_value_at(id_name, 1),
                barrel=_item_values(via, "Barrel"),
                layer_pads=layer_pads,
            )
        )
    return vias


def _net_models(nets: AuroraBlock | None) -> list[AuroraNetModel]:
    if nets is None:
        return []
    result: list[AuroraNetModel] = []
    for net in nets.iter_blocks():
        pin_block = net.get_block("NetPins")
        via_block = net.get_block("NetVias")
        result.append(
            AuroraNetModel(
                name=net.name,
                type=_first_value(net, "Type"),
                voltage=_first_value(net, "Voltage"),
                pins=_net_pin_models(pin_block),
                vias=_net_via_models(via_block),
            )
        )
    return result


def _net_pin_models(pin_block: AuroraBlock | None) -> list[AuroraNetPinModel]:
    if pin_block is None:
        return []
    pins: list[AuroraNetPinModel] = []
    for item in pin_block.get_items("Pin"):
        values = list(item.values)
        pins.append(
            AuroraNetPinModel(
                component_layer=_value_at(values, 0),
                component=_value_at(values, 1),
                pin=_value_at(values, 2),
                metal_layer=_value_at(values, 3),
                raw=values,
            )
        )
    return pins


def _net_via_models(via_block: AuroraBlock | None) -> list[AuroraNetViaModel]:
    if via_block is None:
        return []
    vias: list[AuroraNetViaModel] = []
    for item in via_block.get_items("Via"):
        values = list(item.values)
        vias.append(
            AuroraNetViaModel(
                via_id=_value_at(values, 0),
                location=_location_model(values[1:]),
                raw=values,
            )
        )
    return vias


def _metal_layer_model(layer_name: str, layer: AuroraBlock) -> AuroraMetalLayerModel:
    name_id = _item_values(layer, "NameID")
    name = _value_at(name_id, 0) or layer_name
    return AuroraMetalLayerModel(
        name=name,
        id=_parse_int(_value_at(name_id, 1)),
        type=_first_value(layer, "Type"),
        components=_component_models(layer.get_block("Components")),
        logic_layers=[
            _logic_layer_model(block) for block in layer.get_blocks("LogicLayer")
        ],
        net_geometries=_net_geometry_models(layer.get_block("NetGeometry")),
        raw=_node_model(layer),
    )


def _component_models(components: AuroraBlock | None) -> list[AuroraComponentModel]:
    if components is None:
        return []
    result: list[AuroraComponentModel] = []
    for item in components.iter_items():
        if item.name.casefold() in {"type", "nameid"}:
            continue
        values = list(item.values)
        result.append(
            AuroraComponentModel(
                name=item.name,
                part_name=_value_at(values, 0),
                component_layer=_value_at(values, 1),
                location=_location_model(values[2:9]),
                value=_value_at(values, 9),
                raw=values,
            )
        )
    return result


def _logic_layer_model(logic: AuroraBlock) -> AuroraLogicLayerModel:
    name_id = _item_values(logic, "NameID")
    return AuroraLogicLayerModel(
        name=_value_at(name_id, 0),
        id=_parse_int(_value_at(name_id, 1)),
        type=_first_value(logic, "Type"),
        geometries=[
            _geometry_reference_model(block) for block in logic.get_blocks("Geometry")
        ],
        part_pads=[_part_pad_model(block) for block in logic.get_blocks("PartPad")],
        raw=_node_model(logic),
    )


def _net_geometry_models(
    net_geometry: AuroraBlock | None,
) -> list[AuroraNetGeometryModel]:
    if net_geometry is None:
        return []
    result: list[AuroraNetGeometryModel] = []
    for net_block in net_geometry.iter_blocks():
        result.append(
            AuroraNetGeometryModel(
                net_name=net_block.name,
                geometries=[
                    _geometry_reference_model(block)
                    for block in net_block.get_blocks("NetGeom")
                ],
            )
        )
    return result


def _geometry_reference_model(block: AuroraBlock) -> AuroraGeometryReferenceModel:
    block = _materialized_block(block)
    geometry: AuroraStoredNodeModel | None = None
    for child in block.children:
        if child.name.casefold() not in {"symbolid", "location"}:
            geometry = _node_model(child)
            break
    return AuroraGeometryReferenceModel(
        symbol_id=_first_value(block, "SymbolID"),
        location=_location_model(_item_values(block, "Location")),
        geometry=geometry,
        raw=_node_model(block),
    )


def _parts_model(parts: AuroraBlock | None) -> AuroraPartsModel | None:
    if parts is None:
        return None
    part_list = parts.get_block("PartList")
    symbol_list = parts.get_block("SymbolList")
    footprint_list = parts.get_block("FootprintList")
    return AuroraPartsModel(
        parts=[_part_model(block) for block in part_list.get_blocks("Part")]
        if part_list
        else [],
        schematic_symbols=[
            _schematic_symbol_model(block)
            for block in symbol_list.get_blocks("SchematicSymbol")
        ]
        if symbol_list
        else [],
        footprints=[
            _footprint_symbol_model(block)
            for block in footprint_list.get_blocks("FootPrintSymbol")
        ]
        if footprint_list
        else [],
    )


def _part_model(part: AuroraBlock) -> AuroraPartModel:
    info = _part_info_model(part.get_block("PartInfo"))
    pins = part.get_block("PinList")
    return AuroraPartModel(
        info=info,
        footprint_symbols=_item_values(part, "FootPrintSymbols"),
        symbol_groups=[list(item.values) for item in part.get_items("SymbolGroup")],
        pins=[_part_pin_model(block) for block in pins.get_blocks("Pin")]
        if pins
        else [],
        raw=_node_model(part),
    )


def _part_info_model(info: AuroraBlock | None) -> AuroraPartInfoModel:
    if info is None:
        return AuroraPartInfoModel(name="Unknown")
    return AuroraPartInfoModel(
        name=_first_value(info, "Name") or "Unknown",
        vendor=_first_value(info, "Vendor"),
        type=_first_value(info, "Type"),
        description=_first_value(info, "Description"),
        attributes=[
            _attribute_model(value) for value in _item_values(info, "Attributes")
        ],
    )


def _part_pin_model(pin: AuroraBlock) -> AuroraPartPinModel:
    raw_def_data = _first_value(pin, "DefData")
    fields = _split_comma_values(raw_def_data or "")
    sym_values = _item_values(pin, "SymPinMap")
    fut_values = _item_values(pin, "FutPadMap")
    return AuroraPartPinModel(
        number=_value_at(fields, 0),
        name=_value_at(fields, 1),
        type=_value_at(fields, 2),
        swap_group=_value_at(fields, 3),
        symbol_pin_map=[
            AuroraSymbolPinMapModel(
                symbol_group=sym_values[index],
                symbol_identifier=sym_values[index + 1],
                symbol_pin=sym_values[index + 2],
            )
            for index in range(0, len(sym_values) - 2, 3)
        ],
        footprint_pad_map=[
            AuroraFootprintPadMapModel(
                footprint=fut_values[index],
                pad_id=fut_values[index + 1],
            )
            for index in range(0, len(fut_values) - 1, 2)
        ],
        raw_def_data=raw_def_data,
    )


def _schematic_symbol_model(symbol: AuroraBlock) -> AuroraSchematicSymbolModel:
    pin_list = symbol.get_block("PinList")
    geometry_list = symbol.get_block("GeometryList") or symbol.get_block("Geometry")
    return AuroraSchematicSymbolModel(
        symbol_id=_first_value(symbol, "SymbolID") or "",
        pin_templates=[
            _symbol_pin_template_model(block)
            for block in symbol.get_blocks("SPTemplate")
        ],
        pins=[_symbol_pin_model(item) for item in pin_list.get_items("SymbolPin")]
        if pin_list
        else [],
        geometries=_geometry_list_nodes(geometry_list),
        raw=_node_model(symbol),
    )


def _symbol_pin_template_model(template: AuroraBlock) -> AuroraSymbolPinTemplateModel:
    return AuroraSymbolPinTemplateModel(
        id=_first_value(template, "ID") or "",
        geometries=_geometry_list_nodes(template.get_block("GeometryList")),
    )


def _symbol_pin_model(item: AuroraItem) -> AuroraSymbolPinModel:
    values = list(item.values)
    return AuroraSymbolPinModel(
        number=_value_at(values, 0),
        template_id=_value_at(values, 1),
        location=_location_model(values[2:]),
        raw=values,
    )


def _footprint_symbol_model(footprint: AuroraBlock) -> AuroraFootprintSymbolModel:
    return AuroraFootprintSymbolModel(
        symbol_id=_first_value(footprint, "SymbolID") or "",
        pad_templates=[
            _pad_template_model(block) for block in footprint.get_blocks("PadTemplate")
        ],
        metal_layers=[
            _footprint_metal_layer_model(block)
            for block in footprint.get_blocks("MetalLayer")
        ],
        drill_holes=[_node_model(block) for block in footprint.get_blocks("DrillHole")],
        outline_geometry_type=_first_value(footprint, "OLGeomType"),
        outline=_node_model(footprint.get_block("Outline"))
        if footprint.get_block("Outline")
        else None,
        raw=_node_model(footprint),
    )


def _pad_template_model(template: AuroraBlock) -> AuroraPadTemplateModel:
    return AuroraPadTemplateModel(
        template_id=_first_value(template, "TemplateID") or "",
        geometries=_geometry_list_nodes(template.get_block("GeometryList")),
    )


def _footprint_metal_layer_model(layer: AuroraBlock) -> AuroraFootprintMetalLayerModel:
    name_type = _item_values(layer, "NameType")
    geometry_list = layer.get_block("GeometryList")
    return AuroraFootprintMetalLayerModel(
        name=_value_at(name_type, 0),
        position=_value_at(name_type, 1),
        geometries=_geometry_list_nodes(geometry_list),
        part_pads=[_part_pad_model(block) for block in layer.get_blocks("PartPad")],
        logic_layers=[
            _logic_layer_model(block) for block in layer.get_blocks("LogicLayer")
        ],
        raw=_node_model(layer),
    )


def _part_pad_model(pad: AuroraBlock) -> AuroraPartPadModel:
    pad_ids = _item_values(pad, "PadIDs")
    return AuroraPartPadModel(
        pad_id=_value_at(pad_ids, 0),
        template_id=_value_at(pad_ids, 1),
        location=_location_model(_item_values(pad, "Location")),
        raw=_node_model(pad),
    )


def _geometry_list_nodes(
    geometry_list: AuroraBlock | None,
) -> list[AuroraStoredNodeModel]:
    if geometry_list is None:
        return []
    return [_node_model(child) for child in geometry_list.children]


def _node_model(node: AuroraNode | None) -> AuroraStoredNodeModel | None:
    if node is None:
        return None
    if isinstance(node, AuroraItem):
        return AuroraStoredNodeModel(
            kind="item", name=node.name, values=list(node.values), children=[]
        )
    node = _materialized_block(node)
    return AuroraStoredNodeModel(
        kind="block",
        name=node.name,
        values=[],
        children=[_node_model(child) for child in node.children],
    )


def _materialized_block(block: AuroraBlock) -> AuroraBlock:
    if isinstance(block, AuroraRawBlock):
        return block.parsed_block()
    return block


def _location_model(values: list[str]) -> AuroraLocationModel | None:
    raw = list(values)
    if not raw:
        return None
    return AuroraLocationModel(
        x=_parse_float(_value_at(raw, 0)),
        y=_parse_float(_value_at(raw, 1)),
        ccw=_parse_bool(_value_at(raw, 2)),
        rotation=_parse_float(_value_at(raw, 3)),
        scale=_parse_float(_value_at(raw, 4)),
        flip_x=_parse_bool(_value_at(raw, 5)),
        flip_y=_parse_bool(_value_at(raw, 6)),
        raw=raw,
    )


def _attribute_model(value: str) -> AuroraAttributeModel:
    parts = _split_comma_values(strip_wrapping_pair(value, "(", ")"))
    return AuroraAttributeModel(
        name=_value_at(parts, 0) or "", value=_value_at(parts, 1) or ""
    )


def _split_comma_values(value: str) -> list[str]:
    return split_reserved(value, delimiters=",")


def _first_value(block: AuroraBlock | None, name: str) -> str | None:
    values = _item_values(block, name)
    return _value_at(values, 0)


def _value_at(values: list[str], index: int) -> str | None:
    if index >= len(values):
        return None
    return values[index]


def _parse_int(value: str | None) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _parse_float(value: str | None) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    if value.casefold() in {"y", "yes", "true", "1"}:
        return True
    if value.casefold() in {"n", "no", "false", "0"}:
        return False
    return None


def find_or_create_block(parent: AuroraBlock, name: str) -> AuroraBlock:
    block = parent.get_block(name)
    if block is None:
        block = parent.add_block(name)
    return block


def find_or_create_named_child(parent: AuroraBlock, name: str) -> AuroraBlock:
    block = parent.get_block(name)
    if block is None:
        block = AuroraBlock(name)
        parent.children.append(block)
    return block


def find_or_create_item(
    parent: AuroraBlock, name: str, default: list[str] | None = None
) -> AuroraItem:
    item = parent.get_item(name)
    if item is None:
        item = parent.add_item(name, default or [])
    return item
