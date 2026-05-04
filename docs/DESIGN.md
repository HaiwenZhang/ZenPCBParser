# Design

## Purpose

This document records engineering invariants for Aurora Translator. It is meant
to be read by agents before making structural changes.

## Core Invariants

- Preserve source fidelity first. Source parsers should keep enough native
  detail to diagnose conversion gaps later.
- Use `SemanticBoard` as the only cross-format semantic interchange model.
- Keep source parsing, semantic conversion, and target export separate.
- Prefer explicit schemas and typed models at format boundaries.
- Keep generated output deterministic unless a documented source format rule
  requires otherwise.
- Add abstractions only when they reduce real duplication or clarify an existing
  boundary.

## Boundaries

- `sources/*` owns source format parsing and source JSON models.
- `semantic/*` owns unified PCB semantics and source adapters.
- `targets/*` owns target format generation.
- `pipeline/*` owns orchestration only.
- `cli/*` owns command routing and user-facing options.
- `shared/*` owns logging, serialization helpers, and reusable utilities.
- `crates/*_parser` owns native parser cores for formats that benefit from Rust.

## Decision Rules

- Parser behavior changes require version and changelog review via
  `docs/versioning_policy.md`.
- JSON field additions, removals, renames, or meaning changes require schema
  version review.
- If a behavior is discovered from a case, record the durable summary in the
  changelog or an execution plan, not only in chat.
- Prefer tests, schema generation, and repeatable commands over prose-only
  guarantees.

## Known Tradeoffs

- BRD and ODB++ source JSON may expose format-specific structures that are not
  yet fully mapped into `SemanticBoard`.
- AuroraDB AAF remains available but is not the project-level architecture
  center; it is a target-side internal or explicit artifact.
