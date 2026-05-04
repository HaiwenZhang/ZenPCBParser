use crate::model::{
    Board, Component, Extents, Graphic, Layer, Pad, Padstack, Pin, Point, Shape, Summary, Symbol,
    Track, Via,
};
use std::collections::{BTreeMap, BTreeSet};
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum ParseError {
    #[error("failed to open ALG file {path}: {source}")]
    Open {
        path: String,
        #[source]
        source: std::io::Error,
    },
    #[error("failed to read ALG file {path}: {source}")]
    Read {
        path: String,
        #[source]
        source: std::io::Error,
    },
}

#[derive(Debug, Clone, Default)]
pub struct ParseOptions {
    pub include_details: bool,
}

#[derive(Debug, Clone, Default)]
pub struct ParsedAlg {
    pub summary: Summary,
    pub board: Option<Board>,
    pub layers: Option<Vec<Layer>>,
    pub components: Option<Vec<Component>>,
    pub pins: Option<Vec<Pin>>,
    pub padstacks: Option<Vec<Padstack>>,
    pub pads: Option<Vec<Pad>>,
    pub vias: Option<Vec<Via>>,
    pub tracks: Option<Vec<Track>>,
    pub symbols: Option<Vec<Symbol>>,
    pub outlines: Option<Vec<Graphic>>,
    pub section_counts: BTreeMap<String, usize>,
    pub diagnostics: Vec<String>,
    pub alg_revision: Option<String>,
    pub extracta_version: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Section {
    Unknown,
    Board,
    Layer,
    Component,
    Connectivity,
    CompositePad,
    ComponentPin,
    FullGeometry,
    Function,
    LogicalPin,
    Net,
    Rat,
    Symbol,
    Zone,
    Bend,
}

impl Default for Section {
    fn default() -> Self {
        Section::Unknown
    }
}

impl Section {
    fn name(self) -> &'static str {
        match self {
            Section::Unknown => "unknown",
            Section::Board => "board",
            Section::Layer => "layer",
            Section::Component => "component",
            Section::Connectivity => "connectivity",
            Section::CompositePad => "composite_pad",
            Section::ComponentPin => "component_pin",
            Section::FullGeometry => "full_geometry",
            Section::Function => "function",
            Section::LogicalPin => "logical_pin",
            Section::Net => "net",
            Section::Rat => "rat",
            Section::Symbol => "symbol",
            Section::Zone => "zone",
            Section::Bend => "bend",
        }
    }
}

#[derive(Debug, Default)]
struct ParserState {
    current_section: Section,
    current_fields: BTreeMap<String, usize>,
    section_index: usize,
    board: Option<Board>,
    layers: Vec<Layer>,
    components: Vec<Component>,
    pins: Vec<Pin>,
    padstacks: BTreeMap<String, Padstack>,
    pads: Vec<Pad>,
    vias: BTreeMap<String, Via>,
    tracks: Vec<Track>,
    symbols: Vec<Symbol>,
    outlines: Vec<Graphic>,
    metal_layers: BTreeSet<String>,
    seen_pads: BTreeSet<String>,
    seen_pins: BTreeSet<String>,
    seen_components: BTreeSet<String>,
    seen_nets: BTreeSet<String>,
    section_counts: BTreeMap<String, usize>,
    diagnostics: Vec<String>,
    summary: Summary,
    alg_revision: Option<String>,
    extracta_version: Option<String>,
    include_details: bool,
}

pub fn parse_alg_file(path: &Path, options: &ParseOptions) -> Result<ParsedAlg, ParseError> {
    let file = File::open(path).map_err(|source| ParseError::Open {
        path: path.display().to_string(),
        source,
    })?;
    let mut reader = BufReader::new(file);
    let mut state = ParserState {
        include_details: options.include_details,
        ..ParserState::default()
    };
    let mut line = String::new();
    loop {
        line.clear();
        let bytes = reader
            .read_line(&mut line)
            .map_err(|source| ParseError::Read {
                path: path.display().to_string(),
                source,
            })?;
        if bytes == 0 {
            break;
        }
        state.summary.line_count += 1;
        let trimmed = line.trim_end_matches(['\r', '\n']);
        state.parse_line(trimmed);
    }
    Ok(state.finish())
}

