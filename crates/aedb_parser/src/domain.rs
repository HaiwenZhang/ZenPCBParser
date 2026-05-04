use crate::model::{
    BinaryGeometrySummary, BinaryStringSummary, ComponentDefinition, ComponentPinDefinition,
    ComponentPlacement, DefDomain, DefDomainSummary, MaterialDefinition, PadstackDefinition,
    PadstackLayerPad, StackupLayer, SymbolBox,
};
use crate::parser::{parse_begin, parse_end, unquote, DefRecord, ParsedDef};
use std::collections::HashSet;

pub fn extract_domain(parsed: &ParsedDef) -> DefDomain {
    let mut extractor = DomainExtractor::default();
    for (record_index, record) in parsed.records.iter().enumerate() {
        if let DefRecord::Text(text) = record {
            extractor.ingest_text(record_index, &text.text);
        }
    }
    let binary_strings = binary_string_summary(&scan_length_prefixed_binary_strings(parsed));
    let binary_geometry = binary_geometry_summary(parsed);
    extractor.finish(binary_strings, binary_geometry)
}

pub(crate) fn scan_length_prefixed_binary_strings(parsed: &ParsedDef) -> Vec<String> {
    let mut strings = Vec::new();
    for record in &parsed.records {
        let DefRecord::Binary(binary) = record else {
            continue;
        };
        let bytes = &binary.bytes;
        let mut offset = 0;
        while offset + 8 <= bytes.len() {
            let tag = u32::from_le_bytes([
                bytes[offset],
                bytes[offset + 1],
                bytes[offset + 2],
                bytes[offset + 3],
            ]);
            let length = u32::from_le_bytes([
                bytes[offset + 4],
                bytes[offset + 5],
                bytes[offset + 6],
                bytes[offset + 7],
            ]) as usize;
            if tag == 4 && (1..=512).contains(&length) && offset + 8 + length <= bytes.len() {
                let raw = &bytes[offset + 8..offset + 8 + length];
                if raw.iter().all(|byte| (0x20..0x7f).contains(byte)) {
                    strings.push(String::from_utf8_lossy(raw).into_owned());
                    offset += 8 + length;
                    continue;
                }
            }
            offset += 1;
        }
    }
    strings
}

#[derive(Default)]
struct DomainExtractor {
    materials: Vec<MaterialDefinition>,
    material_names: HashSet<String>,
    stackup_layers: Vec<StackupLayer>,
    stackup_keys: HashSet<String>,
    board_metal_layers: Vec<StackupLayer>,
    board_metal_layer_names: HashSet<String>,
    padstacks: Vec<PadstackDefinition>,
    current_padstack: Option<PadstackDefinition>,
    current_layer_pad: Option<PadstackLayerPad>,
    components: Vec<ComponentDefinition>,
    current_component: Option<ComponentDefinition>,
    current_pin: Option<ComponentPinDefinition>,
    component_names: HashSet<String>,
    component_placements: Vec<ComponentPlacement>,
    current_placement: Option<ComponentPlacement>,
    placement_names: HashSet<String>,
}

impl DomainExtractor {
    fn ingest_text(&mut self, record_index: usize, text: &str) {
        let mut stack: Vec<String> = Vec::new();
        for raw_line in text.lines() {
            let trimmed = raw_line.trim();
            if trimmed.is_empty() {
                continue;
            }

            if let Some(name) = parse_begin(trimmed) {
                self.handle_begin(record_index, &stack, &name);
                stack.push(name);
                continue;
            }

            if let Some(name) = parse_end(trimmed) {
                self.handle_end(&stack, &name);
                stack.pop();
                continue;
            }

            self.handle_line(record_index, &stack, trimmed);
        }
    }

