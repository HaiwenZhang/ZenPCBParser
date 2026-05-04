use super::BrdParseError;

pub(crate) struct Reader<'a> {
    pub(crate) bytes: &'a [u8],
    pos: usize,
}

impl<'a> Reader<'a> {
    pub(crate) fn new(bytes: &'a [u8]) -> Self {
        Self { bytes, pos: 0 }
    }

    pub(crate) fn position(&self) -> usize {
        self.pos
    }

    pub(crate) fn eof(&self) -> bool {
        self.pos >= self.bytes.len()
    }

    pub(crate) fn seek(&mut self, pos: usize) -> Result<(), BrdParseError> {
        if pos > self.bytes.len() {
            return Err(BrdParseError::InvalidSeek {
                offset: pos,
                file_size: self.bytes.len(),
            });
        }
        self.pos = pos;
        Ok(())
    }

    pub(crate) fn peek_u8(&self) -> Result<Option<u8>, BrdParseError> {
        Ok(self.bytes.get(self.pos).copied())
    }

    pub(crate) fn skip(&mut self, n: usize) -> Result<(), BrdParseError> {
        self.take(n).map(|_| ())
    }

    pub(crate) fn skip_u32(&mut self, n: usize) -> Result<(), BrdParseError> {
        self.skip(n * 4)
    }

    pub(crate) fn take(&mut self, n: usize) -> Result<&'a [u8], BrdParseError> {
        if n > self.bytes.len() || self.pos > self.bytes.len() - n {
            return Err(BrdParseError::UnexpectedEof {
                offset: self.pos,
                size: n,
                file_size: self.bytes.len(),
            });
        }
        let start = self.pos;
        self.pos += n;
        Ok(&self.bytes[start..start + n])
    }

    pub(crate) fn u8(&mut self) -> Result<u8, BrdParseError> {
        Ok(self.take(1)?[0])
    }

    pub(crate) fn u16(&mut self) -> Result<u16, BrdParseError> {
        let bytes = self.take(2)?;
        Ok(u16::from_le_bytes([bytes[0], bytes[1]]))
    }

    pub(crate) fn u32(&mut self) -> Result<u32, BrdParseError> {
        let bytes = self.take(4)?;
        Ok(u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
    }

    pub(crate) fn i32(&mut self) -> Result<i32, BrdParseError> {
        let bytes = self.take(4)?;
        Ok(i32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
    }

    pub(crate) fn allegro_f64(&mut self) -> Result<f64, BrdParseError> {
        let high = self.u32()? as u64;
        let low = self.u32()? as u64;
        Ok(f64::from_bits((high << 32) | low))
    }

    pub(crate) fn u32_array4(&mut self) -> Result<[u32; 4], BrdParseError> {
        Ok([self.u32()?, self.u32()?, self.u32()?, self.u32()?])
    }

    pub(crate) fn i32_array4(&mut self) -> Result<[i32; 4], BrdParseError> {
        Ok([self.i32()?, self.i32()?, self.i32()?, self.i32()?])
    }

    pub(crate) fn c_string(&mut self, align_u32: bool) -> Result<String, BrdParseError> {
        let start = self.pos;
        let Some(relative_end) = self.bytes[start..].iter().position(|value| *value == 0) else {
            return Err(BrdParseError::UnterminatedString { offset: start });
        };
        let end = start + relative_end;
        let value = String::from_utf8_lossy(&self.bytes[start..end]).to_string();
        self.pos = end + 1;
        if align_u32 {
            self.align_u32()?;
        }
        Ok(value)
    }

    pub(crate) fn fixed_string(
        &mut self,
        len: usize,
        align_u32: bool,
    ) -> Result<String, BrdParseError> {
        let bytes = self.take(len)?;
        let end = bytes
            .iter()
            .position(|value| *value == 0)
            .unwrap_or(bytes.len());
        let value = String::from_utf8_lossy(&bytes[..end]).to_string();
        if align_u32 {
            self.align_u32()?;
        }
        Ok(value)
    }

    pub(crate) fn align_u32(&mut self) -> Result<(), BrdParseError> {
        let remainder = self.pos % 4;
        if remainder != 0 {
            self.skip(4 - remainder)?;
        }
        Ok(())
    }
}