impl ParserState {
    fn parse_line(&mut self, line: &str) {
        if line.is_empty() {
            return;
        }
        if line.starts_with('#') {
            self.parse_comment(line);
            return;
        }
        if line.starts_with("A!") {
            self.parse_header(line);
            return;
        }
        if line.starts_with("S!") {
            self.summary.data_record_count += 1;
            *self
                .section_counts
                .entry(self.current_section.name().to_string())
                .or_insert(0) += 1;
            self.parse_data(line);
        }
    }

    fn parse_comment(&mut self, line: &str) {
        let text = line.trim_start_matches('#').trim();
        if let Some(value) = text.strip_prefix("ALG for Aurora:") {
            self.alg_revision = Some(value.trim().to_string());
        } else if let Some(value) = text.strip_prefix("extracta version:") {
            let version = value.trim().to_string();
            self.extracta_version = Some(version.clone());
            self.summary.extracta_version = Some(version);
        }
    }

    fn parse_header(&mut self, line: &str) {
        self.section_index += 1;
        self.summary.section_count = self.section_index;
        self.current_fields.clear();
        for (index, field) in line.split('!').skip(1).enumerate() {
            if !field.is_empty() {
                self.current_fields.insert(field.to_string(), index);
            }
        }
        self.current_section = detect_section(&self.current_fields, self.section_index);
    }

    fn parse_data(&mut self, line: &str) {
        let fields: Vec<&str> = line.split('!').skip(1).collect();
        match self.current_section {
            Section::Board => self.parse_board(&fields),
            Section::Layer => self.parse_layer(&fields),
            Section::Component => self.parse_component(&fields),
            Section::CompositePad => self.parse_composite_pad(&fields),
            Section::ComponentPin => self.parse_component_pin(&fields),
            Section::FullGeometry => self.parse_full_geometry(&fields),
            Section::LogicalPin => self.parse_logical_pin(&fields),
            Section::Net => self.parse_net(&fields),
            Section::Symbol => self.parse_symbol(&fields),
            Section::Unknown
            | Section::Connectivity
            | Section::Function
            | Section::Rat
            | Section::Zone
            | Section::Bend => {}
        }
    }

    fn parse_board(&mut self, fields: &[&str]) {
        self.summary.board_record_count += 1;
        let units = self.value(fields, "BOARD_UNITS").unwrap_or("unknown");
        let board = Board {
            name: self.value_string(fields, "BOARD_NAME").unwrap_or_default(),
            units: units.to_string(),
            accuracy: self.float_value(fields, "BOARD_ACCURACY"),
            extents: match (
                self.float_value(fields, "BOARD_EXTENTS_X1"),
                self.float_value(fields, "BOARD_EXTENTS_Y1"),
                self.float_value(fields, "BOARD_EXTENTS_X2"),
                self.float_value(fields, "BOARD_EXTENTS_Y2"),
            ) {
                (Some(x1), Some(y1), Some(x2), Some(y2)) => Some(Extents { x1, y1, x2, y2 }),
                _ => None,
            },
            layer_count: self
                .value(fields, "BOARD_LAYERS")
                .and_then(|value| value.trim().parse::<usize>().ok()),
            thickness: self.value_string(fields, "BOARD_THICKNESS"),
            schematic_name: self.value_string(fields, "BOARD_SCHEMATIC_NAME"),
        };
        self.summary.units = board.units.clone();
        self.summary.accuracy = board.accuracy;
        self.summary.board_name = Some(board.name.clone());
        self.board = Some(board);
    }

    fn parse_layer(&mut self, fields: &[&str]) {
        let name = self.value(fields, "LAYER_SUBCLASS").unwrap_or("").trim();
        let layer_type = self.value_string(fields, "LAYER_TYPE");
        let conductor = is_yes(self.value(fields, "LAYER_CONDUCTOR"));
        if conductor && !name.is_empty() {
            self.metal_layers.insert(fold_key(name));
        }
        let layer = Layer {
            sort: self.value_string(fields, "LAYER_SORT"),
            name: name.to_string(),
            artwork: self.value_string(fields, "LAYER_ARTWORK"),
            use_kind: self.value_string(fields, "LAYER_USE"),
            conductor,
            dielectric_constant: self.value_string(fields, "LAYER_DIELECTRIC_CONSTANT"),
            electrical_conductivity: self.value_string(fields, "LAYER_ELECTRICAL_CONDUCTIVITY"),
            loss_tangent: self.value_string(fields, "LAYER_LOSS_TANGENT"),
            material: self.value_string(fields, "LAYER_MATERIAL"),
            shield_layer: self.value_string(fields, "LAYER_SHIELD_LAYER"),
            thermal_conductivity: self.value_string(fields, "LAYER_THERMAL_CONDUCTIVITY"),
            thickness: self.value_string(fields, "LAYER_THICKNESS"),
            layer_type,
        };
        self.layers.push(layer);
    }

