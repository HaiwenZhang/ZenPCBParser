use super::constants::{MAX_LAYER_COUNT, MAX_VECTOR_COUNT};
use super::reader::Reader;
use super::{BrdParseError, FormatVersion};
use crate::model::{
    Component, ComponentInstance, Footprint, FootprintInstance, Keepout, Layer, LayerInfo, Net,
    NetAssignment, PadDefinition, Padstack, PadstackComponent, PlacedPad, Segment, Shape, Text,
    Track, Via,
};

#[derive(Debug, Clone, Default)]
pub(crate) struct BlockParse {
    pub(crate) key: Option<u32>,
    pub(crate) next: Option<u32>,
    pub(crate) net: Option<Net>,
    pub(crate) padstack: Option<Padstack>,
    pub(crate) component: Option<Component>,
    pub(crate) component_instance: Option<ComponentInstance>,
    pub(crate) footprint: Option<Footprint>,
    pub(crate) footprint_instance: Option<FootprintInstance>,
    pub(crate) pad_definition: Option<PadDefinition>,
    pub(crate) placed_pad: Option<PlacedPad>,
    pub(crate) via: Option<Via>,
    pub(crate) track: Option<Track>,
    pub(crate) segment: Option<Segment>,
    pub(crate) shape: Option<Shape>,
    pub(crate) keepout: Option<Keepout>,
    pub(crate) net_assignment: Option<NetAssignment>,
    pub(crate) text: Option<Text>,
    pub(crate) layer: Option<Layer>,
}

pub(crate) fn parse_block(
    reader: &mut Reader<'_>,
    version: FormatVersion,
    x27_end: usize,
) -> Result<BlockParse, BrdParseError> {
    let block_type = reader.u8()?;
    match block_type {
        0x01 => parse_arc_or_segment(reader, version, block_type, true),
        0x03 => parse_field(reader, version),
        0x04 => parse_net_assignment(reader, version),
        0x05 => parse_track(reader, version),
        0x06 => parse_component(reader, version),
        0x07 => parse_component_inst(reader, version),
        0x08 => parse_pin_number(reader, version),
        0x09 => parse_fill_link(reader, version),
        0x0A => parse_drc(reader, version),
        0x0C => parse_pin_def(reader, version),
        0x0D => parse_pad(reader, version),
        0x0E => parse_rect_0e(reader, version),
        0x0F => parse_function_slot(reader, version),
        0x10 => parse_function_inst(reader, version),
        0x11 => parse_pin_name(reader, version),
        0x12 => parse_xref(reader, version),
        0x14 => parse_graphic(reader, version),
        0x15 | 0x16 | 0x17 => parse_arc_or_segment(reader, version, block_type, false),
        0x1B => parse_net(reader, version),
        0x1C => parse_padstack(reader, version),
        0x1D => parse_constraint_set(reader, version),
        0x1E => parse_si_model(reader, version),
        0x1F => parse_padstack_dim(reader, version),
        0x20 => parse_0x20(reader, version),
        0x21 => parse_blob_0x21(reader),
        0x22 => parse_0x22(reader, version),
        0x23 => parse_ratline(reader, version),
        0x24 => parse_rect_0x24(reader, version),
        0x26 => parse_match_group(reader, version),
        0x27 => parse_xref_0x27(reader, x27_end),
        0x28 => parse_shape(reader, version),
        0x29 => parse_pin_0x29(reader),
        0x2A => parse_layer_list(reader, version),
        0x2B => parse_footprint(reader, version),
        0x2C => parse_table(reader, version),
        0x2D => parse_footprint_inst(reader, version),
        0x2E => parse_connection(reader, version),
        0x2F => parse_0x2f(reader),
        0x30 => parse_text_wrapper(reader, version),
        0x31 => parse_string_graphic(reader, version),
        0x32 => parse_placed_pad(reader, version),
        0x33 => parse_via(reader, version),
        0x34 => parse_keepout(reader, version),
        0x35 => parse_file_ref(reader),
        0x36 => parse_def_table(reader, version),
        0x37 => parse_ptr_array(reader, version),
        0x38 => parse_film(reader, version),
        0x39 => parse_film_layer_list(reader),
        0x3A => parse_film_list_node(reader, version),
        0x3B => parse_property(reader, version),
        0x3C => parse_key_list(reader, version),
        _ => Err(BrdParseError::Invalid(format!(
            "unsupported block type 0x{block_type:02x}"
        ))),
    }
}

