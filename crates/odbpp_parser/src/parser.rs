use crate::model::{
    Component, ComponentPin, ContourVertex, DrillLayerTools, DrillTool, Feature, LayerFeatures,
    LineRecord, Matrix, MatrixRow, Net, NetFeatureRef, NetPinRef, PackageBounds, PackageDefinition,
    PackagePin, PackageShape, Point, Profile, Step, Summary, SurfaceContour, SymbolDefinition,
};
use rayon::prelude::*;
use std::borrow::Cow;
use std::collections::{BTreeMap, HashMap};

#[derive(Debug, Clone, Default)]
pub struct ParseOptions {
    pub selected_step: Option<String>,
    pub include_details: bool,
}

#[derive(Debug, Clone, Default)]
pub struct ParsedOdb {
    pub matrix: Option<Matrix>,
    pub steps: Vec<Step>,
    pub symbols: Option<Vec<SymbolDefinition>>,
    pub drill_tools: Option<Vec<DrillLayerTools>>,
    pub packages: Option<Vec<PackageDefinition>>,
    pub layers: Option<Vec<LayerFeatures>>,
    pub components: Option<Vec<Component>>,
    pub nets: Option<Vec<Net>>,
    pub summary: Summary,
    pub selected_step: Option<String>,
    pub diagnostics: Vec<String>,
}

#[derive(Debug, Clone)]
struct NamedFileRef<'a> {
    name: String,
    bytes: &'a [u8],
}

#[derive(Debug, Clone)]
struct PathFileRef<'a> {
    path: String,
    bytes: &'a [u8],
}

#[derive(Debug, Default)]
struct IndexedStepFiles<'a> {
    profile: Option<&'a [u8]>,
    eda_data: Option<&'a [u8]>,
    layer_features: Vec<NamedFileRef<'a>>,
    layer_attributes: HashMap<String, &'a [u8]>,
    layer_tools: Vec<NamedFileRef<'a>>,
    components: Vec<NamedFileRef<'a>>,
    net_files: Vec<PathFileRef<'a>>,
}

#[derive(Debug, Default)]
struct IndexedFiles<'a> {
    matrix: Option<&'a [u8]>,
    steps: BTreeMap<String, IndexedStepFiles<'a>>,
    symbol_features: Vec<NamedFileRef<'a>>,
}

pub fn parse_odb_files(files: &BTreeMap<String, Vec<u8>>, options: &ParseOptions) -> ParsedOdb {
    let mut diagnostics = Vec::new();
    let index = build_file_index(files);
    let matrix = index
        .matrix
        .and_then(|bytes| text_from_bytes(bytes, "matrix/matrix", &mut diagnostics))
        .map(|text| parse_matrix(&text));

    if matrix.is_none() {
        diagnostics
            .push("Missing matrix/matrix; layer stack information is incomplete".to_string());
    }

    let step_names: Vec<String> = index.steps.keys().cloned().collect();
    let selected_step = select_step(
        &step_names,
        options.selected_step.as_deref(),
        &mut diagnostics,
    );
    let mut steps = Vec::new();
    for name in &step_names {
        let profile = index
            .steps
            .get(name)
            .and_then(|step_files| step_files.profile)
            .and_then(|bytes| {
                text_from_bytes(bytes, &format!("steps/{name}/profile"), &mut diagnostics)
            })
            .map(|text| parse_profile(&text));
        steps.push(Step {
            name: name.clone(),
            profile,
        });
    }

    let (layers, drill_tools, packages, components, nets) = if options.include_details {
        if let Some(step) = selected_step.as_deref() {
            let step_files = index.steps.get(step);
            (
                Some(parse_layer_features(step, step_files, &mut diagnostics)),
                Some(parse_layer_tools(step, step_files, &mut diagnostics)),
                Some(parse_package_definitions(
                    step,
                    step_files,
                    &mut diagnostics,
                )),
                Some(parse_components(step, step_files, &mut diagnostics)),
                Some(parse_nets(step, step_files, &mut diagnostics)),
            )
        } else {
            (
                Some(Vec::new()),
                Some(Vec::new()),
                Some(Vec::new()),
                Some(Vec::new()),
                Some(Vec::new()),
            )
        }
    } else {
        (None, None, None, None, None)
    };
    let symbols = if options.include_details {
        Some(parse_symbol_definitions(
            &index.symbol_features,
            &mut diagnostics,
        ))
    } else {
        None
    };

    let summary = summarize(
        matrix.as_ref(),
        &steps,
        symbols.as_deref(),
        drill_tools.as_deref(),
        packages.as_deref(),
        layers.as_deref(),
        components.as_deref(),
        nets.as_deref(),
        diagnostics.len(),
    );

    ParsedOdb {
        matrix,
        steps,
        symbols,
        drill_tools,
        packages,
        layers,
        components,
        nets,
        summary,
        selected_step,
        diagnostics,
    }
}

fn parse_matrix(text: &str) -> Matrix {
    let mut rows = Vec::new();
    let mut inside_row = false;
    let mut current = BTreeMap::new();

    for line in text.lines() {
        let cleaned = strip_comment(line).trim();
        if cleaned.is_empty() {
            continue;
        }
        if (starts_with_ignore_ascii_case(cleaned, "ROW")
            || starts_with_ignore_ascii_case(cleaned, "LAYER"))
            && cleaned.contains('{')
        {
            inside_row = true;
            current.clear();
            continue;
        }
        if inside_row && cleaned.starts_with('}') {
            rows.push(matrix_row_from_fields(&current));
            current.clear();
            inside_row = false;
            continue;
        }
        if !inside_row {
            continue;
        }
        if let Some((key, value)) = parse_key_value(cleaned) {
            current.insert(key.to_ascii_uppercase(), unquote(value));
        }
    }

    Matrix { rows }
}

fn parse_profile(text: &str) -> Profile {
    let mut units = None;
    let mut records = Vec::new();
    for (index, line) in text.lines().enumerate() {
        let cleaned = strip_comment(line).trim();
        if cleaned.is_empty() {
            continue;
        }
        if let Some(value) = parse_units(cleaned) {
            units = Some(value);
        }
        let tokens = split_tokens(cleaned);
        if tokens.is_empty() {
            continue;
        }
        records.push(LineRecord {
            line_number: index + 1,
            kind: tokens[0].clone(),
            tokens,
        });
    }
    Profile { units, records }
}

fn parse_layer_features(
    step: &str,
    step_files: Option<&IndexedStepFiles<'_>>,
    diagnostics: &mut Vec<String>,
) -> Vec<LayerFeatures> {
    let Some(step_files) = step_files else {
        return Vec::new();
    };
    let results: Vec<(LayerFeatures, Vec<String>)> = step_files
        .layer_features
        .par_iter()
        .filter_map(|layer_file| {
            let path = format!("steps/{step}/layers/{}/features", layer_file.name);
            let mut file_diagnostics = Vec::new();
            let text = text_from_bytes(layer_file.bytes, &path, &mut file_diagnostics)?;
            let layer_attributes =
                layer_attributes_for(step, step_files, &layer_file.name, &mut file_diagnostics);
            Some((
                parse_feature_file(step, &layer_file.name, &text, layer_attributes),
                file_diagnostics,
            ))
        })
        .collect();
    let mut layers = Vec::with_capacity(results.len());
    for (layer, file_diagnostics) in results {
        diagnostics.extend(file_diagnostics);
        layers.push(layer);
    }
    layers.sort_by(|left, right| left.layer_name.cmp(&right.layer_name));
    layers
}

