from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ALGMetadata(SchemaModel):
    project_version: str
    parser_version: str
    output_schema_version: str
    source: str
    source_type: Literal["file", "unknown"]
    backend: Literal["rust-cli", "rust-native"]
    rust_parser_version: str
    alg_revision: str | None = None
    extracta_version: str | None = None


class ALGSummary(SchemaModel):
    line_count: int = Field(..., ge=0)
    section_count: int = Field(..., ge=0)
    data_record_count: int = Field(..., ge=0)
    board_record_count: int = Field(..., ge=0)
    layer_count: int = Field(..., ge=0)
    metal_layer_count: int = Field(..., ge=0)
    component_count: int = Field(..., ge=0)
    pin_count: int = Field(..., ge=0)
    padstack_count: int = Field(..., ge=0)
    pad_count: int = Field(..., ge=0)
    via_count: int = Field(..., ge=0)
    track_count: int = Field(..., ge=0)
    net_count: int = Field(..., ge=0)
    symbol_count: int = Field(..., ge=0)
    outline_count: int = Field(..., ge=0)
    diagnostic_count: int = Field(..., ge=0)
    units: str
    accuracy: float | None = None
    board_name: str | None = None
    extracta_version: str | None = None


class ALGExtents(SchemaModel):
    x1: float
    y1: float
    x2: float
    y2: float


class ALGPoint(SchemaModel):
    x: float
    y: float


class ALGBoard(SchemaModel):
    name: str
    units: str
    accuracy: float | None = None
    extents: ALGExtents | None = None
    layer_count: int | None = Field(default=None, ge=0)
    thickness: str | None = None
    schematic_name: str | None = None


class ALGLayer(SchemaModel):
    sort: str | None = None
    name: str
    artwork: str | None = None
    use_kind: str | None = None
    conductor: bool
    dielectric_constant: str | None = None
    electrical_conductivity: str | None = None
    loss_tangent: str | None = None
    material: str | None = None
    shield_layer: str | None = None
    thermal_conductivity: str | None = None
    thickness: str | None = None
    layer_type: str | None = None


class ALGComponent(SchemaModel):
    refdes: str
    class_name: str | None = None
    package: str | None = None
    device_type: str | None = None
    value: str | None = None
    part_number: str | None = None
    room: str | None = None
    bom_ignore: str | None = None


class ALGPin(SchemaModel):
    refdes: str
    pin_number: str
    x: float | None = None
    y: float | None = None
    pad_stack_name: str | None = None
    pin_type: str | None = None
    net_name: str | None = None
    pin_name: str | None = None


class ALGPadstack(SchemaModel):
    name: str
    pad_stack_type: str | None = None
    start_layer: str | None = None
    end_layer: str | None = None
    drill_hole_name: str | None = None
    drill_figure_shape: str | None = None
    drill_figure_width: float | None = None
    drill_figure_height: float | None = None
    drill_figure_rotation: float | None = None
    via_pad_stack_name: str | None = None


class ALGShape(SchemaModel):
    kind: str
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    rotation: float | None = None


class ALGPad(SchemaModel):
    refdes: str | None = None
    pin_number: str | None = None
    layer_name: str | None = None
    pad_stack_name: str | None = None
    net_name: str | None = None
    x: float | None = None
    y: float | None = None
    pad_type: str | None = None
    shape: ALGShape | None = None
    source_section: str
    record_tag: str | None = None


class ALGVia(SchemaModel):
    key: str
    x: float
    y: float
    pad_stack_name: str | None = None
    net_name: str | None = None
    layer_names: list[str] = Field(default_factory=list)
    shape: ALGShape | None = None


class ALGTrack(SchemaModel):
    kind: str
    layer_name: str | None = None
    net_name: str | None = None
    refdes: str | None = None
    record_tag: str | None = None
    geometry_role: str | None = None
    width: float | None = None
    start: ALGPoint | None = None
    end: ALGPoint | None = None
    center: ALGPoint | None = None
    clockwise: bool | None = None
    bbox: ALGExtents | None = None


class ALGSymbol(SchemaModel):
    sym_type: str | None = None
    sym_name: str | None = None
    refdes: str | None = None
    bbox: ALGExtents | None = None
    center: ALGPoint | None = None
    mirror: bool | None = None
    rotation: float | None = None
    location: ALGPoint | None = None
    library_path: str | None = None


class ALGGraphic(SchemaModel):
    class_name: str | None = None
    subclass: str | None = None
    record_tag: str | None = None
    kind: str
    start: ALGPoint | None = None
    end: ALGPoint | None = None
    center: ALGPoint | None = None
    clockwise: bool | None = None
    bbox: ALGExtents | None = None


class ALGLayout(SchemaModel):
    metadata: ALGMetadata
    summary: ALGSummary
    board: ALGBoard | None = None
    layers: list[ALGLayer] | None = None
    components: list[ALGComponent] | None = None
    pins: list[ALGPin] | None = None
    padstacks: list[ALGPadstack] | None = None
    pads: list[ALGPad] | None = None
    vias: list[ALGVia] | None = None
    tracks: list[ALGTrack] | None = None
    symbols: list[ALGSymbol] | None = None
    outlines: list[ALGGraphic] | None = None
    section_counts: dict[str, int] = Field(default_factory=dict)
    diagnostics: list[str] = Field(default_factory=list)
