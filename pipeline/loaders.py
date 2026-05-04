from __future__ import annotations

import logging
from pathlib import Path

from aurora_translator.shared.logging import log_kv, log_timing

from .types import SourceFormat, SourceLoadOptions


logger = logging.getLogger("aurora_translator.pipeline")


def load_source_payload(
    source_format: SourceFormat,
    source_path: str | Path,
    *,
    options: SourceLoadOptions | None = None,
):
    resolved_source = Path(source_path).expanduser().resolve()
    load_options = options or SourceLoadOptions()

    log_kv(
        logger,
        "Source loader settings",
        source_format=source_format,
        source=resolved_source,
        include_details=load_options.include_details,
        aedt_version=load_options.aedt_version,
        component_center_source=load_options.component_center_source,
        aedb_parse_profile=load_options.aedb_parse_profile
        if source_format == "aedb"
        else None,
        step=load_options.step,
        rust_binary=load_options.rust_binary,
    )

    if source_format == "aedb":
        from aurora_translator.sources.aedb import parse_aedb

        with log_timing(
            logger, "load AEDB source payload", banner=True, source=resolved_source
        ):
            return parse_aedb(
                resolved_source,
                version=load_options.aedt_version,
                include_details=load_options.include_details,
                component_center_source=load_options.component_center_source,
                parse_profile=load_options.aedb_parse_profile,
            )

    if source_format == "auroradb":
        from aurora_translator.sources.auroradb import (
            build_auroradb_model,
            read_auroradb,
        )

        with log_timing(
            logger, "read AuroraDB source package", banner=True, source=resolved_source
        ):
            package = read_auroradb(resolved_source)
        with log_timing(
            logger, "build AuroraDB source model", banner=True, source=resolved_source
        ):
            return build_auroradb_model(
                package, include_raw_blocks=load_options.include_raw_blocks
            )

    if source_format == "odbpp":
        from aurora_translator.sources.odbpp import parse_odbpp

        with log_timing(
            logger, "load ODB++ source payload", banner=True, source=resolved_source
        ):
            return parse_odbpp(
                resolved_source,
                step=load_options.step,
                include_details=load_options.include_details,
                rust_binary=load_options.rust_binary,
            )

    raise ValueError(f"Unsupported source format: {source_format!r}")
