use super::properties::{prop_f64, prop_i32, prop_unit_mil};
use crate::model::{Point, Size, Vertex};
use std::collections::BTreeMap;

const INTERNAL_COORDS_PER_MIL: f64 = 10_000.0;

pub(crate) fn vertices_from_properties(properties: &BTreeMap<String, String>) -> Vec<Vertex> {
    let mut vertices = Vec::new();
    for index in 0..=100_000 {
        let x_key = format!("VX{index}");
        let y_key = format!("VY{index}");
        if !properties.contains_key(&x_key) || !properties.contains_key(&y_key) {
            break;
        }
        let is_round = prop_i32(properties, &format!("KIND{index}"), 0) != 0;
        vertices.push(Vertex {
            is_round,
            radius: prop_unit_mil(properties, &format!("R{index}")).unwrap_or(0.0),
            start_angle: prop_f64(properties, &format!("SA{index}"), 0.0),
            end_angle: prop_f64(properties, &format!("EA{index}"), 0.0),
            position: point_from_property(properties, &x_key, &y_key),
            center: Some(point_from_property(
                properties,
                &format!("CX{index}"),
                &format!("CY{index}"),
            )),
        });
    }
    vertices
}

pub(crate) fn point_from_property(
    properties: &BTreeMap<String, String>,
    x_key: &str,
    y_key: &str,
) -> Point {
    let x = prop_unit_mil(properties, x_key).unwrap_or(0.0);
    let y_source = prop_unit_mil(properties, y_key).unwrap_or(0.0);
    let x_raw = (x * INTERNAL_COORDS_PER_MIL).round() as i32;
    let y_raw = (y_source * INTERNAL_COORDS_PER_MIL).round() as i32;
    Point {
        x_raw,
        y_raw,
        x,
        y: -y_source,
    }
}

pub(crate) fn size_from_property(
    properties: &BTreeMap<String, String>,
    x_key: &str,
    y_key: &str,
) -> Size {
    let x = prop_unit_mil(properties, x_key).unwrap_or(0.0);
    let y = prop_unit_mil(properties, y_key).unwrap_or(0.0);
    Size {
        x_raw: (x * INTERNAL_COORDS_PER_MIL).round() as i32,
        y_raw: (y * INTERNAL_COORDS_PER_MIL).round() as i32,
        x,
        y,
    }
}

pub(crate) fn point_from_raw(x_raw: i32, y_raw: i32) -> Point {
    Point {
        x_raw,
        y_raw,
        x: coord_to_mil_i32(x_raw),
        y: -coord_to_mil_i32(y_raw),
    }
}

pub(crate) fn size_from_raw(x_raw: i32, y_raw: i32) -> Size {
    Size {
        x_raw,
        y_raw,
        x: coord_to_mil_i32(x_raw),
        y: coord_to_mil_i32(y_raw),
    }
}

pub(crate) fn coord_to_mil_i32(raw: i32) -> f64 {
    raw as f64 / INTERNAL_COORDS_PER_MIL
}

pub(crate) fn double_coord_to_raw(value: f64) -> i32 {
    if !value.is_finite() {
        return 0;
    }
    value.round().clamp(i32::MIN as f64, i32::MAX as f64) as i32
}

pub(crate) fn parse_unit_mil(value: &str) -> Option<f64> {
    let trimmed = value.trim().trim_matches('"');
    if trimmed.is_empty() {
        return None;
    }
    let lower = trimmed.to_ascii_lowercase().replace(' ', "");
    let parse_num = |suffix: &str| lower.strip_suffix(suffix)?.parse::<f64>().ok();
    if let Some(value) = parse_num("mils") {
        return Some(value);
    }
    if let Some(value) = parse_num("mil") {
        return Some(value);
    }
    if let Some(value) = parse_num("mm") {
        return Some(value / 0.0254);
    }
    if let Some(value) = parse_num("cm") {
        return Some(value / 0.00254);
    }
    if let Some(value) = parse_num("inch") {
        return Some(value * 1000.0);
    }
    if let Some(value) = parse_num("in") {
        return Some(value * 1000.0);
    }
    lower.parse::<f64>().ok()
}
