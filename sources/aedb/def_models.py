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
    material_count: int
    stackup_layer_count: int
    board_metal_layer_count: int
    dielectric_layer_count: int
    padstack_count: int
    padstack_layer_pad_count: int
    multilayer_padstack_count: int
    component_definition_count: int
    component_pin_definition_count: int
    component_placement_count: int
    component_part_candidate_count: int


class AEDBDefBinaryMaterialDefinition(AEDBDefBinarySchemaModel):
    name: str
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
    antipad_shape: str | None = None
    thermal_shape: str | None = None


class AEDBDefBinaryPadstackDefinition(AEDBDefBinarySchemaModel):
    id: int | None = None
    name: str | None = None
    layer_pads: list[AEDBDefBinaryPadstackLayerPad] = Field(default_factory=list)
    record_index: int


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


class AEDBDefBinaryDomain(AEDBDefBinarySchemaModel):
    summary: AEDBDefBinaryDomainSummary
    materials: list[AEDBDefBinaryMaterialDefinition] = Field(default_factory=list)
    stackup_layers: list[AEDBDefBinaryStackupLayer] = Field(default_factory=list)
    board_metal_layers: list[AEDBDefBinaryStackupLayer] = Field(default_factory=list)
    padstacks: list[AEDBDefBinaryPadstackDefinition] = Field(default_factory=list)
    components: list[AEDBDefBinaryComponentDefinition] = Field(default_factory=list)
    component_placements: list[AEDBDefBinaryComponentPlacement] = Field(
        default_factory=list
    )
    binary_strings: AEDBDefBinaryStringSummary
    binary_geometry: AEDBDefBinaryGeometrySummary


class AEDBDefBinaryLayout(AEDBDefBinarySchemaModel):
    metadata: AEDBDefBinaryMetadata
    summary: AEDBDefBinarySummary
    domain: AEDBDefBinaryDomain
    records: list[AEDBDefBinaryRecordSummary] | None = Field(default=None)
    blocks: list[AEDBDefBinaryBlockSummary] | None = Field(default=None)
    diagnostics: list[str] = Field(default_factory=list)