fn parse_arc_or_segment(
    reader: &mut Reader<'_>,
    version: FormatVersion,
    block_type: u8,
    arc: bool,
) -> Result<BlockParse, BrdParseError> {
    if arc {
        reader.skip(1)?;
        let _unknown_byte = reader.u8()?;
        let subtype = reader.u8()?;
        let key = reader.u32()?;
        let next = reader.u32()?;
        let parent = reader.u32()?;
        let _unknown1 = reader.u32()?;
        if version.ge(FormatVersion::V172) {
            reader.skip_u32(1)?;
        }
        let width_raw = reader.u32()?;
        let start_raw = [reader.i32()?, reader.i32()?];
        let end_raw = [reader.i32()?, reader.i32()?];
        let center_raw = [reader.allegro_f64()?, reader.allegro_f64()?];
        let radius_raw = reader.allegro_f64()?;
        let bbox_raw = reader.i32_array4()?;
        let clockwise = (subtype & 0x40) != 0;
        return Ok(BlockParse {
            key: Some(key),
            next: Some(next),
            segment: Some(Segment {
                key,
                next,
                parent,
                block_type,
                kind: "arc".to_string(),
                width_raw,
                start_raw,
                end_raw,
                center_raw: Some(center_raw),
                radius_raw: Some(radius_raw),
                bbox_raw: Some(bbox_raw),
                clockwise: Some(clockwise),
            }),
            ..BlockParse::default()
        });
    }
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    let parent = reader.u32()?;
    let _flags = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let width_raw = reader.u32()?;
    let start_raw = [reader.i32()?, reader.i32()?];
    let end_raw = [reader.i32()?, reader.i32()?];
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        segment: Some(Segment {
            key,
            next,
            parent,
            block_type,
            kind: "line".to_string(),
            width_raw,
            start_raw,
            end_raw,
            center_raw: None,
            radius_raw: None,
            bbox_raw: None,
            clockwise: None,
        }),
        ..BlockParse::default()
    })
}

fn parse_field(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let _hdr = reader.u16()?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let subtype = reader.u8()?;
    let _hdr2 = reader.u8()?;
    let size = reader.u16()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    match subtype {
        0x65 => {}
        0x64 | 0x66 | 0x67 | 0x6A => reader.skip_u32(1)?,
        0x69 => reader.skip_u32(2)?,
        0x68 | 0x6B | 0x6D | 0x6E | 0x6F | 0x71 | 0x73 | 0x78 => {
            let _ = reader.fixed_string(size as usize, true)?;
        }
        0x6C => {
            let n = guarded_count(reader.u32()?, "0x03 subtype 0x6c")?;
            reader.skip_u32(n as usize)?;
        }
        0x70 | 0x74 => {
            let x0 = reader.u16()? as usize;
            let x1 = reader.u16()? as usize;
            reader.skip(x1 + 4 * x0)?;
        }
        0xF6 => reader.skip_u32(20)?,
        _ if size == 0 => {}
        _ if size == 4 => reader.skip_u32(1)?,
        _ if size == 8 => reader.skip_u32(2)?,
        _ => {
            reader.skip(size as usize)?;
            reader.align_u32()?;
        }
    }
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        ..BlockParse::default()
    })
}

fn parse_net_assignment(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    let net = reader.u32()?;
    let conn_item = reader.u32()?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        net_assignment: Some(NetAssignment {
            key,
            next,
            net,
            conn_item,
        }),
        ..BlockParse::default()
    })
}

fn parse_track(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let layer = parse_layer_info(reader)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    let net_assignment = reader.u32()?;
    reader.skip_u32(8)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(2)?;
    }
    let first_segment = reader.u32()?;
    reader.skip_u32(2)?;
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        track: Some(Track {
            key,
            next,
            layer,
            net_assignment,
            first_segment,
        }),
        ..BlockParse::default()
    })
}

fn parse_component(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    let device_type_string_id = reader.u32()?;
    let symbol_name_string_id = reader.u32()?;
    let first_instance = reader.u32()?;
    let function_slot = reader.u32()?;
    let pin_number = reader.u32()?;
    let fields = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        component: Some(Component {
            key,
            next,
            device_type_string_id,
            device_type: None,
            symbol_name_string_id,
            symbol_name: None,
            first_instance,
            function_slot,
            pin_number,
            fields,
        }),
        ..BlockParse::default()
    })
}

fn parse_component_inst(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(3)?;
    }
    let footprint_instance = reader.u32()?;
    if version.lt(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let refdes_string_id = reader.u32()?;
    let function_instance = reader.u32()?;
    let fields = reader.u32()?;
    reader.skip_u32(1)?;
    let first_pad = reader.u32()?;
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        component_instance: Some(ComponentInstance {
            key,
            next,
            footprint_instance,
            refdes_string_id,
            refdes: None,
            function_instance,
            fields,
            first_pad,
        }),
        ..BlockParse::default()
    })
}

