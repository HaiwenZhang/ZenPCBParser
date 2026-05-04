pub mod model;
pub mod parser;

use model::{AltiumLayout, Metadata};
use parser::{parse_altium_bytes, ParseOptions, ParsedAltium};
#[cfg(feature = "python")]
use pyo3::exceptions::PyRuntimeError;
#[cfg(feature = "python")]
use pyo3::prelude::*;
#[cfg(feature = "python")]
use pythonize::pythonize;
use std::fs;
use std::path::PathBuf;

pub const RUST_PARSER_VERSION: &str = env!("CARGO_PKG_VERSION");
pub const BACKEND_CLI: &str = "rust-cli";
pub const BACKEND_NATIVE: &str = "rust-native";

#[derive(Debug, Clone)]
pub struct BuildPayloadOptions {
    pub source: PathBuf,
    pub include_details: bool,
    pub project_version: String,
    pub parser_version: String,
    pub schema_version: String,
    pub backend: String,
}

pub fn build_payload(options: &BuildPayloadOptions) -> Result<AltiumLayout, String> {
    let bytes = fs::read(&options.source).map_err(|error| {
        format!(
            "failed to read Altium PCB file {}: {error}",
            options.source.display()
        )
    })?;
    let parsed = parse_altium_bytes(
        &bytes,
        &ParseOptions {
            include_details: options.include_details,
        },
    )
    .map_err(|error| error.to_string())?;
    Ok(layout_from_parsed(options, parsed))
}

fn layout_from_parsed(options: &BuildPayloadOptions, mut parsed: ParsedAltium) -> AltiumLayout {
    parsed.summary.diagnostic_count = parsed.diagnostics.len();
    AltiumLayout {
        metadata: Metadata {
            project_version: options.project_version.clone(),
            parser_version: options.parser_version.clone(),
            output_schema_version: options.schema_version.clone(),
            source: options
                .source
                .canonicalize()
                .unwrap_or_else(|_| options.source.clone())
                .display()
                .to_string(),
            source_type: "file".to_string(),
            backend: options.backend.clone(),
            rust_parser_version: RUST_PARSER_VERSION.to_string(),
        },
        summary: parsed.summary,
        file_header: parsed.file_header,
        board: parsed.board,
        layers: parsed.layers,
        nets: parsed.nets,
        classes: parsed.classes,
        rules: parsed.rules,
        polygons: parsed.polygons,
        components: parsed.components,
        pads: parsed.pads,
        vias: parsed.vias,
        tracks: parsed.tracks,
        arcs: parsed.arcs,
        fills: parsed.fills,
        regions: parsed.regions,
        texts: parsed.texts,
        streams: parsed.streams,
        stream_counts: parsed.stream_counts,
        diagnostics: parsed.diagnostics,
    }
}

#[cfg(feature = "python")]
#[pyfunction(signature = (source_path, *, include_details=true, project_version, parser_version, schema_version))]
fn parse_altium(
    py: Python<'_>,
    source_path: String,
    include_details: bool,
    project_version: String,
    parser_version: String,
    schema_version: String,
) -> PyResult<Py<PyAny>> {
    let payload = build_payload(&BuildPayloadOptions {
        source: PathBuf::from(source_path),
        include_details,
        project_version,
        parser_version,
        schema_version,
        backend: BACKEND_NATIVE.to_string(),
    })
    .map_err(PyRuntimeError::new_err)?;
    let object =
        pythonize(py, &payload).map_err(|error| PyRuntimeError::new_err(error.to_string()))?;
    Ok(object.unbind())
}

#[pyfunction]
#[cfg(feature = "python")]
fn rust_parser_version() -> &'static str {
    RUST_PARSER_VERSION
}

#[pyfunction]
#[cfg(feature = "python")]
fn backend_name() -> &'static str {
    BACKEND_NATIVE
}

#[cfg(feature = "python")]
#[pymodule]
fn aurora_altium_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_altium, m)?)?;
    m.add_function(wrap_pyfunction!(rust_parser_version, m)?)?;
    m.add_function(wrap_pyfunction!(backend_name, m)?)?;
    m.add("__version__", RUST_PARSER_VERSION)?;
    m.add("BACKEND", BACKEND_NATIVE)?;
    Ok(())
}
