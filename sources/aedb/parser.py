from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from pyedb import __version__ as pyedb_version
from pyedb.misc.misc import current_version

from aurora_translator.shared.logging import log_kv, log_timing
from aurora_translator.sources.aedb.version import (
    AEDB_JSON_SCHEMA_VERSION,
    AEDB_PARSER_VERSION,
)
from aurora_translator.version import PROJECT_VERSION

from .errors import AEDBParserError
from .extractors import build_aedb_layout
from .models import AEDBLayout
from .session import close_aedb_session, open_aedb_session


logger = logging.getLogger("aurora_translator.aedb")

ComponentCenterSource = Literal["pin-bbox", "layout-instance"]
AEDBParseProfile = Literal["full", "auroradb-minimal"]


def parse_aedb(
    edb_path: str | Path,
    *,
    version: str | None = None,
    include_details: bool = True,
    component_center_source: ComponentCenterSource = "pin-bbox",
    parse_profile: AEDBParseProfile = "full",
) -> AEDBLayout:
    """Parse an AEDB layout with the PyEDB .NET backend."""

    source = Path(edb_path).expanduser()
    if not source.exists():
        raise AEDBParserError(f"AEDB path does not exist: {source}")
    if not source.is_dir() or source.suffix.lower() != ".aedb":
        raise AEDBParserError(f"Expected a .aedb directory, got: {source}")

    resolved_version = version or current_version()
    if not resolved_version:
        raise AEDBParserError(
            "No installed AEDT version was detected. Please pass --version explicitly."
        )

    pedb = None
    try:
        resolved_source = source.resolve()
        log_kv(
            logger,
            "AEDB parser settings",
            source=resolved_source,
            requested_version=version or "auto",
            resolved_version=resolved_version,
            backend="dotnet",
            readonly=True,
            include_details=include_details,
            component_center_source=component_center_source,
            parse_profile=parse_profile,
            project_version=PROJECT_VERSION,
            aedb_parser_version=AEDB_PARSER_VERSION,
            aedb_json_schema_version=AEDB_JSON_SCHEMA_VERSION,
            pyedb_version=pyedb_version,
        )
        with log_timing(
            logger, "open AEDB", source=resolved_source, version=resolved_version
        ):
            pedb = open_aedb_session(source, version=resolved_version)
        if pedb is None:
            raise AEDBParserError(f"Failed to open AEDB layout: {source}")

        layout_name = (
            getattr(getattr(pedb, "layout", None), "name", None) or source.stem
        )
        with log_timing(
            logger,
            "parse AEDB layout",
            heartbeat=False,
            layout_name=layout_name,
            include_details=include_details,
            component_center_source=component_center_source,
            parse_profile=parse_profile,
        ):
            payload = build_aedb_layout(
                pedb,
                source=str(resolved_source),
                layout_name=layout_name,
                pyedb_version=pyedb_version,
                aedt_version=resolved_version,
                include_details=include_details,
                component_center_source=component_center_source,
                parse_profile=parse_profile,
            )
        logger.info(
            "Parsed AEDB layout with layers:%s nets:%s components:%s paths:%s polygons:%s "
            "padstack_defs:%s padstack_instances:%s",
            payload.summary.layer_count,
            payload.summary.net_count,
            payload.summary.component_count,
            payload.summary.path_count,
            payload.summary.polygon_count,
            payload.summary.padstack_definition_count,
            payload.summary.padstack_instance_count,
        )
        return payload
    except AEDBParserError:
        raise
    except (
        Exception
    ) as exc:  # pragma: no cover - depends on installed AEDT/PyEDB runtime
        logger.exception("Unexpected parser failure")
        raise AEDBParserError(f"Failed to parse AEDB layout {source}: {exc}") from exc
    finally:
        if pedb is not None:
            try:
                with log_timing(logger, "close AEDB", source=source.resolve()):
                    close_aedb_session(pedb)
            except Exception:
                logger.warning("Failed to close AEDB cleanly", exc_info=True)
                pass