fn parse_pin_number(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    if version.lt(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let next = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(1)?;
    Ok(with_key_next(key, next))
}

fn parse_fill_link(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    reader.skip_u32(4)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(5)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_drc(reader: &mut Reader<'_>, version: FormatVersion) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip(16)?;
    reader.skip_u32(4)?;
    reader.skip_u32(5)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_pin_def(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(2)?;
    if version.ge(FormatVersion::V172) {
        reader.skip(12)?;
    } else {
        reader.skip(8)?;
    }
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V180) {
        reader.skip_u32(1)?;
    }
    reader.skip(16)?;
    reader.skip_u32(3)?;
    if version.ge(FormatVersion::V174) && version.lt(FormatVersion::V180) {
        reader.skip_u32(1)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_pad(reader: &mut Reader<'_>, version: FormatVersion) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let name_string_id = reader.u32()?;
    let next = reader.u32()?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    let x_raw = reader.i32()?;
    let y_raw = reader.i32()?;
    let padstack = reader.u32()?;
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let flags = reader.u32()?;
    let rotation_mdeg = reader.u32()?;
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        pad_definition: Some(PadDefinition {
            key,
            next,
            name_string_id,
            name: None,
            x_raw,
            y_raw,
            padstack,
            flags,
            rotation_mdeg,
        }),
        ..BlockParse::default()
    })
}

fn parse_rect_0e(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(4)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(2)?;
    }
    reader.skip(16)?;
    reader.skip_u32(3)?;
    reader.skip_u32(1)?;
    Ok(with_key_next(key, next))
}

fn parse_function_slot(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    if version.ge(FormatVersion::V181) {
        reader.skip_u32(3)?;
        let next = reader.u32()?;
        reader.skip_u32(3)?;
        return Ok(with_key_next(key, next));
    }
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    reader.skip(32)?;
    let next = if version.ge(FormatVersion::V172) {
        Some(reader.u32()?)
    } else {
        None
    };
    reader.skip_u32(3)?;
    Ok(BlockParse {
        key: Some(key),
        next,
        ..BlockParse::default()
    })
}

fn parse_function_inst(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(5)?;
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_pin_name(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    reader.skip_u32(1)?;
    let next = reader.u32()?;
    reader.skip_u32(2)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_xref(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    reader.skip_u32(4)?;
    if version.ge(FormatVersion::V165) {
        reader.skip_u32(1)?;
    }
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_graphic(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(2)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(3)?;
    Ok(with_key_next(key, next))
}

fn parse_net(reader: &mut Reader<'_>, version: FormatVersion) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    let name_string_id = reader.u32()?;
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(1)?;
    let assignment = reader.u32()?;
    reader.skip_u32(1)?;
    let fields = reader.u32()?;
    let match_group = reader.u32()?;
    reader.skip_u32(4)?;
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        net: Some(Net {
            key,
            next,
            name_string_id,
            name: None,
            assignment,
            fields,
            match_group,
        }),
        ..BlockParse::default()
    })
}

fn parse_padstack(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let n = reader.u8()?;
    reader.skip(1)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    let name_string_id = reader.u32()?;
    let (layer_count, drill_size_raw) = if version.lt(FormatVersion::V172) {
        let drill = reader.u32()?;
        reader.skip_u32(5)?;
        reader.skip(4)?;
        reader.skip(2)?;
        reader.skip(4)?;
        let layer_count = reader.u16()?;
        reader.skip_u32(8)?;
        if version.ge(FormatVersion::V165) {
            reader.skip_u32(1)?;
        }
        (layer_count, Some(drill))
    } else {
        reader.skip_u32(3)?;
        reader.skip(4)?;
        reader.skip_u32(2)?;
        reader.skip(4)?;
        let layer_count = reader.u16()?;
        reader.skip(2)?;
        reader.skip_u32(4)?;
        let drill = reader.u32()?;
        reader.skip_u32(6)?;
        reader.skip_u32(4)?;
        reader.skip_u32(21)?;
        if version.ge(FormatVersion::V180) {
            reader.skip_u32(8)?;
        }
        (layer_count, Some(drill))
    };
    if layer_count > MAX_LAYER_COUNT {
        return Err(BrdParseError::Invalid(format!(
            "padstack layer count {layer_count} exceeds {MAX_LAYER_COUNT}"
        )));
    }
    let fixed_component_count = if version.lt(FormatVersion::V165) {
        10
    } else if version.lt(FormatVersion::V172) {
        11
    } else {
        21
    };
    let components_per_layer = if version.lt(FormatVersion::V172) {
        3
    } else {
        4
    };
    let component_count = fixed_component_count + layer_count as usize * components_per_layer;
    let mut components = Vec::with_capacity(component_count);
    for index in 0..component_count {
        let component_type = reader.u8()?;
        reader.skip(3)?;
        if version.ge(FormatVersion::V172) {
            reader.skip_u32(1)?;
        }
        let width_raw = reader.i32()?;
        let height_raw = reader.i32()?;
        let z1_raw = if version.ge(FormatVersion::V172) {
            Some(reader.i32()?)
        } else {
            None
        };
        let x_offset_raw = reader.i32()?;
        let y_offset_raw = reader.i32()?;
        let shape_key = reader.u32()?;
        let z2_raw = if version.ge(FormatVersion::V172) || index < component_count - 1 {
            Some(reader.u32()?)
        } else {
            None
        };
        let (layer_index, role) =
            padstack_component_role(index, fixed_component_count, components_per_layer);
        components.push(PadstackComponent {
            slot_index: index,
            layer_index,
            role: role.to_string(),
            component_type,
            type_name: padstack_component_type_name(component_type).to_string(),
            width_raw,
            height_raw,
            z1_raw,
            x_offset_raw,
            y_offset_raw,
            shape_key,
            z2_raw,
        });
    }
    let trailing = n as usize
        * if version.lt(FormatVersion::V172) {
            8
        } else {
            10
        };
    reader.skip_u32(trailing)?;
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        padstack: Some(Padstack {
            key,
            next,
            name_string_id,
            name: None,
            layer_count,
            drill_size_raw,
            fixed_component_count,
            components_per_layer,
            components,
        }),
        ..BlockParse::default()
    })
}

