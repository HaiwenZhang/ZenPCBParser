use super::geometry::parse_unit_mil;
use super::strings::latin1_string;
use std::collections::BTreeMap;

fn prop_key(key: &str) -> String {
    key.to_ascii_uppercase()
}

pub(crate) fn prop_string(properties: &BTreeMap<String, String>, key: &str) -> Option<String> {
    properties
        .get(&prop_key(key))
        .filter(|value| !value.is_empty())
        .cloned()
}

pub(crate) fn prop_bool(properties: &BTreeMap<String, String>, key: &str, default: bool) -> bool {
    match prop_string(properties, key)
        .unwrap_or_default()
        .to_ascii_uppercase()
        .as_str()
    {
        "TRUE" | "T" | "YES" | "Y" | "1" => true,
        "FALSE" | "F" | "NO" | "N" | "0" => false,
        _ => default,
    }
}

pub(crate) fn prop_i32(properties: &BTreeMap<String, String>, key: &str, default: i32) -> i32 {
    prop_string(properties, key)
        .and_then(|value| value.parse::<i32>().ok())
        .unwrap_or(default)
}

pub(crate) fn prop_u32(properties: &BTreeMap<String, String>, key: &str, default: u32) -> u32 {
    prop_string(properties, key)
        .and_then(|value| value.parse::<u32>().ok())
        .unwrap_or(default)
}

pub(crate) fn prop_u16(properties: &BTreeMap<String, String>, key: &str, default: u16) -> u16 {
    prop_string(properties, key)
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(default)
}

pub(crate) fn prop_u8(properties: &BTreeMap<String, String>, key: &str, default: u8) -> u8 {
    prop_string(properties, key)
        .and_then(|value| value.parse::<u8>().ok())
        .unwrap_or(default)
}

pub(crate) fn prop_usize_opt(properties: &BTreeMap<String, String>, key: &str) -> Option<usize> {
    prop_string(properties, key).and_then(|value| value.parse::<usize>().ok())
}

pub(crate) fn prop_f64(properties: &BTreeMap<String, String>, key: &str, default: f64) -> f64 {
    prop_f64_opt(properties, key).unwrap_or(default)
}

pub(crate) fn prop_f64_opt(properties: &BTreeMap<String, String>, key: &str) -> Option<f64> {
    prop_string(properties, key).and_then(|value| value.parse::<f64>().ok())
}

pub(crate) fn prop_unit_mil(properties: &BTreeMap<String, String>, key: &str) -> Option<f64> {
    prop_string(properties, key).and_then(|value| parse_unit_mil(&value))
}

pub(crate) fn parse_properties_payload(data: &[u8]) -> BTreeMap<String, String> {
    let mut payload = latin1_string(data);
    payload = payload.trim_matches('\0').to_string();
    let mut properties = BTreeMap::new();
    for entry in payload.split('|') {
        let entry = entry.trim_matches('\0').trim();
        if entry.is_empty() {
            continue;
        }
        let Some((key, value)) = entry.split_once('=') else {
            continue;
        };
        properties.insert(key.trim().to_ascii_uppercase(), value.trim().to_string());
    }
    properties
}
