use serde::Serialize;
use std::collections::BTreeMap;

#[derive(Debug, Clone, Serialize)]
pub struct OdbLayout {
    pub metadata: Metadata,
    pub summary: Summary,
    pub matrix: Option<Matrix>,
    pub steps: Vec<Step>,
    pub symbols: Option<Vec<SymbolDefinition>>,
    pub drill_tools: Option<Vec<DrillLayerTools>>,
    pub packages: Option<Vec<PackageDefinition>>,
    pub layers: Option<Vec<LayerFeatures>>,
    pub components: Option<Vec<Component>>,
    pub nets: Option<Vec<Net>>,
    pub diagnostics: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Metadata {
    pub project_version: String,
    pub parser_version: String,
    pub output_schema_version: String,
    pub source: String,
    pub source_type: String,
    pub selected_step: Option<String>,
    pub backend: String,
    pub rust_parser_version: String,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Summary {
    pub step_count: usize,
    pub layer_count: usize,
    pub board_layer_count: usize,
    pub signal_layer_count: usize,
    pub component_layer_count: usize,
    pub feature_layer_count: usize,
    pub feature_count: usize,
    pub symbol_count: usize,
    pub drill_tool_count: usize,
    pub package_count: usize,
    pub component_count: usize,
    pub net_count: usize,
    pub profile_record_count: usize,
    pub diagnostic_count: usize,
    pub step_names: Vec<String>,
    pub layer_names: Vec<String>,
    pub net_names: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Matrix {
    pub rows: Vec<MatrixRow>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct MatrixRow {
    pub row: Option<i64>,
    pub name: Option<String>,
    pub context: Option<String>,
    pub layer_type: Option<String>,
    pub polarity: Option<String>,
    pub side: Option<String>,
    pub start_name: Option<String>,
    pub end_name: Option<String>,
    pub raw_fields: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Step {
    pub name: String,
    pub profile: Option<Profile>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Profile {
    pub units: Option<String>,
    pub records: Vec<LineRecord>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct LayerFeatures {
    pub step_name: String,
    pub layer_name: String,
    pub units: Option<String>,
    pub layer_attributes: BTreeMap<String, String>,
    pub symbols: BTreeMap<String, String>,
    pub attributes: BTreeMap<String, String>,
    pub text_strings: BTreeMap<String, String>,
    pub features: Vec<Feature>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct SymbolDefinition {
    pub name: String,
    pub units: Option<String>,
    pub features: Vec<Feature>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct DrillLayerTools {
    pub step_name: String,
    pub layer_name: String,
    pub units: Option<String>,
    pub thickness: Option<f64>,
    pub user_params: Option<String>,
    pub raw_fields: BTreeMap<String, String>,
    pub tools: Vec<DrillTool>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct DrillTool {
    pub number: Option<i64>,
    pub tool_type: Option<String>,
    pub type2: Option<String>,
    pub finish_size: Option<f64>,
    pub drill_size: Option<f64>,
    pub raw_fields: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct PackageDefinition {
    pub step_name: String,
    pub line_number: usize,
    pub package_index: Option<i64>,
    pub name: Option<String>,
    pub feature_id: Option<String>,
    pub pitch: Option<f64>,
    pub bounds: Option<PackageBounds>,
    pub properties: BTreeMap<String, String>,
    pub outlines: Vec<PackageShape>,
    pub pins: Vec<PackagePin>,
    pub tokens: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct PackageBounds {
    pub min: Point,
    pub max: Point,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct PackagePin {
    pub line_number: usize,
    pub name: Option<String>,
    pub side: Option<String>,
    pub position: Option<Point>,
    pub rotation: Option<f64>,
    pub electrical_type: Option<String>,
    pub mount_type: Option<String>,
    pub feature_id: Option<String>,
    pub shapes: Vec<PackageShape>,
    pub tokens: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct PackageShape {
    pub line_number: usize,
    pub kind: String,
    pub tokens: Vec<String>,
    pub center: Option<Point>,
    pub width: Option<f64>,
    pub height: Option<f64>,
    pub radius: Option<f64>,
    pub size: Option<f64>,
    pub contours: Vec<SurfaceContour>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Feature {
    pub feature_index: usize,
    pub kind: String,
    pub line_number: usize,
    pub tokens: Vec<String>,
    pub feature_id: Option<String>,
    pub attributes: BTreeMap<String, String>,
    pub polarity: Option<String>,
    pub symbol: Option<String>,
    pub start: Option<Point>,
    pub end: Option<Point>,
    pub center: Option<Point>,
    pub contours: Vec<SurfaceContour>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct SurfaceContour {
    pub polarity: Option<String>,
    pub vertices: Vec<ContourVertex>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct ContourVertex {
    pub record_type: String,
    pub point: Point,
    pub center: Option<Point>,
    pub clockwise: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Component {
    pub step_name: String,
    pub layer_name: String,
    pub line_number: usize,
    pub record_type: String,
    pub component_index: Option<i64>,
    pub package_index: Option<i64>,
    pub refdes: Option<String>,
    pub package_name: Option<String>,
    pub part_name: Option<String>,
    pub location: Option<Point>,
    pub rotation: Option<f64>,
    pub mirror: Option<String>,
    pub properties: BTreeMap<String, String>,
    pub pins: Vec<ComponentPin>,
    pub tokens: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct ComponentPin {
    pub line_number: usize,
    pub record_type: String,
    pub pin_index: Option<i64>,
    pub name: Option<String>,
    pub position: Option<Point>,
    pub rotation: Option<f64>,
    pub mirror: Option<String>,
    pub net_component_index: Option<i64>,
    pub net_pin_index: Option<i64>,
    pub tokens: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Net {
    pub step_name: String,
    pub name: String,
    pub source_file: String,
    pub line_number: usize,
    pub tokens: Vec<String>,
    pub feature_refs: Vec<NetFeatureRef>,
    pub pin_refs: Vec<NetPinRef>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct NetFeatureRef {
    pub line_number: usize,
    pub subnet_type: Option<String>,
    pub class_code: String,
    pub layer_index: Option<i64>,
    pub layer_name: Option<String>,
    pub feature_index: Option<usize>,
    pub pin_side: Option<String>,
    pub net_component_index: Option<i64>,
    pub net_pin_index: Option<i64>,
    pub tokens: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct NetPinRef {
    pub line_number: usize,
    pub side: Option<String>,
    pub net_component_index: Option<i64>,
    pub net_pin_index: Option<i64>,
    pub tokens: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct LineRecord {
    pub line_number: usize,
    pub kind: String,
    pub tokens: Vec<String>,
}

#[derive(Debug, Clone, Copy, Serialize, Default)]
pub struct Point {
    pub x: f64,
    pub y: f64,
}