fn padstack_component_role(
    index: usize,
    fixed_component_count: usize,
    components_per_layer: usize,
) -> (Option<usize>, &'static str) {
    if index < fixed_component_count || components_per_layer == 0 {
        return (None, "fixed");
    }
    let relative = index - fixed_component_count;
    let layer_index = relative / components_per_layer;
    let role = match relative % components_per_layer {
        0 => "antipad",
        1 => "thermal_relief",
        2 => "pad",
        3 => "keepout",
        _ => "unknown",
    };
    (Some(layer_index), role)
}

fn padstack_component_type_name(component_type: u8) -> &'static str {
    match component_type {
        0x00 => "NULL",
        0x02 => "CIRCLE",
        0x03 => "OCTAGON",
        0x04 => "CROSS",
        0x05 => "SQUARE",
        0x06 => "RECTANGLE",
        0x07 => "DIAMOND",
        0x0A => "PENTAGON",
        0x0B => "OBLONG_X",
        0x0C => "OBLONG_Y",
        0x0F => "HEXAGON_X",
        0x10 => "HEXAGON_Y",
        0x12 => "TRIANGLE",
        0x16 => "SHAPE_SYMBOL",
        0x17 => "FLASH",
        0x19 => "DONUT",
        0x1B => "ROUNDED_RECTANGLE",
        0x1C => "CHAMFERED_RECTANGLE",
        0x1E => "NSIDED_POLYGON",
        0xEE => "APERTURE_EXT",
        _ => "UNKNOWN",
    }
}

