use crate::domain::{extract_domain, scan_length_prefixed_binary_strings};
use crate::model::DefDomain;
use crate::parser::{parse_def_file, ParseOptions};
use serde::Serialize;
use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize)]
pub struct AuroraComparison {
    pub def_source: String,
    pub auroradb_root: String,
    pub def: DefAlignmentSummary,
    pub auroradb: AuroraDbSummary,
    pub checks: Vec<ComparisonCheck>,
}

#[derive(Debug, Clone, Serialize)]
pub struct DefAlignmentSummary {
    pub board_metal_layer_names: Vec<String>,
    pub board_metal_layer_count: usize,
    pub padstack_names: Vec<String>,
    pub multilayer_padstack_names: Vec<String>,
    pub component_definition_names: Vec<String>,
    pub component_placement_names: Vec<String>,
    pub component_part_candidate_names: Vec<String>,
    pub domain: DefDomain,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct AuroraDbSummary {
    pub has_layout: bool,
    pub has_parts: bool,
    pub units: Option<String>,
    pub metal_layer_count: usize,
    pub layer_count: usize,
    pub component_count: usize,
    pub net_count: usize,
    pub net_pin_count: usize,
    pub net_via_count: usize,
    pub net_geometry_count: usize,
    pub net_line_count: usize,
    pub net_arc_count: usize,
    pub net_location_count: usize,
    pub net_polygon_count: usize,
    pub net_polygon_hole_count: usize,
    pub shape_count: usize,
    pub via_template_count: usize,
    pub part_count: usize,
    pub footprint_count: usize,
    pub layer_names: Vec<String>,
    pub net_names: Vec<String>,
    pub via_template_names: Vec<String>,
    pub part_names: Vec<String>,
    pub component_names: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ComparisonCheck {
    pub name: String,
    pub status: String,
    pub expected_count: usize,
    pub actual_count: usize,
    pub missing: Vec<String>,
    pub extra: Vec<String>,
    pub message: Option<String>,
}

pub fn compare_def_to_auroradb(
    source: &Path,
    auroradb_root: &Path,
) -> Result<AuroraComparison, String> {
    let parsed = parse_def_file(
        source,
        &ParseOptions {
            include_details: false,
        },
    )
    .map_err(|error| error.to_string())?;
    let domain = extract_domain(&parsed);
    let binary_strings = scan_length_prefixed_binary_strings(&parsed);
    let binary_string_set: HashSet<String> = binary_strings.into_iter().collect();
    let auroradb = read_auroradb_summary(auroradb_root)?;
    let def = DefAlignmentSummary {
        board_metal_layer_names: domain
            .board_metal_layers
            .iter()
            .map(|layer| layer.name.clone())
            .collect(),
        board_metal_layer_count: domain.board_metal_layers.len(),
        padstack_names: sorted_names(
            domain
                .padstacks
                .iter()
                .filter_map(|padstack| padstack.name.clone())
                .collect(),
        ),
        multilayer_padstack_names: sorted_names(
            domain
                .padstacks
                .iter()
                .filter(|padstack| {
                    padstack
                        .layer_pads
                        .iter()
                        .filter_map(|layer| layer.layer_name.as_ref())
                        .collect::<HashSet<_>>()
                        .len()
                        > 1
                })
                .filter_map(|padstack| padstack.name.clone())
                .collect(),
        ),
        component_definition_names: sorted_names(
            domain
                .components
                .iter()
                .map(|component| component.name.clone())
                .collect(),
        ),
        component_placement_names: sorted_names(
            domain
                .component_placements
                .iter()
                .map(|placement| placement.refdes.clone())
                .collect(),
        ),
        component_part_candidate_names: sorted_names(
            domain
                .component_placements
                .iter()
                .flat_map(|placement| placement.part_name_candidates.iter().cloned())
                .collect(),
        ),
        domain,
    };
    let checks = build_checks(&def, &auroradb, &binary_string_set);
    Ok(AuroraComparison {
        def_source: source
            .canonicalize()
            .unwrap_or_else(|_| source.to_path_buf())
            .display()
            .to_string(),
        auroradb_root: auroradb_root
            .canonicalize()
            .unwrap_or_else(|_| auroradb_root.to_path_buf())
            .display()
            .to_string(),
        def,
        auroradb,
        checks,
    })
}

pub fn read_auroradb_summary(root: &Path) -> Result<AuroraDbSummary, String> {
    let root = root.expand_home();
    if !root.exists() {
        return Err(format!(
            "AuroraDB directory does not exist: {}",
            root.display()
        ));
    }
    if !root.is_dir() {
        return Err(format!(
            "AuroraDB path is not a directory: {}",
            root.display()
        ));
    }

    let mut summary = AuroraDbSummary::default();
    let layout_path = root.join("layout.db");
    if layout_path.exists() {
        summary.has_layout = true;
        let text = fs::read_to_string(&layout_path)
            .map_err(|error| format!("failed to read {}: {error}", layout_path.display()))?;
        summary.units = first_item_value(&text, "Units");
        summary.layer_names = first_item_values(&text, "MetalLayers");
        summary.metal_layer_count = summary.layer_names.len();
        summary.layer_count = first_item_values(&text, "LayerNameIDs").len() / 2;
        summary.net_names = sorted_names(direct_child_block_names(&text, "Nets"));
        summary.net_count = summary.net_names.len();
        summary.net_pin_count = count_item_in_block(&text, "NetPins", "Pin");
        summary.net_via_count = count_item_in_block(&text, "NetVias", "Via");
        summary.shape_count = count_item_in_block(&text, "ShapeList", "IdName");
        summary.via_template_names = via_template_names(&text);
        summary.via_template_count = summary.via_template_names.len();
    }

    let parts_path = root.join("parts.db");
    if parts_path.exists() {
        summary.has_parts = true;
        let text = fs::read_to_string(&parts_path)
            .map_err(|error| format!("failed to read {}: {error}", parts_path.display()))?;
        summary.part_names = sorted_names(part_names(&text));
        summary.part_count = summary.part_names.len();
        summary.footprint_count = direct_child_block_names(&text, "FootprintList").len();
    }

    for layer_path in layer_files(&root, &summary.layer_names)? {
        let text = fs::read_to_string(&layer_path)
            .map_err(|error| format!("failed to read {}: {error}", layer_path.display()))?;
        summary.component_names.extend(component_item_names(&text));
        let geometry_counts = net_geometry_type_counts(&text);
        summary.net_geometry_count += geometry_counts.total;
        summary.net_line_count += geometry_counts.lines;
        summary.net_arc_count += geometry_counts.arcs;
        summary.net_location_count += geometry_counts.locations;
        summary.net_polygon_count += geometry_counts.polygons;
        summary.net_polygon_hole_count += geometry_counts.polygon_holes;
    }
    summary.component_names = sorted_names(summary.component_names);
    summary.component_count = summary.component_names.len();

    Ok(summary)
}

fn build_checks(
    def: &DefAlignmentSummary,
    auroradb: &AuroraDbSummary,
    binary_strings: &HashSet<String>,
) -> Vec<ComparisonCheck> {
    let padstack_names: HashSet<String> = def.padstack_names.iter().cloned().collect();
    let component_names: HashSet<String> = def.component_definition_names.iter().cloned().collect();
    let component_placement_names: HashSet<String> =
        def.component_placement_names.iter().cloned().collect();
    let component_part_candidate_names: HashSet<String> =
        def.component_part_candidate_names.iter().cloned().collect();
    let electrical_net_names: Vec<String> = auroradb
        .net_names
        .iter()
        .filter(|name| !is_synthetic_no_net(name))
        .cloned()
        .collect();
    vec![
        exact_check(
            "metal_layer_names",
            &auroradb.layer_names,
            &def.board_metal_layer_names,
            "Board metal layers parsed from DEF SLayer records.",
        ),
        membership_check(
            "via_template_names_in_padstacks",
            &auroradb.via_template_names,
            &padstack_names,
            "AuroraDB ViaList names should be present in DEF padstack definitions.",
            "fail",
        ),
        membership_check(
            "net_names_in_binary_string_table",
            &electrical_net_names,
            binary_strings,
            "AuroraDB electrical net names should be present in DEF binary string records; synthetic NONET is generated by the exporter.",
            "fail",
        ),
        membership_check(
            "component_names_in_placements",
            &auroradb.component_names,
            &component_placement_names,
            "AuroraDB layer component names should be present as top-level DEF placement records.",
            "fail",
        ),
        membership_check(
            "part_names_in_component_placement_candidates",
            &auroradb.part_names,
            &component_part_candidate_names,
            "AuroraDB part names should be derivable from DEF placement COMP_* fields.",
            "fail",
        ),
        membership_check(
            "part_names_in_component_definitions",
            &auroradb.part_names,
            &component_names,
            "Missing names indicate part/component placement data still needs deeper binary decoding.",
            "warn",
        ),
        count_hint_check(
            "via_instance_name_count_vs_net_vias",
            auroradb.net_via_count,
            def.domain.binary_strings.via_instance_name_count,
            "DEF via_* string count is a reverse-engineering hint, not yet an export invariant.",
        ),
        count_hint_check(
            "binary_via_record_count_vs_net_vias",
            auroradb.net_via_count,
            def.domain.binary_geometry.via_record_count,
            "DEF binary via-tail records decode direct via coordinates; component pad-derived vias still need deeper pin/pad decoding.",
        ),
        count_hint_check(
            "binary_path_line_count_vs_auroradb_lines",
            auroradb.net_line_count,
            def.domain.binary_geometry.path_line_segment_count,
            "DEF binary path records decode raw-point line segments; layer/net filtering and pad-derived geometry are still under reverse engineering.",
        ),
        count_hint_check(
            "binary_path_arc_count_vs_auroradb_arcs",
            auroradb.net_arc_count,
            def.domain.binary_geometry.path_arc_segment_count,
            "DEF binary path records decode raw-point arc-height markers; exact arc export still needs center/CCW validation per layer.",
        ),
        count_hint_check(
            "geometry_instance_name_count_vs_net_geometries",
            auroradb.net_geometry_count,
            def.domain.binary_strings.geometry_instance_name_count,
            "DEF geometry-name string count is a reverse-engineering hint, not yet an export invariant.",
        ),
    ]
}

fn is_synthetic_no_net(name: &str) -> bool {
    matches!(
        name.to_ascii_uppercase().as_str(),
        "NONET" | "NO_NET" | "NO-NET"
    )
}

fn exact_check(
    name: &str,
    expected: &[String],
    actual: &[String],
    message: &str,
) -> ComparisonCheck {
    let expected_set: HashSet<String> = expected.iter().cloned().collect();
    let actual_set: HashSet<String> = actual.iter().cloned().collect();
    let missing = sorted_names(expected_set.difference(&actual_set).cloned().collect());
    let extra = sorted_names(actual_set.difference(&expected_set).cloned().collect());
    ComparisonCheck {
        name: name.to_string(),
        status: if expected == actual { "pass" } else { "fail" }.to_string(),
        expected_count: expected.len(),
        actual_count: actual.len(),
        missing,
        extra,
        message: Some(message.to_string()),
    }
}

fn membership_check(
    name: &str,
    expected_members: &[String],
    actual_set: &HashSet<String>,
    message: &str,
    missing_status: &str,
) -> ComparisonCheck {
    let missing = sorted_names(
        expected_members
            .iter()
            .filter(|value| !actual_set.contains(*value))
            .cloned()
            .collect(),
    );
    ComparisonCheck {
        name: name.to_string(),
        status: if missing.is_empty() {
            "pass"
        } else {
            missing_status
        }
        .to_string(),
        expected_count: expected_members.len(),
        actual_count: expected_members.len() - missing.len(),
        missing,
        extra: Vec::new(),
        message: Some(message.to_string()),
    }
}

fn count_hint_check(
    name: &str,
    expected_count: usize,
    actual_count: usize,
    message: &str,
) -> ComparisonCheck {
    ComparisonCheck {
        name: name.to_string(),
        status: if expected_count == actual_count {
            "pass"
        } else {
            "warn"
        }
        .to_string(),
        expected_count,
        actual_count,
        missing: Vec::new(),
        extra: Vec::new(),
        message: Some(message.to_string()),
    }
}

fn first_item_value(text: &str, item_name: &str) -> Option<String> {
    first_item_values(text, item_name).into_iter().next()
}

fn first_item_values(text: &str, item_name: &str) -> Vec<String> {
    for line in text.lines() {
        let trimmed = line.trim();
        if let Some(rest) = item_rest(trimmed, item_name) {
            return split_tokens(rest);
        }
    }
    Vec::new()
}

fn direct_child_block_names(text: &str, parent_name: &str) -> Vec<String> {
    let mut stack: Vec<String> = Vec::new();
    let mut names = Vec::new();
    for line in text.lines() {
        let trimmed = clean_line(line);
        if trimmed.is_empty() {
            continue;
        }
        if trimmed == "}" {
            stack.pop();
            continue;
        }
        if let Some(name) = block_start_name(trimmed) {
            if stack.last().map(String::as_str) == Some(parent_name) {
                names.push(name.clone());
            }
            stack.push(name);
        }
    }
    names
}

fn count_item_in_block(text: &str, parent_name: &str, item_name: &str) -> usize {
    let mut stack: Vec<String> = Vec::new();
    let mut count = 0;
    for line in text.lines() {
        let trimmed = clean_line(line);
        if trimmed.is_empty() {
            continue;
        }
        if trimmed == "}" {
            stack.pop();
            continue;
        }
        if let Some(name) = block_start_name(trimmed) {
            stack.push(name);
            continue;
        }
        if stack.last().map(String::as_str) == Some(parent_name)
            && item_rest(trimmed, item_name).is_some()
        {
            count += 1;
        }
    }
    count
}

#[derive(Debug, Default)]
struct NetGeometryTypeCounts {
    total: usize,
    lines: usize,
    arcs: usize,
    locations: usize,
    polygons: usize,
    polygon_holes: usize,
}

fn net_geometry_type_counts(text: &str) -> NetGeometryTypeCounts {
    let lines: Vec<&str> = text.lines().collect();
    let mut stack: Vec<String> = Vec::new();
    let mut counts = NetGeometryTypeCounts::default();
    for (index, line) in lines.iter().enumerate() {
        let trimmed = clean_line(line);
        if trimmed.is_empty() {
            continue;
        }
        if trimmed == "}" {
            stack.pop();
            continue;
        }
        if let Some(name) = block_start_name(trimmed) {
            if name == "NetGeom" && stack.iter().any(|part| part == "NetGeometry") {
                counts.total += 1;
                match first_net_geometry_item(&lines, index + 1).as_deref() {
                    Some("Line") => counts.lines += 1,
                    Some("Larc") => counts.arcs += 1,
                    Some("Location") => counts.locations += 1,
                    Some("Polygon") => counts.polygons += 1,
                    Some("PolygonHole") => counts.polygon_holes += 1,
                    _ => {}
                }
            }
            stack.push(name);
        }
    }
    counts
}

fn first_net_geometry_item(lines: &[&str], start: usize) -> Option<String> {
    for line in lines.iter().skip(start) {
        let trimmed = clean_line(line);
        if trimmed.is_empty() || trimmed.starts_with("SymbolID") {
            continue;
        }
        if trimmed == "}" {
            return None;
        }
        return trimmed.split_whitespace().next().map(str::to_string);
    }
    None
}

fn component_item_names(text: &str) -> Vec<String> {
    let mut stack: Vec<String> = Vec::new();
    let mut names = Vec::new();
    for line in text.lines() {
        let trimmed = clean_line(line);
        if trimmed.is_empty() {
            continue;
        }
        if trimmed == "}" {
            stack.pop();
            continue;
        }
        if let Some(name) = block_start_name(trimmed) {
            stack.push(name);
            continue;
        }
        if stack.last().map(String::as_str) == Some("Components") {
            let name = trimmed.split_whitespace().next().unwrap_or("");
            if !matches!(name, "Type" | "NameID") {
                names.push(strip_quotes(name));
            }
        }
    }
    names
}

fn via_template_names(text: &str) -> Vec<String> {
    let mut stack: Vec<String> = Vec::new();
    let mut names = Vec::new();
    for line in text.lines() {
        let trimmed = clean_line(line);
        if trimmed.is_empty() {
            continue;
        }
        if trimmed == "}" {
            stack.pop();
            continue;
        }
        if let Some(name) = block_start_name(trimmed) {
            stack.push(name);
            continue;
        }
        if stack.last().map(String::as_str) == Some("Via")
            && stack.iter().any(|part| part == "ViaList")
        {
            if let Some(rest) = item_rest(trimmed, "IdName") {
                let values = split_tokens(rest);
                if values.len() >= 2 {
                    names.push(values[1].clone());
                }
            }
        }
    }
    sorted_names(names)
}

fn part_names(text: &str) -> Vec<String> {
    let mut stack: Vec<String> = Vec::new();
    let mut names = Vec::new();
    for line in text.lines() {
        let trimmed = clean_line(line);
        if trimmed.is_empty() {
            continue;
        }
        if trimmed == "}" {
            stack.pop();
            continue;
        }
        if let Some(name) = block_start_name(trimmed) {
            stack.push(name);
            continue;
        }
        if stack.last().map(String::as_str) == Some("PartInfo") {
            if let Some(rest) = item_rest(trimmed, "Name") {
                let values = split_tokens(rest);
                if let Some(value) = values.first() {
                    names.push(value.clone());
                }
            }
        }
    }
    names
}

fn layer_files(root: &Path, layer_names: &[String]) -> Result<Vec<PathBuf>, String> {
    let layer_root = root.join("layers");
    if !layer_root.exists() {
        return Ok(Vec::new());
    }
    if !layer_names.is_empty() {
        return Ok(layer_names
            .iter()
            .map(|name| layer_root.join(format!("{name}.lyr")))
            .filter(|path| path.exists())
            .collect());
    }
    let mut paths = Vec::new();
    for entry in fs::read_dir(&layer_root)
        .map_err(|error| format!("failed to read {}: {error}", layer_root.display()))?
    {
        let entry = entry.map_err(|error| error.to_string())?;
        let path = entry.path();
        if path.extension().and_then(|value| value.to_str()) == Some("lyr") {
            paths.push(path);
        }
    }
    paths.sort();
    Ok(paths)
}

fn clean_line(line: &str) -> &str {
    let trimmed = line.trim();
    if trimmed.starts_with('#') {
        ""
    } else {
        trimmed
    }
}

fn block_start_name(trimmed: &str) -> Option<String> {
    let name = trimmed.strip_suffix('{')?.trim();
    if name.is_empty() {
        None
    } else {
        Some(strip_quotes(name))
    }
}

fn item_rest<'a>(trimmed: &'a str, item_name: &str) -> Option<&'a str> {
    let rest = trimmed.strip_prefix(item_name)?;
    if rest.is_empty() || rest.starts_with(char::is_whitespace) {
        Some(rest.trim())
    } else {
        None
    }
}

