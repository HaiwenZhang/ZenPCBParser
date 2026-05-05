# BRD Large Board Performance

## Goal

Reduce wall time and peak memory for large `BRD -> SemanticBoard -> AuroraDB`
conversions without changing generated AuroraDB output semantics.

## Scope

- BRD source loading and validation in `sources/brd/`.
- BRD semantic adapter hot paths in `semantic/adapters/brd.py`.
- AuroraDB export hot paths only if profiling shows meaningful time or memory.

## Non-goals

- No JSON schema changes unless profiling proves a source-model contract is the
  blocker.
- No rewrite of the Rust BRD binary parser in this increment.
- No loss of currently exported geometry, component, pin, via, or stackup data.

## Current Status

- Completed.
- Large public BRD sample `<BRD_CASES>/large-ddr5-17.4.brd` converts
  successfully to AuroraDB and reads back with `diagnostics=0`.
- Baseline stage timing:
  - Rust BRD parser: about `5.5s`.
  - `BRDLayout` validation: about `73.7s`.
  - Source load total: about `96.0s`.
  - BRD semantic build: about `238.8s`.
  - AuroraDB export/write: about `24.8s`.
- Optimized stage timing:
  - Rust BRD parser with temp-file JSON output: about `2.2s`.
  - Trusted `BRDLayout` construction: about `55.9s`.
  - Source load total: about `73.6s`.
  - BRD semantic build: about `104.3s`.
  - AuroraDB export/write: about `58.7s` in the validation run.
- AuroraDB readback initially exposed a reader bug for quoted attribute values
  containing `(`. That was fixed in `sources/auroradb/block.py`.

## Steps

- Completed: profile source validation and BRD semantic build from stage logs.
- Completed: find repeated full-list scans and heavy Pydantic construction in BRD
  adapter code.
- Completed: add focused indexing and trusted internal construction while
  preserving the existing model contract.
- Completed: re-run targeted tests and the large BRD conversion.
- Completed: compare key counts before and after optimization.

## Validation

- `uv run pytest tests/test_auroradb_block.py`
- Large BRD conversion with `main.py convert --from brd --to auroradb`.
- AuroraDB readback with `main.py inspect source --format auroradb`.
- Key invariants: `diagnostics=0`, component count unchanged, net count
  unchanged, generated layer count unchanged.
- Optimized and baseline AuroraDB directories had no `diff -qr` differences.

## Decisions

- Start with Python adapter/indexing changes because the Rust parser is not the
  bottleneck in the baseline run.
- Keep Semantic parser version unchanged because generated Semantic/AuroraDB
  content is unchanged; bump BRD parser version for source-loader integration
  changes and AuroraDB parser version for block reader behavior.

## Open Risks

- JSON decode plus Python source model object construction still dominate source
  load. A native module handoff or streaming source adapter would be needed for
  another large memory reduction.
- Export/write timing varied between runs and may need separate profiling before
  optimizing the AuroraDB writer for BRD-heavy outputs.