fn parse_constraint_set(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(2)?;
    let size_a = reader.u16()? as usize;
    let size_b = reader.u16()? as usize;
    reader.skip(size_b * 56)?;
    reader.skip(size_a * 256)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_si_model(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    if version.ge(FormatVersion::V164) {
        reader.skip(4)?;
    }
    reader.skip_u32(1)?;
    let size = reader.u32()? as usize;
    let _ = reader.fixed_string(size, true)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    if version.ge(FormatVersion::V181) {
        align_to_expected_key(reader, next, 16)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_padstack_dim(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(3)?;
    reader.skip(2)?;
    let size = reader.u16()? as usize;
    let sub_size = if version.ge(FormatVersion::V175) {
        size * 384 + 8
    } else if version.ge(FormatVersion::V172) {
        size * 280 + 8
    } else if version.ge(FormatVersion::V162) {
        size * 280 + 4
    } else {
        size * 240 + 4
    };
    reader.skip(sub_size)?;
    Ok(with_key_next(key, next))
}

fn parse_0x20(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(7)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(10)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_blob_0x21(reader: &mut Reader<'_>) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let size = reader.u32()?;
    if size < 12 {
        return Err(BrdParseError::Invalid(format!(
            "block 0x21 size {size} is too small"
        )));
    }
    let key = reader.u32()?;
    reader.skip(size as usize - 12)?;
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_0x22(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(8)?;
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_ratline(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(4)?;
    reader.skip(20)?;
    reader.skip_u32(4)?;
    if version.ge(FormatVersion::V164) {
        reader.skip_u32(4)?;
    }
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_rect_0x24(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(2)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip(16)?;
    reader.skip_u32(4)?;
    Ok(with_key_next(key, next))
}

fn parse_match_group(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(2)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_xref_0x27(reader: &mut Reader<'_>, x27_end: usize) -> Result<BlockParse, BrdParseError> {
    if x27_end <= reader.position() {
        return Err(BrdParseError::Invalid(format!(
            "block 0x27 end 0x{x27_end:08x} is before current offset 0x{:08x}",
            reader.position()
        )));
    }
    let total = x27_end - 1 - reader.position();
    reader.skip(total)?;
    Ok(BlockParse::default())
}

fn parse_shape(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let layer = parse_layer_info(reader)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(2)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(2)?;
    }
    reader.skip_u32(2)?;
    let first_keepout = reader.u32()?;
    let first_segment = reader.u32()?;
    reader.skip_u32(2)?;
    let table = if version.ge(FormatVersion::V172) {
        reader.u32()?
    } else {
        0
    };
    reader.skip_u32(1)?;
    let table = if version.lt(FormatVersion::V172) {
        reader.u32()?
    } else {
        table
    };
    let coords_raw = reader.i32_array4()?;
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        shape: Some(Shape {
            key,
            next,
            layer,
            first_segment,
            first_keepout,
            table,
            coords_raw,
        }),
        ..BlockParse::default()
    })
}

fn parse_pin_0x29(reader: &mut Reader<'_>) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    reader.skip_u32(4)?;
    reader.skip(8)?;
    reader.skip_u32(5)?;
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_layer_list(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let num_entries = reader.u16()? as usize;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    let mut names = Vec::new();
    if version.lt(FormatVersion::V165) {
        for _ in 0..num_entries {
            names.push(reader.fixed_string(36, true)?);
        }
    } else {
        for _ in 0..num_entries {
            let name_id = reader.u32()?;
            names.push(format!("string:{name_id}"));
            reader.skip_u32(2)?;
        }
    }
    let key = reader.u32()?;
    Ok(BlockParse {
        key: Some(key),
        layer: Some(Layer {
            key,
            class_code: 0,
            names,
        }),
        ..BlockParse::default()
    })
}

fn parse_footprint(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let name_string_id = reader.u32()?;
    reader.skip_u32(1)?;
    let coords_raw = reader.u32_array4()?;
    let next = reader.u32()?;
    let first_instance = reader.u32()?;
    reader.skip_u32(3)?;
    let sym_lib_path_string_id = reader.u32()?;
    reader.skip_u32(3)?;
    if version.ge(FormatVersion::V164) {
        reader.skip_u32(1)?;
    }
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        footprint: Some(Footprint {
            key,
            next,
            name_string_id,
            name: None,
            first_instance,
            sym_lib_path_string_id,
            sym_lib_path: None,
            coords_raw,
        }),
        ..BlockParse::default()
    })
}

fn parse_table(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(3)?;
    }
    reader.skip_u32(1)?;
    if version.lt(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(4)?;
    Ok(with_key_next(key, next))
}

fn parse_footprint_inst(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let layer = reader.u8()?;
    reader.skip(1)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let legacy_component_instance = if version.lt(FormatVersion::V172) {
        Some(reader.u32()?)
    } else {
        None
    };
    reader.skip(4)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(1)?;
    let rotation_mdeg = reader.u32()?;
    let x_raw = reader.i32()?;
    let y_raw = reader.i32()?;
    let component_instance = if version.ge(FormatVersion::V172) {
        reader.u32()?
    } else {
        legacy_component_instance.unwrap_or(0)
    };
    let graphic = reader.u32()?;
    let first_pad = reader.u32()?;
    let text = reader.u32()?;
    reader.skip_u32(4)?;
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        footprint_instance: Some(FootprintInstance {
            key,
            next,
            layer,
            rotation_mdeg,
            x_raw,
            y_raw,
            component_instance,
            graphic,
            first_pad,
            text,
        }),
        ..BlockParse::default()
    })
}

fn parse_connection(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(6)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_0x2f(reader: &mut Reader<'_>) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    reader.skip_u32(6)?;
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_text_wrapper(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let layer = parse_layer_info(reader)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(2)?;
        reader.skip(4)?;
        reader.skip_u32(1)?;
    }
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    let string_graphic_key = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    } else {
        reader.skip_u32(1)?;
        reader.skip(4)?;
    }
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let x_raw = reader.i32()?;
    let y_raw = reader.i32()?;
    reader.skip_u32(1)?;
    let rotation_mdeg = reader.u32()?;
    if version.lt(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        text: Some(Text {
            key,
            next: Some(next),
            layer: Some(layer),
            text: None,
            x_raw: Some(x_raw),
            y_raw: Some(y_raw),
            rotation_mdeg: Some(rotation_mdeg),
            string_graphic_key: Some(string_graphic_key),
        }),
        ..BlockParse::default()
    })
}

fn parse_string_graphic(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let wrapper = reader.u32()?;
    let x_raw = reader.i32()?;
    let y_raw = reader.i32()?;
    reader.skip(2)?;
    let len = reader.u16()?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    let text = reader.fixed_string(len as usize, true)?;
    Ok(BlockParse {
        key: Some(key),
        text: Some(Text {
            key,
            next: None,
            layer: None,
            text: Some(text),
            x_raw: Some(x_raw),
            y_raw: Some(y_raw),
            rotation_mdeg: None,
            string_graphic_key: Some(wrapper),
        }),
        ..BlockParse::default()
    })
}

fn parse_placed_pad(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let layer = parse_layer_info(reader)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    let net_assignment = reader.u32()?;
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(1)?;
    let parent_footprint = reader.u32()?;
    reader.skip_u32(1)?;
    let pad = reader.u32()?;
    reader.skip_u32(2)?;
    let pin_number = reader.u32()?;
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let name_text = reader.u32()?;
    reader.skip_u32(1)?;
    let coords_raw = reader.i32_array4()?;
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        placed_pad: Some(PlacedPad {
            key,
            next,
            layer,
            net_assignment,
            parent_footprint,
            pad,
            pin_number,
            name_text,
            coords_raw,
        }),
        ..BlockParse::default()
    })
}