fn layer_attributes_for(
    step: &str,
    step_files: &IndexedStepFiles<'_>,
    layer_name: &str,
    diagnostics: &mut Vec<String>,
) -> BTreeMap<String, String> {
    let path = format!("steps/{step}/layers/{layer_name}/attrlist");
    let Some(bytes) = step_files.layer_attributes.get(layer_name) else {
        return BTreeMap::new();
    };
    let Some(text) = text_from_bytes(bytes, &path, diagnostics) else {
        return BTreeMap::new();
    };
    parse_attribute_file(&text)
}

fn parse_attribute_file(text: &str) -> BTreeMap<String, String> {
    let mut attributes = BTreeMap::new();
    for line in text.lines() {
        let cleaned = strip_comment(line).trim();
        if cleaned.is_empty() {
            continue;
        }
        if let Some((key, value)) = parse_key_value(cleaned) {
            attributes.insert(key.to_string(), unquote(value));
        }
    }
    attributes
}

fn parse_symbol_definitions(
    symbol_files: &[NamedFileRef<'_>],
    diagnostics: &mut Vec<String>,
) -> Vec<SymbolDefinition> {
    let results: Vec<(SymbolDefinition, Vec<String>)> = symbol_files
        .par_iter()
        .filter_map(|symbol_file| {
            let path = format!("symbols/{}/features", symbol_file.name);
            let mut file_diagnostics = Vec::new();
            let text = text_from_bytes(symbol_file.bytes, &path, &mut file_diagnostics)?;
            let layer_features = parse_feature_file("", &symbol_file.name, &text, BTreeMap::new());
            Some((
                SymbolDefinition {
                    name: symbol_file.name.clone(),
                    units: layer_features.units,
                    features: layer_features.features,
                },
                file_diagnostics,
            ))
        })
        .collect();
    let mut symbols = Vec::with_capacity(results.len());
    for (symbol, file_diagnostics) in results {
        diagnostics.extend(file_diagnostics);
        symbols.push(symbol);
    }
    symbols.sort_by(|left, right| left.name.cmp(&right.name));
    symbols
}

fn parse_layer_tools(
    step: &str,
    step_files: Option<&IndexedStepFiles<'_>>,
    diagnostics: &mut Vec<String>,
) -> Vec<DrillLayerTools> {
    let Some(step_files) = step_files else {
        return Vec::new();
    };
    let results: Vec<(DrillLayerTools, Vec<String>)> = step_files
        .layer_tools
        .par_iter()
        .filter_map(|layer_file| {
            let path = format!("steps/{step}/layers/{}/tools", layer_file.name);
            let mut file_diagnostics = Vec::new();
            let text = text_from_bytes(layer_file.bytes, &path, &mut file_diagnostics)?;
            Some((
                parse_tools_file(step, &layer_file.name, &text),
                file_diagnostics,
            ))
        })
        .collect();
    let mut layers = Vec::with_capacity(results.len());
    for (layer, file_diagnostics) in results {
        diagnostics.extend(file_diagnostics);
        layers.push(layer);
    }
    layers.sort_by(|left, right| left.layer_name.cmp(&right.layer_name));
    layers
}

fn parse_package_definitions(
    step: &str,
    step_files: Option<&IndexedStepFiles<'_>>,
    diagnostics: &mut Vec<String>,
) -> Vec<PackageDefinition> {
    let path = format!("steps/{step}/eda/data");
    let Some(bytes) = step_files.and_then(|step_files| step_files.eda_data) else {
        return Vec::new();
    };
    let Some(text) = text_from_bytes(bytes, &path, diagnostics) else {
        return Vec::new();
    };
    parse_package_file(step, &text)
}

fn parse_components(
    step: &str,
    step_files: Option<&IndexedStepFiles<'_>>,
    diagnostics: &mut Vec<String>,
) -> Vec<Component> {
    let Some(step_files) = step_files else {
        return Vec::new();
    };
    let results: Vec<(Vec<Component>, Vec<String>)> = step_files
        .components
        .par_iter()
        .filter_map(|component_file| {
            let path = format!("steps/{step}/layers/{}/components", component_file.name);
            let mut file_diagnostics = Vec::new();
            let text = text_from_bytes(component_file.bytes, &path, &mut file_diagnostics)?;
            Some((
                parse_component_file(step, &component_file.name, &text),
                file_diagnostics,
            ))
        })
        .collect();
    let mut components = Vec::new();
    for (mut layer_components, file_diagnostics) in results {
        diagnostics.extend(file_diagnostics);
        components.append(&mut layer_components);
    }
    components
}

fn parse_nets(
    step: &str,
    step_files: Option<&IndexedStepFiles<'_>>,
    diagnostics: &mut Vec<String>,
) -> Vec<Net> {
    let Some(step_files) = step_files else {
        return Vec::new();
    };
    let results: Vec<(Vec<Net>, Vec<String>)> = step_files
        .net_files
        .par_iter()
        .filter_map(|net_file| {
            let mut file_diagnostics = Vec::new();
            let text = text_from_bytes(net_file.bytes, &net_file.path, &mut file_diagnostics)?;
            Some((
                parse_net_file(step, &net_file.path, &text),
                file_diagnostics,
            ))
        })
        .collect();

    let mut nets = Vec::new();
    for (mut file_nets, file_diagnostics) in results {
        diagnostics.extend(file_diagnostics);
        nets.append(&mut file_nets);
    }

    merge_nets(nets)
}

fn parse_feature_file(
    step_name: &str,
    layer_name: &str,
    text: &str,
    layer_attributes: BTreeMap<String, String>,
) -> LayerFeatures {
    let mut units = None;
    let mut symbols = BTreeMap::new();
    let mut attributes = BTreeMap::new();
    let mut text_strings = BTreeMap::new();
    let mut features = Vec::new();
    let mut current_surface: Option<Feature> = None;
    let mut current_contour: Option<SurfaceContour> = None;

    for (index, line) in text.lines().enumerate() {
        let cleaned = strip_comment(line).trim();
        if cleaned.is_empty() {
            continue;
        }
        if let Some(value) = parse_units(cleaned) {
            units = Some(value);
            continue;
        }
        if parse_lookup(cleaned, '$', &mut symbols)
            || parse_lookup(cleaned, '@', &mut attributes)
            || parse_lookup(cleaned, '&', &mut text_strings)
        {
            continue;
        }
        let tokens = split_tokens(cleaned);
        if tokens.is_empty() {
            continue;
        }
        let kind = tokens[0].clone();
        if kind == "S" {
            push_surface_contour(&mut current_surface, &mut current_contour);
            push_surface_feature(&mut features, &mut current_surface);
            current_surface = Some(feature_from_tokens(
                features.len(),
                index + 1,
                tokens,
                cleaned,
            ));
            continue;
        }
        if kind == "OB" {
            push_surface_contour(&mut current_surface, &mut current_contour);
            current_contour = contour_from_tokens(&tokens);
            continue;
        }
        if matches!(kind.as_str(), "OS" | "OC") {
            if let Some(contour) = current_contour.as_mut() {
                if let Some(vertex) = contour_vertex_from_tokens(&tokens) {
                    contour.vertices.push(vertex);
                }
            }
            continue;
        }
        if kind == "OE" {
            push_surface_contour(&mut current_surface, &mut current_contour);
            continue;
        }
        if kind == "SE" {
            push_surface_contour(&mut current_surface, &mut current_contour);
            push_surface_feature(&mut features, &mut current_surface);
            continue;
        }
        if matches!(kind.as_str(), "P" | "L" | "A" | "S" | "T" | "B") {
            push_surface_contour(&mut current_surface, &mut current_contour);
            push_surface_feature(&mut features, &mut current_surface);
            features.push(feature_from_tokens(
                features.len(),
                index + 1,
                tokens,
                cleaned,
            ));
        }
    }
    push_surface_contour(&mut current_surface, &mut current_contour);
    push_surface_feature(&mut features, &mut current_surface);

    LayerFeatures {
        step_name: step_name.to_string(),
        layer_name: layer_name.to_string(),
        units,
        layer_attributes,
        symbols,
        attributes,
        text_strings,
        features,
    }
}

fn parse_component_file(step_name: &str, layer_name: &str, text: &str) -> Vec<Component> {
    let mut components = Vec::new();
    let mut current: Option<Component> = None;
    let mut pending_component_index = None;
    for (index, line) in text.lines().enumerate() {
        if let Some(component_index) = component_index_comment(line) {
            pending_component_index = Some(component_index);
            continue;
        }
        let cleaned = strip_comment(line).trim();
        if cleaned.is_empty() {
            continue;
        }
        let tokens = split_tokens(cleaned);
        if tokens.is_empty() {
            continue;
        }
        let record_type = tokens[0].clone();
        match record_type.as_str() {
            "CMP" | "COMP" => {
                if let Some(component) = current.take() {
                    components.push(component);
                }
                current = Some(component_from_tokens(
                    step_name,
                    layer_name,
                    index + 1,
                    pending_component_index.take(),
                    record_type,
                    tokens,
                ));
            }
            "TOP" | "BOT" => {
                if let Some(component) = current.as_mut() {
                    component
                        .pins
                        .push(component_pin_from_tokens(index + 1, record_type, tokens));
                }
            }
            "PRP" => {
                if let Some(component) = current.as_mut() {
                    if let Some((key, value)) = property_from_tokens(&tokens) {
                        if key.eq_ignore_ascii_case("PACKAGE_NAME") {
                            component.package_name = Some(value.clone());
                        } else if key.eq_ignore_ascii_case("PART_NUMBER")
                            && component.part_name.is_none()
                        {
                            component.part_name = Some(value.clone());
                        }
                        component.properties.insert(key, value);
                    }
                }
            }
            _ => {}
        }
    }
    if let Some(component) = current {
        components.push(component);
    }
    components
}

fn parse_net_file(step_name: &str, source_file: &str, text: &str) -> Vec<Net> {
    let mut nets = Vec::new();
    let mut current: Option<Net> = None;
    let mut layer_names: Vec<String> = Vec::new();
    let mut current_subnet_type: Option<String> = None;
    let mut current_pin_ref: Option<NetPinRef> = None;
    for (index, line) in text.lines().enumerate() {
        let cleaned = strip_comment(line).trim();
        if cleaned.is_empty() {
            continue;
        }
        let tokens = split_tokens(cleaned);
        if tokens.is_empty() {
            continue;
        }
        if tokens[0] == "LYR" {
            layer_names = tokens.iter().skip(1).cloned().collect();
            continue;
        }
        if let Some(name) = net_name_from_tokens(&tokens) {
            if let Some(net) = current.take() {
                nets.push(net);
            }
            current = Some(Net {
                step_name: step_name.to_string(),
                name,
                source_file: source_file.to_string(),
                line_number: index + 1,
                tokens,
                feature_refs: Vec::new(),
                pin_refs: Vec::new(),
            });
            continue;
        }
        if let Some(net) = current.as_mut() {
            if let Some(pin_ref) = pin_ref_from_tokens(index + 1, &tokens) {
                current_subnet_type = Some("PIN".to_string());
                current_pin_ref = Some(pin_ref.clone());
                net.pin_refs.push(pin_ref);
                continue;
            }
            if tokens[0] == "SNT" {
                current_subnet_type = tokens.get(1).cloned();
                current_pin_ref = None;
                continue;
            }
            if let Some(feature_ref) = feature_ref_from_tokens(
                index + 1,
                &tokens,
                &layer_names,
                current_subnet_type.as_deref(),
                current_pin_ref.as_ref(),
            ) {
                net.feature_refs.push(feature_ref);
            }
        }
    }
    if let Some(net) = current {
        nets.push(net);
    }
    nets
}

fn parse_tools_file(step_name: &str, layer_name: &str, text: &str) -> DrillLayerTools {
    let mut units = None;
    let mut raw_fields = BTreeMap::new();
    let mut tools = Vec::new();
    let mut inside_tool = false;
    let mut current = BTreeMap::new();

    for line in text.lines() {
        let cleaned = strip_comment(line).trim();
        if cleaned.is_empty() {
            continue;
        }
        if let Some(value) = parse_units(cleaned) {
            units = Some(value);
            continue;
        }
        if starts_with_ignore_ascii_case(cleaned, "TOOLS") && cleaned.contains('{') {
            inside_tool = true;
            current.clear();
            continue;
        }
        if inside_tool && cleaned.starts_with('}') {
            tools.push(drill_tool_from_fields(&current));
            current.clear();
            inside_tool = false;
            continue;
        }
        if inside_tool {
            if let Some((key, value)) = parse_key_value(cleaned) {
                current.insert(key.to_ascii_uppercase(), unquote(value));
            }
        } else if let Some((key, value)) = parse_key_value(cleaned) {
            raw_fields.insert(key.to_ascii_uppercase(), unquote(value));
        }
    }

    DrillLayerTools {
        step_name: step_name.to_string(),
        layer_name: layer_name.to_string(),
        units,
        thickness: field(&raw_fields, &["THICKNESS"]).and_then(parse_f64_value),
        user_params: field(&raw_fields, &["USER_PARAMS"]).map(ToOwned::to_owned),
        raw_fields,
        tools,
    }
}

fn parse_package_file(step_name: &str, text: &str) -> Vec<PackageDefinition> {
    let mut packages = Vec::new();
    let mut current: Option<PackageDefinition> = None;
    let mut pending_package_index = None;
    let mut current_surface_shape: Option<PackageShape> = None;
    let mut current_contour: Option<SurfaceContour> = None;

    for (index, line) in text.lines().enumerate() {
        if let Some(package_index) = package_index_comment(line) {
            pending_package_index = Some(package_index);
            continue;
        }
        let cleaned = strip_comment(line).trim();
        if cleaned.is_empty() {
            continue;
        }
        let tokens = split_tokens(cleaned);
        if tokens.is_empty() {
            continue;
        }
        let record_type = tokens[0].as_str();
        match record_type {
            "PKG" => {
                push_package_surface_shape(
                    &mut current,
                    &mut current_surface_shape,
                    &mut current_contour,
                );
                if let Some(package) = current.take() {
                    packages.push(package);
                }
                current = Some(package_from_tokens(
                    step_name,
                    index + 1,
                    pending_package_index.take(),
                    tokens,
                    cleaned,
                ));
            }
            "PRP" => {
                if let Some(package) = current.as_mut() {
                    if let Some((key, value)) = property_from_tokens(&tokens) {
                        if key.eq_ignore_ascii_case("PACKAGE_NAME") && package.name.is_none() {
                            package.name = Some(value.clone());
                        }
                        package.properties.insert(key, value);
                    }
                }
            }
            "PIN" => {
                push_package_surface_shape(
                    &mut current,
                    &mut current_surface_shape,
                    &mut current_contour,
                );
                if let Some(package) = current.as_mut() {
                    package
                        .pins
                        .push(package_pin_from_tokens(index + 1, tokens));
                }
            }
            "RC" | "CR" | "SQ" => {
                push_package_surface_shape(
                    &mut current,
                    &mut current_surface_shape,
                    &mut current_contour,
                );
                if let Some(shape) = package_shape_from_tokens(index + 1, tokens) {
                    push_package_shape(&mut current, shape);
                }
            }
            "OB" => {
                push_package_surface_shape(
                    &mut current,
                    &mut current_surface_shape,
                    &mut current_contour,
                );
                current_surface_shape = Some(package_surface_shape_from_tokens(index + 1, tokens));
            }
            "OS" | "OC" => {
                if let Some(shape) = current_surface_shape.as_mut() {
                    if shape.contours.is_empty() {
                        shape.contours.push(SurfaceContour::default());
                    }
                    if let Some(vertex) = contour_vertex_from_tokens(&tokens) {
                        if let Some(contour) = shape.contours.last_mut() {
                            contour.vertices.push(vertex);
                        }
                    }
                } else if let Some(contour) = current_contour.as_mut() {
                    if let Some(vertex) = contour_vertex_from_tokens(&tokens) {
                        contour.vertices.push(vertex);
                    }
                }
            }
            "OE" => {
                push_package_surface_contour(&mut current_surface_shape, &mut current_contour);
            }
            "CE" => {
                push_package_surface_shape(
                    &mut current,
                    &mut current_surface_shape,
                    &mut current_contour,
                );
            }
            _ => {}
        }
    }
    push_package_surface_shape(
        &mut current,
        &mut current_surface_shape,
        &mut current_contour,
    );
    if let Some(package) = current {
        packages.push(package);
    }
    packages
}

fn summarize(
    matrix: Option<&Matrix>,
    steps: &[Step],
    symbols: Option<&[SymbolDefinition]>,
    drill_tools: Option<&[DrillLayerTools]>,
    packages: Option<&[PackageDefinition]>,
    layers: Option<&[LayerFeatures]>,
    components: Option<&[Component]>,
    nets: Option<&[Net]>,
    diagnostic_count: usize,
) -> Summary {
    let mut summary = Summary {
        step_count: steps.len(),
        step_names: steps.iter().map(|step| step.name.clone()).collect(),
        profile_record_count: steps
            .iter()
            .map(|step| {
                step.profile
                    .as_ref()
                    .map(|profile| profile.records.len())
                    .unwrap_or(0)
            })
            .sum(),
        diagnostic_count,
        ..Summary::default()
    };

    if let Some(matrix) = matrix {
        summary.layer_count = matrix.rows.len();
        for row in &matrix.rows {
            if let Some(name) = &row.name {
                summary.layer_names.push(name.clone());
            }
            let context = row
                .context
                .as_deref()
                .unwrap_or_default()
                .to_ascii_lowercase();
            let layer_type = row
                .layer_type
                .as_deref()
                .unwrap_or_default()
                .to_ascii_lowercase();
            if context == "board" {
                summary.board_layer_count += 1;
            }
            if layer_type == "signal" {
                summary.signal_layer_count += 1;
            }
            if layer_type == "component" {
                summary.component_layer_count += 1;
            }
        }
    }

    if let Some(layers) = layers {
        summary.feature_layer_count = layers.len();
        summary.feature_count = layers.iter().map(|layer| layer.features.len()).sum();
    }
    if let Some(symbols) = symbols {
        summary.symbol_count = symbols.len();
    }
    if let Some(drill_tools) = drill_tools {
        summary.drill_tool_count = drill_tools.iter().map(|layer| layer.tools.len()).sum();
    }
    if let Some(packages) = packages {
        summary.package_count = packages.len();
    }
    if let Some(components) = components {
        summary.component_count = components.len();
    }
    if let Some(nets) = nets {
        summary.net_count = nets.len();
        summary.net_names = nets.iter().map(|net| net.name.clone()).collect();
        summary
            .net_names
            .sort_by_key(|name| name.to_ascii_lowercase());
    }
    summary
}

fn build_file_index<'a>(files: &'a BTreeMap<String, Vec<u8>>) -> IndexedFiles<'a> {
    let mut index = IndexedFiles::default();

    for (path, bytes) in files {
        let bytes = bytes.as_slice();
        if path == "matrix/matrix" {
            index.matrix = Some(bytes);
            continue;
        }
        if let Some(name) = symbol_feature_name(path) {
            index.symbol_features.push(NamedFileRef { name, bytes });
            continue;
        }
        let Some(rest) = path.strip_prefix("steps/") else {
            continue;
        };
        let Some((step_name, step_rest)) = rest.split_once('/') else {
            continue;
        };
        if step_name.is_empty() {
            continue;
        }

        let step_files = index
            .steps
            .entry(step_name.to_string())
            .or_insert_with(IndexedStepFiles::default);

        if step_rest == "profile" {
            step_files.profile = Some(bytes);
            continue;
        }
        if step_rest == "eda/data" {
            step_files.eda_data = Some(bytes);
            step_files.net_files.push(PathFileRef {
                path: path.clone(),
                bytes,
            });
            continue;
        }
        if step_rest.starts_with("netlists/") {
            step_files.net_files.push(PathFileRef {
                path: path.clone(),
                bytes,
            });
            continue;
        }
        let Some(layer_rest) = step_rest.strip_prefix("layers/") else {
            continue;
        };
        let Some((layer_name, layer_file)) = layer_rest.split_once('/') else {
            continue;
        };
        if layer_name.is_empty() || layer_file.contains('/') {
            continue;
        }
        match layer_file {
            "features" => step_files.layer_features.push(NamedFileRef {
                name: layer_name.to_string(),
                bytes,
            }),
            "attrlist" => {
                step_files
                    .layer_attributes
                    .insert(layer_name.to_string(), bytes);
            }
            "tools" => step_files.layer_tools.push(NamedFileRef {
                name: layer_name.to_string(),
                bytes,
            }),
            "components" => step_files.components.push(NamedFileRef {
                name: layer_name.to_string(),
                bytes,
            }),
            _ => {}
        }
    }

    index
}

