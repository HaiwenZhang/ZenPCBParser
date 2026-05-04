# ODB++ Rust Exporter

## Goal

Add an ODB++ target exporter implemented in Rust under `crates/`, and expose it
through the existing `source -> SemanticBoard -> target` conversion flow.

## Scope

- Export from `SemanticBoard` JSON, not directly from individual source formats.
- Write a deterministic ODB++ directory package with matrix, step profile,
  layer feature files, layer attrlists, component records, EDA package data,
  and cadnet netlist records.
- Add focused Rust tests for generated ODB++ structure and parser round-trip.
- Add a Python target wrapper so `main.py convert --to odbpp` can call the Rust
  exporter.

## Non-goals

- Full-fidelity ODB++ manufacturing output for every optional block.
- Direct AEDB/BRD/ALG/AuroraDB to ODB++ exporters outside `SemanticBoard`.
- ODB++ archive packaging.

## Result

- Completed in project version `1.0.44`.
- Added `crates/odbpp_exporter/` and `targets/odbpp/`.
- The Rust writer is split by ODB++ semantics into `entity`, `features`,
  `attributes`, `components`, `package`, `eda_data`, `netlist`, `formatting`,
  and `model` modules.
- `convert --to odbpp` now routes through `SemanticBoard -> ODB++`.

## Steps

- [x] Inspect the existing ODB++ C++ reference in `examples/odbpp`.
- [x] Add `crates/odbpp_exporter`.
- [x] Wire Python pipeline and CLI target handling.
- [x] Update project docs, changelog, and version metadata.
- [x] Run focused Rust validation.

## Validation

- `cargo test --manifest-path crates/odbpp_exporter/Cargo.toml`

## Decisions

- ODB++ export starts from `SemanticBoard`, following the project invariant that
  cross-format conversion goes through the semantic layer.

## Follow-Up Risks

- Text/font export, soldermask/paste/auxiliary layer generation, richer drill
  tool metadata, ODB++ archive packaging, and full feature/component system
  attributes remain follow-up work.