    fn handle_begin(&mut self, record_index: usize, stack: &[String], name: &str) {
        if stack == ["EDB", "Materials"] && self.material_names.insert(name.to_string()) {
            self.materials.push(MaterialDefinition {
                name: name.to_string(),
                record_index,
            });
        }

        if stack == ["EDB", "pds"] && name == "pd" {
            self.current_padstack = Some(PadstackDefinition {
                id: None,
                name: None,
                layer_pads: Vec::new(),
                record_index,
            });
        } else if name == "lgm" && self.current_padstack.is_some() {
            self.current_layer_pad = Some(PadstackLayerPad {
                layer_name: None,
                id: None,
                pad_shape: None,
                antipad_shape: None,
                thermal_shape: None,
            });
        }

        if stack == ["EDB", "Components"] {
            self.current_component = Some(ComponentDefinition {
                name: name.to_string(),
                uid: None,
                footprint: None,
                cell_name: None,
                pins: Vec::new(),
                record_index,
            });
        } else if name == "Pin" && self.current_component.is_some() {
            self.current_pin = Some(ComponentPinDefinition {
                name: None,
                number: None,
                id: None,
            });
        }

        if stack.is_empty() && is_component_placement_block(name) {
            self.current_placement = Some(ComponentPlacement {
                refdes: name.to_string(),
                component_class: None,
                device_type: None,
                value: None,
                package: None,
                part_number: None,
                symbol_box: None,
                part_name_candidates: Vec::new(),
                record_index,
            });
        }
    }

    fn handle_end(&mut self, stack: &[String], name: &str) {
        if name == "lgm" {
            if let (Some(padstack), Some(layer_pad)) = (
                self.current_padstack.as_mut(),
                self.current_layer_pad.take(),
            ) {
                padstack.layer_pads.push(layer_pad);
            }
        } else if stack == ["EDB", "pds", "pd"] && name == "pd" {
            if let Some(padstack) = self.current_padstack.take() {
                self.padstacks.push(padstack);
            }
        } else if name == "Pin" {
            if let (Some(component), Some(pin)) =
                (self.current_component.as_mut(), self.current_pin.take())
            {
                component.pins.push(pin);
            }
        } else if stack.len() == 3
            && stack[0] == "EDB"
            && stack[1] == "Components"
            && stack[2] == name
        {
            if let Some(component) = self.current_component.take() {
                if self.component_names.insert(component.name.clone()) {
                    self.components.push(component);
                }
            }
        } else if stack.len() == 1 && stack[0] == name && is_component_placement_block(name) {
            if let Some(mut placement) = self.current_placement.take() {
                placement.part_name_candidates = part_name_candidates(&placement);
                if self.placement_names.insert(placement.refdes.clone()) {
                    self.component_placements.push(placement);
                }
            }
        }
    }

    fn handle_line(&mut self, record_index: usize, stack: &[String], line: &str) {
        if line.starts_with("SLayer(") {
            self.register_stackup_layer(record_index, line);
        }
        self.register_padstack_line(stack, line);
        self.register_component_line(stack, line);
        self.register_component_placement_line(stack, line);
    }

    fn register_stackup_layer(&mut self, record_index: usize, line: &str) {
        let Some(name) = extract_named_value(line, "N") else {
            return;
        };
        let layer = StackupLayer {
            name,
            id: extract_named_value(line, "ID").and_then(|value| parse_i64(&value)),
            layer_type: extract_named_value(line, "T"),
            top_bottom: extract_named_value(line, "TB"),
            thickness: extract_named_value(line, "Th"),
            lower_elevation: extract_named_value(line, "LElev"),
            material: extract_named_value(line, "Mat"),
            fill_material: extract_named_value(line, "FilMat"),
            record_index,
        };
        let key = stackup_key(&layer);
        if self.stackup_keys.insert(key) {
            if is_board_metal_layer(&layer)
                && self
                    .board_metal_layer_names
                    .insert(layer.name.to_ascii_lowercase())
            {
                self.board_metal_layers.push(layer.clone());
            }
            self.stackup_layers.push(layer);
        }
    }

    fn register_padstack_line(&mut self, stack: &[String], line: &str) {
        let Some(padstack) = self.current_padstack.as_mut() else {
            return;
        };
        if stack.ends_with(&["pd".to_string()]) && line.starts_with("id=") {
            padstack.id = parse_assignment_i64(line);
            return;
        }
        if line.starts_with("nam=") {
            padstack.name = parse_assignment_string(line);
            return;
        }
        let Some(layer_pad) = self.current_layer_pad.as_mut() else {
            return;
        };
        if line.starts_with("lay=") {
            layer_pad.layer_name = parse_assignment_string(line);
        } else if line.starts_with("id=") {
            layer_pad.id = parse_assignment_i64(line);
        } else if line.starts_with("pad(") {
            layer_pad.pad_shape = extract_named_value(line, "shp");
        } else if line.starts_with("ant(") {
            layer_pad.antipad_shape = extract_named_value(line, "shp");
        } else if line.starts_with("thm(") {
            layer_pad.thermal_shape = extract_named_value(line, "shp");
        }
    }