fn symbol_feature_name(path: &str) -> Option<String> {
    path.strip_prefix("symbols/")
        .and_then(|value| value.strip_suffix("/features"))
        .map(|value| value.trim_matches('/').to_string())
}

fn select_step(
    step_names: &[String],
    requested: Option<&str>,
    diagnostics: &mut Vec<String>,
) -> Option<String> {
    if let Some(requested) = requested {
        if step_names.iter().any(|step| step == requested) {
            return Some(requested.to_string());
        }
        diagnostics.push(format!(
            "Requested step {requested:?} was not found; available steps: {}",
            step_names.join(", ")
        ));
    }
    step_names.first().cloned()
}

fn matrix_row_from_fields(fields: &BTreeMap<String, String>) -> MatrixRow {
    MatrixRow {
        row: field(fields, &["ROW", "ID", "COL"]).and_then(|value| value.parse::<i64>().ok()),
        name: field(fields, &["NAME"]).map(ToOwned::to_owned),
        context: field(fields, &["CONTEXT"]).map(ToOwned::to_owned),
        layer_type: field(fields, &["TYPE"]).map(ToOwned::to_owned),
        polarity: field(fields, &["POLARITY"]).map(ToOwned::to_owned),
        side: field(fields, &["SIDE"]).map(ToOwned::to_owned),
        start_name: field(fields, &["START_NAME", "START"]).map(ToOwned::to_owned),
        end_name: field(fields, &["END_NAME", "END"]).map(ToOwned::to_owned),
        raw_fields: fields.clone(),
    }
}

