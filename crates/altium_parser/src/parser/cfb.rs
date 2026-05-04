use super::strings::utf16le_string;
use super::AltiumParseError;
use crate::model::StreamSummary;
use std::collections::HashSet;

const CFB_SIGNATURE: [u8; 8] = [0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1];
const FREE_SECTOR: u32 = 0xFFFF_FFFF;
const END_OF_CHAIN: u32 = 0xFFFF_FFFE;
const FAT_SECTOR: u32 = 0xFFFF_FFFD;
const DIFAT_SECTOR: u32 = 0xFFFF_FFFC;
const NO_STREAM: u32 = 0xFFFF_FFFF;

struct DirectoryEntry {
    name: String,
    object_type: u8,
    left: u32,
    right: u32,
    child: u32,
    start_sector: u32,
    stream_size: u64,
}

#[derive(Debug, Clone)]
struct CfbStream {
    path: String,
    data: Vec<u8>,
}

#[derive(Debug, Clone)]
pub(crate) struct CompoundFile {
    streams: Vec<CfbStream>,
}

impl CompoundFile {
    pub(crate) fn parse(bytes: &[u8]) -> Result<Self, AltiumParseError> {
        if bytes.len() < 512 {
            return Err(AltiumParseError::UnexpectedEof {
                offset: 0,
                size: 512,
                file_size: bytes.len(),
            });
        }
        if bytes[..8] != CFB_SIGNATURE {
            return Err(AltiumParseError::InvalidSignature);
        }
        let sector_shift = read_u16_at(bytes, 30)?;
        let mini_sector_shift = read_u16_at(bytes, 32)?;
        let sector_size = 1usize
            .checked_shl(sector_shift as u32)
            .ok_or_else(|| AltiumParseError::Invalid("invalid CFB sector shift".to_string()))?;
        let mini_sector_size = 1usize
            .checked_shl(mini_sector_shift as u32)
            .ok_or_else(|| {
                AltiumParseError::Invalid("invalid CFB mini-sector shift".to_string())
            })?;
        let fat_sector_count = read_u32_at(bytes, 44)? as usize;
        let first_directory_sector = read_u32_at(bytes, 48)?;
        let mini_stream_cutoff_size = read_u32_at(bytes, 56)? as u64;
        let first_mini_fat_sector = read_u32_at(bytes, 60)?;
        let mini_fat_sector_count = read_u32_at(bytes, 64)? as usize;
        let first_difat_sector = read_u32_at(bytes, 68)?;
        let difat_sector_count = read_u32_at(bytes, 72)? as usize;

        let mut difat = Vec::new();
        for index in 0..109 {
            let value = read_u32_at(bytes, 76 + index * 4)?;
            if value != FREE_SECTOR {
                difat.push(value);
            }
        }
        let mut next_difat = first_difat_sector;
        for _ in 0..difat_sector_count {
            if next_difat == END_OF_CHAIN || next_difat == FREE_SECTOR {
                break;
            }
            let sector = sector_slice(bytes, sector_size, next_difat)?;
            let entry_count = sector_size / 4 - 1;
            for index in 0..entry_count {
                let value = read_u32_at(sector, index * 4)?;
                if value != FREE_SECTOR {
                    difat.push(value);
                }
            }
            next_difat = read_u32_at(sector, sector_size - 4)?;
        }
        difat.truncate(fat_sector_count);

        let mut fat = Vec::new();
        for sector_id in &difat {
            if *sector_id == FAT_SECTOR || *sector_id == DIFAT_SECTOR {
                continue;
            }
            let sector = sector_slice(bytes, sector_size, *sector_id)?;
            for index in 0..sector_size / 4 {
                fat.push(read_u32_at(sector, index * 4)?);
            }
        }

        let directory_stream =
            read_regular_chain(bytes, sector_size, &fat, first_directory_sector)?;
        let directory = parse_directory(&directory_stream)?;
        let Some(root) = directory.iter().find(|entry| entry.object_type == 5) else {
            return Err(AltiumParseError::Invalid(
                "CFB root storage not found".to_string(),
            ));
        };
        let mini_fat = if mini_fat_sector_count > 0 && first_mini_fat_sector != END_OF_CHAIN {
            let data = read_regular_chain(bytes, sector_size, &fat, first_mini_fat_sector)?;
            let mut entries = Vec::with_capacity(data.len() / 4);
            for index in 0..data.len() / 4 {
                entries.push(read_u32_at(&data, index * 4)?);
            }
            entries
        } else {
            Vec::new()
        };
        let mini_stream = if root.start_sector != END_OF_CHAIN && root.stream_size > 0 {
            let mut data = read_regular_chain(bytes, sector_size, &fat, root.start_sector)?;
            data.truncate(root.stream_size as usize);
            data
        } else {
            Vec::new()
        };

        let mut streams = Vec::new();
        if root.child != NO_STREAM {
            collect_streams(root.child as usize, "", &directory, &mut |entry, path| {
                let data = if entry.stream_size < mini_stream_cutoff_size
                    && !mini_fat.is_empty()
                    && entry.start_sector != END_OF_CHAIN
                {
                    read_mini_chain(
                        &mini_stream,
                        mini_sector_size,
                        &mini_fat,
                        entry.start_sector,
                        entry.stream_size as usize,
                    )
                } else {
                    read_regular_chain(bytes, sector_size, &fat, entry.start_sector).map(
                        |mut data| {
                            data.truncate(entry.stream_size as usize);
                            data
                        },
                    )
                }?;
                streams.push(CfbStream { path, data });
                Ok(())
            })?;
        }
        streams.sort_by(|left, right| left.path.cmp(&right.path));
        Ok(Self { streams })
    }

