use super::properties::prop_string;
use crate::model::Layer;
use std::collections::{BTreeMap, HashMap};

pub(crate) fn layer_name_map(layers: &[Layer]) -> HashMap<u32, String> {
    layers
        .iter()
        .map(|layer| (layer.layer_id, layer.name.clone()))
        .collect()
}

pub(crate) fn resolved_layer_name(layer_id: u32, layer_names: &HashMap<u32, String>) -> String {
    layer_names
        .get(&layer_id)
        .cloned()
        .unwrap_or_else(|| layer_name(layer_id))
}

pub(crate) fn layer_name(layer_id: u32) -> String {
    match layer_id {
        0 => "UNKNOWN".to_string(),
        1 => "TOP".to_string(),
        2..=31 => format!("MID{}", layer_id - 1),
        32 => "BOTTOM".to_string(),
        33 => "TOPOVERLAY".to_string(),
        34 => "BOTTOMOVERLAY".to_string(),
        35 => "TOPPASTE".to_string(),
        36 => "BOTTOMPASTE".to_string(),
        37 => "TOPSOLDER".to_string(),
        38 => "BOTTOMSOLDER".to_string(),
        39..=54 => format!("PLANE{}", layer_id - 38),
        55 => "DRILLGUIDE".to_string(),
        56 => "KEEPOUT".to_string(),
        57..=72 => format!("MECHANICAL{}", layer_id - 56),
        73 => "DRILLDRAWING".to_string(),
        74 => "MULTILAYER".to_string(),
        0x0100_0001 => "TOP".to_string(),
        0x0100_FFFF => "BOTTOM".to_string(),
        0x0102_0001..=0x0102_FFFF => format!("MECHANICAL{}", layer_id - 0x0102_0000),
        _ => format!("LAYER_{layer_id}"),
    }
}

pub(crate) fn layer_id_from_name(name: &str) -> u32 {
    let name = name.trim().to_ascii_uppercase();
    match name.as_str() {
        "TOP" => 1,
        "BOTTOM" => 32,
        "TOPOVERLAY" => 33,
        "BOTTOMOVERLAY" => 34,
        "TOPPASTE" => 35,
        "BOTTOMPASTE" => 36,
        "TOPSOLDER" => 37,
        "BOTTOMSOLDER" => 38,
        "DRILLGUIDE" => 55,
        "KEEPOUT" => 56,
        "DRILLDRAWING" => 73,
        "MULTILAYER" => 74,
        _ if name.starts_with("MID") => name[3..].parse::<u32>().map(|v| v + 1).unwrap_or(0),
        _ if name.starts_with("PLANE") => name[5..].parse::<u32>().map(|v| v + 38).unwrap_or(0),
        _ if name.starts_with("MECHANICAL") => {
            name[10..].parse::<u32>().map(|v| v + 56).unwrap_or(0)
        }
        _ => 0,
    }
}

pub(crate) fn versioned_layer_from_properties(
    properties: &BTreeMap<String, String>,
    v6: &str,
    v7: &str,
) -> u32 {
    let layer_v6 = layer_id_from_name(&prop_string(properties, v6).unwrap_or_default());
    let layer_v7 = layer_id_from_name(&prop_string(properties, v7).unwrap_or_default());
    versioned_layer(layer_v6, layer_v7)
}

pub(crate) fn versioned_layer(v6_layer: u32, v7_layer: u32) -> u32 {
    if (0x0102_0011..=0x0102_FFFF).contains(&v7_layer) {
        v7_layer
    } else if v7_layer != 0 && v6_layer == 0 {
        v7_layer
    } else {
        v6_layer
    }
}
