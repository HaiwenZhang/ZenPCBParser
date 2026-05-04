pub(crate) fn pad_shape_name(value: u8) -> &'static str {
    match value {
        1 => "circle",
        2 => "rectangle",
        3 => "octagonal",
        _ => "unknown",
    }
}

pub(crate) fn pad_shape_alt_name(value: u8) -> &'static str {
    match value {
        1 => "circle",
        2 => "rectangle",
        3 => "octagonal",
        9 => "roundrect",
        _ => "unknown",
    }
}

pub(crate) fn pad_hole_shape_name(value: u8) -> &'static str {
    match value {
        0 => "round",
        1 => "square",
        2 => "slot",
        _ => "unknown",
    }
}

pub(crate) fn pad_mode_name(value: u8) -> &'static str {
    match value {
        0 => "simple",
        1 => "top_middle_bottom",
        2 => "full_stack",
        _ => "unknown",
    }
}

pub(crate) fn region_kind_name(value: i32, is_board_cutout: bool) -> &'static str {
    match (value, is_board_cutout) {
        (0, true) => "board_cutout",
        (0, false) => "copper",
        (1, _) => "polygon_cutout",
        (2, _) => "dashed_outline",
        (3, _) => "unknown_3",
        (4, _) => "cavity_definition",
        _ => "unknown",
    }
}

pub(crate) fn text_font_type_name(value: u8) -> &'static str {
    match value {
        0 => "stroke",
        1 => "truetype",
        2 => "barcode",
        _ => "unknown",
    }
}
