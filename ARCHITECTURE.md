# Architecture Map

This file is the root map for agents and maintainers. The canonical architecture
document remains `docs/architecture.md`.

## System Shape

Aurora Translator parses PCB source formats into source-specific JSON models,
normalizes them through `SemanticBoard`, and writes target formats such as
AuroraDB and ODB++.

Primary flow:

```text
source format -> source model -> SemanticBoard -> target exporter
```

Current source formats:

- `sources/aedb/`
- `sources/auroradb/`
- `sources/odbpp/`
- `sources/brd/`
- `sources/alg/`
- `sources/altium/`

Current Rust parser cores:

- `crates/aedb_parser/`
- `crates/odbpp_parser/`
- `crates/brd_parser/`
- `crates/alg_parser/`
- `crates/altium_parser/`

Current Rust target exporters:

- `crates/odbpp_exporter/`

Current Python target wrappers:

- `targets/auroradb/`
- `targets/odbpp/`

## Authoritative References

- Full project architecture: `docs/architecture.md`
- Engineering invariants: `docs/DESIGN.md`
- Reliability contracts: `docs/RELIABILITY.md`
- Security rules: `docs/SECURITY.md`
- Versioning and changelog policy: `docs/versioning_policy.md`
- Documentation style: `docs/documentation_style.md`

## Agent Navigation

Use `AGENTS.md` as the entrypoint. Use this file to find the right deeper doc.
Do not duplicate detailed parser, schema, or exporter behavior here; put that in
the owning package or project doc and link to it.

## Validation Entry Points

- Python compile: `uv run python -m compileall <paths>`
- Rust AEDB DEF checks: `cargo test --manifest-path crates/aedb_parser/Cargo.toml`
- Rust AEDB DEF/AuroraDB alignment: `crates/aedb_parser/target/debug/aedb_parser compare-auroradb <board.def> --auroradb <auroradb-dir>`
- Rust BRD checks: `cargo test --manifest-path crates/brd_parser/Cargo.toml`
- Rust ODB++ checks: `cargo test --manifest-path crates/odbpp_parser/Cargo.toml`
- Rust ODB++ exporter checks: `cargo test --manifest-path crates/odbpp_exporter/Cargo.toml`
- Rust Altium checks: `cargo test --manifest-path crates/altium_parser/Cargo.toml`
- Project formatting: `uv run ruff format --check .`