fn parse_via(reader: &mut Reader<'_>, version: FormatVersion) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let layer = parse_layer_info(reader)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    let net_assignment = reader.u32()?;
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let x_raw = reader.i32()?;
    let y_raw = reader.i32()?;
    reader.skip_u32(1)?;
    let padstack = reader.u32()?;
    reader.skip_u32(4)?;
    reader.skip(16)?;
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        via: Some(Via {
            key,
            next,
            layer,
            net_assignment,
            padstack,
            x_raw,
            y_raw,
        }),
        ..BlockParse::default()
    })
}

fn parse_keepout(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let layer = parse_layer_info(reader)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let flags = reader.u32()?;
    let first_segment = reader.u32()?;
    reader.skip_u32(2)?;
    Ok(BlockParse {
        key: Some(key),
        next: Some(next),
        keepout: Some(Keepout {
            key,
            next,
            layer,
            flags,
            first_segment,
        }),
        ..BlockParse::default()
    })
}

fn parse_file_ref(reader: &mut Reader<'_>) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    reader.skip(120)?;
    Ok(BlockParse::default())
}

fn parse_def_table(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let code = reader.u16()?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let num_items = guarded_count(reader.u32()?, "0x36 num_items")?;
    let count = reader.u32()?;
    if count > num_items as u32 {
        return Err(BrdParseError::Invalid(format!(
            "block 0x36 count {count} exceeds capacity {num_items}"
        )));
    }
    reader.skip_u32(2)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    for _ in 0..num_items {
        match code {
            0x02 => {
                let _ = reader.fixed_string(32, true)?;
                reader.skip_u32(14)?;
                if version.ge(FormatVersion::V164) {
                    reader.skip_u32(3)?;
                }
                if version.ge(FormatVersion::V172) {
                    reader.skip_u32(2)?;
                }
            }
            0x03 => {
                let _ = reader.fixed_string(
                    if version.ge(FormatVersion::V172) {
                        64
                    } else {
                        32
                    },
                    true,
                )?;
                if version.ge(FormatVersion::V174) {
                    reader.skip_u32(1)?;
                }
            }
            0x05 => {
                reader.skip(28)?;
                if version.ge(FormatVersion::V174) {
                    reader.skip_u32(1)?;
                }
            }
            0x06 => {
                reader.skip(8)?;
                if version.lt(FormatVersion::V172) {
                    reader.skip_u32(50)?;
                }
            }
            0x08 => {
                reader.skip_u32(4)?;
                if version.ge(FormatVersion::V174) && version.lt(FormatVersion::V181) {
                    reader.skip_u32(1)?;
                }
                reader.skip_u32(4)?;
                if version.ge(FormatVersion::V172) {
                    reader.skip_u32(8)?;
                }
            }
            0x0B => reader.skip(1016)?,
            0x0C => reader.skip(232)?,
            0x0D => reader.skip(200)?,
            0x0F => reader.skip_u32(5)?,
            0x10 => {
                reader.skip(108)?;
                if version.ge(FormatVersion::V180) {
                    reader.skip_u32(1)?;
                }
            }
            0x12 => reader.skip(1052)?,
            _ => {
                return Err(BrdParseError::Invalid(format!(
                    "unknown 0x36 substruct type 0x{code:02x}"
                )))
            }
        }
    }
    Ok(with_key_next(key, next))
}