    fn register_component_line(&mut self, stack: &[String], line: &str) {
        let Some(component) = self.current_component.as_mut() else {
            return;
        };
        if self.current_pin.is_none() && stack.len() == 3 && stack[0] == "EDB" {
            if line.starts_with("UID=") {
                component.uid = parse_assignment_i64(line);
            } else if line.starts_with("Footprint=") {
                component.footprint = parse_assignment_string(line);
            } else if line.starts_with("CellName=") {
                component.cell_name = parse_assignment_string(line);
            }
            return;
        }
        let Some(pin) = self.current_pin.as_mut() else {
            return;
        };
        if line.starts_with("name=") {
            pin.name = parse_assignment_string(line);
        } else if line.starts_with("number=") {
            pin.number = parse_assignment_i64(line);
        } else if line.starts_with("id=") {
            pin.id = parse_assignment_i64(line);
        }
    }

    fn register_component_placement_line(&mut self, stack: &[String], line: &str) {
        let Some(placement) = self.current_placement.as_mut() else {
            return;
        };
        if stack.len() != 1 || stack[0] != placement.refdes {
            return;
        }
        if line.starts_with("COMP_CLASS=") {
            placement.component_class = parse_assignment_string(line);
        } else if line.starts_with("COMP_DEVICE_TYPE=") {
            placement.device_type = parse_assignment_string(line);
        } else if line.starts_with("COMP_VALUE=") {
            placement.value = parse_assignment_string(line);
        } else if line.starts_with("COMP_PACKAGE=") {
            placement.package = parse_assignment_string(line);
        } else if line.starts_with("COMP_PART_NUMBER=") {
            placement.part_number = parse_assignment_string(line);
        } else if line.starts_with("SYM_BOX(") {
            placement.symbol_box = parse_symbol_box(line);
        }
    }

    fn finish(
        mut self,
        binary_strings: BinaryStringSummary,
        binary_geometry: BinaryGeometrySummary,
    ) -> DefDomain {
        if let Some(padstack) = self.current_padstack.take() {
            self.padstacks.push(padstack);
        }
        if let Some(component) = self.current_component.take() {
            if self.component_names.insert(component.name.clone()) {
                self.components.push(component);
            }
        }
        if let Some(mut placement) = self.current_placement.take() {
            placement.part_name_candidates = part_name_candidates(&placement);
            if self.placement_names.insert(placement.refdes.clone()) {
                self.component_placements.push(placement);
            }
        }
        let component_part_candidates: HashSet<String> = self
            .component_placements
            .iter()
            .flat_map(|placement| placement.part_name_candidates.iter().cloned())
            .collect();
        let summary = DefDomainSummary {
            material_count: self.materials.len(),
            stackup_layer_count: self.stackup_layers.len(),
            board_metal_layer_count: self.board_metal_layers.len(),
            dielectric_layer_count: self
                .stackup_layers
                .iter()
                .filter(|layer| layer.layer_type.as_deref() == Some("dielectric"))
                .count(),
            padstack_count: self.padstacks.len(),
            padstack_layer_pad_count: self
                .padstacks
                .iter()
                .map(|padstack| padstack.layer_pads.len())
                .sum(),
            multilayer_padstack_count: self
                .padstacks
                .iter()
                .filter(|padstack| padstack_unique_layer_count(padstack) > 1)
                .count(),
            component_definition_count: self.components.len(),
            component_pin_definition_count: self
                .components
                .iter()
                .map(|component| component.pins.len())
                .sum(),
            component_placement_count: self.component_placements.len(),
            component_part_candidate_count: component_part_candidates.len(),
        };
        DefDomain {
            summary,
            materials: self.materials,
            stackup_layers: self.stackup_layers,
            board_metal_layers: self.board_metal_layers,
            padstacks: self.padstacks,
            components: self.components,
            component_placements: self.component_placements,
            binary_strings,
            binary_geometry,
        }
    }
}

