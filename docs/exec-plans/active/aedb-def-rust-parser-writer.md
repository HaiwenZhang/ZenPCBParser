# AEDB DEF Rust Parser And Writer

## Goal

Build a Rust AEDB `.def` parser and writer that can operate without Ansys AEDT.
The first deliverable is a native crate that reads AEDB `.def` files, exposes a
structured JSON summary for reverse engineering, and writes deterministic `.def`
files for parser roundtrip validation.

The current increment extends the parser toward AuroraDB parity by extracting a
domain model from `.def` text records and length-prefixed binary strings, then
comparing that model against the provided standard AuroraDB directories.

## Scope

- Add `crates/aedb_parser/` as the native AEDB `.def` parser and writer core.
- Parse AEDB `.def` record framing, including length-prefixed text records and
  intervening binary records.
- Parse `$begin` / `$end` AEDB DSL text blocks into a source-fidelity tree.
- Extract domain objects for materials, stackup layers, board metal layers,
  padstacks, component definitions, component pins, component placements,
  part-name candidates, geometry string statistics, via-tail coordinate counts,
  and raw-point path Line/Larc segment counts.
- Preserve unknown text and binary records so encrypted or unsupported content
  is explicit rather than silently discarded.
- Add a writer path that emits `.def` from the parsed record stream.
- Add CLI commands for parse JSON output and roundtrip `.def` export.
- Add a CLI comparison command for `.def` extraction versus standard AuroraDB
  directories.
- Use `examples/edb_cases/*.def` as initial public fixtures.

## Non-Goals

- Full PyEDB parity in the first increment.
- Writing arbitrary AEDB designs from `SemanticBoard` directly in the first
  increment.
- Supporting `Encrypted=true` AEDB content before plaintext `.def` coverage is
  stable.
- Replacing the Python `sources/aedb/` PyEDB path until Rust output is validated
  against golden PyEDB JSON.

## Current Status

- Existing AEDB parser depends on PyEDB and AEDT through `sources/aedb/`.
- `examples/edb_cases/fpc.def`, `kb.def`, and `mb.def` are plaintext AEDB DEF
  samples with `Encrypted=false`.
- The samples contain a binary record envelope plus AEDB DSL text records.
- The provided `examples/edb_cases/*_auroradb` directories are used as standard
  AuroraDB references. The `mb` reference directory currently has a leading
  space in its directory name and is consumed as-is.

## Steps

- Create `crates/aedb_parser/` with Rust CLI, serde models, parser, writer, and
  unit tests.
- Implement low-level record scanning:
  - text record header: one tag byte, little-endian `u32` text length, UTF-8 or
    loss-tolerant text payload.
  - binary runs between text records, preserved as byte counts and hashes in
    JSON and as original bytes in roundtrip output.
- Implement AEDB DSL block parsing for `$begin '<name>'` / `$end '<name>'`
  nesting and assignment/function lines.
- Implement deterministic writer:
  - roundtrip mode preserves original record order and binary bytes.
  - text export mode normalizes parsed text records from the AST once semantic
    writing begins.
- Add tests for all public `.def` samples:
  - record counts are nonzero.
  - header reports `Encrypted=false`.
  - roundtrip output is byte-identical for unchanged input.
- Add opt-in Python integration behind `--aedb-backend def-binary` while keeping
  the PyEDB backend as the default.
- Add domain extraction and standard AuroraDB comparison:
  - `parse` emits `domain` in the separate `AEDBDefBinaryLayout` payload.
  - `compare-auroradb` checks board metal layer names, ViaList template names,
    electrical net names, component placement names, and placement-derived
    part-name candidates against the standard AuroraDB directory.
  - Binary via-tail and raw-point path records are decoded into summary counts
    for direct via coordinates, named/anonymous paths, Line/Larc segments, and
    path widths.
  - Geometry and via-instance count mismatches stay as warnings until component
    pad-derived vias, Location pad geometry, polygon/void payloads, and exact
    layer/net ownership are decoded.

## Validation

- `cargo test --manifest-path crates/aedb_parser/Cargo.toml`
- `cargo check --manifest-path crates/aedb_parser/Cargo.toml`
- `uv run python -m compileall sources/aedb cli pipeline`
- Parse `examples/edb_cases/*.def` and compare high-level counts.
- Roundtrip `examples/edb_cases/*.def` to a temporary output and compare bytes.
- Run `main.py inspect source --format aedb <case.def> --aedb-backend def-binary`.
- Run `main.py dump source-json --format aedb <case.def> --aedb-backend def-binary`.
- Run `crates/aedb_parser/target/debug/aedb_parser compare-auroradb
  examples/edb_cases/<case>.def --auroradb examples/edb_cases/<case>_auroradb`
  for `fpc`, `kb`, and `mb` reference cases. The `mb` AuroraDB directory name
  is currently `examples/edb_cases/ mb_auroradb`.

## Decisions

- Treat the first writer as a source-fidelity `.def` writer, not yet a full
  high-level AEDB authoring API.
- Keep `sources/aedb/parser.py` and default CLI behavior on PyEDB; Rust `.def`
  parsing is explicit opt-in only.
- Keep AST and record-stream layers separate so later semantic writer work can
  reuse the DSL writer without losing unknown binary records.
- Keep `.def` binary bytes local and never write raw dumps into long-lived docs.
- Treat `NONET` in standard AuroraDB as a synthetic exporter net, not a required
  `.def` binary string-table name.

## Open Risks

- AEDB `.def` version `12.1` may not cover all AEDT releases.
- Some source records may contain escaped nested `$begin` text that should not
  become top-level blocks.
- Full semantic export requires verified mappings for components, nets,
  padstacks, primitives, layers, and simulation metadata.
- Raw-point path segment counts do not yet equal AuroraDB `NetGeometry` counts
  across all samples because component pad-derived geometry, polygon/void
  payloads, and exact layer/net ownership are not fully decoded.
