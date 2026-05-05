from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aurora_translator.semantic.models import (
    SemanticBoard,
    SemanticLayer,
    SemanticMaterial,
)
from aurora_translator.targets.auroradb.formatting import (
    MIL_PER_METER,
    _auroradb_output_unit,
    _format_number,
    _format_scalar,
    _length_to_unit,
    _number,
    _unit_scale_to_mil,
)
from aurora_translator.targets.auroradb.names import _standardize_name, _unique_name


DEFAULT_METAL_THICKNESS_MIL = 3.56e-5 * MIL_PER_METER
DEFAULT_DIELECTRIC_THICKNESS_MIL = 0.5
DEFAULT_CONDUCTIVITY = 5.8e7
DEFAULT_PERMITTIVITY = 4.5
DEFAULT_DIELECTRIC_LOSS_TANGENT = 0.02


@dataclass(slots=True)
class _ExportLayer:
    source_name: str | None
    name: str
    kind: str
    thickness: float
    unit: str
    material_name: str
    material: SemanticMaterial | None = None
    generated: bool = False
    conductivity: Any = None
    permittivity: Any = None
    dielectric_loss_tangent: Any = None


def _export_layers(board: SemanticBoard) -> list[_ExportLayer]:
    materials_by_id = {material.id: material for material in board.materials}
    materials_by_name = {
        material.name.casefold(): material for material in board.materials
    }
    output_unit = _auroradb_output_unit(board.units)
    seen_names: set[str] = set()
    export_layers: list[_ExportLayer] = []

    for index, layer in enumerate(_ordered_layers(board.layers)):
        kind = _stackup_kind(layer)
        if kind is None:
            continue
        material = _layer_material(layer, kind, materials_by_id, materials_by_name)
        default_material = "COPPER_AURORA" if kind == "Metal" else "DIELECTRIC_AURORA"
        material_name = _standardize_name(
            material.name if material else default_material
        )
        layer_name = _unique_name(
            _standardize_name(layer.name or f"Layer_{index}"), seen_names
        )
        thickness = _length_to_unit(
            layer.thickness, source_unit=board.units, target_unit=output_unit
        )
        if thickness is None or thickness <= 0:
            thickness = (
                _mil_to_unit(DEFAULT_METAL_THICKNESS_MIL, output_unit)
                if kind == "Metal"
                else _mil_to_unit(DEFAULT_DIELECTRIC_THICKNESS_MIL, output_unit)
            )

        export_layers.append(
            _ExportLayer(
                source_name=layer.name,
                name=layer_name,
                kind=kind,
                thickness=thickness,
                unit=output_unit,
                material_name=material_name,
                material=material,
            )
        )
    return export_layers


def _with_generated_dielectrics(layers: list[_ExportLayer]) -> list[_ExportLayer]:
    if not layers:
        return []

    result: list[_ExportLayer] = []
    unit = layers[0].unit
    default_index = 0
    for index, layer in enumerate(layers):
        if index == 0 and layer.kind == "Metal":
            result.append(
                _generated_dielectric("SOLDERMASK_TOP", "SOLDERMASK_AURORA", unit=unit)
            )
        if result and layer.kind == "Metal" and result[-1].kind == "Metal":
            result.append(
                _generated_dielectric(
                    f"DIELECTRIC_AURORA_{default_index}",
                    "DIELECTRIC_AURORA",
                    unit=unit,
                )
            )
            default_index += 1
        result.append(layer)
        if index == len(layers) - 1 and layer.kind == "Metal":
            result.append(
                _generated_dielectric(
                    "SOLDERMASK_BOTTOM", "SOLDERMASK_AURORA", unit=unit
                )
            )
    return result


