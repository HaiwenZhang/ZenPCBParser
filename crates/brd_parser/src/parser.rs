use crate::model::{
    BlockSummary, Footprint, Header, Keepout, Layer, LayerInfo, LayerMapEntry, LinkedList, Net,
    NetAssignment, Padstack, PlacedPad, Segment, Shape, StringEntry, Summary, Text, Track, Via,
};
use std::collections::{BTreeMap, HashMap};
use thiserror::Error;

const STRING_TABLE_OFFSET: usize = 0x1200;
const MAX_LAYER_COUNT: u16 = 256;
const MAX_VECTOR_COUNT: u32 = 1_000_000;

#[derive(Debug, Error)]
pub enum BrdParseError {
    #[error("failed to read {size} bytes at offset 0x{offset:08x}; file size is {file_size}")]
    UnexpectedEof {
        offset: usize,
        size: usize,
        file_size: usize,
    },
    #[error("failed to seek to offset 0x{offset:08x}; file size is {file_size}")]
    InvalidSeek { offset: usize, file_size: usize },
    #[error("unterminated string at offset 0x{offset:08x}")]
    UnterminatedString { offset: usize },
    #[error("unknown Allegro BRD magic 0x{0:08x}")]
    UnknownMagic(u32),
    #[error("unsupported pre-v16 Allegro BRD magic 0x{0:08x}")]
    UnsupportedPreV16(u32),
    #[error("{0}")]
    Invalid(String),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum FormatVersion {
    V160,
    V162,
    V164,
    V165,
    V166,
    V172,
    V174,
    V175,
    V180,
    V181,
}

impl FormatVersion {
    fn from_magic(magic: u32) -> Result<Self, BrdParseError> {
        match magic & 0xFFFF_FF00 {
            0x0013_0000 => Ok(Self::V160),
            0x0013_0400 => Ok(Self::V162),
            0x0013_0C00 => Ok(Self::V164),
            0x0013_1000 => Ok(Self::V165),
            0x0013_1500 => Ok(Self::V166),
            0x0014_0400 | 0x0014_0500 | 0x0014_0600 | 0x0014_0700 => Ok(Self::V172),
            0x0014_0900 | 0x0014_0E00 => Ok(Self::V174),
            0x0014_1500 => Ok(Self::V175),
            0x0015_0000 | 0x0015_0200 => Ok(Self::V180),
            0x0016_0100 => Ok(Self::V181),
            _ if ((magic >> 16) & 0xFFFF) <= 0x0012 => Err(BrdParseError::UnsupportedPreV16(magic)),
            _ => Err(BrdParseError::UnknownMagic(magic)),
        }
    }

    fn label(self) -> &'static str {
        match self {
            Self::V160 => "V_160",
            Self::V162 => "V_162",
            Self::V164 => "V_164",
            Self::V165 => "V_165",
            Self::V166 => "V_166",
            Self::V172 => "V_172",
            Self::V174 => "V_174",
            Self::V175 => "V_175",
            Self::V180 => "V_180",
            Self::V181 => "V_181",
        }
    }

    fn ge(self, other: Self) -> bool {
        self >= other
    }

    fn lt(self, other: Self) -> bool {
        self < other
    }
}

#[derive(Debug, Clone, Default)]
pub struct ParsedBrd {
    pub summary: Summary,
    pub header: Header,
    pub strings: Option<Vec<StringEntry>>,
    pub layers: Option<Vec<Layer>>,
    pub nets: Option<Vec<Net>>,
    pub padstacks: Option<Vec<Padstack>>,
    pub footprints: Option<Vec<Footprint>>,
    pub placed_pads: Option<Vec<PlacedPad>>,
    pub vias: Option<Vec<Via>>,
    pub tracks: Option<Vec<Track>>,
    pub segments: Option<Vec<Segment>>,
    pub shapes: Option<Vec<Shape>>,
    pub keepouts: Option<Vec<Keepout>>,
    pub net_assignments: Option<Vec<NetAssignment>>,
    pub texts: Option<Vec<Text>>,
    pub blocks: Option<Vec<BlockSummary>>,
    pub block_counts: BTreeMap<String, usize>,
    pub diagnostics: Vec<String>,
}

#[derive(Debug, Clone, Default)]
pub struct ParseOptions {
    pub include_details: bool,
}

#[derive(Debug, Clone, Default)]
struct BlockParse {
    key: Option<u32>,
    next: Option<u32>,
    net: Option<Net>,
    padstack: Option<Padstack>,
    footprint: Option<Footprint>,
    placed_pad: Option<PlacedPad>,
    via: Option<Via>,
    track: Option<Track>,
    segment: Option<Segment>,
    shape: Option<Shape>,
    keepout: Option<Keepout>,
    net_assignment: Option<NetAssignment>,
    text: Option<Text>,
    layer: Option<Layer>,
}