    pub(crate) fn stream_summaries(&self) -> Vec<StreamSummary> {
        self.streams
            .iter()
            .map(|stream| StreamSummary {
                path: stream.path.clone(),
                size: stream.data.len(),
                parsed: false,
            })
            .collect()
    }

    pub(crate) fn find_stream(&self, name: &str) -> Option<&[u8]> {
        let target = name.to_ascii_lowercase();
        let target_data = format!("{target}/data");
        self.streams
            .iter()
            .find(|stream| {
                let path = stream.path.to_ascii_lowercase();
                path == target || path == target_data || path.ends_with(&format!("/{target_data}"))
            })
            .map(|stream| stream.data.as_slice())
    }
}

fn collect_streams<F>(
    sid: usize,
    parent: &str,
    directory: &[DirectoryEntry],
    visit: &mut F,
) -> Result<(), AltiumParseError>
where
    F: FnMut(&DirectoryEntry, String) -> Result<(), AltiumParseError>,
{
    if sid >= directory.len() {
        return Ok(());
    }
    let entry = &directory[sid];
    if entry.left != NO_STREAM {
        collect_streams(entry.left as usize, parent, directory, visit)?;
    }
    match entry.object_type {
        1 => {
            let path = join_path(parent, &entry.name);
            if entry.child != NO_STREAM {
                collect_streams(entry.child as usize, &path, directory, visit)?;
            }
        }
        2 => visit(entry, join_path(parent, &entry.name))?,
        _ => {}
    }
    if entry.right != NO_STREAM {
        collect_streams(entry.right as usize, parent, directory, visit)?;
    }
    Ok(())
}

fn join_path(parent: &str, name: &str) -> String {
    if parent.is_empty() {
        name.to_string()
    } else {
        format!("{parent}/{name}")
    }
}

fn parse_directory(bytes: &[u8]) -> Result<Vec<DirectoryEntry>, AltiumParseError> {
    let mut entries = Vec::new();
    for chunk in bytes.chunks_exact(128) {
        let name_len = read_u16_at(chunk, 64)? as usize;
        let name_bytes_len = name_len.saturating_sub(2).min(64);
        let name = utf16le_string(&chunk[..name_bytes_len]);
        entries.push(DirectoryEntry {
            name,
            object_type: chunk[66],
            left: read_u32_at(chunk, 68)?,
            right: read_u32_at(chunk, 72)?,
            child: read_u32_at(chunk, 76)?,
            start_sector: read_u32_at(chunk, 116)?,
            stream_size: read_u64_at(chunk, 120)?,
        });
    }
    Ok(entries)
}

