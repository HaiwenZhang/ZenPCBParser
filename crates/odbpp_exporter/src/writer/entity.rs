use super::components::*;
use super::features::*;
use super::formatting::*;
use super::model::*;
use super::netlist::*;
use super::package::*;
use serde_json::Value;
use std::collections::{BTreeMap, HashMap};
use std::fs;
use std::path::{Path, PathBuf};
use thiserror::Error;

pub const RUST_EXPORTER_VERSION: &str = env!("CARGO_PKG_VERSION");

#[derive(Debug, Error)]
pub enum ExportError {
    #[error("failed to read {path}: {source}")]
    Read {
        path: String,
        #[source]
        source: std::io::Error,
    },
    #[error("failed to parse SemanticBoard JSON {path}: {source}")]
    Json {
        path: String,
        #[source]
        source: serde_json::Error,
    },
    #[error("failed to write {path}: {source}")]
    Write {
        path: String,
        #[source]
        source: std::io::Error,
    },
}

#[derive(Debug, Clone)]
pub struct ExportOptions {
    pub step_name: Option<String>,
    pub product_name: Option<String>,
}

impl Default for ExportOptions {
    fn default() -> Self {
        Self {
            step_name: Some("pcb".to_string()),
            product_name: Some("aurora_semantic".to_string()),
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct OdbExportSummary {
    pub root: PathBuf,
    pub units: String,
    pub step_name: String,
    pub layer_count: usize,
    pub feature_count: usize,
    pub component_count: usize,
    pub package_count: usize,
    pub net_count: usize,
}

pub fn export_semantic_json_file(
    input: &Path,
    output: &Path,
    options: &ExportOptions,
) -> Result<OdbExportSummary, ExportError> {
    let text = fs::read_to_string(input).map_err(|source| ExportError::Read {
        path: input.display().to_string(),
        source,
    })?;
    let board: SemanticBoard = serde_json::from_str(&text).map_err(|source| ExportError::Json {
        path: input.display().to_string(),
        source,
    })?;
    export_semantic_board(&board, output, options)
}

pub fn export_semantic_board(
    board: &SemanticBoard,
    output: &Path,
    options: &ExportOptions,
) -> Result<OdbExportSummary, ExportError> {
    let units = UnitScale::from_semantic_units(board.units.as_deref());
    let step_name = legal_step_name(
        options
            .step_name
            .as_deref()
            .filter(|value| !value.trim().is_empty())
            .unwrap_or("pcb"),
    );
    let product_name = legal_entity_name(
        options
            .product_name
            .as_deref()
            .filter(|value| !value.trim().is_empty())
            .unwrap_or("aurora_semantic"),
    );
    let root = output.to_path_buf();
    prepare_output_root(&root)?;

    let mut package = OdbPackage::new(board, units, step_name, product_name);
    package.build();
    package.write(&root)?;

    Ok(OdbExportSummary {
        root,
        units: package.units.odb_units.to_string(),
        step_name: package.step_name.clone(),
        layer_count: package.matrix_layers.len(),
        feature_count: package.feature_count(),
        component_count: package.components.len(),
        package_count: package.packages.len(),
        net_count: package.net_names.len(),
    })
}

#[derive(Debug, Clone)]
pub(super) struct OdbPackage<'a> {
    pub(super) board: &'a SemanticBoard,
    pub(super) units: UnitScale,
    pub(super) step_name: String,
    pub(super) product_name: String,
    pub(super) source_format: String,
    pub(super) shape_by_id: HashMap<String, &'a SemanticShape>,
    pub(super) net_name_by_id: HashMap<String, String>,
    pub(super) net_names: Vec<(String, String)>,
    pub(super) layer_name_map: HashMap<String, String>,
    pub(super) matrix_layers: Vec<MatrixLayer>,
    pub(super) feature_layers: BTreeMap<String, FeatureLayer>,
    pub(super) drill_layer_name: Option<String>,
    pub(super) components: Vec<ComponentOut>,
    pub(super) packages: Vec<PackageOut>,
    pub(super) package_index_by_footprint_id: HashMap<String, usize>,
    pub(super) package_index_by_name: HashMap<String, usize>,
    pub(super) pin_key_by_id: HashMap<String, PinNetKey>,
    pub(super) feature_links: Vec<NetFeatureLink>,
}

impl<'a> OdbPackage<'a> {
    fn new(
        board: &'a SemanticBoard,
        units: UnitScale,
        step_name: String,
        product_name: String,
    ) -> Self {
        let source_format = board
            .metadata
            .source_format
            .as_deref()
            .unwrap_or_default()
            .to_ascii_lowercase();
        let shape_by_id = board
            .shapes
            .iter()
            .map(|shape| (shape.id.clone(), shape))
            .collect();
        let net_name_by_id = board
            .nets
            .iter()
            .map(|net| (net.id.clone(), odb_net_name(&net.name)))
            .collect();
        let net_names = board
            .nets
            .iter()
            .map(|net| (net.id.clone(), odb_net_name(&net.name)))
            .collect();
        Self {
            board,
            units,
            step_name,
            product_name,
            source_format,
            shape_by_id,
            net_name_by_id,
            net_names,
            layer_name_map: HashMap::new(),
            matrix_layers: Vec::new(),
            feature_layers: BTreeMap::new(),
            drill_layer_name: None,
            components: Vec::new(),
            packages: Vec::new(),
            package_index_by_footprint_id: HashMap::new(),
            package_index_by_name: HashMap::new(),
            pin_key_by_id: HashMap::new(),
            feature_links: Vec::new(),
        }
    }

    fn build(&mut self) {
        self.build_layers();
        self.build_packages();
        self.build_components();
        self.build_primitives();
        self.build_pads();
        self.build_vias();
        self.ensure_profile_extents();
    }

    fn feature_count(&self) -> usize {
        self.feature_layers
            .values()
            .map(|layer| layer.features.len())
            .sum()
    }

    fn write(&self, root: &Path) -> Result<(), ExportError> {
        self.write_root_dirs(root)?;
        self.write_misc_info(root)?;
        self.write_matrix(root)?;
        self.write_step(root)?;
        Ok(())
    }

    fn build_layers(&mut self) {
        let mut ordered_layers: Vec<(usize, &'a SemanticLayer)> =
            self.board.layers.iter().enumerate().collect();
        ordered_layers.sort_by_key(|(index, layer)| {
            (
                layer.order_index.unwrap_or(i64::MAX),
                i64::try_from(*index).unwrap_or(i64::MAX),
            )
        });

        let has_top_components = self
            .board
            .components
            .iter()
            .any(|component| component_side(component) != "bottom");
        let has_bottom_components = self
            .board
            .components
            .iter()
            .any(|component| component_side(component) == "bottom");

        if has_top_components {
            self.push_component_matrix_layer("COMP_+_TOP", "TOP");
        }

        for (_index, layer) in ordered_layers {
            let odb_name = self.unique_layer_name(&layer.name);
            self.layer_name_map
                .insert(layer.name.clone(), odb_name.clone());
            self.layer_name_map
                .insert(layer.id.clone(), odb_name.clone());
            let classification = classify_layer(layer);
            if classification.layer_type == "DIELECTRIC" {
                self.matrix_layers.push(MatrixLayer {
                    name: odb_name,
                    context: "BOARD".to_string(),
                    layer_type: "DIELECTRIC".to_string(),
                    polarity: "POSITIVE".to_string(),
                    side: None,
                    start_name: None,
                    end_name: None,
                    dielectric_type: Some("PREPREG".to_string()),
                });
            } else if classification.layer_type != "DRILL" {
                self.matrix_layers.push(MatrixLayer {
                    name: odb_name.clone(),
                    context: classification.context,
                    layer_type: classification.layer_type,
                    polarity: "POSITIVE".to_string(),
                    side: classification.side,
                    start_name: None,
                    end_name: None,
                    dielectric_type: None,
                });
                self.feature_layers
                    .entry(odb_name.clone())
                    .or_insert_with(|| FeatureLayer::new(odb_name));
            }
        }

        self.ensure_used_signal_layers();

        if !self.board.vias.is_empty() {
            let drill_name = self.unique_generated_layer_name("DRILL");
            let span = self.signal_layer_span();
            self.matrix_layers.push(MatrixLayer {
                name: drill_name.clone(),
                context: "BOARD".to_string(),
                layer_type: "DRILL".to_string(),
                polarity: "POSITIVE".to_string(),
                side: None,
                start_name: span.as_ref().map(|(start, _)| start.clone()),
                end_name: span.map(|(_, end)| end),
                dielectric_type: None,
            });
            self.feature_layers
                .entry(drill_name.clone())
                .or_insert_with(|| FeatureLayer::new(drill_name.clone()));
            self.drill_layer_name = Some(drill_name);
        }

        if has_bottom_components {
            self.push_component_matrix_layer("COMP_+_BOT", "BOTTOM");
        }
    }

    fn push_component_matrix_layer(&mut self, name: &str, side: &str) {
        self.matrix_layers.push(MatrixLayer {
            name: name.to_string(),
            context: "BOARD".to_string(),
            layer_type: "COMPONENT".to_string(),
            polarity: "POSITIVE".to_string(),
            side: Some(side.to_string()),
            start_name: None,
            end_name: None,
            dielectric_type: None,
        });
    }

    fn ensure_used_signal_layers(&mut self) {
        let mut used = Vec::new();
        for primitive in &self.board.primitives {
            if let Some(layer) = primitive.layer_name.as_deref() {
                used.push(layer.to_string());
            }
        }
        for pad in &self.board.pads {
            if let Some(layer) = pad.layer_name.as_deref() {
                used.push(layer.to_string());
            }
        }
        for via in &self.board.vias {
            used.extend(via.layer_names.iter().cloned());
        }

        for name in used {
            if self.layer_name_map.contains_key(&name) {
                continue;
            }
            let odb_name = self.unique_layer_name(&name);
            self.layer_name_map.insert(name, odb_name.clone());
            self.matrix_layers.push(MatrixLayer {
                name: odb_name.clone(),
                context: "BOARD".to_string(),
                layer_type: "SIGNAL".to_string(),
                polarity: "POSITIVE".to_string(),
                side: layer_side_from_name(&odb_name),
                start_name: None,
                end_name: None,
                dielectric_type: None,
            });
            self.feature_layers
                .entry(odb_name.clone())
                .or_insert_with(|| FeatureLayer::new(odb_name));
        }
    }

    fn signal_layer_span(&self) -> Option<(String, String)> {
        let signals: Vec<String> = self
            .matrix_layers
            .iter()
            .filter(|layer| layer.layer_type == "SIGNAL")
            .map(|layer| layer.name.clone())
            .collect();
        Some((signals.first()?.clone(), signals.last()?.clone()))
    }

    fn build_primitives(&mut self) {
        let primitives = self.board.primitives.clone();
        for primitive in primitives {
            let Some(layer_name) = primitive
                .layer_name
                .as_deref()
                .and_then(|name| self.odb_layer_name(name))
            else {
                continue;
            };
            let kind = primitive.kind.to_ascii_lowercase();
            if kind.contains("polygon")
                || !geometry_points(&primitive.geometry, "raw_points").is_empty()
            {
                self.add_surface_primitive(&primitive, &layer_name);
            } else if kind.contains("arc")
                || (geometry_point(&primitive.geometry, "start").is_some()
                    && geometry_point(&primitive.geometry, "end").is_some()
                    && geometry_point(&primitive.geometry, "center").is_some())
            {
                self.add_arc_primitive(&primitive, &layer_name);
            } else {
                self.add_line_primitive(&primitive, &layer_name);
            }
        }
    }

    fn add_line_primitive(&mut self, primitive: &SemanticPrimitive, layer_name: &str) {
        let mut segments = Vec::new();
        let center_line = geometry_points(&primitive.geometry, "center_line");
        if center_line.len() >= 2 {
            for pair in center_line.windows(2) {
                segments.push((pair[0], pair[1]));
            }
        } else if let (Some(start), Some(end)) = (
            geometry_point(&primitive.geometry, "start"),
            geometry_point(&primitive.geometry, "end"),
        ) {
            segments.push((start, end));
        }
        if segments.is_empty() {
            return;
        }
        let width = geometry_number(&primitive.geometry, "width").unwrap_or(0.0);
        let symbol_name = symbol_for_width(self.units.length(width));
        for (start, end) in segments {
            let start = self.units.point(start);
            let end = self.units.point(end);
            let feature_index = {
                let layer = self.feature_layer_mut(layer_name);
                let symbol = layer.symbol_index(symbol_name.clone());
                layer.push(FeatureRecord::Line {
                    start,
                    end,
                    symbol,
                    id: feature_id(primitive.id.as_str(), primitive.source.raw_id.as_deref()),
                })
            };
            self.push_feature_link(
                primitive.net_id.as_deref(),
                layer_name,
                feature_index,
                "C",
                "TRC",
                None,
            );
        }
    }

    fn add_arc_primitive(&mut self, primitive: &SemanticPrimitive, layer_name: &str) {
        let (Some(start), Some(end), Some(center)) = (
            geometry_point(&primitive.geometry, "start"),
            geometry_point(&primitive.geometry, "end"),
            geometry_point(&primitive.geometry, "center"),
        ) else {
            self.add_line_primitive(primitive, layer_name);
            return;
        };
        let width = geometry_number(&primitive.geometry, "width").unwrap_or(0.0);
        let clockwise = geometry_bool(&primitive.geometry, "clockwise")
            .or_else(|| geometry_bool(&primitive.geometry, "is_ccw").map(|value| !value))
            .unwrap_or(false);
        let symbol_name = symbol_for_width(self.units.length(width));
        let start = self.units.point(start);
        let end = self.units.point(end);
        let center = self.units.point(center);
        let feature_index = {
            let layer = self.feature_layer_mut(layer_name);
            let symbol = layer.symbol_index(symbol_name);
            layer.push(FeatureRecord::Arc {
                start,
                end,
                center,
                symbol,
                clockwise,
                id: feature_id(primitive.id.as_str(), primitive.source.raw_id.as_deref()),
            })
        };
        self.push_feature_link(
            primitive.net_id.as_deref(),
            layer_name,
            feature_index,
            "C",
            "TRC",
            None,
        );
    }

    fn add_surface_primitive(&mut self, primitive: &SemanticPrimitive, layer_name: &str) {
        let raw_points = geometry_points(&primitive.geometry, "raw_points");
        if raw_points.len() < 3 {
            return;
        }
        let mut contours = vec![SurfaceContourOut {
            polarity: "I".to_string(),
            vertices: raw_points
                .into_iter()
                .map(|point| SurfaceVertex::Line(self.units.point(point)))
                .collect(),
        }];
        if let Some(voids) = primitive.geometry.get("voids").and_then(Value::as_array) {
            for void in voids {
                let points = geometry_points(void, "raw_points");
                if points.len() >= 3 {
                    contours.push(SurfaceContourOut {
                        polarity: "H".to_string(),
                        vertices: points
                            .into_iter()
                            .map(|point| SurfaceVertex::Line(self.units.point(point)))
                            .collect(),
                    });
                }
            }
        }
        let feature_index = {
            let layer = self.feature_layer_mut(layer_name);
            layer.push(FeatureRecord::Surface {
                contours,
                id: feature_id(primitive.id.as_str(), primitive.source.raw_id.as_deref()),
            })
        };
        self.push_feature_link(
            primitive.net_id.as_deref(),
            layer_name,
            feature_index,
            "C",
            "PLN",
            None,
        );
    }

    fn build_pads(&mut self) {
        let pads = self.board.pads.clone();
        for pad in pads {
            let Some(net_id) = pad.net_id.as_deref() else {
                continue;
            };
            let Some(position) = pad.position.as_ref().map(point_from_semantic) else {
                continue;
            };
            let Some(layer_name) = pad
                .layer_name
                .as_deref()
                .and_then(|name| self.odb_layer_name(name))
            else {
                continue;
            };
            let shape = self.shape_for_pad(&pad);
            let center = self.units.point(position);
            let symbol_name = shape
                .map(|shape| symbol_for_shape(shape, self.units))
                .or_else(|| {
                    pad.padstack_definition
                        .as_deref()
                        .map(|name| legal_symbol_name(name))
                })
                .unwrap_or_else(|| "r0.1".to_string());
            let rotation = geometry_value(&pad.geometry, "rotation")
                .map(|value| rotation_to_odb_degrees(Some(value), &self.source_format))
                .unwrap_or(0.0);
            let mirror = geometry_bool(&pad.geometry, "mirror_x").unwrap_or(false);
            let feature_index = {
                let layer = self.feature_layer_mut(&layer_name);
                let symbol = layer.symbol_index(symbol_name);
                layer.push(FeatureRecord::Pad {
                    center,
                    symbol,
                    rotation,
                    mirror,
                    id: Some(pad.id.clone()),
                })
            };
            let pin_key = pad
                .pin_id
                .as_deref()
                .and_then(|pin_id| self.pin_key_by_id.get(pin_id).cloned());
            self.push_feature_link(
                Some(net_id),
                &layer_name,
                feature_index,
                "C",
                "TOP",
                pin_key,
            );
        }
    }

    fn build_vias(&mut self) {
        let Some(drill_layer_name) = self.drill_layer_name.clone() else {
            return;
        };
        let via_template_by_id: HashMap<&str, &SemanticViaTemplate> = self
            .board
            .via_templates
            .iter()
            .map(|template| (template.id.as_str(), template))
            .collect();
        let vias = self.board.vias.clone();
        for via in vias {
            let Some(net_id) = via.net_id.as_deref() else {
                continue;
            };
            let Some(position) = via.position.as_ref().map(point_from_semantic) else {
                continue;
            };
            let template = via
                .template_id
                .as_deref()
                .and_then(|id| via_template_by_id.get(id).copied());
            let drill_shape = template
                .and_then(|template| template.barrel_shape_id.as_deref())
                .and_then(|shape_id| self.shape_by_id.get(shape_id).copied())
                .or_else(|| {
                    template.and_then(|template| {
                        template.layer_pads.iter().find_map(|layer_pad| {
                            layer_pad
                                .pad_shape_id
                                .as_deref()
                                .and_then(|shape_id| self.shape_by_id.get(shape_id).copied())
                        })
                    })
                });

            let drill_center = self.units.point(position);
            let drill_rotation = geometry_value(&via.geometry, "rotation")
                .map(|value| rotation_to_odb_degrees(Some(value), &self.source_format))
                .unwrap_or(0.0);
            let drill_symbol_name = drill_shape
                .map(|shape| symbol_for_shape(shape, self.units))
                .unwrap_or_else(|| "r0.1".to_string());
            let drill_feature_index = {
                let layer = self.feature_layer_mut(&drill_layer_name);
                let symbol = layer.symbol_index(drill_symbol_name);
                layer.push(FeatureRecord::Pad {
                    center: drill_center,
                    symbol,
                    rotation: drill_rotation,
                    mirror: false,
                    id: Some(via.id.clone()),
                })
            };
            self.push_feature_link(
                Some(net_id),
                &drill_layer_name,
                drill_feature_index,
                "H",
                "VIA",
                None,
            );

            if let Some(template) = template {
                for layer_pad in &template.layer_pads {
                    let Some(layer_name) = self.odb_layer_name(&layer_pad.layer_name) else {
                        continue;
                    };
                    let shape = layer_pad
                        .pad_shape_id
                        .as_deref()
                        .and_then(|shape_id| self.shape_by_id.get(shape_id).copied())
                        .or(drill_shape);
                    let center = self.units.point(position);
                    let symbol_name = shape
                        .map(|shape| symbol_for_shape(shape, self.units))
                        .unwrap_or_else(|| "r0.1".to_string());
                    let feature_index = {
                        let layer = self.feature_layer_mut(&layer_name);
                        let symbol = layer.symbol_index(symbol_name);
                        layer.push(FeatureRecord::Pad {
                            center,
                            symbol,
                            rotation: 0.0,
                            mirror: false,
                            id: Some(format!("{}_{}", via.id, layer_pad.layer_name)),
                        })
                    };
                    self.push_feature_link(
                        Some(net_id),
                        &layer_name,
                        feature_index,
                        "C",
                        "VIA",
                        None,
                    );
                }
            }
        }
    }

    fn ensure_profile_extents(&mut self) {
        let _ = self.profile_contours();
    }

    pub(super) fn shape_for_pad(&self, pad: &SemanticPad) -> Option<&'a SemanticShape> {
        geometry_string(&pad.geometry, "shape_id")
            .as_deref()
            .and_then(|id| self.shape_by_id.get(id).copied())
    }

    fn feature_layer_mut(&mut self, layer_name: &str) -> &mut FeatureLayer {
        self.feature_layers
            .entry(layer_name.to_string())
            .or_insert_with(|| FeatureLayer::new(layer_name.to_string()))
    }

    fn odb_layer_name(&self, name: &str) -> Option<String> {
        self.layer_name_map
            .get(name)
            .cloned()
            .or_else(|| self.layer_name_map.get(&name.to_ascii_uppercase()).cloned())
            .or_else(|| {
                let legal = legal_entity_name(name);
                self.feature_layers
                    .contains_key(&legal)
                    .then_some(legal.clone())
                    .or_else(|| {
                        self.feature_layers
                            .keys()
                            .find(|candidate| candidate.eq_ignore_ascii_case(&legal))
                            .cloned()
                    })
            })
    }

    fn unique_layer_name(&self, raw_name: &str) -> String {
        let base = legal_entity_name(raw_name);
        unique_name(
            base,
            self.matrix_layers.iter().map(|layer| layer.name.as_str()),
        )
    }

    fn unique_generated_layer_name(&self, raw_name: &str) -> String {
        let base = legal_entity_name(raw_name);
        unique_name(
            base,
            self.matrix_layers.iter().map(|layer| layer.name.as_str()),
        )
    }

    fn profile_contours(&self) -> Vec<SurfaceContourOut> {
        let values = self
            .board
            .board_outline
            .get("values")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let points = polygon_points_from_values(&values, self.units);
        if points.len() >= 3 {
            return vec![SurfaceContourOut {
                polarity: "I".to_string(),
                vertices: points.into_iter().map(SurfaceVertex::Line).collect(),
            }];
        }

        let mut extents = Extents::default();
        for layer in self.feature_layers.values() {
            for feature in &layer.features {
                feature.extend_extents(&mut extents);
            }
        }
        let (min, max) = extents
            .bounds()
            .unwrap_or((Point { x: -0.5, y: -0.5 }, Point { x: 0.5, y: 0.5 }));
        let margin = ((max.x - min.x).abs().max((max.y - min.y).abs()) * 0.05).max(1.0);
        vec![SurfaceContourOut {
            polarity: "I".to_string(),
            vertices: vec![
                SurfaceVertex::Line(Point {
                    x: min.x - margin,
                    y: min.y - margin,
                }),
                SurfaceVertex::Line(Point {
                    x: max.x + margin,
                    y: min.y - margin,
                }),
                SurfaceVertex::Line(Point {
                    x: max.x + margin,
                    y: max.y + margin,
                }),
                SurfaceVertex::Line(Point {
                    x: min.x - margin,
                    y: max.y + margin,
                }),
            ],
        }]
    }

    fn write_root_dirs(&self, root: &Path) -> Result<(), ExportError> {
        for dirname in [
            "fonts", "input", "matrix", "misc", "symbols", "user", "wheels",
        ] {
            create_dir(root.join(dirname))?;
        }
        create_dir(root.join("steps").join(&self.step_name))?;
        Ok(())
    }

    fn write_misc_info(&self, root: &Path) -> Result<(), ExportError> {
        let mut text = String::new();
        write_kv(&mut text, "JOB_NAME", &self.product_name);
        write_kv(&mut text, "ODB_UNITS", self.units.odb_units);
        write_kv(&mut text, "ODB_VERSION_MAJOR", "8");
        write_kv(&mut text, "ODB_VERSION_MINOR", "1");
        write_kv(&mut text, "ODB_SOURCE", "Aurora Translator");
        write_kv(
            &mut text,
            "AURORA_ODBPP_EXPORTER_VERSION",
            RUST_EXPORTER_VERSION,
        );
        write_kv(&mut text, "CREATION_DATE", "19700101.000000");
        write_kv(&mut text, "SAVE_DATE", "19700101.000000");
        write_file(root.join("misc").join("info"), text)
    }

    fn write_matrix(&self, root: &Path) -> Result<(), ExportError> {
        let mut text = String::new();
        text.push_str("STEP {\n");
        write_kv(&mut text, "COL", "1");
        write_kv(&mut text, "NAME", &self.step_name.to_ascii_uppercase());
        text.push_str("}\n");
        for (index, layer) in self.matrix_layers.iter().enumerate() {
            text.push_str("LAYER {\n");
            write_kv(&mut text, "ROW", &(index + 1).to_string());
            write_kv(&mut text, "CONTEXT", &layer.context);
            write_kv(&mut text, "TYPE", &layer.layer_type);
            write_kv(&mut text, "NAME", &layer.name);
            write_kv(&mut text, "OLD_NAME", "");
            write_kv(&mut text, "POLARITY", &layer.polarity);
            if let Some(side) = &layer.side {
                write_kv(&mut text, "SIDE", side);
            }
            if let Some(start) = &layer.start_name {
                write_kv(&mut text, "START_NAME", start);
            }
            if let Some(end) = &layer.end_name {
                write_kv(&mut text, "END_NAME", end);
            }
            if let Some(dielectric_type) = &layer.dielectric_type {
                write_kv(&mut text, "DIELECTRIC_TYPE", dielectric_type);
            }
            text.push_str("}\n");
        }
        write_file(root.join("matrix").join("matrix"), text)
    }

    fn write_step(&self, root: &Path) -> Result<(), ExportError> {
        let step_root = root.join("steps").join(&self.step_name);
        create_dir(step_root.join("layers"))?;
        for layer in self.feature_layers.values() {
            let layer_root = step_root.join("layers").join(&layer.name);
            create_dir(&layer_root)?;
            write_file(
                layer_root.join("features"),
                layer.to_features_text(self.units.odb_units),
            )?;
            write_file(
                layer_root.join("attrlist"),
                self.layer_attrlist_text(&layer.name),
            )?;
            if Some(layer.name.as_str()) == self.drill_layer_name.as_deref() {
                write_file(layer_root.join("tools"), self.drill_tools_text())?;
            }
        }
        for side_layer in ["COMP_+_TOP", "COMP_+_BOT"] {
            if self
                .components
                .iter()
                .any(|component| component.layer_name == side_layer)
            {
                let layer_root = step_root.join("layers").join(side_layer);
                create_dir(&layer_root)?;
                write_file(
                    layer_root.join("components"),
                    self.components_text(side_layer),
                )?;
                write_file(layer_root.join("attrlist"), String::new())?;
            }
        }
        create_dir(step_root.join("eda"))?;
        write_file(step_root.join("eda").join("data"), self.eda_data_text())?;
        create_dir(step_root.join("netlists").join("cadnet"))?;
        write_file(
            step_root.join("netlists").join("cadnet").join("netlist"),
            self.cadnet_text(),
        )?;
        write_file(step_root.join("profile"), self.profile_text())?;
        write_file(step_root.join("stephdr"), self.step_header_text())?;
        Ok(())
    }

    fn profile_text(&self) -> String {
        let contours = self.profile_contours();
        let mut text = String::new();
        write_kv(&mut text, "UNITS", self.units.odb_units);
        text.push_str("#\n#Num Features\n#\n");
        text.push_str("F 1\n");
        text.push_str("#\n#Layer features\n#\n");
        FeatureRecord::Surface {
            contours,
            id: Some("board_outline".to_string()),
        }
        .write(&mut text);
        text
    }

    fn step_header_text(&self) -> String {
        let mut text = String::new();
        write_kv(&mut text, "UNITS", self.units.odb_units);
        write_kv(&mut text, "X_DATUM", "0");
        write_kv(&mut text, "Y_DATUM", "0");
        write_kv(&mut text, "X_ORIGIN", "0");
        write_kv(&mut text, "Y_ORIGIN", "0");
        write_kv(&mut text, "TOP_ACTIVE", "0");
        write_kv(&mut text, "BOTTOM_ACTIVE", "0");
        write_kv(&mut text, "RIGHT_ACTIVE", "0");
        write_kv(&mut text, "LEFT_ACTIVE", "0");
        write_kv(&mut text, "AFFECTING_BOM", "");
        write_kv(&mut text, "AFFECTING_BOM_CHANGED", "0");
        text
    }

    fn drill_tools_text(&self) -> String {
        let mut text = String::new();
        write_kv(&mut text, "UNITS", self.units.odb_units);
        let mut symbols = BTreeSetLike::default();
        if let Some(layer_name) = self.drill_layer_name.as_deref() {
            if let Some(layer) = self.feature_layers.get(layer_name) {
                for symbol in layer.symbols.values() {
                    symbols.insert(symbol.clone());
                }
            }
        }
        for (index, symbol) in symbols.into_vec().into_iter().enumerate() {
            let size = diameter_from_symbol(&symbol).unwrap_or(0.1);
            text.push_str("TOOLS {\n");
            write_kv(&mut text, "NUM", &(index + 1).to_string());
            write_kv(&mut text, "TYPE", "VIA");
            write_kv(&mut text, "TYPE2", "PLATED");
            write_kv(&mut text, "FINISH_SIZE", &fmt(size));
            write_kv(&mut text, "DRILL_SIZE", &fmt(size));
            text.push_str("}\n");
        }
        text
    }
}

#[derive(Debug, Clone)]
pub(super) struct MatrixLayer {
    pub(super) name: String,
    pub(super) context: String,
    pub(super) layer_type: String,
    pub(super) polarity: String,
    pub(super) side: Option<String>,
    pub(super) start_name: Option<String>,
    pub(super) end_name: Option<String>,
    pub(super) dielectric_type: Option<String>,
}

#[derive(Debug, Clone)]
struct LayerClassification {
    context: String,
    layer_type: String,
    side: Option<String>,
}

#[derive(Debug, Default)]
struct BTreeSetLike {
    values: BTreeMap<String, ()>,
}

impl BTreeSetLike {
    fn insert(&mut self, value: String) {
        self.values.insert(value, ());
    }

    fn into_vec(self) -> Vec<String> {
        self.values.into_keys().collect()
    }
}

fn classify_layer(layer: &SemanticLayer) -> LayerClassification {
    let text = format!(
        "{} {}",
        layer.role.as_deref().unwrap_or_default(),
        layer.layer_type.as_deref().unwrap_or_default()
    )
    .to_ascii_lowercase();
    let side = layer
        .side
        .as_deref()
        .and_then(layer_side_code)
        .map(ToOwned::to_owned)
        .or_else(|| layer_side_from_name(&layer.name));
    if text.contains("dielectric") || text.contains("prepreg") || text.contains("core") {
        return LayerClassification {
            context: "BOARD".to_string(),
            layer_type: "DIELECTRIC".to_string(),
            side: None,
        };
    }
    if text.contains("drill") {
        return LayerClassification {
            context: "BOARD".to_string(),
            layer_type: "DRILL".to_string(),
            side: None,
        };
    }
    if text.contains("mask") {
        return LayerClassification {
            context: "BOARD".to_string(),
            layer_type: "SOLDER_MASK".to_string(),
            side,
        };
    }
    if text.contains("paste") {
        return LayerClassification {
            context: "BOARD".to_string(),
            layer_type: "SOLDER_PASTE".to_string(),
            side,
        };
    }
    if text.contains("silk") {
        return LayerClassification {
            context: "BOARD".to_string(),
            layer_type: "SILK_SCREEN".to_string(),
            side,
        };
    }
    if text.contains("signal")
        || text.contains("plane")
        || text.contains("conductor")
        || text.contains("etch")
        || text.contains("metal")
        || text.contains("copper")
    {
        return LayerClassification {
            context: "BOARD".to_string(),
            layer_type: "SIGNAL".to_string(),
            side,
        };
    }
    LayerClassification {
        context: "MISC".to_string(),
        layer_type: "DOCUMENT".to_string(),
        side,
    }
}

fn layer_side_from_name(name: &str) -> Option<String> {
    let text = name.to_ascii_lowercase();
    if text.contains("top") || text.starts_with('f') {
        Some("TOP".to_string())
    } else if text.contains("bot") || text.contains("bottom") || text.starts_with('b') {
        Some("BOTTOM".to_string())
    } else {
        None
    }
}

fn layer_side_code(value: &str) -> Option<&'static str> {
    match value.to_ascii_lowercase().as_str() {
        "top" => Some("TOP"),
        "bottom" => Some("BOTTOM"),
        _ => None,
    }
}

pub(super) fn point_from_semantic(point: &SemanticPoint) -> Point {
    Point {
        x: point.x,
        y: point.y,
    }
}

fn symbol_for_width(width: f64) -> String {
    format!("r{}", fmt(width.max(0.0)))
}

fn symbol_for_shape(shape: &SemanticShape, units: UnitScale) -> String {
    let kind = if shape.auroradb_type.is_empty() {
        shape.kind.as_str()
    } else {
        shape.auroradb_type.as_str()
    }
    .replace('_', "")
    .to_ascii_lowercase();
    if kind == "circle" {
        let diameter = value_number(shape.values.get(2)).unwrap_or(0.1);
        return format!("r{}", fmt(units.length(diameter)));
    }
    if kind == "rectangle" || kind == "square" {
        let width = value_number(shape.values.get(2)).unwrap_or(0.1);
        let height = value_number(shape.values.get(3)).unwrap_or(width);
        return format!(
            "rect{}x{}",
            fmt(units.length(width)),
            fmt(units.length(height))
        );
    }
    if kind == "roundedrectangle" || kind == "oval" {
        let width = value_number(shape.values.get(2)).unwrap_or(0.1);
        let height = value_number(shape.values.get(3)).unwrap_or(width);
        let radius = value_number(shape.values.get(4)).unwrap_or(width.min(height) / 2.0);
        if radius > 0.0 {
            return format!(
                "rect{}x{}xr{}",
                fmt(units.length(width)),
                fmt(units.length(height)),
                fmt(units.length(radius))
            );
        }
        return format!(
            "rect{}x{}",
            fmt(units.length(width)),
            fmt(units.length(height))
        );
    }
    legal_symbol_name(
        shape
            .name
            .as_deref()
            .filter(|value| !value.trim().is_empty())
            .unwrap_or("r0.1"),
    )
}

fn geometry_point(value: &Value, key: &str) -> Option<Point> {
    let item = value.get(key)?;
    point_from_value(item)
}

fn geometry_points(value: &Value, key: &str) -> Vec<Point> {
    value
        .get(key)
        .and_then(Value::as_array)
        .map(|items| items.iter().filter_map(point_from_value).collect())
        .unwrap_or_default()
}

fn point_from_value(value: &Value) -> Option<Point> {
    if let Some(array) = value.as_array() {
        return Some(Point {
            x: value_number(array.first())?,
            y: value_number(array.get(1))?,
        });
    }
    if let Some(object) = value.as_object() {
        return Some(Point {
            x: object
                .get("x")
                .and_then(|value| value_number(Some(value)))?,
            y: object
                .get("y")
                .and_then(|value| value_number(Some(value)))?,
        });
    }
    None
}

fn geometry_number(value: &Value, key: &str) -> Option<f64> {
    value.get(key).and_then(|value| value_number(Some(value)))
}

fn geometry_bool(value: &Value, key: &str) -> Option<bool> {
    value.get(key).and_then(|value| {
        value.as_bool().or_else(|| {
            value.as_str().map(|text| {
                matches!(
                    text.to_ascii_lowercase().as_str(),
                    "1" | "true" | "yes" | "y"
                )
            })
        })
    })
}

fn geometry_string(value: &Value, key: &str) -> Option<String> {
    value.get(key).and_then(|value| {
        value
            .as_str()
            .map(ToOwned::to_owned)
            .or_else(|| value.as_i64().map(|number| number.to_string()))
            .or_else(|| value.as_u64().map(|number| number.to_string()))
    })
}

fn geometry_value<'a>(value: &'a Value, key: &str) -> Option<&'a Value> {
    value.get(key)
}