pub fn parse_brd_bytes(bytes: &[u8], options: &ParseOptions) -> Result<ParsedBrd, BrdParseError> {
    let mut diagnostics = Vec::new();
    let mut reader = Reader::new(bytes);
    let mut header = parse_header(&mut reader)?;
    let version = FormatVersion::from_magic(header.magic)?;
    let strings = parse_strings(bytes, header.string_count, &mut diagnostics)?;
    let string_map: HashMap<u32, String> = strings
        .iter()
        .map(|entry| (entry.id, entry.value.clone()))
        .collect();
    resolve_layer_names(&mut header, &string_map);

    let mut blocks = Vec::new();
    let mut nets = Vec::new();
    let mut padstacks = Vec::new();
    let mut footprints = Vec::new();
    let mut placed_pads = Vec::new();
    let mut vias = Vec::new();
    let mut tracks = Vec::new();
    let mut segments = Vec::new();
    let mut shapes = Vec::new();
    let mut keepouts = Vec::new();
    let mut net_assignments = Vec::new();
    let mut texts_by_key: BTreeMap<u32, Text> = BTreeMap::new();
    let mut layers_by_key: BTreeMap<u32, Layer> = BTreeMap::new();
    let mut counts = BTreeMap::new();

    reader.seek(after_string_table_offset(bytes, &strings)?)?;
    while !reader.eof() {
        let offset = reader.position();
        let Some(block_type) = reader.peek_u8()? else {
            break;
        };
        if block_type == 0 {
            reader.skip(1)?;
            if let Some(next_offset) = scan_zero_gap(&mut reader)? {
                reader.seek(next_offset)?;
                continue;
            }
            break;
        }
        if block_type > 0x3C {
            diagnostics.push(format!(
                "Stopped at unsupported block type 0x{block_type:02x} at offset 0x{offset:08x}"
            ));
            break;
        }

        let parsed = parse_block(&mut reader, version, header.x27_end as usize)?;
        let length = reader.position().saturating_sub(offset);
        *counts.entry(format!("0x{block_type:02X}")).or_insert(0) += 1;
        blocks.push(BlockSummary {
            block_type,
            type_name: block_type_name(block_type).to_string(),
            offset,
            length,
            key: parsed.key,
            next: parsed.next,
        });
        if let Some(mut net) = parsed.net {
            net.name = string_map.get(&net.name_string_id).cloned();
            nets.push(net);
        }
        if let Some(mut padstack) = parsed.padstack {
            padstack.name = string_map.get(&padstack.name_string_id).cloned();
            padstacks.push(padstack);
        }
        if let Some(mut footprint) = parsed.footprint {
            footprint.name = string_map.get(&footprint.name_string_id).cloned();
            footprint.sym_lib_path = string_map.get(&footprint.sym_lib_path_string_id).cloned();
            footprints.push(footprint);
        }
        if let Some(placed_pad) = parsed.placed_pad {
            placed_pads.push(placed_pad);
        }
        if let Some(via) = parsed.via {
            vias.push(via);
        }
        if let Some(track) = parsed.track {
            tracks.push(track);
        }
        if let Some(segment) = parsed.segment {
            segments.push(segment);
        }
        if let Some(shape) = parsed.shape {
            shapes.push(shape);
        }
        if let Some(keepout) = parsed.keepout {
            keepouts.push(keepout);
        }
        if let Some(net_assignment) = parsed.net_assignment {
            net_assignments.push(net_assignment);
        }
        if let Some(text) = parsed.text {
            texts_by_key
                .entry(text.key)
                .and_modify(|existing| merge_text(existing, &text))
                .or_insert(text);
        }
        if let Some(layer) = parsed.layer {
            layers_by_key.insert(layer.key, layer);
        }
    }

    for text in texts_by_key.values_mut() {
        if text.text.is_none() {
            continue;
        }
    }

    let layers = layers_by_key.into_values().collect::<Vec<_>>();
    let texts = texts_by_key.into_values().collect::<Vec<_>>();
    let summary = Summary {
        object_count_declared: header.object_count,
        object_count_parsed: blocks.len(),
        string_count: strings.len(),
        layer_count: layers.len(),
        net_count: nets.len(),
        padstack_count: padstacks.len(),
        footprint_count: footprints.len(),
        placed_pad_count: placed_pads.len(),
        via_count: vias.len(),
        track_count: tracks.len(),
        segment_count: segments.len(),
        shape_count: shapes.len(),
        keepout_count: keepouts.len(),
        net_assignment_count: net_assignments.len(),
        text_count: texts.len(),
        diagnostic_count: diagnostics.len(),
        format_version: header.format_version.clone(),
        allegro_version: header.allegro_version.clone(),
        units: header.board_units.clone(),
    };

    Ok(ParsedBrd {
        summary,
        header,
        strings: options.include_details.then_some(strings),
        layers: options.include_details.then_some(layers),
        nets: options.include_details.then_some(nets),
        padstacks: options.include_details.then_some(padstacks),
        footprints: options.include_details.then_some(footprints),
        placed_pads: options.include_details.then_some(placed_pads),
        vias: options.include_details.then_some(vias),
        tracks: options.include_details.then_some(tracks),
        segments: options.include_details.then_some(segments),
        shapes: options.include_details.then_some(shapes),
        keepouts: options.include_details.then_some(keepouts),
        net_assignments: options.include_details.then_some(net_assignments),
        texts: options.include_details.then_some(texts),
        blocks: options.include_details.then_some(blocks),
        block_counts: counts,
        diagnostics,
    })
}

