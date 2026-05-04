use crate::model::{
    Arc, Board, Class, Component, Fill, Layer, Net, Pad, PadSizeAndShape, Point, Polygon, Region,
    Rule, Size, StreamSummary, Summary, Text, Track, Vertex, Via,
};
use std::collections::{BTreeMap, HashMap, HashSet};
use thiserror::Error;

const CFB_SIGNATURE: [u8; 8] = [0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1];
const FREE_SECTOR: u32 = 0xFFFF_FFFF;
const END_OF_CHAIN: u32 = 0xFFFF_FFFE;
const FAT_SECTOR: u32 = 0xFFFF_FFFD;
const DIFAT_SECTOR: u32 = 0xFFFF_FFFC;
const NO_STREAM: u32 = 0xFFFF_FFFF;
const ALTIUM_NET_UNCONNECTED: u16 = u16::MAX;
const ALTIUM_POLYGON_NONE: u16 = u16::MAX;
const ALTIUM_POLYGON_BOARD: u16 = u16::MAX - 1;
const INTERNAL_COORDS_PER_MIL: f64 = 10_000.0;

#[derive(Debug, Error)]
pub enum AltiumParseError {
    #[error("failed to read {size} bytes at offset 0x{offset:08x}; file size is {file_size}")]
    UnexpectedEof {
        offset: usize,
        size: usize,
        file_size: usize,
    },
    #[error("invalid Altium compound file signature")]
    InvalidSignature,
    #[error("{0}")]
    Invalid(String),
}

#[derive(Debug, Clone, Default)]
pub struct ParsedAltium {
    pub summary: Summary,
    pub file_header: Option<String>,
    pub board: Option<Board>,
    pub layers: Option<Vec<Layer>>,
    pub nets: Option<Vec<Net>>,
    pub classes: Option<Vec<Class>>,
    pub rules: Option<Vec<Rule>>,
    pub polygons: Option<Vec<Polygon>>,
    pub components: Option<Vec<Component>>,
    pub pads: Option<Vec<Pad>>,
    pub vias: Option<Vec<Via>>,
    pub tracks: Option<Vec<Track>>,
    pub arcs: Option<Vec<Arc>>,
    pub fills: Option<Vec<Fill>>,
    pub regions: Option<Vec<Region>>,
    pub texts: Option<Vec<Text>>,
    pub streams: Option<Vec<StreamSummary>>,
    pub stream_counts: BTreeMap<String, usize>,
    pub diagnostics: Vec<String>,
}

#[derive(Debug, Clone, Default)]
pub struct ParseOptions {
    pub include_details: bool,
}