fn read_regular_chain(
    bytes: &[u8],
    sector_size: usize,
    fat: &[u32],
    first_sector: u32,
) -> Result<Vec<u8>, AltiumParseError> {
    if first_sector == END_OF_CHAIN || first_sector == FREE_SECTOR {
        return Ok(Vec::new());
    }
    let mut data = Vec::new();
    let mut sector_id = first_sector;
    let mut seen = HashSet::new();
    while sector_id != END_OF_CHAIN {
        if sector_id as usize >= fat.len() {
            return Err(AltiumParseError::Invalid(format!(
                "CFB sector {sector_id} is outside FAT"
            )));
        }
        if !seen.insert(sector_id) {
            return Err(AltiumParseError::Invalid(format!(
                "CFB sector chain loops at sector {sector_id}"
            )));
        }
        data.extend_from_slice(sector_slice(bytes, sector_size, sector_id)?);
        sector_id = fat[sector_id as usize];
    }
    Ok(data)
}

fn read_mini_chain(
    mini_stream: &[u8],
    mini_sector_size: usize,
    mini_fat: &[u32],
    first_sector: u32,
    stream_size: usize,
) -> Result<Vec<u8>, AltiumParseError> {
    let mut data = Vec::new();
    let mut sector_id = first_sector;
    let mut seen = HashSet::new();
    while sector_id != END_OF_CHAIN && data.len() < stream_size {
        if sector_id as usize >= mini_fat.len() {
            return Err(AltiumParseError::Invalid(format!(
                "CFB mini-sector {sector_id} is outside mini FAT"
            )));
        }
        if !seen.insert(sector_id) {
            return Err(AltiumParseError::Invalid(format!(
                "CFB mini-sector chain loops at sector {sector_id}"
            )));
        }
        let start = sector_id as usize * mini_sector_size;
        let end = start + mini_sector_size;
        if end > mini_stream.len() {
            return Err(AltiumParseError::UnexpectedEof {
                offset: start,
                size: mini_sector_size,
                file_size: mini_stream.len(),
            });
        }
        data.extend_from_slice(&mini_stream[start..end]);
        sector_id = mini_fat[sector_id as usize];
    }
    data.truncate(stream_size);
    Ok(data)
}

fn sector_slice<'a>(
    bytes: &'a [u8],
    sector_size: usize,
    sector_id: u32,
) -> Result<&'a [u8], AltiumParseError> {
    let start = 512usize
        .checked_add(sector_id as usize * sector_size)
        .ok_or_else(|| AltiumParseError::Invalid("CFB sector offset overflow".to_string()))?;
    let end = start + sector_size;
    if end > bytes.len() {
        return Err(AltiumParseError::UnexpectedEof {
            offset: start,
            size: sector_size,
            file_size: bytes.len(),
        });
    }
    Ok(&bytes[start..end])
}

fn read_u16_at(bytes: &[u8], offset: usize) -> Result<u16, AltiumParseError> {
    if offset + 2 > bytes.len() {
        return Err(AltiumParseError::UnexpectedEof {
            offset,
            size: 2,
            file_size: bytes.len(),
        });
    }
    Ok(u16::from_le_bytes([bytes[offset], bytes[offset + 1]]))
}

fn read_u32_at(bytes: &[u8], offset: usize) -> Result<u32, AltiumParseError> {
    if offset + 4 > bytes.len() {
        return Err(AltiumParseError::UnexpectedEof {
            offset,
            size: 4,
            file_size: bytes.len(),
        });
    }
    Ok(u32::from_le_bytes([
        bytes[offset],
        bytes[offset + 1],
        bytes[offset + 2],
        bytes[offset + 3],
    ]))
}

fn read_u64_at(bytes: &[u8], offset: usize) -> Result<u64, AltiumParseError> {
    if offset + 8 > bytes.len() {
        return Err(AltiumParseError::UnexpectedEof {
            offset,
            size: 8,
            file_size: bytes.len(),
        });
    }
    Ok(u64::from_le_bytes([
        bytes[offset],
        bytes[offset + 1],
        bytes[offset + 2],
        bytes[offset + 3],
        bytes[offset + 4],
        bytes[offset + 5],
        bytes[offset + 6],
        bytes[offset + 7],
    ]))
}
