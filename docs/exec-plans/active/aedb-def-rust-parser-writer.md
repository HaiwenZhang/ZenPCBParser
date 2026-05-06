# AEDB DEF Rust Parser And Writer

## Goal

Build a Rust AEDB `.def` parser and writer that can operate without Ansys AEDT.
The first deliverable is a native crate that reads AEDB `.def` files, exposes a
structured JSON summary for reverse engineering, and writes deterministic `.def`
files for parser roundtrip validation.

The current increment extends the parser toward AuroraDB parity by extracting a
domain model from `.def` text records and length-prefixed binary strings, then
comparing that model against the provided standard AuroraDB directories.
The current reverse-engineering focus is the `.def` binaries under
`examples/edb_cases/`. Earlier ANF sidecars were used as human-readable
references; the active fixtures may now contain only `.def` files, so the
current work treats ANF as optional enrichment rather than required input.

## Scope

- Add `crates/aedb_parser/` as the native AEDB `.def` parser and writer core.
- Parse AEDB `.def` record framing, including length-prefixed text records and
  intervening binary records.
- Parse `$begin` / `$end` AEDB DSL text blocks into a source-fidelity tree.
- Extract domain objects for materials, stackup layers, board metal layers,
  padstacks, component definitions, component pins, component placements,
  part-name candidates, binary layout net names, geometry string statistics,
  padstack instance records, via-tail coordinate counts, raw-point path records
  with decoded owner fields, raw-point polygon/void records with decoded layer
  and parent fields, and raw-point path Line/Larc segment counts.
- Preserve unknown text and binary records so encrypted or unsupported content
  is explicit rather than silently discarded.
- Add a writer path that emits `.def` from the parsed record stream.
- Add CLI commands for parse JSON output and roundtrip `.def` export.
- Add a CLI comparison command for `.def` extraction versus standard AuroraDB
  directories.
- Use `examples/edb_cases/*.def` as initial public fixtures.

## Non-Goals

- Full PyEDB parity in the first increment.
- Writing arbitrary AEDB designs from `SemanticBoard` directly in the first
  increment.
- Supporting `Encrypted=true` AEDB content before plaintext `.def` coverage is
  stable.
- Replacing the Python `sources/aedb/` PyEDB path until Rust output is validated
  against golden PyEDB JSON.

## Current Status

- Existing AEDB parser depends on PyEDB and AEDT through `sources/aedb/`.
- `examples/edb_cases/DemoCase_LPDDR4.def` is a plaintext AEDB DEF sample with
  `Encrypted=false`. Historical ANF exports were used for cross-checking object
  counts and geometry values, but the current conversion path must work when
  those sidecars are absent.
- The `.def` sample contains AEDB DSL text records interleaved with binary
  records. It is not a direct binary packing of ANF text.
- The Demo case `.def` text records expose materials, stackup, padstacks,
  component definitions, and component placement text. The large layout binary
  record contains path/via geometry payloads, native polygon/void records, and
  native `Outline` polygon records.
- The Rust parser currently decodes 1965 binary path records from the Demo case;
  these match ANF `Graphics(... Path(...))` records by order, width, and meter
  coordinates. The parser also decodes the path preamble owner fields: layer is
  stored as `0x00010000 + stackup_layer_id`, and net is stored as
  `page_byte * 256 + low_byte` into the binary layout net table. All 1965 Demo
  case path owner pairs match ANF net/layer context.
- The first decoded path record is `GND` on `BOTTOM`, has width `0.0002032`, and
  has points `(0.00748411, 0.008244586)` to `(0.007891018, 0.008244586)`.
- The large Demo case binary record starts with a layout net table; the parser
  currently recovers `335` layout net entries.
- The component/pad binary record decoder currently recovers all 2843 Demo case
  EDB `PadstackInstance` records and matches ANF `via(...)` by geometry ID and
  coordinate. The records split into 1714 component pin pads, 1117 `via_*`
  records, and 12 unnamed/mechanical records. The `pyedb-core` API source
  confirms this is the right object family: `PadstackInstance` owns
  position/rotation, layer range, padstack definition, net, component, and
  layout-pin state. The decoder also recovers a `drill_diameter` double from the
  padstack-instance tail for real vias; component pin pads leave it empty.
- Same-version cross-checks now cover `SW_ARM_1029` and `Zynq_Phoenix_Pro`.
  Their decoded path records match ANF by geometry ID, layer, width, point list,
  and arc-height values (`2833` and `2208` paths). Their decoded padstack
  instance records match ANF `via(...)` by geometry ID, coordinate, and rotation
  (`3531` and `2709` records).
