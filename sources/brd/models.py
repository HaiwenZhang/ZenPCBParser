from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BRDMetadata(SchemaModel):
    project_version: str
    parser_version: str
    output_schema_version: str
    source: str
    source_type: Literal["file", "unknown"]
    backend: Literal["rust-cli", "rust-native"]
    rust_parser_version: str


class BRDSummary(SchemaModel):
    object_count_declared: int = Field(..., ge=0)
    object_count_parsed: int = Field(..., ge=0)
    string_count: int = Field(..., ge=0)
    layer_count: int = Field(..., ge=0)
    net_count: int = Field(..., ge=0)
    padstack_count: int = Field(..., ge=0)
    footprint_count: int = Field(..., ge=0)
    placed_pad_count: int = Field(..., ge=0)
    via_count: int = Field(..., ge=0)
    track_count: int = Field(..., ge=0)
    segment_count: int = Field(..., ge=0)
    shape_count: int = Field(..., ge=0)
    keepout_count: int = Field(..., ge=0)
    net_assignment_count: int = Field(..., ge=0)
    text_count: int = Field(..., ge=0)
    diagnostic_count: int = Field(..., ge=0)
    format_version: str
    allegro_version: str
    units: str


class BRDLinkedList(SchemaModel):
    head: int = Field(..., ge=0)
    tail: int = Field(..., ge=0)


class BRDLayerMapEntry(SchemaModel):
    index: int = Field(..., ge=0)
    class_code: int = Field(..., ge=0)
    layer_list_key: int = Field(..., ge=0)


class BRDHeader(SchemaModel):
    magic: int = Field(..., ge=0)
    format_version: str
    file_role: int = Field(..., ge=0)
    writer_program: int = Field(..., ge=0)
    object_count: int = Field(..., ge=0)
    max_key: int = Field(..., ge=0)
    allegro_version: str
    board_units_code: int = Field(..., ge=0)
    board_units: str
    units_divisor: int = Field(..., ge=0)
    coordinate_scale_nm: float | None = None
    string_count: int = Field(..., ge=0)
    x27_end: int = Field(..., ge=0)
    linked_lists: dict[str, BRDLinkedList] = Field(default_factory=dict)
    layer_map: list[BRDLayerMapEntry] = Field(default_factory=list)


class BRDStringEntry(SchemaModel):
    id: int = Field(..., ge=0)
    value: str


class BRDLayerInfo(SchemaModel):
    class_code: int = Field(..., ge=0)
    subclass_code: int = Field(..., ge=0)
    class_name: str
    subclass_name: str | None = None


class BRDLayer(SchemaModel):
    key: int = Field(..., ge=0)
    class_code: int = Field(..., ge=0)
    names: list[str] = Field(default_factory=list)


class BRDBlockSummary(SchemaModel):
    block_type: int = Field(..., ge=0)
    type_name: str
    offset: int = Field(..., ge=0)
    length: int = Field(..., ge=0)
    key: int | None = Field(default=None, ge=0)
    next: int | None = Field(default=None, ge=0)


class BRDNet(SchemaModel):
    key: int = Field(..., ge=0)
    next: int = Field(..., ge=0)
    name_string_id: int = Field(..., ge=0)
    name: str | None = None
    assignment: int = Field(..., ge=0)
    fields: int = Field(..., ge=0)
    match_group: int = Field(..., ge=0)


class BRDPadstack(SchemaModel):
    key: int = Field(..., ge=0)
    next: int = Field(..., ge=0)
    name_string_id: int = Field(..., ge=0)
    name: str | None = None
    layer_count: int = Field(..., ge=0)
    drill_size_raw: int | None = Field(default=None, ge=0)
    fixed_component_count: int = Field(..., ge=0)
    components_per_layer: int = Field(..., ge=0)
    components: list["BRDPadstackComponent"] = Field(default_factory=list)


class BRDPadstackComponent(SchemaModel):
    slot_index: int = Field(..., ge=0)
    layer_index: int | None = Field(default=None, ge=0)
    role: str
    component_type: int = Field(..., ge=0)
    type_name: str
    width_raw: int
    height_raw: int
    z1_raw: int | None = None
    x_offset_raw: int
    y_offset_raw: int
    shape_key: int = Field(..., ge=0)
    z2_raw: int | None = Field(default=None, ge=0)


class BRDComponent(SchemaModel):
    key: int = Field(..., ge=0)
    next: int = Field(..., ge=0)
    device_type_string_id: int = Field(..., ge=0)
    device_type: str | None = None
    symbol_name_string_id: int = Field(..., ge=0)
    symbol_name: str | None = None
    first_instance: int = Field(..., ge=0)
    function_slot: int = Field(..., ge=0)
    pin_number: int = Field(..., ge=0)
    fields: int = Field(..., ge=0)


class BRDComponentInstance(SchemaModel):
    key: int = Field(..., ge=0)
    next: int = Field(..., ge=0)
    footprint_instance: int = Field(..., ge=0)
    refdes_string_id: int = Field(..., ge=0)
    refdes: str | None = None
    function_instance: int = Field(..., ge=0)
    fields: int = Field(..., ge=0)
    first_pad: int = Field(..., ge=0)