fn drill_tool_from_fields(fields: &BTreeMap<String, String>) -> DrillTool {
    DrillTool {
        number: field(fields, &["NUM", "NUMBER"]).and_then(|value| value.parse::<i64>().ok()),
        tool_type: field(fields, &["TYPE"]).map(ToOwned::to_owned),
        type2: field(fields, &["TYPE2"]).map(ToOwned::to_owned),
        finish_size: field(fields, &["FINISH_SIZE", "FINISHED_SIZE"]).and_then(parse_f64_value),
        drill_size: field(fields, &["DRILL_SIZE", "SIZE"]).and_then(parse_f64_value),
        raw_fields: fields.clone(),
    }
}

fn package_from_tokens(
    step_name: &str,
    line_number: usize,
    package_index: Option<i64>,
    tokens: Vec<String>,
    raw_line: &str,
) -> PackageDefinition {
    let attributes = record_attributes(raw_line);
    PackageDefinition {
        step_name: step_name.to_string(),
        line_number,
        package_index,
        name: tokens.get(1).map(|value| clean_scalar_token(value)),
        feature_id: attributes
            .get("ID")
            .cloned()
            .or_else(|| token_attribute(&tokens, "ID")),
        pitch: tokens.get(2).and_then(|value| parse_f64_value(value)),
        bounds: package_bounds_from_tokens(&tokens),
        properties: BTreeMap::new(),
        outlines: Vec::new(),
        pins: Vec::new(),
        tokens,
    }
}

