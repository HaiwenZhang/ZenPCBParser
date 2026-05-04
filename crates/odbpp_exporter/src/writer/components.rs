use super::attributes::empty_feature_attribute_tables_text;
use super::entity::{point_from_semantic, rotation_to_odb_degrees, OdbPackage};
use super::formatting::{fmt, legal_component_name, legal_scalar};
use super::model::{Point, SemanticComponent, SemanticPad, SemanticPin};
use super::package::{PackageBounds, PackageOut};
use std::collections::HashMap;

impl<'a> OdbPackage<'a> {
    pub(super) fn build_components(&mut self) {
        let pin_by_id: HashMap<&str, &SemanticPin> = self
            .board
            .pins
            .iter()
            .map(|pin| (pin.id.as_str(), pin))
            .collect();
        let pad_by_id: HashMap<&str, &SemanticPad> = self
            .board
            .pads
            .iter()
            .map(|pad| (pad.id.as_str(), pad))
            .collect();
        let mut ordered: Vec<&SemanticComponent> = self.board.components.iter().collect();
        ordered.sort_by_key(|component| {
            legal_scalar(
                component
                    .refdes
                    .as_deref()
                    .or(component.name.as_deref())
                    .unwrap_or(component.id.as_str()),
            )
            .to_ascii_lowercase()
        });

        for component in ordered {
            let component_index = self.components.len();
            let side = component_side(component);
            let component_layer = if side == "bottom" {
                "COMP_+_BOT"
            } else {
                "COMP_+_TOP"
            };
            let package_index = self.package_index_for_component(component);
            let location = component
                .location
                .as_ref()
                .map(point_from_semantic)
                .map(|point| self.units.point(point))
                .unwrap_or_default();
            let rotation =
                rotation_to_odb_degrees(component.rotation.as_ref(), &self.source_format);
            let mirror = if side == "bottom" { "M" } else { "N" }.to_string();
            let refdes = legal_component_name(
                component
                    .refdes
                    .as_deref()
                    .or(component.name.as_deref())
                    .unwrap_or(component.id.as_str()),
            );
            let part_name = legal_scalar(
                component
                    .part_name
                    .as_deref()
                    .or(component.package_name.as_deref())
                    .unwrap_or("Unknown"),
            );
            let mut pins = Vec::new();

            for pin_id in &component.pin_ids {
                if let Some(pin) = pin_by_id.get(pin_id.as_str()).copied() {
                    let index = pins.len();
                    let out =
                        self.component_pin_from_pin(pin, index, component_index, &pad_by_id, side);
                    self.pin_key_by_id.insert(pin.id.clone(), out.key.clone());
                    pins.push(out);
                }
            }

            if pins.is_empty() {
                for pad_id in &component.pad_ids {
                    let Some(pad) = pad_by_id.get(pad_id.as_str()).copied() else {
                        continue;
                    };
                    let index = pins.len();
                    let pin_name = pad.name.as_deref().unwrap_or(pad.id.as_str());
                    let position = pad
                        .position
                        .as_ref()
                        .map(point_from_semantic)
                        .map(|point| self.units.point(point))
                        .unwrap_or(location);
                    let key = PinNetKey {
                        side: if side == "bottom" { "B" } else { "T" }.to_string(),
                        component_index,
                        pin_index: index,
                    };
                    if let Some(pin_id) = pad.pin_id.as_deref() {
                        self.pin_key_by_id.insert(pin_id.to_string(), key.clone());
                    }
                    pins.push(ComponentPinOut {
                        index,
                        name: legal_scalar(pin_name),
                        position,
                        rotation: 0.0,
                        mirror: mirror.clone(),
                        net_id: pad.net_id.clone(),
                        key,
                    });
                }
            }

            self.components.push(ComponentOut {
                index: component_index,
                layer_name: component_layer.to_string(),
                package_index,
                refdes,
                part_name,
                package_name: component.package_name.clone(),
                location,
                rotation,
                mirror,
                pins,
            });
        }
    }

    fn package_index_for_component(&mut self, component: &SemanticComponent) -> usize {
        if let Some(footprint_id) = component.footprint_id.as_deref() {
            if let Some(index) = self.package_index_by_footprint_id.get(footprint_id) {
                return *index;
            }
        }
        if let Some(name) = component.package_name.as_deref() {
            if let Some(index) = self.package_index_by_name.get(&name.to_ascii_lowercase()) {
                return *index;
            }
        }
        let index = self.packages.len();
        let name = legal_scalar(
            component
                .package_name
                .as_deref()
                .or(component.part_name.as_deref())
                .unwrap_or("Unknown"),
        );
        self.packages.push(PackageOut {
            index,
            name: name.clone(),
            pitch: 1.0,
            bounds: PackageBounds {
                min: Point { x: -0.5, y: -0.5 },
                max: Point { x: 0.5, y: 0.5 },
            },
            outlines: Vec::new(),
            pins: Vec::new(),
        });
        self.package_index_by_name
            .entry(name.to_ascii_lowercase())
            .or_insert(index);
        index
    }

