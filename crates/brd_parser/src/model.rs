use serde::Serialize;
use std::collections::BTreeMap;

#[derive(Debug, Clone, Serialize)]
pub struct BrdLayout {
    pub metadata: Metadata,
    pub summary: Summary,
    pub header: Header,
    pub strings: Option<Vec<StringEntry>>,
    pub layers: Option<Vec<Layer>>,
    pub nets: Option<Vec<Net>>,
    pub padstacks: Option<Vec<Padstack>>,
    pub components: Option<Vec<Component>>,
    pub component_instances: Option<Vec<ComponentInstance>>,
    pub footprints: Option<Vec<Footprint>>,
    pub footprint_instances: Option<Vec<FootprintInstance>>,
    pub pad_definitions: Option<Vec<PadDefinition>>,
    pub placed_pads: Option<Vec<PlacedPad>>,
    pub vias: Option<Vec<Via>>,
    pub tracks: Option<Vec<Track>>,
    pub segments: Option<Vec<Segment>>,
    pub shapes: Option<Vec<Shape>>,
    pub keepouts: Option<Vec<Keepout>>,
    pub net_assignments: Option<Vec<NetAssignment>>,
    pub texts: Option<Vec<Text>>,
    pub blocks: Option<Vec<BlockSummary>>,
    pub block_counts: BTreeMap<String, usize>,
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
    pub object_count_declared: u32,
    pub object_count_parsed: usize,
    pub string_count: usize,
    pub layer_count: usize,
    pub net_count: usize,
    pub padstack_count: usize,
    pub footprint_count: usize,
    pub placed_pad_count: usize,
    pub via_count: usize,
    pub track_count: usize,
    pub segment_count: usize,
    pub shape_count: usize,
    pub keepout_count: usize,
    pub net_assignment_count: usize,
    pub text_count: usize,
    pub diagnostic_count: usize,
    pub format_version: String,
    pub allegro_version: String,
    pub units: String,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Header {
    pub magic: u32,
    pub format_version: String,
    pub file_role: u32,
    pub writer_program: u32,
    pub object_count: u32,
    pub max_key: u32,
    pub allegro_version: String,
    pub board_units_code: u8,
    pub board_units: String,
    pub units_divisor: u32,
    pub coordinate_scale_nm: Option<f64>,
    pub string_count: u32,
    pub x27_end: u32,
    pub linked_lists: BTreeMap<String, LinkedList>,
    pub layer_map: Vec<LayerMapEntry>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct LinkedList {
    pub head: u32,
    pub tail: u32,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct LayerMapEntry {
    pub index: usize,
    pub class_code: u32,
    pub layer_list_key: u32,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct StringEntry {
    pub id: u32,
    pub value: String,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct LayerInfo {
    pub class_code: u8,
    pub subclass_code: u8,
    pub class_name: String,
    pub subclass_name: Option<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Layer {
    pub key: u32,
    pub class_code: u8,
    pub names: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct BlockSummary {
    pub block_type: u8,
    pub type_name: String,
    pub offset: usize,
    pub length: usize,
    pub key: Option<u32>,
    pub next: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Net {
    pub key: u32,
    pub next: u32,
    pub name_string_id: u32,
    pub name: Option<String>,
    pub assignment: u32,
    pub fields: u32,
    pub match_group: u32,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Padstack {
    pub key: u32,
    pub next: u32,
    pub name_string_id: u32,
    pub name: Option<String>,
    pub layer_count: u16,
    pub drill_size_raw: Option<u32>,
    pub fixed_component_count: usize,
    pub components_per_layer: usize,
    pub components: Vec<PadstackComponent>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct PadstackComponent {
    pub slot_index: usize,
    pub layer_index: Option<usize>,
    pub role: String,
    pub component_type: u8,
    pub type_name: String,
    pub width_raw: i32,
    pub height_raw: i32,
    pub z1_raw: Option<i32>,
    pub x_offset_raw: i32,
    pub y_offset_raw: i32,
    pub shape_key: u32,
    pub z2_raw: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Component {
    pub key: u32,
    pub next: u32,
    pub device_type_string_id: u32,
    pub device_type: Option<String>,
    pub symbol_name_string_id: u32,
    pub symbol_name: Option<String>,
    pub first_instance: u32,
    pub function_slot: u32,
    pub pin_number: u32,
    pub fields: u32,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct ComponentInstance {
    pub key: u32,
    pub next: u32,
    pub footprint_instance: u32,
    pub refdes_string_id: u32,
    pub refdes: Option<String>,
    pub function_instance: u32,
    pub fields: u32,
    pub first_pad: u32,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Footprint {
    pub key: u32,
    pub next: u32,
    pub name_string_id: u32,
    pub name: Option<String>,
    pub first_instance: u32,
    pub sym_lib_path_string_id: u32,
    pub sym_lib_path: Option<String>,
    pub coords_raw: [u32; 4],
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct FootprintInstance {
    pub key: u32,
    pub next: u32,
    pub layer: u8,
    pub rotation_mdeg: u32,
    pub x_raw: i32,
    pub y_raw: i32,
    pub component_instance: u32,
    pub graphic: u32,
    pub first_pad: u32,
    pub text: u32,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct PadDefinition {
    pub key: u32,
    pub next: u32,
    pub name_string_id: u32,
    pub name: Option<String>,
    pub x_raw: i32,
    pub y_raw: i32,
    pub padstack: u32,
    pub flags: u32,
    pub rotation_mdeg: u32,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct PlacedPad {
    pub key: u32,
    pub next: u32,
    pub layer: LayerInfo,
    pub net_assignment: u32,
    pub parent_footprint: u32,
    pub pad: u32,
    pub pin_number: u32,
    pub name_text: u32,
    pub coords_raw: [i32; 4],
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Via {
    pub key: u32,
    pub next: u32,
    pub layer: LayerInfo,
    pub net_assignment: u32,
    pub padstack: u32,
    pub x_raw: i32,
    pub y_raw: i32,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Track {
    pub key: u32,
    pub next: u32,
    pub layer: LayerInfo,
    pub net_assignment: u32,
    pub first_segment: u32,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Segment {
    pub key: u32,
    pub next: u32,
    pub parent: u32,
    pub block_type: u8,
    pub kind: String,
    pub width_raw: u32,
    pub start_raw: [i32; 2],
    pub end_raw: [i32; 2],
    pub center_raw: Option<[f64; 2]>,
    pub radius_raw: Option<f64>,
    pub bbox_raw: Option<[i32; 4]>,
    pub clockwise: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Shape {
    pub key: u32,
    pub next: u32,
    pub layer: LayerInfo,
    pub first_segment: u32,
    pub first_keepout: u32,
    pub table: u32,
    pub coords_raw: [i32; 4],
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Keepout {
    pub key: u32,
    pub next: u32,
    pub layer: LayerInfo,
    pub flags: u32,
    pub first_segment: u32,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct NetAssignment {
    pub key: u32,
    pub next: u32,
    pub net: u32,
    pub conn_item: u32,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Text {
    pub key: u32,
    pub next: Option<u32>,
    pub layer: Option<LayerInfo>,
    pub text: Option<String>,
    pub x_raw: Option<i32>,
    pub y_raw: Option<i32>,
    pub rotation_mdeg: Option<u32>,
    pub string_graphic_key: Option<u32>,
}