fn parse_assignment_string(line: &str) -> Option<String> {
    line.split_once('=')
        .map(|(_, value)| unquote(value).to_string())
}

fn parse_assignment_i64(line: &str) -> Option<i64> {
    parse_assignment_string(line).and_then(|value| parse_i64(&value))
}

fn parse_i64(value: &str) -> Option<i64> {
    value.trim().parse::<i64>().ok()
}

fn parse_symbol_box(line: &str) -> Option<SymbolBox> {
    let value = line
        .strip_prefix("SYM_BOX(")?
        .strip_suffix(')')?
        .split(',')
        .map(str::trim)
        .map(str::parse::<f64>)
        .collect::<Result<Vec<_>, _>>()
        .ok()?;
    if value.len() != 4 {
        return None;
    }
    Some(SymbolBox {
        x_min: value[0],
        y_min: value[1],
        x_max: value[2],
        y_max: value[3],
    })
}

fn is_component_placement_block(name: &str) -> bool {
    !matches!(name, "" | "Hdr" | "EDB" | "PropDisplays" | "RCSComponent")
}

pub(crate) fn part_name_candidates(placement: &ComponentPlacement) -> Vec<String> {
    let mut candidates = Vec::new();
    for value in [
        placement.part_number.as_deref(),
        placement.device_type.as_deref(),
        placement.value.as_deref(),
        placement.package.as_deref(),
    ]
    .into_iter()
    .flatten()
    {
        if value.is_empty() || value == "?" {
            continue;
        }
        push_unique(&mut candidates, value.to_string());
        push_unique(&mut candidates, format!("{}_{}", value, placement.refdes));
        push_unique(&mut candidates, format!("{}__{}", value, placement.refdes));
    }
    candidates
}

fn push_unique(values: &mut Vec<String>, value: String) {
    if !values.contains(&value) {
        values.push(value);
    }
}

fn extract_named_value(line: &str, key: &str) -> Option<String> {
    let bytes = line.as_bytes();
    let key_bytes = key.as_bytes();
    let mut index = 0;
    while index + key_bytes.len() < bytes.len() {
        let Some(relative) = line[index..].find(key) else {
            break;
        };
        let start = index + relative;
        let equals = start + key_bytes.len();
        if equals < bytes.len()
            && bytes[equals] == b'='
            && (start == 0 || !is_identifier_byte(bytes[start - 1]))
        {
            return parse_value_at(line, equals + 1);
        }
        index = start + 1;
    }
    None
}

fn parse_value_at(line: &str, start: usize) -> Option<String> {
    let bytes = line.as_bytes();
    if start >= bytes.len() {
        return None;
    }
    if bytes[start] == b'\'' || bytes[start] == b'"' {
        let quote = bytes[start];
        let mut index = start + 1;
        while index < bytes.len() {
            if bytes[index] == quote && bytes.get(index.wrapping_sub(1)) != Some(&b'\\') {
                return Some(line[start + 1..index].to_string());
            }
            index += 1;
        }
        return None;
    }
    let mut end = start;
    while end < bytes.len() && !matches!(bytes[end], b',' | b')' | b' ' | b'\t') {
        end += 1;
    }
    if end == start {
        None
    } else {
        Some(line[start..end].to_string())
    }
}

fn is_identifier_byte(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || matches!(byte, b'_')
}

fn stackup_key(layer: &StackupLayer) -> String {
    format!(
        "{}|{:?}|{:?}|{:?}|{:?}|{:?}|{:?}",
        layer.name,
        layer.id,
        layer.layer_type,
        layer.thickness,
        layer.lower_elevation,
        layer.material,
        layer.fill_material
    )
}

fn is_board_metal_layer(layer: &StackupLayer) -> bool {
    if layer.layer_type.as_deref() != Some("signal") {
        return false;
    }
    let lowered = layer.name.to_ascii_lowercase();
    !lowered.contains("solderball")
        && !lowered.contains("portlayer")
        && !lowered.contains("extent")
        && !lowered.contains("airbox")
}

