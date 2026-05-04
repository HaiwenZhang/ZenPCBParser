pub mod archive;
pub mod model;
pub mod parser;

use archive::{read_source, OdbSource, ReadSourceOptions};
use model::{Metadata, OdbLayout};
use parser::{parse_odb_files, ParseOptions, ParsedOdb};
#[cfg(feature = "python")]
use pyo3::exceptions::PyRuntimeError;
#[cfg(feature = "python")]
use pyo3::prelude::*;
#[cfg(feature = "python")]
use pythonize::pythonize;
use std::path::PathBuf;

pub const RUST_PARSER_VERSION: &str = env!("CARGO_PKG_VERSION");
pub const BACKEND_CLI: &str = "rust-cli";
pub const BACKEND_NATIVE: &str = "rust-native";

#[derive(Debug, Clone)]
pub struct BuildPayloadOptions {
    pub source: PathBuf,
    pub step: Option<String>,
    pub include_details: bool,
    pub project_version: String,
    pub parser_version: String,
    pub schema_version: String,
    pub backend: String,
}

pub fn build_payload(options: &BuildPayloadOptions) -> Result<OdbLayout, String> {
    let (source, parsed) = read_and_parse_source(options)?;

    let mut diagnostics = source.diagnostics;
    diagnostics.extend(parsed.diagnostics);
    let mut summary = parsed.summary;
    summary.diagnostic_count = diagnostics.len();

    Ok(OdbLayout {
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
            source_type: source.source_type,
            selected_step: parsed.selected_step,
            backend: options.backend.clone(),
            rust_parser_version: RUST_PARSER_VERSION.to_string(),
        },
        summary,
        matrix: parsed.matrix,
        steps: parsed.steps,
        symbols: parsed.symbols,
        drill_tools: parsed.drill_tools,
        packages: parsed.packages,
        layers: parsed.layers,
        components: parsed.components,
        nets: parsed.nets,
        diagnostics,
    })
}

fn read_and_parse_source(options: &BuildPayloadOptions) -> Result<(OdbSource, ParsedOdb), String> {
    if options.include_details && options.step.is_none() {
        let (_summary_source, summary) =
            read_and_parse_once(options, None, false).map_err(|error| error.to_string())?;
        if let Some(selected_step) = summary.selected_step {
            return read_and_parse_once(options, Some(selected_step), true)
                .map_err(|error| error.to_string());
        }
    }

    read_and_parse_once(options, options.step.clone(), options.include_details)
        .map_err(|error| error.to_string())
}

fn read_and_parse_once(
    options: &BuildPayloadOptions,
    selected_step: Option<String>,
    include_details: bool,
) -> Result<(OdbSource, ParsedOdb), String> {
    let source = read_source(
        &options.source,
        &ReadSourceOptions {
            selected_step: selected_step.clone(),
            include_details,
            max_entry_size_bytes: None,
        },
    )
    .map_err(|error| error.to_string())?;
    let parsed = parse_odb_files(
        &source.files,
        &ParseOptions {
            selected_step,
            include_details,
        },
    );
    Ok((source, parsed))
}

#[cfg(feature = "python")]
#[pyfunction(signature = (source_path, *, step=None, include_details=true, project_version, parser_version, schema_version))]
fn parse_odbpp(
    py: Python<'_>,
    source_path: String,
    step: Option<String>,
    include_details: bool,
    project_version: String,
    parser_version: String,
    schema_version: String,
) -> PyResult<Py<PyAny>> {
    let payload = build_payload(&BuildPayloadOptions {
        source: PathBuf::from(source_path),
        step,
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
fn aurora_odbpp_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_odbpp, m)?)?;
    m.add_function(wrap_pyfunction!(rust_parser_version, m)?)?;
    m.add_function(wrap_pyfunction!(backend_name, m)?)?;
    m.add("__version__", RUST_PARSER_VERSION)?;
    m.add("BACKEND", BACKEND_NATIVE)?;
    Ok(())
}
