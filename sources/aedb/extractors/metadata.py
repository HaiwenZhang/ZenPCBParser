from __future__ import annotations

from aurora_translator.sources.aedb.models import AEDBMetadata
from aurora_translator.sources.aedb.version import (
    AEDB_JSON_SCHEMA_VERSION,
    AEDB_PARSER_VERSION,
)
from aurora_translator.version import PROJECT_VERSION


def extract_metadata(
    *,
    source: str,
    layout_name: str,
    pyedb_version: str,
    aedt_version: str,
) -> AEDBMetadata:
    return AEDBMetadata.model_validate(
        {
            "project_version": PROJECT_VERSION,
            "parser_version": AEDB_PARSER_VERSION,
            "output_schema_version": AEDB_JSON_SCHEMA_VERSION,
            "source": source,
            "layout_name": layout_name,
            "backend": "dotnet",
            "pyedb_version": pyedb_version,
            "aedt_version": aedt_version,
            "read_only": True,
        }
    )