    fn parse_component(&mut self, fields: &[&str]) {
        let Some(refdes) = self.value_nonempty(fields, "REFDES") else {
            return;
        };
        if !self.seen_components.insert(refdes.to_string()) {
            return;
        }
        self.components.push(Component {
            refdes: refdes.to_string(),
            class_name: self.value_string(fields, "COMP_CLASS"),
            package: self.value_string(fields, "COMP_PACKAGE"),
            device_type: self.value_string(fields, "COMP_DEVICE_TYPE"),
            value: self.value_string(fields, "COMP_VALUE"),
            part_number: self.value_string(fields, "COMP_PART_NUMBER"),
            room: self.value_string(fields, "COMP_ROOM"),
            bom_ignore: self.value_string(fields, "COMP_BOM_IGNORE"),
        });
    }

    fn parse_composite_pad(&mut self, fields: &[&str]) {
        let Some(name) = self.value_nonempty(fields, "PAD_STACK_NAME") else {
            return;
        };
        if name.eq_ignore_ascii_case("NOPAD") {
            return;
        }
        let start_layer = self.value_string(fields, "START_LAYER_NAME");
        let end_layer = self.value_string(fields, "END_LAYER_NAME");
        let pad_stack_type = self.value_string(fields, "PAD_STACK_TYPE");
        let drill_hole_name = self.value_string(fields, "DRILL_HOLE_NAME");
        let drill_figure_shape = self.value_string(fields, "DRILL_FIGURE_SHAPE");
        let drill_figure_width = self.float_value(fields, "DRILL_FIGURE_WIDTH");
        let drill_figure_height = self.float_value(fields, "DRILL_FIGURE_HEIGHT");
        let drill_figure_rotation = self.float_value(fields, "DRILL_FIGURE_ROTATION");
        let via_pad_stack_name = self.value_string(fields, "VIA_PAD_STACK_NAME");
        let key = format!(
            "{}|{}|{}",
            name,
            start_layer.as_deref().unwrap_or(""),
            end_layer.as_deref().unwrap_or("")
        );
        self.padstacks.entry(key).or_insert_with(|| Padstack {
            name: name.to_string(),
            pad_stack_type,
            start_layer,
            end_layer,
            drill_hole_name,
            drill_figure_shape,
            drill_figure_width,
            drill_figure_height,
            drill_figure_rotation,
            via_pad_stack_name,
        });
    }

    fn parse_component_pin(&mut self, fields: &[&str]) {
        let Some(refdes) = self.value_nonempty(fields, "REFDES") else {
            return;
        };
        let Some(pin_number) = self.value_nonempty(fields, "PIN_NUMBER") else {
            return;
        };
        let key = format!("{refdes}|{pin_number}");
        if !self.seen_pins.insert(key) {
            return;
        }
        self.pins.push(Pin {
            refdes: refdes.to_string(),
            pin_number: pin_number.to_string(),
            x: self.float_value(fields, "PIN_X"),
            y: self.float_value(fields, "PIN_Y"),
            pad_stack_name: self.value_string(fields, "PAD_STACK_NAME"),
            pin_type: self.value_string(fields, "PIN_TYPE"),
            net_name: self.value_string(fields, "NET_NAME"),
            pin_name: None,
        });
    }

    fn parse_full_geometry(&mut self, fields: &[&str]) {
        let class_name = self.value(fields, "CLASS").unwrap_or("");
        match class_name {
            "ETCH" | "CONDUCTOR" => self.parse_track(fields),
            "PIN" => self.parse_pad(fields),
            "VIA CLASS" => self.parse_via(fields),
            "BOARD GEOMETRY" | "SUBSTRATE GEOMETRY" => self.parse_outline(fields),
            _ => {}
        }
    }