pub fn parse_altium_bytes(
    bytes: &[u8],
    options: &ParseOptions,
) -> Result<ParsedAltium, AltiumParseError> {
    let compound = CompoundFile::parse(bytes)?;
    let mut diagnostics = Vec::new();
    let mut stream_summaries = compound.stream_summaries();
    let mut parsed_stream_count = 0usize;
    let mut stream_counts = BTreeMap::new();
    for stream in &stream_summaries {
        let key = stream
            .path
            .split('/')
            .next()
            .unwrap_or("")
            .to_ascii_lowercase();
        *stream_counts.entry(key).or_insert(0) += 1;
    }

    let mut file_header = None;
    if let Some(data) = compound.find_stream("FileHeader") {
        match parse_file_header(data) {
            Ok(value) => {
                parsed_stream_count += 1;
                file_header = value;
                mark_stream_parsed(&mut stream_summaries, "FileHeader");
            }
            Err(error) => diagnostics.push(format!("FileHeader parse failed: {error}")),
        }
    }

    let mut board = None;
    let mut layers = Vec::new();
    if let Some(data) = compound.find_stream("Board6") {
        match parse_board_stream(data) {
            Ok((parsed_board, parsed_layers)) => {
                parsed_stream_count += 1;
                board = Some(parsed_board);
                layers = parsed_layers;
                mark_stream_parsed(&mut stream_summaries, "Board6");
            }
            Err(error) => diagnostics.push(format!("Board6 parse failed: {error}")),
        }
    } else {
        diagnostics.push("Board6 stream not found".to_string());
    }

    let mut nets = Vec::new();
    if let Some(data) = compound.find_stream("Nets6") {
        match parse_property_records(data, parse_net_record) {
            Ok(parsed) => {
                parsed_stream_count += 1;
                nets = parsed;
                mark_stream_parsed(&mut stream_summaries, "Nets6");
            }
            Err(error) => diagnostics.push(format!("Nets6 parse failed: {error}")),
        }
    }

    let mut classes = Vec::new();
    if let Some(data) = compound.find_stream("Classes6") {
        match parse_property_records(data, parse_class_record) {
            Ok(parsed) => {
                parsed_stream_count += 1;
                classes = parsed;
                mark_stream_parsed(&mut stream_summaries, "Classes6");
            }
            Err(error) => diagnostics.push(format!("Classes6 parse failed: {error}")),
        }
    }

    let mut rules = Vec::new();
    if let Some(data) = compound.find_stream("Rules6") {
        match parse_rules_stream(data) {
            Ok(parsed) => {
                parsed_stream_count += 1;
                rules = parsed;
                mark_stream_parsed(&mut stream_summaries, "Rules6");
            }
            Err(error) => diagnostics.push(format!("Rules6 parse failed: {error}")),
        }
    }

    let mut polygons = Vec::new();
    if let Some(data) = compound.find_stream("Polygons6") {
        match parse_property_records(data, parse_polygon_record) {
            Ok(parsed) => {
                parsed_stream_count += 1;
                polygons = parsed;
                mark_stream_parsed(&mut stream_summaries, "Polygons6");
            }
            Err(error) => diagnostics.push(format!("Polygons6 parse failed: {error}")),
        }
    }

    let mut components = Vec::new();
    if let Some(data) = compound.find_stream("Components6") {
        match parse_property_records(data, parse_component_record) {
            Ok(parsed) => {
                parsed_stream_count += 1;
                components = parsed;
                mark_stream_parsed(&mut stream_summaries, "Components6");
            }
            Err(error) => diagnostics.push(format!("Components6 parse failed: {error}")),
        }
    }

    let mut wide_strings = BTreeMap::new();
    if let Some(data) = compound.find_stream("WideStrings6") {
        match parse_wide_string_table(data) {
            Ok(parsed) => {
                parsed_stream_count += 1;
                wide_strings = parsed;
                mark_stream_parsed(&mut stream_summaries, "WideStrings6");
            }
            Err(error) => diagnostics.push(format!("WideStrings6 parse failed: {error}")),
        }
    }

    let layer_names = layer_name_map(&layers);
    let mut pads = Vec::new();
    if let Some(data) = compound.find_stream("Pads6") {
        match parse_binary_records(data, |reader, index| {
            parse_pad_record(reader, index, &layer_names)
        }) {
            Ok(parsed) => {
                parsed_stream_count += 1;
                pads = parsed;
                mark_stream_parsed(&mut stream_summaries, "Pads6");
            }
            Err(error) => diagnostics.push(format!("Pads6 parse failed: {error}")),
        }
    }

    let mut vias = Vec::new();
    if let Some(data) = compound.find_stream("Vias6") {
        match parse_binary_records(data, |reader, index| {
            parse_via_record(reader, index, &layer_names)
        }) {
            Ok(parsed) => {
                parsed_stream_count += 1;
                vias = parsed;
                mark_stream_parsed(&mut stream_summaries, "Vias6");
            }
            Err(error) => diagnostics.push(format!("Vias6 parse failed: {error}")),
        }
    }

    let mut tracks = Vec::new();
    if let Some(data) = compound.find_stream("Tracks6") {
        match parse_binary_records(data, |reader, index| {
            parse_track_record(reader, index, &layer_names)
        }) {
            Ok(parsed) => {
                parsed_stream_count += 1;
                tracks = parsed;
                mark_stream_parsed(&mut stream_summaries, "Tracks6");
            }
            Err(error) => diagnostics.push(format!("Tracks6 parse failed: {error}")),
        }
    }

    let mut arcs = Vec::new();
    if let Some(data) = compound.find_stream("Arcs6") {
        match parse_binary_records(data, |reader, index| {
            parse_arc_record(reader, index, &layer_names)
        }) {
            Ok(parsed) => {
                parsed_stream_count += 1;
                arcs = parsed;
                mark_stream_parsed(&mut stream_summaries, "Arcs6");
            }
            Err(error) => diagnostics.push(format!("Arcs6 parse failed: {error}")),
        }
    }

    let mut fills = Vec::new();
    if let Some(data) = compound.find_stream("Fills6") {
        match parse_binary_records(data, |reader, index| {
            parse_fill_record(reader, index, &layer_names)
        }) {
            Ok(parsed) => {
                parsed_stream_count += 1;
                fills = parsed;
                mark_stream_parsed(&mut stream_summaries, "Fills6");
            }
            Err(error) => diagnostics.push(format!("Fills6 parse failed: {error}")),
        }
    }

    let mut regions = Vec::new();
    if let Some(data) = compound.find_stream("Regions6") {
        match parse_binary_records(data, |reader, index| {
            parse_region_record(reader, index, false, &layer_names)
        }) {
            Ok(parsed) => {
                parsed_stream_count += 1;
                regions.extend(parsed);
                mark_stream_parsed(&mut stream_summaries, "Regions6");
            }
            Err(error) => diagnostics.push(format!("Regions6 parse failed: {error}")),
        }
    }
    if let Some(data) = compound.find_stream("ShapeBasedRegions6") {
        match parse_binary_records(data, |reader, index| {
            parse_region_record(reader, index + regions.len(), true, &layer_names)
        }) {
            Ok(parsed) => {
                parsed_stream_count += 1;
                regions.extend(parsed);
                mark_stream_parsed(&mut stream_summaries, "ShapeBasedRegions6");
            }
            Err(error) => diagnostics.push(format!("ShapeBasedRegions6 parse failed: {error}")),
        }
    }
    if let Some(data) = compound.find_stream("BoardRegions") {
        match parse_binary_records(data, |reader, index| {
            parse_region_record(reader, index + regions.len(), false, &layer_names)
        }) {
            Ok(parsed) => {
                parsed_stream_count += 1;
                regions.extend(parsed);
                mark_stream_parsed(&mut stream_summaries, "BoardRegions");
            }
            Err(error) => diagnostics.push(format!("BoardRegions parse failed: {error}")),
        }
    }

    let mut texts = Vec::new();
    if let Some(data) = compound.find_stream("Texts6") {
        match parse_binary_records(data, |reader, index| {
            parse_text_record(reader, index, &layer_names, &wide_strings)
        }) {
            Ok(parsed) => {
                parsed_stream_count += 1;
                texts = parsed;
                mark_stream_parsed(&mut stream_summaries, "Texts6");
            }
            Err(error) => diagnostics.push(format!("Texts6 parse failed: {error}")),
        }
    }

    let board_outline_vertex_count = board
        .as_ref()
        .map(|item| item.outline.len())
        .unwrap_or(0)
        + regions
            .iter()
            .filter(|region| region.kind == "board_cutout" || region.polygon == ALTIUM_POLYGON_BOARD)
            .map(|region| region.outline.len())
            .sum::<usize>();

    let summary = Summary {
        stream_count: stream_summaries.len(),
        parsed_stream_count,
        layer_count: layers.len(),
        net_count: nets.len(),
        class_count: classes.len(),
        rule_count: rules.len(),
        polygon_count: polygons.len(),
        component_count: components.len(),
        pad_count: pads.len(),
        via_count: vias.len(),
        track_count: tracks.len(),
        arc_count: arcs.len(),
        fill_count: fills.len(),
        region_count: regions.len(),
        text_count: texts.len(),
        board_outline_vertex_count,
        diagnostic_count: diagnostics.len(),
        units: "mil".to_string(),
        format: "altium-pcbdoc-cfb".to_string(),
    };

    Ok(ParsedAltium {
        summary,
        file_header,
        board,
        layers: if options.include_details {
            Some(layers)
        } else {
            None
        },
        nets: if options.include_details {
            Some(nets)
        } else {
            None
        },
        classes: if options.include_details {
            Some(classes)
        } else {
            None
        },
        rules: if options.include_details {
            Some(rules)
        } else {
            None
        },
        polygons: if options.include_details {
            Some(polygons)
        } else {
            None
        },
        components: if options.include_details {
            Some(components)
        } else {
            None
        },
        pads: if options.include_details {
            Some(pads)
        } else {
            None
        },
        vias: if options.include_details {
            Some(vias)
        } else {
            None
        },
        tracks: if options.include_details {
            Some(tracks)
        } else {
            None
        },
        arcs: if options.include_details {
            Some(arcs)
        } else {
            None
        },
        fills: if options.include_details {
            Some(fills)
        } else {
            None
        },
        regions: if options.include_details {
            Some(regions)
        } else {
            None
        },
        texts: if options.include_details {
            Some(texts)
        } else {
            None
        },
        streams: Some(stream_summaries),
        stream_counts,
        diagnostics,
    })
}

fn mark_stream_parsed(streams: &mut [StreamSummary], name: &str) {
    let name = name.to_ascii_lowercase();
    for stream in streams {
        let path = stream.path.to_ascii_lowercase();
        if path == name || path == format!("{name}/data") || path.ends_with(&format!("/{name}/data"))
        {
            stream.parsed = true;
        }
    }
}

fn parse_file_header(bytes: &[u8]) -> Result<Option<String>, AltiumParseError> {
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

fn parse_board_stream(bytes: &[u8]) -> Result<(Board, Vec<Layer>), AltiumParseError> {
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

fn parse_net_record(
    index: usize,
    properties: BTreeMap<String, String>,
) -> Result<Net, AltiumParseError> {
    Ok(Net {
        index,
        name: prop_string(&properties, "NAME").unwrap_or_else(|| format!("Net{index}")),
        properties,
    })
}

fn parse_class_record(
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

fn parse_polygon_record(
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
        hatch_style: prop_string(&properties, "HATCHSTYLE").unwrap_or_else(|| "Unknown".to_string()),
        grid_size: prop_unit_mil(&properties, "GRIDSIZE"),
        track_width: prop_unit_mil(&properties, "TRACKWIDTH"),
        min_primitive_length: prop_unit_mil(&properties, "MINPRIMLENGTH"),
        use_octagons: prop_bool(&properties, "USEOCTAGONS", false),
        pour_index: prop_i32(&properties, "POURINDEX", 0),
        vertices: vertices_from_properties(&properties),
        properties,
    })
}

fn parse_component_record(
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
            value.strip_prefix('\\').unwrap_or(value.as_str()).to_string()
        }),
        source_hierarchical_path: prop_string(&properties, "SOURCEHIERARCHICALPATH"),
        source_footprint_library: prop_string(&properties, "SOURCEFOOTPRINTLIBRARY"),
        pattern: prop_string(&properties, "PATTERN"),
        source_component_library: prop_string(&properties, "SOURCECOMPONENTLIBRARY"),
        source_lib_reference: prop_string(&properties, "SOURCELIBREFERENCE"),
        properties,
    })
}