fn package_bounds_from_tokens(tokens: &[String]) -> Option<PackageBounds> {
    Some(PackageBounds {
        min: Point {
            x: tokens.get(3).and_then(|value| parse_f64_value(value))?,
            y: tokens.get(4).and_then(|value| parse_f64_value(value))?,
        },
        max: Point {
            x: tokens.get(5).and_then(|value| parse_f64_value(value))?,
            y: tokens.get(6).and_then(|value| parse_f64_value(value))?,
        },
    })
}

fn package_pin_from_tokens(line_number: usize, tokens: Vec<String>) -> PackagePin {
    PackagePin {
        line_number,
        name: tokens.get(1).map(|value| clean_scalar_token(value)),
        side: tokens.get(2).map(|value| clean_scalar_token(value)),
        position: point_at(&tokens, 3, 4),
        rotation: tokens.get(5).and_then(|value| parse_f64_value(value)),
        electrical_type: tokens.get(6).map(|value| clean_scalar_token(value)),
        mount_type: tokens.get(7).map(|value| clean_scalar_token(value)),
        feature_id: token_attribute(&tokens, "ID"),
        shapes: Vec::new(),
        tokens,
    }
}

fn package_shape_from_tokens(line_number: usize, tokens: Vec<String>) -> Option<PackageShape> {
    let kind = tokens.first()?.clone();
    match kind.as_str() {
        "RC" => {
            let x = tokens.get(1).and_then(|value| parse_f64_value(value))?;
            let y = tokens.get(2).and_then(|value| parse_f64_value(value))?;
            let width = tokens.get(3).and_then(|value| parse_f64_value(value))?;
            let height = tokens.get(4).and_then(|value| parse_f64_value(value))?;
            Some(PackageShape {
                line_number,
                kind,
                tokens,
                center: Some(Point {
                    x: x + width / 2.0,
                    y: y + height / 2.0,
                }),
                width: Some(width),
                height: Some(height),
                ..PackageShape::default()
            })
        }
        "CR" => {
            let center = point_at(&tokens, 1, 2)?;
            let radius = tokens.get(3).and_then(|value| parse_f64_value(value))?;
            Some(PackageShape {
                line_number,
                kind,
                tokens,
                center: Some(center),
                radius: Some(radius),
                ..PackageShape::default()
            })
        }
        "SQ" => {
            let center = point_at(&tokens, 1, 2)?;
            let size = tokens.get(3).and_then(|value| parse_f64_value(value))?;
            Some(PackageShape {
                line_number,
                kind,
                tokens,
                center: Some(center),
                size: Some(size),
                ..PackageShape::default()
            })
        }
        _ => None,
    }
}

fn package_surface_shape_from_tokens(line_number: usize, tokens: Vec<String>) -> PackageShape {
    let mut shape = PackageShape {
        line_number,
        kind: "CT".to_string(),
        tokens: tokens.clone(),
        ..PackageShape::default()
    };
    if let Some(contour) = contour_from_tokens(&tokens) {
        shape.contours.push(contour);
    }
    shape.center = package_shape_center_from_contours(&shape.contours);
    shape
}

fn package_shape_center_from_contours(contours: &[SurfaceContour]) -> Option<Point> {
    let mut min_x = f64::INFINITY;
    let mut min_y = f64::INFINITY;
    let mut max_x = f64::NEG_INFINITY;
    let mut max_y = f64::NEG_INFINITY;
    let mut found = false;
    for contour in contours {
        for vertex in &contour.vertices {
            found = true;
            min_x = min_x.min(vertex.point.x);
            min_y = min_y.min(vertex.point.y);
            max_x = max_x.max(vertex.point.x);
            max_y = max_y.max(vertex.point.y);
        }
    }
    if !found {
        return None;
    }
    Some(Point {
        x: (min_x + max_x) / 2.0,
        y: (min_y + max_y) / 2.0,
    })
}