fn split_tokens(text: &str) -> Vec<String> {
    let mut tokens = Vec::new();
    let mut buffer = String::new();
    let mut in_quote = false;
    let mut chars = text.chars().peekable();
    while let Some(ch) = chars.next() {
        match ch {
            '"' => {
                in_quote = !in_quote;
            }
            '\\' if in_quote => {
                if let Some(next) = chars.next() {
                    buffer.push(next);
                }
            }
            ch if ch.is_whitespace() && !in_quote => {
                if !buffer.is_empty() {
                    tokens.push(std::mem::take(&mut buffer));
                }
            }
            _ => buffer.push(ch),
        }
    }
    if !buffer.is_empty() {
        tokens.push(buffer);
    }
    tokens
}

fn strip_quotes(value: &str) -> String {
    let trimmed = value.trim();
    if trimmed.len() >= 2 && trimmed.starts_with('"') && trimmed.ends_with('"') {
        trimmed[1..trimmed.len() - 1].replace("\\\"", "\"")
    } else {
        trimmed.to_string()
    }
}

fn sorted_names(mut names: Vec<String>) -> Vec<String> {
    names.sort_by_key(|value| value.to_ascii_lowercase());
    names.dedup();
    names
}

trait ExpandHome {
    fn expand_home(&self) -> PathBuf;
}