    fn parse_logical_pin(&mut self, fields: &[&str]) {
        let Some(refdes) = self.value_nonempty(fields, "REFDES") else {
            return;
        };
        let Some(pin_number) = self.value_nonempty(fields, "PIN_NUMBER") else {
            return;
        };
        let pin_name = self.value_string(fields, "PIN_NAME");
        if pin_name.is_none() {
            return;
        }
        for pin in self
            .pins
            .iter_mut()
            .filter(|pin| pin.refdes == refdes && pin.pin_number == pin_number)
        {
            pin.pin_name = pin_name.clone();
        }
    }

    fn parse_net(&mut self, fields: &[&str]) {
        if let Some(net) = self.value_nonempty(fields, "NET_NAME") {
            self.seen_nets.insert(net.to_string());
        }
    }

    fn parse_symbol(&mut self, fields: &[&str]) {
        let sym_type = self.value_string(fields, "SYM_TYPE");
        let refdes = self.value_string(fields, "REFDES");
        let bbox = match (
            self.float_value(fields, "SYM_BOX_X1"),
            self.float_value(fields, "SYM_BOX_Y1"),
            self.float_value(fields, "SYM_BOX_X2"),
            self.float_value(fields, "SYM_BOX_Y2"),
        ) {
            (Some(x1), Some(y1), Some(x2), Some(y2)) => Some(Extents { x1, y1, x2, y2 }),
            _ => None,
        };
        self.symbols.push(Symbol {
            sym_type,
            sym_name: self.value_string(fields, "SYM_NAME"),
            refdes,
            bbox,
            center: point_from_values(
                self.float_value(fields, "SYM_CENTER_X"),
                self.float_value(fields, "SYM_CENTER_Y"),
            ),
            mirror: self.value(fields, "SYM_MIRROR").map(is_yes_value),
            rotation: self.float_value(fields, "SYM_ROTATE"),
            location: point_from_values(
                self.float_value(fields, "SYM_X"),
                self.float_value(fields, "SYM_Y"),
            ),
            library_path: self.value_string(fields, "SYM_LIBRARY_PATH"),
        });
    }

    fn parse_track(&mut self, fields: &[&str]) {
        let Some(graphic) = self.value_nonempty(fields, "GRAPHIC_DATA_NAME") else {
            return;
        };
        let layer = self.value_string(fields, "SUBCLASS");
        let layer_known = layer
            .as_deref()
            .map(|name| self.is_metal_layer(name) || name.eq_ignore_ascii_case("WIRE"))
            .unwrap_or(false);
        if !layer_known {
            return;
        }
        let net = self.value_string(fields, "NET_NAME");
        let geometry_role = self.value_string(fields, "GRAPHIC_DATA_10");
        match graphic {
            "LINE" => {
                self.tracks.push(Track {
                    kind: "line".to_string(),
                    layer_name: layer,
                    net_name: net,
                    refdes: self.value_string(fields, "REFDES"),
                    record_tag: self.value_string(fields, "RECORD_TAG"),
                    geometry_role,
                    width: self.float_value(fields, "GRAPHIC_DATA_5"),
                    start: point_from_values(
                        self.float_value(fields, "GRAPHIC_DATA_1"),
                        self.float_value(fields, "GRAPHIC_DATA_2"),
                    ),
                    end: point_from_values(
                        self.float_value(fields, "GRAPHIC_DATA_3"),
                        self.float_value(fields, "GRAPHIC_DATA_4"),
                    ),
                    center: None,
                    clockwise: None,
                    bbox: None,
                });
            }
            "ARC" => {
                self.tracks.push(Track {
                    kind: "arc".to_string(),
                    layer_name: layer,
                    net_name: net,
                    refdes: self.value_string(fields, "REFDES"),
                    record_tag: self.value_string(fields, "RECORD_TAG"),
                    geometry_role,
                    width: self.float_value(fields, "GRAPHIC_DATA_8"),
                    start: point_from_values(
                        self.float_value(fields, "GRAPHIC_DATA_1"),
                        self.float_value(fields, "GRAPHIC_DATA_2"),
                    ),
                    end: point_from_values(
                        self.float_value(fields, "GRAPHIC_DATA_3"),
                        self.float_value(fields, "GRAPHIC_DATA_4"),
                    ),
                    center: point_from_values(
                        self.float_value(fields, "GRAPHIC_DATA_5"),
                        self.float_value(fields, "GRAPHIC_DATA_6"),
                    ),
                    clockwise: self
                        .value(fields, "GRAPHIC_DATA_9")
                        .map(|value| value.eq_ignore_ascii_case("CLOCKWISE")),
                    bbox: None,
                });
            }
            "RECTANGLE" => {
                self.tracks.push(Track {
                    kind: "rectangle".to_string(),
                    layer_name: layer,
                    net_name: net,
                    refdes: self.value_string(fields, "REFDES"),
                    record_tag: self.value_string(fields, "RECORD_TAG"),
                    geometry_role,
                    width: None,
                    start: None,
                    end: None,
                    center: None,
                    clockwise: None,
                    bbox: extents_from_values(
                        self.float_value(fields, "GRAPHIC_DATA_1"),
                        self.float_value(fields, "GRAPHIC_DATA_2"),
                        self.float_value(fields, "GRAPHIC_DATA_3"),
                        self.float_value(fields, "GRAPHIC_DATA_4"),
                    ),
                });
            }
            _ => {}
        }
    }

