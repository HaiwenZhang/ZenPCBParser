use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
pub struct AedbDefLayout {
    pub metadata: Metadata,
    pub summary: Summary,
    pub domain: DefDomain,
    pub records: Option<Vec<RecordSummary>>,
    pub blocks: Option<Vec<DslBlockSummary>>,
    pub diagnostics: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Metadata {
    pub project_version: String,
    pub parser_version: String,
    pub output_schema_version: String,
    pub source: String,
    pub source_type: String,
    pub backend: String,
    pub rust_parser_version: String,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Summary {
    pub file_size_bytes: usize,
    pub record_count: usize,
    pub text_record_count: usize,
    pub binary_record_count: usize,
    pub text_payload_bytes: usize,
    pub binary_bytes: usize,
    pub dsl_block_count: usize,
    pub top_level_block_count: usize,
    pub assignment_line_count: usize,
    pub function_line_count: usize,
    pub other_line_count: usize,
    pub diagnostic_count: usize,
    pub def_version: Option<String>,
    pub last_update_timestamp: Option<String>,
    pub encrypted: Option<bool>,
}

#[derive(Debug, Clone, Serialize)]
pub struct RecordSummary {
    pub index: usize,
    pub kind: String,
    pub offset: usize,
    pub end_offset: usize,
    pub total_size: usize,
    pub tag: Option<u8>,
    pub payload_size: usize,
    pub payload_hash: String,
    pub valid_utf8: Option<bool>,
    pub line_count: Option<usize>,
    pub first_block_name: Option<String>,
    pub block_count: Option<usize>,
    pub assignment_line_count: Option<usize>,
    pub function_line_count: Option<usize>,
    pub other_line_count: Option<usize>,
}

#[derive(Debug, Clone, Serialize)]
pub struct DslBlockSummary {
    pub record_index: usize,
    pub name: String,
    pub path: String,
    pub depth: usize,
    pub start_line: usize,
    pub end_line: Option<usize>,
    pub assignment_line_count: usize,
    pub function_line_count: usize,
    pub other_line_count: usize,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct DefDomain {
    pub summary: DefDomainSummary,
    pub materials: Vec<MaterialDefinition>,
    pub stackup_layers: Vec<StackupLayer>,
    pub board_metal_layers: Vec<StackupLayer>,
    pub padstacks: Vec<PadstackDefinition>,
    pub components: Vec<ComponentDefinition>,
    pub component_placements: Vec<ComponentPlacement>,
    pub binary_strings: BinaryStringSummary,
    pub binary_geometry: BinaryGeometrySummary,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct DefDomainSummary {
    pub material_count: usize,
    pub stackup_layer_count: usize,
    pub board_metal_layer_count: usize,
    pub dielectric_layer_count: usize,
    pub padstack_count: usize,
    pub padstack_layer_pad_count: usize,
    pub multilayer_padstack_count: usize,
    pub component_definition_count: usize,
    pub component_pin_definition_count: usize,
    pub component_placement_count: usize,
    pub component_part_candidate_count: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct MaterialDefinition {
    pub name: String,
    pub record_index: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct StackupLayer {
    pub name: String,
    pub id: Option<i64>,
    pub layer_type: Option<String>,
    pub top_bottom: Option<String>,
    pub thickness: Option<String>,
    pub lower_elevation: Option<String>,
    pub material: Option<String>,
    pub fill_material: Option<String>,
    pub record_index: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct PadstackDefinition {
    pub id: Option<i64>,
    pub name: Option<String>,
    pub layer_pads: Vec<PadstackLayerPad>,
    pub record_index: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct PadstackLayerPad {
    pub layer_name: Option<String>,
    pub id: Option<i64>,
    pub pad_shape: Option<String>,
    pub antipad_shape: Option<String>,
    pub thermal_shape: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ComponentDefinition {
    pub name: String,
    pub uid: Option<i64>,
    pub footprint: Option<String>,
    pub cell_name: Option<String>,
    pub pins: Vec<ComponentPinDefinition>,
    pub record_index: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct ComponentPinDefinition {
    pub name: Option<String>,
    pub number: Option<i64>,
    pub id: Option<i64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ComponentPlacement {
    pub refdes: String,
    pub component_class: Option<String>,
    pub device_type: Option<String>,
    pub value: Option<String>,
    pub package: Option<String>,
    pub part_number: Option<String>,
    pub symbol_box: Option<SymbolBox>,
    pub part_name_candidates: Vec<String>,
    pub record_index: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct SymbolBox {
    pub x_min: f64,
    pub y_min: f64,
    pub x_max: f64,
    pub y_max: f64,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct BinaryStringSummary {
    pub string_count: usize,
    pub unique_string_count: usize,
    pub via_instance_name_count: usize,
    pub unique_via_instance_name_count: usize,
    pub line_instance_name_count: usize,
    pub unique_line_instance_name_count: usize,
    pub polygon_instance_name_count: usize,
    pub unique_polygon_instance_name_count: usize,
    pub polygon_void_instance_name_count: usize,
    pub unique_polygon_void_instance_name_count: usize,
    pub geometry_instance_name_count: usize,
    pub unique_geometry_instance_name_count: usize,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct BinaryGeometrySummary {
    pub via_record_count: usize,
    pub named_via_record_count: usize,
    pub unnamed_via_record_count: usize,
    pub unique_via_location_count: usize,
    pub path_record_count: usize,
    pub named_path_record_count: usize,
    pub unnamed_path_record_count: usize,
    pub path_line_segment_count: usize,
    pub path_arc_segment_count: usize,
    pub path_segment_count: usize,
    pub path_width_count: usize,
}
