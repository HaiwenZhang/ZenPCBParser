mod blocks;
mod constants;
mod header;
mod reader;

use self::blocks::{block_type_name, merge_text, parse_block, scan_zero_gap};
use self::header::{after_string_table_offset, parse_header, parse_strings, resolve_layer_names};
use self::reader::Reader;
use crate::model::{
    BlockSummary, Component, ComponentInstance, Footprint, FootprintInstance, Header, Keepout,
    Layer, Net, NetAssignment, PadDefinition, Padstack, PlacedPad, Segment, Shape, StringEntry,
    Summary, Text, Track, Via,
};
use std::collections::{BTreeMap, HashMap};
use thiserror::Error;

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
    pub(crate) fn from_magic(magic: u32) -> Result<Self, BrdParseError> {
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

    pub(crate) fn label(self) -> &'static str {
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

    pub(crate) fn ge(self, other: Self) -> bool {
        self >= other
    }

    pub(crate) fn lt(self, other: Self) -> bool {
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
    pub components: Option<Vec<Component>>,
    pub component_instances: Option<Vec<ComponentInstance>>,
    pub footprints: Option<Vec<Footprint>>,
    pub footprint_instances: Option<Vec<FootprintInstance>>,
    pub pad_definitions: Option<Vec<PadDefinition>>,
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
    let mut components = Vec::new();
    let mut component_instances = Vec::new();
    let mut footprints = Vec::new();
    let mut footprint_instances = Vec::new();
    let mut pad_definitions = Vec::new();
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
        if let Some(mut component) = parsed.component {
            component.device_type = string_map.get(&component.device_type_string_id).cloned();
            component.symbol_name = string_map.get(&component.symbol_name_string_id).cloned();
            components.push(component);
        }
        if let Some(mut component_instance) = parsed.component_instance {
            component_instance.refdes = string_map
                .get(&component_instance.refdes_string_id)
                .cloned();
            component_instances.push(component_instance);
        }
        if let Some(mut footprint) = parsed.footprint {
            footprint.name = string_map.get(&footprint.name_string_id).cloned();
            footprint.sym_lib_path = string_map.get(&footprint.sym_lib_path_string_id).cloned();
            footprints.push(footprint);
        }
        if let Some(footprint_instance) = parsed.footprint_instance {
            footprint_instances.push(footprint_instance);
        }
        if let Some(mut pad_definition) = parsed.pad_definition {
            pad_definition.name = string_map.get(&pad_definition.name_string_id).cloned();
            pad_definitions.push(pad_definition);
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
        components: options.include_details.then_some(components),
        component_instances: options.include_details.then_some(component_instances),
        footprints: options.include_details.then_some(footprints),
        footprint_instances: options.include_details.then_some(footprint_instances),
        pad_definitions: options.include_details.then_some(pad_definitions),
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
