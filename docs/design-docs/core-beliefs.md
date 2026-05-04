# Core Beliefs

## Purpose

These beliefs adapt agent-first repository practices to Aurora Translator.

## Beliefs

- The repository is the record system. If future agents need to know something,
  encode it in code, tests, schemas, plans, or docs.
- `AGENTS.md` should stay short. It points to authoritative documents rather
  than trying to contain them.
- Prefer maps over manuals. Start with indexes and link to deeper docs only when
  needed.
- Make behavior inspectable. Parser summaries, diagnostics, schema versions, and
  counts are part of the product.
- Enforce invariants mechanically where practical. Tests, schema generation, and
  lint checks age better than prose.
- Keep plans as first-class artifacts for complex work.
- Remove or update stale guidance. Outdated docs are worse than missing docs
  because agents can follow them confidently.

## Source Inspiration

This structure is inspired by OpenAI's harness engineering article about using a
repository as an agent-readable record system and keeping `AGENTS.md` as a
navigation map.
