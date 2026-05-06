use crate::model::{DslBlockSummary, RecordSummary, Summary};
use std::fs;
use std::path::Path;
use thiserror::Error;

const TEXT_HEADER_SIZE: usize = 5;
const TEXT_BEGIN: &[u8] = b"$begin '";

#[derive(Debug, Error)]
pub enum ParseError {
    #[error("failed to read AEDB DEF file {path}: {source}")]
    Read {
        path: String,
        #[source]
        source: std::io::Error,
    },
    #[error("AEDB DEF text record at offset {offset} is too large: {length} bytes")]
    TextRecordTooLarge { offset: usize, length: usize },
}

#[derive(Debug, Clone, Default)]
pub struct ParseOptions {
    pub include_details: bool,
}

#[derive(Debug, Clone)]
pub struct ParsedDef {
    pub source_bytes: Vec<u8>,
    pub records: Vec<DefRecord>,
    pub record_summaries: Vec<RecordSummary>,
    pub block_summaries: Vec<DslBlockSummary>,
    pub summary: Summary,
    pub diagnostics: Vec<String>,
}

#[derive(Debug, Clone)]
pub enum DefRecord {
    Text(TextRecord),
    Binary(BinaryRecord),
}

#[derive(Debug, Clone)]
pub struct TextRecord {
    pub offset: usize,
    pub tag: u8,
    pub raw_text: Vec<u8>,
    pub text: String,
    pub valid_utf8: bool,
}

#[derive(Debug, Clone)]
pub struct BinaryRecord {
    pub offset: usize,
    pub bytes: Vec<u8>,
}

#[derive(Debug, Clone, Default)]
struct TextAnalysis {
    blocks: Vec<DslBlockSummary>,
    first_block_name: Option<String>,
    line_count: usize,
    assignment_line_count: usize,
    function_line_count: usize,
    other_line_count: usize,
    diagnostics: Vec<String>,
}

#[derive(Debug, Clone)]
struct OpenBlock {
    summary_index: usize,
    name: String,
}

pub fn parse_def_file(path: &Path, options: &ParseOptions) -> Result<ParsedDef, ParseError> {
    let bytes = fs::read(path).map_err(|source| ParseError::Read {
        path: path.display().to_string(),
        source,
    })?;
    parse_def_bytes(bytes, options)
}

pub fn parse_def_bytes(bytes: Vec<u8>, options: &ParseOptions) -> Result<ParsedDef, ParseError> {
    let records = scan_records(&bytes)?;
    let mut record_summaries = Vec::new();
    let mut block_summaries = Vec::new();
    let mut diagnostics = Vec::new();
    let mut summary = Summary {
        file_size_bytes: bytes.len(),
        record_count: records.len(),
        ..Summary::default()
    };

    for (index, record) in records.iter().enumerate() {
        match record {
            DefRecord::Text(text_record) => {
                summary.text_record_count += 1;
                summary.text_payload_bytes += text_record.raw_text.len();
                let analysis = analyze_text_record(index, &text_record.text);
                if summary.def_version.is_none() || summary.encrypted.is_none() {
                    extract_header_fields(&text_record.text, &mut summary);
                }
                summary.dsl_block_count += analysis.blocks.len();
                summary.top_level_block_count += analysis
                    .blocks
                    .iter()
                    .filter(|block| block.depth == 0)
                    .count();
                summary.assignment_line_count += analysis.assignment_line_count;
                summary.function_line_count += analysis.function_line_count;
                summary.other_line_count += analysis.other_line_count;
                diagnostics.extend(analysis.diagnostics.clone());
                if options.include_details {
                    block_summaries.extend(analysis.blocks.clone());
                }
                record_summaries.push(RecordSummary {
                    index,
                    kind: "text".to_string(),
                    offset: text_record.offset,
                    end_offset: text_record.end_offset(),
                    total_size: TEXT_HEADER_SIZE + text_record.raw_text.len(),
                    tag: Some(text_record.tag),
                    payload_size: text_record.raw_text.len(),
                    payload_hash: fnv1a64_hex(&text_record.raw_text),
                    valid_utf8: Some(text_record.valid_utf8),
                    line_count: Some(analysis.line_count),
                    first_block_name: analysis.first_block_name,
                    block_count: Some(analysis.blocks.len()),
                    assignment_line_count: Some(analysis.assignment_line_count),
                    function_line_count: Some(analysis.function_line_count),
                    other_line_count: Some(analysis.other_line_count),
                });
            }
            DefRecord::Binary(binary_record) => {
                summary.binary_record_count += 1;
                summary.binary_bytes += binary_record.bytes.len();
                record_summaries.push(RecordSummary {
                    index,
                    kind: "binary".to_string(),
                    offset: binary_record.offset,
                    end_offset: binary_record.end_offset(),
                    total_size: binary_record.bytes.len(),
                    tag: None,
                    payload_size: binary_record.bytes.len(),
                    payload_hash: fnv1a64_hex(&binary_record.bytes),
                    valid_utf8: None,
                    line_count: None,
                    first_block_name: None,
                    block_count: None,
                    assignment_line_count: None,
                    function_line_count: None,
                    other_line_count: None,
                });
            }
        }
    }

    summary.diagnostic_count = diagnostics.len();

    Ok(ParsedDef {
        source_bytes: bytes,
        records,
        record_summaries: if options.include_details {
            record_summaries
        } else {
            Vec::new()
        },
        block_summaries: if options.include_details {
            block_summaries
        } else {
            Vec::new()
        },
        summary,
        diagnostics,
    })
}