fn parse_property_records<T, F>(bytes: &[u8], parse: F) -> Result<Vec<T>, AltiumParseError>
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

fn parse_rules_stream(bytes: &[u8]) -> Result<Vec<Rule>, AltiumParseError> {
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

fn parse_binary_records<T, F>(bytes: &[u8], mut parse: F) -> Result<Vec<T>, AltiumParseError>
where
    F: FnMut(&mut BinaryReader<'_>, usize) -> Result<T, AltiumParseError>,
{
    let mut reader = BinaryReader::new(bytes);
    let mut records = Vec::new();
    while reader.remaining() >= 5 {
        records.push(parse(&mut reader, records.len())?);
    }
    Ok(records)
}

fn parse_pad_record(
    reader: &mut BinaryReader<'_>,
    index: usize,
    layer_names: &HashMap<u32, String>,
) -> Result<Pad, AltiumParseError> {
    expect_record_type(reader, 2, "Pads6")?;
    let subrecord1 = reader.read_subrecord_len()?;
    if subrecord1 == 0 {
        return Err(AltiumParseError::Invalid(
            "Pads6 subrecord1 has zero length".to_string(),
        ));
    }
    let name = reader.read_wx_string()?;
    reader.skip_subrecord()?;
    reader.read_subrecord_len()?;
    reader.skip_subrecord()?;
    reader.read_subrecord_len()?;
    reader.skip_subrecord()?;
    reader.read_subrecord_len()?;
    reader.skip_subrecord()?;

    let subrecord5 = reader.read_subrecord_len()?;
    if subrecord5 < 110 {
        return Err(AltiumParseError::Invalid(format!(
            "Pads6 subrecord5 length {subrecord5} is too short"
        )));
    }
    let layer_v6 = reader.u8()? as u32;
    let flags1 = reader.u8()?;
    let is_test_fab_top = flags1 & 0x80 != 0;
    let is_tent_bottom = flags1 & 0x40 != 0;
    let is_tent_top = flags1 & 0x20 != 0;
    let is_locked = flags1 & 0x04 == 0;
    let flags2 = reader.u8()?;
    let is_test_fab_bottom = flags2 & 0x01 != 0;
    let net = reader.u16()?;
    reader.skip(2)?;
    let component = reader.u16()?;
    reader.skip(4)?;
    let position = reader.point()?;
    let top_size = reader.size()?;
    let mid_size = reader.size()?;
    let bottom_size = reader.size()?;
    let hole_size = coord_to_mil_i32(reader.i32()?);
    let top_shape = pad_shape_name(reader.u8()?).to_string();
    let mid_shape = pad_shape_name(reader.u8()?).to_string();
    let bottom_shape = pad_shape_name(reader.u8()?).to_string();
    let direction = reader.f64()?;
    let plated = reader.u8()? != 0;
    reader.skip(1)?;
    let pad_mode = pad_mode_name(reader.u8()?).to_string();
    reader.skip(23)?;
    let _paste_mask_expansion = reader.i32()?;
    let _solder_mask_expansion = reader.i32()?;
    reader.skip(7)?;
    let _paste_mode = reader.u8()?;
    let _solder_mode = reader.u8()?;
    reader.skip(3)?;
    let hole_rotation = if subrecord5 == 110 {
        let _unknown = reader.i32()?;
        0.0
    } else {
        reader.f64()?
    };
    let mut to_layer_id = None;
    let mut from_layer_id = None;
    if subrecord5 >= 120 && reader.remaining_subrecord_bytes() >= 4 {
        to_layer_id = Some(reader.u8()? as u32);
        reader.skip(2)?;
        from_layer_id = Some(reader.u8()? as u32);
    }
    reader.skip_subrecord()?;

    let subrecord6 = reader.read_subrecord_len()?;
    let size_and_shape = if subrecord6 >= 596 {
        Some(parse_pad_size_and_shape(reader)?)
    } else {
        None
    };
    reader.skip_subrecord()?;
    let layer_id = layer_v6;
    Ok(Pad {
        index,
        name,
        layer_id,
        layer_name: resolved_layer_name(layer_id, layer_names),
        net,
        component,
        position,
        top_size,
        mid_size,
        bottom_size,
        hole_size,
        top_shape,
        mid_shape,
        bottom_shape,
        direction,
        plated,
        pad_mode,
        hole_rotation,
        from_layer_id,
        to_layer_id,
        size_and_shape,
        is_locked,
        is_tent_top,
        is_tent_bottom,
        is_test_fab_top,
        is_test_fab_bottom,
    })
}

fn parse_pad_size_and_shape(
    reader: &mut BinaryReader<'_>,
) -> Result<PadSizeAndShape, AltiumParseError> {
    let mut inner_x = Vec::with_capacity(29);
    for _ in 0..29 {
        inner_x.push(reader.i32()?);
    }
    let mut inner_sizes = Vec::with_capacity(29);
    for x_raw in inner_x {
        let y_raw = reader.i32()?;
        inner_sizes.push(size_from_raw(x_raw, y_raw));
    }
    let mut inner_shapes = Vec::with_capacity(29);
    for _ in 0..29 {
        inner_shapes.push(pad_shape_name(reader.u8()?).to_string());
    }
    reader.skip(1)?;
    let hole_shape = pad_hole_shape_name(reader.u8()?).to_string();
    let slot_size = coord_to_mil_i32(reader.i32()?);
    let slot_rotation = reader.f64()?;
    let mut offset_x = Vec::with_capacity(32);
    for _ in 0..32 {
        offset_x.push(reader.i32()?);
    }
    let mut hole_offsets = Vec::with_capacity(32);
    for x_raw in offset_x {
        let y_raw = reader.i32()?;
        hole_offsets.push(point_from_raw(x_raw, y_raw));
    }
    reader.skip(1)?;
    let mut alternate_shapes = Vec::with_capacity(32);
    for _ in 0..32 {
        alternate_shapes.push(pad_shape_alt_name(reader.u8()?).to_string());
    }
    let mut corner_radii = Vec::with_capacity(32);
    for _ in 0..32 {
        corner_radii.push(reader.u8()?);
    }
    Ok(PadSizeAndShape {
        hole_shape,
        slot_size,
        slot_rotation,
        inner_sizes,
        inner_shapes,
        hole_offsets,
        alternate_shapes,
        corner_radii,
    })
}

fn parse_via_record(
    reader: &mut BinaryReader<'_>,
    index: usize,
    layer_names: &HashMap<u32, String>,
) -> Result<Via, AltiumParseError> {
    expect_record_type(reader, 3, "Vias6")?;
    let subrecord1 = reader.read_subrecord_len()?;
    reader.skip(1)?;
    let flags1 = reader.u8()?;
    let is_tent_bottom = flags1 & 0x40 != 0;
    let is_tent_top = flags1 & 0x20 != 0;
    let is_locked = flags1 & 0x04 == 0;
    let _flags2 = reader.u8()?;
    let net = reader.u16()?;
    reader.skip(8)?;
    let position = reader.point()?;
    let diameter = coord_to_mil_i32(reader.i32()?);
    let hole_size = coord_to_mil_i32(reader.i32()?);
    let start_layer_id = reader.u8()? as u32;
    let end_layer_id = reader.u8()? as u32;
    let mut via_mode = "simple".to_string();
    let mut diameter_by_layer = Vec::new();
    if subrecord1 > 74 && reader.remaining_subrecord_bytes() >= 74 {
        reader.skip(1)?;
        let _thermal_airgap = reader.i32()?;
        let _thermal_conductors = reader.u8()?;
        reader.skip(1)?;
        let _thermal_width = reader.i32()?;
        reader.skip(16)?;
        let _solder_front = reader.i32()?;
        reader.skip(15)?;
        via_mode = pad_mode_name(reader.u8()?).to_string();
        for _ in 0..32 {
            if reader.remaining_subrecord_bytes() < 4 {
                break;
            }
            diameter_by_layer.push(coord_to_mil_i32(reader.i32()?));
        }
    }
    reader.skip_subrecord()?;
    Ok(Via {
        index,
        net,
        position,
        diameter,
        hole_size,
        start_layer_id,
        start_layer_name: resolved_layer_name(start_layer_id, layer_names),
        end_layer_id,
        end_layer_name: resolved_layer_name(end_layer_id, layer_names),
        via_mode,
        diameter_by_layer,
        is_locked,
        is_tent_top,
        is_tent_bottom,
    })
}

fn parse_track_record(
    reader: &mut BinaryReader<'_>,
    index: usize,
    layer_names: &HashMap<u32, String>,
) -> Result<Track, AltiumParseError> {
    expect_record_type(reader, 4, "Tracks6")?;
    reader.read_subrecord_len()?;
    let layer_v6 = reader.u8()? as u32;
    let flags1 = reader.u8()?;
    let is_locked = flags1 & 0x04 == 0;
    let is_polygon_outline = flags1 & 0x02 != 0;
    let flags2 = reader.u8()?;
    let is_keepout = flags2 == 2;
    let net = reader.u16()?;
    let polygon = reader.u16()?;
    let component = reader.u16()?;
    reader.skip(4)?;
    let start = reader.point()?;
    let end = reader.point()?;
    let width = coord_to_mil_i32(reader.i32()?);
    let subpolygon = reader.u16()?;
    reader.skip(1)?;
    let remaining = reader.remaining_subrecord_bytes();
    let mut layer_id = layer_v6;
    if remaining >= 9 {
        reader.skip(5)?;
        layer_id = versioned_layer(layer_v6, reader.u32()?);
    }
    let keepout_restrictions = if remaining >= 10 {
        reader.u8()?
    } else if is_keepout {
        0x1F
    } else {
        0
    };
    reader.skip_subrecord()?;
    Ok(Track {
        index,
        layer_id,
        layer_name: resolved_layer_name(layer_id, layer_names),
        net,
        component,
        polygon,
        subpolygon,
        start,
        end,
        width,
        is_locked,
        is_keepout,
        is_polygon_outline,
        keepout_restrictions,
    })
}

fn parse_arc_record(
    reader: &mut BinaryReader<'_>,
    index: usize,
    layer_names: &HashMap<u32, String>,
) -> Result<Arc, AltiumParseError> {
    expect_record_type(reader, 1, "Arcs6")?;
    reader.read_subrecord_len()?;
    let layer_v6 = reader.u8()? as u32;
    let flags1 = reader.u8()?;
    let is_locked = flags1 & 0x04 == 0;
    let is_polygon_outline = flags1 & 0x02 != 0;
    let flags2 = reader.u8()?;
    let is_keepout = flags2 == 2;
    let net = reader.u16()?;
    let polygon = reader.u16()?;
    let component = reader.u16()?;
    reader.skip(4)?;
    let center = reader.point()?;
    let radius = coord_to_mil_i32(reader.i32()?);
    let start_angle = reader.f64()?;
    let end_angle = reader.f64()?;
    let width = coord_to_mil_i32(reader.i32()?);
    let subpolygon = reader.u16()?;
    let remaining = reader.remaining_subrecord_bytes();
    let mut layer_id = layer_v6;
    if remaining >= 9 {
        reader.skip(5)?;
        layer_id = versioned_layer(layer_v6, reader.u32()?);
    }
    let keepout_restrictions = if remaining >= 10 {
        reader.u8()?
    } else if is_keepout {
        0x1F
    } else {
        0
    };
    reader.skip_subrecord()?;
    Ok(Arc {
        index,
        layer_id,
        layer_name: resolved_layer_name(layer_id, layer_names),
        net,
        component,
        polygon,
        subpolygon,
        center,
        radius,
        start_angle,
        end_angle,
        width,
        is_locked,
        is_keepout,
        is_polygon_outline,
        keepout_restrictions,
    })
}

fn parse_fill_record(
    reader: &mut BinaryReader<'_>,
    index: usize,
    layer_names: &HashMap<u32, String>,
) -> Result<Fill, AltiumParseError> {
    expect_record_type(reader, 6, "Fills6")?;
    reader.read_subrecord_len()?;
    let layer_v6 = reader.u8()? as u32;
    let flags1 = reader.u8()?;
    let is_locked = flags1 & 0x04 == 0;
    let flags2 = reader.u8()?;
    let is_keepout = flags2 == 2;
    let net = reader.u16()?;
    reader.skip(2)?;
    let component = reader.u16()?;
    reader.skip(4)?;
    let position1 = reader.point()?;
    let position2 = reader.point()?;
    let rotation = reader.f64()?;
    let remaining = reader.remaining_subrecord_bytes();
    let mut layer_id = layer_v6;
    if remaining >= 9 {
        reader.skip(5)?;
        layer_id = versioned_layer(layer_v6, reader.u32()?);
    }
    let keepout_restrictions = if remaining >= 10 {
        reader.u8()?
    } else if is_keepout {
        0x1F
    } else {
        0
    };
    reader.skip_subrecord()?;
    Ok(Fill {
        index,
        layer_id,
        layer_name: resolved_layer_name(layer_id, layer_names),
        component,
        net,
        position1,
        position2,
        rotation,
        is_locked,
        is_keepout,
        keepout_restrictions,
    })
}

fn parse_region_record(
    reader: &mut BinaryReader<'_>,
    index: usize,
    extended_vertices: bool,
    layer_names: &HashMap<u32, String>,
) -> Result<Region, AltiumParseError> {
    expect_record_type(reader, 11, "Regions6")?;
    reader.read_subrecord_len()?;
    let layer_v6 = reader.u8()? as u32;
    let flags1 = reader.u8()?;
    let is_locked = flags1 & 0x04 == 0;
    let flags2 = reader.u8()?;
    let is_keepout = flags2 == 2;
    let net = reader.u16()?;
    let polygon = reader.u16()?;
    let component = reader.u16()?;
    reader.skip(5)?;
    let hole_count = reader.u16()?;
    reader.skip(2)?;
    let properties = reader.read_properties()?;
    let layer_v7 = layer_id_from_name(&prop_string(&properties, "V7_LAYER").unwrap_or_default());
    let layer_id = versioned_layer(layer_v6, layer_v7);
    let raw_kind = prop_i32(&properties, "KIND", 0);
    let is_board_cutout = prop_bool(&properties, "ISBOARDCUTOUT", false);
    let is_shape_based = prop_bool(&properties, "ISSHAPEBASED", extended_vertices);
    let kind = region_kind_name(raw_kind, is_board_cutout).to_string();
    let keepout_restrictions = prop_u8(&properties, "KEEPOUTRESTRIC", 0x1F);
    let subpolygon = prop_u16(&properties, "SUBPOLYINDEX", ALTIUM_POLYGON_NONE);
    let mut outline_count = reader.u32()? as usize;
    if extended_vertices {
        outline_count = outline_count.saturating_add(1);
    }
    let mut outline = Vec::with_capacity(outline_count);
    for _ in 0..outline_count {
        outline.push(read_region_vertex(reader, extended_vertices)?);
    }
    let mut holes = Vec::with_capacity(hole_count as usize);
    for _ in 0..hole_count {
        let hole_vertices = reader.u32()? as usize;
        let mut hole = Vec::with_capacity(hole_vertices);
        for _ in 0..hole_vertices {
            hole.push(read_region_vertex(reader, extended_vertices)?);
        }
        holes.push(hole);
    }
    reader.skip_subrecord()?;
    Ok(Region {
        index,
        layer_id,
        layer_name: resolved_layer_name(layer_id, layer_names),
        net,
        component,
        polygon,
        subpolygon,
        kind,
        outline,
        holes,
        is_locked,
        is_keepout,
        is_shape_based,
        keepout_restrictions,
    })
}

fn read_region_vertex(
    reader: &mut BinaryReader<'_>,
    extended_vertices: bool,
) -> Result<Vertex, AltiumParseError> {
    if extended_vertices {
        let is_round = reader.u8()? != 0;
        let position = reader.point()?;
        let center = reader.point()?;
        let radius = coord_to_mil_i32(reader.i32()?);
        let start_angle = reader.f64()?;
        let end_angle = reader.f64()?;
        Ok(Vertex {
            is_round,
            radius,
            start_angle,
            end_angle,
            position,
            center: Some(center),
        })
    } else {
        let x = double_coord_to_raw(reader.f64()?);
        let y = double_coord_to_raw(reader.f64()?);
        Ok(Vertex {
            is_round: false,
            radius: 0.0,
            start_angle: 0.0,
            end_angle: 0.0,
            position: point_from_raw(x, y),
            center: None,
        })
    }
}

fn parse_text_record(
    reader: &mut BinaryReader<'_>,
    index: usize,
    layer_names: &HashMap<u32, String>,
    wide_strings: &BTreeMap<u32, String>,
) -> Result<Text, AltiumParseError> {
    expect_record_type(reader, 5, "Texts6")?;
    let subrecord1 = reader.read_subrecord_len()?;
    let layer_v6 = reader.u8()? as u32;
    reader.skip(6)?;
    let component = reader.u16()?;
    reader.skip(4)?;
    let position = reader.point()?;
    let height = coord_to_mil_i32(reader.i32()?);
    let _stroke_font_type = reader.u16()?;
    let rotation = reader.f64()?;
    let is_mirrored = reader.u8()? != 0;
    let stroke_width = coord_to_mil_i32(reader.i32()?);
    if subrecord1 < 123 {
        reader.skip_subrecord()?;
        return Ok(Text {
            index,
            layer_id: layer_v6,
            layer_name: resolved_layer_name(layer_v6, layer_names),
            component,
            position,
            height,
            rotation,
            stroke_width,
            font_type: "stroke".to_string(),
            font_name: None,
            text: String::new(),
            is_bold: false,
            is_italic: false,
            is_mirrored,
            is_comment: false,
            is_designator: false,
        });
    }
    let is_comment = reader.u8()? != 0;
    let is_designator = reader.u8()? != 0;
    reader.skip(1)?;
    let mut font_type = text_font_type_name(reader.u8()?).to_string();
    let is_bold = reader.u8()? != 0;
    let is_italic = reader.u8()? != 0;
    let font_name = Some(reader.utf16_fixed_string(64)?);
    reader.skip(1)?;
    let _margin = reader.i32()?;
    let wide_index = reader.u32()?;
    reader.skip(4)?;
    reader.skip(1)?;
    reader.skip(8)?;
    reader.skip(1)?;
    reader.skip(4)?;
    let remaining = reader.remaining_subrecord_bytes();
    let mut layer_id = layer_v6;
    if remaining >= 93 {
        reader.skip(25)?;
        font_type = text_font_type_name(reader.u8()?).to_string();
        reader.skip(64)?;
        reader.skip(1)?;
        layer_id = versioned_layer(layer_v6, reader.u32()?);
    }
    reader.skip_subrecord()?;
    reader.read_subrecord_len()?;
    let text = if let Some(value) = wide_strings.get(&wide_index) {
        value.clone()
    } else {
        reader.read_wx_string()?
    }
    .replace("\r\n", "\n");
    reader.skip_subrecord()?;
    Ok(Text {
        index,
        layer_id,
        layer_name: resolved_layer_name(layer_id, layer_names),
        component,
        position,
        height,
        rotation,
        stroke_width,
        font_type,
        font_name,
        text,
        is_bold,
        is_italic,
        is_mirrored,
        is_comment,
        is_designator,
    })
}

fn parse_wide_string_table(bytes: &[u8]) -> Result<BTreeMap<u32, String>, AltiumParseError> {
    let mut reader = BinaryReader::new(bytes);
    let mut table = BTreeMap::new();
    while reader.remaining() >= 8 {
        let index = reader.u32()?;
        let byte_len = reader.u32()? as usize;
        if byte_len > reader.remaining() {
            break;
        }
        let bytes = reader.bytes(byte_len)?;
        table.insert(index, utf16le_string(bytes));
    }
    Ok(table)
}

fn expect_record_type(
    reader: &mut BinaryReader<'_>,
    expected: u8,
    stream: &str,
) -> Result<(), AltiumParseError> {
    let actual = reader.u8()?;
    if actual != expected {
        return Err(AltiumParseError::Invalid(format!(
            "{stream} has invalid record type {actual}; expected {expected}"
        )));
    }
    Ok(())
}

fn layer_name_map(layers: &[Layer]) -> HashMap<u32, String> {
    layers
        .iter()
        .map(|layer| (layer.layer_id, layer.name.clone()))
        .collect()
}

fn resolved_layer_name(layer_id: u32, layer_names: &HashMap<u32, String>) -> String {
    layer_names
        .get(&layer_id)
        .cloned()
        .unwrap_or_else(|| layer_name(layer_id))
}

fn layer_name(layer_id: u32) -> String {
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

fn layer_id_from_name(name: &str) -> u32 {
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
        _ if name.starts_with("MECHANICAL") => name[10..].parse::<u32>().map(|v| v + 56).unwrap_or(0),
        _ => 0,
    }
}

fn versioned_layer_from_properties(properties: &BTreeMap<String, String>, v6: &str, v7: &str) -> u32 {
    let layer_v6 = layer_id_from_name(&prop_string(properties, v6).unwrap_or_default());
    let layer_v7 = layer_id_from_name(&prop_string(properties, v7).unwrap_or_default());
    versioned_layer(layer_v6, layer_v7)
}

fn versioned_layer(v6_layer: u32, v7_layer: u32) -> u32 {
    if (0x0102_0011..=0x0102_FFFF).contains(&v7_layer) {
        v7_layer
    } else if v7_layer != 0 && v6_layer == 0 {
        v7_layer
    } else {
        v6_layer
    }
}

fn vertices_from_properties(properties: &BTreeMap<String, String>) -> Vec<Vertex> {
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

fn point_from_property(properties: &BTreeMap<String, String>, x_key: &str, y_key: &str) -> Point {
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

fn size_from_property(properties: &BTreeMap<String, String>, x_key: &str, y_key: &str) -> Size {
    let x = prop_unit_mil(properties, x_key).unwrap_or(0.0);
    let y = prop_unit_mil(properties, y_key).unwrap_or(0.0);
    Size {
        x_raw: (x * INTERNAL_COORDS_PER_MIL).round() as i32,
        y_raw: (y * INTERNAL_COORDS_PER_MIL).round() as i32,
        x,
        y,
    }
}

fn point_from_raw(x_raw: i32, y_raw: i32) -> Point {
    Point {
        x_raw,
        y_raw,
        x: coord_to_mil_i32(x_raw),
        y: -coord_to_mil_i32(y_raw),
    }
}

fn size_from_raw(x_raw: i32, y_raw: i32) -> Size {
    Size {
        x_raw,
        y_raw,
        x: coord_to_mil_i32(x_raw),
        y: coord_to_mil_i32(y_raw),
    }
}

fn coord_to_mil_i32(raw: i32) -> f64 {
    raw as f64 / INTERNAL_COORDS_PER_MIL
}

fn double_coord_to_raw(value: f64) -> i32 {
    (value * INTERNAL_COORDS_PER_MIL).round() as i32
}

fn parse_unit_mil(value: &str) -> Option<f64> {
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

fn prop_key(key: &str) -> String {
    key.to_ascii_uppercase()
}

fn prop_string(properties: &BTreeMap<String, String>, key: &str) -> Option<String> {
    properties.get(&prop_key(key)).filter(|value| !value.is_empty()).cloned()
}

fn prop_bool(properties: &BTreeMap<String, String>, key: &str, default: bool) -> bool {
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

fn prop_i32(properties: &BTreeMap<String, String>, key: &str, default: i32) -> i32 {
    prop_string(properties, key)
        .and_then(|value| value.parse::<i32>().ok())
        .unwrap_or(default)
}

fn prop_u32(properties: &BTreeMap<String, String>, key: &str, default: u32) -> u32 {
    prop_string(properties, key)
        .and_then(|value| value.parse::<u32>().ok())
        .unwrap_or(default)
}

fn prop_u16(properties: &BTreeMap<String, String>, key: &str, default: u16) -> u16 {
    prop_string(properties, key)
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(default)
}

fn prop_u8(properties: &BTreeMap<String, String>, key: &str, default: u8) -> u8 {
    prop_string(properties, key)
        .and_then(|value| value.parse::<u8>().ok())
        .unwrap_or(default)
}

fn prop_usize_opt(properties: &BTreeMap<String, String>, key: &str) -> Option<usize> {
    prop_string(properties, key).and_then(|value| value.parse::<usize>().ok())
}

fn prop_f64(properties: &BTreeMap<String, String>, key: &str, default: f64) -> f64 {
    prop_f64_opt(properties, key).unwrap_or(default)
}

fn prop_f64_opt(properties: &BTreeMap<String, String>, key: &str) -> Option<f64> {
    prop_string(properties, key).and_then(|value| value.parse::<f64>().ok())
}

fn prop_unit_mil(properties: &BTreeMap<String, String>, key: &str) -> Option<f64> {
    prop_string(properties, key).and_then(|value| parse_unit_mil(&value))
}

fn pad_shape_name(value: u8) -> &'static str {
    match value {
        1 => "circle",
        2 => "rectangle",
        3 => "octagonal",
        _ => "unknown",
    }
}

fn pad_shape_alt_name(value: u8) -> &'static str {
    match value {
        1 => "circle",
        2 => "rectangle",
        3 => "octagonal",
        9 => "roundrect",
        _ => "unknown",
    }
}

fn pad_hole_shape_name(value: u8) -> &'static str {
    match value {
        0 => "round",
        1 => "square",
        2 => "slot",
        _ => "unknown",
    }
}

fn pad_mode_name(value: u8) -> &'static str {
    match value {
        0 => "simple",
        1 => "top_middle_bottom",
        2 => "full_stack",
        _ => "unknown",
    }
}

fn region_kind_name(value: i32, is_board_cutout: bool) -> &'static str {
    match (value, is_board_cutout) {
        (0, true) => "board_cutout",
        (0, false) => "copper",
        (1, _) => "polygon_cutout",
        (2, _) => "dashed_outline",
        (3, _) => "unknown_3",
        (4, _) => "cavity_definition",
        _ => "unknown",
    }
}

fn text_font_type_name(value: u8) -> &'static str {
    match value {
        0 => "stroke",
        1 => "truetype",
        2 => "barcode",
        _ => "unknown",
    }
}

