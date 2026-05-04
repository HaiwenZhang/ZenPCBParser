from __future__ import annotations

import logging
from typing import Any, Literal

from aurora_translator.sources.aedb.models import AEDBLayout
from aurora_translator.shared.logging import log_field_block, log_timing

from .components import extract_components
from .context import ExtractionContext
from .layers import extract_layers
from .materials import extract_materials
from .metadata import extract_metadata
from .nets import extract_nets_from_sections
from .padstacks import extract_padstacks
from .primitives import extract_primitives
from .summary import build_layout_summary_from_sections, extract_layout_summary


logger = logging.getLogger("aurora_translator.aedb.extractors.layout")

ComponentCenterSource = Literal["pin-bbox", "layout-instance"]
AEDBParseProfile = Literal["full", "auroradb-minimal"]


def build_aedb_layout(
    pedb: Any,
    *,
    source: str,
    layout_name: str,
    pyedb_version: str,
    aedt_version: str,
    include_details: bool = True,
    component_center_source: ComponentCenterSource = "pin-bbox",
    parse_profile: AEDBParseProfile = "full",
) -> AEDBLayout:
    context = ExtractionContext(pedb)
    payload: dict[str, Any] = {
        "metadata": extract_metadata(
            source=source,
            layout_name=layout_name,
            pyedb_version=pyedb_version,
            aedt_version=aedt_version,
        ),
    }

    if include_details:
        component_layout_records_by_id = None
        if component_center_source == "layout-instance":
            with log_timing(
                logger, "build component layout records", count=len(context.components)
            ):
                component_layout_records_by_id = context.component_layout_records_by_id
        materials = extract_materials(context)
        layers = extract_layers(context)
        with log_timing(
            logger,
            "build padstack instance records",
            count=len(context.padstack_instances),
        ):
            padstack_instance_records = context.padstack_instance_records
        log_field_block(
            logger,
            "Parsed padstack instance records",
            fields={"instances": len(padstack_instance_records)},
        )
        components = extract_components(
            context,
            use_layout_object_index=True,
            component_layout_records_by_id=component_layout_records_by_id,
            include_layout_geometry=True,
            component_center_source=component_center_source,
        )
        padstacks = extract_padstacks(context)
        primitives = extract_primitives(context, parse_profile=parse_profile)
        nets = extract_nets_from_sections(context, primitives)

        payload["summary"] = build_layout_summary_from_sections(
            context=context,
            materials=materials,
            layers=layers,
            nets=nets,
            components=components,
            padstacks=padstacks,
            primitives=primitives,
        )
        payload["materials"] = materials
        payload["layers"] = layers
        payload["nets"] = nets
        payload["components"] = components
        payload["padstacks"] = padstacks
        payload["primitives"] = primitives
    else:
        payload["summary"] = extract_layout_summary(context)

    with log_timing(logger, "validate AEDBLayout model"):
        model = AEDBLayout.model_validate(payload)
    logger.info(
        "AEDBLayout model validated with detail_sections:%s",
        "enabled" if include_details else "summary-only",
    )
    return model
