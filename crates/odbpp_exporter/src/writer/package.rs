use super::entity::{point_from_semantic, polygon_points_from_values, value_number, OdbPackage};
use super::features::{write_surface_contours, Extents, SurfaceContourOut, SurfaceVertex};
use super::formatting::{fmt, legal_scalar};
use super::model::{Point, SemanticPad, SemanticShape, UnitScale};
use serde_json::Value;
use std::collections::HashMap;

impl<'a> OdbPackage<'a> {
    pub(super) fn build_packages(&mut self) {
        let pad_by_id: HashMap<&str, &SemanticPad> = self
            .board
            .pads
            .iter()
            .map(|pad| (pad.id.as_str(), pad))
            .collect();

        for footprint in &self.board.footprints {
            let mut pins = Vec::new();
            for pad_id in &footprint.pad_ids {
                let Some(pad) = pad_by_id.get(pad_id.as_str()).copied() else {
                    continue;
                };
                if pad.component_id.is_some() {
                    continue;
                }
                pins.push(self.package_pin_from_pad(pad));
            }
            if pins.is_empty() {
                for pad in self
                    .board
                    .pads
                    .iter()
                    .filter(|pad| pad.footprint_id.as_deref() == Some(footprint.id.as_str()))
                    .filter(|pad| pad.component_id.is_none())
                {
                    pins.push(self.package_pin_from_pad(pad));
                }
            }
            let outlines = footprint_outlines(&footprint.geometry, self.units);
            let bounds = package_bounds(&pins, &outlines).unwrap_or(PackageBounds {
                min: Point { x: -0.5, y: -0.5 },
                max: Point { x: 0.5, y: 0.5 },
            });
            let index = self.packages.len();
            let name = legal_scalar(
                footprint
                    .part_name
                    .as_deref()
                    .unwrap_or(footprint.name.as_str()),
            );
            self.package_index_by_footprint_id
                .insert(footprint.id.clone(), index);
            self.package_index_by_name
                .entry(footprint.name.to_ascii_lowercase())
                .or_insert(index);
            let pitch = package_pitch(&pins).unwrap_or(1.0);
            self.packages.push(PackageOut {
                index,
                name,
                pitch,
                bounds,
                outlines,
                pins,
            });
        }
    }

    pub(super) fn package_pin_from_pad(&self, pad: &SemanticPad) -> PackagePinOut {
        let position = pad
            .position
            .as_ref()
            .map(point_from_semantic)
            .map(|point| self.units.point(point))
            .unwrap_or_default();
        let shape = self
            .shape_for_pad(pad)
            .map(|shape| package_shape_from_shape(shape, position, self.units))
            .unwrap_or_else(|| PackageShapeOut::Circle {
                center: position,
                radius: 0.05,
            });
        PackagePinOut {
            name: legal_scalar(pad.name.as_deref().unwrap_or(pad.id.as_str())),
            position,
            rotation: 0.0,
            electrical_type: "E".to_string(),
            mount_type: "S".to_string(),
            shapes: vec![shape],
        }
    }
}

#[derive(Debug, Clone)]
pub(super) struct PackageOut {
    pub(super) index: usize,
    pub(super) name: String,
    pub(super) pitch: f64,
    pub(super) bounds: PackageBounds,
    pub(super) outlines: Vec<PackageShapeOut>,
    pub(super) pins: Vec<PackagePinOut>,
}

#[derive(Debug, Clone, Copy)]
pub(super) struct PackageBounds {
    pub(super) min: Point,
    pub(super) max: Point,
}

#[derive(Debug, Clone)]
pub(super) struct PackagePinOut {
    pub(super) name: String,
    pub(super) position: Point,
    pub(super) rotation: f64,
    pub(super) electrical_type: String,
    pub(super) mount_type: String,
    pub(super) shapes: Vec<PackageShapeOut>,
}

#[derive(Debug, Clone)]
pub(super) enum PackageShapeOut {
    Rect {
        lower_left: Point,
        width: f64,
        height: f64,
    },
    Circle {
        center: Point,
        radius: f64,
    },
    Contour {
        contours: Vec<SurfaceContourOut>,
    },
}

impl PackageShapeOut {
    pub(super) fn write_package_shape(&self, text: &mut String) {
        match self {
            PackageShapeOut::Rect {
                lower_left,
                width,
                height,
            } => text.push_str(&format!(
                "RC {} {} {} {}\n",
                fmt(lower_left.x),
                fmt(lower_left.y),
                fmt(*width),
                fmt(*height)
            )),
            PackageShapeOut::Circle { center, radius } => text.push_str(&format!(
                "CR {} {} {}\n",
                fmt(center.x),
                fmt(center.y),
                fmt(*radius)
            )),
            PackageShapeOut::Contour { contours } => {
                text.push_str("CT\n");
                write_surface_contours(text, contours);
                text.push_str("CE\n");
            }
        }
    }

