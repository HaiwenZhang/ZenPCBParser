from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AltiumMetadata(SchemaModel):
    project_version: str
    parser_version: str
    output_schema_version: str
    source: str
    source_type: Literal["file", "unknown"]
    backend: Literal["rust-cli", "rust-native"]
    rust_parser_version: str


class AltiumSummary(SchemaModel):
    stream_count: int = Field(..., ge=0)
    parsed_stream_count: int = Field(..., ge=0)
    layer_count: int = Field(..., ge=0)
    net_count: int = Field(..., ge=0)
    class_count: int = Field(..., ge=0)
    rule_count: int = Field(..., ge=0)
    polygon_count: int = Field(..., ge=0)
    component_count: int = Field(..., ge=0)
    pad_count: int = Field(..., ge=0)
    via_count: int = Field(..., ge=0)
    track_count: int = Field(..., ge=0)
    arc_count: int = Field(..., ge=0)
    fill_count: int = Field(..., ge=0)
    region_count: int = Field(..., ge=0)
    text_count: int = Field(..., ge=0)
    board_outline_vertex_count: int = Field(..., ge=0)
    diagnostic_count: int = Field(..., ge=0)
    units: str
    format: str


class AltiumStreamSummary(SchemaModel):
    path: str
    size: int = Field(..., ge=0)
    parsed: bool


class AltiumPoint(SchemaModel):
    x_raw: int
    y_raw: int
    x: float
    y: float


class AltiumSize(SchemaModel):
    x_raw: int
    y_raw: int
    x: float
    y: float


class AltiumVertex(SchemaModel):
    is_round: bool
    radius: float
    start_angle: float
    end_angle: float
    position: AltiumPoint
    center: AltiumPoint | None = None


class AltiumBoard(SchemaModel):
    sheet_position: AltiumPoint | None = None
    sheet_size: AltiumSize | None = None
    layer_count_declared: int | None = None
    outline: list[AltiumVertex] = Field(default_factory=list)
    properties: dict[str, str] = Field(default_factory=dict)


class AltiumLayer(SchemaModel):
    layer_id: int = Field(..., ge=0)
    name: str
    next_id: int | None = Field(default=None, ge=0)
    prev_id: int | None = Field(default=None, ge=0)
    copper_thickness: float | None = None
    dielectric_constant: float | None = None
    dielectric_thickness: float | None = None
    dielectric_material: str | None = None
    mechanical_enabled: bool
    mechanical_kind: str | None = None


class AltiumNet(SchemaModel):
    index: int = Field(..., ge=0)
    name: str
    properties: dict[str, str] = Field(default_factory=dict)


class AltiumClass(SchemaModel):
    index: int = Field(..., ge=0)
    name: str
    unique_id: str | None = None
    kind: int
    members: list[str] = Field(default_factory=list)
    properties: dict[str, str] = Field(default_factory=dict)


class AltiumRule(SchemaModel):
    index: int = Field(..., ge=0)
    name: str
    kind: str
    priority: int
    scope1_expression: str | None = None
    scope2_expression: str | None = None
    properties: dict[str, str] = Field(default_factory=dict)


class AltiumComponent(SchemaModel):
    index: int = Field(..., ge=0)
    layer_id: int = Field(..., ge=0)
    layer_name: str
    position: AltiumPoint
    rotation: float
    locked: bool
    name_on: bool
    comment_on: bool
    source_designator: str | None = None
    source_unique_id: str | None = None
    source_hierarchical_path: str | None = None
    source_footprint_library: str | None = None
    pattern: str | None = None
    source_component_library: str | None = None
    source_lib_reference: str | None = None
    properties: dict[str, str] = Field(default_factory=dict)


class AltiumPadSizeAndShape(SchemaModel):
    hole_shape: str
    slot_size: float
    slot_rotation: float
    inner_sizes: list[AltiumSize] = Field(default_factory=list)
    inner_shapes: list[str] = Field(default_factory=list)
    hole_offsets: list[AltiumPoint] = Field(default_factory=list)
    alternate_shapes: list[str] = Field(default_factory=list)
    corner_radii: list[int] = Field(default_factory=list)


class AltiumPad(SchemaModel):
    index: int = Field(..., ge=0)
    name: str
    layer_id: int = Field(..., ge=0)
    layer_name: str
    net: int = Field(..., ge=0)
    component: int = Field(..., ge=0)
    position: AltiumPoint
    top_size: AltiumSize
    mid_size: AltiumSize
    bottom_size: AltiumSize
    hole_size: float
    top_shape: str
    mid_shape: str
    bottom_shape: str
    direction: float
    plated: bool
    pad_mode: str
    hole_rotation: float
    from_layer_id: int | None = Field(default=None, ge=0)
    to_layer_id: int | None = Field(default=None, ge=0)
    size_and_shape: AltiumPadSizeAndShape | None = None
    is_locked: bool
    is_tent_top: bool
    is_tent_bottom: bool
    is_test_fab_top: bool
    is_test_fab_bottom: bool