    fn component_pin_from_pin(
        &self,
        pin: &SemanticPin,
        index: usize,
        component_index: usize,
        pad_by_id: &HashMap<&str, &SemanticPad>,
        side: &str,
    ) -> ComponentPinOut {
        let position = pin
            .position
            .as_ref()
            .map(point_from_semantic)
            .or_else(|| {
                pin.pad_ids.iter().find_map(|pad_id| {
                    pad_by_id
                        .get(pad_id.as_str())
                        .and_then(|pad| pad.position.as_ref())
                        .map(point_from_semantic)
                })
            })
            .map(|point| self.units.point(point))
            .unwrap_or_default();
        let net_id = pin.net_id.clone().or_else(|| {
            pin.pad_ids.iter().find_map(|pad_id| {
                pad_by_id
                    .get(pad_id.as_str())
                    .and_then(|pad| pad.net_id.clone())
            })
        });
        let key = PinNetKey {
            side: if side == "bottom" { "B" } else { "T" }.to_string(),
            component_index,
            pin_index: index,
        };
        ComponentPinOut {
            index,
            name: legal_scalar(pin.name.as_deref().unwrap_or(pin.id.as_str())),
            position,
            rotation: 0.0,
            mirror: if side == "bottom" { "M" } else { "N" }.to_string(),
            net_id,
            key,
        }
    }

    pub(super) fn components_text(&self, side_layer: &str) -> String {
        let mut text = String::new();
        let pin_net_subnets = self.component_pin_net_subnets();
        super::formatting::write_kv(&mut text, "UNITS", self.units.odb_units);
        text.push_str(&empty_feature_attribute_tables_text());
        for component in self
            .components
            .iter()
            .filter(|component| component.layer_name == side_layer)
        {
            text.push_str(&format!("# CMP {}\n", component.index));
            text.push_str(&format!(
                "CMP {} {} {} {} {} {} {}\n",
                component.package_index,
                fmt(component.location.x),
                fmt(component.location.y),
                fmt(component.rotation),
                component.mirror,
                component.refdes,
                component.part_name
            ));
            if let Some(package_name) = &component.package_name {
                text.push_str(&format!(
                    "PRP PACKAGE_NAME {}\n",
                    legal_scalar(package_name)
                ));
            }
            for pin in &component.pins {
                let (net_num, subnet_num) =
                    pin_net_subnets.get(&pin.key).copied().unwrap_or((0, 0));
                text.push_str(&format!(
                    "TOP {} {} {} {} {} {} {} {}\n",
                    pin.index,
                    fmt(pin.position.x),
                    fmt(pin.position.y),
                    fmt(pin.rotation),
                    pin.mirror,
                    net_num,
                    subnet_num,
                    pin.name
                ));
            }
            text.push_str("#\n");
        }
        text
    }

    fn component_pin_net_subnets(&self) -> HashMap<PinNetKey, (usize, usize)> {
        let net_index_by_id: HashMap<String, usize> = self
            .net_names
            .iter()
            .enumerate()
            .map(|(index, (net_id, _net_name))| (net_id.clone(), index))
            .collect();
        let mut subnet_count_by_net_id: HashMap<String, usize> = HashMap::new();
        let mut result = HashMap::new();
        for pin in self
            .components
            .iter()
            .flat_map(|component| component.pins.iter())
        {
            let Some(net_id) = pin.net_id.as_ref() else {
                continue;
            };
            let Some(net_index) = net_index_by_id.get(net_id).copied() else {
                continue;
            };
            let subnet_index = subnet_count_by_net_id.entry(net_id.clone()).or_insert(0);
            result.insert(pin.key.clone(), (net_index, *subnet_index));
            *subnet_index += 1;
        }
        result
    }
}

#[derive(Debug, Clone)]
pub(super) struct ComponentOut {
    pub(super) index: usize,
    pub(super) layer_name: String,
    pub(super) package_index: usize,
    pub(super) refdes: String,
    pub(super) part_name: String,
    pub(super) package_name: Option<String>,
    pub(super) location: Point,
    pub(super) rotation: f64,
    pub(super) mirror: String,
    pub(super) pins: Vec<ComponentPinOut>,
}

#[derive(Debug, Clone)]
pub(super) struct ComponentPinOut {
    pub(super) index: usize,
    pub(super) name: String,
    pub(super) position: Point,
    pub(super) rotation: f64,
    pub(super) mirror: String,
    pub(super) net_id: Option<String>,
    pub(super) key: PinNetKey,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub(super) struct PinNetKey {
    pub(super) side: String,
    pub(super) component_index: usize,
    pub(super) pin_index: usize,
}

pub(super) fn component_side(component: &SemanticComponent) -> &'static str {
    let text = format!(
        "{} {}",
        component.side.as_deref().unwrap_or_default(),
        component.layer_name.as_deref().unwrap_or_default()
    )
    .to_ascii_lowercase();
    if text.contains("bot") || text.contains("bottom") || text.contains("b_cu") {
        "bottom"
    } else {
        "top"
    }
}
