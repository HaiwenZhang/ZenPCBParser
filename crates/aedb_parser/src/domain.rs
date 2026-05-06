use crate::model::{
    BinaryGeometrySummary, BinaryPadstackInstanceRecord, BinaryPathItem, BinaryPathRecord,
    BinaryPolygonRecord, BinaryStringSummary, ComponentDefinition, ComponentPinDefinition,
    ComponentPlacement, DefDomain, DefDomainSummary, LayoutNetDefinition, MaterialDefinition,
    PadstackDefinition, PadstackInstanceDefinitionRecord, PadstackLayerPad, StackupLayer,
    SymbolBox,
};
use crate::parser::{parse_begin, parse_end, unquote, DefRecord, ParsedDef, TextRecord};
use std::collections::{HashMap, HashSet};

pub fn extract_domain(parsed: &ParsedDef) -> DefDomain {
    let mut extractor = DomainExtractor::default();
    for (record_index, record) in parsed.records.iter().enumerate() {
        if let DefRecord::Text(text) = record {
            extractor.ingest_text(
                record_index,
                &text.text,
                text_record_object_id(parsed, record_index, text),
            );
        }
    }
    let binary_strings = binary_string_summary(&scan_length_prefixed_binary_strings(parsed));
    let layout_nets = binary_layout_net_names(parsed);
    let layer_names = extractor.layer_name_by_id();
    let net_names = layout_net_name_by_index(&layout_nets);
    let (
        binary_geometry,
        binary_padstack_instance_records,
        binary_path_records,
        binary_polygon_records,
    ) = binary_geometry_summary(parsed, &layer_names, &net_names);
    extractor.finish(
        layout_nets,
        binary_strings,
        binary_geometry,
        binary_padstack_instance_records,
        binary_path_records,
        binary_polygon_records,
    )
}

fn text_record_object_id(
    parsed: &ParsedDef,
    record_index: usize,
    text: &TextRecord,
) -> Option<i64> {
    let previous = record_index.checked_sub(1)?;
    let DefRecord::Binary(binary) = parsed.records.get(previous)? else {
        return None;
    };
    if binary.bytes.len() != 7 || read_u32_le(&binary.bytes, 0) != Some(6) {
        return None;
    }
    let value = u32::from_le_bytes([binary.bytes[4], binary.bytes[5], binary.bytes[6], text.tag]);
    if (1..=10_000_000).contains(&value) {
        Some(i64::from(value))
    } else {
        None
    }
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
    padstack_instance_definitions: Vec<PadstackInstanceDefinitionRecord>,
    current_padstack: Option<PadstackDefinition>,
    current_layer_pad: Option<PadstackLayerPad>,
    components: Vec<ComponentDefinition>,
    current_component: Option<ComponentDefinition>,
    current_pin: Option<ComponentPinDefinition>,
    component_names: HashSet<String>,
    component_placements: Vec<ComponentPlacement>,
    current_placement: Option<ComponentPlacement>,
    placement_names: HashSet<String>,
    layout_layer_names_by_id: HashMap<i64, String>,
}

