from __future__ import annotations

import logging
from typing import Any

from aurora_translator.sources.aedb.models import LayerModel
from aurora_translator.sources.aedb.normalizers import safe_getattr
from aurora_translator.shared.logging import log_timing

from .context import ExtractionContext


logger = logging.getLogger("aurora_translator.aedb.extractors.layers")


def extract_layer(layer: Any) -> LayerModel:
    return LayerModel.model_validate(
        {
            "name": safe_getattr(layer, "name"),
            "id": safe_getattr(layer, "id"),
            "type": safe_getattr(layer, "type"),
            "material": safe_getattr(layer, "material"),
            "fill_material": safe_getattr(layer, "fill_material"),
            "dielectric_fill": safe_getattr(layer, "dielectric_fill"),
            "thickness": safe_getattr(layer, "thickness"),
            "lower_elevation": safe_getattr(layer, "lower_elevation"),
            "upper_elevation": safe_getattr(layer, "upper_elevation"),
            "conductivity": safe_getattr(layer, "conductivity"),
            "permittivity": safe_getattr(layer, "permittivity"),
            "loss_tangent": safe_getattr(layer, "loss_tangent"),
            "roughness_enabled": safe_getattr(layer, "roughness_enabled"),
            "is_negative": safe_getattr(layer, "is_negative"),
            "is_stackup_layer": safe_getattr(layer, "is_stackup_layer"),
            "is_via_layer": safe_getattr(layer, "is_via_layer"),
            "color": safe_getattr(layer, "color"),
            "transparency": safe_getattr(layer, "transparency"),
        }
    )


def extract_layers(context: ExtractionContext) -> list[LayerModel]:
    layer_values = context.layers
    with log_timing(logger, "serialize layers", count=len(layer_values)):
        return [extract_layer(layer) for layer in layer_values]