fn parse_header(reader: &mut Reader<'_>) -> Result<Header, BrdParseError> {
    let start = reader.position();
    let magic = reader.u32()?;
    let version = FormatVersion::from_magic(magic)?;
    let _unknown1a = reader.u32()?;
    let file_role = reader.u32()?;
    let _unknown1b = reader.u32()?;
    let writer_program = reader.u32()?;
    let object_count = reader.u32()?;
    let _unknown_magic = reader.u32()?;
    let _unknown_flags = reader.u32()?;

    let mut linked_lists = BTreeMap::new();
    let (string_count_v18, x27_end_v18) = if version.lt(FormatVersion::V180) {
        reader.skip_u32(7)?;
        (None, None)
    } else {
        let _unknown2a = reader.u32()?;
        let _unknown2b = reader.u32()?;
        let x27_end = reader.u32()?;
        let _unknown2d = reader.u32()?;
        let _unknown2e = reader.u32()?;
        let string_count = reader.u32()?;
        let _unknown2g = reader.u32()?;
        for name in ["v18_1", "v18_2", "v18_3", "v18_4", "v18_5"] {
            linked_lists.insert(name.to_string(), read_ll(reader, version)?);
        }
        (Some(string_count), Some(x27_end))
    };

    for name in [
        "0x04_net_assignments",
        "0x06_components",
        "0x0c_pin_defs",
        "shapes",
        "0x14_graphics",
        "0x1b_nets",
        "0x1c_padstacks",
        "0x24_0x28",
        "unknown1",
        "0x2b_footprints",
        "0x03_0x30",
        "0x0a_drc",
        "0x1d_0x1e_0x1f",
        "unknown2",
        "0x38_films",
        "0x2c_tables",
        "0x0c_secondary",
        "unknown3",
    ] {
        linked_lists.insert(name.to_string(), read_ll(reader, version)?);
    }

    if version.lt(FormatVersion::V180) {
        let _x35_start = reader.u32()?;
        let _x35_end = reader.u32()?;
    }

    if version.ge(FormatVersion::V180) {
        linked_lists.insert("unknown5_v18".to_string(), read_ll(reader, version)?);
    }
    linked_lists.insert("0x36".to_string(), read_ll(reader, version)?);
    if version.lt(FormatVersion::V180) {
        linked_lists.insert("unknown5_pre_v18".to_string(), read_ll(reader, version)?);
    }
    linked_lists.insert("unknown6".to_string(), read_ll(reader, version)?);
    linked_lists.insert("0x0a_2".to_string(), read_ll(reader, version)?);
    if version.lt(FormatVersion::V180) {
        let _unknown3 = reader.u32()?;
    }
    if version.ge(FormatVersion::V180) {
        linked_lists.insert("v18_6".to_string(), read_ll(reader, version)?);
        let _x35_start = reader.u32()?;
        let _x35_end = reader.u32()?;
    }

    let expected_version_offset = if version.lt(FormatVersion::V180) {
        0xF8
    } else {
        0x124
    };
    if reader.position().saturating_sub(start) != expected_version_offset {
        return Err(BrdParseError::Invalid(format!(
            "header version string offset mismatch: expected 0x{expected_version_offset:x}, got 0x{:x}",
            reader.position().saturating_sub(start)
        )));
    }

    let allegro_version = reader.fixed_string(60, false)?;
    let _unknown4 = reader.u32()?;
    let max_key = reader.u32()?;
    if version.lt(FormatVersion::V180) {
        reader.skip_u32(17)?;
    } else {
        reader.skip_u32(9)?;
    }
    let board_units_code = reader.u8()?;
    reader.skip(3)?;
    let _unknown6 = reader.u32()?;
    if version.lt(FormatVersion::V180) {
        let _unknown7 = reader.u32()?;
    }
    let x27_end_pre_v18 = if version.lt(FormatVersion::V180) {
        Some(reader.u32()?)
    } else {
        None
    };
    let _unknown8 = reader.u32()?;
    let string_count_pre_v18 = if version.lt(FormatVersion::V180) {
        Some(reader.u32()?)
    } else {
        None
    };
    reader.skip_u32(50)?;
    let _unknown10a = reader.u32()?;
    let _unknown10b = reader.u32()?;
    let _unknown10c = reader.u32()?;
    let units_divisor = reader.u32()?;
    reader.skip_u32(110)?;
    let mut layer_map = Vec::with_capacity(25);
    for index in 0..25 {
        layer_map.push(LayerMapEntry {
            index,
            class_code: reader.u32()?,
            layer_list_key: reader.u32()?,
        });
    }

    Ok(Header {
        magic,
        format_version: version.label().to_string(),
        file_role,
        writer_program,
        object_count,
        max_key,
        allegro_version,
        board_units_code,
        board_units: board_units_name(board_units_code).to_string(),
        units_divisor,
        coordinate_scale_nm: (units_divisor > 0).then_some(25400.0 / units_divisor as f64),
        string_count: string_count_v18.or(string_count_pre_v18).unwrap_or(0),
        x27_end: x27_end_v18.or(x27_end_pre_v18).unwrap_or(0),
        linked_lists,
        layer_map,
    })
}

fn parse_strings(
    bytes: &[u8],
    count: u32,
    diagnostics: &mut Vec<String>,
) -> Result<Vec<StringEntry>, BrdParseError> {
    let mut reader = Reader::new(bytes);
    reader.seek(STRING_TABLE_OFFSET)?;
    let mut strings = Vec::with_capacity(count as usize);
    for _ in 0..count {
        if reader.eof() {
            diagnostics.push("String table ended before declared string count".to_string());
            break;
        }
        let id = reader.u32()?;
        let value = reader.c_string(true)?;
        strings.push(StringEntry { id, value });
    }
    Ok(strings)
}

fn after_string_table_offset(
    bytes: &[u8],
    strings: &[StringEntry],
) -> Result<usize, BrdParseError> {
    let mut reader = Reader::new(bytes);
    reader.seek(STRING_TABLE_OFFSET)?;
    for _ in strings {
        reader.skip(4)?;
        let _ = reader.c_string(true)?;
    }
    Ok(reader.position())
}

fn resolve_layer_names(header: &mut Header, string_map: &HashMap<u32, String>) {
    for entry in &mut header.layer_map {
        let _ = string_map.get(&entry.layer_list_key);
    }
}

fn parse_block(
    reader: &mut Reader<'_>,
    version: FormatVersion,
    x27_end: usize,
) -> Result<BlockParse, BrdParseError> {
    let block_type = reader.u8()?;
    match block_type {
        0x01 => parse_arc_or_segment(reader, version, block_type, true),
        0x03 => parse_field(reader, version),
        0x04 => parse_net_assignment(reader, version),
        0x05 => parse_track(reader, version),
        0x06 => parse_component(reader, version),
        0x07 => parse_component_inst(reader, version),
        0x08 => parse_pin_number(reader, version),
        0x09 => parse_fill_link(reader, version),
        0x0A => parse_drc(reader, version),
        0x0C => parse_pin_def(reader, version),
        0x0D => parse_pad(reader, version),
        0x0E => parse_rect_0e(reader, version),
        0x0F => parse_function_slot(reader, version),
        0x10 => parse_function_inst(reader, version),
        0x11 => parse_pin_name(reader, version),
        0x12 => parse_xref(reader, version),
        0x14 => parse_graphic(reader, version),
        0x15 | 0x16 | 0x17 => parse_arc_or_segment(reader, version, block_type, false),
        0x1B => parse_net(reader, version),
        0x1C => parse_padstack(reader, version),
        0x1D => parse_constraint_set(reader, version),
        0x1E => parse_si_model(reader, version),
        0x1F => parse_padstack_dim(reader, version),
        0x20 => parse_0x20(reader, version),
        0x21 => parse_blob_0x21(reader),
        0x22 => parse_0x22(reader, version),
        0x23 => parse_ratline(reader, version),
        0x24 => parse_rect_0x24(reader, version),
        0x26 => parse_match_group(reader, version),
        0x27 => parse_xref_0x27(reader, x27_end),
        0x28 => parse_shape(reader, version),
        0x29 => parse_pin_0x29(reader),
        0x2A => parse_layer_list(reader, version),
        0x2B => parse_footprint(reader, version),
        0x2C => parse_table(reader, version),
        0x2D => parse_footprint_inst(reader, version),
        0x2E => parse_connection(reader, version),
        0x2F => parse_0x2f(reader),
        0x30 => parse_text_wrapper(reader, version),
        0x31 => parse_string_graphic(reader, version),
        0x32 => parse_placed_pad(reader, version),
        0x33 => parse_via(reader, version),
        0x34 => parse_keepout(reader, version),
        0x35 => parse_file_ref(reader),
        0x36 => parse_def_table(reader, version),
        0x37 => parse_ptr_array(reader, version),
        0x38 => parse_film(reader, version),
        0x39 => parse_film_layer_list(reader),
        0x3A => parse_film_list_node(reader, version),
        0x3B => parse_property(reader, version),
        0x3C => parse_key_list(reader, version),
        _ => Err(BrdParseError::Invalid(format!(
            "unsupported block type 0x{block_type:02x}"
        ))),
    }
}

