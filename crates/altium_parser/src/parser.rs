mod binary_records;
mod cfb;
mod constants;
mod geometry;
mod layers;
mod primitive_names;
mod properties;
mod property_records;
mod reader;
mod strings;

use self::binary_records::{
    parse_arc_record, parse_binary_records, parse_binary_records_lossy, parse_fill_record,
    parse_pad_record, parse_region_record, parse_text_record, parse_track_record, parse_via_record,
    parse_wide_string_table,
};
use self::cfb::CompoundFile;
use self::constants::ALTIUM_POLYGON_BOARD;
use self::layers::layer_name_map;
use self::property_records::{
    parse_board_stream, parse_class_record, parse_component_record, parse_file_header,
    parse_net_record, parse_polygon_record, parse_property_records, parse_rules_stream,
};
use crate::model::{
    Arc, Board, Class, Component, Fill, Layer, Net, Pad, Polygon, Region, Rule, StreamSummary,
    Summary, Text, Track, Via,
};
use std::collections::BTreeMap;
use thiserror::Error;

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
    if let Some(data) = compound.find_stream("ShapeBasedRegions6") {
        let (parsed, error) = parse_binary_records_lossy(data, |reader, index| {
            parse_region_record(reader, index, true, &layer_names)
        });
        if !parsed.is_empty() {
            parsed_stream_count += 1;
            regions.extend(parsed);
            mark_stream_parsed(&mut stream_summaries, "ShapeBasedRegions6");
        }
        if let Some(error) = error {
            diagnostics.push(format!("ShapeBasedRegions6 parse failed: {error}"));
        }
    }
    if let Some(data) = compound.find_stream("Regions6") {
        let base_index = regions.len();
        match parse_binary_records(data, |reader, index| {
            parse_region_record(reader, index + base_index, false, &layer_names)
        }) {
            Ok(parsed) => {
                parsed_stream_count += 1;
                regions.extend(parsed);
                mark_stream_parsed(&mut stream_summaries, "Regions6");
            }
            Err(error) => diagnostics.push(format!("Regions6 parse failed: {error}")),
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

    let board_outline_vertex_count = board.as_ref().map(|item| item.outline.len()).unwrap_or(0)
        + regions
            .iter()
            .filter(|region| {
                region.kind == "board_cutout" || region.polygon == ALTIUM_POLYGON_BOARD
            })
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
        if path == name
            || path == format!("{name}/data")
            || path.ends_with(&format!("/{name}/data"))
        {
            stream.parsed = true;
        }
    }
}
