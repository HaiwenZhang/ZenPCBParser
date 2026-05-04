use serde::Serialize;
use std::collections::BTreeMap;

#[derive(Debug, Clone, Serialize)]
pub struct AltiumLayout {
    pub metadata: Metadata,
    pub summary: Summary,
    pub file_header: Option<String>,
    pub board: Option<Board>,
    pub layers: Option<Vec<Layer>>,
    pub nets: Option<Vec<Net>>,
    pub classes: Option<Vec<Class>>,
    pub rules: Option<Vec<Rule>>,
    pub polygons: Option<Vec<Polygon>>,
    pub components: Option<Vec<Component>>,
    pub pads: Option<Vec<Pad>>,
    pub vias: Option<Vec<Via>>,
    pub tracks: Option<Vec<Track>>,
    pub arcs: Option<Vec<Arc>>,
    pub fills: Option<Vec<Fill>>,
    pub regions: Option<Vec<Region>>,
    pub texts: Option<Vec<Text>>,
    pub streams: Option<Vec<StreamSummary>>,
    pub stream_counts: BTreeMap<String, usize>,
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
    pub stream_count: usize,
    pub parsed_stream_count: usize,
    pub layer_count: usize,
    pub net_count: usize,
    pub class_count: usize,
    pub rule_count: usize,
    pub polygon_count: usize,
    pub component_count: usize,
    pub pad_count: usize,
    pub via_count: usize,
    pub track_count: usize,
    pub arc_count: usize,
    pub fill_count: usize,
    pub region_count: usize,
    pub text_count: usize,
    pub board_outline_vertex_count: usize,
    pub diagnostic_count: usize,
    pub units: String,
    pub format: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct StreamSummary {
    pub path: String,
    pub size: usize,
    pub parsed: bool,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Board {
    pub sheet_position: Option<Point>,
    pub sheet_size: Option<Size>,
    pub layer_count_declared: Option<i32>,
    pub outline: Vec<Vertex>,
    pub properties: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Layer {
    pub layer_id: u32,
    pub name: String,
    pub next_id: Option<usize>,
    pub prev_id: Option<usize>,
    pub copper_thickness: Option<f64>,
    pub dielectric_constant: Option<f64>,
    pub dielectric_thickness: Option<f64>,
    pub dielectric_material: Option<String>,
    pub mechanical_enabled: bool,
    pub mechanical_kind: Option<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Net {
    pub index: usize,
    pub name: String,
    pub properties: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Class {
    pub index: usize,
    pub name: String,
    pub unique_id: Option<String>,
    pub kind: i32,
    pub members: Vec<String>,
    pub properties: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Rule {
    pub index: usize,
    pub name: String,
    pub kind: String,
    pub priority: i32,
    pub scope1_expression: Option<String>,
    pub scope2_expression: Option<String>,
    pub properties: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Component {
    pub index: usize,
    pub layer_id: u32,
    pub layer_name: String,
    pub position: Point,
    pub rotation: f64,
    pub locked: bool,
    pub name_on: bool,
    pub comment_on: bool,
    pub source_designator: Option<String>,
    pub source_unique_id: Option<String>,
    pub source_hierarchical_path: Option<String>,
    pub source_footprint_library: Option<String>,
    pub pattern: Option<String>,
    pub source_component_library: Option<String>,
    pub source_lib_reference: Option<String>,
    pub properties: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Pad {
    pub index: usize,
    pub name: String,
    pub layer_id: u32,
    pub layer_name: String,
    pub net: u16,
    pub component: u16,
    pub position: Point,
    pub top_size: Size,
    pub mid_size: Size,
    pub bottom_size: Size,
    pub hole_size: f64,
    pub top_shape: String,
    pub mid_shape: String,
    pub bottom_shape: String,
    pub direction: f64,
    pub plated: bool,
    pub pad_mode: String,
    pub hole_rotation: f64,
    pub from_layer_id: Option<u32>,
    pub to_layer_id: Option<u32>,
    pub size_and_shape: Option<PadSizeAndShape>,
    pub is_locked: bool,
    pub is_tent_top: bool,
    pub is_tent_bottom: bool,
    pub is_test_fab_top: bool,
    pub is_test_fab_bottom: bool,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct PadSizeAndShape {
    pub hole_shape: String,
    pub slot_size: f64,
    pub slot_rotation: f64,
    pub inner_sizes: Vec<Size>,
    pub inner_shapes: Vec<String>,
    pub hole_offsets: Vec<Point>,
    pub alternate_shapes: Vec<String>,
    pub corner_radii: Vec<u8>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Via {
    pub index: usize,
    pub net: u16,
    pub position: Point,
    pub diameter: f64,
    pub hole_size: f64,
    pub start_layer_id: u32,
    pub start_layer_name: String,
    pub end_layer_id: u32,
    pub end_layer_name: String,
    pub via_mode: String,
    pub diameter_by_layer: Vec<f64>,
    pub is_locked: bool,
    pub is_tent_top: bool,
    pub is_tent_bottom: bool,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Track {
    pub index: usize,
    pub layer_id: u32,
    pub layer_name: String,
    pub net: u16,
    pub component: u16,
    pub polygon: u16,
    pub subpolygon: u16,
    pub start: Point,
    pub end: Point,
    pub width: f64,
    pub is_locked: bool,
    pub is_keepout: bool,
    pub is_polygon_outline: bool,
    pub keepout_restrictions: u8,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Arc {
    pub index: usize,
    pub layer_id: u32,
    pub layer_name: String,
    pub net: u16,
    pub component: u16,
    pub polygon: u16,
    pub subpolygon: u16,
    pub center: Point,
    pub radius: f64,
    pub start_angle: f64,
    pub end_angle: f64,
    pub width: f64,
    pub is_locked: bool,
    pub is_keepout: bool,
    pub is_polygon_outline: bool,
    pub keepout_restrictions: u8,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Fill {
    pub index: usize,
    pub layer_id: u32,
    pub layer_name: String,
    pub component: u16,
    pub net: u16,
    pub position1: Point,
    pub position2: Point,
    pub rotation: f64,
    pub is_locked: bool,
    pub is_keepout: bool,
    pub keepout_restrictions: u8,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Region {
    pub index: usize,
    pub layer_id: u32,
    pub layer_name: String,
    pub net: u16,
    pub component: u16,
    pub polygon: u16,
    pub subpolygon: u16,
    pub kind: String,
    pub outline: Vec<Vertex>,
    pub holes: Vec<Vec<Vertex>>,
    pub is_locked: bool,
    pub is_keepout: bool,
    pub is_shape_based: bool,
    pub keepout_restrictions: u8,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Polygon {
    pub index: usize,
    pub layer_id: u32,
    pub layer_name: String,
    pub net: u16,
    pub locked: bool,
    pub hatch_style: String,
    pub grid_size: Option<f64>,
    pub track_width: Option<f64>,
    pub min_primitive_length: Option<f64>,
    pub use_octagons: bool,
    pub pour_index: i32,
    pub vertices: Vec<Vertex>,
    pub properties: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Text {
    pub index: usize,
    pub layer_id: u32,
    pub layer_name: String,
    pub component: u16,
    pub position: Point,
    pub height: f64,
    pub rotation: f64,
    pub stroke_width: f64,
    pub font_type: String,
    pub font_name: Option<String>,
    pub text: String,
    pub is_bold: bool,
    pub is_italic: bool,
    pub is_mirrored: bool,
    pub is_comment: bool,
    pub is_designator: bool,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Point {
    pub x_raw: i32,
    pub y_raw: i32,
    pub x: f64,
    pub y: f64,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Size {
    pub x_raw: i32,
    pub y_raw: i32,
    pub x: f64,
    pub y: f64,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Vertex {
    pub is_round: bool,
    pub radius: f64,
    pub start_angle: f64,
    pub end_angle: f64,
    pub position: Point,
    pub center: Option<Point>,
}
