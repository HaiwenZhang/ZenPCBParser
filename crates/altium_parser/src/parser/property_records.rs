use super::constants::ALTIUM_NET_UNCONNECTED;
use super::geometry::{point_from_property, size_from_property, vertices_from_properties};
use super::layers::{layer_id_from_name, layer_name, versioned_layer_from_properties};
use super::properties::{
    prop_bool, prop_f64, prop_f64_opt, prop_i32, prop_string, prop_u16, prop_u32, prop_unit_mil,
    prop_usize_opt,
};
use super::reader::BinaryReader;
use super::strings::latin1_string;
use super::AltiumParseError;
use crate::model::{Board, Class, Component, Layer, Net, Polygon, Rule};
use std::collections::BTreeMap;

pub(crate) fn parse_file_header(bytes: &[u8]) -> Result<Option<String>, AltiumParseError> {
    if bytes.is_empty() {
        return Ok(None);
    }
    let mut reader = BinaryReader::new(bytes);
    if reader.remaining() >= 4 {
        let len = reader.peek_u32()?;
        if len as usize <= reader.remaining().saturating_sub(4) {
            reader.read_subrecord_len()?;
            let text = reader.read_wx_string()?;
            return Ok(Some(text));
        }
    }
    Ok(Some(latin1_string(bytes).trim_matches('\0').to_string()))
}

pub(crate) fn parse_board_stream(bytes: &[u8]) -> Result<(Board, Vec<Layer>), AltiumParseError> {
    let mut reader = BinaryReader::new(bytes);
    let properties = reader.read_properties()?;
    let board = Board {
        sheet_position: Some(point_from_property(&properties, "SHEETX", "SHEETY")),
        sheet_size: Some(size_from_property(&properties, "SHEETWIDTH", "SHEETHEIGHT")),
        layer_count_declared: Some(prop_i32(&properties, "LAYERSETSCOUNT", 1) + 1),
        outline: vertices_from_properties(&properties),
        properties: properties.clone(),
    };
    let layers = layers_from_properties(&properties);
    Ok((board, layers))
}

fn layers_from_properties(properties: &BTreeMap<String, String>) -> Vec<Layer> {
    let mut layers = Vec::new();
    let mut layer_indices = Vec::new();
    for key in properties.keys() {
        if key.starts_with("LAYER") && key.ends_with("NAME") && !key.starts_with("LAYERV7_") {
            let number = &key[5..key.len() - 4];
            if let Ok(index) = number.parse::<u32>() {
                layer_indices.push(index);
            }
        }
    }
    layer_indices.sort_unstable();
    layer_indices.dedup();
    for index in layer_indices {
        let prefix = format!("LAYER{index}");
        if let Some(name) = prop_string(properties, &format!("{prefix}NAME")) {
            layers.push(layer_from_properties(properties, &prefix, index, name));
        }
    }

    let mut layer_v7_indices = Vec::new();
    for key in properties.keys() {
        if key.starts_with("LAYERV7_") && key.ends_with("NAME") {
            let number = &key[8..key.len() - 4];
            if let Ok(index) = number.parse::<u32>() {
                layer_v7_indices.push(index);
            }
        }
    }
    layer_v7_indices.sort_unstable();
    layer_v7_indices.dedup();
    for index in layer_v7_indices {
        let prefix = format!("LAYERV7_{index}");
        if let Some(name) = prop_string(properties, &format!("{prefix}NAME")) {
            let layer_id = prop_u32(properties, &format!("{prefix}LAYERID"), 0);
            layers.push(layer_from_properties(properties, &prefix, layer_id, name));
        }
    }
    layers
}

fn layer_from_properties(
    properties: &BTreeMap<String, String>,
    prefix: &str,
    fallback_layer_id: u32,
    name: String,
) -> Layer {
    let mech_enabled = prop_string(properties, &format!("{prefix}MECHENABLED"))
        .map(|value| !value.to_ascii_uppercase().contains("FALSE"))
        .unwrap_or(false);
    Layer {
        layer_id: prop_u32(properties, &format!("{prefix}LAYERID"), fallback_layer_id),
        name,
        next_id: prop_usize_opt(properties, &format!("{prefix}NEXT")),
        prev_id: prop_usize_opt(properties, &format!("{prefix}PREV")),
        copper_thickness: prop_unit_mil(properties, &format!("{prefix}COPTHICK")),
        dielectric_constant: prop_f64_opt(properties, &format!("{prefix}DIELCONST")),
        dielectric_thickness: prop_unit_mil(properties, &format!("{prefix}DIELHEIGHT")),
        dielectric_material: prop_string(properties, &format!("{prefix}DIELMATERIAL")),
        mechanical_enabled: mech_enabled,
        mechanical_kind: prop_string(properties, &format!("{prefix}MECHKIND")),
    }
}

pub(crate) fn parse_net_record(
    index: usize,
    properties: BTreeMap<String, String>,
) -> Result<Net, AltiumParseError> {
    Ok(Net {
        index,
        name: prop_string(&properties, "NAME").unwrap_or_else(|| format!("Net{index}")),
        properties,
    })
}

pub(crate) fn parse_class_record(
    index: usize,
    properties: BTreeMap<String, String>,
) -> Result<Class, AltiumParseError> {
    let mut members = Vec::new();
    for member_index in 0..=100_000 {
        let key = format!("M{member_index}");
        let Some(value) = prop_string(&properties, &key) else {
            break;
        };
        members.push(value);
    }
    Ok(Class {
        index,
        name: prop_string(&properties, "NAME").unwrap_or_else(|| format!("Class{index}")),
        unique_id: prop_string(&properties, "UNIQUEID"),
        kind: prop_i32(&properties, "KIND", -1),
        members,
        properties,
    })
}