    fn parse_pad(&mut self, fields: &[&str]) {
        let layer = self.value_string(fields, "SUBCLASS");
        if !layer
            .as_deref()
            .map(|name| self.is_metal_layer(name))
            .unwrap_or(false)
        {
            return;
        }
        if self
            .value(fields, "PAD_TYPE")
            .is_some_and(|value| !value.eq_ignore_ascii_case("REGULAR"))
        {
            return;
        }
        let x = self
            .float_value(fields, "PIN_X")
            .or_else(|| self.float_value(fields, "GRAPHIC_DATA_1"));
        let y = self
            .float_value(fields, "PIN_Y")
            .or_else(|| self.float_value(fields, "GRAPHIC_DATA_2"));
        let key = format!(
            "{}|{}|{}|{}|{}|{}|{}|{}",
            self.value(fields, "REFDES").unwrap_or(""),
            self.value(fields, "PIN_NUMBER").unwrap_or(""),
            layer.as_deref().unwrap_or(""),
            x.map(float_key).unwrap_or_default(),
            y.map(float_key).unwrap_or_default(),
            self.value(fields, "GRAPHIC_DATA_NAME").unwrap_or(""),
            self.value(fields, "GRAPHIC_DATA_3").unwrap_or(""),
            self.value(fields, "GRAPHIC_DATA_4").unwrap_or("")
        );
        if !self.seen_pads.insert(key) {
            return;
        }
        self.pads.push(Pad {
            refdes: self.value_string(fields, "REFDES"),
            pin_number: self.value_string(fields, "PIN_NUMBER"),
            layer_name: layer,
            pad_stack_name: self.value_string(fields, "PAD_STACK_NAME"),
            net_name: self.value_string(fields, "NET_NAME"),
            x,
            y,
            pad_type: self.value_string(fields, "PAD_TYPE"),
            shape: self.shape_from_fields(fields),
            source_section: "full_geometry".to_string(),
            record_tag: self.value_string(fields, "RECORD_TAG"),
        });
    }

    fn parse_via(&mut self, fields: &[&str]) {
        let layer = self.value_nonempty(fields, "SUBCLASS");
        if !layer.map(|name| self.is_metal_layer(name)).unwrap_or(false) {
            return;
        }
        if self
            .value(fields, "PAD_TYPE")
            .is_some_and(|value| !value.eq_ignore_ascii_case("REGULAR"))
        {
            return;
        }
        let Some(x) = self.float_value(fields, "VIA_X") else {
            return;
        };
        let Some(y) = self.float_value(fields, "VIA_Y") else {
            return;
        };
        let pad_stack_name = self.value_string(fields, "PAD_STACK_NAME");
        let net_name = self.value_string(fields, "NET_NAME");
        let layer_name = self.value_string(fields, "SUBCLASS");
        let new_shape = self.shape_from_fields(fields);
        let update_shape = new_shape.clone();
        let key = format!(
            "{}|{}|{}|{}",
            float_key(x),
            float_key(y),
            pad_stack_name.as_deref().unwrap_or(""),
            net_name.as_deref().unwrap_or("")
        );
        let via = self.vias.entry(key.clone()).or_insert_with(|| Via {
            key,
            x,
            y,
            pad_stack_name,
            net_name,
            layer_names: Vec::new(),
            shape: new_shape,
        });
        if via.shape.is_none() {
            via.shape = update_shape;
        }
        if let Some(layer_name) = layer_name {
            if !via
                .layer_names
                .iter()
                .any(|existing| existing.eq_ignore_ascii_case(&layer_name))
            {
                via.layer_names.push(layer_name);
            }
        }
    }

