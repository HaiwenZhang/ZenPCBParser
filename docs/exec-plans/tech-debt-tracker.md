# Tech Debt Tracker

## Purpose

Track known debt that affects future parser, converter, exporter, or agent
workflow work.

## Open Items

| Area | Debt | Impact | Next Step |
| --- | --- | --- | --- |
| BRD | Geometry-rich BRD objects are preserved in source JSON but only layers and nets are mapped into `SemanticBoard`. | `BRD -> AuroraDB` is not yet a full geometry conversion path. | Create an execution plan before implementing BRD Semantic geometry mapping. |
| Docs | Generated schema references are spread across format folders. | Agents need a single generated-doc map. | Expand `docs/generated/db-schema.md` into a generated schema index when schema generation is next touched. |

## Maintenance

Update this file when a plan closes with known follow-up work or when repeated
debugging exposes a durable gap.