fn latin1_string(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| *byte as char).collect()
}

fn utf16le_string(bytes: &[u8]) -> String {
    let mut units = Vec::with_capacity(bytes.len() / 2);
    let mut index = 0;
    while index + 1 < bytes.len() {
        let value = u16::from_le_bytes([bytes[index], bytes[index + 1]]);
        if value == 0 {
            break;
        }
        units.push(value);
        index += 2;
    }
    String::from_utf16_lossy(&units)
}

struct BinaryReader<'a> {
    data: &'a [u8],
    position: usize,
    subrecord_end: Option<usize>,
}

impl<'a> BinaryReader<'a> {
    fn new(data: &'a [u8]) -> Self {
        Self {
            data,
            position: 0,
            subrecord_end: None,
        }
    }

    fn remaining(&self) -> usize {
        self.data.len().saturating_sub(self.position)
    }

    fn remaining_subrecord_bytes(&self) -> usize {
        self.subrecord_end
            .unwrap_or(self.data.len())
            .saturating_sub(self.position)
    }

    fn bytes(&mut self, size: usize) -> Result<&'a [u8], AltiumParseError> {
        if self.position + size > self.data.len() {
            return Err(AltiumParseError::UnexpectedEof {
                offset: self.position,
                size,
                file_size: self.data.len(),
            });
        }
        let start = self.position;
        self.position += size;
        Ok(&self.data[start..start + size])
    }

    fn skip(&mut self, size: usize) -> Result<(), AltiumParseError> {
        self.bytes(size).map(|_| ())
    }

    fn u8(&mut self) -> Result<u8, AltiumParseError> {
        Ok(self.bytes(1)?[0])
    }

    fn u16(&mut self) -> Result<u16, AltiumParseError> {
        let bytes = self.bytes(2)?;
        Ok(u16::from_le_bytes([bytes[0], bytes[1]]))
    }

    fn u32(&mut self) -> Result<u32, AltiumParseError> {
        let bytes = self.bytes(4)?;
        Ok(u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
    }

    fn i32(&mut self) -> Result<i32, AltiumParseError> {
        let bytes = self.bytes(4)?;
        Ok(i32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
    }

    fn f64(&mut self) -> Result<f64, AltiumParseError> {
        let bytes = self.bytes(8)?;
        Ok(f64::from_le_bytes([
            bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7],
        ]))
    }

    fn peek_u32(&self) -> Result<u32, AltiumParseError> {
        if self.position + 4 > self.data.len() {
            return Err(AltiumParseError::UnexpectedEof {
                offset: self.position,
                size: 4,
                file_size: self.data.len(),
            });
        }
        let bytes = &self.data[self.position..self.position + 4];
        Ok(u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
    }

    fn read_subrecord_len(&mut self) -> Result<usize, AltiumParseError> {
        let length = self.u32()? as usize;
        let end = self
            .position
            .checked_add(length)
            .ok_or_else(|| AltiumParseError::Invalid("subrecord length overflow".to_string()))?;
        if end > self.data.len() {
            return Err(AltiumParseError::UnexpectedEof {
                offset: self.position,
                size: length,
                file_size: self.data.len(),
            });
        }
        self.subrecord_end = Some(end);
        Ok(length)
    }

    fn skip_subrecord(&mut self) -> Result<(), AltiumParseError> {
        if let Some(end) = self.subrecord_end.take() {
            if end > self.data.len() {
                return Err(AltiumParseError::UnexpectedEof {
                    offset: self.position,
                    size: end.saturating_sub(self.position),
                    file_size: self.data.len(),
                });
            }
            self.position = end;
        }
        Ok(())
    }

    fn read_wx_string(&mut self) -> Result<String, AltiumParseError> {
        let len = self.u8()? as usize;
        let bytes = self.bytes(len)?;
        Ok(latin1_string(bytes).trim_matches('\0').to_string())
    }

    fn utf16_fixed_string(&mut self, size: usize) -> Result<String, AltiumParseError> {
        let bytes = self.bytes(size)?;
        Ok(utf16le_string(bytes))
    }

    fn point(&mut self) -> Result<Point, AltiumParseError> {
        let x = self.i32()?;
        let y = self.i32()?;
        Ok(point_from_raw(x, y))
    }

    fn size(&mut self) -> Result<Size, AltiumParseError> {
        let x = self.i32()?;
        let y = self.i32()?;
        Ok(size_from_raw(x, y))
    }

    fn read_properties(&mut self) -> Result<BTreeMap<String, String>, AltiumParseError> {
        if self.remaining() == 0 {
            return Ok(BTreeMap::new());
        }
        let start = self.position;
        let data = if self.remaining() >= 4 {
            let length = self.peek_u32()? as usize;
            if length <= self.remaining().saturating_sub(4) {
                self.skip(4)?;
                self.bytes(length)?
            } else {
                self.bytes(self.remaining())?
            }
        } else {
            self.bytes(self.remaining())?
        };
        let properties = parse_properties_payload(data);
        if properties.is_empty() && self.position == start {
            self.position = self.data.len();
        }
        Ok(properties)
    }
}

fn parse_properties_payload(data: &[u8]) -> BTreeMap<String, String> {
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

#[derive(Debug, Clone)]
struct DirectoryEntry {
    name: String,
    object_type: u8,
    left: u32,
    right: u32,
    child: u32,
    start_sector: u32,
    stream_size: u64,
}

#[derive(Debug, Clone)]
struct CfbStream {
    path: String,
    data: Vec<u8>,
}

#[derive(Debug, Clone)]
struct CompoundFile {
    streams: Vec<CfbStream>,
}

impl CompoundFile {
    fn parse(bytes: &[u8]) -> Result<Self, AltiumParseError> {
        if bytes.len() < 512 {
            return Err(AltiumParseError::UnexpectedEof {
                offset: 0,
                size: 512,
                file_size: bytes.len(),
            });
        }
        if bytes[..8] != CFB_SIGNATURE {
            return Err(AltiumParseError::InvalidSignature);
        }
        let sector_shift = read_u16_at(bytes, 30)?;
        let mini_sector_shift = read_u16_at(bytes, 32)?;
        let sector_size = 1usize
            .checked_shl(sector_shift as u32)
            .ok_or_else(|| AltiumParseError::Invalid("invalid CFB sector shift".to_string()))?;
        let mini_sector_size = 1usize
            .checked_shl(mini_sector_shift as u32)
            .ok_or_else(|| AltiumParseError::Invalid("invalid CFB mini-sector shift".to_string()))?;
        let fat_sector_count = read_u32_at(bytes, 44)? as usize;
        let first_directory_sector = read_u32_at(bytes, 48)?;
        let mini_stream_cutoff_size = read_u32_at(bytes, 56)? as u64;
        let first_mini_fat_sector = read_u32_at(bytes, 60)?;
        let mini_fat_sector_count = read_u32_at(bytes, 64)? as usize;
        let first_difat_sector = read_u32_at(bytes, 68)?;
        let difat_sector_count = read_u32_at(bytes, 72)? as usize;

        let mut difat = Vec::new();
        for index in 0..109 {
            let value = read_u32_at(bytes, 76 + index * 4)?;
            if value != FREE_SECTOR {
                difat.push(value);
            }
        }
        let mut next_difat = first_difat_sector;
        for _ in 0..difat_sector_count {
            if next_difat == END_OF_CHAIN || next_difat == FREE_SECTOR {
                break;
            }
            let sector = sector_slice(bytes, sector_size, next_difat)?;
            let entry_count = sector_size / 4 - 1;
            for index in 0..entry_count {
                let value = read_u32_at(sector, index * 4)?;
                if value != FREE_SECTOR {
                    difat.push(value);
                }
            }
            next_difat = read_u32_at(sector, sector_size - 4)?;
        }
        difat.truncate(fat_sector_count);

        let mut fat = Vec::new();
        for sector_id in &difat {
            if *sector_id == FAT_SECTOR || *sector_id == DIFAT_SECTOR {
                continue;
            }
            let sector = sector_slice(bytes, sector_size, *sector_id)?;
            for index in 0..sector_size / 4 {
                fat.push(read_u32_at(sector, index * 4)?);
            }
        }

        let directory_stream = read_regular_chain(bytes, sector_size, &fat, first_directory_sector)?;
        let directory = parse_directory(&directory_stream)?;
        let Some(root) = directory.iter().find(|entry| entry.object_type == 5) else {
            return Err(AltiumParseError::Invalid(
                "CFB root storage not found".to_string(),
            ));
        };
        let mini_fat = if mini_fat_sector_count > 0 && first_mini_fat_sector != END_OF_CHAIN {
            let data = read_regular_chain(bytes, sector_size, &fat, first_mini_fat_sector)?;
            let mut entries = Vec::with_capacity(data.len() / 4);
            for index in 0..data.len() / 4 {
                entries.push(read_u32_at(&data, index * 4)?);
            }
            entries
        } else {
            Vec::new()
        };
        let mini_stream = if root.start_sector != END_OF_CHAIN && root.stream_size > 0 {
            let mut data = read_regular_chain(bytes, sector_size, &fat, root.start_sector)?;
            data.truncate(root.stream_size as usize);
            data
        } else {
            Vec::new()
        };

        let mut streams = Vec::new();
        if root.child != NO_STREAM {
            collect_streams(
                root.child as usize,
                "",
                &directory,
                &mut |entry, path| {
                    let data = if entry.stream_size < mini_stream_cutoff_size
                        && !mini_fat.is_empty()
                        && entry.start_sector != END_OF_CHAIN
                    {
                        read_mini_chain(
                            &mini_stream,
                            mini_sector_size,
                            &mini_fat,
                            entry.start_sector,
                            entry.stream_size as usize,
                        )
                    } else {
                        read_regular_chain(bytes, sector_size, &fat, entry.start_sector).map(
                            |mut data| {
                                data.truncate(entry.stream_size as usize);
                                data
                            },
                        )
                    }?;
                    streams.push(CfbStream { path, data });
                    Ok(())
                },
            )?;
        }
        streams.sort_by(|left, right| left.path.cmp(&right.path));
        Ok(Self { streams })
    }

    fn stream_summaries(&self) -> Vec<StreamSummary> {
        self.streams
            .iter()
            .map(|stream| StreamSummary {
                path: stream.path.clone(),
                size: stream.data.len(),
                parsed: false,
            })
            .collect()
    }

    fn find_stream(&self, name: &str) -> Option<&[u8]> {
        let target = name.to_ascii_lowercase();
        let target_data = format!("{target}/data");
        self.streams
            .iter()
            .find(|stream| {
                let path = stream.path.to_ascii_lowercase();
                path == target || path == target_data || path.ends_with(&format!("/{target_data}"))
            })
            .map(|stream| stream.data.as_slice())
    }
}

fn collect_streams<F>(
    sid: usize,
    parent: &str,
    directory: &[DirectoryEntry],
    visit: &mut F,
) -> Result<(), AltiumParseError>
where
    F: FnMut(&DirectoryEntry, String) -> Result<(), AltiumParseError>,
{
    if sid >= directory.len() {
        return Ok(());
    }
    let entry = &directory[sid];
    if entry.left != NO_STREAM {
        collect_streams(entry.left as usize, parent, directory, visit)?;
    }
    match entry.object_type {
        1 => {
            let path = join_path(parent, &entry.name);
            if entry.child != NO_STREAM {
                collect_streams(entry.child as usize, &path, directory, visit)?;
            }
        }
        2 => visit(entry, join_path(parent, &entry.name))?,
        _ => {}
    }
    if entry.right != NO_STREAM {
        collect_streams(entry.right as usize, parent, directory, visit)?;
    }
    Ok(())
}

fn join_path(parent: &str, name: &str) -> String {
    if parent.is_empty() {
        name.to_string()
    } else {
        format!("{parent}/{name}")
    }
}

fn parse_directory(bytes: &[u8]) -> Result<Vec<DirectoryEntry>, AltiumParseError> {
    let mut entries = Vec::new();
    for chunk in bytes.chunks_exact(128) {
        let name_len = read_u16_at(chunk, 64)? as usize;
        let name_bytes_len = name_len.saturating_sub(2).min(64);
        let name = utf16le_string(&chunk[..name_bytes_len]);
        entries.push(DirectoryEntry {
            name,
            object_type: chunk[66],
            left: read_u32_at(chunk, 68)?,
            right: read_u32_at(chunk, 72)?,
            child: read_u32_at(chunk, 76)?,
            start_sector: read_u32_at(chunk, 116)?,
            stream_size: read_u64_at(chunk, 120)?,
        });
    }
    Ok(entries)
}

fn read_regular_chain(
    bytes: &[u8],
    sector_size: usize,
    fat: &[u32],
    first_sector: u32,
) -> Result<Vec<u8>, AltiumParseError> {
    if first_sector == END_OF_CHAIN || first_sector == FREE_SECTOR {
        return Ok(Vec::new());
    }
    let mut data = Vec::new();
    let mut sector_id = first_sector;
    let mut seen = HashSet::new();
    while sector_id != END_OF_CHAIN {
        if sector_id as usize >= fat.len() {
            return Err(AltiumParseError::Invalid(format!(
                "CFB sector {sector_id} is outside FAT"
            )));
        }
        if !seen.insert(sector_id) {
            return Err(AltiumParseError::Invalid(format!(
                "CFB sector chain loops at sector {sector_id}"
            )));
        }
        data.extend_from_slice(sector_slice(bytes, sector_size, sector_id)?);
        sector_id = fat[sector_id as usize];
    }
    Ok(data)
}

fn read_mini_chain(
    mini_stream: &[u8],
    mini_sector_size: usize,
    mini_fat: &[u32],
    first_sector: u32,
    stream_size: usize,
) -> Result<Vec<u8>, AltiumParseError> {
    let mut data = Vec::new();
    let mut sector_id = first_sector;
    let mut seen = HashSet::new();
    while sector_id != END_OF_CHAIN && data.len() < stream_size {
        if sector_id as usize >= mini_fat.len() {
            return Err(AltiumParseError::Invalid(format!(
                "CFB mini-sector {sector_id} is outside mini FAT"
            )));
        }
        if !seen.insert(sector_id) {
            return Err(AltiumParseError::Invalid(format!(
                "CFB mini-sector chain loops at sector {sector_id}"
            )));
        }
        let start = sector_id as usize * mini_sector_size;
        let end = start + mini_sector_size;
        if end > mini_stream.len() {
            return Err(AltiumParseError::UnexpectedEof {
                offset: start,
                size: mini_sector_size,
                file_size: mini_stream.len(),
            });
        }
        data.extend_from_slice(&mini_stream[start..end]);
        sector_id = mini_fat[sector_id as usize];
    }
    data.truncate(stream_size);
    Ok(data)
}

fn sector_slice<'a>(
    bytes: &'a [u8],
    sector_size: usize,
    sector_id: u32,
) -> Result<&'a [u8], AltiumParseError> {
    let start = 512usize
        .checked_add(sector_id as usize * sector_size)
        .ok_or_else(|| AltiumParseError::Invalid("CFB sector offset overflow".to_string()))?;
    let end = start + sector_size;
    if end > bytes.len() {
        return Err(AltiumParseError::UnexpectedEof {
            offset: start,
            size: sector_size,
            file_size: bytes.len(),
        });
    }
    Ok(&bytes[start..end])
}