fn push_package_shape(current: &mut Option<PackageDefinition>, shape: PackageShape) {
    let Some(package) = current.as_mut() else {
        return;
    };
    if let Some(pin) = package.pins.last_mut() {
        pin.shapes.push(shape);
    } else {
        package.outlines.push(shape);
    }
}

fn push_package_surface_contour(
    current_shape: &mut Option<PackageShape>,
    current_contour: &mut Option<SurfaceContour>,
) {
    let Some(contour) = current_contour.take() else {
        return;
    };
    if let Some(shape) = current_shape.as_mut() {
        shape.contours.push(contour);
        shape.center = package_shape_center_from_contours(&shape.contours);
    }
}

fn push_package_surface_shape(
    current: &mut Option<PackageDefinition>,
    current_shape: &mut Option<PackageShape>,
    current_contour: &mut Option<SurfaceContour>,
) {
    push_package_surface_contour(current_shape, current_contour);
    let Some(mut shape) = current_shape.take() else {
        return;
    };
    shape.center = package_shape_center_from_contours(&shape.contours);
    push_package_shape(current, shape);
}

fn push_surface_contour(
    current_surface: &mut Option<Feature>,
    current_contour: &mut Option<SurfaceContour>,
) {
    let Some(contour) = current_contour.take() else {
        return;
    };
    if let Some(surface) = current_surface.as_mut() {
        surface.contours.push(contour);
    }
}

fn push_surface_feature(features: &mut Vec<Feature>, current_surface: &mut Option<Feature>) {
    let Some(mut surface) = current_surface.take() else {
        return;
    };
    surface.feature_index = features.len();
    features.push(surface);
}

fn contour_from_tokens(tokens: &[String]) -> Option<SurfaceContour> {
    let mut contour = SurfaceContour {
        polarity: tokens.get(3).cloned(),
        vertices: Vec::new(),
    };
    if let Some(point) = point_at(tokens, 1, 2) {
        contour.vertices.push(ContourVertex {
            record_type: tokens[0].clone(),
            point,
            center: None,
            clockwise: None,
        });
    }
    Some(contour)
}

fn contour_vertex_from_tokens(tokens: &[String]) -> Option<ContourVertex> {
    let record_type = tokens.first()?.clone();
    let point = point_at(tokens, 1, 2)?;
    let (center, clockwise) = if record_type == "OC" {
        (
            point_at(tokens, 3, 4),
            tokens.get(5).map(|value| value.eq_ignore_ascii_case("Y")),
        )
    } else {
        (None, None)
    };
    Some(ContourVertex {
        record_type,
        point,
        center,
        clockwise,
    })
}

fn feature_from_tokens(
    feature_index: usize,
    line_number: usize,
    tokens: Vec<String>,
    raw_line: &str,
) -> Feature {
    let kind = tokens.first().cloned().unwrap_or_default();
    let start = point_at(&tokens, 1, 2);
    let (end, center, symbol, polarity) = match kind.as_str() {
        "P" => (
            None,
            None,
            tokens.get(3).map(|value| clean_scalar_token(value)),
            tokens.get(4).map(|value| clean_scalar_token(value)),
        ),
        "L" => (
            point_at(&tokens, 3, 4),
            None,
            tokens.get(5).map(|value| clean_scalar_token(value)),
            tokens.get(6).map(|value| clean_scalar_token(value)),
        ),
        "A" => (
            point_at(&tokens, 3, 4),
            point_at(&tokens, 5, 6),
            tokens.get(7).map(|value| clean_scalar_token(value)),
            tokens.get(8).map(|value| clean_scalar_token(value)),
        ),
        "S" => (
            None,
            None,
            None,
            tokens.get(1).map(|value| clean_scalar_token(value)),
        ),
        _ => (
            None,
            None,
            tokens.get(1).map(|value| clean_scalar_token(value)),
            tokens.get(2).map(|value| clean_scalar_token(value)),
        ),
    };
    let attributes = record_attributes(raw_line);
    let feature_id = attributes.get("ID").cloned();
    Feature {
        feature_index,
        kind,
        line_number,
        tokens,
        feature_id,
        attributes,
        polarity,
        symbol,
        start,
        end,
        center,
        contours: Vec::new(),
    }
}

fn component_from_tokens(
    step_name: &str,
    layer_name: &str,
    line_number: usize,
    component_index: Option<i64>,
    record_type: String,
    tokens: Vec<String>,
) -> Component {
    let package_index = tokens.get(1).and_then(|value| value.parse::<i64>().ok());
    let location = point_at(&tokens, 2, 3);
    let rotation = tokens.get(4).and_then(|value| parse_f64_value(value));
    let mirror = tokens.get(5).cloned();
    let refdes = tokens
        .get(6)
        .cloned()
        .or_else(|| best_refdes_candidate(&tokens));
    let package_name =
        token_after_label(&tokens, "PKG").or_else(|| token_after_label(&tokens, "PACKAGE"));
    let part_name = token_after_label(&tokens, "PART").or_else(|| tokens.get(7).cloned());
    Component {
        step_name: step_name.to_string(),
        layer_name: layer_name.to_string(),
        line_number,
        record_type,
        component_index,
        package_index,
        refdes,
        package_name,
        part_name,
        location,
        rotation,
        mirror,
        properties: BTreeMap::new(),
        pins: Vec::new(),
        tokens,
    }
}

fn component_pin_from_tokens(
    line_number: usize,
    record_type: String,
    tokens: Vec<String>,
) -> ComponentPin {
    ComponentPin {
        line_number,
        record_type,
        pin_index: tokens.get(1).and_then(|value| value.parse::<i64>().ok()),
        name: tokens.get(8).cloned(),
        position: point_at(&tokens, 2, 3),
        rotation: tokens.get(4).and_then(|value| parse_f64_value(value)),
        mirror: tokens.get(5).cloned(),
        net_component_index: tokens.get(6).and_then(|value| value.parse::<i64>().ok()),
        net_pin_index: tokens.get(7).and_then(|value| value.parse::<i64>().ok()),
        tokens,
    }
}

fn property_from_tokens(tokens: &[String]) -> Option<(String, String)> {
    if tokens.len() < 3 || tokens[0] != "PRP" {
        return None;
    }
    Some((tokens[1].clone(), tokens[2..].join(" ")))
}

fn component_index_comment(line: &str) -> Option<i64> {
    let trimmed = line.trim();
    let rest = trimmed.strip_prefix("#")?.trim();
    let mut tokens = rest.split_whitespace();
    if !tokens.next()?.eq_ignore_ascii_case("CMP") {
        return None;
    }
    tokens.next()?.parse::<i64>().ok()
}

