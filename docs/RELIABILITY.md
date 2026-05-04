# Reliability

## Purpose

This document defines reliability expectations for parsers, converters, and
exporters.

## Parser Reliability

- Prefer structured parsers over ad hoc string slicing when the format supports
  it.
- Preserve unknown but safely skippable source data as diagnostics or source
  metadata when possible.
- Treat unsupported blocks as non-fatal only when continuing would be unsafe or
  misleading.
- Guard untrusted counts and sizes before allocation or skipping.
- Record parser version changes when parsing behavior changes.

## Conversion Reliability

- `SemanticBoard` adapters must make unmapped source behavior explicit.
- Unit and coordinate conversions should be centralized and deterministic.
- Count mismatches should become diagnostics or validation notes, not silent
  drift.

## Export Reliability

- AuroraDB output should be deterministic and diffable.
- Exporters should not depend on source parser private state unless documented.
- AAF output is optional unless the command explicitly requests it.

## Verification

Prefer small, repeatable checks:

- Parser summary checks for case-driven parser fixes.
- `python -m compileall` for edited Python modules.
- `cargo test` or `cargo check` for edited Rust crates.
- Count and invariant comparisons across source, Semantic, and target layers.