- The Python conversion path now accepts `--aedb-backend def-binary` for
  AuroraDB export. `AEDBDefBinaryLayout -> SemanticBoard` maps stackup, nets,
  components, pins, padstack instances, path records, and board outline into the
  shared semantic model, so `convert --from aedb --aedb-backend def-binary --to
  auroradb` writes `layout.db`, `parts.db`, `stackup.dat`, `stackup.json`, and
  `layers/*.lyr`.
- When a sibling ANF sidecar is available, the semantic adapter uses ANF
  `via(...)` / `Padstacks` / `PolygonWithVoids` as an enrichment source for
  padstack names, layer spans, basic pad shapes, polygons, and holes. Without
  ANF, the adapter now emits native `binary_polygon_records` as
  `Polygon`/`PolygonHole`/`Holes`, derives drill circles from
  `drill_diameter`, maps `raw_definition_index` through native
  `padstack_instance_definitions`, parses text padstack circle/rectangle/square/
  oval shapes, and infers a board-outline fallback from large native polygon
  bboxes.
- Native padstack-instance definition decoding now emits
  `domain.padstack_instance_definitions`. The parser recovers the object id from
  the 7-byte prefix before an unnamed text record and reads the following
  `$begin ''` block's `def`, `fl`, and `tl` fields to map raw instance
  definition ids back to global padstack ids and concrete layout layers.
  No-ANF sample counts are `DemoCase_LPDDR4=80`, `SW_ARM_1029=112`, and
  `Zynq_Phoenix_Pro=52`.
- Native polygon decoding now emits `domain.binary_polygon_records`. `.def`
  polygon records store the ANF `Polygon(id, ...)` point stream as little-endian
  `f64` pairs. Vertex items are `(x, y)` and arc-height items are
  `(arc_height, f64::MAX)`; the preceding count stores twice the ANF item count.
  The parser decodes geometry id, layer id/name, outer/void status, and parent
  polygon id, including odd-offset records and parent ids greater than `255`.
  Polygon net ownership is recovered from the same binary primitive stream:
  path records are monotonic by layout net, and native polygon/void records are
  inserted inside the active path net group. The parser writes that owner into
  `binary_polygon_records[].net_index/net_name` and propagates it to voids.
- The native polygon scanner also recognizes `Outline` layer records and the
  semantic adapter uses them for board outline before falling back to large
  plane bboxes. `SLayer(...)` text is reassembled across lines, and material
  text blocks now carry conductivity, permittivity, and loss tangent through
  source and semantic material records.
- Current no-ANF native polygon/void counts are
  `DemoCase_LPDDR4=840`, `SW_ARM_1029=403`, and
  `Zynq_Phoenix_Pro=744`. The earlier `537 / 345 / 384` counts did not include
  the expanded native polygon scan and outline records.
- AEDB DEF binary semantic via/template geometry now records exact layer-span
  taxonomy (`through`, `blind`, `buried`, `single_layer`, or `unknown`) from
  the native padstack-instance definition first/last layer mapping. Via
  instances also carry `via_usage`, and the AuroraDB exporter uses that to emit
  direct `NetVias` only for `routing_via` while keeping component-pin padstack
  instances on the pin/pad export path.
- Against the standard AuroraDB for `DemoCase_LPDDR4.def`, the direct DEF-binary
  output now matches `units=mils`, the rounded board outline, stackup layer
  order/thickness/material properties, `components=293`, `parts=58`,
  `nets=335`, `via_templates=7`, `shapes=61`, and `net_geometries=9785`.
  Layer geometry type counts now match the Standard reference exactly:
  `Line=7998`, `Polygon=33`, and `PolygonHole=39`.
- Explicit full-circle void raw geometry now stays as AuroraDB `Pnt` + `Parc`
  arc holes instead of falling back to bbox rectangles when the contour has
  fewer than three point vertices.
- Text padstack `hle(...)`, `ant(...)`, and `thm(...)` fields are now preserved
  in the Rust source model and used by the semantic adapter. `C200-109T` now
  exports the Standard `RectCutCorner 0 0 150 200 75 N Y Y Y Y` barrel, and
  `ViaList` IDs/order now match the Standard sequence:
  `1 VIA8D16`, `2 VIA10D18`, `6 C060-040T`, `7 S060-040T`, `8 C200-109T`,
  `9 HOLE64N`, and `10 HOLE35N`.
