use super::attributes::empty_feature_attribute_tables_text;
use super::entity::{MatrixLayer, OdbPackage, RUST_EXPORTER_VERSION};
use super::formatting::{fmt, odb_token, write_kv};
use std::collections::BTreeMap;

impl<'a> OdbPackage<'a> {
    pub(super) fn eda_data_text(&self) -> String {
        let layer_index = eda_layer_index(&self.matrix_layers);
        let mut text = String::new();
        text.push_str("# Aurora Translator ODB++ export\n");
        text.push_str(&format!(
            "HDR Aurora_Translator {}\n",
            RUST_EXPORTER_VERSION
        ));
        write_kv(&mut text, "UNITS", self.units.odb_units);
        text.push_str("LYR");
        for name in &layer_index.names {
            text.push(' ');
            text.push_str(name);
        }
        text.push('\n');
        text.push_str(&empty_feature_attribute_tables_text());

        for (net_id, net_name) in &self.net_names {
            text.push_str(&format!("NET {}\n", odb_token(net_name)));
            for pin in self
                .components
                .iter()
                .flat_map(|component| component.pins.iter())
                .filter(|pin| pin.net_id.as_deref() == Some(net_id.as_str()))
            {
                text.push_str(&format!(
                    "SNT TOP {} {} {}\n",
                    pin.key.side, pin.key.component_index, pin.key.pin_index
                ));
            }
            for link in self
                .feature_links
                .iter()
                .filter(|link| link.net_id == *net_id)
            {
                if let Some(pin_key) = &link.pin_key {
                    text.push_str(&format!(
                        "SNT TOP {} {} {}\n",
                        pin_key.side, pin_key.component_index, pin_key.pin_index
                    ));
                } else {
                    text.push_str(&format!("SNT {}\n", link.subnet_type));
                }
                if let Some(index) = layer_index.by_name.get(&link.layer_name) {
                    text.push_str(&format!(
                        "FID {} {} {}\n",
                        link.class_code, index, link.feature_index
                    ));
                }
            }
        }

        for package in &self.packages {
            text.push_str(&format!("# PKG {}\n", package.index));
            text.push_str(&format!(
                "PKG {} {} {} {} {} {};\n",
                package.name,
                fmt(package.pitch),
                fmt(package.bounds.min.x),
                fmt(package.bounds.min.y),
                fmt(package.bounds.max.x),
                fmt(package.bounds.max.y)
            ));
            for outline in &package.outlines {
                outline.write_package_shape(&mut text);
            }
            for pin in &package.pins {
                text.push_str(&format!(
                    "PIN {} S {} {} {} {} {}\n",
                    pin.name,
                    fmt(pin.position.x),
                    fmt(pin.position.y),
                    fmt(pin.rotation),
                    pin.electrical_type,
                    pin.mount_type
                ));
                for shape in &pin.shapes {
                    shape.write_package_shape(&mut text);
                }
            }
            text.push_str("#\n");
        }
        text
    }
}

struct EdaLayerIndex {
    names: Vec<String>,
    by_name: BTreeMap<String, usize>,
}

fn eda_layer_index(matrix_layers: &[MatrixLayer]) -> EdaLayerIndex {
    let mut names = Vec::new();
    let mut by_name = BTreeMap::new();
    for layer in matrix_layers {
        if layer.layer_type == "SIGNAL" || layer.layer_type == "DRILL" {
            let index = names.len();
            names.push(layer.name.clone());
            by_name.insert(layer.name.clone(), index);
        }
    }
    EdaLayerIndex { names, by_name }
}
