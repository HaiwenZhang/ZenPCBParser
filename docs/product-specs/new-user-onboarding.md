# New User Onboarding

## Purpose

Define the first successful path for someone using Aurora Translator.

## Primary Workflow

The user should be able to:

- Set up the environment with `scripts/setup_env.ps1` or `uv sync --locked`.
- Inspect a source file summary.
- Convert a supported source into AuroraDB.
- Optionally dump source JSON or Semantic JSON for debugging.
- Find schema and version information for every generated payload.

## Success Criteria

- The README points to the recommended commands.
- CLI errors identify the source format, stage, and likely remediation.
- Logs include project version, parser version, and output location.
- Schema files can be generated without running a full conversion.

## Current Gaps

- BRD support includes source parsing and an initial Semantic adapter, but full
  geometry mapping into `SemanticBoard` is still tracked as tech debt.
