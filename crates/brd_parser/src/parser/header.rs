use super::constants::STRING_TABLE_OFFSET;
use super::reader::Reader;
use super::{BrdParseError, FormatVersion};
use crate::model::{Header, LayerMapEntry, LinkedList, StringEntry};
use std::collections::{BTreeMap, HashMap};

pub(crate) fn parse_header(reader: &mut Reader<'_>) -> Result<Header, BrdParseError> {
    let start = reader.position();
    let magic = reader.u32()?;
    let version = FormatVersion::from_magic(magic)?;
    let _unknown1a = reader.u32()?;
    let file_role = reader.u32()?;
    let _unknown1b = reader.u32()?;
    let writer_program = reader.u32()?;
    let object_count = reader.u32()?;
    let _unknown_magic = reader.u32()?;
    let _unknown_flags = reader.u32()?;

    let mut linked_lists = BTreeMap::new();
    let (string_count_v18, x27_end_v18) = if version.lt(FormatVersion::V180) {
        reader.skip_u32(7)?;
        (None, None)
    } else {
        let _unknown2a = reader.u32()?;
        let _unknown2b = reader.u32()?;
        let x27_end = reader.u32()?;
        let _unknown2d = reader.u32()?;
        let _unknown2e = reader.u32()?;
        let string_count = reader.u32()?;
        let _unknown2g = reader.u32()?;
        for name in ["v18_1", "v18_2", "v18_3", "v18_4", "v18_5"] {
            linked_lists.insert(name.to_string(), read_ll(reader, version)?);
        }
        (Some(string_count), Some(x27_end))
    };

    for name in [
        "0x04_net_assignments",
        "0x06_components",
        "0x0c_pin_defs",
        "shapes",
        "0x14_graphics",
        "0x1b_nets",
        "0x1c_padstacks",
        "0x24_0x28",
        "unknown1",
        "0x2b_footprints",
        "0x03_0x30",
        "0x0a_drc",
        "0x1d_0x1e_0x1f",
        "unknown2",
        "0x38_films",
        "0x2c_tables",
        "0x0c_secondary",
        "unknown3",
    ] {
        linked_lists.insert(name.to_string(), read_ll(reader, version)?);
    }

    if version.lt(FormatVersion::V180) {
        let _x35_start = reader.u32()?;
        let _x35_end = reader.u32()?;
    }

    if version.ge(FormatVersion::V180) {
        linked_lists.insert("unknown5_v18".to_string(), read_ll(reader, version)?);
    }
    linked_lists.insert("0x36".to_string(), read_ll(reader, version)?);
    if version.lt(FormatVersion::V180) {
        linked_lists.insert("unknown5_pre_v18".to_string(), read_ll(reader, version)?);
    }
    linked_lists.insert("unknown6".to_string(), read_ll(reader, version)?);
    linked_lists.insert("0x0a_2".to_string(), read_ll(reader, version)?);
    if version.lt(FormatVersion::V180) {
        let _unknown3 = reader.u32()?;
    }
    if version.ge(FormatVersion::V180) {
        linked_lists.insert("v18_6".to_string(), read_ll(reader, version)?);
        let _x35_start = reader.u32()?;
        let _x35_end = reader.u32()?;
    }

    let expected_version_offset = if version.lt(FormatVersion::V180) {
        0xF8
    } else {
        0x124
    };
    if reader.position().saturating_sub(start) != expected_version_offset {
        return Err(BrdParseError::Invalid(format!(
            "header version string offset mismatch: expected 0x{expected_version_offset:x}, got 0x{:x}",
            reader.position().saturating_sub(start)
        )));
    }

    let allegro_version = reader.fixed_string(60, false)?;
    let _unknown4 = reader.u32()?;
    let max_key = reader.u32()?;
    if version.lt(FormatVersion::V180) {
        reader.skip_u32(17)?;
    } else {
        reader.skip_u32(9)?;
    }
    let board_units_code = reader.u8()?;
    reader.skip(3)?;
    let _unknown6 = reader.u32()?;
    if version.lt(FormatVersion::V180) {
        let _unknown7 = reader.u32()?;
    }
    let x27_end_pre_v18 = if version.lt(FormatVersion::V180) {
        Some(reader.u32()?)
    } else {
        None
    };
    let _unknown8 = reader.u32()?;
    let string_count_pre_v18 = if version.lt(FormatVersion::V180) {
        Some(reader.u32()?)
    } else {
        None
    };
    reader.skip_u32(50)?;
    let _unknown10a = reader.u32()?;
    let _unknown10b = reader.u32()?;
    let _unknown10c = reader.u32()?;
    let units_divisor = reader.u32()?;
    reader.skip_u32(110)?;
    let mut layer_map = Vec::with_capacity(25);
    for index in 0..25 {
        layer_map.push(LayerMapEntry {
            index,
            class_code: reader.u32()?,
            layer_list_key: reader.u32()?,
        });
    }

    Ok(Header {
        magic,
        format_version: version.label().to_string(),
        file_role,
        writer_program,
        object_count,
        max_key,
        allegro_version,
        board_units_code,
        board_units: board_units_name(board_units_code).to_string(),
        units_divisor,
        coordinate_scale_nm: (units_divisor > 0).then_some(25400.0 / units_divisor as f64),
        string_count: string_count_v18.or(string_count_pre_v18).unwrap_or(0),
        x27_end: x27_end_v18.or(x27_end_pre_v18).unwrap_or(0),
        linked_lists,
        layer_map,
    })
}

pub(crate) fn parse_strings(
    bytes: &[u8],
    count: u32,
    diagnostics: &mut Vec<String>,
) -> Result<Vec<StringEntry>, BrdParseError> {
    let mut reader = Reader::new(bytes);
    reader.seek(STRING_TABLE_OFFSET)?;
    let mut strings = Vec::with_capacity(count as usize);
    for _ in 0..count {
        if reader.eof() {
            diagnostics.push("String table ended before declared string count".to_string());
            break;
        }
        let id = reader.u32()?;
        let value = reader.c_string(true)?;
        strings.push(StringEntry { id, value });
    }
    Ok(strings)
}

pub(crate) fn after_string_table_offset(
    bytes: &[u8],
    strings: &[StringEntry],
) -> Result<usize, BrdParseError> {
    let mut reader = Reader::new(bytes);
    reader.seek(STRING_TABLE_OFFSET)?;
    for _ in strings {
        reader.skip(4)?;
        let _ = reader.c_string(true)?;
    }
    Ok(reader.position())
}

pub(crate) fn resolve_layer_names(header: &mut Header, string_map: &HashMap<u32, String>) {
    for entry in &mut header.layer_map {
        let _ = string_map.get(&entry.layer_list_key);
    }
}

fn read_ll(reader: &mut Reader<'_>, version: FormatVersion) -> Result<LinkedList, BrdParseError> {
    let first = reader.u32()?;
    let second = reader.u32()?;
    if version.ge(FormatVersion::V180) {
        Ok(LinkedList {
            head: first,
            tail: second,
        })
    } else {
        Ok(LinkedList {
            head: second,
            tail: first,
        })
    }
}

fn board_units_name(code: u8) -> &'static str {
    match code {
        0x01 => "mils",
        0x02 => "inches",
        0x03 => "millimeters",
        0x04 => "centimeters",
        0x05 => "micrometers",
        _ => "unknown",
    }
}
