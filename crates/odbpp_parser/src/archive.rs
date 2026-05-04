use flate2::read::GzDecoder;
use std::collections::BTreeMap;
use std::fs::{self, File};
use std::io::Read;
use std::path::Path;
use tar::Archive;
use thiserror::Error;
use walkdir::WalkDir;
use zip::ZipArchive;

pub const DEFAULT_MAX_ENTRY_SIZE_BYTES: u64 = 512 * 1024 * 1024;

#[derive(Debug, Error)]
pub enum ArchiveError {
    #[error("source does not exist: {0}")]
    MissingSource(String),
    #[error("failed to read {path}: {source}")]
    Read {
        path: String,
        #[source]
        source: std::io::Error,
    },
    #[error("failed to parse zip archive {path}: {source}")]
    Zip {
        path: String,
        #[source]
        source: zip::result::ZipError,
    },
    #[error("failed to parse tar archive {path}: {source}")]
    Tar {
        path: String,
        #[source]
        source: std::io::Error,
    },
}

#[derive(Debug, Clone)]
pub struct OdbSource {
    pub source_type: String,
    pub files: BTreeMap<String, Vec<u8>>,
    pub diagnostics: Vec<String>,
}

#[derive(Debug, Clone, Default)]
pub struct ReadSourceOptions {
    pub selected_step: Option<String>,
    pub include_details: bool,
    pub max_entry_size_bytes: Option<u64>,
}

impl ReadSourceOptions {
    fn max_entry_size_bytes(&self) -> u64 {
        self.max_entry_size_bytes
            .unwrap_or(DEFAULT_MAX_ENTRY_SIZE_BYTES)
    }
}

pub fn read_source(path: &Path, options: &ReadSourceOptions) -> Result<OdbSource, ArchiveError> {
    if !path.exists() {
        return Err(ArchiveError::MissingSource(path.display().to_string()));
    }
    if path.is_dir() {
        return read_directory(path, options);
    }

    let name = path
        .file_name()
        .and_then(|value| value.to_str())
        .unwrap_or_default()
        .to_ascii_lowercase();
    if name.ends_with(".zip") {
        return read_zip(path, options);
    }
    if name.ends_with(".tgz") || name.ends_with(".tar.gz") {
        return read_tar_gz(path, options);
    }
    if name.ends_with(".tar") {
        return read_tar(path, options);
    }

    Err(ArchiveError::MissingSource(format!(
        "expected ODB++ directory, .zip, .tgz, .tar.gz, or .tar, got {}",
        path.display()
    )))
}

pub fn strip_product_root(files: BTreeMap<String, Vec<u8>>) -> BTreeMap<String, Vec<u8>> {
    if files.contains_key("matrix/matrix") {
        return files;
    }

    let mut shortest_prefix: Option<&str> = None;
    for key in files.keys() {
        if let Some(prefix) = key
            .strip_suffix("/matrix/matrix")
            .filter(|prefix| !prefix.is_empty())
        {
            if shortest_prefix
                .map(|current| prefix.len() < current.len())
                .unwrap_or(true)
            {
                shortest_prefix = Some(prefix);
            }
        }
    }
    let Some(prefix) = shortest_prefix else {
        return files;
    };
    let marker = format!("{}/", prefix);

    files
        .into_iter()
        .filter_map(|(key, value)| {
            key.strip_prefix(&marker)
                .map(|stripped| (stripped.to_string(), value))
        })
        .collect()
}

fn read_directory(path: &Path, options: &ReadSourceOptions) -> Result<OdbSource, ArchiveError> {
    let mut files = BTreeMap::new();
    let mut diagnostics = Vec::new();
    for entry in WalkDir::new(path).follow_links(false) {
        let entry = match entry {
            Ok(entry) => entry,
            Err(error) => {
                diagnostics.push(format!("Skipped directory entry: {error}"));
                continue;
            }
        };
        if !entry.file_type().is_file() {
            continue;
        }
        let file_path = entry.path();
        let relative = match file_path.strip_prefix(path) {
            Ok(value) => normalize_path(value),
            Err(_) => continue,
        };
        if relative.to_ascii_lowercase().ends_with(".z") {
            diagnostics.push(format!(
                "Skipped UNIX .Z compressed file {relative}; convert it before parsing"
            ));
            continue;
        }
        if !should_read_file(&relative, options) {
            continue;
        }
        let size = entry
            .metadata()
            .map(|metadata| metadata.len())
            .unwrap_or_default();
        if is_oversized_entry(&relative, size, options, &mut diagnostics) {
            continue;
        }
        let bytes = fs::read(file_path).map_err(|source| ArchiveError::Read {
            path: file_path.display().to_string(),
            source,
        })?;
        files.insert(relative, bytes);
    }
    Ok(OdbSource {
        source_type: "directory".to_string(),
        files: strip_product_root(files),
        diagnostics,
    })
}