pub(super) fn value_number(value: Option<&Value>) -> Option<f64> {
    let value = value?;
    value.as_f64().or_else(|| {
        value
            .as_str()
            .and_then(|text| text.trim().split(';').next()?.parse::<f64>().ok())
    })
}

pub(super) fn polygon_points_from_values(values: &[Value], units: UnitScale) -> Vec<Point> {
    if values.is_empty() {
        return Vec::new();
    }
    let count = value_number(values.first())
        .and_then(|value| usize::try_from(value as i64).ok())
        .unwrap_or(values.len());
    values
        .iter()
        .skip(1)
        .take(count)
        .filter_map(|value| tuple_point(value).map(|point| units.point(point)))
        .collect()
}

fn tuple_point(value: &Value) -> Option<Point> {
    if let Some(point) = point_from_value(value) {
        return Some(point);
    }
    let text = value.as_str()?.trim().trim_matches('(').trim_matches(')');
    let parts: Vec<&str> = text.split(',').collect();
    if parts.len() < 2 {
        return None;
    }
    Some(Point {
        x: parts.first()?.trim().parse().ok()?,
        y: parts.get(1)?.trim().parse().ok()?,
    })
}

pub(super) fn rotation_to_odb_degrees(value: Option<&Value>, source_format: &str) -> f64 {
    let radians = value
        .and_then(|value| value_number(Some(value)))
        .unwrap_or(0.0);
    let degrees = radians.to_degrees();
    if source_format.eq_ignore_ascii_case("odbpp") {
        normalize_degrees(degrees)
    } else {
        normalize_degrees(360.0 - degrees)
    }
}