- Source-backed clearance/antipad hole synthesis now covers the decoded
  through-hole and unnamed padstacks that produce `84.04`, `80.04`, `70.04`,
  and `51.04 mil` holes. Current DemoCase nested hole count is `1733` versus
  Standard `1742`; the remaining gap is mainly AEDT's routing-via clearance
  subdivision between `24.04 mil` and `26.04 mil`, plus one native complex hole.
  Keep future work focused on the source rule that decides that split rather
  than broad center-in-polygon synthesis.
- The older via tail decoder still reports the 1117 direct via-tail records as a
  low-level geometry hint, but the complete ANF `via(...)` population now comes
  from `domain.binary_padstack_instance_records`.
- Historical `fpc.def`, `kb.def`, and `mb.def` fixtures are still supported by
  tests when present, but the current public workspace may only contain the
  Demo case.

## Steps

- Create `crates/aedb_parser/` with Rust CLI, serde models, parser, writer, and
  unit tests.
- Implement low-level record scanning:
  - text record header: one tag byte, little-endian `u32` text length, UTF-8 or
    loss-tolerant text payload.
  - binary runs between text records, preserved as byte counts and hashes in
    JSON and as original bytes in roundtrip output.
- Implement AEDB DSL block parsing for `$begin '<name>'` / `$end '<name>'`
  nesting and assignment/function lines.
- Implement deterministic writer:
  - roundtrip mode preserves original record order and binary bytes.
  - text export mode normalizes parsed text records from the AST once semantic
    writing begins.
- Add tests for all public `.def` samples:
  - record counts are nonzero.
  - header reports `Encrypted=false`.
  - roundtrip output is byte-identical for unchanged input.
- Add opt-in Python integration behind `--aedb-backend def-binary` while keeping
  the PyEDB backend as the default.
- Add domain extraction and standard AuroraDB comparison:
  - `parse` emits `domain` in the separate `AEDBDefBinaryLayout` payload.
  - Binary layout net names are emitted as `domain.layout_nets`.
  - `compare-auroradb` checks board metal layer names, ViaList template names,
    electrical net names, component placement names, and placement-derived
    part-name candidates against the standard AuroraDB directory.
  - Binary via-tail and raw-point path records are decoded into summary counts
    for direct via coordinates, named/anonymous paths, Line/Larc segments, and
    path widths.
  - Binary padstack instance records are emitted as
    `domain.binary_padstack_instance_records` with global offset, geometry ID,
    instance name, name class, net owner, coordinates, rotation, raw owner/
    definition references, and optional secondary pin/name fields.
  - Binary path records are emitted as `domain.binary_path_records` with global
    offset, decoded geometry ID where available, net/layer owner fields, width,
    point/arc-height items, and Line/Larc segment counts.
  - Binary polygon records are emitted as `domain.binary_polygon_records` with
    global offsets, geometry ID, parent geometry ID, layer owner, outer/void
    flag, point/arc-height items, and polygon point/arc counts.
  - Geometry count mismatches stay as warnings until remaining Location pad
    geometry and component-definition variant names are decoded.

## Validation

- `cargo test --manifest-path crates/aedb_parser/Cargo.toml`
- `cargo build --manifest-path crates/aedb_parser/Cargo.toml`
- `uv run python -m compileall sources/aedb cli pipeline`
- Parse `examples/edb_cases/*.def` and compare high-level counts.
- Roundtrip `examples/edb_cases/*.def` to a temporary output and compare bytes.
- Run `main.py inspect source --format aedb <case.def> --aedb-backend def-binary`.
- Run `main.py dump source-json --format aedb <case.def> --aedb-backend def-binary`.
- Run `crates/aedb_parser/target/debug/aedb_parser parse
  examples/edb_cases/DemoCase_LPDDR4.def --compact` and confirm
  `domain.layout_nets` has `335` entries, `domain.binary_path_records` has
  `1965` entries, `domain.binary_padstack_instance_records` has `2843` entries,
  `domain.binary_polygon_records` has `840` entries, and the first/last path,
  padstack, and polygon records match the corresponding ANF net, layer, width,
  coordinates, rotation, or polygon point stream.
- Run the same parse and ANF cross-check for `SW_ARM_1029` and
  `Zynq_Phoenix_Pro`; expected path counts are `2833` / `2208`, and expected
  padstack instance counts are `3531` / `2709`, with zero missing, extra, or
  mismatched geometry IDs.
