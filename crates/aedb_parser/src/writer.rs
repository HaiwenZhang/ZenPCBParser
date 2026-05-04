use crate::parser::{DefRecord, ParsedDef};
use std::fs;
use std::io::Write;
use std::path::Path;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum WriteError {
    #[error("failed to create parent directory {path}: {source}")]
    CreateParent {
        path: String,
        #[source]
        source: std::io::Error,
    },
    #[error("failed to write AEDB DEF file {path}: {source}")]
    Write {
        path: String,
        #[source]
        source: std::io::Error,
    },
    #[error("AEDB DEF text record is too large to write: {length} bytes")]
    TextRecordTooLarge { length: usize },
}

pub fn write_def_file(parsed: &ParsedDef, output: &Path) -> Result<(), WriteError> {
    if let Some(parent) = output.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent).map_err(|source| WriteError::CreateParent {
                path: parent.display().to_string(),
                source,
            })?;
        }
    }

    let mut bytes = Vec::with_capacity(parsed.source_bytes.len());
    write_def_bytes(parsed, &mut bytes)?;
    fs::write(output, bytes).map_err(|source| WriteError::Write {
        path: output.display().to_string(),
        source,
    })
}

pub fn write_def_bytes(parsed: &ParsedDef, output: &mut Vec<u8>) -> Result<(), WriteError> {
    for record in &parsed.records {
        match record {
            DefRecord::Text(text) => {
                let length = u32::try_from(text.raw_text.len()).map_err(|_| {
                    WriteError::TextRecordTooLarge {
                        length: text.raw_text.len(),
                    }
                })?;
                output
                    .write_all(&[text.tag])
                    .map_err(|source| WriteError::Write {
                        path: "<memory>".to_string(),
                        source,
                    })?;
                output
                    .write_all(&length.to_le_bytes())
                    .map_err(|source| WriteError::Write {
                        path: "<memory>".to_string(),
                        source,
                    })?;
                output
                    .write_all(&text.raw_text)
                    .map_err(|source| WriteError::Write {
                        path: "<memory>".to_string(),
                        source,
                    })?;
            }
            DefRecord::Binary(binary) => {
                output
                    .write_all(&binary.bytes)
                    .map_err(|source| WriteError::Write {
                        path: "<memory>".to_string(),
                        source,
                    })?;
            }
        }
    }
    Ok(())
}
