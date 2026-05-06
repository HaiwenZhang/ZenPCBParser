from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AEDBDefBinarySchemaModel(BaseModel):
    """Base model for Rust AEDB DEF binary parser payloads."""

    model_config = ConfigDict(extra="forbid")


class AEDBDefBinaryMetadata(AEDBDefBinarySchemaModel):
    project_version: str
    parser_version: str
    output_schema_version: str
    source: str
    source_type: str
    backend: str
    rust_parser_version: str


class AEDBDefBinarySummary(AEDBDefBinarySchemaModel):
    file_size_bytes: int
    record_count: int
    text_record_count: int
    binary_record_count: int
    text_payload_bytes: int
    binary_bytes: int
    dsl_block_count: int
    top_level_block_count: int
    assignment_line_count: int
    function_line_count: int
    other_line_count: int
    diagnostic_count: int
    def_version: str | None = None
    last_update_timestamp: str | None = None
    encrypted: bool | None = None


class AEDBDefBinaryRecordSummary(AEDBDefBinarySchemaModel):
    index: int
    kind: str
    offset: int
    end_offset: int
    total_size: int
    tag: int | None = None
    payload_size: int
    payload_hash: str
    valid_utf8: bool | None = None
    line_count: int | None = None
    first_block_name: str | None = None
    block_count: int | None = None
    assignment_line_count: int | None = None
    function_line_count: int | None = None
    other_line_count: int | None = None


class AEDBDefBinaryBlockSummary(AEDBDefBinarySchemaModel):
    record_index: int
    name: str
    path: str
    depth: int
    start_line: int
    end_line: int | None = None
    assignment_line_count: int
    function_line_count: int
    other_line_count: int


class AEDBDefBinaryDomainSummary(AEDBDefBinarySchemaModel):
    layout_net_count: int
    material_count: int
    stackup_layer_count: int
    board_metal_layer_count: int
    dielectric_layer_count: int
    padstack_count: int
    padstack_instance_definition_count: int = 0
    padstack_layer_pad_count: int
    multilayer_padstack_count: int
    component_definition_count: int
    component_pin_definition_count: int
    component_placement_count: int
    component_part_candidate_count: int


class AEDBDefBinaryLayoutNetDefinition(AEDBDefBinarySchemaModel):
    index: int
    name: str


class AEDBDefBinaryMaterialDefinition(AEDBDefBinarySchemaModel):
    name: str
    conductivity: str | None = None
    permittivity: str | None = None
    dielectric_loss_tangent: str | None = None
    record_index: int


class AEDBDefBinaryStackupLayer(AEDBDefBinarySchemaModel):
    name: str
    id: int | None = None
    layer_type: str | None = None
    top_bottom: str | None = None
    thickness: str | None = None
    lower_elevation: str | None = None
    material: str | None = None
    fill_material: str | None = None
    record_index: int


class AEDBDefBinaryPadstackLayerPad(AEDBDefBinarySchemaModel):
    layer_name: str | None = None
    id: int | None = None
    pad_shape: str | None = None
    pad_parameters: list[str] = Field(default_factory=list)
    pad_offset_x: str | None = None
    pad_offset_y: str | None = None
    pad_rotation: str | None = None
    antipad_shape: str | None = None
    antipad_parameters: list[str] = Field(default_factory=list)
    antipad_offset_x: str | None = None
    antipad_offset_y: str | None = None
    antipad_rotation: str | None = None
    thermal_shape: str | None = None
    thermal_parameters: list[str] = Field(default_factory=list)
    thermal_offset_x: str | None = None
    thermal_offset_y: str | None = None
    thermal_rotation: str | None = None


class AEDBDefBinaryPadstackDefinition(AEDBDefBinarySchemaModel):
    id: int | None = None
    name: str | None = None
    hole_shape: str | None = None
    hole_parameters: list[str] = Field(default_factory=list)
    hole_offset_x: str | None = None
    hole_offset_y: str | None = None
    hole_rotation: str | None = None
    layer_pads: list[AEDBDefBinaryPadstackLayerPad] = Field(default_factory=list)
    record_index: int


class AEDBDefBinaryPadstackInstanceDefinitionRecord(AEDBDefBinarySchemaModel):
    record_index: int
    raw_definition_index: int
    padstack_id: int | None = None
    padstack_name: str | None = None
    first_layer_id: int | None = None
    first_layer_name: str | None = None
    last_layer_id: int | None = None
    last_layer_name: str | None = None
    first_layer_positive: bool | None = None
    solder_ball_layer_id: int | None = None
    solder_ball_layer_name: str | None = None


class AEDBDefBinaryComponentPinDefinition(AEDBDefBinarySchemaModel):
    name: str | None = None
    number: int | None = None
    id: int | None = None


class AEDBDefBinaryComponentDefinition(AEDBDefBinarySchemaModel):
    name: str
    uid: int | None = None
    footprint: str | None = None
    cell_name: str | None = None
    pins: list[AEDBDefBinaryComponentPinDefinition] = Field(default_factory=list)
    record_index: int


class AEDBDefBinarySymbolBox(AEDBDefBinarySchemaModel):
    x_min: float
    y_min: float
    x_max: float
    y_max: float


