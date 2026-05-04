# Agent Instructions

This file is a short map, not a project manual. Keep durable knowledge in `docs/`
so future agents can find it without relying on chat history.

## Start Here

- `ARCHITECTURE.md` is the root navigation map.
- `docs/architecture.md` is the canonical project architecture.
- `docs/DESIGN.md` records engineering invariants and style decisions.
- `docs/PLANS.md` explains when to create or update execution plans.
- `docs/QUALITY_SCORE.md` defines review and verification expectations.
- `docs/RELIABILITY.md` defines parser/exporter reliability rules.
- `docs/SECURITY.md` defines local data, path, and dependency safety rules.

## Required Reads

Before changing parser, exporter, conversion, CLI behavior, or generated output,
read:

- `docs/versioning_policy.md`

Before adding or editing project documentation, read:

- `docs/documentation_style.md`

Before changing architecture boundaries, read:

- `docs/architecture.md`
- `docs/DESIGN.md`

Before starting broad or multi-step work, read:

- `docs/PLANS.md`
- `docs/exec-plans/tech-debt-tracker.md`

## Working Rules

- Prefer repository-local evidence over assumptions. If a rule matters, encode it
  in code, tests, generated schema, or a maintained doc.
- Keep plans and decisions versioned. Use `docs/exec-plans/active/` for live
  execution plans and move completed plans to `docs/exec-plans/completed/`.
- Update the smallest authoritative document that makes future work easier.
- Use project-relative paths in docs. Do not record private absolute paths,
  raw parser dumps, or temporary debug logs in long-lived docs.
- If documentation becomes too large for this file, add or update a focused doc
  and link it from the relevant index.