def _stackup_dat(layers: list[_ExportLayer], *, design_name: str | None = None) -> str:
    lines = ["Stackup {"]
    if design_name:
        lines.append(f"Design {design_name}")
    lines.append(f"Unit {_stackup_unit(layers)}")
    for layer in layers:
        thickness = _format_number(layer.thickness)
        if layer.kind == "Metal":
            sigma = _format_stackup_scalar(
                _material_property(layer, "conductivity", DEFAULT_CONDUCTIVITY)
            )
            lines.append(f"Metal {layer.name} {thickness} {sigma}")
        else:
            eps_r = _format_scalar(
                _material_property(layer, "permittivity", DEFAULT_PERMITTIVITY)
            )
            delta = _format_scalar(
                _material_property(
                    layer, "dielectric_loss_tangent", DEFAULT_DIELECTRIC_LOSS_TANGENT
                )
            )
            lines.append(f"Dielectric {layer.name} {thickness} {eps_r} {delta}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _format_stackup_scalar(value: Any) -> str:
    number = _number(value)
    if number is None:
        return str(value)
    if abs(number) >= 1_000_000:
        return f"{number:.6g}".replace("e+", "e").replace("e0", "e")
    return _format_number(number)


def _stackup_json(layers: list[_ExportLayer]) -> dict[str, Any]:
    materials: list[dict[str, Any]] = []
    seen_materials: set[str] = set()
    stackup_layers: list[dict[str, Any]] = []

    for layer in layers:
        material_key = layer.material_name.casefold()
        if material_key not in seen_materials:
            seen_materials.add(material_key)
            if layer.kind == "Metal":
                materials.append(
                    {
                        "name": layer.material_name,
                        "type": "Metal",
                        "sigma": _json_scalar(
                            _material_property(
                                layer, "conductivity", DEFAULT_CONDUCTIVITY
                            )
                        ),
                        "freq_dep": "no",
                    }
                )
            else:
                materials.append(
                    {
                        "name": layer.material_name,
                        "type": "Dielectric",
                        "eps_r": _json_scalar(
                            _material_property(
                                layer, "permittivity", DEFAULT_PERMITTIVITY
                            )
                        ),
                        "delta": _json_scalar(
                            _material_property(
                                layer,
                                "dielectric_loss_tangent",
                                DEFAULT_DIELECTRIC_LOSS_TANGENT,
                            )
                        ),
                        "freq_dep": "no",
                    }
                )

        stackup_layers.append(
            {
                "name": layer.name,
                "type": layer.kind,
                "thickness": _format_number(layer.thickness),
                "material": layer.material_name,
                "roughness": {"type": "no"},
                "bot_roughness": {"type": "no"},
                "side_roughness": {"type": "no"},
            }
        )

    return {
        "version": "1.1",
        "unit": _stackup_unit(layers),
        "materials": materials,
        "layers": stackup_layers,
    }


def _stackup_unit(layers: list[_ExportLayer]) -> str:
    if layers:
        return layers[0].unit
    return "mils"


def _ordered_layers(layers: list[SemanticLayer]) -> list[SemanticLayer]:
    indexed_layers = list(enumerate(layers))
    indexed_layers.sort(
        key=lambda item: (
            item[1].order_index is None,
            item[1].order_index if item[1].order_index is not None else item[0],
            item[0],
        )
    )
    return [layer for _, layer in indexed_layers]


def _stackup_kind(layer: SemanticLayer) -> str | None:
    role = (layer.role or "").casefold()
    layer_type = (layer.layer_type or "").casefold()
    if (
        role in {"signal", "plane"}
        or "signallayer" in layer_type
        or "signal" in layer_type
    ):
        return "Metal"
    if role == "dielectric" or "dielectric" in layer_type:
        return "Dielectric"
    return None


def _layer_material(
    layer: SemanticLayer,
    kind: str,
    materials_by_id: dict[str, SemanticMaterial],
    materials_by_name: dict[str, SemanticMaterial],
) -> SemanticMaterial | None:
    candidates: list[SemanticMaterial] = []
    for material_id in [layer.material_id, layer.fill_material_id]:
        if material_id and material_id in materials_by_id:
            candidates.append(materials_by_id[material_id])
    for material_name in [layer.material, layer.fill_material]:
        if material_name and material_name.casefold() in materials_by_name:
            candidates.append(materials_by_name[material_name.casefold()])

    preferred_role = "metal" if kind == "Metal" else "dielectric"
    for material in candidates:
        if material.role == preferred_role:
            return material
    return candidates[0] if candidates else None


def _generated_dielectric(name: str, material_name: str, *, unit: str) -> _ExportLayer:
    return _ExportLayer(
        source_name=None,
        name=name,
        kind="Dielectric",
        thickness=_mil_to_unit(DEFAULT_DIELECTRIC_THICKNESS_MIL, unit),
        unit=unit,
        material_name=material_name,
        generated=True,
        permittivity=DEFAULT_PERMITTIVITY,
        dielectric_loss_tangent=DEFAULT_DIELECTRIC_LOSS_TANGENT,
    )


def _mil_to_unit(value_mil: float, unit: str) -> float:
    scale = _unit_scale_to_mil(unit)
    if scale is None or scale == 0:
        return value_mil
    return value_mil / scale


def _material_property(layer: _ExportLayer, field_name: str, default: Any) -> Any:
    generated_value = getattr(layer, field_name)
    if generated_value is not None:
        return generated_value
    material_value = (
        getattr(layer.material, field_name, None)
        if layer.material is not None
        else None
    )
    return _scalar_value(material_value, default)


def _scalar_value(value: Any, default: Any) -> Any:
    if value in {None, ""}:
        return default
    number = _number(value)
    return number if number is not None else value


def _json_scalar(value: Any) -> Any:
    number = _number(value)
    return number if number is not None else value