fn padstack_unique_layer_count(padstack: &PadstackDefinition) -> usize {
    padstack
        .layer_pads
        .iter()
        .filter_map(|layer| layer.layer_name.as_ref())
        .collect::<HashSet<_>>()
        .len()
}

fn binary_string_summary(strings: &[String]) -> BinaryStringSummary {
    let unique: HashSet<&str> = strings.iter().map(String::as_str).collect();
    let via_count = strings
        .iter()
        .filter(|value| is_via_instance_name(value))
        .count();
    let unique_via_count = unique
        .iter()
        .filter(|value| is_via_instance_name(value))
        .count();
    let line_count = strings
        .iter()
        .filter(|value| is_line_instance_name(value))
        .count();
    let unique_line_count = unique
        .iter()
        .filter(|value| is_line_instance_name(value))
        .count();
    let polygon_count = strings
        .iter()
        .filter(|value| is_polygon_instance_name(value))
        .count();
    let unique_polygon_count = unique
        .iter()
        .filter(|value| is_polygon_instance_name(value))
        .count();
    let void_count = strings
        .iter()
        .filter(|value| is_polygon_void_instance_name(value))
        .count();
    let unique_void_count = unique
        .iter()
        .filter(|value| is_polygon_void_instance_name(value))
        .count();
    BinaryStringSummary {
        string_count: strings.len(),
        unique_string_count: unique.len(),
        via_instance_name_count: via_count,
        unique_via_instance_name_count: unique_via_count,
        line_instance_name_count: line_count,
        unique_line_instance_name_count: unique_line_count,
        polygon_instance_name_count: polygon_count,
        unique_polygon_instance_name_count: unique_polygon_count,
        polygon_void_instance_name_count: void_count,
        unique_polygon_void_instance_name_count: unique_void_count,
        geometry_instance_name_count: via_count + line_count + polygon_count + void_count,
        unique_geometry_instance_name_count: unique_via_count
            + unique_line_count
            + unique_polygon_count
            + unique_void_count,
    }
}

fn binary_geometry_summary(parsed: &ParsedDef) -> BinaryGeometrySummary {
    let mut summary = BinaryGeometrySummary::default();
    let mut named_via_tail_offsets = HashSet::new();
    let mut via_locations = HashSet::new();
    let mut path_widths = HashSet::new();

    for record in &parsed.records {
        let DefRecord::Binary(binary) = record else {
            continue;
        };
        let bytes = &binary.bytes;
        let string_ranges = ascii_string_ranges(bytes);
        let string_payload_mask = string_payload_mask(bytes.len(), &string_ranges);

        let named_vias = scan_named_via_records(bytes, binary.offset);
        summary.named_via_record_count += named_vias.len();
        for via in named_vias {
            named_via_tail_offsets.insert(via.tail_offset);
            via_locations.insert(via.location_key);
        }

        for via in scan_unnamed_via_records(
            bytes,
            binary.offset,
            &named_via_tail_offsets,
            &string_payload_mask,
        ) {
            summary.unnamed_via_record_count += 1;
            via_locations.insert(via.location_key);
        }

        for path in scan_path_records(bytes) {
            summary.path_record_count += 1;
            summary.path_line_segment_count += path.line_segment_count;
            summary.path_arc_segment_count += path.arc_segment_count;
            path_widths.insert(round_microunit(path.width_mil));
            if path.named {
                summary.named_path_record_count += 1;
            }
        }
    }

    summary.via_record_count = summary.named_via_record_count + summary.unnamed_via_record_count;
    summary.unique_via_location_count = via_locations.len();
    summary.unnamed_path_record_count = summary
        .path_record_count
        .saturating_sub(summary.named_path_record_count);
    summary.path_segment_count = summary.path_line_segment_count + summary.path_arc_segment_count;
    summary.path_width_count = path_widths.len();
    summary
}

#[derive(Debug, Clone)]
struct ViaRecordHint {
    tail_offset: usize,
    location_key: (i64, i64),
}

#[derive(Debug, Clone)]
struct PathRecordHint {
    named: bool,
    width_mil: f64,
    line_segment_count: usize,
    arc_segment_count: usize,
}

