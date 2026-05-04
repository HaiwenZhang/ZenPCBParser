use super::components::PinNetKey;
use super::entity::{point_from_semantic, value_number, OdbPackage};
use super::formatting::{fmt, odb_token};
use super::model::{Point, SemanticShape};
use std::collections::BTreeMap;

impl<'a> OdbPackage<'a> {
    pub(super) fn push_feature_link(
        &mut self,
        net_id: Option<&str>,
        layer_name: &str,
        feature_index: usize,
        class_code: &str,
        subnet_type: &str,
        pin_key: Option<PinNetKey>,
    ) {
        let Some(net_id) = net_id else {
            return;
        };
        if !self.net_name_by_id.contains_key(net_id) {
            return;
        }
        self.feature_links.push(NetFeatureLink {
            net_id: net_id.to_string(),
            layer_name: layer_name.to_string(),
            feature_index,
            class_code: class_code.to_string(),
            subnet_type: subnet_type.to_string(),
            pin_key,
        });
    }

    pub(super) fn cadnet_text(&self) -> String {
        let mut text = String::from("H optimize n staggered n\n");
        for (index, (_net_id, net_name)) in self.net_names.iter().enumerate() {
            text.push_str(&format!("${} {}\n", index, odb_token(net_name)));
        }
        text.push_str("#\n#Netlist points\n#\n");
        for record in self.cadnet_records() {
            record.write(&mut text);
        }
        text
    }

    fn cadnet_records(&self) -> Vec<CadnetPointRecord> {
        let net_index_by_id: BTreeMap<&str, usize> = self
            .net_names
            .iter()
            .enumerate()
            .map(|(index, (net_id, _net_name))| (net_id.as_str(), index))
            .collect();
        let mut records = Vec::new();

        for pad in &self.board.pads {
            let Some(net_id) = pad.net_id.as_deref() else {
                continue;
            };
            let Some(net_index) = net_index_by_id.get(net_id).copied() else {
                continue;
            };
            let Some(position) = pad.position.as_ref().map(point_from_semantic) else {
                continue;
            };
            let side = pad
                .layer_name
                .as_deref()
                .and_then(cadnet_side_from_layer_name)
                .unwrap_or("T");
            if side == "I" {
                continue;
            }
            let shape = self.shape_for_pad(pad);
            let (x_size, y_size) = pad_size(shape, self.units);
            records.push(CadnetPointRecord {
                net_index,
                drill_size: 0.0,
                position: self.units.point(position),
                side: side.to_string(),
                pad_size: Some((x_size, y_size)),
                exposed: "c".to_string(),
                is_via: false,
            });
        }

        for via in &self.board.vias {
            let Some(net_id) = via.net_id.as_deref() else {
                continue;
            };
            let Some(net_index) = net_index_by_id.get(net_id).copied() else {
                continue;
            };
            let Some(position) = via.position.as_ref().map(point_from_semantic) else {
                continue;
            };
            let side = cadnet_side_from_via_layers(&via.layer_names);
            if side == "I" {
                continue;
            }
            records.push(CadnetPointRecord {
                net_index,
                drill_size: via_drill_size(self, via.template_id.as_deref()),
                position: self.units.point(position),
                side,
                pad_size: None,
                exposed: "c".to_string(),
                is_via: true,
            });
        }

        records.sort_by(|left, right| {
            left.net_index
                .cmp(&right.net_index)
                .then_with(|| left.position.x.total_cmp(&right.position.x))
                .then_with(|| left.position.y.total_cmp(&right.position.y))
                .then_with(|| left.is_via.cmp(&right.is_via))
        });
        records
    }
}

#[derive(Debug, Clone)]
pub(super) struct NetFeatureLink {
    pub(super) net_id: String,
    pub(super) layer_name: String,
    pub(super) feature_index: usize,
    pub(super) class_code: String,
    pub(super) subnet_type: String,
    pub(super) pin_key: Option<PinNetKey>,
}

struct CadnetPointRecord {
    net_index: usize,
    drill_size: f64,
    position: Point,
    side: String,
    pad_size: Option<(f64, f64)>,
    exposed: String,
    is_via: bool,
}

impl CadnetPointRecord {
    fn write(&self, text: &mut String) {
        text.push_str(&format!(
            "{} {} {} {} {} ",
            self.net_index,
            fmt(self.drill_size),
            fmt(self.position.x),
            fmt(self.position.y),
            self.side
        ));
        if let Some((x_size, y_size)) = self.pad_size {
            text.push_str(&format!("{} {} ", fmt(x_size), fmt(y_size)));
        }
        text.push_str("e ");
        text.push_str(&self.exposed);
        if self.pad_size.is_none() {
            text.push_str(" staggered 0 0 0");
        }
        if self.is_via {
            text.push_str(" v");
        }
        text.push('\n');
    }
}

fn pad_size(shape: Option<&SemanticShape>, units: super::model::UnitScale) -> (f64, f64) {
    let Some(shape) = shape else {
        return (0.0, 0.0);
    };
    let kind = if shape.auroradb_type.is_empty() {
        shape.kind.as_str()
    } else {
        shape.auroradb_type.as_str()
    }
    .replace('_', "")
    .to_ascii_lowercase();
    if kind == "circle" {
        let diameter = units.length(value_number(shape.values.get(2)).unwrap_or(0.0));
        return (diameter, diameter);
    }
    let width = units.length(value_number(shape.values.get(2)).unwrap_or(0.0));
    let height = units.length(value_number(shape.values.get(3)).unwrap_or(width));
    (width, height)
}

fn via_drill_size(package: &OdbPackage<'_>, template_id: Option<&str>) -> f64 {
    let template = template_id.and_then(|id| {
        package
            .board
            .via_templates
            .iter()
            .find(|template| template.id == id)
    });
    let drill_shape = template
        .and_then(|template| template.barrel_shape_id.as_deref())
        .and_then(|shape_id| package.shape_by_id.get(shape_id).copied())
        .or_else(|| {
            template.and_then(|template| {
                template.layer_pads.iter().find_map(|layer_pad| {
                    layer_pad
                        .pad_shape_id
                        .as_deref()
                        .and_then(|shape_id| package.shape_by_id.get(shape_id).copied())
                })
            })
        });
    pad_size(drill_shape, package.units).0
}

fn cadnet_side_from_layer_name(layer_name: &str) -> Option<&'static str> {
    let text = layer_name.to_ascii_lowercase();
    if text.contains("top") || text.starts_with('f') {
        Some("T")
    } else if text.contains("bot") || text.contains("bottom") || text.starts_with('b') {
        Some("D")
    } else {
        Some("I")
    }
}

fn cadnet_side_from_via_layers(layer_names: &[String]) -> String {
    let has_top = layer_names
        .iter()
        .any(|layer| cadnet_side_from_layer_name(layer) == Some("T"));
    let has_bottom = layer_names
        .iter()
        .any(|layer| cadnet_side_from_layer_name(layer) == Some("D"));
    if has_top && has_bottom {
        "B".to_string()
    } else if has_top {
        "T".to_string()
    } else if has_bottom {
        "D".to_string()
    } else {
        "I".to_string()
    }
}