impl ExpandHome for Path {
    fn expand_home(&self) -> PathBuf {
        let text = self.to_string_lossy();
        if text == "~" || text.starts_with("~/") {
            if let Some(home) = std::env::var_os("HOME") {
                let mut path = PathBuf::from(home);
                if text.len() > 2 {
                    path.push(&text[2..]);
                }
                return path;
            }
        }
        self.to_path_buf()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture(name: &str) -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../examples/edb_cases")
            .join(name)
    }

    #[test]
    fn compares_public_def_cases_to_standard_auroradb_names() {
        let cases = [
            ("fpc.def", "fpc_auroradb", 2, 29, 1, 2, 1),
            ("kb.def", "kb_auroradb", 4, 34, 7, 57, 23),
            ("mb.def", " mb_auroradb", 10, 1049, 16, 2207, 257),
        ];
        for (def_name, auroradb_name, metal_layers, nets, vias, components, parts) in cases {
            let comparison =
                compare_def_to_auroradb(&fixture(def_name), &fixture(auroradb_name)).unwrap();
            assert_eq!(
                comparison.auroradb.metal_layer_count, metal_layers,
                "{def_name}"
            );
            assert_eq!(comparison.auroradb.net_count, nets, "{def_name}");
            assert_eq!(comparison.auroradb.via_template_count, vias, "{def_name}");
            assert_eq!(
                comparison.auroradb.component_count, components,
                "{def_name}"
            );
            assert_eq!(comparison.auroradb.part_count, parts, "{def_name}");
            for check_name in [
                "metal_layer_names",
                "via_template_names_in_padstacks",
                "net_names_in_binary_string_table",
                "component_names_in_placements",
                "part_names_in_component_placement_candidates",
            ] {
                let check = comparison
                    .checks
                    .iter()
                    .find(|check| check.name == check_name)
                    .unwrap();
                assert_eq!(check.status, "pass", "{def_name} {check_name}");
            }
        }
    }
}
