use super::entity::{MatrixLayer, OdbPackage};
use super::formatting::{fmt, legal_entity_name};
use super::model::{SemanticLayer, SemanticMaterial, UnitScale};
use serde_json::Value;

#[derive(Debug, Clone, Default)]
pub(super) struct AttributeTables {
    feature_names: Vec<String>,
    feature_texts: Vec<String>,
}

impl AttributeTables {
    pub(super) fn empty() -> Self {
        Self::default()
    }

    pub(super) fn to_tables_text(&self) -> String {
        let mut text = String::new();
        text.push_str("#\n#Feature attribute names\n#\n");
        for (index, name) in self.feature_names.iter().enumerate() {
            text.push_str(&format!("@{} {}\n", index, name));
        }
        text.push_str("#\n#Feature attribute text strings\n#\n");
        for (index, value) in self.feature_texts.iter().enumerate() {
            text.push_str(&format!("&{} {}\n", index, value));
        }
        text
    }
}

impl<'a> OdbPackage<'a> {
    pub(super) fn layer_attrlist_text(&self, layer_name: &str) -> String {
        let layer = self.semantic_layer_for_odb_layer(layer_name);
        let Some(matrix_layer) = self
            .matrix_layers
            .iter()
            .find(|matrix_layer| matrix_layer.name == layer_name)
        else {
            return String::new();
        };
        layer_attrlist_text(
            layer,
            matrix_layer,
            self.material_for_layer(layer),
            self.units,
        )
    }

    fn semantic_layer_for_odb_layer(&self, layer_name: &str) -> Option<&SemanticLayer> {
        self.board.layers.iter().find(|layer| {
            self.layer_name_map
                .get(&layer.id)
                .or_else(|| self.layer_name_map.get(&layer.name))
                .is_some_and(|mapped| mapped == layer_name)
        })
    }

    fn material_for_layer(&self, layer: Option<&SemanticLayer>) -> Option<&SemanticMaterial> {
        let layer = layer?;
        layer
            .material_id
            .as_deref()
            .or(layer.fill_material_id.as_deref())
            .and_then(|id| {
                self.board
                    .materials
                    .iter()
                    .find(|material| material.id == id)
            })
    }
}

pub(super) fn empty_feature_attribute_tables_text() -> String {
    AttributeTables::empty().to_tables_text()
}

fn layer_attrlist_text(
    layer: Option<&SemanticLayer>,
    matrix_layer: &MatrixLayer,
    material: Option<&SemanticMaterial>,
    units: UnitScale,
) -> String {
    let mut text = String::new();
    let Some(layer) = layer else {
        return text;
    };

    if let Some(thickness) = layer.thickness.as_ref().and_then(value_number) {
        text.push_str(&format!(
            ".layer_dielectric={}\n",
            fmt(units.length(thickness))
        ));
        if matrix_layer.layer_type == "SIGNAL" || matrix_layer.layer_type == "POWER_GROUND" {
            let copper_weight_oz = units.length_mm(thickness) / 0.035;
            if copper_weight_oz.is_finite() && copper_weight_oz > 0.0 {
                text.push_str(&format!(".copper_weight={}\n", fmt(copper_weight_oz)));
            }
        }
    }

    if let Some(permittivity) = material
        .and_then(|material| material.permittivity.as_ref())
        .and_then(value_number)
    {
        text.push_str(&format!(".dielectric_constant={}\n", fmt(permittivity)));
    }

    if let Some(loss_tangent) = material
        .and_then(|material| material.dielectric_loss_tangent.as_ref())
        .and_then(value_number)
    {
        text.push_str(&format!(".loss_tangent={}\n", fmt(loss_tangent)));
    }

    let material_name = layer
        .material
        .as_deref()
        .or(layer.fill_material.as_deref())
        .or(material.map(|material| material.name.as_str()));
    if let Some(material_name) = material_name.filter(|value| !value.trim().is_empty()) {
        text.push_str(&format!(".material={}\n", legal_entity_name(material_name)));
    }

    text
}

fn value_number(value: &Value) -> Option<f64> {
    value.as_f64().or_else(|| {
        value
            .as_str()
            .and_then(|text| parse_leading_number(text.trim()))
    })
}

fn parse_leading_number(text: &str) -> Option<f64> {
    let mut end = 0;
    for (index, ch) in text.char_indices() {
        if ch.is_ascii_digit() || matches!(ch, '+' | '-' | '.' | 'e' | 'E') {
            end = index + ch.len_utf8();
        } else if end > 0 {
            break;
        }
    }
    (end > 0).then(|| text[..end].parse::<f64>().ok())?
}