    fn parse_outline(&mut self, fields: &[&str]) {
        let subclass = self.value(fields, "SUBCLASS").unwrap_or("");
        if !matches!(subclass, "OUTLINE" | "DESIGN_OUTLINE") {
            return;
        }
        let Some(graphic) = self.value_nonempty(fields, "GRAPHIC_DATA_NAME") else {
            return;
        };
        let mut outline = Graphic {
            class_name: self.value_string(fields, "CLASS"),
            subclass: self.value_string(fields, "SUBCLASS"),
            record_tag: self.value_string(fields, "RECORD_TAG"),
            kind: graphic.to_ascii_lowercase(),
            ..Graphic::default()
        };
        match graphic {
            "LINE" => {
                outline.start = point_from_values(
                    self.float_value(fields, "GRAPHIC_DATA_1"),
                    self.float_value(fields, "GRAPHIC_DATA_2"),
                );
                outline.end = point_from_values(
                    self.float_value(fields, "GRAPHIC_DATA_3"),
                    self.float_value(fields, "GRAPHIC_DATA_4"),
                );
            }
            "ARC" => {
                outline.start = point_from_values(
                    self.float_value(fields, "GRAPHIC_DATA_1"),
                    self.float_value(fields, "GRAPHIC_DATA_2"),
                );
                outline.end = point_from_values(
                    self.float_value(fields, "GRAPHIC_DATA_3"),
                    self.float_value(fields, "GRAPHIC_DATA_4"),
                );
                outline.center = point_from_values(
                    self.float_value(fields, "GRAPHIC_DATA_5"),
                    self.float_value(fields, "GRAPHIC_DATA_6"),
                );
                outline.clockwise = self
                    .value(fields, "GRAPHIC_DATA_9")
                    .map(|value| value.eq_ignore_ascii_case("CLOCKWISE"));
            }
            "RECTANGLE" => {
                outline.bbox = extents_from_values(
                    self.float_value(fields, "GRAPHIC_DATA_1"),
                    self.float_value(fields, "GRAPHIC_DATA_2"),
                    self.float_value(fields, "GRAPHIC_DATA_3"),
                    self.float_value(fields, "GRAPHIC_DATA_4"),
                );
            }
            _ => {}
        }
        self.outlines.push(outline);
    }

    fn shape_from_fields(&self, fields: &[&str]) -> Option<Shape> {
        let kind = self.value_nonempty(fields, "GRAPHIC_DATA_NAME")?;
        Some(Shape {
            kind: kind.to_string(),
            x: self.float_value(fields, "GRAPHIC_DATA_1"),
            y: self.float_value(fields, "GRAPHIC_DATA_2"),
            width: self.float_value(fields, "GRAPHIC_DATA_3"),
            height: self.float_value(fields, "GRAPHIC_DATA_4"),
            rotation: self.float_value(fields, "GRAPHIC_DATA_5"),
        })
    }