fn package_index_comment(line: &str) -> Option<i64> {
    let trimmed = line.trim();
    let rest = trimmed.strip_prefix("#")?.trim();
    let mut tokens = rest.split_whitespace();
    if !tokens.next()?.eq_ignore_ascii_case("PKG") {
        return None;
    }
    tokens.next()?.parse::<i64>().ok()
}

fn record_attributes(line: &str) -> BTreeMap<String, String> {
    let mut attributes = BTreeMap::new();
    let Some((_, tail)) = line.split_once(';') else {
        return attributes;
    };
    let mut raw_parts = Vec::new();
    for part in tail.split(';').flat_map(|part| part.split(',')) {
        let text = part.trim().trim_matches(',');
        if text.is_empty() {
            continue;
        }
        if let Some((key, value)) = text.split_once('=') {
            attributes.insert(
                key.trim().to_string(),
                unquote(value.trim().trim_matches(',')),
            );
        } else {
            raw_parts.push(text.to_string());
        }
    }
    if !raw_parts.is_empty() {
        attributes.insert("raw".to_string(), raw_parts.join(";"));
    }
    attributes
}

fn point_at(tokens: &[String], x_index: usize, y_index: usize) -> Option<Point> {
    let x = parse_f64_value(tokens.get(x_index)?)?;
    let y = parse_f64_value(tokens.get(y_index)?)?;
    Some(Point { x, y })
}

fn parse_f64_value(value: &str) -> Option<f64> {
    clean_scalar_slice(value).parse::<f64>().ok()
}

fn clean_scalar_token(value: &str) -> String {
    clean_scalar_slice(value).to_string()
}

fn token_attribute(tokens: &[String], key: &str) -> Option<String> {
    let prefix = format!("{key}=");
    tokens.iter().find_map(|token| {
        let token = token.trim_matches(';').trim_matches(',');
        strip_ascii_case_prefix(token, &prefix).map(unquote)
    })
}

fn field<'a>(fields: &'a BTreeMap<String, String>, keys: &[&str]) -> Option<&'a str> {
    keys.iter()
        .find_map(|key| fields.get(*key).map(|value| value.as_str()))
        .filter(|value| !value.is_empty())
}

fn parse_key_value(line: &str) -> Option<(&str, &str)> {
    if let Some((key, value)) = line.split_once('=') {
        return Some((key.trim(), value.trim()));
    }
    let mut parts = line.splitn(2, char::is_whitespace);
    let key = parts.next()?.trim();
    let value = parts.next()?.trim();
    if key.is_empty() || value.is_empty() {
        None
    } else {
        Some((key, value))
    }
}

fn parse_lookup(line: &str, prefix: char, target: &mut BTreeMap<String, String>) -> bool {
    if !line.starts_with(prefix) {
        return false;
    }
    let body = line.trim_start_matches(prefix).trim();
    if body.is_empty() {
        return false;
    }
    if let Some((key, value)) = body.split_once(char::is_whitespace) {
        target.insert(key.to_string(), unquote(value.trim()));
    } else if let Some((key, value)) = body.split_once('=') {
        target.insert(key.trim().to_string(), unquote(value.trim()));
    } else {
        target.insert(body.to_string(), String::new());
    }
    true
}

fn parse_units(line: &str) -> Option<String> {
    if starts_with_ignore_ascii_case(line, "UNITS") {
        if let Some((_, value)) = parse_key_value(line) {
            return Some(unquote(value));
        }
    }
    if starts_with_ignore_ascii_case(line, "U ") {
        return line.split_whitespace().nth(1).map(unquote);
    }
    None
}

fn net_name_from_tokens(tokens: &[String]) -> Option<String> {
    if tokens.len() >= 2 && matches!(tokens[0].as_str(), "NET" | "$NET" | "NET_NAME") {
        return Some(clean_net_name(&tokens[1]));
    }
    for token in tokens {
        if let Some(value) = strip_ascii_case_prefix(token, "NET_NAME=") {
            return Some(clean_net_name(value));
        }
        if let Some(value) = token.strip_prefix("$") {
            if !value.is_empty() && !value.chars().all(|ch| ch.is_ascii_digit()) {
                return Some(clean_net_name(value));
            }
        }
    }
    None
}

fn pin_ref_from_tokens(line_number: usize, tokens: &[String]) -> Option<NetPinRef> {
    if tokens.len() < 5 || tokens[0] != "SNT" || !tokens[1].eq_ignore_ascii_case("TOP") {
        return None;
    }
    let side = match tokens[2].to_ascii_uppercase().as_str() {
        "T" => Some("top".to_string()),
        "B" => Some("bottom".to_string()),
        _ => None,
    };
    Some(NetPinRef {
        line_number,
        side,
        net_component_index: tokens.get(3).and_then(|value| value.parse::<i64>().ok()),
        net_pin_index: tokens.get(4).and_then(|value| value.parse::<i64>().ok()),
        tokens: tokens.to_vec(),
    })
}

fn feature_ref_from_tokens(
    line_number: usize,
    tokens: &[String],
    layer_names: &[String],
    subnet_type: Option<&str>,
    pin_ref: Option<&NetPinRef>,
) -> Option<NetFeatureRef> {
    if tokens.len() < 4 || tokens[0] != "FID" {
        return None;
    }
    let class_code = tokens.get(1)?.clone();
    let layer_index = tokens.get(2).and_then(|value| value.parse::<i64>().ok());
    let feature_index = tokens.get(3).and_then(|value| value.parse::<usize>().ok());
    let layer_name = layer_index
        .and_then(|index| usize::try_from(index).ok())
        .and_then(|index| layer_names.get(index).cloned());
    Some(NetFeatureRef {
        line_number,
        subnet_type: subnet_type.map(ToOwned::to_owned),
        class_code,
        layer_index,
        layer_name,
        feature_index,
        pin_side: pin_ref.and_then(|value| value.side.clone()),
        net_component_index: pin_ref.and_then(|value| value.net_component_index),
        net_pin_index: pin_ref.and_then(|value| value.net_pin_index),
        tokens: tokens.to_vec(),
    })
}

fn merge_nets(nets: Vec<Net>) -> Vec<Net> {
    let mut by_key: HashMap<String, Net> = HashMap::new();
    let mut order: Vec<String> = Vec::new();
    for net in nets {
        let key = net.name.to_ascii_lowercase();
        if let Some(existing) = by_key.get_mut(&key) {
            existing.feature_refs.extend(net.feature_refs);
            existing.pin_refs.extend(net.pin_refs);
            continue;
        }
        order.push(key.clone());
        by_key.insert(key, net);
    }
    order
        .into_iter()
        .filter_map(|key| by_key.remove(&key))
        .collect()
}

fn clean_net_name(value: &str) -> String {
    unquoted_slice(value)
        .trim_matches(',')
        .trim_matches(';')
        .trim()
        .to_string()
}

fn best_refdes_candidate(tokens: &[String]) -> Option<String> {
    token_after_label(tokens, "REFDES").or_else(|| {
        tokens.iter().find_map(|token| {
            let token = token.trim_matches('"');
            if looks_like_refdes(token) {
                Some(token.to_string())
            } else {
                None
            }
        })
    })
}