fn scan_records(bytes: &[u8]) -> Result<Vec<DefRecord>, ParseError> {
    let mut records = Vec::new();
    let mut offset = 0;
    while offset < bytes.len() {
        if let Some((tag, length)) = text_record_at(bytes, offset)? {
            let payload_start = offset + TEXT_HEADER_SIZE;
            let payload_end = payload_start + length;
            let raw_text = bytes[payload_start..payload_end].to_vec();
            let (text, valid_utf8) = match String::from_utf8(raw_text.clone()) {
                Ok(value) => (value, true),
                Err(error) => (
                    String::from_utf8_lossy(error.as_bytes()).into_owned(),
                    false,
                ),
            };
            records.push(DefRecord::Text(TextRecord {
                offset,
                tag,
                raw_text,
                text,
                valid_utf8,
            }));
            offset = payload_end;
            continue;
        }

        let next = find_next_text_record(bytes, offset)?;
        let end = next.unwrap_or(bytes.len());
        records.push(DefRecord::Binary(BinaryRecord {
            offset,
            bytes: bytes[offset..end].to_vec(),
        }));
        offset = end;
    }
    Ok(records)
}

fn find_next_text_record(bytes: &[u8], start: usize) -> Result<Option<usize>, ParseError> {
    if bytes.len().saturating_sub(start) < TEXT_HEADER_SIZE + TEXT_BEGIN.len() {
        return Ok(None);
    }
    for offset in start..=bytes.len() - TEXT_HEADER_SIZE - TEXT_BEGIN.len() {
        if text_record_at(bytes, offset)?.is_some() {
            return Ok(Some(offset));
        }
    }
    Ok(None)
}

fn text_record_at(bytes: &[u8], offset: usize) -> Result<Option<(u8, usize)>, ParseError> {
    if offset + TEXT_HEADER_SIZE + TEXT_BEGIN.len() > bytes.len() {
        return Ok(None);
    }
    let length = u32::from_le_bytes([
        bytes[offset + 1],
        bytes[offset + 2],
        bytes[offset + 3],
        bytes[offset + 4],
    ]) as usize;
    let payload_start = offset + TEXT_HEADER_SIZE;
    let payload_end = payload_start + length;
    if payload_end > bytes.len() {
        if bytes[payload_start..].starts_with(TEXT_BEGIN) {
            return Err(ParseError::TextRecordTooLarge { offset, length });
        }
        return Ok(None);
    }
    if length >= TEXT_BEGIN.len() && bytes[payload_start..].starts_with(TEXT_BEGIN) {
        Ok(Some((bytes[offset], length)))
    } else {
        Ok(None)
    }
}