fn ascii_string_ranges(bytes: &[u8]) -> Vec<(usize, usize)> {
    let mut ranges = Vec::new();
    let mut offset = 0;
    while offset + 8 <= bytes.len() {
        let tag = read_u32_le(bytes, offset);
        let Some(length) = read_u32_le(bytes, offset + 4).map(|value| value as usize) else {
            break;
        };
        if tag == Some(4)
            && (1..=512).contains(&length)
            && offset + 8 + length <= bytes.len()
            && bytes[offset + 8..offset + 8 + length]
                .iter()
                .all(|byte| (0x20..0x7f).contains(byte))
        {
            ranges.push((offset + 8, offset + 8 + length));
            offset += 8 + length;
            continue;
        }
        offset += 1;
    }
    ranges
}

fn scan_named_via_records(bytes: &[u8], base_offset: usize) -> Vec<ViaRecordHint> {
    let mut records = Vec::new();
    for (_raw_start, raw_end, value) in ascii_strings(bytes) {
        if !is_via_instance_name(&value) {
            continue;
        }
        let tail_offset = raw_end + 4;
        if let Some(location_key) = parse_via_tail_location(bytes, tail_offset) {
            records.push(ViaRecordHint {
                tail_offset: base_offset + tail_offset,
                location_key,
            });
        }
    }
    records
}

fn scan_unnamed_via_records(
    bytes: &[u8],
    base_offset: usize,
    named_tail_offsets: &HashSet<usize>,
    string_payload_mask: &[bool],
) -> Vec<ViaRecordHint> {
    let mut records = Vec::new();
    let mut offset = 0;
    while offset + 84 <= bytes.len() {
        let global_offset = base_offset + offset;
        if named_tail_offsets.contains(&global_offset)
            || string_payload_mask.get(offset).copied().unwrap_or(false)
        {
            offset += 1;
            continue;
        }
        if let Some(location_key) = parse_via_tail_location(bytes, offset) {
            records.push(ViaRecordHint {
                tail_offset: global_offset,
                location_key,
            });
            offset += 84;
            continue;
        }
        offset += 1;
    }
    records
}

fn parse_via_tail_location(bytes: &[u8], offset: usize) -> Option<(i64, i64)> {
    if read_u32_le(bytes, offset)? != 4
        || read_u32_le(bytes, offset + 8)? != u32::MAX
        || read_u32_le(bytes, offset + 12)? != 4
    {
        return None;
    }
    let x_mil = read_f64_le(bytes, offset + 20)? * 39_370.078_740_157_48;
    let y_mil = read_f64_le(bytes, offset + 32)? * 39_370.078_740_157_48;
    let diameter_mil = read_f64_le(bytes, offset + 56)? * 39_370.078_740_157_48;
    if !x_mil.is_finite()
        || !y_mil.is_finite()
        || !diameter_mil.is_finite()
        || !(-10_000.0..=10_000.0).contains(&x_mil)
        || !(-10_000.0..=10_000.0).contains(&y_mil)
        || !(1.0..=20.0).contains(&diameter_mil)
        || (x_mil.abs() + y_mil.abs()) <= 1e-9
    {
        return None;
    }
    Some((round_microunit(x_mil), round_microunit(y_mil)))
}

fn scan_path_records(bytes: &[u8]) -> Vec<PathRecordHint> {
    const MARKER: &[u8] = &[
        0x00, 0x00, 0x00, 0x00, 0x33, 0x33, 0x33, 0x33, 0x33, 0x33, 0xe3, 0x3f, 0x00, 0x00, 0x00,
        0x00, 0x24, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00,
    ];
    let mut records = Vec::new();
    let mut search_offset = 0;
    while let Some(relative) = find_bytes(&bytes[search_offset..], MARKER) {
        let marker_offset = search_offset + relative;
        search_offset = marker_offset + 1;
        if marker_offset < 8 {
            continue;
        }
        let width_offset = marker_offset - 8;
        let Some(width_mil) =
            read_f64_le(bytes, width_offset).map(|value| value * 39_370.078_740_157_48)
        else {
            continue;
        };
        let Some(double_count) = read_u32_le(bytes, width_offset + 33).map(|value| value as usize)
        else {
            continue;
        };
        let doubles_offset = width_offset + 41;
        if !(0.0..100.0).contains(&width_mil)
            || double_count == 0
            || double_count > 20_000
            || doubles_offset + double_count * 8 > bytes.len()
        {
            continue;
        }
        let Some((line_segment_count, arc_segment_count)) =
            path_segment_counts(bytes, doubles_offset, double_count)
        else {
            continue;
        };
        records.push(PathRecordHint {
            named: path_has_line_name(bytes, width_offset),
            width_mil,
            line_segment_count,
            arc_segment_count,
        });
    }
    records
}

