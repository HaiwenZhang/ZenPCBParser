use super::constants::ALTIUM_POLYGON_NONE;
use super::geometry::{coord_to_mil_i32, double_coord_to_raw, point_from_raw, size_from_raw};
use super::layers::{layer_id_from_name, resolved_layer_name, versioned_layer};
use super::primitive_names::{
    pad_hole_shape_name, pad_mode_name, pad_shape_alt_name, pad_shape_name, region_kind_name,
    text_font_type_name,
};
use super::properties::{prop_bool, prop_i32, prop_string, prop_u16, prop_u8};
use super::reader::BinaryReader;
use super::strings::utf16le_string;
use super::AltiumParseError;
use crate::model::{Arc, Fill, Pad, PadSizeAndShape, Region, Text, Track, Vertex, Via};
use std::collections::{BTreeMap, HashMap};

pub(crate) fn parse_binary_records<T, F>(
    bytes: &[u8],
    mut parse: F,
) -> Result<Vec<T>, AltiumParseError>
where
    F: FnMut(&mut BinaryReader<'_>, usize) -> Result<T, AltiumParseError>,
{
    let mut reader = BinaryReader::new(bytes);
    let mut records = Vec::new();
    while reader.remaining() >= 5 {
        records.push(parse(&mut reader, records.len())?);
    }
    Ok(records)
}

pub(crate) fn parse_binary_records_lossy<T, F>(
    bytes: &[u8],
    mut parse: F,
) -> (Vec<T>, Option<AltiumParseError>)
where
    F: FnMut(&mut BinaryReader<'_>, usize) -> Result<T, AltiumParseError>,
{
    let mut reader = BinaryReader::new(bytes);
    let mut records = Vec::new();
    while reader.remaining() >= 5 {
        let start = reader.position();
        match parse(&mut reader, records.len()) {
            Ok(record) => records.push(record),
            Err(error) => return (records, Some(error)),
        }
        if reader.position() <= start {
            return (
                records,
                Some(AltiumParseError::Invalid(
                    "binary record parser made no progress".to_string(),
                )),
            );
        }
    }
    (records, None)
}

pub(crate) fn parse_pad_record(
    reader: &mut BinaryReader<'_>,
    index: usize,
    layer_names: &HashMap<u32, String>,
) -> Result<Pad, AltiumParseError> {
    expect_record_type(reader, 2, "Pads6")?;
    let subrecord1 = reader.read_subrecord_len()?;
    if subrecord1 == 0 {
        return Err(AltiumParseError::Invalid(
            "Pads6 subrecord1 has zero length".to_string(),
        ));
    }
    let name = reader.read_wx_string()?;
    reader.skip_subrecord()?;
    reader.read_subrecord_len()?;
    reader.skip_subrecord()?;
    reader.read_subrecord_len()?;
    reader.skip_subrecord()?;
    reader.read_subrecord_len()?;
    reader.skip_subrecord()?;

    let subrecord5 = reader.read_subrecord_len()?;
    if subrecord5 < 110 {
        return Err(AltiumParseError::Invalid(format!(
            "Pads6 subrecord5 length {subrecord5} is too short"
        )));
    }
    let layer_v6 = reader.u8()? as u32;
    let flags1 = reader.u8()?;
    let is_test_fab_top = flags1 & 0x80 != 0;
    let is_tent_bottom = flags1 & 0x40 != 0;
    let is_tent_top = flags1 & 0x20 != 0;
    let is_locked = flags1 & 0x04 == 0;
    let flags2 = reader.u8()?;
    let is_test_fab_bottom = flags2 & 0x01 != 0;
    let net = reader.u16()?;
    reader.skip(2)?;
    let component = reader.u16()?;
    reader.skip(4)?;
    let position = reader.point()?;
    let top_size = reader.size()?;
    let mid_size = reader.size()?;
    let bottom_size = reader.size()?;
    let hole_size = coord_to_mil_i32(reader.i32()?);
    let top_shape = pad_shape_name(reader.u8()?).to_string();
    let mid_shape = pad_shape_name(reader.u8()?).to_string();
    let bottom_shape = pad_shape_name(reader.u8()?).to_string();
    let direction = reader.f64()?;
    let plated = reader.u8()? != 0;
    reader.skip(1)?;
    let pad_mode = pad_mode_name(reader.u8()?).to_string();
    reader.skip(23)?;
    let _paste_mask_expansion = reader.i32()?;
    let _solder_mask_expansion = reader.i32()?;
    reader.skip(7)?;
    let _paste_mode = reader.u8()?;
    let _solder_mode = reader.u8()?;
    reader.skip(3)?;
    let hole_rotation = if subrecord5 == 110 {
        let _unknown = reader.i32()?;
        0.0
    } else {
        reader.f64()?
    };
    let mut to_layer_id = None;
    let mut from_layer_id = None;
    if subrecord5 >= 120 && reader.remaining_subrecord_bytes() >= 4 {
        to_layer_id = Some(reader.u8()? as u32);
        reader.skip(2)?;
        from_layer_id = Some(reader.u8()? as u32);
    }
    reader.skip_subrecord()?;

    let subrecord6 = reader.read_subrecord_len()?;
    let size_and_shape = if subrecord6 >= 596 {
        Some(parse_pad_size_and_shape(reader)?)
    } else {
        None
    };
    reader.skip_subrecord()?;
    let layer_id = layer_v6;
    Ok(Pad {
        index,
        name,
        layer_id,
        layer_name: resolved_layer_name(layer_id, layer_names),
        net,
        component,
        position,
        top_size,
        mid_size,
        bottom_size,
        hole_size,
        top_shape,
        mid_shape,
        bottom_shape,
        direction,
        plated,
        pad_mode,
        hole_rotation,
        from_layer_id,
        to_layer_id,
        size_and_shape,
        is_locked,
        is_tent_top,
        is_tent_bottom,
        is_test_fab_top,
        is_test_fab_bottom,
    })
}

fn parse_pad_size_and_shape(
    reader: &mut BinaryReader<'_>,
) -> Result<PadSizeAndShape, AltiumParseError> {
    let mut inner_x = Vec::with_capacity(29);
    for _ in 0..29 {
        inner_x.push(reader.i32()?);
    }
    let mut inner_sizes = Vec::with_capacity(29);
    for x_raw in inner_x {
        let y_raw = reader.i32()?;
        inner_sizes.push(size_from_raw(x_raw, y_raw));
    }
    let mut inner_shapes = Vec::with_capacity(29);
    for _ in 0..29 {
        inner_shapes.push(pad_shape_name(reader.u8()?).to_string());
    }
    reader.skip(1)?;
    let hole_shape = pad_hole_shape_name(reader.u8()?).to_string();
    let slot_size = coord_to_mil_i32(reader.i32()?);
    let slot_rotation = reader.f64()?;
    let mut offset_x = Vec::with_capacity(32);
    for _ in 0..32 {
        offset_x.push(reader.i32()?);
    }
    let mut hole_offsets = Vec::with_capacity(32);
    for x_raw in offset_x {
        let y_raw = reader.i32()?;
        hole_offsets.push(point_from_raw(x_raw, y_raw));
    }
    reader.skip(1)?;
    let mut alternate_shapes = Vec::with_capacity(32);
    for _ in 0..32 {
        alternate_shapes.push(pad_shape_alt_name(reader.u8()?).to_string());
    }
    let mut corner_radii = Vec::with_capacity(32);
    for _ in 0..32 {
        corner_radii.push(reader.u8()?);
    }
    Ok(PadSizeAndShape {
        hole_shape,
        slot_size,
        slot_rotation,
        inner_sizes,
        inner_shapes,
        hole_offsets,
        alternate_shapes,
        corner_radii,
    })
}

pub(crate) fn parse_via_record(
    reader: &mut BinaryReader<'_>,
    index: usize,
    layer_names: &HashMap<u32, String>,
) -> Result<Via, AltiumParseError> {
    expect_record_type(reader, 3, "Vias6")?;
    let subrecord1 = reader.read_subrecord_len()?;
    reader.skip(1)?;
    let flags1 = reader.u8()?;
    let is_tent_bottom = flags1 & 0x40 != 0;
    let is_tent_top = flags1 & 0x20 != 0;
    let is_locked = flags1 & 0x04 == 0;
    let _flags2 = reader.u8()?;
    let net = reader.u16()?;
    reader.skip(8)?;
    let position = reader.point()?;
    let diameter = coord_to_mil_i32(reader.i32()?);
    let hole_size = coord_to_mil_i32(reader.i32()?);
    let start_layer_id = reader.u8()? as u32;
    let end_layer_id = reader.u8()? as u32;
    let mut via_mode = "simple".to_string();
    let mut diameter_by_layer = Vec::new();
    if subrecord1 > 74 && reader.remaining_subrecord_bytes() >= 74 {
        reader.skip(1)?;
        let _thermal_airgap = reader.i32()?;
        let _thermal_conductors = reader.u8()?;
        reader.skip(1)?;
        let _thermal_width = reader.i32()?;
        reader.skip(16)?;
        let _solder_front = reader.i32()?;
        reader.skip(15)?;
        via_mode = pad_mode_name(reader.u8()?).to_string();
        for _ in 0..32 {
            if reader.remaining_subrecord_bytes() < 4 {
                break;
            }
            // Vias6 stores per-layer diameters as 8.8 fixed-point values on
            // top of Altium's regular internal coordinate scale. The scalar
            // via diameter fields above use only the internal coordinate scale.
            diameter_by_layer.push(coord_to_mil_i32(reader.i32()?) / 256.0);
        }
    }
    reader.skip_subrecord()?;
    Ok(Via {
        index,
        net,
        position,
        diameter,
        hole_size,
        start_layer_id,
        start_layer_name: resolved_layer_name(start_layer_id, layer_names),
        end_layer_id,
        end_layer_name: resolved_layer_name(end_layer_id, layer_names),
        via_mode,
        diameter_by_layer,
        is_locked,
        is_tent_top,
        is_tent_bottom,
    })
}

pub(crate) fn parse_track_record(
    reader: &mut BinaryReader<'_>,
    index: usize,
    layer_names: &HashMap<u32, String>,
) -> Result<Track, AltiumParseError> {
    expect_record_type(reader, 4, "Tracks6")?;
    reader.read_subrecord_len()?;
    let layer_v6 = reader.u8()? as u32;
    let flags1 = reader.u8()?;
    let is_locked = flags1 & 0x04 == 0;
    let is_polygon_outline = flags1 & 0x02 != 0;
    let flags2 = reader.u8()?;
    let is_keepout = flags2 == 2;
    let net = reader.u16()?;
    let polygon = reader.u16()?;
    let component = reader.u16()?;
    reader.skip(4)?;
    let start = reader.point()?;
    let end = reader.point()?;
    let width = coord_to_mil_i32(reader.i32()?);
    let subpolygon = reader.u16()?;
    reader.skip(1)?;
    let remaining = reader.remaining_subrecord_bytes();
    let mut layer_id = layer_v6;
    if remaining >= 9 {
        reader.skip(5)?;
        layer_id = versioned_layer(layer_v6, reader.u32()?);
    }
    let keepout_restrictions = if remaining >= 10 {
        reader.u8()?
    } else if is_keepout {
        0x1F
    } else {
        0
    };
    reader.skip_subrecord()?;
    Ok(Track {
        index,
        layer_id,
        layer_name: resolved_layer_name(layer_id, layer_names),
        net,
        component,
        polygon,
        subpolygon,
        start,
        end,
        width,
        is_locked,
        is_keepout,
        is_polygon_outline,
        keepout_restrictions,
    })
}

pub(crate) fn parse_arc_record(
    reader: &mut BinaryReader<'_>,
    index: usize,
    layer_names: &HashMap<u32, String>,
) -> Result<Arc, AltiumParseError> {
    expect_record_type(reader, 1, "Arcs6")?;
    reader.read_subrecord_len()?;
    let layer_v6 = reader.u8()? as u32;
    let flags1 = reader.u8()?;
    let is_locked = flags1 & 0x04 == 0;
    let is_polygon_outline = flags1 & 0x02 != 0;
    let flags2 = reader.u8()?;
    let is_keepout = flags2 == 2;
    let net = reader.u16()?;
    let polygon = reader.u16()?;
    let component = reader.u16()?;
    reader.skip(4)?;
    let center = reader.point()?;
    let radius = coord_to_mil_i32(reader.i32()?);
    let start_angle = reader.f64()?;
    let end_angle = reader.f64()?;
    let width = coord_to_mil_i32(reader.i32()?);
    let subpolygon = reader.u16()?;
    let remaining = reader.remaining_subrecord_bytes();
    let mut layer_id = layer_v6;
    if remaining >= 9 {
        reader.skip(5)?;
        layer_id = versioned_layer(layer_v6, reader.u32()?);
    }
    let keepout_restrictions = if remaining >= 10 {
        reader.u8()?
    } else if is_keepout {
        0x1F
    } else {
        0
    };
    reader.skip_subrecord()?;
    Ok(Arc {
        index,
        layer_id,
        layer_name: resolved_layer_name(layer_id, layer_names),
        net,
        component,
        polygon,
        subpolygon,
        center,
        radius,
        start_angle,
        end_angle,
        width,
        is_locked,
        is_keepout,
        is_polygon_outline,
        keepout_restrictions,
    })
}

pub(crate) fn parse_fill_record(
    reader: &mut BinaryReader<'_>,
    index: usize,
    layer_names: &HashMap<u32, String>,
) -> Result<Fill, AltiumParseError> {
    expect_record_type(reader, 6, "Fills6")?;
    reader.read_subrecord_len()?;
    let layer_v6 = reader.u8()? as u32;
    let flags1 = reader.u8()?;
    let is_locked = flags1 & 0x04 == 0;
    let flags2 = reader.u8()?;
    let is_keepout = flags2 == 2;
    let net = reader.u16()?;
    reader.skip(2)?;
    let component = reader.u16()?;
    reader.skip(4)?;
    let position1 = reader.point()?;
    let position2 = reader.point()?;
    let rotation = reader.f64()?;
    let remaining = reader.remaining_subrecord_bytes();
    let mut layer_id = layer_v6;
    if remaining >= 9 {
        reader.skip(5)?;
        layer_id = versioned_layer(layer_v6, reader.u32()?);
    }
    let keepout_restrictions = if remaining >= 10 {
        reader.u8()?
    } else if is_keepout {
        0x1F
    } else {
        0
    };
    reader.skip_subrecord()?;
    Ok(Fill {
        index,
        layer_id,
        layer_name: resolved_layer_name(layer_id, layer_names),
        component,
        net,
        position1,
        position2,
        rotation,
        is_locked,
        is_keepout,
        keepout_restrictions,
    })
}

pub(crate) fn parse_region_record(
    reader: &mut BinaryReader<'_>,
    index: usize,
    extended_vertices: bool,
    layer_names: &HashMap<u32, String>,
) -> Result<Region, AltiumParseError> {
    expect_record_type(reader, 11, "Regions6")?;
    reader.read_subrecord_len()?;
    let layer_v6 = reader.u8()? as u32;
    let flags1 = reader.u8()?;
    let is_locked = flags1 & 0x04 == 0;
    let flags2 = reader.u8()?;
    let is_keepout = flags2 == 2;
    let net = reader.u16()?;
    let polygon = reader.u16()?;
    let component = reader.u16()?;
    reader.skip(5)?;
    let hole_count = reader.u16()?;
    reader.skip(2)?;
    let properties = reader.read_properties()?;
    let layer_v7 = layer_id_from_name(&prop_string(&properties, "V7_LAYER").unwrap_or_default());
    let layer_id = versioned_layer(layer_v6, layer_v7);
    let raw_kind = prop_i32(&properties, "KIND", 0);
    let is_board_cutout = prop_bool(&properties, "ISBOARDCUTOUT", false);
    let is_shape_based = extended_vertices;
    let kind = region_kind_name(raw_kind, is_board_cutout).to_string();
    let keepout_restrictions = prop_u8(&properties, "KEEPOUTRESTRIC", 0x1F);
    let subpolygon = prop_u16(&properties, "SUBPOLYINDEX", ALTIUM_POLYGON_NONE);
    let outline_count = reader.u32()? as usize;
    let outline_count = if extended_vertices {
        outline_count.saturating_add(1)
    } else {
        outline_count
    };
    let mut outline = Vec::with_capacity(outline_count);
    for _ in 0..outline_count {
        outline.push(read_region_vertex(reader, extended_vertices)?);
    }
    let mut holes = Vec::with_capacity(hole_count as usize);
    for _ in 0..hole_count {
        if reader.remaining_subrecord_bytes() < 4 {
            break;
        }
        let hole_vertices = reader.u32()? as usize;
        let mut hole = Vec::with_capacity(hole_vertices);
        for _ in 0..hole_vertices {
            hole.push(read_region_double_vertex(reader)?);
        }
        holes.push(hole);
    }
    reader.skip_subrecord()?;
    Ok(Region {
        index,
        layer_id,
        layer_name: resolved_layer_name(layer_id, layer_names),
        net,
        component,
        polygon,
        subpolygon,
        kind,
        outline,
        holes,
        is_locked,
        is_keepout,
        is_shape_based,
        keepout_restrictions,
    })
}

fn read_region_vertex(
    reader: &mut BinaryReader<'_>,
    extended_vertices: bool,
) -> Result<Vertex, AltiumParseError> {
    if extended_vertices {
        let is_round = reader.u8()? != 0;
        let position = reader.point()?;
        let center = reader.point()?;
        let radius = coord_to_mil_i32(reader.i32()?);
        let start_angle = reader.f64()?;
        let end_angle = if reader.remaining_subrecord_bytes() >= 8 {
            reader.f64()?
        } else {
            start_angle
        };
        Ok(Vertex {
            is_round,
            radius,
            start_angle,
            end_angle,
            position,
            center: Some(center),
        })
    } else {
        read_region_double_vertex(reader)
    }
}

fn read_region_double_vertex(reader: &mut BinaryReader<'_>) -> Result<Vertex, AltiumParseError> {
    let x = double_coord_to_raw(reader.f64()?);
    let y = double_coord_to_raw(reader.f64()?);
    Ok(Vertex {
        is_round: false,
        radius: 0.0,
        start_angle: 0.0,
        end_angle: 0.0,
        position: point_from_raw(x, y),
        center: None,
    })
}

pub(crate) fn parse_text_record(
    reader: &mut BinaryReader<'_>,
    index: usize,
    layer_names: &HashMap<u32, String>,
    wide_strings: &BTreeMap<u32, String>,
) -> Result<Text, AltiumParseError> {
    expect_record_type(reader, 5, "Texts6")?;
    let subrecord1 = reader.read_subrecord_len()?;
    let layer_v6 = reader.u8()? as u32;
    reader.skip(6)?;
    let component = reader.u16()?;
    reader.skip(4)?;
    let position = reader.point()?;
    let height = coord_to_mil_i32(reader.i32()?);
    let _stroke_font_type = reader.u16()?;
    let rotation = reader.f64()?;
    let is_mirrored = reader.u8()? != 0;
    let stroke_width = coord_to_mil_i32(reader.i32()?);
    if subrecord1 < 123 {
        reader.skip_subrecord()?;
        return Ok(Text {
            index,
            layer_id: layer_v6,
            layer_name: resolved_layer_name(layer_v6, layer_names),
            component,
            position,
            height,
            rotation,
            stroke_width,
            font_type: "stroke".to_string(),
            font_name: None,
            text: String::new(),
            is_bold: false,
            is_italic: false,
            is_mirrored,
            is_comment: false,
            is_designator: false,
        });
    }
    let is_comment = reader.u8()? != 0;
    let is_designator = reader.u8()? != 0;
    reader.skip(1)?;
    let mut font_type = text_font_type_name(reader.u8()?).to_string();
    let is_bold = reader.u8()? != 0;
    let is_italic = reader.u8()? != 0;
    let font_name = Some(reader.utf16_fixed_string(64)?);
    reader.skip(1)?;
    let _margin = reader.i32()?;
    let wide_index = reader.u32()?;
    reader.skip(4)?;
    reader.skip(1)?;
    reader.skip(8)?;
    reader.skip(1)?;
    reader.skip(4)?;
    let remaining = reader.remaining_subrecord_bytes();
    let mut layer_id = layer_v6;
    if remaining >= 93 {
        reader.skip(25)?;
        font_type = text_font_type_name(reader.u8()?).to_string();
        reader.skip(64)?;
        reader.skip(1)?;
        layer_id = versioned_layer(layer_v6, reader.u32()?);
    }
    reader.skip_subrecord()?;
    reader.read_subrecord_len()?;
    let text = if let Some(value) = wide_strings.get(&wide_index) {
        value.clone()
    } else {
        reader.read_wx_string()?
    }
    .replace("\r\n", "\n");
    reader.skip_subrecord()?;
    Ok(Text {
        index,
        layer_id,
        layer_name: resolved_layer_name(layer_id, layer_names),
        component,
        position,
        height,
        rotation,
        stroke_width,
        font_type,
        font_name,
        text,
        is_bold,
        is_italic,
        is_mirrored,
        is_comment,
        is_designator,
    })
}

pub(crate) fn parse_wide_string_table(
    bytes: &[u8],
) -> Result<BTreeMap<u32, String>, AltiumParseError> {
    let mut reader = BinaryReader::new(bytes);
    let mut table = BTreeMap::new();
    while reader.remaining() >= 8 {
        let index = reader.u32()?;
        let byte_len = reader.u32()? as usize;
        if byte_len > reader.remaining() {
            break;
        }
        let bytes = reader.bytes(byte_len)?;
        table.insert(index, utf16le_string(bytes));
    }
    Ok(table)
}

fn expect_record_type(
    reader: &mut BinaryReader<'_>,
    expected: u8,
    stream: &str,
) -> Result<(), AltiumParseError> {
    let actual = reader.u8()?;
    if actual != expected {
        return Err(AltiumParseError::Invalid(format!(
            "{stream} has invalid record type {actual}; expected {expected}"
        )));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn subrecord(data: &[u8]) -> Vec<u8> {
        let mut out = Vec::new();
        out.extend_from_slice(&(data.len() as u32).to_le_bytes());
        out.extend_from_slice(data);
        out
    }

    fn region_body(
        layer: u8,
        net: u16,
        polygon: u16,
        hole_count: u16,
        properties: &[u8],
    ) -> Vec<u8> {
        let mut body = Vec::new();
        body.push(layer);
        body.push(0);
        body.push(0);
        body.extend_from_slice(&net.to_le_bytes());
        body.extend_from_slice(&polygon.to_le_bytes());
        body.extend_from_slice(&65535u16.to_le_bytes());
        body.extend_from_slice(&[0; 5]);
        body.extend_from_slice(&hole_count.to_le_bytes());
        body.extend_from_slice(&[0; 2]);
        body.extend_from_slice(&(properties.len() as u32).to_le_bytes());
        body.extend_from_slice(properties);
        body
    }

    fn shape_region_vertex(x: i32, y: i32) -> Vec<u8> {
        let mut body = Vec::new();
        body.push(0);
        body.extend_from_slice(&x.to_le_bytes());
        body.extend_from_slice(&y.to_le_bytes());
        body.extend_from_slice(&0i32.to_le_bytes());
        body.extend_from_slice(&0i32.to_le_bytes());
        body.extend_from_slice(&0i32.to_le_bytes());
        body.extend_from_slice(&0.0f64.to_le_bytes());
        body.extend_from_slice(&0.0f64.to_le_bytes());
        body
    }

    #[test]
    fn parses_region_double_coordinates_as_raw_internal_units() {
        let mut record = vec![11];
        let mut body = region_body(2, 7, 9, 0, b"V7_LAYER=MID1|KIND=0|");
        body.extend_from_slice(&3u32.to_le_bytes());
        for (x, y) in [(10000.0, 20000.0), (30000.0, 40000.0), (50000.0, 60000.0)] {
            body.extend_from_slice(&f64::to_le_bytes(x));
            body.extend_from_slice(&f64::to_le_bytes(y));
        }
        record.extend_from_slice(&subrecord(&body));

        let mut reader = BinaryReader::new(&record);
        let region = parse_region_record(&mut reader, 0, false, &HashMap::new()).unwrap();

        assert_eq!(region.layer_name, "MID1");
        assert_eq!(region.outline.len(), 3);
        assert_eq!(region.outline[0].position.x_raw, 10000);
        assert_eq!(region.outline[0].position.x, 1.0);
        assert_eq!(region.outline[0].position.y, -2.0);
    }

    #[test]
    fn parses_shape_based_region_with_closing_vertex() {
        let mut record = vec![11];
        let mut body = region_body(2, 7, 9, 0, b"V7_LAYER=MID1|KIND=0|");
        body.extend_from_slice(&2u32.to_le_bytes());
        for (x, y) in [
            (10000i32, 20000i32),
            (30000i32, 40000i32),
            (10000i32, 20000i32),
        ] {
            body.extend_from_slice(&shape_region_vertex(x, y));
        }
        record.extend_from_slice(&subrecord(&body));

        let mut reader = BinaryReader::new(&record);
        let region = parse_region_record(&mut reader, 0, true, &HashMap::new()).unwrap();

        assert_eq!(region.outline.len(), 3);
        assert_eq!(region.outline[1].position.x, 3.0);
        assert_eq!(reader.remaining(), 0);
    }

    #[test]
    fn parses_shape_based_region_holes_as_double_coordinates() {
        let mut record = vec![11];
        let mut body = region_body(2, 7, 9, 1, b"V7_LAYER=MID1|KIND=0|");
        body.extend_from_slice(&2u32.to_le_bytes());
        for (x, y) in [
            (10000i32, 20000i32),
            (30000i32, 40000i32),
            (10000i32, 20000i32),
        ] {
            body.extend_from_slice(&shape_region_vertex(x, y));
        }
        body.extend_from_slice(&2u32.to_le_bytes());
        for (x, y) in [(11000.0, 21000.0), (12000.0, 22000.0)] {
            body.extend_from_slice(&f64::to_le_bytes(x));
            body.extend_from_slice(&f64::to_le_bytes(y));
        }
        record.extend_from_slice(&subrecord(&body));

        let mut reader = BinaryReader::new(&record);
        let region = parse_region_record(&mut reader, 0, true, &HashMap::new()).unwrap();

        assert_eq!(region.holes.len(), 1);
        assert_eq!(region.holes[0].len(), 2);
        assert_eq!(region.holes[0][0].position.x, 1.1);
        assert_eq!(region.holes[0][0].position.y, -2.1);
        assert_eq!(reader.remaining(), 0);
    }

    #[test]
    fn lossy_binary_records_keep_complete_prefix() {
        let mut record = vec![11];
        let mut body = region_body(2, 7, 9, 0, b"V7_LAYER=MID1|KIND=0|");
        body.extend_from_slice(&1u32.to_le_bytes());
        body.extend_from_slice(&1.0f64.to_le_bytes());
        body.extend_from_slice(&2.0f64.to_le_bytes());
        record.extend_from_slice(&subrecord(&body));
        record.push(11);
        record.extend_from_slice(&100u32.to_le_bytes());

        let (regions, error) = parse_binary_records_lossy(&record, |reader, index| {
            parse_region_record(reader, index, false, &HashMap::new())
        });

        assert_eq!(regions.len(), 1);
        assert!(error.is_some());
    }

    #[test]
    fn parses_track_record() {
        let mut record = vec![4];
        let mut body = Vec::new();
        body.push(1);
        body.push(0);
        body.push(0);
        body.extend_from_slice(&7u16.to_le_bytes());
        body.extend_from_slice(&0u16.to_le_bytes());
        body.extend_from_slice(&0u16.to_le_bytes());
        body.extend_from_slice(&[0; 4]);
        body.extend_from_slice(&10000i32.to_le_bytes());
        body.extend_from_slice(&20000i32.to_le_bytes());
        body.extend_from_slice(&30000i32.to_le_bytes());
        body.extend_from_slice(&40000i32.to_le_bytes());
        body.extend_from_slice(&5000i32.to_le_bytes());
        body.extend_from_slice(&0u16.to_le_bytes());
        body.push(0);
        record.extend_from_slice(&subrecord(&body));
        let mut reader = BinaryReader::new(&record);
        let track = parse_track_record(&mut reader, 0, &HashMap::new()).unwrap();
        assert_eq!(track.net, 7);
        assert_eq!(track.layer_name, "TOP");
        assert_eq!(track.start.x, 1.0);
        assert_eq!(track.start.y, -2.0);
        assert_eq!(track.width, 0.5);
    }
}