fn normalize_degrees(value: f64) -> f64 {
    let mut result = value % 360.0;
    if result < 0.0 {
        result += 360.0;
    }
    if (result - 360.0).abs() < 1e-9 {
        0.0
    } else {
        result
    }
}

fn diameter_from_symbol(symbol: &str) -> Option<f64> {
    let rest = symbol.strip_prefix('r')?;
    rest.parse::<f64>().ok()
}

fn prepare_output_root(root: &Path) -> Result<(), ExportError> {
    create_dir(root)?;
    for dirname in [
        "fonts", "input", "matrix", "misc", "steps", "symbols", "user", "wheels",
    ] {
        let path = root.join(dirname);
        if path.exists() {
            fs::remove_dir_all(&path).map_err(|source| ExportError::Write {
                path: path.display().to_string(),
                source,
            })?;
        }
    }
    Ok(())
}

fn create_dir(path: impl AsRef<Path>) -> Result<(), ExportError> {
    let path = path.as_ref();
    fs::create_dir_all(path).map_err(|source| ExportError::Write {
        path: path.display().to_string(),
        source,
    })
}

fn write_file(path: impl AsRef<Path>, text: String) -> Result<(), ExportError> {
    let path = path.as_ref();
    if let Some(parent) = path.parent() {
        create_dir(parent)?;
    }
    fs::write(path, text).map_err(|source| ExportError::Write {
        path: path.display().to_string(),
        source,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use aurora_odbpp_native::archive::{read_source, ReadSourceOptions};
    use aurora_odbpp_native::parser::{parse_odb_files, ParseOptions};
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn exports_parseable_odbpp_directory() {
        let board: SemanticBoard = serde_json::from_str(SAMPLE_SEMANTIC).unwrap();
        let root = temp_output_dir("parseable");
        let summary = export_semantic_board(&board, &root, &ExportOptions::default()).unwrap();
        assert_eq!(summary.units, "MM");
        assert_eq!(summary.component_count, 1);
        assert!(root.join("matrix").join("matrix").exists());
        assert!(root
            .join("steps")
            .join("pcb")
            .join("layers")
            .join("TOP")
            .join("features")
            .exists());

        let source = read_source(
            &root,
            &ReadSourceOptions {
                selected_step: Some("pcb".to_string()),
                include_details: true,
                max_entry_size_bytes: None,
            },
        )
        .unwrap();
        let parsed = parse_odb_files(
            &source.files,
            &ParseOptions {
                selected_step: Some("pcb".to_string()),
                include_details: true,
            },
        );
        assert_eq!(parsed.summary.step_count, 1);
        assert_eq!(parsed.summary.component_count, 1);
        assert_eq!(parsed.summary.net_count, 1);
        assert!(parsed.summary.feature_count >= 3);
        fs::remove_dir_all(root).ok();
    }

    #[test]
    fn converts_meters_to_mm() {
        let units = UnitScale::from_semantic_units(Some("m"));
        assert_eq!(units.odb_units, "MM");
        assert_eq!(fmt(units.length(0.001)), "1");
    }

    fn temp_output_dir(name: &str) -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("odbpp_exporter_{name}_{unique}"))
    }

    const SAMPLE_SEMANTIC: &str = r#"
{
  "metadata": {"source_format": "brd"},
  "units": "mm",
  "summary": {},
  "layers": [
    {"id": "layer_top", "name": "TOP", "role": "signal", "side": "top", "order_index": 0},
    {"id": "layer_bottom", "name": "BOTTOM", "role": "signal", "side": "bottom", "order_index": 1}
  ],
  "shapes": [
    {"id": "shape_round", "kind": "circle", "auroradb_type": "Circle", "values": [0, 0, 0.5]},
    {"id": "shape_rect", "kind": "rectangle", "auroradb_type": "Rectangle", "values": [0, 0, 0.6, 0.4]}
  ],
  "via_templates": [
    {
      "id": "via_template_1",
      "name": "via_0_3",
      "barrel_shape_id": "shape_round",
      "layer_pads": [
        {"layer_name": "TOP", "pad_shape_id": "shape_round"},
        {"layer_name": "BOTTOM", "pad_shape_id": "shape_round"}
      ]
    }
  ],
  "nets": [{"id": "net_1", "name": "N1"}],
  "footprints": [{"id": "fp_1", "name": "R0603", "pad_ids": ["fp_pad_1"]}],
  "components": [
    {
      "id": "comp_1",
      "refdes": "R1",
      "part_name": "R0603",
      "package_name": "R0603",
      "footprint_id": "fp_1",
      "side": "top",
      "location": {"x": 1.0, "y": 2.0},
      "pin_ids": ["pin_1"],
      "pad_ids": ["pad_1"]
    }
  ],
  "pins": [
    {"id": "pin_1", "name": "1", "component_id": "comp_1", "net_id": "net_1", "pad_ids": ["pad_1"], "position": {"x": 1.0, "y": 2.0}}
  ],
  "pads": [
    {"id": "fp_pad_1", "name": "1", "footprint_id": "fp_1", "position": {"x": 0.0, "y": 0.0}, "geometry": {"shape_id": "shape_rect"}},
    {"id": "pad_1", "name": "1", "component_id": "comp_1", "pin_id": "pin_1", "net_id": "net_1", "layer_name": "TOP", "position": {"x": 1.0, "y": 2.0}, "geometry": {"shape_id": "shape_rect"}}
  ],
  "vias": [
    {"id": "via_1", "template_id": "via_template_1", "net_id": "net_1", "layer_names": ["TOP", "BOTTOM"], "position": {"x": 3.0, "y": 4.0}}
  ],
  "primitives": [
    {"id": "trace_1", "kind": "trace", "layer_name": "TOP", "net_id": "net_1", "geometry": {"width": 0.2, "center_line": [[1.0, 2.0], [3.0, 4.0]]}}
  ],
  "board_outline": {"kind": "polygon", "auroradb_type": "Polygon", "values": [4, "(0,0)", "(5,0)", "(5,5)", "(0,5)", "Y", "Y"]}
}
"#;
}
