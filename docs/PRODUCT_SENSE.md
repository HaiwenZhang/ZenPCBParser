# Product Sense

## Product Goal

Aurora Translator should make PCB data translation predictable, inspectable, and
repeatable across supported source and target formats.

## Primary Users

- Engineers translating PCB design data between AEDB, ODB++, BRD, Semantic JSON,
  and AuroraDB.
- Maintainers validating parser or exporter behavior against sample boards.
- Automation that runs conversions and inspects summaries in CI or batch jobs.

## Product Principles

- Trust comes from explainable output. Summaries, diagnostics, versions, and
  schema IDs must be easy to inspect.
- Intermediate JSON is a debugging and archival capability, not the required
  main path.
- Case fixes should improve general format behavior when possible, but must
  clearly state the verified case scope.
- CLI options should make expensive or lossy behavior explicit.
- Diagnostics should describe what was preserved, skipped, or not yet mapped.

## What Good Looks Like

- A conversion can be rerun from a command recorded in logs or docs.
- Source, Semantic, and target counts can be compared.
- Parser limitations are visible as diagnostics, not silent omissions.
- Generated files are deterministic enough for meaningful diffs.