impl DomainExtractor {
    fn ingest_text(&mut self, record_index: usize, text: &str, object_id: Option<i64>) {
        if let Some(definition) =
            parse_padstack_instance_definition_text(record_index, object_id, text)
        {
            self.padstack_instance_definitions.push(definition);
        }

        let mut stack: Vec<String> = Vec::new();
        let mut pending_slayer: Option<String> = None;
        for raw_line in text.lines() {
            let trimmed = raw_line.trim();
            if trimmed.is_empty() {
                continue;
            }

            if let Some(statement) = pending_slayer.as_mut() {
                statement.push(' ');
                statement.push_str(trimmed);
                if is_complete_slayer_statement(statement) {
                    let complete = pending_slayer.take().unwrap();
                    self.handle_line(record_index, &stack, &complete);
                }
                continue;
            }

            if trimmed.starts_with("SLayer(") && !is_complete_slayer_statement(trimmed) {
                pending_slayer = Some(trimmed.to_string());
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
        if let Some(statement) = pending_slayer {
            self.handle_line(record_index, &stack, &statement);
        }
    }

    fn handle_begin(&mut self, record_index: usize, stack: &[String], name: &str) {
        if stack == ["EDB", "Materials"] && self.material_names.insert(name.to_string()) {
            self.materials.push(MaterialDefinition {
                name: name.to_string(),
                conductivity: None,
                permittivity: None,
                dielectric_loss_tangent: None,
                record_index,
            });
        }

        if stack == ["EDB", "pds"] && name == "pd" {
            self.current_padstack = Some(PadstackDefinition {
                id: None,
                name: None,
                hole_shape: None,
                hole_parameters: Vec::new(),
                hole_offset_x: None,
                hole_offset_y: None,
                hole_rotation: None,
                layer_pads: Vec::new(),
                record_index,
            });
        } else if name == "lgm" && self.current_padstack.is_some() {
            self.current_layer_pad = Some(PadstackLayerPad {
                layer_name: None,
                id: None,
                pad_shape: None,
                pad_parameters: Vec::new(),
                pad_offset_x: None,
                pad_offset_y: None,
                pad_rotation: None,
                antipad_shape: None,
                antipad_parameters: Vec::new(),
                antipad_offset_x: None,
                antipad_offset_y: None,
                antipad_rotation: None,
                thermal_shape: None,
                thermal_parameters: Vec::new(),
                thermal_offset_x: None,
                thermal_offset_y: None,
                thermal_rotation: None,
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
        } else if line.starts_with("Layer(") {
            self.register_layout_layer_line(line);
        }
        self.register_material_line(stack, line);
        self.register_padstack_line(stack, line);
        self.register_component_line(stack, line);
        self.register_component_placement_line(stack, line);
    }

    fn register_material_line(&mut self, stack: &[String], line: &str) {
        if stack.len() != 3 || stack[0] != "EDB" || stack[1] != "Materials" {
            return;
        }
        let material_name = &stack[2];
        let Some(material) = self
            .materials
            .iter_mut()
            .rev()
            .find(|material| &material.name == material_name)
        else {
            return;
        };
        if line.starts_with("conductivity=") {
            material.conductivity = parse_assignment_string(line);
        } else if line.starts_with("permittivity=") {
            material.permittivity = parse_assignment_string(line);
        } else if line.starts_with("dielectric_loss_tangent=") {
            material.dielectric_loss_tangent = parse_assignment_string(line);
        }
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

    fn register_layout_layer_line(&mut self, line: &str) {
        let (Some(name), Some(id)) = (
            extract_named_value(line, "N"),
            extract_named_value(line, "ID").and_then(|value| parse_i64(&value)),
        ) else {
            return;
        };
        self.layout_layer_names_by_id.insert(id, name);
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
        if line.starts_with("hle(") {
            padstack.hole_shape = extract_named_value(line, "shp");
            padstack.hole_parameters = extract_szs_values(line);
            padstack.hole_offset_x = extract_named_value(line, "X");
            padstack.hole_offset_y = extract_named_value(line, "Y");
            padstack.hole_rotation = extract_named_value(line, "R");
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
            layer_pad.pad_parameters = extract_szs_values(line);
            layer_pad.pad_offset_x = extract_named_value(line, "X");
            layer_pad.pad_offset_y = extract_named_value(line, "Y");
            layer_pad.pad_rotation = extract_named_value(line, "R");
        } else if line.starts_with("ant(") {
            layer_pad.antipad_shape = extract_named_value(line, "shp");
            layer_pad.antipad_parameters = extract_szs_values(line);
            layer_pad.antipad_offset_x = extract_named_value(line, "X");
            layer_pad.antipad_offset_y = extract_named_value(line, "Y");
            layer_pad.antipad_rotation = extract_named_value(line, "R");
        } else if line.starts_with("thm(") {
            layer_pad.thermal_shape = extract_named_value(line, "shp");
            layer_pad.thermal_parameters = extract_szs_values(line);
            layer_pad.thermal_offset_x = extract_named_value(line, "X");
            layer_pad.thermal_offset_y = extract_named_value(line, "Y");
            layer_pad.thermal_rotation = extract_named_value(line, "R");
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
        layout_nets: Vec<LayoutNetDefinition>,
        binary_strings: BinaryStringSummary,
        binary_geometry: BinaryGeometrySummary,
        binary_padstack_instance_records: Vec<BinaryPadstackInstanceRecord>,
        binary_path_records: Vec<BinaryPathRecord>,
        binary_polygon_records: Vec<BinaryPolygonRecord>,
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
        let layer_names = self.layer_name_by_id();
        let padstack_names_by_id: HashMap<i64, String> = self
            .padstacks
            .iter()
            .filter_map(|padstack| Some((padstack.id?, padstack.name.as_ref()?.to_string())))
            .collect();
        for definition in &mut self.padstack_instance_definitions {
            definition.padstack_name = definition
                .padstack_id
                .and_then(|id| padstack_names_by_id.get(&id).cloned());
            definition.first_layer_name = definition
                .first_layer_id
                .and_then(|id| layer_names.get(&id).cloned());
            definition.last_layer_name = definition
                .last_layer_id
                .and_then(|id| layer_names.get(&id).cloned());
            definition.solder_ball_layer_name = definition
                .solder_ball_layer_id
                .and_then(|id| layer_names.get(&id).cloned());
        }
        let component_part_candidates: HashSet<String> = self
            .component_placements
            .iter()
            .flat_map(|placement| placement.part_name_candidates.iter().cloned())
            .collect();
        let summary = DefDomainSummary {
            layout_net_count: layout_nets.len(),
            material_count: self.materials.len(),
            stackup_layer_count: self.stackup_layers.len(),
            board_metal_layer_count: self.board_metal_layers.len(),
            dielectric_layer_count: self
                .stackup_layers
                .iter()
                .filter(|layer| layer.layer_type.as_deref() == Some("dielectric"))
                .count(),
            padstack_count: self.padstacks.len(),
            padstack_instance_definition_count: self.padstack_instance_definitions.len(),
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
            layout_nets,
            materials: self.materials,
            stackup_layers: self.stackup_layers,
            board_metal_layers: self.board_metal_layers,
            padstacks: self.padstacks,
            padstack_instance_definitions: self.padstack_instance_definitions,
            components: self.components,
            component_placements: self.component_placements,
            binary_strings,
            binary_geometry,
            binary_padstack_instance_records,
            binary_path_records,
            binary_polygon_records,
        }
    }

    fn layer_name_by_id(&self) -> HashMap<i64, String> {
        let mut names = self.layout_layer_names_by_id.clone();
        names.extend(
            self.stackup_layers
                .iter()
                .filter_map(|layer| layer.id.map(|id| (id, layer.name.clone()))),
        );
        names
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

fn parse_assignment_bool(line: &str) -> Option<bool> {
    match parse_assignment_string(line)?.as_str() {
        "true" => Some(true),
        "false" => Some(false),
        _ => None,
    }
}

fn parse_padstack_instance_definition_text(
    record_index: usize,
    object_id: Option<i64>,
    text: &str,
) -> Option<PadstackInstanceDefinitionRecord> {
    let raw_definition_index = object_id?;
    let mut saw_empty_block = false;
    let mut padstack_id = None;
    let mut first_layer_id = None;
    let mut last_layer_id = None;
    let mut first_layer_positive = None;
    let mut solder_ball_layer_id = None;

    for raw_line in text.lines() {
        let line = raw_line.trim();
        if line == "$begin ''" {
            saw_empty_block = true;
        } else if line.starts_with("def=") {
            padstack_id = parse_assignment_i64(line);
        } else if line.starts_with("fl=") {
            first_layer_id = parse_assignment_i64(line);
        } else if line.starts_with("tl=") {
            last_layer_id = parse_assignment_i64(line);
        } else if line.starts_with("flp=") {
            first_layer_positive = parse_assignment_bool(line);
        } else if line.starts_with("sbl=") {
            solder_ball_layer_id = parse_assignment_i64(line);
        }
    }
    if !saw_empty_block || padstack_id.is_none() {
        return None;
    }
    Some(PadstackInstanceDefinitionRecord {
        record_index,
        raw_definition_index,
        padstack_id,
        padstack_name: None,
        first_layer_id,
        first_layer_name: None,
        last_layer_id,
        last_layer_name: None,
        first_layer_positive,
        solder_ball_layer_id,
        solder_ball_layer_name: None,
    })
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

fn is_complete_slayer_statement(line: &str) -> bool {
    line.contains("OxideMaterials())")
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

fn extract_szs_values(line: &str) -> Vec<String> {
    let Some(start) = line.find("Szs(") else {
        return Vec::new();
    };
    let tail = &line[start + "Szs(".len()..];
    let Some(end) = tail.find(')') else {
        return Vec::new();
    };
    let inner = &tail[..end];
    let mut values = Vec::new();
    let mut current = String::new();
    let mut in_quote = false;
    for ch in inner.chars() {
        if ch == '\'' {
            if in_quote {
                values.push(current.clone());
                current.clear();
            }
            in_quote = !in_quote;
        } else if in_quote {
            current.push(ch);
        }
    }
    values
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

fn binary_layout_net_names(parsed: &ParsedDef) -> Vec<LayoutNetDefinition> {
    for record in &parsed.records {
        let DefRecord::Binary(binary) = record else {
            continue;
        };
        let bytes = &binary.bytes;
        let Some(max_net_index) = read_u32_le(bytes, 8).map(|value| value as usize) else {
            continue;
        };
        if max_net_index == 0 || max_net_index > 100_000 {
            continue;
        }
        let strings = ascii_strings(bytes);
        if strings.len() <= max_net_index {
            continue;
        }
        let Some((first_header_offset, _, first_name)) = strings.first() else {
            continue;
        };
        if *first_header_offset > 128 || first_name.is_empty() {
            continue;
        }
        return strings
            .into_iter()
            .take(max_net_index + 1)
            .enumerate()
            .map(|(index, (_, _, name))| LayoutNetDefinition { index, name })
            .collect();
    }
    Vec::new()
}

fn layout_net_name_by_index(layout_nets: &[LayoutNetDefinition]) -> HashMap<u64, String> {
    layout_nets
        .iter()
        .map(|net| (net.index as u64, net.name.clone()))
        .collect()
}

fn binary_geometry_summary(
    parsed: &ParsedDef,
    layer_names: &HashMap<i64, String>,
    net_names: &HashMap<u64, String>,
) -> (
    BinaryGeometrySummary,
    Vec<BinaryPadstackInstanceRecord>,
    Vec<BinaryPathRecord>,
    Vec<BinaryPolygonRecord>,
) {
    let mut summary = BinaryGeometrySummary::default();
    let mut padstack_instance_records = Vec::new();
    let mut path_records = Vec::new();
    let mut polygon_records = Vec::new();
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

        for padstack_instance in scan_padstack_instance_records(bytes, binary.offset, net_names) {
            summary.padstack_instance_record_count += 1;
            if padstack_instance.secondary_name.is_some() {
                summary.padstack_instance_secondary_name_count += 1;
            }
            match padstack_instance.name_kind.as_str() {
                "component_pin" => summary.component_pin_padstack_instance_record_count += 1,
                "via" => summary.named_via_padstack_instance_record_count += 1,
                "unnamed" => summary.unnamed_padstack_instance_record_count += 1,
                _ => {}
            }
            padstack_instance_records.push(padstack_instance);
        }

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

        let scanned_paths = scan_path_records(bytes, binary.offset, layer_names, net_names);
        for path in &scanned_paths {
            summary.path_record_count += 1;
            summary.path_line_segment_count += path.line_segment_count;
            summary.path_arc_segment_count += path.arc_segment_count;
            path_widths.insert(round_microunit(path.width * 39_370.078_740_157_48));
            if path.named {
                summary.named_path_record_count += 1;
            }
        }
        path_records.extend(scanned_paths.iter().cloned());

        let mut scanned_polygons =
            scan_polygon_records(bytes, binary.offset, layer_names, net_names);
        scanned_polygons.extend(scan_outline_polygon_records(
            bytes,
            binary.offset,
            layer_names,
        ));
        assign_polygon_net_owners(&mut scanned_polygons, &scanned_paths, net_names);
        for polygon in scanned_polygons {
            summary.polygon_record_count += 1;
            summary.polygon_point_count += polygon.point_count;
            summary.polygon_arc_segment_count += polygon.arc_segment_count;
            if polygon.is_void {
                summary.polygon_void_record_count += 1;
            } else {
                summary.polygon_outer_record_count += 1;
            }
            polygon_records.push(polygon);
        }
    }

    summary.via_record_count = summary.named_via_record_count + summary.unnamed_via_record_count;
    summary.unique_via_location_count = via_locations.len();
    summary.unnamed_path_record_count = summary
        .path_record_count
        .saturating_sub(summary.named_path_record_count);
    summary.path_segment_count = summary.path_line_segment_count + summary.path_arc_segment_count;
    summary.path_width_count = path_widths.len();
    (
        summary,
        padstack_instance_records,
        path_records,
        polygon_records,
    )
}

#[derive(Debug, Clone)]
struct ViaRecordHint {
    tail_offset: usize,
    location_key: (i64, i64),
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

fn scan_padstack_instance_records(
    bytes: &[u8],
    base_offset: usize,
    net_names: &HashMap<u64, String>,
) -> Vec<BinaryPadstackInstanceRecord> {
    let mut records = Vec::new();
    for (raw_start, raw_end, name) in ascii_strings(bytes) {
        let Some(preamble_offset) = raw_start.checked_sub(60) else {
            continue;
        };
        let name_len = raw_end.saturating_sub(raw_start);
        if !is_padstack_instance_preamble(bytes, preamble_offset, name_len) {
            continue;
        }
        let post_offset = raw_end + 4;
        if read_u32_le(bytes, post_offset) != Some(4)
            || read_u32_le(bytes, post_offset + 12) != Some(4)
        {
            continue;
        }
        let Some(x) = read_f64_le(bytes, post_offset + 20) else {
            continue;
        };
        let Some(y) = read_f64_le(bytes, post_offset + 32) else {
            continue;
        };
        let Some(rotation) = read_f64_le(bytes, post_offset + 44) else {
            continue;
        };
        let drill_diameter = parse_padstack_instance_drill_diameter(bytes, post_offset + 56);
        if !is_valid_layout_coordinate(x, y)
            || !rotation.is_finite()
            || rotation.abs() > 10.0 * std::f64::consts::PI
        {
            continue;
        }
        let net_raw = read_i32_le(bytes, post_offset + 4);
        let net_index = net_raw.and_then(|value| u64::try_from(value).ok());
        let (secondary_name, secondary_id) = parse_secondary_name(bytes, post_offset + 68);
        records.push(BinaryPadstackInstanceRecord {
            offset: base_offset + preamble_offset,
            geometry_id: read_u32_le(bytes, preamble_offset + 20)
                .map(u64::from)
                .unwrap_or_default(),
            name_kind: padstack_instance_name_kind(&name).to_string(),
            name,
            net_index,
            net_name: net_index.and_then(|index| net_names.get(&index).cloned()),
            raw_owner_index: read_i32_le(bytes, post_offset + 8).map(i64::from),
            raw_definition_index: read_i32_le(bytes, post_offset + 16).map(i64::from),
            x,
            y,
            rotation,
            drill_diameter,
            secondary_name,
            secondary_id,
        });
    }
    records
}

fn parse_padstack_instance_drill_diameter(bytes: &[u8], offset: usize) -> Option<f64> {
    let diameter = read_f64_le(bytes, offset)?;
    let diameter_mil = diameter * 39_370.078_740_157_48;
    if diameter_mil.is_finite() && (0.1..=500.0).contains(&diameter_mil) {
        Some(diameter)
    } else {
        None
    }
}

fn is_padstack_instance_preamble(bytes: &[u8], offset: usize, name_len: usize) -> bool {
    const PREFIX: &[(usize, u32)] = &[
        (0, 7),
        (4, 2),
        (8, 1),
        (12, 0),
        (16, 1),
        (24, 0),
        (28, 7),
        (32, 1),
        (36, 7),
        (40, 2),
        (44, 1),
        (48, 11),
        (52, 4),
    ];
    PREFIX
        .iter()
        .all(|(relative, expected)| read_u32_le(bytes, offset + relative) == Some(*expected))
        && read_u32_le(bytes, offset + 56) == Some(name_len as u32)
        && read_u32_le(bytes, offset + 20)
            .map(|id| id <= 10_000_000)
            .unwrap_or(false)
}

fn is_valid_layout_coordinate(x: f64, y: f64) -> bool {
    if !x.is_finite() || !y.is_finite() {
        return false;
    }
    let x_mil = x * 39_370.078_740_157_48;
    let y_mil = y * 39_370.078_740_157_48;
    (-10_000.0..=10_000.0).contains(&x_mil) && (-10_000.0..=10_000.0).contains(&y_mil)
}

fn parse_secondary_name(bytes: &[u8], offset: usize) -> (Option<String>, Option<i64>) {
    let Some(length) = read_u32_le(bytes, offset).map(|value| value as usize) else {
        return (None, None);
    };
    if !(1..=64).contains(&length) || offset + 4 + length + 4 > bytes.len() {
        return (None, None);
    }
    let raw_start = offset + 4;
    let raw_end = raw_start + length;
    let raw = &bytes[raw_start..raw_end];
    if !raw.iter().all(|byte| (0x20..0x7f).contains(byte)) {
        return (None, None);
    }
    (
        Some(String::from_utf8_lossy(raw).into_owned()),
        read_i32_le(bytes, raw_end).map(i64::from),
    )
}

fn padstack_instance_name_kind(name: &str) -> &'static str {
    if is_via_instance_name(name) {
        "via"
    } else if name.starts_with("UNNAMED") {
        "unnamed"
    } else if name.contains('-') {
        "component_pin"
    } else {
        "named"
    }
}

fn scan_path_records(
    bytes: &[u8],
    base_offset: usize,
    layer_names: &HashMap<i64, String>,
    net_names: &HashMap<u64, String>,
) -> Vec<BinaryPathRecord> {
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
        let Some(width) = read_f64_le(bytes, width_offset) else {
            continue;
        };
        let width_mil = width * 39_370.078_740_157_48;
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
        let Some(items) = path_items(bytes, doubles_offset, double_count) else {
            continue;
        };
        let (line_segment_count, arc_segment_count) = path_segment_counts(&items);
        let point_count = items
            .iter()
            .filter(|item| item.kind.as_str() == "point")
            .count();
        let net_index = path_net_index(bytes, width_offset);
        let layer_id = path_layer_id(bytes, width_offset);
        records.push(BinaryPathRecord {
            offset: base_offset + width_offset,
            geometry_id: path_geometry_id(bytes, width_offset),
            net_index,
            net_name: net_index.and_then(|index| net_names.get(&index).cloned()),
            layer_id,
            layer_name: layer_id.and_then(|id| layer_names.get(&id).cloned()),
            named: path_has_line_name(bytes, width_offset),
            width,
            item_count: items.len(),
            point_count,
            line_segment_count,
            arc_segment_count,
            items,
        });
    }
    records
}

fn scan_polygon_records(
    bytes: &[u8],
    base_offset: usize,
    layer_names: &HashMap<i64, String>,
    net_names: &HashMap<u64, String>,
) -> Vec<BinaryPolygonRecord> {
    let mut records = Vec::new();
    let mut count_offset = 100;
    while count_offset + 8 <= bytes.len() {
        let Some(header) = polygon_header_at(bytes, count_offset) else {
            count_offset += 1;
            continue;
        };
        let Some(double_count) = read_u32_le(bytes, count_offset).map(|value| value as usize)
        else {
            count_offset += 1;
            continue;
        };
        let coordinate_offset = count_offset + 8;
        if double_count % 2 != 0
            || double_count < 6
            || double_count > 200_000
            || coordinate_offset + double_count * 8 > bytes.len()
        {
            count_offset += 1;
            continue;
        }
        let Some(items) = path_items(bytes, coordinate_offset, double_count) else {
            count_offset += 1;
            continue;
        };
        let point_count = items
            .iter()
            .filter(|item| item.kind.as_str() == "point")
            .count();
        if point_count < 3 {
            count_offset += 1;
            continue;
        }
        let arc_segment_count = items
            .iter()
            .filter(|item| item.kind.as_str() == "arc_height")
            .count();
        let coordinate_end = coordinate_offset + double_count * 8;
        records.push(BinaryPolygonRecord {
            offset: base_offset + header.preamble_offset,
            count_offset: base_offset + count_offset,
            coordinate_offset: base_offset + coordinate_offset,
            geometry_id: header.geometry_id,
            parent_geometry_id: header.parent_geometry_id,
            is_void: header.parent_geometry_id.is_some(),
            layer_id: header.layer_id,
            layer_name: header.layer_id.and_then(|id| layer_names.get(&id).cloned()),
            net_index: header.net_index,
            net_name: header
                .net_index
                .and_then(|index| net_names.get(&index).cloned()),
            item_count: items.len(),
            point_count,
            arc_segment_count,
            items,
        });
        count_offset = coordinate_end;
    }
    records
}

fn assign_polygon_net_owners(
    polygons: &mut [BinaryPolygonRecord],
    paths: &[BinaryPathRecord],
    net_names: &HashMap<u64, String>,
) {
    let mut path_refs: Vec<&BinaryPathRecord> = paths
        .iter()
        .filter(|record| record.net_index.is_some())
        .collect();
    path_refs.sort_by_key(|record| record.offset);
    if path_refs.is_empty() {
        return;
    }

    let mut polygon_indices: Vec<usize> = (0..polygons.len()).collect();
    polygon_indices.sort_by_key(|index| polygons[*index].offset);

    let mut path_index = 0;
    let mut current_net_index = None;
    for polygon_index in polygon_indices {
        let polygon_offset = polygons[polygon_index].offset;
        while path_index < path_refs.len() && path_refs[path_index].offset < polygon_offset {
            current_net_index = path_refs[path_index].net_index;
            path_index += 1;
        }
        if polygons[polygon_index].net_index.is_some() {
            continue;
        }
        let owner = current_net_index.or_else(|| {
            path_refs
                .get(path_index)
                .and_then(|record| record.net_index)
        });
        if let Some(net_index) = owner {
            polygons[polygon_index].net_index = Some(net_index);
            polygons[polygon_index].net_name = net_names.get(&net_index).cloned();
        }
    }

    let owner_by_geometry: HashMap<u64, (Option<u64>, Option<String>)> = polygons
        .iter()
        .filter_map(|record| {
            Some((
                record.geometry_id?,
                (record.net_index, record.net_name.clone()),
            ))
        })
        .collect();
    for polygon in polygons {
        let Some(parent_id) = polygon.parent_geometry_id else {
            continue;
        };
        if let Some((net_index, net_name)) = owner_by_geometry.get(&parent_id) {
            polygon.net_index = *net_index;
            polygon.net_name = net_name.clone();
        }
    }
}

#[derive(Debug, Clone)]
struct PolygonHeader {
    preamble_offset: usize,
    geometry_id: Option<u64>,
    parent_geometry_id: Option<u64>,
    layer_id: Option<i64>,
    net_index: Option<u64>,
}

fn polygon_header_at(bytes: &[u8], count_offset: usize) -> Option<PolygonHeader> {
    const HEADER_FIELDS: &[(usize, u32)] = &[
        (4, 196_608),
        (8, 393_216),
        (12, 65_536),
        (16, 458_752),
        (20, 131_072),
        (24, 65_536),
        (28, 0),
        (32, 65_536),
        (40, 0),
        (44, 458_752),
        (48, 0),
        (52, 458_752),
        (56, 0),
        (60, 262_144),
        (68, 4_294_901_760),
        (92, 16_777_216),
        (96, 2),
    ];
    let preamble_offset = count_offset.checked_sub(100)?;
    if count_offset + 8 > bytes.len()
        || read_u32_le(bytes, count_offset + 4) != Some(2)
        || read_u32_le(bytes, preamble_offset) != read_u32_le(bytes, preamble_offset + 36)
        || !HEADER_FIELDS.iter().all(|(relative, expected)| {
            read_u32_le(bytes, preamble_offset + relative) == Some(*expected)
        })
    {
        return None;
    }

    let geometry_raw = read_u32_le(bytes, preamble_offset)? >> 16;
    let geometry_id = if (1..=10_000_000).contains(&geometry_raw) {
        Some(u64::from(geometry_raw))
    } else {
        None
    };
    let layer_raw = read_u32_le(bytes, preamble_offset + 76)? >> 16;
    let layer_id = if (1..=100_000).contains(&layer_raw) {
        Some(i64::from(layer_raw))
    } else {
        None
    };
    let net_raw = read_u32_le(bytes, preamble_offset + 64)? >> 16;
    let net_index = if net_raw <= 100_000 {
        Some(u64::from(net_raw))
    } else {
        None
    };

    let parent_low = read_u32_le(bytes, preamble_offset + 84)? >> 24;
    let parent_high = read_u32_le(bytes, preamble_offset + 88)? & 0xff;
    let parent_geometry_id = if parent_low == 255 && parent_high == 255 {
        None
    } else {
        let parent_id = parent_high * 256 + parent_low;
        if (1..=10_000_000).contains(&parent_id) {
            Some(u64::from(parent_id))
        } else {
            None
        }
    };

    Some(PolygonHeader {
        preamble_offset,
        geometry_id,
        parent_geometry_id,
        layer_id,
        net_index,
    })
}

fn scan_outline_polygon_records(
    bytes: &[u8],
    base_offset: usize,
    layer_names: &HashMap<i64, String>,
) -> Vec<BinaryPolygonRecord> {
    let mut records = Vec::new();
    let mut count_offset = 64;
    while count_offset + 8 <= bytes.len() {
        let Some(header) = outline_polygon_header_at(bytes, count_offset, layer_names) else {
            count_offset += 1;
            continue;
        };
        let Some(double_count) = read_u32_le(bytes, count_offset).map(|value| value as usize)
        else {
            count_offset += 1;
            continue;
        };
        let coordinate_offset = count_offset + 8;
        if double_count % 2 != 0
            || double_count < 6
            || double_count > 200_000
            || coordinate_offset + double_count * 8 > bytes.len()
        {
            count_offset += 1;
            continue;
        }
        let Some(items) = path_items(bytes, coordinate_offset, double_count) else {
            count_offset += 1;
            continue;
        };
        let point_count = items
            .iter()
            .filter(|item| item.kind.as_str() == "point")
            .count();
        if point_count < 3 {
            count_offset += 1;
            continue;
        }
        let arc_segment_count = items
            .iter()
            .filter(|item| item.kind.as_str() == "arc_height")
            .count();
        let coordinate_end = coordinate_offset + double_count * 8;
        records.push(BinaryPolygonRecord {
            offset: base_offset + header.preamble_offset,
            count_offset: base_offset + count_offset,
            coordinate_offset: base_offset + coordinate_offset,
            geometry_id: header.geometry_id,
            parent_geometry_id: None,
            is_void: false,
            layer_id: header.layer_id,
            layer_name: header.layer_id.and_then(|id| layer_names.get(&id).cloned()),
            net_index: None,
            net_name: None,
            item_count: items.len(),
            point_count,
            arc_segment_count,
            items,
        });
        count_offset = coordinate_end;
    }
    records
}

fn outline_polygon_header_at(
    bytes: &[u8],
    count_offset: usize,
    layer_names: &HashMap<i64, String>,
) -> Option<PolygonHeader> {
    const HEADER_FIELDS: &[(usize, u32)] = &[
        (4, 0),
        (8, 458_752),
        (12, 0),
        (16, 458_752),
        (20, 0),
        (24, 262_144),
        (28, 4_294_901_760),
        (32, 4_294_967_295),
        (36, 327_679),
        (44, 0),
        (48, 4_278_190_080),
        (52, 620_756_991),
        (56, 16_777_216),
        (60, 2),
    ];
    let preamble_offset = count_offset.checked_sub(64)?;
    if count_offset + 8 > bytes.len()
        || read_u32_le(bytes, count_offset + 4) != Some(2)
        || !HEADER_FIELDS.iter().all(|(relative, expected)| {
            read_u32_le(bytes, preamble_offset + relative) == Some(*expected)
        })
    {
        return None;
    }

    let geometry_raw = read_u32_le(bytes, preamble_offset)? >> 16;
    let geometry_id = if (1..=10_000_000).contains(&geometry_raw) {
        Some(u64::from(geometry_raw))
    } else {
        None
    };
    let layer_raw = read_u32_le(bytes, preamble_offset + 40)? >> 16;
    let layer_id = if (1..=100_000).contains(&layer_raw) {
        Some(i64::from(layer_raw))
    } else {
        None
    };
    let layer_name = layer_id.and_then(|id| layer_names.get(&id));
    if layer_name
        .map(|name| name.eq_ignore_ascii_case("outline"))
        != Some(true)
    {
        return None;
    }

    Some(PolygonHeader {
        preamble_offset,
        geometry_id,
        parent_geometry_id: None,
        layer_id,
        net_index: None,
    })
}

fn path_items(
    bytes: &[u8],
    doubles_offset: usize,
    double_count: usize,
) -> Option<Vec<BinaryPathItem>> {
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
            items.push(BinaryPathItem {
                kind: "arc_height".to_string(),
                x: None,
                y: None,
                arc_height: Some(first),
            });
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
            items.push(BinaryPathItem {
                kind: "point".to_string(),
                x: Some(first),
                y: Some(second),
                arc_height: None,
            });
        }
        index += 2;
    }
    if items.len() < 2 {
        return None;
    }
    Some(items)
}

fn path_segment_counts(items: &[BinaryPathItem]) -> (usize, usize) {
    let mut line_segments = 0;
    let mut arc_segments = 0;
    for index in 1..items.len() {
        match (items[index - 1].kind.as_str(), items[index].kind.as_str()) {
            (_, "arc_height") => {}
            ("arc_height", "point") => {
                if index >= 2 && items[index - 2].kind.as_str() == "point" {
                    arc_segments += 1;
                }
            }
            ("point", "point") => line_segments += 1,
            _ => {}
        }
    }
    (line_segments, arc_segments)
}

fn path_geometry_id(bytes: &[u8], width_offset: usize) -> Option<u64> {
    let preamble_offset = width_offset.checked_sub(80)?;
    let low = read_u32_be(bytes, preamble_offset + 12)?;
    let high = read_u32_le(bytes, preamble_offset + 16)?;
    if low > 255 || high > 1_000_000 {
        return None;
    }
    Some(u64::from(high) * 256 + u64::from(low))
}

fn path_net_index(bytes: &[u8], width_offset: usize) -> Option<u64> {
    let preamble_offset = width_offset.checked_sub(80)?;
    let low = read_u32_be(bytes, preamble_offset + 40)?;
    if low > 255 {
        return None;
    }
    let high = u64::from(*bytes.get(preamble_offset + 44)?);
    if bytes.get(preamble_offset + 45..preamble_offset + 48)? != [0x00, 0x00, 0xff] {
        return None;
    }
    Some(high * 256 + u64::from(low))
}

fn path_layer_id(bytes: &[u8], width_offset: usize) -> Option<i64> {
    let preamble_offset = width_offset.checked_sub(80)?;
    let value = read_u32_be(bytes, preamble_offset + 52)?;
    let layer_id = value.checked_sub(65_536)?;
    if layer_id > 100_000 {
        return None;
    }
    Some(i64::from(layer_id))
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

fn read_u32_be(bytes: &[u8], offset: usize) -> Option<u32> {
    let value = bytes.get(offset..offset + 4)?;
    Some(u32::from_be_bytes(value.try_into().ok()?))
}

fn read_i32_le(bytes: &[u8], offset: usize) -> Option<i32> {
    let value = bytes.get(offset..offset + 4)?;
    Some(i32::from_le_bytes(value.try_into().ok()?))
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
            (
                "DemoCase_LPDDR4.def",
                8,
                45,
                12,
                54,
                1282,
                293,
                1117,
                1117,
                1117,
                1965,
                7998,
                0,
            ),
            (
                "SW_ARM_1029.def",
                8,
                107,
                18,
                100,
                969,
                492,
                1367,
                1367,
                1367,
                2833,
                9833,
                5,
            ),
            (
                "Zynq_Phoenix_Pro.def",
                10,
                23,
                7,
                66,
                763,
                282,
                1160,
                1069,
                1069,
                2208,
                11297,
                2635,
            ),
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
            let source = fixture(name);
            if !source.exists() {
                continue;
            }
            let parsed = parse_def_file(
                &source,
                &ParseOptions {
                    include_details: false,
                },
            )
            .unwrap();
            let domain = extract_domain(&parsed);
            if name == "DemoCase_LPDDR4.def" {
                assert_eq!(domain.summary.layout_net_count, 335, "{name}");
                assert_eq!(domain.layout_nets[0].name, "GND", "{name}");
                assert_eq!(domain.layout_nets[331].name, "PMIC_ON_REQ", "{name}");
                assert_eq!(
                    domain.binary_geometry.padstack_instance_record_count, 2843,
                    "{name}"
                );
                assert_eq!(
                    domain
                        .binary_geometry
                        .component_pin_padstack_instance_record_count,
                    1714,
                    "{name}"
                );
                assert_eq!(
                    domain
                        .binary_geometry
                        .named_via_padstack_instance_record_count,
                    1117,
                    "{name}"
                );
                assert_eq!(
                    domain
                        .binary_geometry
                        .unnamed_padstack_instance_record_count,
                    12,
                    "{name}"
                );
                assert_eq!(
                    domain
                        .binary_geometry
                        .padstack_instance_secondary_name_count,
                    1726,
                    "{name}"
                );
                assert_eq!(domain.binary_geometry.polygon_record_count, 840, "{name}");
                assert_eq!(
                    domain.binary_geometry.polygon_outer_record_count, 74,
                    "{name}"
                );
                assert_eq!(
                    domain.binary_geometry.polygon_void_record_count, 766,
                    "{name}"
                );
                assert_eq!(domain.binary_geometry.polygon_point_count, 9405, "{name}");
                assert_eq!(
                    domain.binary_geometry.polygon_arc_segment_count, 6692,
                    "{name}"
                );
            }
            if name == "SW_ARM_1029.def" {
                assert_eq!(domain.summary.layout_net_count, 456, "{name}");
                assert_eq!(
                    domain.binary_geometry.padstack_instance_record_count, 3531,
                    "{name}"
                );
                assert_eq!(
                    domain
                        .binary_geometry
                        .component_pin_padstack_instance_record_count,
                    2163,
                    "{name}"
                );
                assert_eq!(
                    domain
                        .binary_geometry
                        .named_via_padstack_instance_record_count,
                    1367,
                    "{name}"
                );
                assert_eq!(
                    domain
                        .binary_geometry
                        .padstack_instance_secondary_name_count,
                    2164,
                    "{name}"
                );
                let outline = domain
                    .binary_path_records
                    .iter()
                    .find(|record| record.geometry_id == Some(3675))
                    .unwrap();
                assert_eq!(outline.layer_id, Some(17));
                assert_eq!(outline.layer_name.as_deref(), Some("Outline"));
                assert_eq!(domain.binary_geometry.polygon_record_count, 403, "{name}");
                assert_eq!(
                    domain.binary_geometry.polygon_outer_record_count, 178,
                    "{name}"
                );
                assert_eq!(
                    domain.binary_geometry.polygon_void_record_count, 225,
                    "{name}"
                );
                assert_eq!(domain.binary_geometry.polygon_point_count, 12297, "{name}");
                assert_eq!(
                    domain.binary_geometry.polygon_arc_segment_count, 4538,
                    "{name}"
                );
            }
            if name == "Zynq_Phoenix_Pro.def" {
                assert_eq!(domain.summary.layout_net_count, 326, "{name}");
                assert_eq!(
                    domain.binary_geometry.padstack_instance_record_count, 2709,
                    "{name}"
                );
                assert_eq!(
                    domain
                        .binary_geometry
                        .component_pin_padstack_instance_record_count,
                    1549,
                    "{name}"
                );
                assert_eq!(
                    domain
                        .binary_geometry
                        .named_via_padstack_instance_record_count,
                    1160,
                    "{name}"
                );
                assert_eq!(
                    domain
                        .binary_geometry
                        .padstack_instance_secondary_name_count,
                    1549,
                    "{name}"
                );
                assert_eq!(domain.binary_geometry.polygon_record_count, 744, "{name}");
                assert_eq!(
                    domain.binary_geometry.polygon_outer_record_count, 147,
                    "{name}"
                );
                assert_eq!(
                    domain.binary_geometry.polygon_void_record_count, 597,
                    "{name}"
                );
                assert_eq!(domain.binary_geometry.polygon_point_count, 10738, "{name}");
                assert_eq!(
                    domain.binary_geometry.polygon_arc_segment_count, 4559,
                    "{name}"
                );
            }
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

    #[test]
    fn extracts_binary_path_record_points() {
        let source = fixture("DemoCase_LPDDR4.def");
        if !source.exists() {
            return;
        }
        let parsed = parse_def_file(
            &source,
            &ParseOptions {
                include_details: false,
            },
        )
        .unwrap();
        let domain = extract_domain(&parsed);
        assert_eq!(domain.binary_path_records.len(), 1965);
        let first = &domain.binary_path_records[0];
        assert_eq!(first.geometry_id, Some(0));
        assert_eq!(first.net_index, Some(0));
        assert_eq!(first.net_name.as_deref(), Some("GND"));
        assert_eq!(first.layer_id, Some(1));
        assert_eq!(first.layer_name.as_deref(), Some("BOTTOM"));
        assert_eq!(first.line_segment_count, 1);
        assert_eq!(first.arc_segment_count, 0);
        assert_eq!(first.point_count, 2);
        assert!((first.width - 0.0002032).abs() < 1e-12);
        assert!((first.items[0].x.unwrap() - 0.00748411).abs() < 1e-12);
        assert!((first.items[0].y.unwrap() - 0.008244586).abs() < 1e-12);
        assert!((first.items[1].x.unwrap() - 0.007891018).abs() < 1e-12);
        assert!((first.items[1].y.unwrap() - 0.008244586).abs() < 1e-12);

        let late = domain
            .binary_path_records
            .iter()
            .find(|record| record.geometry_id == Some(3778))
            .unwrap();
        assert_eq!(late.net_index, Some(331));
        assert_eq!(late.net_name.as_deref(), Some("PMIC_ON_REQ"));
        assert_eq!(late.layer_id, Some(15));
        assert_eq!(late.layer_name.as_deref(), Some("TOP"));
    }

    #[test]
    fn extracts_binary_padstack_instance_records() {
        let source = fixture("DemoCase_LPDDR4.def");
        if !source.exists() {
            return;
        }
        let parsed = parse_def_file(
            &source,
            &ParseOptions {
                include_details: false,
            },
        )
        .unwrap();
        let domain = extract_domain(&parsed);
        assert_eq!(domain.binary_padstack_instance_records.len(), 2843);

        let first = &domain.binary_padstack_instance_records[0];
        assert_eq!(first.geometry_id, 3781);
        assert_eq!(first.name, "U8-60");
        assert_eq!(first.name_kind, "component_pin");
        assert_eq!(first.net_index, Some(0));
        assert_eq!(first.net_name.as_deref(), Some("GND"));
        assert_eq!(first.raw_owner_index, Some(35));
        assert_eq!(first.raw_definition_index, Some(0));
        assert_eq!(first.secondary_name.as_deref(), Some("60"));
        assert_eq!(first.secondary_id, Some(0));
        assert_eq!(first.drill_diameter, None);
        assert!((first.x - 0.013511784).abs() < 1e-12);
        assert!((first.y - 0.0143383).abs() < 1e-12);
        assert!((first.rotation - std::f64::consts::FRAC_PI_2).abs() < 1e-12);

        let component_pin = domain
            .binary_padstack_instance_records
            .iter()
            .find(|record| record.geometry_id == 4228)
            .unwrap();
        assert_eq!(component_pin.name, "U1-E27");
        assert_eq!(component_pin.net_index, Some(330));
        assert_eq!(component_pin.net_name.as_deref(), Some("JTAG_TDI"));
        assert_eq!(component_pin.secondary_name.as_deref(), Some("E27"));
        assert_eq!(component_pin.secondary_id, Some(386));

        let unnamed = domain
            .binary_padstack_instance_records
            .iter()
            .find(|record| record.geometry_id == 4608)
            .unwrap();
        assert_eq!(unnamed.name, "UNNAMED_10");
        assert_eq!(unnamed.name_kind, "unnamed");
        assert_eq!(unnamed.net_index, None);
        assert_eq!(unnamed.secondary_name.as_deref(), Some("UNNAMED_10"));
        assert_eq!(unnamed.secondary_id, Some(-1));
        assert!((unnamed.rotation - 3.0 * std::f64::consts::FRAC_PI_2).abs() < 1e-12);

        let late = domain
            .binary_padstack_instance_records
            .iter()
            .find(|record| record.geometry_id == 6623)
            .unwrap();
        assert_eq!(late.name, "via_4897");
        assert_eq!(late.name_kind, "via");
        assert_eq!(late.net_index, Some(331));
        assert_eq!(late.net_name.as_deref(), Some("PMIC_ON_REQ"));
        assert_eq!(late.secondary_name, None);

        let via = domain
            .binary_padstack_instance_records
            .iter()
            .find(|record| record.name == "via_3781")
            .unwrap();
        assert!((via.drill_diameter.unwrap() - 0.0002032).abs() < 1e-12);
    }

    #[test]
    fn extracts_binary_polygon_records() {
        let source = fixture("DemoCase_LPDDR4.def");
        if !source.exists() {
            return;
        }
        let parsed = parse_def_file(
            &source,
            &ParseOptions {
                include_details: false,
            },
        )
        .unwrap();
        let domain = extract_domain(&parsed);
        assert_eq!(domain.binary_polygon_records.len(), 840);

        let first = &domain.binary_polygon_records[0];
        assert_eq!(first.geometry_id, Some(94));
        assert_eq!(first.parent_geometry_id, None);
        assert!(!first.is_void);
        assert_eq!(first.layer_id, Some(1));
        assert_eq!(first.layer_name.as_deref(), Some("BOTTOM"));
        assert_eq!(first.item_count, 369);
        assert_eq!(first.point_count, 269);
        assert_eq!(first.arc_segment_count, 100);
        assert_eq!(first.net_index, Some(0));
        assert_eq!(first.net_name.as_deref(), Some("GND"));
        assert!((first.items[0].x.unwrap() - 0.0025146).abs() < 1e-12);
        assert!((first.items[0].y.unwrap() - 0.000508).abs() < 1e-12);
        assert!((first.items[1].x.unwrap() - 0.0482854).abs() < 1e-12);
        assert!((first.items[1].y.unwrap() - 0.000508).abs() < 1e-12);

        let first_void = domain
            .binary_polygon_records
            .iter()
            .find(|record| record.geometry_id == Some(95))
            .unwrap();
        assert!(first_void.is_void);
        assert_eq!(first_void.parent_geometry_id, Some(94));
        assert_eq!(first_void.layer_id, Some(1));
        assert_eq!(first_void.layer_name.as_deref(), Some("BOTTOM"));
        assert_eq!(first_void.net_index, Some(0));
        assert_eq!(first_void.net_name.as_deref(), Some("GND"));
        assert_eq!(first_void.item_count, 20);
        assert_eq!(first_void.point_count, 16);
        assert_eq!(first_void.arc_segment_count, 4);

        let zynq_source = fixture("Zynq_Phoenix_Pro.def");
        if !zynq_source.exists() {
            return;
        }
        let zynq_parsed = parse_def_file(
            &zynq_source,
            &ParseOptions {
                include_details: false,
            },
        )
        .unwrap();
        let zynq_domain = extract_domain(&zynq_parsed);
        let zynq_first = &zynq_domain.binary_polygon_records[0];
        assert_eq!(zynq_first.geometry_id, Some(533));
        assert_eq!(zynq_first.layer_id, Some(19));
        assert_eq!(zynq_first.layer_name.as_deref(), Some("TOP"));
        assert_eq!(zynq_first.net_index, Some(0));
        assert_eq!(zynq_first.net_name.as_deref(), Some("GND"));
        assert_eq!(zynq_first.point_count, 4);
        assert_eq!(zynq_first.arc_segment_count, 0);
        assert_eq!(zynq_first.count_offset % 2, 1);
        let high_parent_void = zynq_domain
            .binary_polygon_records
            .iter()
            .find(|record| record.parent_geometry_id == Some(741))
            .unwrap();
        assert!(high_parent_void.is_void);
    }
}