    pub(super) fn extend_extents(&self, extents: &mut Extents) {
        match self {
            PackageShapeOut::Rect {
                lower_left,
                width,
                height,
            } => {
                extents.add(*lower_left);
                extents.add(Point {
                    x: lower_left.x + width,
                    y: lower_left.y + height,
                });
            }
            PackageShapeOut::Circle { center, radius } => {
                extents.add(Point {
                    x: center.x - radius,
                    y: center.y - radius,
                });
                extents.add(Point {
                    x: center.x + radius,
                    y: center.y + radius,
                });
            }
            PackageShapeOut::Contour { contours } => {
                for contour in contours {
                    for vertex in &contour.vertices {
                        match vertex {
                            SurfaceVertex::Line(point) => extents.add(*point),
                            SurfaceVertex::Arc { end, center, .. } => {
                                extents.add(*end);
                                extents.add(*center);
                            }
                        }
                    }
                }
            }
        }
    }
}

pub(super) fn package_shape_from_shape(
    shape: &SemanticShape,
    center: Point,
    units: UnitScale,
) -> PackageShapeOut {
    let kind = if shape.auroradb_type.is_empty() {
        shape.kind.as_str()
    } else {
        shape.auroradb_type.as_str()
    }
    .replace('_', "")
    .to_ascii_lowercase();
    let offset = Point {
        x: units.length(value_number(shape.values.first()).unwrap_or(0.0)),
        y: units.length(value_number(shape.values.get(1)).unwrap_or(0.0)),
    };
    let shape_center = Point {
        x: center.x + offset.x,
        y: center.y + offset.y,
    };
    if kind == "circle" {
        let diameter = units.length(value_number(shape.values.get(2)).unwrap_or(0.1));
        return PackageShapeOut::Circle {
            center: shape_center,
            radius: diameter / 2.0,
        };
    }
    if kind == "polygon" {
        let points = polygon_points_from_values(&shape.values, units)
            .into_iter()
            .map(|point| Point {
                x: point.x + center.x,
                y: point.y + center.y,
            })
            .collect::<Vec<_>>();
        if points.len() >= 3 {
            return PackageShapeOut::Contour {
                contours: vec![SurfaceContourOut {
                    polarity: "I".to_string(),
                    vertices: points.into_iter().map(SurfaceVertex::Line).collect(),
                }],
            };
        }
    }
    let width = units.length(value_number(shape.values.get(2)).unwrap_or(0.1));
    let height = units.length(value_number(shape.values.get(3)).unwrap_or(width));
    PackageShapeOut::Rect {
        lower_left: Point {
            x: shape_center.x - width / 2.0,
            y: shape_center.y - height / 2.0,
        },
        width,
        height,
    }
}

fn footprint_outlines(value: &Value, units: UnitScale) -> Vec<PackageShapeOut> {
    let Some(outlines) = value.get("outlines").and_then(Value::as_array) else {
        return Vec::new();
    };
    let mut result = Vec::new();
    for outline in outlines {
        if let Some(values) = outline.get("values").and_then(Value::as_array) {
            let points = polygon_points_from_values(values, units);
            if points.len() >= 3 {
                result.push(PackageShapeOut::Contour {
                    contours: vec![SurfaceContourOut {
                        polarity: "I".to_string(),
                        vertices: points.into_iter().map(SurfaceVertex::Line).collect(),
                    }],
                });
            }
        }
    }
    result
}

fn package_bounds(pins: &[PackagePinOut], outlines: &[PackageShapeOut]) -> Option<PackageBounds> {
    let mut extents = Extents::default();
    for outline in outlines {
        outline.extend_extents(&mut extents);
    }
    for pin in pins {
        extents.add(pin.position);
        for shape in &pin.shapes {
            shape.extend_extents(&mut extents);
        }
    }
    let (min, max) = extents.bounds()?;
    Some(PackageBounds { min, max })
}

fn package_pitch(pins: &[PackagePinOut]) -> Option<f64> {
    if pins.len() < 2 {
        return None;
    }
    let mut pitch = f64::INFINITY;
    for (index, left) in pins.iter().enumerate() {
        for right in pins.iter().skip(index + 1) {
            let dx = left.position.x - right.position.x;
            let dy = left.position.y - right.position.y;
            pitch = pitch.min((dx * dx + dy * dy).sqrt());
        }
    }
    pitch.is_finite().then_some(pitch)
}
