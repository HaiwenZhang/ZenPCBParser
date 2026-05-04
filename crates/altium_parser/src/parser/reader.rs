use super::geometry::{point_from_raw, size_from_raw};
use super::properties::parse_properties_payload;
use super::strings::{latin1_string, utf16le_string};
use super::AltiumParseError;
use crate::model::{Point, Size};
use std::collections::BTreeMap;

pub(crate) struct BinaryReader<'a> {
    data: &'a [u8],
    position: usize,
    subrecord_end: Option<usize>,
}

impl<'a> BinaryReader<'a> {
    pub(crate) fn new(data: &'a [u8]) -> Self {
        Self {
            data,
            position: 0,
            subrecord_end: None,
        }
    }

    pub(crate) fn remaining(&self) -> usize {
        self.data.len().saturating_sub(self.position)
    }

    pub(crate) fn remaining_subrecord_bytes(&self) -> usize {
        self.subrecord_end
            .unwrap_or(self.data.len())
            .saturating_sub(self.position)
    }

    pub(crate) fn bytes(&mut self, size: usize) -> Result<&'a [u8], AltiumParseError> {
        if self.position + size > self.data.len() {
            return Err(AltiumParseError::UnexpectedEof {
                offset: self.position,
                size,
                file_size: self.data.len(),
            });
        }
        let start = self.position;
        self.position += size;
        Ok(&self.data[start..start + size])
    }

    pub(crate) fn skip(&mut self, size: usize) -> Result<(), AltiumParseError> {
        self.bytes(size).map(|_| ())
    }

    pub(crate) fn u8(&mut self) -> Result<u8, AltiumParseError> {
        Ok(self.bytes(1)?[0])
    }

    pub(crate) fn u16(&mut self) -> Result<u16, AltiumParseError> {
        let bytes = self.bytes(2)?;
        Ok(u16::from_le_bytes([bytes[0], bytes[1]]))
    }

    pub(crate) fn u32(&mut self) -> Result<u32, AltiumParseError> {
        let bytes = self.bytes(4)?;
        Ok(u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
    }

    pub(crate) fn i32(&mut self) -> Result<i32, AltiumParseError> {
        let bytes = self.bytes(4)?;
        Ok(i32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
    }

    pub(crate) fn f64(&mut self) -> Result<f64, AltiumParseError> {
        let bytes = self.bytes(8)?;
        Ok(f64::from_le_bytes([
            bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7],
        ]))
    }

    pub(crate) fn peek_u32(&self) -> Result<u32, AltiumParseError> {
        if self.position + 4 > self.data.len() {
            return Err(AltiumParseError::UnexpectedEof {
                offset: self.position,
                size: 4,
                file_size: self.data.len(),
            });
        }
        let bytes = &self.data[self.position..self.position + 4];
        Ok(u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
    }

    pub(crate) fn read_subrecord_len(&mut self) -> Result<usize, AltiumParseError> {
        let length = self.u32()? as usize;
        let end = self
            .position
            .checked_add(length)
            .ok_or_else(|| AltiumParseError::Invalid("subrecord length overflow".to_string()))?;
        if end > self.data.len() {
            return Err(AltiumParseError::UnexpectedEof {
                offset: self.position,
                size: length,
                file_size: self.data.len(),
            });
        }
        self.subrecord_end = Some(end);
        Ok(length)
    }

    pub(crate) fn skip_subrecord(&mut self) -> Result<(), AltiumParseError> {
        if let Some(end) = self.subrecord_end.take() {
            if end > self.data.len() {
                return Err(AltiumParseError::UnexpectedEof {
                    offset: self.position,
                    size: end.saturating_sub(self.position),
                    file_size: self.data.len(),
                });
            }
            self.position = end;
        }
        Ok(())
    }

    pub(crate) fn read_wx_string(&mut self) -> Result<String, AltiumParseError> {
        let len = self.u8()? as usize;
        let bytes = self.bytes(len)?;
        Ok(latin1_string(bytes).trim_matches('\0').to_string())
    }

    pub(crate) fn utf16_fixed_string(&mut self, size: usize) -> Result<String, AltiumParseError> {
        let bytes = self.bytes(size)?;
        Ok(utf16le_string(bytes))
    }

    pub(crate) fn point(&mut self) -> Result<Point, AltiumParseError> {
        let x = self.i32()?;
        let y = self.i32()?;
        Ok(point_from_raw(x, y))
    }

    pub(crate) fn size(&mut self) -> Result<Size, AltiumParseError> {
        let x = self.i32()?;
        let y = self.i32()?;
        Ok(size_from_raw(x, y))
    }

    pub(crate) fn read_properties(&mut self) -> Result<BTreeMap<String, String>, AltiumParseError> {
        if self.remaining() == 0 {
            return Ok(BTreeMap::new());
        }
        let start = self.position;
        let data = if self.remaining() >= 4 {
            let length = self.peek_u32()? as usize;
            if length <= self.remaining().saturating_sub(4) {
                self.skip(4)?;
                self.bytes(length)?
            } else {
                self.bytes(self.remaining())?
            }
        } else {
            self.bytes(self.remaining())?
        };
        let properties = parse_properties_payload(data);
        if properties.is_empty() && self.position == start {
            self.position = self.data.len();
        }
        Ok(properties)
    }
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

    #[test]
    fn parses_pipe_properties() {
        let data = subrecord(b"|NAME=GND|KIND=0|M0=U1|");
        let mut reader = BinaryReader::new(&data);
        let props = reader.read_properties().unwrap();
        assert_eq!(props["NAME"], "GND");
        assert_eq!(props["M0"], "U1");
    }
}