fn parse_arc_or_segment(
    reader: &mut Reader<'_>,
    version: FormatVersion,
    block_type: u8,
    arc: bool,
) -> Result<BlockParse, BrdParseError> {
    if arc {
        reader.skip(1)?;
        let _unknown_byte = reader.u8()?;
        let subtype = reader.u8()?;
        let key = reader.u32()?;
        let next = reader.u32()?;
        let parent = reader.u32()?;
        let _unknown1 = reader.u32()?;
        if version.ge(FormatVersion::V172) {
            reader.skip_u32(1)?;
        }
        let width_raw = reader.u32()?;
        let start_raw = [reader.i32()?, reader.i32()?];
        let end_raw = [reader.i32()?, reader.i32()?];
        let center_raw = [reader.allegro_f64()?, reader.allegro_f64()?];
        let radius_raw = reader.allegro_f64()?;
        let bbox_raw = reader.i32_array4()?;
        let clockwise = (subtype & 0x40) != 0;
        return Ok(BlockParse {
            key: Some(key),
            next: Some(next),
            segment: Some(Segment {
                key,
                next,
                parent,
                block_type,
                kind: "arc".to_string(),
                width_raw,
                start_raw,
                end_raw,
                center_raw: Some(center_raw),
                radius_raw: Some(radius_raw),
                bbox_raw: Some(bbox_raw),
                clockwise: Some(clockwise),
            }),
            ..BlockParse::default()
        });
    }
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    let parent = reader.u32()?;
    let _flags = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let width_raw = reader.u32()?;
    let start_raw = [reader.i32()?, reader.i32()?];
    let end_raw = [reader.i32()?, reader.i32()?];
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        segment: Some(Segment {
            key,
            next,
            parent,
            block_type,
            kind: "line".to_string(),
            width_raw,
            start_raw,
            end_raw,
            center_raw: None,
            radius_raw: None,
            bbox_raw: None,
            clockwise: None,
        }),
        ..BlockParse::default()
    })
}

fn parse_field(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let _hdr = reader.u16()?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let subtype = reader.u8()?;
    let _hdr2 = reader.u8()?;
    let size = reader.u16()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    match subtype {
        0x65 => {}
        0x64 | 0x66 | 0x67 | 0x6A => reader.skip_u32(1)?,
        0x69 => reader.skip_u32(2)?,
        0x68 | 0x6B | 0x6D | 0x6E | 0x6F | 0x71 | 0x73 | 0x78 => {
            let _ = reader.fixed_string(size as usize, true)?;
        }
        0x6C => {
            let n = guarded_count(reader.u32()?, "0x03 subtype 0x6c")?;
            reader.skip_u32(n as usize)?;
        }
        0x70 | 0x74 => {
            let x0 = reader.u16()? as usize;
            let x1 = reader.u16()? as usize;
            reader.skip(x1 + 4 * x0)?;
        }
        0xF6 => reader.skip_u32(20)?,
        _ if size == 0 => {}
        _ if size == 4 => reader.skip_u32(1)?,
        _ if size == 8 => reader.skip_u32(2)?,
        _ => {
            reader.skip(size as usize)?;
            reader.align_u32()?;
        }
    }
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        ..BlockParse::default()
    })
}

fn parse_net_assignment(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    let net = reader.u32()?;
    let conn_item = reader.u32()?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        net_assignment: Some(NetAssignment {
            key,
            next,
            net,
            conn_item,
        }),
        ..BlockParse::default()
    })
}

fn parse_track(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let layer = parse_layer_info(reader)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    let net_assignment = reader.u32()?;
    reader.skip_u32(8)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(2)?;
    }
    let first_segment = reader.u32()?;
    reader.skip_u32(2)?;
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        track: Some(Track {
            key,
            next,
            layer,
            net_assignment,
            first_segment,
        }),
        ..BlockParse::default()
    })
}