fn token_after_label(tokens: &[String], label: &str) -> Option<String> {
    for (index, token) in tokens.iter().enumerate() {
        if token.eq_ignore_ascii_case(label) {
            return tokens.get(index + 1).cloned();
        }
        let prefix = format!("{label}=");
        if let Some(value) = strip_ascii_case_prefix(token, &prefix) {
            return Some(value.to_string());
        }
    }
    None
}

fn looks_like_refdes(value: &str) -> bool {
    let mut chars = value.chars();
    let Some(first) = chars.next() else {
        return false;
    };
    first.is_ascii_alphabetic() && chars.any(|ch| ch.is_ascii_digit())
}

fn split_tokens(line: &str) -> Vec<String> {
    let mut tokens = Vec::new();
    let mut current = String::new();
    let mut in_quote = false;
    let mut quote_char = '\0';
    for ch in line.chars() {
        if in_quote {
            if ch == quote_char {
                in_quote = false;
                tokens.push(std::mem::take(&mut current));
            } else {
                current.push(ch);
            }
            continue;
        }
        if ch == '"' || ch == '\'' {
            if !current.is_empty() {
                tokens.push(std::mem::take(&mut current));
            }
            in_quote = true;
            quote_char = ch;
            continue;
        }
        if ch.is_whitespace() {
            if !current.is_empty() {
                tokens.push(std::mem::take(&mut current));
            }
        } else {
            current.push(ch);
        }
    }
    if !current.is_empty() {
        tokens.push(current);
    }
    tokens
}

fn strip_comment(line: &str) -> &str {
    if line.trim_start().starts_with('#') {
        ""
    } else {
        line
    }
}

fn unquote(value: &str) -> String {
    unquoted_slice(value).to_string()
}

fn clean_scalar_slice(value: &str) -> &str {
    value
        .split(';')
        .next()
        .unwrap_or(value)
        .trim()
        .trim_matches(',')
        .trim_matches('"')
        .trim_matches('\'')
}

fn unquoted_slice(value: &str) -> &str {
    value
        .trim()
        .trim_matches('"')
        .trim_matches('\'')
        .trim_end_matches(';')
}

fn starts_with_ignore_ascii_case(value: &str, prefix: &str) -> bool {
    value
        .get(..prefix.len())
        .map(|head| head.eq_ignore_ascii_case(prefix))
        .unwrap_or(false)
}

fn strip_ascii_case_prefix<'a>(value: &'a str, prefix: &str) -> Option<&'a str> {
    let (head, tail) = value.split_at_checked(prefix.len())?;
    if head.eq_ignore_ascii_case(prefix) {
        Some(tail)
    } else {
        None
    }
}

fn text_from_bytes<'a>(
    bytes: &'a [u8],
    path: &str,
    diagnostics: &mut Vec<String>,
) -> Option<Cow<'a, str>> {
    match std::str::from_utf8(bytes) {
        Ok(text) => Some(Cow::Borrowed(text)),
        Err(_) => match String::from_utf8_lossy(bytes) {
            Cow::Borrowed(text) => Some(Cow::Borrowed(text)),
            Cow::Owned(text) => {
                diagnostics.push(format!("Decoded {path} with replacement characters"));
                Some(Cow::Owned(text))
            }
        },
    }
}

#[cfg(test)]
mod tests {
    use super::{parse_feature_file, parse_matrix, parse_net_file, split_tokens, BTreeMap};

    #[test]
    fn tokenizer_preserves_quoted_tokens() {
        let tokens = split_tokens(r#"P 1 2 "r 100x200" P;ID=pad1"#);

        assert_eq!(tokens, vec!["P", "1", "2", "r 100x200", "P;ID=pad1"]);
    }

    #[test]
    fn matrix_parser_reads_layer_rows() {
        let matrix = parse_matrix(
            r#"
            ROW {
              ROW=1
              NAME=TOP
              CONTEXT=BOARD
              TYPE=SIGNAL
              POLARITY=POSITIVE
              SIDE=TOP
            }
            "#,
        );

        assert_eq!(matrix.rows.len(), 1);
        let row = &matrix.rows[0];
        assert_eq!(row.row, Some(1));
        assert_eq!(row.name.as_deref(), Some("TOP"));
        assert_eq!(row.context.as_deref(), Some("BOARD"));
        assert_eq!(row.layer_type.as_deref(), Some("SIGNAL"));
        assert_eq!(row.side.as_deref(), Some("TOP"));
    }

    #[test]
    fn feature_parser_reads_points_lines_and_surface_arcs() {
        let layer = parse_feature_file(
            "main",
            "top",
            r#"
            UNITS=MM
            $1 r100
            @1 net_type
            P 1.0 2.0 $1 P;ID=pad1
            L 0 0 10 0 r50 P
            S P
            OB 0 0 I
            OS 10 0
            OC 10 10 5 5 Y
            OE
            SE
            "#,
            BTreeMap::new(),
        );

        assert_eq!(layer.units.as_deref(), Some("MM"));
        assert_eq!(layer.symbols.get("1").map(String::as_str), Some("r100"));
        assert_eq!(layer.features.len(), 3);
        assert_eq!(layer.features[0].kind, "P");
        assert_eq!(layer.features[0].feature_id.as_deref(), Some("pad1"));
        assert_eq!(layer.features[0].symbol.as_deref(), Some("$1"));
        assert_eq!(layer.features[1].kind, "L");
        let surface = &layer.features[2];
        assert_eq!(surface.kind, "S");
        assert_eq!(surface.contours.len(), 1);
        assert_eq!(surface.contours[0].polarity.as_deref(), Some("I"));
        assert_eq!(surface.contours[0].vertices.len(), 3);
        assert_eq!(surface.contours[0].vertices[2].record_type, "OC");
        assert_eq!(surface.contours[0].vertices[2].clockwise, Some(true));
    }

    #[test]
    fn net_parser_keeps_pin_and_feature_refs() {
        let nets = parse_net_file(
            "main",
            "steps/main/eda/data",
            r#"
            LYR TOP BOT
            NET GND
            SNT TOP T 3 4
            FID C 0 12
            SNT VIA
            FID C 1 20
            NET "V CC"
            FID C 0 30
            "#,
        );

        assert_eq!(nets.len(), 2);
        assert_eq!(nets[0].name, "GND");
        assert_eq!(nets[0].pin_refs.len(), 1);
        assert_eq!(nets[0].feature_refs.len(), 2);
        assert_eq!(nets[0].feature_refs[0].layer_name.as_deref(), Some("TOP"));
        assert_eq!(nets[0].feature_refs[0].net_component_index, Some(3));
        assert_eq!(nets[0].feature_refs[0].net_pin_index, Some(4));
        assert_eq!(nets[0].feature_refs[1].subnet_type.as_deref(), Some("VIA"));
        assert_eq!(nets[0].feature_refs[1].layer_name.as_deref(), Some("BOT"));
        assert_eq!(nets[1].name, "V CC");
        assert_eq!(nets[1].feature_refs[0].feature_index, Some(30));
    }
}
