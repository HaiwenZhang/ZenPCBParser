use super::attributes::empty_feature_attribute_tables_text;
use super::formatting::{fmt, write_id, write_kv};
use super::model::Point;
use std::collections::{BTreeMap, HashMap};

#[derive(Debug, Clone)]
pub(super) struct FeatureLayer {
    pub(super) name: String,
    pub(super) symbols: BTreeMap<usize, String>,
    symbol_indices: HashMap<String, usize>,
    pub(super) features: Vec<FeatureRecord>,
}

impl FeatureLayer {
    pub(super) fn new(name: String) -> Self {
        Self {
            name,
            symbols: BTreeMap::new(),
            symbol_indices: HashMap::new(),
            features: Vec::new(),
        }
    }

    pub(super) fn symbol_index(&mut self, symbol: String) -> usize {
        if let Some(index) = self.symbol_indices.get(&symbol) {
            return *index;
        }
        let index = self.symbols.len();
        self.symbols.insert(index, symbol.clone());
        self.symbol_indices.insert(symbol, index);
        index
    }

    pub(super) fn push(&mut self, feature: FeatureRecord) -> usize {
        let index = self.features.len();
        self.features.push(feature);
        index
    }

    pub(super) fn to_features_text(&self, units: &str) -> String {
        let mut text = String::new();
        write_kv(&mut text, "UNITS", units);
        text.push_str("#\n#Num Features\n#\n");
        text.push_str(&format!("F {}\n\n", self.features.len()));
        if self.features.is_empty() {
            return text;
        }
        text.push_str("#\n#Feature symbol names\n#\n");
        for (index, symbol) in &self.symbols {
            text.push_str(&format!("${} {}\n", index, symbol));
        }
        text.push_str(&empty_feature_attribute_tables_text());
        text.push_str("#\n#Layer features\n#\n");
        for feature in &self.features {
            feature.write(&mut text);
        }
        text
    }
}

#[derive(Debug, Clone)]
pub(super) enum FeatureRecord {
    Pad {
        center: Point,
        symbol: usize,
        rotation: f64,
        mirror: bool,
        id: Option<String>,
    },
    Line {
        start: Point,
        end: Point,
        symbol: usize,
        id: Option<String>,
    },
    Arc {
        start: Point,
        end: Point,
        center: Point,
        symbol: usize,
        clockwise: bool,
        id: Option<String>,
    },
    Surface {
        contours: Vec<SurfaceContourOut>,
        id: Option<String>,
    },
}

impl FeatureRecord {
    pub(super) fn write(&self, text: &mut String) {
        match self {
            FeatureRecord::Pad {
                center,
                symbol,
                rotation,
                mirror,
                id,
            } => {
                text.push_str(&format!(
                    "P {} {} {} P 0 {} {}",
                    fmt(center.x),
                    fmt(center.y),
                    symbol,
                    if *mirror { "9" } else { "8" },
                    fmt(*rotation)
                ));
                write_id(text, id);
                text.push('\n');
            }
            FeatureRecord::Line {
                start,
                end,
                symbol,
                id,
            } => {
                text.push_str(&format!(
                    "L {} {} {} {} {} P 0",
                    fmt(start.x),
                    fmt(start.y),
                    fmt(end.x),
                    fmt(end.y),
                    symbol
                ));
                write_id(text, id);
                text.push('\n');
            }
            FeatureRecord::Arc {
                start,
                end,
                center,
                symbol,
                clockwise,
                id,
            } => {
                text.push_str(&format!(
                    "A {} {} {} {} {} {} {} P 0 {}",
                    fmt(start.x),
                    fmt(start.y),
                    fmt(end.x),
                    fmt(end.y),
                    fmt(center.x),
                    fmt(center.y),
                    symbol,
                    if *clockwise { "Y" } else { "N" }
                ));
                write_id(text, id);
                text.push('\n');
            }
            FeatureRecord::Surface { contours, id } => {
                text.push_str("S P 0");
                write_id(text, id);
                text.push('\n');
                write_surface_contours(text, contours);
                text.push_str("SE\n");
            }
        }
    }

    pub(super) fn extend_extents(&self, extents: &mut Extents) {
        match self {
            FeatureRecord::Pad { center, .. } => extents.add(*center),
            FeatureRecord::Line { start, end, .. } => {
                extents.add(*start);
                extents.add(*end);
            }
            FeatureRecord::Arc {
                start, end, center, ..
            } => {
                extents.add(*start);
                extents.add(*end);
                extents.add(*center);
            }
            FeatureRecord::Surface { contours, .. } => {
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

#[derive(Debug, Clone)]
pub(super) struct SurfaceContourOut {
    pub(super) polarity: String,
    pub(super) vertices: Vec<SurfaceVertex>,
}

#[derive(Debug, Clone)]
pub(super) enum SurfaceVertex {
    Line(Point),
    #[allow(dead_code)]
    Arc {
        end: Point,
        center: Point,
        clockwise: bool,
    },
}

#[derive(Debug, Default)]
pub(super) struct Extents {
    min_x: f64,
    min_y: f64,
    max_x: f64,
    max_y: f64,
    found: bool,
}

impl Extents {
    pub(super) fn add(&mut self, point: Point) {
        if !point.x.is_finite() || !point.y.is_finite() {
            return;
        }
        if !self.found {
            self.min_x = point.x;
            self.min_y = point.y;
            self.max_x = point.x;
            self.max_y = point.y;
            self.found = true;
            return;
        }
        self.min_x = self.min_x.min(point.x);
        self.min_y = self.min_y.min(point.y);
        self.max_x = self.max_x.max(point.x);
        self.max_y = self.max_y.max(point.y);
    }

    pub(super) fn bounds(&self) -> Option<(Point, Point)> {
        self.found.then_some((
            Point {
                x: self.min_x,
                y: self.min_y,
            },
            Point {
                x: self.max_x,
                y: self.max_y,
            },
        ))
    }
}

pub(super) fn write_surface_contours(text: &mut String, contours: &[SurfaceContourOut]) {
    for contour in contours {
        let Some(first) = contour.vertices.first() else {
            continue;
        };
        let first_point = match first {
            SurfaceVertex::Line(point) => *point,
            SurfaceVertex::Arc { end, .. } => *end,
        };
        text.push_str(&format!(
            "OB {} {} {}\n",
            fmt(first_point.x),
            fmt(first_point.y),
            contour.polarity
        ));
        for vertex in contour.vertices.iter().skip(1) {
            match vertex {
                SurfaceVertex::Line(point) => {
                    text.push_str(&format!("OS {} {}\n", fmt(point.x), fmt(point.y)));
                }
                SurfaceVertex::Arc {
                    end,
                    center,
                    clockwise,
                } => {
                    text.push_str(&format!(
                        "OC {} {} {} {} {}\n",
                        fmt(end.x),
                        fmt(end.y),
                        fmt(center.x),
                        fmt(center.y),
                        if *clockwise { "Y" } else { "N" }
                    ));
                }
            }
        }
        text.push_str("OE\n");
    }
}