fn path_segment_counts(
    bytes: &[u8],
    doubles_offset: usize,
    double_count: usize,
) -> Option<(usize, usize)> {
    let mut items = Vec::new();
    let mut index = 0;
    while index + 1 < double_count {
        let first = read_f64_le(bytes, doubles_offset + index * 8)?;
        let second = read_f64_le(bytes, doubles_offset + (index + 1) * 8)?;
        if second.abs() > 1e100 {
            let height_mil = first * 39_370.078_740_157_48;
            if !height_mil.is_finite() || height_mil.abs() > 10_000.0 {
                return None;
            }
            items.push(PathItem::ArcMarker);
        } else {
            let x_mil = first * 39_370.078_740_157_48;
            let y_mil = second * 39_370.078_740_157_48;
            if !x_mil.is_finite()
                || !y_mil.is_finite()
                || !(-10_000.0..=10_000.0).contains(&x_mil)
                || !(-10_000.0..=10_000.0).contains(&y_mil)
            {
                return None;
            }
            items.push(PathItem::Point);
        }
        index += 2;
    }
    if items.len() < 2 {
        return None;
    }
    let mut line_segments = 0;
    let mut arc_segments = 0;
    for index in 1..items.len() {
        match (items[index - 1], items[index]) {
            (_, PathItem::ArcMarker) => {}
            (PathItem::ArcMarker, PathItem::Point) => {
                if index >= 2 && items[index - 2] == PathItem::Point {
                    arc_segments += 1;
                }
            }
            (PathItem::Point, PathItem::Point) => line_segments += 1,
        }
    }
    Some((line_segments, arc_segments))
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum PathItem {
    Point,
    ArcMarker,
}

fn ascii_strings(bytes: &[u8]) -> Vec<(usize, usize, String)> {
    let mut strings = Vec::new();
    let mut offset = 0;
    while offset + 8 <= bytes.len() {
        let tag = read_u32_le(bytes, offset);
        let Some(length) = read_u32_le(bytes, offset + 4).map(|value| value as usize) else {
            break;
        };
        if tag == Some(4) && (1..=512).contains(&length) && offset + 8 + length <= bytes.len() {
            let raw = &bytes[offset + 8..offset + 8 + length];
            if raw.iter().all(|byte| (0x20..0x7f).contains(byte)) {
                strings.push((
                    offset + 8,
                    offset + 8 + length,
                    String::from_utf8_lossy(raw).into_owned(),
                ));
                offset += 8 + length;
                continue;
            }
        }
        offset += 1;
    }
    strings
}

fn path_has_line_name(bytes: &[u8], width_offset: usize) -> bool {
    for length in 1..=64 {
        let Some(raw_start) = width_offset.checked_sub(length + 45) else {
            continue;
        };
        let Some(header_start) = raw_start.checked_sub(8) else {
            continue;
        };
        if read_u32_le(bytes, header_start) == Some(4)
            && read_u32_le(bytes, header_start + 4) == Some(length as u32)
            && raw_start + length <= bytes.len()
        {
            let value = String::from_utf8_lossy(&bytes[raw_start..raw_start + length]);
            if is_line_instance_name(&value) {
                return true;
            }
        }
    }
    false
}

fn string_payload_mask(length: usize, ranges: &[(usize, usize)]) -> Vec<bool> {
    let mut mask = vec![false; length];
    for (start, end) in ranges {
        let end = (*end).min(mask.len());
        for value in mask.iter_mut().take(end).skip(*start) {
            *value = true;
        }
    }
    mask
}

fn find_bytes(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    haystack
        .windows(needle.len())
        .position(|window| window == needle)
}

fn read_u32_le(bytes: &[u8], offset: usize) -> Option<u32> {
    let value = bytes.get(offset..offset + 4)?;
    Some(u32::from_le_bytes(value.try_into().ok()?))
}

fn read_f64_le(bytes: &[u8], offset: usize) -> Option<f64> {
    let value = bytes.get(offset..offset + 8)?;
    Some(f64::from_le_bytes(value.try_into().ok()?))
}

fn round_microunit(value: f64) -> i64 {
    (value * 1_000_000.0).round() as i64
}

pub(crate) fn is_via_instance_name(value: &str) -> bool {
    let Some(rest) = value.strip_prefix("via_") else {
        return false;
    };
    !rest.is_empty() && rest.bytes().all(|byte| byte.is_ascii_digit())
}

pub(crate) fn is_line_instance_name(value: &str) -> bool {
    let Some(rest) = value
        .strip_prefix("line__")
        .or_else(|| value.strip_prefix("line_"))
    else {
        return false;
    };
    !rest.is_empty() && rest.bytes().all(|byte| byte.is_ascii_digit())
}

pub(crate) fn is_polygon_instance_name(value: &str) -> bool {
    let Some(rest) = value.strip_prefix("poly__") else {
        return false;
    };
    !rest.is_empty() && rest.bytes().all(|byte| byte.is_ascii_digit())
}

pub(crate) fn is_polygon_void_instance_name(value: &str) -> bool {
    let Some(rest) = value.strip_prefix("poly void_") else {
        return false;
    };
    !rest.is_empty() && rest.bytes().all(|byte| byte.is_ascii_digit())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parser::{parse_def_file, ParseOptions};
    use std::path::PathBuf;

    fn fixture(name: &str) -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../examples/edb_cases")
            .join(name)
    }

    #[test]
    fn extracts_domain_counts_from_public_cases() {
        let cases = [
            ("fpc.def", 2, 5, 1, 2, 78, 2, 480, 371, 371, 66, 303, 212),
            (
                "kb.def", 4, 43, 8, 27, 154, 57, 686, 582, 537, 287, 1098, 21,
            ),
            (
                "mb.def", 10, 131, 17, 240, 3163, 2207, 22955, 19879, 17352, 13658, 48263, 518,
            ),
        ];
        for (
            name,
            metal_layers,
            padstacks,
            multilayer_padstacks,
            components,
            pins,
            placements,
            geometry_names,
            via_records,
            unique_via_locations,
            path_records,
            path_lines,
            path_arcs,
        ) in cases
        {
            let parsed = parse_def_file(
                &fixture(name),
                &ParseOptions {
                    include_details: false,
                },
            )
            .unwrap();
            let domain = extract_domain(&parsed);
            assert_eq!(
                domain.summary.board_metal_layer_count, metal_layers,
                "{name}"
            );
            assert_eq!(domain.summary.padstack_count, padstacks, "{name}");
            assert_eq!(
                domain.summary.multilayer_padstack_count, multilayer_padstacks,
                "{name}"
            );
            assert_eq!(
                domain.summary.component_definition_count, components,
                "{name}"
            );
            assert_eq!(
                domain.summary.component_pin_definition_count, pins,
                "{name}"
            );
            assert_eq!(
                domain.summary.component_placement_count, placements,
                "{name}"
            );
            assert_eq!(
                domain.binary_strings.geometry_instance_name_count, geometry_names,
                "{name}"
            );
            assert_eq!(
                domain.binary_geometry.via_record_count, via_records,
                "{name}"
            );
            assert_eq!(
                domain.binary_geometry.unique_via_location_count, unique_via_locations,
                "{name}"
            );
            assert_eq!(
                domain.binary_geometry.path_record_count, path_records,
                "{name}"
            );
            assert_eq!(
                domain.binary_geometry.path_line_segment_count, path_lines,
                "{name}"
            );
            assert_eq!(
                domain.binary_geometry.path_arc_segment_count, path_arcs,
                "{name}"
            );
        }
    }
}