- Run `main.py convert --from aedb --aedb-backend def-binary --to auroradb
  examples/edb_cases/DemoCase_LPDDR4.def -o
  examples/edb_cases/_auroradb_def_binary_standard_compare/DemoCase_LPDDR4` and
  inspect the output. Expected Standard-aligned readback counts are
  `layers=8`, `nets=335`, `components=293`, `parts=58`, `vias=7`,
  `net_geometries=9785`, and `units=mils`; layer geometry type counts should be
  `Line=7998`, `Polygon=33`, and `PolygonHole=39`.
- Run `main.py convert --from aedb --aedb-backend def-binary --to auroradb
  examples/edb_cases/<case>.def -o examples/edb_cases/_auroradb_def_binary_pipeline/<case>`
  for `DemoCase_LPDDR4`, `SW_ARM_1029`, and `Zynq_Phoenix_Pro`. Expected
  readback counts after ANF sidecar enrichment:
  - Demo: `parts=98`, `components=293`, `net_geometries=9626`,
    `PolygonHole=39`.
  - SW: `parts=129`, `components=492`, `net_geometries=11902`,
    `PolygonHole=25`.
  - Zynq: `parts=99`, `components=282`, `net_geometries=15509`,
    `PolygonHole=49`.
- Run `crates/aedb_parser/target/debug/aedb_parser compare-auroradb
  examples/edb_cases/<case>.def --auroradb
  examples/edb_cases/_auroradb_def_binary_pipeline/<case> --compact`. The three
  pipeline outputs should have no `fail` checks; remaining `warn` checks are
  reverse-engineering hints for component-definition variant names, low-level
  via-tail counts, geometry-name hints, and the known `SW_ARM_1029` outline arc
  path count mismatch.
- Run `crates/aedb_parser/target/debug/aedb_parser compare-auroradb
  examples/edb_cases/<case>.def --auroradb examples/edb_cases/<case>_auroradb`
  for `fpc`, `kb`, and `mb` reference cases. The `mb` AuroraDB directory name
  is currently `examples/edb_cases/ mb_auroradb`. Skip missing reference cases
  when they are not present in the current workspace.

## Decisions

- Treat the first writer as a source-fidelity `.def` writer, not yet a full
  high-level AEDB authoring API.
- Keep `sources/aedb/parser.py` and default CLI behavior on PyEDB; Rust `.def`
  parsing is explicit opt-in only.
- Keep AST and record-stream layers separate so later semantic writer work can
  reuse the DSL writer without losing unknown binary records.
- Keep `.def` binary bytes local and never write raw dumps into long-lived docs.
- Treat `NONET` in standard AuroraDB as a synthetic exporter net, not a required
  `.def` binary string-table name.
- Treat ANF as a reference export for object names, order, and geometry
  cross-checks, not as the authoritative on-disk grammar for `.def`.
- Store decoded `.def` coordinates in source SI units when the binary payload is
  already little-endian `f64` meters, matching the Demo ANF coordinate values.
- Decode path owner fields from the `.def` binary preamble itself. ANF is only
  the cross-check; production parsing should use the binary net table and
  stackup layer IDs.

## Open Risks

- AEDB `.def` version `12.1` may not cover all AEDT releases.
- Some source records may contain escaped nested `$begin` text that should not
  become top-level blocks.
- Full semantic export requires verified mappings for components, nets,
  padstacks, primitives, layers, and simulation metadata.
- Raw-point path segment counts do not yet equal AuroraDB `NetGeometry` counts
  across all samples because some source records still have exporter-specific
  normalization, but native polygon ownership and AEDB via taxonomy are decoded
  for the current no-ANF samples.
- Demo case padstack instance records now cover all 2843 ANF `via(...)` entries
  by geometry ID and coordinate. The parser now also decodes the separate
  native padstack-instance definition records that map raw definition ids back
  to padstack names and top/bottom layer ranges.
- The current AuroraDB path no longer requires ANF sidecars for polygon holes or
  stackup/parts output. Without ANF, component pad templates use native
  padstack-instance definition mappings plus text padstack shape fields, and
  native polygon net owners come from the binary primitive stream ordering.
- Native polygon point/arc streams, void parent IDs, and net owners are decoded
  for the current same-version cases. The remaining risk is whether AEDB `.def`
  versions outside `12.1` keep the same primitive stream ordering.