fn read_zip(path: &Path, options: &ReadSourceOptions) -> Result<OdbSource, ArchiveError> {
    let file = File::open(path).map_err(|source| ArchiveError::Read {
        path: path.display().to_string(),
        source,
    })?;
    let mut archive = ZipArchive::new(file).map_err(|source| ArchiveError::Zip {
        path: path.display().to_string(),
        source,
    })?;
    let mut files = BTreeMap::new();
    let mut diagnostics = Vec::new();
    for index in 0..archive.len() {
        let mut entry = archive
            .by_index(index)
            .map_err(|source| ArchiveError::Zip {
                path: path.display().to_string(),
                source,
            })?;
        if entry.is_dir() {
            continue;
        }
        let name = normalize_str_path(entry.name());
        if name.to_ascii_lowercase().ends_with(".z") {
            diagnostics.push(format!(
                "Skipped UNIX .Z compressed file {name}; convert it before parsing"
            ));
            continue;
        }
        if !should_read_file(&name, options) {
            continue;
        }
        if is_oversized_entry(&name, entry.size(), options, &mut diagnostics) {
            continue;
        }
        let mut bytes = Vec::with_capacity(entry.size().try_into().unwrap_or(0));
        entry
            .read_to_end(&mut bytes)
            .map_err(|source| ArchiveError::Read {
                path: name.clone(),
                source,
            })?;
        files.insert(name, bytes);
    }
    Ok(OdbSource {
        source_type: "zip".to_string(),
        files: strip_product_root(files),
        diagnostics,
    })
}

fn read_tar_gz(path: &Path, options: &ReadSourceOptions) -> Result<OdbSource, ArchiveError> {
    let file = File::open(path).map_err(|source| ArchiveError::Read {
        path: path.display().to_string(),
        source,
    })?;
    let decoder = GzDecoder::new(file);
    read_tar_stream(path, decoder, "tgz", options)
}

fn read_tar(path: &Path, options: &ReadSourceOptions) -> Result<OdbSource, ArchiveError> {
    let file = File::open(path).map_err(|source| ArchiveError::Read {
        path: path.display().to_string(),
        source,
    })?;
    read_tar_stream(path, file, "tar", options)
}

fn read_tar_stream<R: Read>(
    path: &Path,
    reader: R,
    source_type: &str,
    options: &ReadSourceOptions,
) -> Result<OdbSource, ArchiveError> {
    let mut archive = Archive::new(reader);
    let mut files = BTreeMap::new();
    let mut diagnostics = Vec::new();
    let entries = archive.entries().map_err(|source| ArchiveError::Tar {
        path: path.display().to_string(),
        source,
    })?;
    for entry in entries {
        let mut entry = entry.map_err(|source| ArchiveError::Tar {
            path: path.display().to_string(),
            source,
        })?;
        if !entry.header().entry_type().is_file() {
            continue;
        }
        let entry_path = entry.path().map_err(|source| ArchiveError::Tar {
            path: path.display().to_string(),
            source,
        })?;
        let name = normalize_path(&entry_path);
        if name.to_ascii_lowercase().ends_with(".z") {
            diagnostics.push(format!(
                "Skipped UNIX .Z compressed file {name}; convert it before parsing"
            ));
            continue;
        }
        if !should_read_file(&name, options) {
            continue;
        }
        if is_oversized_entry(&name, entry.size(), options, &mut diagnostics) {
            continue;
        }
        let mut bytes = Vec::with_capacity(entry.size().try_into().unwrap_or(0));
        entry
            .read_to_end(&mut bytes)
            .map_err(|source| ArchiveError::Read {
                path: name.clone(),
                source,
            })?;
        files.insert(name, bytes);
    }
    Ok(OdbSource {
        source_type: source_type.to_string(),
        files: strip_product_root(files),
        diagnostics,
    })
}

fn normalize_path(path: &Path) -> String {
    normalize_str_path(&path.to_string_lossy())
}