    fn value<'a>(&self, fields: &'a [&'a str], name: &str) -> Option<&'a str> {
        self.current_fields
            .get(name)
            .and_then(|index| fields.get(*index).copied())
            .map(str::trim)
    }

    fn value_nonempty<'a>(&self, fields: &'a [&'a str], name: &str) -> Option<&'a str> {
        self.value(fields, name).filter(|value| !value.is_empty())
    }

    fn value_string(&self, fields: &[&str], name: &str) -> Option<String> {
        self.value_nonempty(fields, name).map(ToOwned::to_owned)
    }

    fn float_value(&self, fields: &[&str], name: &str) -> Option<f64> {
        parse_float(self.value(fields, name)?)
    }

    fn is_metal_layer(&self, layer_name: &str) -> bool {
        self.metal_layers.contains(&fold_key(layer_name))
    }

    fn finish(mut self) -> ParsedAlg {
        self.summary.layer_count = self.layers.len();
        self.summary.metal_layer_count = self.metal_layers.len();
        self.summary.component_count = self.components.len();
        self.summary.pin_count = self.pins.len();
        self.summary.padstack_count = self.padstacks.len();
        self.summary.pad_count = self.pads.len();
        self.summary.via_count = self.vias.len();
        self.summary.track_count = self.tracks.len();
        self.summary.net_count = self.seen_nets.len();
        self.summary.symbol_count = self.symbols.len();
        self.summary.outline_count = self.outlines.len();
        if self.summary.units.is_empty() {
            self.summary.units = "unknown".to_string();
        }
        if self.summary.section_count < 12 {
            self.diagnostics.push(format!(
                "ALG file has {} A! sections; a complete extracta export usually has at least 12 sections",
                self.summary.section_count
            ));
        }
        self.summary.diagnostic_count = self.diagnostics.len();

        let include_details = self.include_details;
        ParsedAlg {
            summary: self.summary,
            board: self.board,
            layers: maybe_vec(include_details, self.layers),
            components: maybe_vec(include_details, self.components),
            pins: maybe_vec(include_details, self.pins),
            padstacks: maybe_vec(include_details, self.padstacks.into_values().collect()),
            pads: maybe_vec(include_details, self.pads),
            vias: maybe_vec(include_details, self.vias.into_values().collect()),
            tracks: maybe_vec(include_details, self.tracks),
            symbols: maybe_vec(include_details, self.symbols),
            outlines: maybe_vec(include_details, self.outlines),
            section_counts: self.section_counts,
            diagnostics: self.diagnostics,
            alg_revision: self.alg_revision,
            extracta_version: self.extracta_version,
        }
    }
}

fn detect_section(fields: &BTreeMap<String, usize>, section_index: usize) -> Section {
    let has = |name: &str| fields.contains_key(name);
    if has("BOARD_NAME") && has("BOARD_UNITS") {
        return Section::Board;
    }
    if has("LAYER_SUBCLASS") && has("LAYER_CONDUCTOR") {
        return Section::Layer;
    }
    if has("REFDES") && has("COMP_PACKAGE") && has("COMP_DEVICE_TYPE") {
        return Section::Component;
    }
    if has("NODE_SORT") && has("NODE_CONNECTS") {
        return Section::Connectivity;
    }
    if has("PAD_STACK_INNER_LAYER") && has("DRILL_HOLE_NAME") {
        return Section::CompositePad;
    }
    if has("PIN_EDITED") && has("PIN_FLOATING_PIN") {
        return Section::ComponentPin;
    }
    if has("CLASS") && has("SUBCLASS") && has("GRAPHIC_DATA_NAME") && has("SYM_NAME") {
        return Section::FullGeometry;
    }
    if has("FUNC_DES") && has("FUNC_TYPE") {
        return Section::Function;
    }
    if has("PIN_NAME") && has("FUNC_DES") {
        return Section::LogicalPin;
    }
    if has("NET_STATUS") && has("NET_VOLTAGE") {
        return Section::Net;
    }
    if has("NET_RAT_SCHEDULE") {
        return Section::Rat;
    }
    if has("SYM_TYPE") && has("SYM_BOX_X1") {
        return Section::Symbol;
    }
    match section_index {
        13 => Section::Zone,
        14 => Section::Bend,
        _ => Section::Unknown,
    }
}

fn parse_float(value: &str) -> Option<f64> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return None;
    }
    let number = trimmed.split_whitespace().next().unwrap_or(trimmed);
    number.parse::<f64>().ok()
}

fn is_yes(value: Option<&str>) -> bool {
    value.map(is_yes_value).unwrap_or(false)
}

fn is_yes_value(value: &str) -> bool {
    matches!(fold_key(value.trim()).as_str(), "yes" | "true" | "y" | "1")
}

fn point_from_values(x: Option<f64>, y: Option<f64>) -> Option<Point> {
    match (x, y) {
        (Some(x), Some(y)) => Some(Point { x, y }),
        _ => None,
    }
}