class BRDFootprint(SchemaModel):
    key: int = Field(..., ge=0)
    next: int = Field(..., ge=0)
    name_string_id: int = Field(..., ge=0)
    name: str | None = None
    first_instance: int = Field(..., ge=0)
    sym_lib_path_string_id: int = Field(..., ge=0)
    sym_lib_path: str | None = None
    coords_raw: list[int]


class BRDFootprintInstance(SchemaModel):
    key: int = Field(..., ge=0)
    next: int = Field(..., ge=0)
    layer: int = Field(..., ge=0)
    rotation_mdeg: int = Field(..., ge=0)
    x_raw: int
    y_raw: int
    component_instance: int = Field(..., ge=0)
    graphic: int = Field(..., ge=0)
    first_pad: int = Field(..., ge=0)
    text: int = Field(..., ge=0)


class BRDPadDefinition(SchemaModel):
    key: int = Field(..., ge=0)
    next: int = Field(..., ge=0)
    name_string_id: int = Field(..., ge=0)
    name: str | None = None
    x_raw: int
    y_raw: int
    padstack: int = Field(..., ge=0)
    flags: int = Field(..., ge=0)
    rotation_mdeg: int = Field(..., ge=0)


class BRDPlacedPad(SchemaModel):
    key: int = Field(..., ge=0)
    next: int = Field(..., ge=0)
    layer: BRDLayerInfo
    net_assignment: int = Field(..., ge=0)
    parent_footprint: int = Field(..., ge=0)
    pad: int = Field(..., ge=0)
    pin_number: int = Field(..., ge=0)
    name_text: int = Field(..., ge=0)
    coords_raw: list[int]


class BRDVia(SchemaModel):
    key: int = Field(..., ge=0)
    next: int = Field(..., ge=0)
    layer: BRDLayerInfo
    net_assignment: int = Field(..., ge=0)
    padstack: int = Field(..., ge=0)
    x_raw: int
    y_raw: int


class BRDTrack(SchemaModel):
    key: int = Field(..., ge=0)
    next: int = Field(..., ge=0)
    layer: BRDLayerInfo
    net_assignment: int = Field(..., ge=0)
    first_segment: int = Field(..., ge=0)


class BRDSegment(SchemaModel):
    key: int = Field(..., ge=0)
    next: int = Field(..., ge=0)
    parent: int = Field(..., ge=0)
    block_type: int = Field(..., ge=0)
    kind: Literal["line", "arc"]
    width_raw: int = Field(..., ge=0)
    start_raw: list[int]
    end_raw: list[int]
    center_raw: list[float] | None = None
    radius_raw: float | None = None
    bbox_raw: list[int] | None = None
    clockwise: bool | None = None


class BRDShape(SchemaModel):
    key: int = Field(..., ge=0)
    next: int = Field(..., ge=0)
    layer: BRDLayerInfo
    first_segment: int = Field(..., ge=0)
    first_keepout: int = Field(..., ge=0)
    table: int = Field(..., ge=0)
    coords_raw: list[int]


class BRDKeepout(SchemaModel):
    key: int = Field(..., ge=0)
    next: int = Field(..., ge=0)
    layer: BRDLayerInfo
    flags: int = Field(..., ge=0)
    first_segment: int = Field(..., ge=0)


class BRDNetAssignment(SchemaModel):
    key: int = Field(..., ge=0)
    next: int = Field(..., ge=0)
    net: int = Field(..., ge=0)
    conn_item: int = Field(..., ge=0)


class BRDText(SchemaModel):
    key: int = Field(..., ge=0)
    next: int | None = Field(default=None, ge=0)
    layer: BRDLayerInfo | None = None
    text: str | None = None
    x_raw: int | None = None
    y_raw: int | None = None
    rotation_mdeg: int | None = Field(default=None, ge=0)
    string_graphic_key: int | None = Field(default=None, ge=0)


class BRDLayout(SchemaModel):
    metadata: BRDMetadata
    summary: BRDSummary
    header: BRDHeader
    strings: list[BRDStringEntry] | None = None
    layers: list[BRDLayer] | None = None
    nets: list[BRDNet] | None = None
    padstacks: list[BRDPadstack] | None = None
    components: list[BRDComponent] | None = None
    component_instances: list[BRDComponentInstance] | None = None
    footprints: list[BRDFootprint] | None = None
    footprint_instances: list[BRDFootprintInstance] | None = None
    pad_definitions: list[BRDPadDefinition] | None = None
    placed_pads: list[BRDPlacedPad] | None = None
    vias: list[BRDVia] | None = None
    tracks: list[BRDTrack] | None = None
    segments: list[BRDSegment] | None = None
    shapes: list[BRDShape] | None = None
    keepouts: list[BRDKeepout] | None = None
    net_assignments: list[BRDNetAssignment] | None = None
    texts: list[BRDText] | None = None
    blocks: list[BRDBlockSummary] | None = None
    block_counts: dict[str, int] = Field(default_factory=dict)
    diagnostics: list[str] = Field(default_factory=list)
