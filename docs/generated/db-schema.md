# Generated Schema Notes

## Purpose

This folder is for generated or generated-adjacent reference material. The file
name follows the harness layout, but Aurora Translator currently does not own a
relational application database schema.

## Current Generated Schemas

Machine-readable JSON schemas are maintained by source or semantic package:

- AEDB: `sources/aedb/docs/aedb_schema.json`
- AuroraDB: `sources/auroradb/docs/auroradb_schema.json`
- ODB++: `sources/odbpp/docs/odbpp_schema.json`
- Semantic: `semantic/docs/semantic_schema.json`
- BRD: generated from `sources/brd/models.py` through the unified schema command
- ALG: generated from `sources/alg/models.py` through the unified schema command
- Altium: generated from `sources/altium/models.py` through the unified schema command

## Rule

Generated files should document their source command or owning model. Do not
hand-edit generated output unless the generator itself is also updated.
