# Altium Rust Parser

## Goal

Add an Altium Designer source path that parses `.PcbDoc` compound files with a
Rust core, validates the result through a Python source model, and converts the
core board objects into `SemanticBoard`.

## Result Summary

Completed in project version `1.0.44`. Added `crates/altium_parser/`,
`sources/altium/`, `semantic.adapters.altium`, CLI/pipeline/schema routing, and
semantic schema support for `source_format=altium`. Validated Rust parser tests,
Python semantic adapter tests, `examples/altium_cases/VR.PcbDoc`,
`examples/altium_cases/XC7Z020CLG400-AD9).PcbDoc`, and an Altium -> AuroraDB
conversion smoke test.

## Scope

- Add `crates/altium_parser/` with CLI and optional PyO3 native module, following
  the `crates/brd_parser/` integration shape.
- Parse the Microsoft Compound File container used by Altium `.PcbDoc` files.
- Parse first-pass Altium PCB streams: `FileHeader`, `Board6`, `Nets6`,
  `Components6`, `Pads6`, `Vias6`, `Tracks6`, `Arcs6`, `Fills6`, `Regions6`,
  `ShapeBasedRegions6`, `Polygons6`, and `WideStrings6` when present.
- Add `sources/altium/` Pydantic models, schema helper, parser wrapper, and
  source version constants.
- Add `semantic.adapters.altium` for layers, nets, components, pads, vias,
  traces, arcs, fills, regions, and board outline where source geometry is
  available.
- Wire `altium` into `convert`, `dump`, `inspect`, `schema`, and semantic CLI
  flows.

## Non-goals

- No direct `Altium -> AuroraDB` bypass; conversion stays
  `Altium -> SemanticBoard -> target`.
- No Altium library or integrated library footprint expansion in this pass.
- No 3D model extraction, rule transformation, dimensions, embedded fonts, or
  exhaustive mechanical-layer semantics in this pass.
- No schema fixture generated from private board data.

## Current Status

- Existing architecture supports Rust source parsers for ODB++, BRD, and ALG.
- `examples/altium/` contains KiCad-derived C++ reference code and a Kaitai
  format sketch for the binary record streams.
- `examples/altium_cases/` contains two committed `.PcbDoc` sample fixtures:
  `VR.PcbDoc` and `XC7Z020CLG400-AD9).PcbDoc`.

## Steps

- Create the Rust parser crate and unit tests for CFB traversal, property
  record parsing, and binary primitive parsing.
- Add Python source package and CLI/native fallback behavior.
- Add semantic mapping and lightweight unit tests with synthetic Altium payloads.
- Update source and semantic schema versions, project changelog, architecture
  maps, and package metadata.
- Run `cargo test`, Python compile checks, and targeted pytest.

## Validation

- `cargo test --manifest-path crates/altium_parser/Cargo.toml`
- `uv run python -m compileall sources/altium semantic cli pipeline`
- Targeted pytest for semantic adapter and architecture routing.
- Case validation with `examples/altium_cases/VR.PcbDoc` and
  `examples/altium_cases/XC7Z020CLG400-AD9).PcbDoc`.

## Decisions

- Source JSON preserves Altium-specific fields and raw values instead of
  normalizing directly into target-specific structures.
- Semantic coordinates are emitted in `mil`; binary coordinate values are
  converted as Altium internal coordinate units divided by `10000`, with Y
  mirrored to match the Altium importer reference's board-coordinate convention.
- Unsupported or malformed streams produce diagnostics when the parser can
  continue safely.

## Open Risks

- `XC7Z020CLG400-AD9).PcbDoc` still reports a non-fatal
  `ShapeBasedRegions6` tail-read diagnostic; the main board object streams
  continue parsing and semantic conversion succeeds.
- Altium property encoding details can vary by version and locale; the first
  pass keeps raw stream diagnostics for unsupported encodings.
