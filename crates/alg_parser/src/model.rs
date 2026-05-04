use serde::Serialize;
use std::collections::BTreeMap;

#[derive(Debug, Clone, Serialize)]
pub struct AlgLayout {
    pub metadata: Metadata,
    pub summary: Summary,
    pub board: Option<Board>,
    pub layers: Option<Vec<Layer>>,
    pub components: Option<Vec<Component>>,
    pub pins: Option<Vec<Pin>>,
    pub padstacks: Option<Vec<Padstack>>,
    pub pads: Option<Vec<Pad>>,
    pub vias: Option<Vec<Via>>,
    pub tracks: Option<Vec<Track>>,
    pub symbols: Option<Vec<Symbol>>,
    pub outlines: Option<Vec<Graphic>>,
    pub section_counts: BTreeMap<String, usize>,
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
    pub alg_revision: Option<String>,
    pub extracta_version: Option<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Summary {
    pub line_count: usize,
    pub section_count: usize,
    pub data_record_count: usize,
    pub board_record_count: usize,
    pub layer_count: usize,
    pub metal_layer_count: usize,
    pub component_count: usize,
    pub pin_count: usize,
    pub padstack_count: usize,
    pub pad_count: usize,
    pub via_count: usize,
    pub track_count: usize,
    pub net_count: usize,
    pub symbol_count: usize,
    pub outline_count: usize,
    pub diagnostic_count: usize,
    pub units: String,
    pub accuracy: Option<f64>,
    pub board_name: Option<String>,
    pub extracta_version: Option<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Board {
    pub name: String,
    pub units: String,
    pub accuracy: Option<f64>,
    pub extents: Option<Extents>,
    pub layer_count: Option<usize>,
    pub thickness: Option<String>,
    pub schematic_name: Option<String>,
}

#[derive(Debug, Clone, Copy, Serialize, Default)]
pub struct Extents {
    pub x1: f64,
    pub y1: f64,
    pub x2: f64,
    pub y2: f64,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Layer {
    pub sort: Option<String>,
    pub name: String,
    pub artwork: Option<String>,
    pub use_kind: Option<String>,
    pub conductor: bool,
    pub dielectric_constant: Option<String>,
    pub electrical_conductivity: Option<String>,
    pub loss_tangent: Option<String>,
    pub material: Option<String>,
    pub shield_layer: Option<String>,
    pub thermal_conductivity: Option<String>,
    pub thickness: Option<String>,
    pub layer_type: Option<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Component {
    pub refdes: String,
    pub class_name: Option<String>,
    pub package: Option<String>,
    pub device_type: Option<String>,
    pub value: Option<String>,
    pub part_number: Option<String>,
    pub room: Option<String>,
    pub bom_ignore: Option<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Pin {
    pub refdes: String,
    pub pin_number: String,
    pub x: Option<f64>,
    pub y: Option<f64>,
    pub pad_stack_name: Option<String>,
    pub pin_type: Option<String>,
    pub net_name: Option<String>,
    pub pin_name: Option<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Padstack {
    pub name: String,
    pub pad_stack_type: Option<String>,
    pub start_layer: Option<String>,
    pub end_layer: Option<String>,
    pub drill_hole_name: Option<String>,
    pub drill_figure_shape: Option<String>,
    pub drill_figure_width: Option<f64>,
    pub drill_figure_height: Option<f64>,
    pub drill_figure_rotation: Option<f64>,
    pub via_pad_stack_name: Option<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Pad {
    pub refdes: Option<String>,
    pub pin_number: Option<String>,
    pub layer_name: Option<String>,
    pub pad_stack_name: Option<String>,
    pub net_name: Option<String>,
    pub x: Option<f64>,
    pub y: Option<f64>,
    pub pad_type: Option<String>,
    pub shape: Option<Shape>,
    pub source_section: String,
    pub record_tag: Option<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Via {
    pub key: String,
    pub x: f64,
    pub y: f64,
    pub pad_stack_name: Option<String>,
    pub net_name: Option<String>,
    pub layer_names: Vec<String>,
    pub shape: Option<Shape>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Track {
    pub kind: String,
    pub layer_name: Option<String>,
    pub net_name: Option<String>,
    pub refdes: Option<String>,
    pub record_tag: Option<String>,
    pub geometry_role: Option<String>,
    pub width: Option<f64>,
    pub start: Option<Point>,
    pub end: Option<Point>,
    pub center: Option<Point>,
    pub clockwise: Option<bool>,
    pub bbox: Option<Extents>,
}

#[derive(Debug, Clone, Copy, Serialize, Default)]
pub struct Point {
    pub x: f64,
    pub y: f64,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Shape {
    pub kind: String,
    pub x: Option<f64>,
    pub y: Option<f64>,
    pub width: Option<f64>,
    pub height: Option<f64>,
    pub rotation: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Symbol {
    pub sym_type: Option<String>,
    pub sym_name: Option<String>,
    pub refdes: Option<String>,
    pub bbox: Option<Extents>,
    pub center: Option<Point>,
    pub mirror: Option<bool>,
    pub rotation: Option<f64>,
    pub location: Option<Point>,
    pub library_path: Option<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct Graphic {
    pub class_name: Option<String>,
    pub subclass: Option<String>,
    pub record_tag: Option<String>,
    pub kind: String,
    pub start: Option<Point>,
    pub end: Option<Point>,
    pub center: Option<Point>,
    pub clockwise: Option<bool>,
    pub bbox: Option<Extents>,
}
