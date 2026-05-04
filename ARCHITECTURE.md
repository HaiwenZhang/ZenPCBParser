# Architecture Map

This file is the root map for agents and maintainers. The canonical architecture
document remains `docs/architecture.md`.

## System Shape

Aurora Translator parses PCB source formats into source-specific JSON models,
normalizes them through `SemanticBoard`, and writes target formats such as
AuroraDB.

Primary flow:

```text
source format -> source model -> SemanticBoard -> target exporter
```

Current source formats:

- `sources/aedb/`
- `sources/auroradb/`
- `sources/odbpp/`
- `sources/brd/`

Current Rust parser cores:

- `crates/odbpp_parser/`
- `crates/brd_parser/`

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
- Rust BRD checks: `cargo test --manifest-path crates/brd_parser/Cargo.toml`
- Rust ODB++ checks: `cargo test --manifest-path crates/odbpp_parser/Cargo.toml`
- Project formatting: `uv run ruff format --check .`