fn read_u16_at(bytes: &[u8], offset: usize) -> Result<u16, AltiumParseError> {
    if offset + 2 > bytes.len() {
        return Err(AltiumParseError::UnexpectedEof {
            offset,
            size: 2,
            file_size: bytes.len(),
        });
    }
    Ok(u16::from_le_bytes([bytes[offset], bytes[offset + 1]]))
}

fn read_u32_at(bytes: &[u8], offset: usize) -> Result<u32, AltiumParseError> {
    if offset + 4 > bytes.len() {
        return Err(AltiumParseError::UnexpectedEof {
            offset,
            size: 4,
            file_size: bytes.len(),
        });
    }
    Ok(u32::from_le_bytes([
        bytes[offset],
        bytes[offset + 1],
        bytes[offset + 2],
        bytes[offset + 3],
    ]))
}

fn read_u64_at(bytes: &[u8], offset: usize) -> Result<u64, AltiumParseError> {
    if offset + 8 > bytes.len() {
        return Err(AltiumParseError::UnexpectedEof {
            offset,
            size: 8,
            file_size: bytes.len(),
        });
    }
    Ok(u64::from_le_bytes([
        bytes[offset],
        bytes[offset + 1],
        bytes[offset + 2],
        bytes[offset + 3],
        bytes[offset + 4],
        bytes[offset + 5],
        bytes[offset + 6],
        bytes[offset + 7],
    ]))
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
    fn parses_pipe_properties() {
        let data = subrecord(b"|NAME=GND|KIND=0|M0=U1|");
        let mut reader = BinaryReader::new(&data);
        let props = reader.read_properties().unwrap();
        assert_eq!(props["NAME"], "GND");
        assert_eq!(props["M0"], "U1");
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

    #[test]
    fn parses_track_record() {
        let mut record = vec![4];
        let mut body = Vec::new();
        body.push(1);
        body.push(0);
        body.push(0);
        body.extend_from_slice(&7u16.to_le_bytes());
        body.extend_from_slice(&0u16.to_le_bytes());
        body.extend_from_slice(&0u16.to_le_bytes());
        body.extend_from_slice(&[0; 4]);
        body.extend_from_slice(&10000i32.to_le_bytes());
        body.extend_from_slice(&20000i32.to_le_bytes());
        body.extend_from_slice(&30000i32.to_le_bytes());
        body.extend_from_slice(&40000i32.to_le_bytes());
        body.extend_from_slice(&5000i32.to_le_bytes());
        body.extend_from_slice(&0u16.to_le_bytes());
        body.push(0);
        record.extend_from_slice(&subrecord(&body));
        let mut reader = BinaryReader::new(&record);
        let track = parse_track_record(&mut reader, 0, &HashMap::new()).unwrap();
        assert_eq!(track.net, 7);
        assert_eq!(track.layer_name, "TOP");
        assert_eq!(track.start.x, 1.0);
        assert_eq!(track.start.y, -2.0);
        assert_eq!(track.width, 0.5);
    }
}