fn normalize_str_path(path: &str) -> String {
    path.replace('\\', "/")
        .trim_start_matches("./")
        .trim_start_matches('/')
        .to_string()
}

fn should_read_file(path: &str, options: &ReadSourceOptions) -> bool {
    if options.include_details && options.selected_step.is_none() {
        return true;
    }

    let logical = logical_odb_path(path);
    if logical == "matrix/matrix" {
        return true;
    }

    let Some(rest) = logical.strip_prefix("steps/") else {
        return options.include_details && symbol_feature_name(&logical).is_some();
    };
    let Some((step_name, step_rest)) = rest.split_once('/') else {
        return false;
    };
    if step_rest == "profile" {
        return true;
    }
    if !options.include_details {
        return false;
    }
    if let Some(selected_step) = options.selected_step.as_deref() {
        if step_name != selected_step {
            return false;
        }
    }
    is_selected_step_detail(step_rest)
}

fn logical_odb_path(path: &str) -> String {
    for marker in ["matrix/matrix", "steps/", "symbols/"] {
        if let Some(index) = path.find(marker) {
            return path[index..].to_string();
        }
    }
    path.to_string()
}

fn symbol_feature_name(path: &str) -> Option<String> {
    path.strip_prefix("symbols/")
        .and_then(|value| value.strip_suffix("/features"))
        .map(|value| value.trim_matches('/').to_string())
}

fn is_selected_step_detail(step_rest: &str) -> bool {
    if step_rest == "eda/data" || step_rest.starts_with("netlists/") {
        return true;
    }
    let Some(layer_rest) = step_rest.strip_prefix("layers/") else {
        return false;
    };
    let Some((_layer_name, layer_file)) = layer_rest.split_once('/') else {
        return false;
    };
    !layer_file.contains('/')
        && matches!(layer_file, "features" | "attrlist" | "tools" | "components")
}

fn is_oversized_entry(
    name: &str,
    size: u64,
    options: &ReadSourceOptions,
    diagnostics: &mut Vec<String>,
) -> bool {
    let max_size = options.max_entry_size_bytes();
    if size <= max_size {
        return false;
    }
    diagnostics.push(format!(
        "Skipped oversized ODB++ entry {name}; size={size} bytes exceeds limit={max_size} bytes"
    ));
    true
}

#[cfg(test)]
mod tests {
    use super::{read_source, should_read_file, ReadSourceOptions};
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn summary_only_reads_matrix_and_profiles() {
        let options = ReadSourceOptions {
            selected_step: None,
            include_details: false,
            max_entry_size_bytes: None,
        };
        assert!(should_read_file("product/matrix/matrix", &options));
        assert!(should_read_file("product/steps/main/profile", &options));
        assert!(!should_read_file(
            "product/steps/main/layers/top/features",
            &options
        ));
        assert!(!should_read_file("product/symbols/r100/features", &options));
    }

    #[test]
    fn explicit_step_reads_only_selected_step_details() {
        let options = ReadSourceOptions {
            selected_step: Some("main".to_string()),
            include_details: true,
            max_entry_size_bytes: None,
        };
        assert!(should_read_file("steps/main/layers/top/features", &options));
        assert!(should_read_file("steps/main/eda/data", &options));
        assert!(should_read_file("steps/other/profile", &options));
        assert!(!should_read_file(
            "steps/other/layers/top/features",
            &options
        ));
        assert!(should_read_file("symbols/r100/features", &options));
    }

    #[test]
    fn directory_reader_skips_entries_over_size_limit() {
        let root = std::env::temp_dir().join(format!(
            "aurora_odbpp_size_limit_{}_{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("system clock should be after epoch")
                .as_nanos()
        ));
        let matrix_dir = root.join("matrix");
        fs::create_dir_all(&matrix_dir).expect("test matrix dir should be creatable");
        fs::write(matrix_dir.join("matrix"), b"0123456789")
            .expect("test matrix should be writable");

        let source = read_source(
            &root,
            &ReadSourceOptions {
                selected_step: None,
                include_details: true,
                max_entry_size_bytes: Some(4),
            },
        )
        .expect("test source should be readable");

        fs::remove_dir_all(&root).expect("test directory should be removable");
        assert!(!source.files.contains_key("matrix/matrix"));
        assert!(source
            .diagnostics
            .iter()
            .any(|message| message.contains("Skipped oversized ODB++ entry matrix/matrix")));
    }
}