fn analyze_text_record(record_index: usize, text: &str) -> TextAnalysis {
    let mut analysis = TextAnalysis::default();
    let mut stack: Vec<OpenBlock> = Vec::new();

    for (line_index, raw_line) in text.lines().enumerate() {
        analysis.line_count += 1;
        let line_number = line_index + 1;
        let trimmed = raw_line.trim();
        if trimmed.is_empty() {
            continue;
        }

        if let Some(name) = parse_begin(trimmed) {
            let depth = stack.len();
            let mut path_parts: Vec<String> =
                stack.iter().map(|block| block.name.clone()).collect();
            path_parts.push(name.clone());
            let path = path_parts.join("/");
            let summary_index = analysis.blocks.len();
            if analysis.first_block_name.is_none() {
                analysis.first_block_name = Some(name.clone());
            }
            analysis.blocks.push(DslBlockSummary {
                record_index,
                name: name.clone(),
                path,
                depth,
                start_line: line_number,
                end_line: None,
                assignment_line_count: 0,
                function_line_count: 0,
                other_line_count: 0,
            });
            stack.push(OpenBlock {
                summary_index,
                name,
            });
            continue;
        }

        if let Some(name) = parse_end(trimmed) {
            match stack.pop() {
                Some(open) if open.name == name => {
                    analysis.blocks[open.summary_index].end_line = Some(line_number);
                }
                Some(open) => {
                    analysis.blocks[open.summary_index].end_line = Some(line_number);
                    analysis.diagnostics.push(format!(
                        "record {record_index} line {line_number}: mismatched end block {name:?}, expected {:?}",
                        open.name
                    ));
                }
                None => analysis.diagnostics.push(format!(
                    "record {record_index} line {line_number}: end block {name:?} without matching begin"
                )),
            }
            continue;
        }

        let kind = classify_line(trimmed);
        match kind {
            LineKind::Assignment => analysis.assignment_line_count += 1,
            LineKind::Function => analysis.function_line_count += 1,
            LineKind::Other => analysis.other_line_count += 1,
        }
        if let Some(open) = stack.last() {
            let block = &mut analysis.blocks[open.summary_index];
            match kind {
                LineKind::Assignment => block.assignment_line_count += 1,
                LineKind::Function => block.function_line_count += 1,
                LineKind::Other => block.other_line_count += 1,
            }
        }
    }

    for open in stack.into_iter().rev() {
        analysis.diagnostics.push(format!(
            "record {record_index}: unterminated block {:?} starting at line {}",
            open.name, analysis.blocks[open.summary_index].start_line
        ));
    }

    analysis
}

#[derive(Debug, Clone, Copy)]
enum LineKind {
    Assignment,
    Function,
    Other,
}

fn classify_line(trimmed: &str) -> LineKind {
    if looks_like_assignment(trimmed) {
        LineKind::Assignment
    } else if looks_like_function(trimmed) {
        LineKind::Function
    } else {
        LineKind::Other
    }
}

fn looks_like_assignment(trimmed: &str) -> bool {
    let Some(eq_index) = trimmed.find('=') else {
        return false;
    };
    let name = trimmed[..eq_index].trim();
    !name.is_empty()
        && name
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '_' | '-' | '.' | ' '))
}

fn looks_like_function(trimmed: &str) -> bool {
    let Some(paren_index) = trimmed.find('(') else {
        return false;
    };
    if !trimmed.ends_with(')') && !trimmed.ends_with("\\") {
        return false;
    }
    let name = trimmed[..paren_index].trim();
    !name.is_empty()
        && name
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '_' | '-'))
}

pub(crate) fn parse_begin(trimmed: &str) -> Option<String> {
    parse_quoted_block_marker(trimmed, "$begin '")
}

pub(crate) fn parse_end(trimmed: &str) -> Option<String> {
    parse_quoted_block_marker(trimmed, "$end '")
}

fn parse_quoted_block_marker(trimmed: &str, prefix: &str) -> Option<String> {
    let rest = trimmed.strip_prefix(prefix)?;
    let end = rest.find('\'')?;
    let suffix = rest[end + 1..].trim();
    if !suffix.is_empty() {
        return None;
    }
    Some(rest[..end].to_string())
}

fn extract_header_fields(text: &str, summary: &mut Summary) {
    for raw_line in text.lines() {
        let trimmed = raw_line.trim();
        if let Some(value) = trimmed.strip_prefix("Version=") {
            summary.def_version = Some(unquote(value).to_string());
        } else if let Some(value) = trimmed.strip_prefix("LastUpdateTimeStamp=") {
            summary.last_update_timestamp = Some(unquote(value).to_string());
        } else if let Some(value) = trimmed.strip_prefix("Encrypted=") {
            summary.encrypted = match unquote(value) {
                "true" => Some(true),
                "false" => Some(false),
                _ => None,
            };
        }
    }
}