fn parse_rule_record(
    index: usize,
    properties: BTreeMap<String, String>,
) -> Result<Rule, AltiumParseError> {
    Ok(Rule {
        index,
        name: prop_string(&properties, "NAME").unwrap_or_else(|| format!("Rule{index}")),
        kind: prop_string(&properties, "RULEKIND").unwrap_or_else(|| "Unknown".to_string()),
        priority: prop_i32(&properties, "PRIORITY", 1),
        scope1_expression: prop_string(&properties, "SCOPE1EXPRESSION"),
        scope2_expression: prop_string(&properties, "SCOPE2EXPRESSION"),
        properties,
    })
}

pub(crate) fn parse_polygon_record(
    index: usize,
    properties: BTreeMap<String, String>,
) -> Result<Polygon, AltiumParseError> {
    let layer_id = versioned_layer_from_properties(&properties, "LAYER", "LAYER_V7");
    Ok(Polygon {
        index,
        layer_id,
        layer_name: layer_name(layer_id),
        net: prop_u16(&properties, "NET", ALTIUM_NET_UNCONNECTED),
        locked: prop_bool(&properties, "LOCKED", false),
        hatch_style: prop_string(&properties, "HATCHSTYLE")
            .unwrap_or_else(|| "Unknown".to_string()),
        grid_size: prop_unit_mil(&properties, "GRIDSIZE"),
        track_width: prop_unit_mil(&properties, "TRACKWIDTH"),
        min_primitive_length: prop_unit_mil(&properties, "MINPRIMLENGTH"),
        use_octagons: prop_bool(&properties, "USEOCTAGONS", false),
        pour_index: prop_i32(&properties, "POURINDEX", 0),
        vertices: vertices_from_properties(&properties),
        properties,
    })
}

pub(crate) fn parse_component_record(
    index: usize,
    properties: BTreeMap<String, String>,
) -> Result<Component, AltiumParseError> {
    let layer_id = layer_id_from_name(&prop_string(&properties, "LAYER").unwrap_or_default());
    Ok(Component {
        index,
        layer_id,
        layer_name: layer_name(layer_id),
        position: point_from_property(&properties, "X", "Y"),
        rotation: prop_f64(&properties, "ROTATION", 0.0),
        locked: prop_bool(&properties, "LOCKED", false),
        name_on: prop_bool(&properties, "NAMEON", true),
        comment_on: prop_bool(&properties, "COMMENTON", false),
        source_designator: prop_string(&properties, "SOURCEDESIGNATOR"),
        source_unique_id: prop_string(&properties, "SOURCEUNIQUEID").map(|value| {
            value
                .strip_prefix('\\')
                .unwrap_or(value.as_str())
                .to_string()
        }),
        source_hierarchical_path: prop_string(&properties, "SOURCEHIERARCHICALPATH"),
        source_footprint_library: prop_string(&properties, "SOURCEFOOTPRINTLIBRARY"),
        pattern: prop_string(&properties, "PATTERN"),
        source_component_library: prop_string(&properties, "SOURCECOMPONENTLIBRARY"),
        source_lib_reference: prop_string(&properties, "SOURCELIBREFERENCE"),
        properties,
    })
}

pub(crate) fn parse_property_records<T, F>(
    bytes: &[u8],
    parse: F,
) -> Result<Vec<T>, AltiumParseError>
where
    F: Fn(usize, BTreeMap<String, String>) -> Result<T, AltiumParseError>,
{
    let mut reader = BinaryReader::new(bytes);
    let mut records = Vec::new();
    while reader.remaining() >= 4 {
        let index = records.len();
        let properties = reader.read_properties()?;
        if properties.is_empty() {
            break;
        }
        records.push(parse(index, properties)?);
    }
    Ok(records)
}

pub(crate) fn parse_rules_stream(bytes: &[u8]) -> Result<Vec<Rule>, AltiumParseError> {
    let mut reader = BinaryReader::new(bytes);
    let mut rules = Vec::new();
    while reader.remaining() >= 6 {
        reader.skip(2)?;
        let properties = reader.read_properties()?;
        if properties.is_empty() {
            break;
        }
        rules.push(parse_rule_record(rules.len(), properties)?);
    }
    Ok(rules)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn subrecord(data: &[u8]) -> Vec<u8> {
        let mut out = Vec::new();
        out.extend_from_slice(&(data.len() as u32).to_le_bytes());
        out.extend_from_slice(data);
        out
    }

    #[test]
    fn parses_board_layers_from_properties() {
        let mut data = Vec::new();
        data.extend_from_slice(b"|SHEETX=0mil|SHEETY=0mil|LAYERSETSCOUNT=1|");
        data.extend_from_slice(b"LAYER1NAME=TOP|LAYER1NEXT=32|LAYER32NAME=BOTTOM|");
        data.extend_from_slice(b"LAYER32PREV=1|VX0=0mil|VY0=0mil|VX1=10mil|VY1=0mil|");
        let payload = subrecord(&data);
        let (board, layers) = parse_board_stream(&payload).unwrap();
        assert_eq!(layers.len(), 2);
        assert_eq!(layers[0].name, "TOP");
        assert_eq!(board.outline.len(), 2);
    }
}