fn parse_component(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(6)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_component_inst(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(3)?;
    }
    reader.skip_u32(1)?;
    if version.lt(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(5)?;
    Ok(with_key_next(key, next))
}

fn parse_pin_number(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    if version.lt(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let next = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(1)?;
    Ok(with_key_next(key, next))
}

fn parse_fill_link(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    reader.skip_u32(4)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(5)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_drc(reader: &mut Reader<'_>, version: FormatVersion) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip(16)?;
    reader.skip_u32(4)?;
    reader.skip_u32(5)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_pin_def(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(2)?;
    if version.ge(FormatVersion::V172) {
        reader.skip(12)?;
    } else {
        reader.skip(8)?;
    }
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V180) {
        reader.skip_u32(1)?;
    }
    reader.skip(16)?;
    reader.skip_u32(3)?;
    if version.ge(FormatVersion::V174) && version.lt(FormatVersion::V180) {
        reader.skip_u32(1)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_pad(reader: &mut Reader<'_>, version: FormatVersion) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    reader.skip_u32(1)?;
    let next = reader.u32()?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    reader.skip(8)?;
    reader.skip_u32(2)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(2)?;
    Ok(with_key_next(key, next))
}

fn parse_rect_0e(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(4)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(2)?;
    }
    reader.skip(16)?;
    reader.skip_u32(3)?;
    reader.skip_u32(1)?;
    Ok(with_key_next(key, next))
}

fn parse_function_slot(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    if version.ge(FormatVersion::V181) {
        reader.skip_u32(3)?;
        let next = reader.u32()?;
        reader.skip_u32(3)?;
        return Ok(with_key_next(key, next));
    }
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    reader.skip(32)?;
    let next = if version.ge(FormatVersion::V172) {
        Some(reader.u32()?)
    } else {
        None
    };
    reader.skip_u32(3)?;
    Ok(BlockParse {
        key: Some(key),
        next,
        ..BlockParse::default()
    })
}

fn parse_function_inst(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(5)?;
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_pin_name(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    reader.skip_u32(1)?;
    let next = reader.u32()?;
    reader.skip_u32(2)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_xref(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    reader.skip_u32(4)?;
    if version.ge(FormatVersion::V165) {
        reader.skip_u32(1)?;
    }
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_graphic(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(2)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(3)?;
    Ok(with_key_next(key, next))
}

fn parse_net(reader: &mut Reader<'_>, version: FormatVersion) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    let name_string_id = reader.u32()?;
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(1)?;
    let assignment = reader.u32()?;
    reader.skip_u32(1)?;
    let fields = reader.u32()?;
    let match_group = reader.u32()?;
    reader.skip_u32(4)?;
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        net: Some(Net {
            key,
            next,
            name_string_id,
            name: None,
            assignment,
            fields,
            match_group,
        }),
        ..BlockParse::default()
    })
}

fn parse_padstack(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let n = reader.u8()?;
    reader.skip(1)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    let name_string_id = reader.u32()?;
    let (layer_count, drill_size_raw) = if version.lt(FormatVersion::V172) {
        let drill = reader.u32()?;
        reader.skip_u32(5)?;
        reader.skip(4)?;
        reader.skip(2)?;
        reader.skip(4)?;
        let layer_count = reader.u16()?;
        reader.skip_u32(8)?;
        if version.ge(FormatVersion::V165) {
            reader.skip_u32(1)?;
        }
        (layer_count, Some(drill))
    } else {
        reader.skip_u32(3)?;
        reader.skip(4)?;
        reader.skip_u32(2)?;
        reader.skip(4)?;
        let layer_count = reader.u16()?;
        reader.skip(2)?;
        reader.skip_u32(4)?;
        let drill = reader.u32()?;
        reader.skip_u32(6)?;
        reader.skip_u32(4)?;
        reader.skip_u32(21)?;
        if version.ge(FormatVersion::V180) {
            reader.skip_u32(8)?;
        }
        (layer_count, Some(drill))
    };
    if layer_count > MAX_LAYER_COUNT {
        return Err(BrdParseError::Invalid(format!(
            "padstack layer count {layer_count} exceeds {MAX_LAYER_COUNT}"
        )));
    }
    let fixed_component_count = if version.lt(FormatVersion::V165) {
        10
    } else if version.lt(FormatVersion::V172) {
        11
    } else {
        21
    };
    let components_per_layer = if version.lt(FormatVersion::V172) {
        3
    } else {
        4
    };
    let component_count = fixed_component_count + layer_count as usize * components_per_layer;
    for index in 0..component_count {
        reader.skip(4)?;
        if version.ge(FormatVersion::V172) {
            reader.skip_u32(1)?;
        }
        reader.skip(8)?;
        if version.ge(FormatVersion::V172) {
            reader.skip(4)?;
        }
        reader.skip(8)?;
        reader.skip_u32(1)?;
        if version.ge(FormatVersion::V172) || index < component_count - 1 {
            reader.skip_u32(1)?;
        }
    }
    let trailing = n as usize
        * if version.lt(FormatVersion::V172) {
            8
        } else {
            10
        };
    reader.skip_u32(trailing)?;
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        padstack: Some(Padstack {
            key,
            next,
            name_string_id,
            name: None,
            layer_count,
            drill_size_raw,
            fixed_component_count,
            components_per_layer,
        }),
        ..BlockParse::default()
    })
}

fn parse_constraint_set(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(2)?;
    let size_a = reader.u16()? as usize;
    let size_b = reader.u16()? as usize;
    reader.skip(size_b * 56)?;
    reader.skip(size_a * 256)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_si_model(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    if version.ge(FormatVersion::V164) {
        reader.skip(4)?;
    }
    reader.skip_u32(1)?;
    let size = reader.u32()? as usize;
    let _ = reader.fixed_string(size, true)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    if version.ge(FormatVersion::V181) {
        align_to_expected_key(reader, next, 16)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_padstack_dim(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(3)?;
    reader.skip(2)?;
    let size = reader.u16()? as usize;
    let sub_size = if version.ge(FormatVersion::V175) {
        size * 384 + 8
    } else if version.ge(FormatVersion::V172) {
        size * 280 + 8
    } else if version.ge(FormatVersion::V162) {
        size * 280 + 4
    } else {
        size * 240 + 4
    };
    reader.skip(sub_size)?;
    Ok(with_key_next(key, next))
}

fn parse_0x20(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(7)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(10)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_blob_0x21(reader: &mut Reader<'_>) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let size = reader.u32()?;
    if size < 12 {
        return Err(BrdParseError::Invalid(format!(
            "block 0x21 size {size} is too small"
        )));
    }
    let key = reader.u32()?;
    reader.skip(size as usize - 12)?;
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_0x22(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(8)?;
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_ratline(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(4)?;
    reader.skip(20)?;
    reader.skip_u32(4)?;
    if version.ge(FormatVersion::V164) {
        reader.skip_u32(4)?;
    }
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_rect_0x24(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(2)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip(16)?;
    reader.skip_u32(4)?;
    Ok(with_key_next(key, next))
}

fn parse_match_group(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(2)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_xref_0x27(reader: &mut Reader<'_>, x27_end: usize) -> Result<BlockParse, BrdParseError> {
    if x27_end <= reader.position() {
        return Err(BrdParseError::Invalid(format!(
            "block 0x27 end 0x{x27_end:08x} is before current offset 0x{:08x}",
            reader.position()
        )));
    }
    let total = x27_end - 1 - reader.position();
    reader.skip(total)?;
    Ok(BlockParse::default())
}

fn parse_shape(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let layer = parse_layer_info(reader)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(2)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(2)?;
    }
    reader.skip_u32(2)?;
    let first_keepout = reader.u32()?;
    let first_segment = reader.u32()?;
    reader.skip_u32(2)?;
    let table = if version.ge(FormatVersion::V172) {
        reader.u32()?
    } else {
        0
    };
    reader.skip_u32(1)?;
    let table = if version.lt(FormatVersion::V172) {
        reader.u32()?
    } else {
        table
    };
    let coords_raw = reader.i32_array4()?;
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        shape: Some(Shape {
            key,
            next,
            layer,
            first_segment,
            first_keepout,
            table,
            coords_raw,
        }),
        ..BlockParse::default()
    })
}

fn parse_pin_0x29(reader: &mut Reader<'_>) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    reader.skip_u32(4)?;
    reader.skip(8)?;
    reader.skip_u32(5)?;
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_layer_list(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let num_entries = reader.u16()? as usize;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    let mut names = Vec::new();
    if version.lt(FormatVersion::V165) {
        for _ in 0..num_entries {
            names.push(reader.fixed_string(36, true)?);
        }
    } else {
        for _ in 0..num_entries {
            let name_id = reader.u32()?;
            names.push(format!("string:{name_id}"));
            reader.skip_u32(2)?;
        }
    }
    let key = reader.u32()?;
    Ok(BlockParse {
        key: Some(key),
        layer: Some(Layer {
            key,
            class_code: 0,
            names,
        }),
        ..BlockParse::default()
    })
}

fn parse_footprint(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let name_string_id = reader.u32()?;
    reader.skip_u32(1)?;
    let coords_raw = reader.u32_array4()?;
    let next = reader.u32()?;
    let first_instance = reader.u32()?;
    reader.skip_u32(3)?;
    let sym_lib_path_string_id = reader.u32()?;
    reader.skip_u32(3)?;
    if version.ge(FormatVersion::V164) {
        reader.skip_u32(1)?;
    }
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        footprint: Some(Footprint {
            key,
            next,
            name_string_id,
            name: None,
            first_instance,
            sym_lib_path_string_id,
            sym_lib_path: None,
            coords_raw,
        }),
        ..BlockParse::default()
    })
}

fn parse_table(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(3)?;
    }
    reader.skip_u32(1)?;
    if version.lt(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(4)?;
    Ok(with_key_next(key, next))
}

fn parse_footprint_inst(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    if version.lt(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip(4)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(1)?;
    reader.skip_u32(1)?;
    reader.skip(8)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(7)?;
    Ok(with_key_next(key, next))
}

fn parse_connection(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(6)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_0x2f(reader: &mut Reader<'_>) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    reader.skip_u32(6)?;
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_text_wrapper(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let layer = parse_layer_info(reader)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(2)?;
        reader.skip(4)?;
        reader.skip_u32(1)?;
    }
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    let string_graphic_key = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    } else {
        reader.skip_u32(1)?;
        reader.skip(4)?;
    }
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let x_raw = reader.i32()?;
    let y_raw = reader.i32()?;
    reader.skip_u32(1)?;
    let rotation_mdeg = reader.u32()?;
    if version.lt(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        text: Some(Text {
            key,
            next: Some(next),
            layer: Some(layer),
            text: None,
            x_raw: Some(x_raw),
            y_raw: Some(y_raw),
            rotation_mdeg: Some(rotation_mdeg),
            string_graphic_key: Some(string_graphic_key),
        }),
        ..BlockParse::default()
    })
}

fn parse_string_graphic(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let wrapper = reader.u32()?;
    let x_raw = reader.i32()?;
    let y_raw = reader.i32()?;
    reader.skip(2)?;
    let len = reader.u16()?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    let text = reader.fixed_string(len as usize, true)?;
    Ok(BlockParse {
        key: Some(key),
        text: Some(Text {
            key,
            next: None,
            layer: None,
            text: Some(text),
            x_raw: Some(x_raw),
            y_raw: Some(y_raw),
            rotation_mdeg: None,
            string_graphic_key: Some(wrapper),
        }),
        ..BlockParse::default()
    })
}

fn parse_placed_pad(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let layer = parse_layer_info(reader)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    let net_assignment = reader.u32()?;
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(1)?;
    let parent_footprint = reader.u32()?;
    reader.skip_u32(1)?;
    let pad = reader.u32()?;
    reader.skip_u32(2)?;
    let pin_number = reader.u32()?;
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let name_text = reader.u32()?;
    reader.skip_u32(1)?;
    let coords_raw = reader.i32_array4()?;
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        placed_pad: Some(PlacedPad {
            key,
            next,
            layer,
            net_assignment,
            parent_footprint,
            pad,
            pin_number,
            name_text,
            coords_raw,
        }),
        ..BlockParse::default()
    })
}

fn parse_via(reader: &mut Reader<'_>, version: FormatVersion) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let layer = parse_layer_info(reader)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    let net_assignment = reader.u32()?;
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let x_raw = reader.i32()?;
    let y_raw = reader.i32()?;
    reader.skip_u32(1)?;
    let padstack = reader.u32()?;
    reader.skip_u32(4)?;
    reader.skip(16)?;
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        via: Some(Via {
            key,
            next,
            layer,
            net_assignment,
            padstack,
            x_raw,
            y_raw,
        }),
        ..BlockParse::default()
    })
}

fn parse_keepout(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let layer = parse_layer_info(reader)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let flags = reader.u32()?;
    let first_segment = reader.u32()?;
    reader.skip_u32(2)?;
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        keepout: Some(Keepout {
            key,
            next,
            layer,
            flags,
            first_segment,
        }),
        ..BlockParse::default()
    })
}

fn parse_file_ref(reader: &mut Reader<'_>) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    reader.skip(120)?;
    Ok(BlockParse::default())
}

fn parse_def_table(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let code = reader.u16()?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let num_items = guarded_count(reader.u32()?, "0x36 num_items")?;
    let count = reader.u32()?;
    if count > num_items as u32 {
        return Err(BrdParseError::Invalid(format!(
            "block 0x36 count {count} exceeds capacity {num_items}"
        )));
    }
    reader.skip_u32(2)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    for _ in 0..num_items {
        match code {
            0x02 => {
                let _ = reader.fixed_string(32, true)?;
                reader.skip_u32(14)?;
                if version.ge(FormatVersion::V164) {
                    reader.skip_u32(3)?;
                }
                if version.ge(FormatVersion::V172) {
                    reader.skip_u32(2)?;
                }
            }
            0x03 => {
                let _ = reader.fixed_string(
                    if version.ge(FormatVersion::V172) {
                        64
                    } else {
                        32
                    },
                    true,
                )?;
                if version.ge(FormatVersion::V174) {
                    reader.skip_u32(1)?;
                }
            }
            0x05 => {
                reader.skip(28)?;
                if version.ge(FormatVersion::V174) {
                    reader.skip_u32(1)?;
                }
            }
            0x06 => {
                reader.skip(8)?;
                if version.lt(FormatVersion::V172) {
                    reader.skip_u32(50)?;
                }
            }
            0x08 => {
                reader.skip_u32(4)?;
                if version.ge(FormatVersion::V174) && version.lt(FormatVersion::V181) {
                    reader.skip_u32(1)?;
                }
                reader.skip_u32(4)?;
                if version.ge(FormatVersion::V172) {
                    reader.skip_u32(8)?;
                }
            }
            0x0B => reader.skip(1016)?,
            0x0C => reader.skip(232)?,
            0x0D => reader.skip(200)?,
            0x0F => reader.skip_u32(5)?,
            0x10 => {
                reader.skip(108)?;
                if version.ge(FormatVersion::V180) {
                    reader.skip_u32(1)?;
                }
            }
            0x12 => reader.skip(1052)?,
            _ => {
                return Err(BrdParseError::Invalid(format!(
                    "unknown 0x36 substruct type 0x{code:02x}"
                )))
            }
        }
    }
    Ok(with_key_next(key, next))
}

fn parse_ptr_array(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    reader.skip_u32(1)?;
    let next = reader.u32()?;
    reader.skip_u32(3)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(100)?;
    Ok(with_key_next(key, next))
}

fn parse_film(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(1)?;
    if version.lt(FormatVersion::V166) {
        let _ = reader.fixed_string(20, true)?;
    } else {
        reader.skip_u32(2)?;
    }
    reader.skip_u32(7)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_film_layer_list(reader: &mut Reader<'_>) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    reader.skip_u32(2)?;
    reader.skip(44)?;
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_film_list_node(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let _layer = parse_layer_info(reader)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_property(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let len = reader.u32()? as usize;
    let _ = reader.fixed_string(128, true)?;
    let _ = reader.fixed_string(32, true)?;
    reader.skip_u32(2)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let _ = reader.fixed_string(len, true)?;
    Ok(BlockParse::default())
}

fn parse_key_list(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    let n = guarded_count(reader.u32()?, "0x3c entries")?;
    reader.skip_u32(n as usize)?;
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn with_key_next(key: u32, next: u32) -> BlockParse {
    BlockParse {
        key: Some(key),
        next: Some(next),
        ..BlockParse::default()
    }
}

fn align_to_expected_key(
    reader: &mut Reader<'_>,
    expected_key: u32,
    max_scan: usize,
) -> Result<(), BrdParseError> {
    if expected_key == 0 {
        return Ok(());
    }
    let start = reader.position();
    for extra in (0..=max_scan).step_by(4) {
        let candidate = start + extra;
        if candidate + 8 > reader.bytes.len() {
            break;
        }
        let block_type = reader.bytes[candidate];
        if block_type == 0 || block_type > 0x3C {
            continue;
        }
        let key_offset = candidate + 4;
        let key = u32::from_le_bytes([
            reader.bytes[key_offset],
            reader.bytes[key_offset + 1],
            reader.bytes[key_offset + 2],
            reader.bytes[key_offset + 3],
        ]);
        if key == expected_key {
            reader.seek(candidate)?;
            break;
        }
    }
    Ok(())
}

fn parse_layer_info(reader: &mut Reader<'_>) -> Result<LayerInfo, BrdParseError> {
    let class_code = reader.u8()?;
    let subclass_code = reader.u8()?;
    Ok(LayerInfo {
        class_code,
        subclass_code,
        class_name: layer_class_name(class_code).to_string(),
        subclass_name: fixed_subclass_name(class_code, subclass_code).map(ToOwned::to_owned),
    })
}

fn read_ll(reader: &mut Reader<'_>, version: FormatVersion) -> Result<LinkedList, BrdParseError> {
    let first = reader.u32()?;
    let second = reader.u32()?;
    if version.ge(FormatVersion::V180) {
        Ok(LinkedList {
            head: first,
            tail: second,
        })
    } else {
        Ok(LinkedList {
            head: second,
            tail: first,
        })
    }
}

fn scan_zero_gap(reader: &mut Reader<'_>) -> Result<Option<usize>, BrdParseError> {
    let mut scan_pos = reader.position();
    while let Some(value) = reader.peek_u8()? {
        if value == 0 {
            reader.skip(1)?;
            scan_pos = reader.position();
            continue;
        }
        if value <= 0x3C {
            let block_start = scan_pos - (scan_pos % 4);
            return Ok(Some(block_start));
        }
        return Ok(None);
    }
    Ok(None)
}

fn merge_text(existing: &mut Text, incoming: &Text) {
    if existing.text.is_none() {
        existing.text = incoming.text.clone();
    }
    if existing.layer.is_none() {
        existing.layer = incoming.layer.clone();
    }
    if existing.x_raw.is_none() {
        existing.x_raw = incoming.x_raw;
    }
    if existing.y_raw.is_none() {
        existing.y_raw = incoming.y_raw;
    }
    if existing.rotation_mdeg.is_none() {
        existing.rotation_mdeg = incoming.rotation_mdeg;
    }
    if existing.string_graphic_key.is_none() {
        existing.string_graphic_key = incoming.string_graphic_key;
    }
}

fn guarded_count(value: u32, label: &str) -> Result<usize, BrdParseError> {
    if value > MAX_VECTOR_COUNT {
        return Err(BrdParseError::Invalid(format!(
            "{label} count {value} exceeds limit {MAX_VECTOR_COUNT}"
        )));
    }
    Ok(value as usize)
}

fn board_units_name(code: u8) -> &'static str {
    match code {
        0x01 => "mils",
        0x02 => "inches",
        0x03 => "millimeters",
        0x04 => "centimeters",
        0x05 => "micrometers",
        _ => "unknown",
    }
}

fn layer_class_name(code: u8) -> &'static str {
    match code {
        0x01 => "BOARD_GEOMETRY",
        0x02 => "COMPONENT_VALUE",
        0x03 => "DEVICE_TYPE",
        0x04 => "DRAWING_FORMAT",
        0x05 => "DRC_ERROR",
        0x06 => "ETCH",
        0x07 => "MANUFACTURING",
        0x08 => "ANALYSIS",
        0x09 => "PACKAGE_GEOMETRY",
        0x0A => "PACKAGE_KEEPIN",
        0x0B => "PACKAGE_KEEPOUT",
        0x0C => "PIN",
        0x0D => "REF_DES",
        0x0E => "ROUTE_KEEPIN",
        0x0F => "ROUTE_KEEPOUT",
        0x10 => "TOLERANCE",
        0x11 => "USER_PART_NUMBER",
        0x12 => "VIA_CLASS",
        0x13 => "VIA_KEEPOUT",
        0x14 => "ANTI_ETCH",
        0x15 => "BOUNDARY",
        0x16 => "CONSTRAINTS_REGION",
        _ => "UNKNOWN",
    }
}

fn fixed_subclass_name(class_code: u8, subclass_code: u8) -> Option<&'static str> {
    match (class_code, subclass_code) {
        (0x01, 0xEA) => Some("BGEOM_OUTLINE"),
        (0x04, 0xFD) => Some("DFMT_OUTLINE"),
        (_, 0xF8) => Some("DISPLAY_BOTTOM"),
        (_, 0xF9) => Some("DISPLAY_TOP"),
        (_, 0xFA) => Some("SILKSCREEN_BOTTOM"),
        (_, 0xFB) => Some("SILKSCREEN_TOP"),
        (_, 0xFC) => Some("ASSEMBLY_BOTTOM"),
        (_, 0xFD) => Some("ASSEMBLY_TOP_OR_ALL"),
        _ => None,
    }
}

fn block_type_name(block_type: u8) -> &'static str {
    match block_type {
        0x01 => "ARC",
        0x03 => "FIELD",
        0x04 => "NET_ASSIGNMENT",
        0x05 => "TRACK",
        0x06 => "COMPONENT",
        0x07 => "COMPONENT_INST",
        0x08 => "PIN_NUMBER",
        0x09 => "FILL_LINK",
        0x0A => "DRC",
        0x0C => "PIN_DEF",
        0x0D => "PAD",
        0x0E => "RECT_0E",
        0x0F => "FUNCTION_SLOT",
        0x10 => "FUNCTION_INST",
        0x11 => "PIN_NAME",
        0x12 => "XREF",
        0x14 => "GRAPHIC",
        0x15 | 0x16 | 0x17 => "SEGMENT",
        0x1B => "NET",
        0x1C => "PADSTACK",
        0x1D => "CONSTRAINT_SET",
        0x1E => "SI_MODEL",
        0x1F => "PADSTACK_DIM",
        0x20 => "UNKNOWN_20",
        0x21 => "BLOB",
        0x22 => "UNKNOWN_22",
        0x23 => "RATLINE",
        0x24 => "RECT",
        0x26 => "MATCH_GROUP",
        0x27 => "CSTRMGR_XREF",
        0x28 => "SHAPE",
        0x29 => "PIN",
        0x2A => "LAYER_LIST",
        0x2B => "FOOTPRINT_DEF",
        0x2C => "TABLE",
        0x2D => "FOOTPRINT_INST",
        0x2E => "CONNECTION",
        0x2F => "UNKNOWN_2F",
        0x30 => "TEXT_WRAPPER",
        0x31 => "STRING_GRAPHIC",
        0x32 => "PLACED_PAD",
        0x33 => "VIA",
        0x34 => "KEEPOUT",
        0x35 => "FILE_REF",
        0x36 => "DEF_TABLE",
        0x37 => "PTR_ARRAY",
        0x38 => "FILM",
        0x39 => "FILM_LAYER_LIST",
        0x3A => "FILM_LIST_NODE",
        0x3B => "PROPERTY",
        0x3C => "KEY_LIST",
        _ => "UNKNOWN",
    }
}

struct Reader<'a> {
    bytes: &'a [u8],
    pos: usize,
}