fn parse_ptr_array(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    reader.skip_u32(1)?;
    let next = reader.u32()?;
    reader.skip_u32(3)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    reader.skip_u32(100)?;
    Ok(with_key_next(key, next))
}

fn parse_film(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(1)?;
    if version.lt(FormatVersion::V166) {
        let _ = reader.fixed_string(20, true)?;
    } else {
        reader.skip_u32(2)?;
    }
    reader.skip_u32(7)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_film_layer_list(reader: &mut Reader<'_>) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    reader.skip_u32(2)?;
    reader.skip(44)?;
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn parse_film_list_node(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(1)?;
    let _layer = parse_layer_info(reader)?;
    let key = reader.u32()?;
    let next = reader.u32()?;
    reader.skip_u32(1)?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    Ok(with_key_next(key, next))
}

fn parse_property(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let len = reader.u32()? as usize;
    let _ = reader.fixed_string(128, true)?;
    let _ = reader.fixed_string(32, true)?;
    reader.skip_u32(2)?;
    if version.ge(FormatVersion::V172) {
        reader.skip_u32(1)?;
    }
    let _ = reader.fixed_string(len, true)?;
    Ok(BlockParse::default())
}

fn parse_key_list(
    reader: &mut Reader<'_>,
    version: FormatVersion,
) -> Result<BlockParse, BrdParseError> {
    reader.skip(3)?;
    let key = reader.u32()?;
    if version.ge(FormatVersion::V174) {
        reader.skip_u32(1)?;
    }
    let n = guarded_count(reader.u32()?, "0x3c entries")?;
    reader.skip_u32(n as usize)?;
    Ok(BlockParse {
        key: Some(key),
        ..BlockParse::default()
    })
}

fn with_key_next(key: u32, next: u32) -> BlockParse {
    BlockParse {
        key: Some(key),
        next: Some(next),
        ..BlockParse::default()
    }
}

fn align_to_expected_key(
    reader: &mut Reader<'_>,
    expected_key: u32,
    max_scan: usize,
) -> Result<(), BrdParseError> {
    if expected_key == 0 {
        return Ok(());
    }
    let start = reader.position();
    for extra in (0..=max_scan).step_by(4) {
        let candidate = start + extra;
        if candidate + 8 > reader.bytes.len() {
            break;
        }
        let block_type = reader.bytes[candidate];
        if block_type == 0 || block_type > 0x3C {
            continue;
        }
        let key_offset = candidate + 4;
        let key = u32::from_le_bytes([
            reader.bytes[key_offset],
            reader.bytes[key_offset + 1],
            reader.bytes[key_offset + 2],
            reader.bytes[key_offset + 3],
        ]);
        if key == expected_key {
            reader.seek(candidate)?;
            break;
        }
    }
    Ok(())
}

fn parse_layer_info(reader: &mut Reader<'_>) -> Result<LayerInfo, BrdParseError> {
    let class_code = reader.u8()?;
    let subclass_code = reader.u8()?;
    Ok(LayerInfo {
        class_code,
        subclass_code,
        class_name: layer_class_name(class_code).to_string(),
        subclass_name: fixed_subclass_name(class_code, subclass_code).map(ToOwned::to_owned),
    })
}

pub(crate) fn scan_zero_gap(reader: &mut Reader<'_>) -> Result<Option<usize>, BrdParseError> {
    let mut scan_pos = reader.position();
    while let Some(value) = reader.peek_u8()? {
        if value == 0 {
            reader.skip(1)?;
            scan_pos = reader.position();
            continue;
        }
        if value <= 0x3C {
            let block_start = scan_pos - (scan_pos % 4);
            return Ok(Some(block_start));
        }
        return Ok(None);
    }
    Ok(None)
}

pub(crate) fn merge_text(existing: &mut Text, incoming: &Text) {
    if existing.text.is_none() {
        existing.text = incoming.text.clone();
    }
    if existing.layer.is_none() {
        existing.layer = incoming.layer.clone();
    }
    if existing.x_raw.is_none() {
        existing.x_raw = incoming.x_raw;
    }
    if existing.y_raw.is_none() {
        existing.y_raw = incoming.y_raw;
    }
    if existing.rotation_mdeg.is_none() {
        existing.rotation_mdeg = incoming.rotation_mdeg;
    }
    if existing.string_graphic_key.is_none() {
        existing.string_graphic_key = incoming.string_graphic_key;
    }
}

fn guarded_count(value: u32, label: &str) -> Result<usize, BrdParseError> {
    if value > MAX_VECTOR_COUNT {
        return Err(BrdParseError::Invalid(format!(
            "{label} count {value} exceeds limit {MAX_VECTOR_COUNT}"
        )));
    }
    Ok(value as usize)
}

fn layer_class_name(code: u8) -> &'static str {
    match code {
        0x01 => "BOARD_GEOMETRY",
        0x02 => "COMPONENT_VALUE",
        0x03 => "DEVICE_TYPE",
        0x04 => "DRAWING_FORMAT",
        0x05 => "DRC_ERROR",
        0x06 => "ETCH",
        0x07 => "MANUFACTURING",
        0x08 => "ANALYSIS",
        0x09 => "PACKAGE_GEOMETRY",
        0x0A => "PACKAGE_KEEPIN",
        0x0B => "PACKAGE_KEEPOUT",
        0x0C => "PIN",
        0x0D => "REF_DES",
        0x0E => "ROUTE_KEEPIN",
        0x0F => "ROUTE_KEEPOUT",
        0x10 => "TOLERANCE",
        0x11 => "USER_PART_NUMBER",
        0x12 => "VIA_CLASS",
        0x13 => "VIA_KEEPOUT",
        0x14 => "ANTI_ETCH",
        0x15 => "BOUNDARY",
        0x16 => "CONSTRAINTS_REGION",
        _ => "UNKNOWN",
    }
}

fn fixed_subclass_name(class_code: u8, subclass_code: u8) -> Option<&'static str> {
    match (class_code, subclass_code) {
        (0x01, 0xEA) => Some("BGEOM_OUTLINE"),
        (0x04, 0xFD) => Some("DFMT_OUTLINE"),
        (_, 0xF8) => Some("DISPLAY_BOTTOM"),
        (_, 0xF9) => Some("DISPLAY_TOP"),
        (_, 0xFA) => Some("SILKSCREEN_BOTTOM"),
        (_, 0xFB) => Some("SILKSCREEN_TOP"),
        (_, 0xFC) => Some("ASSEMBLY_BOTTOM"),
        (_, 0xFD) => Some("ASSEMBLY_TOP_OR_ALL"),
        _ => None,
    }
}