class AEDBDefBinaryComponentPlacement(AEDBDefBinarySchemaModel):
    refdes: str
    component_class: str | None = None
    device_type: str | None = None
    value: str | None = None
    package: str | None = None
    part_number: str | None = None
    symbol_box: AEDBDefBinarySymbolBox | None = None
    part_name_candidates: list[str] = Field(default_factory=list)
    record_index: int


class AEDBDefBinaryStringSummary(AEDBDefBinarySchemaModel):
    string_count: int
    unique_string_count: int
    via_instance_name_count: int
    unique_via_instance_name_count: int
    line_instance_name_count: int
    unique_line_instance_name_count: int
    polygon_instance_name_count: int
    unique_polygon_instance_name_count: int
    polygon_void_instance_name_count: int
    unique_polygon_void_instance_name_count: int
    geometry_instance_name_count: int
    unique_geometry_instance_name_count: int


class AEDBDefBinaryGeometrySummary(AEDBDefBinarySchemaModel):
    padstack_instance_record_count: int
    component_pin_padstack_instance_record_count: int
    named_via_padstack_instance_record_count: int
    unnamed_padstack_instance_record_count: int
    padstack_instance_secondary_name_count: int
    via_record_count: int
    named_via_record_count: int
    unnamed_via_record_count: int
    unique_via_location_count: int
    path_record_count: int
    named_path_record_count: int
    unnamed_path_record_count: int
    path_line_segment_count: int
    path_arc_segment_count: int
    path_segment_count: int
    path_width_count: int
    polygon_record_count: int
    polygon_outer_record_count: int
    polygon_void_record_count: int
    polygon_point_count: int
    polygon_arc_segment_count: int


class AEDBDefBinaryPadstackInstanceRecord(AEDBDefBinarySchemaModel):
    offset: int
    geometry_id: int
    name: str
    name_kind: str
    net_index: int | None = None
    net_name: str | None = None
    raw_owner_index: int | None = None
    raw_definition_index: int | None = None
    x: float
    y: float
    rotation: float
    drill_diameter: float | None = None
    secondary_name: str | None = None
    secondary_id: int | None = None


class AEDBDefBinaryPathItem(AEDBDefBinarySchemaModel):
    kind: str
    x: float | None = None
    y: float | None = None
    arc_height: float | None = None


class AEDBDefBinaryPathRecord(AEDBDefBinarySchemaModel):
    offset: int
    geometry_id: int | None = None
    net_index: int | None = None
    net_name: str | None = None
    layer_id: int | None = None
    layer_name: str | None = None
    named: bool
    width: float
    item_count: int
    point_count: int
    line_segment_count: int
    arc_segment_count: int
    items: list[AEDBDefBinaryPathItem] = Field(default_factory=list)


class AEDBDefBinaryPolygonRecord(AEDBDefBinarySchemaModel):
    offset: int
    count_offset: int
    coordinate_offset: int
    geometry_id: int | None = None
    parent_geometry_id: int | None = None
    is_void: bool
    layer_id: int | None = None
    layer_name: str | None = None
    net_index: int | None = None
    net_name: str | None = None
    item_count: int
    point_count: int
    arc_segment_count: int
    items: list[AEDBDefBinaryPathItem] = Field(default_factory=list)


class AEDBDefBinaryDomain(AEDBDefBinarySchemaModel):
    summary: AEDBDefBinaryDomainSummary
    layout_nets: list[AEDBDefBinaryLayoutNetDefinition] = Field(default_factory=list)
    materials: list[AEDBDefBinaryMaterialDefinition] = Field(default_factory=list)
    stackup_layers: list[AEDBDefBinaryStackupLayer] = Field(default_factory=list)
    board_metal_layers: list[AEDBDefBinaryStackupLayer] = Field(default_factory=list)
    padstacks: list[AEDBDefBinaryPadstackDefinition] = Field(default_factory=list)
    padstack_instance_definitions: list[
        AEDBDefBinaryPadstackInstanceDefinitionRecord
    ] = Field(default_factory=list)
    components: list[AEDBDefBinaryComponentDefinition] = Field(default_factory=list)
    component_placements: list[AEDBDefBinaryComponentPlacement] = Field(
        default_factory=list
    )
    binary_strings: AEDBDefBinaryStringSummary
    binary_geometry: AEDBDefBinaryGeometrySummary
    binary_padstack_instance_records: list[AEDBDefBinaryPadstackInstanceRecord] = Field(
        default_factory=list
    )
    binary_path_records: list[AEDBDefBinaryPathRecord] = Field(default_factory=list)
    binary_polygon_records: list[AEDBDefBinaryPolygonRecord] = Field(
        default_factory=list
    )


class AEDBDefBinaryLayout(AEDBDefBinarySchemaModel):
    metadata: AEDBDefBinaryMetadata
    summary: AEDBDefBinarySummary
    domain: AEDBDefBinaryDomain
    records: list[AEDBDefBinaryRecordSummary] | None = Field(default=None)
    blocks: list[AEDBDefBinaryBlockSummary] | None = Field(default=None)
    diagnostics: list[str] = Field(default_factory=list)
