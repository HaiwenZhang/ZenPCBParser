from __future__ import annotations

import logging
from typing import Any

from aurora_translator.sources.aedb.models import MaterialModel
from aurora_translator.sources.aedb.normalizers import safe_getattr
from aurora_translator.shared.logging import log_timing

from .context import ExtractionContext


logger = logging.getLogger("aurora_translator.aedb.extractors.materials")


def extract_material(material: Any) -> MaterialModel:
    return MaterialModel.model_validate(
        {
            "name": safe_getattr(material, "name"),
            "type": safe_getattr(material, "type"),
            "conductivity": safe_getattr(material, "conductivity"),
            "dc_conductivity": safe_getattr(material, "dc_conductivity"),
            "permittivity": safe_getattr(material, "permittivity"),
            "dc_permittivity": safe_getattr(material, "dc_permittivity"),
            "permeability": safe_getattr(material, "permeability"),
            "loss_tangent": safe_getattr(material, "loss_tangent"),
            "dielectric_loss_tangent": safe_getattr(
                material, "dielectric_loss_tangent"
            ),
            "magnetic_loss_tangent": safe_getattr(material, "magnetic_loss_tangent"),
            "mass_density": safe_getattr(material, "mass_density"),
            "poisson_ratio": safe_getattr(material, "poisson_ratio"),
            "specific_heat": safe_getattr(material, "specific_heat"),
            "thermal_conductivity": safe_getattr(material, "thermal_conductivity"),
            "thermal_expansion_coefficient": safe_getattr(
                material, "thermal_expansion_coefficient"
            ),
            "youngs_modulus": safe_getattr(material, "youngs_modulus"),
            "dielectric_model_frequency": safe_getattr(
                material, "dielectric_model_frequency"
            ),
        }
    )


def extract_materials(context: ExtractionContext) -> list[MaterialModel]:
    material_values = context.materials
    with log_timing(logger, "serialize materials", count=len(material_values)):
        return sorted(
            (extract_material(material) for material in material_values),
            key=lambda item: item.name or "",
        )