pub(crate) fn block_type_name(block_type: u8) -> &'static str {
    match block_type {
        0x01 => "ARC",
        0x03 => "FIELD",
        0x04 => "NET_ASSIGNMENT",
        0x05 => "TRACK",
        0x06 => "COMPONENT",
        0x07 => "COMPONENT_INST",
        0x08 => "PIN_NUMBER",
        0x09 => "FILL_LINK",
        0x0A => "DRC",
        0x0C => "PIN_DEF",
        0x0D => "PAD",
        0x0E => "RECT_0E",
        0x0F => "FUNCTION_SLOT",
        0x10 => "FUNCTION_INST",
        0x11 => "PIN_NAME",
        0x12 => "XREF",
        0x14 => "GRAPHIC",
        0x15 | 0x16 | 0x17 => "SEGMENT",
        0x1B => "NET",
        0x1C => "PADSTACK",
        0x1D => "CONSTRAINT_SET",
        0x1E => "SI_MODEL",
        0x1F => "PADSTACK_DIM",
        0x20 => "UNKNOWN_20",
        0x21 => "BLOB",
        0x22 => "UNKNOWN_22",
        0x23 => "RATLINE",
        0x24 => "RECT",
        0x26 => "MATCH_GROUP",
        0x27 => "CSTRMGR_XREF",
        0x28 => "SHAPE",
        0x29 => "PIN",
        0x2A => "LAYER_LIST",
        0x2B => "FOOTPRINT_DEF",
        0x2C => "TABLE",
        0x2D => "FOOTPRINT_INST",
        0x2E => "CONNECTION",
        0x2F => "UNKNOWN_2F",
        0x30 => "TEXT_WRAPPER",
        0x31 => "STRING_GRAPHIC",
        0x32 => "PLACED_PAD",
        0x33 => "VIA",
        0x34 => "KEEPOUT",
        0x35 => "FILE_REF",
        0x36 => "DEF_TABLE",
        0x37 => "PTR_ARRAY",
        0x38 => "FILM",
        0x39 => "FILM_LAYER_LIST",
        0x3A => "FILM_LIST_NODE",
        0x3B => "PROPERTY",
        0x3C => "KEY_LIST",
        _ => "UNKNOWN",
    }
}