fn extents_from_values(
    x1: Option<f64>,
    y1: Option<f64>,
    x2: Option<f64>,
    y2: Option<f64>,
) -> Option<Extents> {
    match (x1, y1, x2, y2) {
        (Some(x1), Some(y1), Some(x2), Some(y2)) => Some(Extents { x1, y1, x2, y2 }),
        _ => None,
    }
}

fn maybe_vec<T>(include_details: bool, values: Vec<T>) -> Option<Vec<T>> {
    if include_details {
        Some(values)
    } else {
        None
    }
}

fn float_key(value: f64) -> String {
    format!("{value:.6}")
}

fn fold_key(value: &str) -> String {
    value.to_ascii_lowercase()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn parses_minimal_alg_sections() {
        let dir = std::env::temp_dir();
        let path = dir.join(format!("alg_parser_test_{}.alg", std::process::id()));
        fs::write(
            &path,
            "# ALG for Aurora: rev.1.0.b\n\
             # extracta version: 23.1-P001\n\
             A!BOARD_NAME!BOARD_ACCURACY!BOARD_UNITS!BOARD_EXTENTS_X1!BOARD_EXTENTS_Y1!BOARD_EXTENTS_X2!BOARD_EXTENTS_Y2!BOARD_LAYERS!BOARD_THICKNESS!\n\
             S!sample.brd!0.01!mils!0!0!100!50!2!4 mil!\n\
             A!LAYER_SORT!LAYER_SUBCLASS!LAYER_CONDUCTOR!LAYER_THICKNESS!LAYER_TYPE!\n\
             S!000001!TOP!YES!1 mil!CONDUCTOR!\n\
             S!000002!BOTTOM!YES!1 mil!CONDUCTOR!\n\
             A!REFDES!COMP_CLASS!COMP_PACKAGE!COMP_DEVICE_TYPE!COMP_VALUE!COMP_PART_NUMBER!COMP_ROOM!COMP_BOM_IGNORE!\n\
             S!U1!IC!BGA!PART!VAL!PN!!!\n\
             A!REFDES!PIN_NUMBER!PIN_X!PIN_Y!PIN_TYPE!PAD_STACK_NAME!NET_NAME!PIN_EDITED!PIN_FLOATING_PIN!\n\
             S!U1!1!10!20!IN!C010!GND!NO!NO!\n\
             A!CLASS!SUBCLASS!RECORD_TAG!GRAPHIC_DATA_NAME!GRAPHIC_DATA_1!GRAPHIC_DATA_2!GRAPHIC_DATA_3!GRAPHIC_DATA_4!GRAPHIC_DATA_5!GRAPHIC_DATA_8!GRAPHIC_DATA_9!GRAPHIC_DATA_10!REFDES!PIN_NUMBER!PAD_STACK_NAME!PAD_TYPE!NET_NAME!PIN_X!PIN_Y!VIA_X!VIA_Y!SYM_NAME!\n\
             S!ETCH!TOP!1 1!LINE!0!0!10!10!4!!!!!!!!GND!!!!!\n\
             S!PIN!TOP!2 1!CIRCLE!10!20!8!8!!!!!U1!1!C010!REGULAR!GND!10!20!!!\n\
             S!VIA CLASS!TOP!3 1!CIRCLE!30!40!16!16!!!!!!!VIA8D16!REGULAR!GND!!!30!40!\n\
             A!NET_NAME!NET_STATUS!NET_VOLTAGE!\n\
             S!GND!REGULAR!!\n",
        )
        .unwrap();
        let parsed = parse_alg_file(
            &path,
            &ParseOptions {
                include_details: true,
            },
        )
        .unwrap();
        fs::remove_file(&path).ok();
        assert_eq!(parsed.summary.units, "mils");
        assert_eq!(parsed.summary.metal_layer_count, 2);
        assert_eq!(parsed.summary.component_count, 1);
        assert_eq!(parsed.summary.pin_count, 1);
        assert_eq!(parsed.summary.pad_count, 1);
        assert_eq!(parsed.summary.via_count, 1);
        assert_eq!(parsed.summary.track_count, 1);
        assert_eq!(parsed.summary.net_count, 1);
    }
}
