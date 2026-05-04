use serde::Deserialize;
use serde_json::Value;

#[derive(Debug, Clone, Default, Deserialize)]
pub struct SemanticBoard {
    #[serde(default)]
    pub(super) metadata: SemanticMetadata,
    #[serde(default)]
    pub(super) units: Option<String>,
    #[serde(default)]
    pub(super) layers: Vec<SemanticLayer>,
    #[serde(default)]
    pub(super) materials: Vec<SemanticMaterial>,
    #[serde(default)]
    pub(super) shapes: Vec<SemanticShape>,
    #[serde(default)]
    pub(super) via_templates: Vec<SemanticViaTemplate>,
    #[serde(default)]
    pub(super) nets: Vec<SemanticNet>,
    #[serde(default)]
    pub(super) components: Vec<SemanticComponent>,
    #[serde(default)]
    pub(super) footprints: Vec<SemanticFootprint>,
    #[serde(default)]
    pub(super) pins: Vec<SemanticPin>,
    #[serde(default)]
    pub(super) pads: Vec<SemanticPad>,
    #[serde(default)]
    pub(super) vias: Vec<SemanticVia>,
    #[serde(default)]
    pub(super) primitives: Vec<SemanticPrimitive>,
    #[serde(default)]
    pub(super) board_outline: Value,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub(super) struct SemanticMetadata {
    #[serde(default)]
    pub(super) source_format: Option<String>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub(super) struct SourceRef {
    #[serde(default)]
    pub(super) raw_id: Option<String>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub(super) struct SemanticPoint {
    pub(super) x: f64,
    pub(super) y: f64,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub(super) struct SemanticLayer {
    pub(super) id: String,
    pub(super) name: String,
    #[serde(default)]
    pub(super) layer_type: Option<String>,
    #[serde(default)]
    pub(super) role: Option<String>,
    #[serde(default)]
    pub(super) side: Option<String>,
    #[serde(default)]
    pub(super) order_index: Option<i64>,
    #[serde(default)]
    pub(super) material: Option<String>,
    #[serde(default)]
    pub(super) material_id: Option<String>,
    #[serde(default)]
    pub(super) fill_material: Option<String>,
    #[serde(default)]
    pub(super) fill_material_id: Option<String>,
    #[serde(default)]
    pub(super) thickness: Option<Value>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub(super) struct SemanticMaterial {
    pub(super) id: String,
    pub(super) name: String,
    #[serde(default)]
    pub(super) permittivity: Option<Value>,
    #[serde(default)]
    pub(super) dielectric_loss_tangent: Option<Value>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub(super) struct SemanticShape {
    pub(super) id: String,
    #[serde(default)]
    pub(super) name: Option<String>,
    pub(super) kind: String,
    #[serde(default)]
    pub(super) auroradb_type: String,
    #[serde(default)]
    pub(super) values: Vec<Value>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub(super) struct SemanticViaTemplateLayer {
    pub(super) layer_name: String,
    #[serde(default)]
    pub(super) pad_shape_id: Option<String>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub(super) struct SemanticViaTemplate {
    pub(super) id: String,
    #[serde(default)]
    pub(super) barrel_shape_id: Option<String>,
    #[serde(default)]
    pub(super) layer_pads: Vec<SemanticViaTemplateLayer>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub(super) struct SemanticNet {
    pub(super) id: String,
    pub(super) name: String,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub(super) struct SemanticFootprint {
    pub(super) id: String,
    pub(super) name: String,
    #[serde(default)]
    pub(super) part_name: Option<String>,
    #[serde(default)]
    pub(super) pad_ids: Vec<String>,
    #[serde(default)]
    pub(super) geometry: Value,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub(super) struct SemanticComponent {
    pub(super) id: String,
    #[serde(default)]
    pub(super) refdes: Option<String>,
    #[serde(default)]
    pub(super) name: Option<String>,
    #[serde(default)]
    pub(super) part_name: Option<String>,
    #[serde(default)]
    pub(super) package_name: Option<String>,
    #[serde(default)]
    pub(super) footprint_id: Option<String>,
    #[serde(default)]
    pub(super) layer_name: Option<String>,
    #[serde(default)]
    pub(super) side: Option<String>,
    #[serde(default)]
    pub(super) location: Option<SemanticPoint>,
    #[serde(default)]
    pub(super) rotation: Option<Value>,
    #[serde(default)]
    pub(super) pin_ids: Vec<String>,
    #[serde(default)]
    pub(super) pad_ids: Vec<String>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub(super) struct SemanticPin {
    pub(super) id: String,
    #[serde(default)]
    pub(super) name: Option<String>,
    #[serde(default)]
    pub(super) net_id: Option<String>,
    #[serde(default)]
    pub(super) pad_ids: Vec<String>,
    #[serde(default)]
    pub(super) position: Option<SemanticPoint>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub(super) struct SemanticPad {
    pub(super) id: String,
    #[serde(default)]
    pub(super) name: Option<String>,
    #[serde(default)]
    pub(super) footprint_id: Option<String>,
    #[serde(default)]
    pub(super) component_id: Option<String>,
    #[serde(default)]
    pub(super) pin_id: Option<String>,
    #[serde(default)]
    pub(super) net_id: Option<String>,
    #[serde(default)]
    pub(super) layer_name: Option<String>,
    #[serde(default)]
    pub(super) position: Option<SemanticPoint>,
    #[serde(default)]
    pub(super) padstack_definition: Option<String>,
    #[serde(default)]
    pub(super) geometry: Value,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub(super) struct SemanticVia {
    pub(super) id: String,
    #[serde(default)]
    pub(super) template_id: Option<String>,
    #[serde(default)]
    pub(super) net_id: Option<String>,
    #[serde(default)]
    pub(super) layer_names: Vec<String>,
    #[serde(default)]
    pub(super) position: Option<SemanticPoint>,
    #[serde(default)]
    pub(super) geometry: Value,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub(super) struct SemanticPrimitive {
    pub(super) id: String,
    pub(super) kind: String,
    #[serde(default)]
    pub(super) layer_name: Option<String>,
    #[serde(default)]
    pub(super) net_id: Option<String>,
    #[serde(default)]
    pub(super) geometry: Value,
    #[serde(default)]
    pub(super) source: SourceRef,
}

#[derive(Debug, Clone, Copy)]
pub(super) struct UnitScale {
    pub(super) odb_units: &'static str,
    factor: f64,
    mm_factor: f64,
}

impl UnitScale {
    pub(super) fn from_semantic_units(value: Option<&str>) -> Self {
        let text = value.unwrap_or("mm").trim().to_ascii_lowercase();
        match text.as_str() {
            "m" | "meter" | "meters" => Self {
                odb_units: "MM",
                factor: 1000.0,
                mm_factor: 1000.0,
            },
            "mil" | "mils" => Self {
                odb_units: "INCH",
                factor: 0.001,
                mm_factor: 0.0254,
            },
            "inch" | "inches" | "in" | "inch." => Self {
                odb_units: "INCH",
                factor: 1.0,
                mm_factor: 25.4,
            },
            _ => Self {
                odb_units: "MM",
                factor: 1.0,
                mm_factor: 1.0,
            },
        }
    }

    pub(super) fn length(&self, value: f64) -> f64 {
        value * self.factor
    }

    pub(super) fn length_mm(&self, value: f64) -> f64 {
        value * self.mm_factor
    }

    pub(super) fn point(&self, point: Point) -> Point {
        Point {
            x: self.length(point.x),
            y: self.length(point.y),
        }
    }
}

#[derive(Debug, Clone, Copy, Default)]
pub(super) struct Point {
    pub(super) x: f64,
    pub(super) y: f64,
}