impl<'a> Reader<'a> {
    fn new(bytes: &'a [u8]) -> Self {
        Self { bytes, pos: 0 }
    }

    fn position(&self) -> usize {
        self.pos
    }

    fn eof(&self) -> bool {
        self.pos >= self.bytes.len()
    }

    fn seek(&mut self, pos: usize) -> Result<(), BrdParseError> {
        if pos > self.bytes.len() {
            return Err(BrdParseError::InvalidSeek {
                offset: pos,
                file_size: self.bytes.len(),
            });
        }
        self.pos = pos;
        Ok(())
    }

    fn peek_u8(&self) -> Result<Option<u8>, BrdParseError> {
        Ok(self.bytes.get(self.pos).copied())
    }

    fn skip(&mut self, n: usize) -> Result<(), BrdParseError> {
        self.take(n).map(|_| ())
    }

    fn skip_u32(&mut self, n: usize) -> Result<(), BrdParseError> {
        self.skip(n * 4)
    }

    fn take(&mut self, n: usize) -> Result<&'a [u8], BrdParseError> {
        if n > self.bytes.len() || self.pos > self.bytes.len() - n {
            return Err(BrdParseError::UnexpectedEof {
                offset: self.pos,
                size: n,
                file_size: self.bytes.len(),
            });
        }
        let start = self.pos;
        self.pos += n;
        Ok(&self.bytes[start..start + n])
    }

    fn u8(&mut self) -> Result<u8, BrdParseError> {
        Ok(self.take(1)?[0])
    }

    fn u16(&mut self) -> Result<u16, BrdParseError> {
        let bytes = self.take(2)?;
        Ok(u16::from_le_bytes([bytes[0], bytes[1]]))
    }

    fn u32(&mut self) -> Result<u32, BrdParseError> {
        let bytes = self.take(4)?;
        Ok(u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
    }

    fn i32(&mut self) -> Result<i32, BrdParseError> {
        let bytes = self.take(4)?;
        Ok(i32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
    }

    fn allegro_f64(&mut self) -> Result<f64, BrdParseError> {
        let high = self.u32()? as u64;
        let low = self.u32()? as u64;
        Ok(f64::from_bits((high << 32) | low))
    }

    fn u32_array4(&mut self) -> Result<[u32; 4], BrdParseError> {
        Ok([self.u32()?, self.u32()?, self.u32()?, self.u32()?])
    }

    fn i32_array4(&mut self) -> Result<[i32; 4], BrdParseError> {
        Ok([self.i32()?, self.i32()?, self.i32()?, self.i32()?])
    }

    fn c_string(&mut self, align_u32: bool) -> Result<String, BrdParseError> {
        let start = self.pos;
        let Some(relative_end) = self.bytes[start..].iter().position(|value| *value == 0) else {
            return Err(BrdParseError::UnterminatedString { offset: start });
        };
        let end = start + relative_end;
        let value = String::from_utf8_lossy(&self.bytes[start..end]).to_string();
        self.pos = end + 1;
        if align_u32 {
            self.align_u32()?;
        }
        Ok(value)
    }

    fn fixed_string(&mut self, len: usize, align_u32: bool) -> Result<String, BrdParseError> {
        let bytes = self.take(len)?;
        let end = bytes
            .iter()
            .position(|value| *value == 0)
            .unwrap_or(bytes.len());
        let value = String::from_utf8_lossy(&bytes[..end]).to_string();
        if align_u32 {
            self.align_u32()?;
        }
        Ok(value)
    }

    fn align_u32(&mut self) -> Result<(), BrdParseError> {
        let remainder = self.pos % 4;
        if remainder != 0 {
            self.skip(4 - remainder)?;
        }
        Ok(())
    }
}
