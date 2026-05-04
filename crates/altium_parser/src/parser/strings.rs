pub(crate) fn latin1_string(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| *byte as char).collect()
}

pub(crate) fn utf16le_string(bytes: &[u8]) -> String {
    let mut units = Vec::with_capacity(bytes.len() / 2);
    let mut index = 0;
    while index + 1 < bytes.len() {
        let value = u16::from_le_bytes([bytes[index], bytes[index + 1]]);
        if value == 0 {
            break;
        }
        units.push(value);
        index += 2;
    }
    String::from_utf16_lossy(&units)
}