pub(crate) fn unquote(value: &str) -> &str {
    let trimmed = value.trim();
    if trimmed.len() >= 2 && trimmed.starts_with('\'') && trimmed.ends_with('\'') {
        &trimmed[1..trimmed.len() - 1]
    } else {
        trimmed
    }
}

fn fnv1a64_hex(bytes: &[u8]) -> String {
    let mut hash = 0xcbf29ce484222325u64;
    for byte in bytes {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(0x100000001b3);
    }
    format!("{hash:016x}")
}

impl TextRecord {
    pub fn end_offset(&self) -> usize {
        self.offset + TEXT_HEADER_SIZE + self.raw_text.len()
    }
}

impl BinaryRecord {
    pub fn end_offset(&self) -> usize {
        self.offset + self.bytes.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::writer::write_def_file;
    use std::path::PathBuf;

    fn fixture(name: &str) -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../examples/edb_cases")
            .join(name)
    }

    #[test]
    fn parses_public_def_cases() {
        let mut checked = 0;
        for name in ["DemoCase_LPDDR4.def", "fpc.def", "kb.def", "mb.def"] {
            let source = fixture(name);
            if !source.exists() {
                continue;
            }
            checked += 1;
            let parsed = parse_def_file(
                &source,
                &ParseOptions {
                    include_details: true,
                },
            )
            .unwrap();
            assert!(parsed.summary.file_size_bytes > 0, "{name}");
            assert!(parsed.summary.text_record_count > 0, "{name}");
            assert!(parsed.summary.binary_record_count > 0, "{name}");
            assert!(parsed.summary.dsl_block_count > 0, "{name}");
            assert_eq!(
                parsed.summary.def_version.as_deref(),
                Some("12.1"),
                "{name}"
            );
            assert_eq!(parsed.summary.encrypted, Some(false), "{name}");
            assert_eq!(parsed.summary.diagnostic_count, 0, "{name}");
        }
        assert!(checked > 0, "no AEDB DEF fixtures were available");
    }

    #[test]
    fn roundtrip_public_def_cases_byte_identical() {
        let mut checked = 0;
        for name in ["DemoCase_LPDDR4.def", "fpc.def", "kb.def", "mb.def"] {
            let source = fixture(name);
            if !source.exists() {
                continue;
            }
            checked += 1;
            let parsed = parse_def_file(
                &source,
                &ParseOptions {
                    include_details: false,
                },
            )
            .unwrap();
            let output = std::env::temp_dir().join(format!(
                "aurora_aedb_parser_roundtrip_{}_{}",
                std::process::id(),
                name
            ));
            write_def_file(&parsed, &output).unwrap();
            let original = fs::read(&source).unwrap();
            let roundtrip = fs::read(&output).unwrap();
            let _ = fs::remove_file(&output);
            assert_eq!(original, roundtrip, "{name}");
        }
        assert!(checked > 0, "no AEDB DEF fixtures were available");
    }

    #[test]
    fn scans_synthetic_text_and_binary_records() {
        let mut bytes = Vec::new();
        bytes.push(0);
        let text = b"$begin 'Hdr'\n\tVersion='12.1'\n\tEncrypted=false\n$end 'Hdr'\n";
        bytes.extend_from_slice(&(text.len() as u32).to_le_bytes());
        bytes.extend_from_slice(text);
        bytes.extend_from_slice(&[0xff, 0xff, 0xff, 0xff]);
        bytes.push(7);
        let second = b"$begin 'EDB'\n$end 'EDB'\n";
        bytes.extend_from_slice(&(second.len() as u32).to_le_bytes());
        bytes.extend_from_slice(second);

        let parsed = parse_def_bytes(
            bytes,
            &ParseOptions {
                include_details: true,
            },
        )
        .unwrap();
        assert_eq!(parsed.summary.record_count, 3);
        assert_eq!(parsed.summary.text_record_count, 2);
        assert_eq!(parsed.summary.binary_record_count, 1);
        assert_eq!(parsed.summary.encrypted, Some(false));
    }
}