class AltiumVia(SchemaModel):
    index: int = Field(..., ge=0)
    net: int = Field(..., ge=0)
    position: AltiumPoint
    diameter: float
    hole_size: float
    start_layer_id: int = Field(..., ge=0)
    start_layer_name: str
    end_layer_id: int = Field(..., ge=0)
    end_layer_name: str
    via_mode: str
    diameter_by_layer: list[float] = Field(default_factory=list)
    is_locked: bool
    is_tent_top: bool
    is_tent_bottom: bool


class AltiumTrack(SchemaModel):
    index: int = Field(..., ge=0)
    layer_id: int = Field(..., ge=0)
    layer_name: str
    net: int = Field(..., ge=0)
    component: int = Field(..., ge=0)
    polygon: int = Field(..., ge=0)
    subpolygon: int = Field(..., ge=0)
    start: AltiumPoint
    end: AltiumPoint
    width: float
    is_locked: bool
    is_keepout: bool
    is_polygon_outline: bool
    keepout_restrictions: int = Field(..., ge=0)


class AltiumArc(SchemaModel):
    index: int = Field(..., ge=0)
    layer_id: int = Field(..., ge=0)
    layer_name: str
    net: int = Field(..., ge=0)
    component: int = Field(..., ge=0)
    polygon: int = Field(..., ge=0)
    subpolygon: int = Field(..., ge=0)
    center: AltiumPoint
    radius: float
    start_angle: float
    end_angle: float
    width: float
    is_locked: bool
    is_keepout: bool
    is_polygon_outline: bool
    keepout_restrictions: int = Field(..., ge=0)


class AltiumFill(SchemaModel):
    index: int = Field(..., ge=0)
    layer_id: int = Field(..., ge=0)
    layer_name: str
    component: int = Field(..., ge=0)
    net: int = Field(..., ge=0)
    position1: AltiumPoint
    position2: AltiumPoint
    rotation: float
    is_locked: bool
    is_keepout: bool
    keepout_restrictions: int = Field(..., ge=0)


class AltiumRegion(SchemaModel):
    index: int = Field(..., ge=0)
    layer_id: int = Field(..., ge=0)
    layer_name: str
    net: int = Field(..., ge=0)
    component: int = Field(..., ge=0)
    polygon: int = Field(..., ge=0)
    subpolygon: int = Field(..., ge=0)
    kind: str
    outline: list[AltiumVertex] = Field(default_factory=list)
    holes: list[list[AltiumVertex]] = Field(default_factory=list)
    is_locked: bool
    is_keepout: bool
    is_shape_based: bool
    keepout_restrictions: int = Field(..., ge=0)


class AltiumPolygon(SchemaModel):
    index: int = Field(..., ge=0)
    layer_id: int = Field(..., ge=0)
    layer_name: str
    net: int = Field(..., ge=0)
    locked: bool
    hatch_style: str
    grid_size: float | None = None
    track_width: float | None = None
    min_primitive_length: float | None = None
    use_octagons: bool
    pour_index: int
    vertices: list[AltiumVertex] = Field(default_factory=list)
    properties: dict[str, str] = Field(default_factory=dict)


class AltiumText(SchemaModel):
    index: int = Field(..., ge=0)
    layer_id: int = Field(..., ge=0)
    layer_name: str
    component: int = Field(..., ge=0)
    position: AltiumPoint
    height: float
    rotation: float
    stroke_width: float
    font_type: str
    font_name: str | None = None
    text: str
    is_bold: bool
    is_italic: bool
    is_mirrored: bool
    is_comment: bool
    is_designator: bool


class AltiumLayout(SchemaModel):
    metadata: AltiumMetadata
    summary: AltiumSummary
    file_header: str | None = None
    board: AltiumBoard | None = None
    layers: list[AltiumLayer] | None = None
    nets: list[AltiumNet] | None = None
    classes: list[AltiumClass] | None = None
    rules: list[AltiumRule] | None = None
    polygons: list[AltiumPolygon] | None = None
    components: list[AltiumComponent] | None = None
    pads: list[AltiumPad] | None = None
    vias: list[AltiumVia] | None = None
    tracks: list[AltiumTrack] | None = None
    arcs: list[AltiumArc] | None = None
    fills: list[AltiumFill] | None = None
    regions: list[AltiumRegion] | None = None
    texts: list[AltiumText] | None = None
    streams: list[AltiumStreamSummary] | None = None
    stream_counts: dict[str, int] = Field(default_factory=dict)
    diagnostics: list[str] = Field(default_factory=list)
