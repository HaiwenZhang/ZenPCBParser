from __future__ import annotations

import math
import re
from typing import Any

from aurora_translator.sources.aedb.models import (
    AEDBLayout,
    LayerModel,
    MaterialModel,
    PadPropertyModel,
    PadstackDefinitionModel,
    PathPrimitiveModel,
    PolygonPrimitiveModel,
)
from aurora_translator.semantic.adapters.utils import (
    point_from_pair,
    role_from_layer_type,
    role_from_net_name,
    semantic_id,
    side_from_layer_name,
    source_ref,
    text_value,
)
from aurora_translator.semantic.models import (
    SemanticBoard,
    SemanticComponent,
    SemanticDiagnostic,
    SemanticFootprint,
    SemanticLayer,
    SemanticMaterial,
    SemanticMetadata,
    SemanticNet,
    SemanticPad,
    SemanticPin,
    SemanticPrimitive,
    SemanticPrimitiveGeometry,
    SemanticShape,
    SemanticSummary,
    SemanticVia,
    SemanticViaTemplate,
    SemanticViaTemplateLayer,
)
from aurora_translator.semantic.passes import (
    build_connectivity_diagnostics,
    build_connectivity_edges,
)


def from_aedb(payload: AEDBLayout, *, build_connectivity: bool = True) -> SemanticBoard:
    nets_by_id: dict[str, SemanticNet] = {}
    components_by_id: dict[str, SemanticComponent] = {}
    footprints_by_id: dict[str, SemanticFootprint] = {}
    pins: list[SemanticPin] = []
    pads: list[SemanticPad] = []
    vias: list[SemanticVia] = []
    primitives: list[SemanticPrimitive] = []
    diagnostics: list[SemanticDiagnostic] = []
    materials: list[SemanticMaterial] = []
    material_ids_by_name: dict[str, str] = {}
    shapes: list[SemanticShape] = []
    shape_ids_by_key: dict[tuple[str, tuple[str, ...]], str] = {}
    via_templates: list[SemanticViaTemplate] = []
    via_template_ids_by_name: dict[str, str] = {}
    seen_list_members: dict[str, set[str]] = {}

    def append_unique(owner_key: str, values: list[str], value: str | None) -> None:
        if not value:
            return
        seen = seen_list_members.setdefault(owner_key, set())
        if value in seen:
            return
        seen.add(value)
        values.append(value)

    for material_index, material in enumerate(payload.materials or []):
        _add_material_from_model(
            materials, material_ids_by_name, material, material_index
        )

    layers: list[SemanticLayer] = []
    for index, layer in enumerate(payload.layers or []):
        layer_type = text_value(layer.type)
        role = role_from_layer_type(layer_type, is_via_layer=layer.is_via_layer)
        material_name = _clean_material_name(layer.material)
        fill_material_name = _clean_material_name(
            layer.fill_material or layer.dielectric_fill
        )
        material_id = _ensure_layer_material(
            materials,
            material_ids_by_name,
            layer,
            material_name,
            index,
            role=role,
            path=f"layers[{index}].material",
        )
        fill_material_id = _ensure_layer_material(
            materials,
            material_ids_by_name,
            layer,
            fill_material_name,
            index,
            role="dielectric" if role == "dielectric" else "unknown",
            path=f"layers[{index}].fill_material",
        )
        layers.append(
            SemanticLayer(
                id=semantic_id("layer", layer.name, index),
                name=layer.name or f"layer_{index}",
                layer_type=layer_type,
                role=role,
                side=side_from_layer_name(layer.name),
                order_index=index,
                material=material_name,
                material_id=material_id,
                fill_material=fill_material_name,
                fill_material_id=fill_material_id,
                thickness=text_value(layer.thickness),
                source=source_ref("aedb", f"layers[{index}]", layer.id),
            )
        )
    layer_order_by_name = _layer_order_by_name(layers)

    for index, net in enumerate(payload.nets or []):
        name = net.name or f"net_{index}"
        net_id = semantic_id("net", name, index)
        nets_by_id[net_id] = SemanticNet(
            id=net_id,
            name=name,
            role="power" if net.is_power_ground else role_from_net_name(name),
            source=source_ref("aedb", f"nets[{index}]", name),
        )

    for component_index, component in enumerate(payload.components or []):
        refdes = component.refdes or component.component_name
        component_id = semantic_id("component", refdes, component_index)
        footprint_id = None
        if component.part_name:
            footprint_id = semantic_id("footprint", component.part_name)
            if footprint_id not in footprints_by_id:
                footprints_by_id[footprint_id] = SemanticFootprint(
                    id=footprint_id,
                    name=component.part_name,
                    part_name=component.part_name,
                    source=source_ref(
                        "aedb",
                        f"components[{component_index}].part_name",
                        component.part_name,
                    ),
                )
        semantic_component = SemanticComponent(
            id=component_id,
            refdes=component.refdes,
            name=component.component_name,
            part_name=component.part_name,
            package_name=component.part_name,
            footprint_id=footprint_id,
            layer_name=component.placement_layer,
            side=side_from_layer_name(
                component.placement_layer, is_top=component.is_top_mounted
            ),
            value=text_value(component.value),
            location=point_from_pair(component.center or component.location),
            rotation=component.rotation,
            source=source_ref("aedb", f"components[{component_index}]", refdes),
        )
        components_by_id[component_id] = semantic_component

        for pin_index, pin in enumerate(component.pins):
            pin_label = pin.name or pin.id
            pin_id = semantic_id(
                "pin",
                f"{component_id}:{pin_label}" if pin_label is not None else None,
                f"{component_id}:{pin_index}",
            )
            net_id = semantic_id("net", pin.net_name) if pin.net_name else None
            semantic_pin = SemanticPin(
                id=pin_id,
                name=pin.name,
                component_id=component_id,
                net_id=net_id,
                layer_name=pin.placement_layer or pin.start_layer,
                position=point_from_pair(pin.position),
                source=source_ref(
                    "aedb", f"components[{component_index}].pins[{pin_index}]", pin.id
                ),
            )
            pins.append(semantic_pin)
            append_unique(
                f"component:{component_id}:pins", semantic_component.pin_ids, pin_id
            )
            if net_id in nets_by_id:
                append_unique(f"net:{net_id}:pins", nets_by_id[net_id].pin_ids, pin_id)

            pad_id = semantic_id(
                "pad",
                f"{component_id}:{pin_label}" if pin_label is not None else None,
                f"{component_id}:{pin_index}",
            )
            semantic_pad = SemanticPad(
                id=pad_id,
                name=pin.name,
                footprint_id=footprint_id,
                component_id=component_id,
                pin_id=pin_id,
                net_id=net_id,
                layer_name=pin.placement_layer or pin.start_layer,
                position=point_from_pair(pin.position),
                padstack_definition=pin.padstack_definition,
                geometry={"rotation": pin.rotation},
                source=source_ref(
                    "aedb", f"components[{component_index}].pins[{pin_index}]", pin.id
                ),
            )
            pads.append(semantic_pad)
            append_unique(f"pin:{pin_id}:pads", semantic_pin.pad_ids, pad_id)
            append_unique(
                f"component:{component_id}:pads", semantic_component.pad_ids, pad_id
            )
            if footprint_id in footprints_by_id:
                append_unique(
                    f"footprint:{footprint_id}:pads",
                    footprints_by_id[footprint_id].pad_ids,
                    pad_id,
                )
            if net_id in nets_by_id:
                append_unique(f"net:{net_id}:pads", nets_by_id[net_id].pad_ids, pad_id)

    if payload.padstacks is not None:
        for definition_index, definition in enumerate(payload.padstacks.definitions):
            via_template = _via_template_from_padstack_definition(
                definition,
                definition_index,
                shapes,
                shape_ids_by_key,
                layer_order_by_name,
            )
            via_templates.append(via_template)
            via_template_ids_by_name[via_template.name.casefold()] = via_template.id

    if payload.components is None:
        diagnostics.append(
            SemanticDiagnostic(
                code="aedb.components_missing",
                message="AEDB component details are not present; semantic pins and component connectivity are limited.",
                source=source_ref("aedb", "components"),
            )
        )

    if payload.padstacks is not None:
        for via_index, instance in enumerate(payload.padstacks.instances):
            if instance.is_pin:
                continue
            net_id = (
                semantic_id("net", instance.net_name) if instance.net_name else None
            )
            layer_names = [
                str(layer)
                for layer in (instance.layer_range_names or [])
                if layer not in {None, ""}
            ]
            if not layer_names:
                layer_names = [
                    name for name in [instance.start_layer, instance.stop_layer] if name
                ]
            via_id = semantic_id("via", instance.id or instance.name, via_index)
            vias.append(
                SemanticVia(
                    id=via_id,
                    name=instance.name,
                    template_id=_via_template_id_for_name(
                        via_template_ids_by_name, instance.padstack_definition
                    ),
                    net_id=net_id,
                    layer_names=layer_names,
                    position=point_from_pair(instance.position),
                    source=source_ref(
                        "aedb",
                        f"padstacks.instances[{via_index}]",
                        instance.id or instance.name,
                    ),
                )
            )
            if net_id in nets_by_id:
                append_unique(f"net:{net_id}:vias", nets_by_id[net_id].via_ids, via_id)

    if payload.primitives is not None:
        for path_index, path in enumerate(payload.primitives.paths):
            primitive = _path_primitive(path, path_index)
            primitives.append(primitive)
            if primitive.net_id in nets_by_id:
                append_unique(
                    f"net:{primitive.net_id}:primitives",
                    nets_by_id[primitive.net_id].primitive_ids,
                    primitive.id,
                )
        for polygon_index, polygon in enumerate(payload.primitives.polygons):
            primitive = _polygon_primitive(
                polygon, polygon_index, "polygon", "primitives.polygons"
            )
            primitives.append(primitive)
            if primitive.net_id in nets_by_id:
                append_unique(
                    f"net:{primitive.net_id}:primitives",
                    nets_by_id[primitive.net_id].primitive_ids,
                    primitive.id,
                )
        for zone_index, zone in enumerate(payload.primitives.zone_primitives):
            primitive = _polygon_primitive(
                zone, zone_index, "zone", "primitives.zone_primitives"
            )
            primitives.append(primitive)
            if primitive.net_id in nets_by_id:
                append_unique(
                    f"net:{primitive.net_id}:primitives",
                    nets_by_id[primitive.net_id].primitive_ids,
                    primitive.id,
                )

    board = SemanticBoard(
        metadata=SemanticMetadata(
            source_format="aedb",
            source=payload.metadata.source,
            source_parser_version=payload.metadata.parser_version,
            source_schema_version=payload.metadata.output_schema_version,
        ),
        units="m",
        summary=SemanticSummary(),
        layers=layers,
        materials=materials,
        shapes=shapes,
        via_templates=via_templates,
        nets=list(nets_by_id.values()),
        components=list(components_by_id.values()),
        footprints=list(footprints_by_id.values()),
        pins=pins,
        pads=pads,
        vias=vias,
        primitives=primitives,
        diagnostics=diagnostics,
    )
    if build_connectivity:
        board.connectivity = build_connectivity_edges(board)
        board.diagnostics = [*board.diagnostics, *build_connectivity_diagnostics(board)]
    return board.with_computed_summary()


def _add_material_from_model(
    materials: list[SemanticMaterial],
    material_ids_by_name: dict[str, str],
    material: MaterialModel,
    index: int,
) -> str | None:
    name = _clean_material_name(material.name)
    if name is None:
        return None
    conductivity = _first_text(material.conductivity, material.dc_conductivity)
    permittivity = _first_text(material.permittivity, material.dc_permittivity)
    dielectric_loss_tangent = _first_text(
        material.dielectric_loss_tangent, material.loss_tangent
    )
    return _upsert_material(
        materials,
        material_ids_by_name,
        name=name,
        role=_material_role(
            material_type=text_value(material.type),
            layer_role=None,
            conductivity=conductivity,
            permittivity=permittivity,
            dielectric_loss_tangent=dielectric_loss_tangent,
        ),
        conductivity=conductivity,
        permittivity=permittivity,
        dielectric_loss_tangent=dielectric_loss_tangent,
        source=source_ref("aedb", f"materials[{index}]", name),
    )


def _ensure_layer_material(
    materials: list[SemanticMaterial],
    material_ids_by_name: dict[str, str],
    layer: LayerModel,
    name: str | None,
    index: int,
    *,
    role: str | None,
    path: str,
) -> str | None:
    if name is None:
        return None
    existing_id = material_ids_by_name.get(name.casefold())
    if existing_id is not None:
        return existing_id
    conductivity = _first_text(layer.conductivity)
    permittivity = _first_text(layer.permittivity)
    dielectric_loss_tangent = _first_text(layer.loss_tangent)
    return _upsert_material(
        materials,
        material_ids_by_name,
        name=name,
        role=_material_role(
            material_type=None,
            layer_role=role,
            conductivity=conductivity,
            permittivity=permittivity,
            dielectric_loss_tangent=dielectric_loss_tangent,
        ),
        conductivity=conductivity,
        permittivity=permittivity,
        dielectric_loss_tangent=dielectric_loss_tangent,
        source=source_ref("aedb", path, layer.id if layer.id is not None else index),
    )


def _upsert_material(
    materials: list[SemanticMaterial],
    material_ids_by_name: dict[str, str],
    *,
    name: str,
    role: str,
    conductivity: str | None,
    permittivity: str | None,
    dielectric_loss_tangent: str | None,
    source,
) -> str:
    key = name.casefold()
    existing_id = material_ids_by_name.get(key)
    if existing_id is not None:
        return existing_id
    material_id = semantic_id("material", name, len(materials))
    materials.append(
        SemanticMaterial(
            id=material_id,
            name=name,
            role=role,  # type: ignore[arg-type]
            conductivity=conductivity,
            permittivity=permittivity,
            dielectric_loss_tangent=dielectric_loss_tangent,
            source=source,
        )
    )
    material_ids_by_name[key] = material_id
    return material_id


def _material_role(
    *,
    material_type: str | None,
    layer_role: str | None,
    conductivity: str | None,
    permittivity: str | None,
    dielectric_loss_tangent: str | None,
) -> str:
    type_text = (material_type or "").casefold()
    if "dielectric" in type_text:
        return "dielectric"
    if "metal" in type_text or "conductor" in type_text:
        return "metal"
    if layer_role == "dielectric":
        return "dielectric"
    if layer_role in {"signal", "plane"}:
        return "metal"
    if conductivity and not (permittivity or dielectric_loss_tangent):
        return "metal"
    if permittivity or dielectric_loss_tangent:
        return "dielectric"
    return "unknown"


def _first_text(*values: object | None) -> str | None:
    for value in values:
        text = text_value(value)
        if text not in {None, ""}:
            return text
    return None


def _clean_material_name(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.casefold() in {"none", "null"}:
        return None
    return text


def _via_template_from_padstack_definition(
    definition: PadstackDefinitionModel,
    index: int,
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[str, ...]], str],
    layer_order_by_name: dict[str, int],
) -> SemanticViaTemplate:
    name = definition.name or f"padstack_{index}"
    barrel_shape_id = _shape_from_hole(definition, index, shapes, shape_ids_by_key)
    layer_names = sorted(
        {
            *definition.pad_by_layer.keys(),
            *definition.antipad_by_layer.keys(),
            *definition.thermalpad_by_layer.keys(),
        },
        key=lambda layer_name: _layer_sort_key(layer_name, layer_order_by_name),
    )
    layer_pads: list[SemanticViaTemplateLayer] = []
    for layer_name in layer_names:
        pad_shape_id = _shape_from_pad_property(
            definition.pad_by_layer.get(layer_name),
            shapes,
            shape_ids_by_key,
            path=f"padstacks.definitions[{index}].pad_by_layer[{layer_name}]",
        )
        antipad_shape_id = _shape_from_pad_property(
            definition.antipad_by_layer.get(layer_name),
            shapes,
            shape_ids_by_key,
            path=f"padstacks.definitions[{index}].antipad_by_layer[{layer_name}]",
        )
        thermal_shape_id = _shape_from_pad_property(
            definition.thermalpad_by_layer.get(layer_name),
            shapes,
            shape_ids_by_key,
            path=f"padstacks.definitions[{index}].thermalpad_by_layer[{layer_name}]",
        )
        if pad_shape_id or antipad_shape_id or thermal_shape_id:
            layer_pads.append(
                SemanticViaTemplateLayer(
                    layer_name=str(layer_name),
                    pad_shape_id=pad_shape_id,
                    antipad_shape_id=antipad_shape_id,
                    thermal_shape_id=thermal_shape_id,
                )
            )

    return SemanticViaTemplate(
        id=semantic_id("via_template", name, index),
        name=name,
        barrel_shape_id=barrel_shape_id,
        layer_pads=layer_pads,
        source=source_ref("aedb", f"padstacks.definitions[{index}]", name),
    )


def _layer_order_by_name(layers: list[SemanticLayer]) -> dict[str, int]:
    return {layer.name.casefold(): layer.order_index for layer in layers if layer.name}


def _layer_sort_key(
    layer_name: str, layer_order_by_name: dict[str, int]
) -> tuple[int, str]:
    name = str(layer_name)
    return (layer_order_by_name.get(name.casefold(), 1_000_000), name.casefold())


def _shape_from_hole(
    definition: PadstackDefinitionModel,
    index: int,
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[str, ...]], str],
) -> str | None:
    diameter = text_value(definition.hole_diameter) or text_value(
        definition.hole_finished_size
    )
    if diameter in {None, ""}:
        return None
    shape_type = text_value(definition.hole_type)
    if (
        shape_type
        and "circle" not in shape_type.casefold()
        and "round" not in shape_type.casefold()
    ):
        return None
    return _upsert_shape(
        shapes,
        shape_ids_by_key,
        kind="circle",
        auroradb_type="Circle",
        values=[0, 0, diameter],
        name=f"{definition.name or f'padstack_{index}'}_hole",
        source=source_ref(
            "aedb", f"padstacks.definitions[{index}].hole_diameter", definition.name
        ),
    )


def _shape_from_pad_property(
    pad_property: PadPropertyModel | None,
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[str, ...]], str],
    *,
    path: str,
) -> str | None:
    if pad_property is None:
        return None
    shape = _shape_geometry(pad_property)
    if shape is None:
        return None
    kind, auroradb_type, values = shape
    return _upsert_shape(
        shapes,
        shape_ids_by_key,
        kind=kind,
        auroradb_type=auroradb_type,
        values=values,
        name=text_value(pad_property.shape) or text_value(pad_property.geometry_type),
        source=source_ref("aedb", path, text_value(pad_property.geometry_type)),
    )


def _shape_geometry(
    pad_property: PadPropertyModel,
) -> tuple[str, str, list[str | float | int]] | None:
    shape_text = " ".join(
        value
        for value in [
            text_value(pad_property.geometry_type),
            text_value(pad_property.shape),
        ]
        if value
    ).casefold()
    if not shape_text or "nogeometry" in shape_text or shape_text in {"none", "null"}:
        return None

    parameters = pad_property.parameters or {}
    if "round45" in shape_text:
        polygon_values = _round_thermal_pad_shape_values(
            pad_property, rotation_degrees=45.0
        )
        if polygon_values is not None:
            return ("polygon", "Polygon", polygon_values)
        return None

    if "round90" in shape_text:
        polygon_values = _round_thermal_pad_shape_values(
            pad_property, rotation_degrees=0.0
        )
        if polygon_values is not None:
            return ("polygon", "Polygon", polygon_values)
        return None

    if "bullet" in shape_text:
        polygon_values = _bullet_pad_shape_values(pad_property)
        if polygon_values is not None:
            return ("polygon", "Polygon", polygon_values)
        return None

    if (
        "nsidedpolygon" in shape_text
        or "nsided polygon" in shape_text
        or "n sided polygon" in shape_text
    ):
        polygon_values = _nsided_polygon_pad_shape_values(pad_property)
        if polygon_values is not None:
            return ("polygon", "Polygon", polygon_values)
        return None

    if "polygon" in shape_text:
        polygon_values = _polygon_pad_shape_values(pad_property)
        if polygon_values is not None:
            return ("polygon", "Polygon", polygon_values)
        return None

    if "circle" in shape_text or "round" in shape_text:
        diameter = _dimension(parameters, ["diameter", "diam", "dia", "size", "d"])
        if diameter is None:
            diameter = _first_dimension(parameters)
        return ("circle", "Circle", [0, 0, diameter]) if diameter is not None else None

    if "oval" in shape_text or "rounded" in shape_text:
        width = _dimension(parameters, ["width", "x_size", "xsize", "x", "w"])
        height = _dimension(
            parameters, ["height", "length", "y_size", "ysize", "y", "h", "l"]
        )
        radius = (
            _dimension(parameters, ["radius", "corner_radius", "rounding", "r"]) or 0
        )
        values = _first_dimensions(parameters, 3)
        if width is None and len(values) >= 1:
            width = values[0]
        if height is None and len(values) >= 2:
            height = values[1]
        if radius == 0 and len(values) >= 3:
            radius = values[2]
        if width is not None and height is not None:
            return (
                "rounded_rectangle",
                "RoundedRectangle",
                [0, 0, width, height, radius],
            )
        return None

    if "rect" in shape_text or "square" in shape_text:
        width = _dimension(parameters, ["width", "x_size", "xsize", "x", "w"])
        height = _dimension(
            parameters, ["height", "length", "y_size", "ysize", "y", "h", "l"]
        )
        values = _first_dimensions(parameters, 2)
        if width is None and len(values) >= 1:
            width = values[0]
        if height is None and len(values) >= 2:
            height = values[1]
        if height is None:
            height = width
        if width is not None and height is not None:
            return ("rectangle", "Rectangle", [0, 0, width, height])
        return None

    return None


def _nsided_polygon_pad_shape_values(
    pad_property: PadPropertyModel,
) -> list[str | float | int] | None:
    parameters = pad_property.parameters or {}
    size = _dimension_float(parameters, ["size", "diameter", "diam", "dia", "d"])
    sides = _dimension_float(
        parameters, ["num_sides", "numsides", "num sides", "sides", "n"]
    )
    if size is None or sides is None:
        values = _first_dimension_floats(parameters, 2)
        if size is None and len(values) >= 1:
            size = values[0]
        if sides is None and len(values) >= 2:
            sides = values[1]
    if size is None or sides is None:
        return None
    side_count = int(round(sides))
    if side_count < 3 or size <= 0:
        return None

    radius = size / 2.0
    # Match the legacy AEDB adapter orientation for regular polygons.
    angle_offset = math.radians(90.0 * (side_count - 2) / side_count)
    points = [
        (
            radius * math.cos(angle_offset + 2.0 * math.pi * index / side_count),
            radius * math.sin(angle_offset + 2.0 * math.pi * index / side_count),
        )
        for index in range(side_count)
    ]
    return _polygon_shape_values_from_points(points, pad_property)


def _bullet_pad_shape_values(
    pad_property: PadPropertyModel,
) -> list[str | float | int] | None:
    parameters = pad_property.parameters or {}
    width = _dimension_float(parameters, ["width", "x_size", "xsize", "x", "w"])
    height = _dimension_float(
        parameters, ["height", "length", "y_size", "ysize", "y", "h", "l"]
    )
    radius = _dimension_float(
        parameters, ["radius", "corner_radius", "cornerradius", "rounding", "r"]
    )
    values = _first_dimension_floats(parameters, 3)
    if width is None and len(values) >= 1:
        width = values[0]
    if height is None and len(values) >= 2:
        height = values[1]
    if radius is None and len(values) >= 3:
        radius = values[2]
    if width is None or height is None or width <= 0 or height <= 0:
        return None
    if radius is None:
        radius = min(width, height) / 2.0
    radius = max(0.0, min(radius, width / 2.0, height / 2.0))
    half_width = width / 2.0
    half_height = height / 2.0
    if radius <= 0.0:
        return _polygon_shape_values_from_points(
            [
                (-half_width, -half_height),
                (half_width, -half_height),
                (half_width, half_height),
                (-half_width, half_height),
            ],
            pad_property,
        )

    parts = [
        ("point", (-half_width + radius, -half_height)),
        ("point", (half_width - radius, -half_height)),
        (
            "arc",
            (half_width, -half_height + radius),
            (half_width - radius, -half_height + radius),
            "Y",
        ),
        ("point", (half_width, half_height - radius)),
        (
            "arc",
            (half_width - radius, half_height),
            (half_width - radius, half_height - radius),
            "Y",
        ),
        ("point", (-half_width + radius, half_height)),
        (
            "arc",
            (-half_width, half_height - radius),
            (-half_width + radius, half_height - radius),
            "Y",
        ),
        ("point", (-half_width, -half_height + radius)),
        (
            "arc",
            (-half_width + radius, -half_height),
            (-half_width + radius, -half_height + radius),
            "Y",
        ),
    ]
    return _polygon_shape_values_from_parts(parts, pad_property)


def _round_thermal_pad_shape_values(
    pad_property: PadPropertyModel,
    *,
    rotation_degrees: float,
) -> list[str | float | int] | None:
    parameters = pad_property.parameters or {}
    inner = _dimension_float(
        parameters, ["inner", "inner_diameter", "innerdiameter", "diameter", "diam"]
    )
    channel_width = _dimension_float(
        parameters,
        ["channel_width", "channelwidth", "channel", "width", "w"],
    )
    isolation_gap = _dimension_float(
        parameters,
        ["isolation_gap", "isolationgap", "gap", "clearance"],
    )
    values = _first_dimension_floats(parameters, 3)
    if inner is None and len(values) >= 1:
        inner = values[0]
    if channel_width is None and len(values) >= 2:
        channel_width = values[1]
    if isolation_gap is None and len(values) >= 3:
        isolation_gap = values[2]
    if inner is None or channel_width is None or inner <= 0 or channel_width <= 0:
        return None
    if isolation_gap is None:
        isolation_gap = 0.0

    outer_radius = max(inner / 2.0 + max(isolation_gap, 0.0), channel_width / 2.0)
    half_channel = min(channel_width / 2.0, outer_radius)
    if outer_radius <= 0.0 or half_channel <= 0.0:
        return None
    points = [
        (outer_radius, -half_channel),
        (half_channel, -half_channel),
        (half_channel, -outer_radius),
        (-half_channel, -outer_radius),
        (-half_channel, -half_channel),
        (-outer_radius, -half_channel),
        (-outer_radius, half_channel),
        (-half_channel, half_channel),
        (-half_channel, outer_radius),
        (half_channel, outer_radius),
        (half_channel, half_channel),
        (outer_radius, half_channel),
    ]
    rotated = _rotate_points(points, math.radians(rotation_degrees))
    return _polygon_shape_values_from_points(rotated, pad_property)


def _polygon_pad_shape_values(
    pad_property: PadPropertyModel,
) -> list[str | float | int] | None:
    vertices = _polygon_pad_vertices(pad_property)
    if len(vertices) < 3:
        return None
    return [len(vertices), *vertices, "Y", "Y"]


def _polygon_pad_vertices(pad_property: PadPropertyModel) -> list[str]:
    raw_points = pad_property.raw_points or []
    if not isinstance(raw_points, (list, tuple)):
        return []

    offset_x = _float_value(pad_property.offset_x) or 0.0
    offset_y = _float_value(pad_property.offset_y) or 0.0
    rotation = _float_value(pad_property.rotation) or 0.0
    cos_angle = math.cos(rotation)
    sin_angle = math.sin(rotation)

    items: list[tuple[float, float] | float] = []
    for raw_point in raw_points:
        point = _raw_point_pair(raw_point)
        if point is None:
            continue
        x, y = point
        if _is_arc_height_marker(y):
            items.append(x)
            continue
        transformed = (
            (x * cos_angle - y * sin_angle) + offset_x,
            (x * sin_angle + y * cos_angle) + offset_y,
        )
        if (
            items
            and isinstance(items[-1], tuple)
            and _same_point(items[-1], transformed)
        ):
            continue
        items.append(transformed)

    if not items:
        return []

    leading_arc_height: float | None = None
    if isinstance(items[0], float):
        leading_arc_height = items[0]
        items = items[1:]
    if not items or isinstance(items[0], float):
        return []

    vertices = [_polygon_vertex_value(items[0])]
    for index in range(1, len(items)):
        current = items[index]
        previous = items[index - 1]
        if isinstance(current, float):
            continue
        if isinstance(previous, float):
            if index < 2 or isinstance(items[index - 2], float):
                continue
            center = _arc_center_from_height(items[index - 2], current, previous)
            if center is None:
                continue
            vertices.append(
                _polygon_arc_value(current, center, _ccw_flag_from_arc_height(previous))
            )
        else:
            vertices.append(_polygon_vertex_value(current))

    if leading_arc_height is not None and not isinstance(items[-1], float):
        center = _arc_center_from_height(items[-1], items[0], leading_arc_height)
        if center is not None:
            vertices.append(
                _polygon_arc_value(
                    items[0], center, _ccw_flag_from_arc_height(leading_arc_height)
                )
            )
    elif (
        len(items) >= 2
        and isinstance(items[-1], float)
        and not isinstance(items[-2], float)
    ):
        center = _arc_center_from_height(items[-2], items[0], items[-1])
        if center is not None:
            vertices.append(
                _polygon_arc_value(
                    items[0], center, _ccw_flag_from_arc_height(items[-1])
                )
            )

    if len(vertices) >= 2 and vertices[0] == vertices[-1]:
        vertices.pop()
    return vertices


def _raw_point_pair(value: Any) -> tuple[float, float] | None:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        raw_x, raw_y = value[0], value[1]
    elif isinstance(value, dict):
        raw_x, raw_y = value.get("x"), value.get("y")
    else:
        raw_x, raw_y = getattr(value, "x", None), getattr(value, "y", None)
    x = _float_value(raw_x)
    y = _float_value(raw_y)
    if x is None or y is None:
        return None
    return x, y


def _float_value(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, dict):
        for key in ("value", "display"):
            number = _float_value(value.get(key))
            if number is not None:
                return number
        return None
    text = text_value(value)
    if text in {None, ""}:
        return None
    try:
        number = float(str(text).strip())
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _is_arc_height_marker(value: float) -> bool:
    return math.isfinite(value) and abs(value) > 1e100


def _same_point(left: tuple[float, float], right: tuple[float, float]) -> bool:
    return abs(left[0] - right[0]) <= 1e-15 and abs(left[1] - right[1]) <= 1e-15


def _arc_center_from_height(
    start: tuple[float, float],
    end: tuple[float, float],
    arc_height: float,
) -> tuple[float, float] | None:
    if not math.isfinite(arc_height) or abs(arc_height) < 1e-15:
        return None
    x2 = end[0] - start[0]
    y2 = end[1] - start[1]
    chord_squared = x2 * x2 + y2 * y2
    if chord_squared == 0:
        return start
    chord = math.sqrt(chord_squared)
    factor = 0.125 * chord / arc_height - 0.5 * arc_height / chord
    return (
        start[0] + 0.5 * x2 + y2 * factor,
        start[1] + 0.5 * y2 - x2 * factor,
    )


def _ccw_flag_from_arc_height(arc_height: float) -> str:
    return "Y" if arc_height < 0 else "N"


def _polygon_vertex_value(point: tuple[float, float]) -> str:
    return f"({_shape_number(point[0])},{_shape_number(point[1])})"


def _polygon_arc_value(
    end: tuple[float, float], center: tuple[float, float], direction: str
) -> str:
    return (
        f"({_shape_number(end[0])},{_shape_number(end[1])},"
        f"{_shape_number(center[0])},{_shape_number(center[1])},{direction})"
    )


def _polygon_shape_values_from_points(
    points: list[tuple[float, float]],
    pad_property: PadPropertyModel,
) -> list[str | float | int] | None:
    transformed_points = [_transform_pad_point(point, pad_property) for point in points]
    deduped: list[tuple[float, float]] = []
    for point in transformed_points:
        if deduped and _same_point(deduped[-1], point):
            continue
        deduped.append(point)
    if len(deduped) >= 2 and _same_point(deduped[0], deduped[-1]):
        deduped.pop()
    if len(deduped) < 3:
        return None
    vertices = [_polygon_vertex_value(point) for point in deduped]
    return [len(vertices), *vertices, "Y", "Y"]


def _polygon_shape_values_from_parts(
    parts: list[
        tuple[str, tuple[float, float], tuple[float, float] | None, str | None]
        | tuple[str, tuple[float, float]]
    ],
    pad_property: PadPropertyModel,
) -> list[str | float | int] | None:
    vertices: list[str] = []
    for part in parts:
        if part[0] == "point":
            vertices.append(
                _polygon_vertex_value(_transform_pad_point(part[1], pad_property))
            )
            continue
        if (
            part[0] == "arc"
            and len(part) >= 4
            and part[2] is not None
            and part[3] is not None
        ):
            end = _transform_pad_point(part[1], pad_property)
            center = _transform_pad_point(part[2], pad_property)
            vertices.append(_polygon_arc_value(end, center, str(part[3])))
    if len(vertices) < 3:
        return None
    return [len(vertices), *vertices, "Y", "Y"]


def _transform_pad_point(
    point: tuple[float, float], pad_property: PadPropertyModel
) -> tuple[float, float]:
    offset_x = _dimension_float_value(pad_property.offset_x) or 0.0
    offset_y = _dimension_float_value(pad_property.offset_y) or 0.0
    rotation = _dimension_float_value(pad_property.rotation) or 0.0
    cos_angle = math.cos(rotation)
    sin_angle = math.sin(rotation)
    x, y = point
    return (
        (x * cos_angle - y * sin_angle) + offset_x,
        (x * sin_angle + y * cos_angle) + offset_y,
    )


def _rotate_points(
    points: list[tuple[float, float]], angle: float
) -> list[tuple[float, float]]:
    if abs(angle) < 1e-15:
        return points
    cos_angle = math.cos(angle)
    sin_angle = math.sin(angle)
    return [
        (x * cos_angle - y * sin_angle, x * sin_angle + y * cos_angle)
        for x, y in points
    ]


def _shape_number(value: float) -> str:
    if abs(value) < 1e-15:
        value = 0.0
    return f"{value:.12g}"


def _upsert_shape(
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[str, ...]], str],
    *,
    kind: str,
    auroradb_type: str,
    values: list[str | float | int],
    name: str | None,
    source,
) -> str:
    key = (auroradb_type, tuple(_shape_key_value(value) for value in values))
    existing_id = shape_ids_by_key.get(key)
    if existing_id is not None:
        return existing_id
    shape_id = semantic_id("shape", f"{auroradb_type}_{len(shapes)}")
    shapes.append(
        SemanticShape(
            id=shape_id,
            name=name,
            kind=kind,
            auroradb_type=auroradb_type,
            values=values,
            source=source,
        )
    )
    shape_ids_by_key[key] = shape_id
    return shape_id


def _shape_key_value(value: str | float | int) -> str:
    return str(value).strip().casefold()


def _dimension(
    parameters: dict[str, Any], names: list[str]
) -> str | float | int | None:
    normalized_names = {_normalize_key(name) for name in names}
    for key, value in parameters.items():
        normalized_key = _normalize_key(key)
        if normalized_key in normalized_names:
            return _dimension_value(value)
    return None


def _dimension_float(parameters: dict[str, Any], names: list[str]) -> float | None:
    return _dimension_float_value(_dimension(parameters, names))


def _first_dimension(parameters: dict[str, Any]) -> str | float | int | None:
    values = _first_dimensions(parameters, 1)
    return values[0] if values else None


def _first_dimensions(
    parameters: dict[str, Any], count: int
) -> list[str | float | int]:
    values: list[str | float | int] = []
    for value in parameters.values():
        dimension = _dimension_value(value)
        if dimension is None:
            continue
        values.append(dimension)
        if len(values) >= count:
            break
    return values


def _first_dimension_floats(parameters: dict[str, Any], count: int) -> list[float]:
    values: list[float] = []
    for value in parameters.values():
        dimension = _dimension_float_value(value)
        if dimension is None:
            continue
        values.append(dimension)
        if len(values) >= count:
            break
    return values


def _dimension_value(value: Any) -> str | float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = text_value(value)
    if text in {None, ""}:
        return None
    return text


def _dimension_float_value(value: Any) -> float | None:
    number = _float_value(value)
    if number is not None:
        return number
    if isinstance(value, dict):
        for key in ("value", "display"):
            number = _dimension_float_value(value.get(key))
            if number is not None:
                return number
        return None
    text = text_value(value)
    if text in {None, ""}:
        return None
    match = re.match(
        r"^\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*([A-Za-zµμ]*)\s*$",
        str(text),
    )
    if not match:
        return None
    raw_number = float(match.group(1))
    unit = match.group(2).casefold().replace("µ", "u").replace("μ", "u")
    scale = {
        "": 1.0,
        "m": 1.0,
        "meter": 1.0,
        "meters": 1.0,
        "metre": 1.0,
        "metres": 1.0,
        "mm": 1e-3,
        "millimeter": 1e-3,
        "millimeters": 1e-3,
        "millimetre": 1e-3,
        "millimetres": 1e-3,
        "um": 1e-6,
        "micron": 1e-6,
        "microns": 1e-6,
        "micrometer": 1e-6,
        "micrometers": 1e-6,
        "micrometre": 1e-6,
        "micrometres": 1e-6,
        "mil": 25.4e-6,
        "mils": 25.4e-6,
        "in": 0.0254,
        "inch": 0.0254,
        "inches": 0.0254,
    }.get(unit)
    if scale is None:
        return None
    number = raw_number * scale
    return number if math.isfinite(number) else None


def _normalize_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _via_template_id_for_name(
    via_template_ids_by_name: dict[str, str], name: str | None
) -> str | None:
    if not name:
        return None
    return via_template_ids_by_name.get(name.casefold())


def _path_primitive(path: PathPrimitiveModel, index: int) -> SemanticPrimitive:
    net_id = semantic_id("net", path.net_name) if path.net_name else None
    component_id = (
        semantic_id("component", path.component_name) if path.component_name else None
    )
    return SemanticPrimitive.model_construct(
        id=semantic_id(
            "primitive", path.id or path.aedt_name or path.name, f"path_{index}"
        ),
        kind="trace",
        layer_name=path.layer_name,
        net_id=net_id,
        component_id=component_id,
        geometry=SemanticPrimitiveGeometry.model_validate(
            {
                "width": text_value(path.width),
                "length": path.length,
                "center_line": path.center_line,
                "bbox": path.bbox,
            }
        ),
        source=source_ref(
            "aedb", f"primitives.paths[{index}]", path.id or path.aedt_name or path.name
        ),
    )


def _polygon_primitive(
    polygon: PolygonPrimitiveModel,
    index: int,
    kind: str,
    path_prefix: str,
) -> SemanticPrimitive:
    net_id = semantic_id("net", polygon.net_name) if polygon.net_name else None
    component_id = (
        semantic_id("component", polygon.component_name)
        if polygon.component_name
        else None
    )
    return SemanticPrimitive.model_construct(
        id=semantic_id(
            "primitive",
            polygon.id or polygon.aedt_name or polygon.name,
            f"{kind}_{index}",
        ),
        kind=kind,
        layer_name=polygon.layer_name,
        net_id=net_id,
        component_id=component_id,
        geometry=SemanticPrimitiveGeometry.model_validate(
            {
                "raw_points": polygon.raw_points,
                "arc_count": len(polygon.arcs),
                "arcs": [_arc_geometry(arc) for arc in polygon.arcs],
                "bbox": polygon.bbox,
                "area": polygon.area,
                "is_void": polygon.is_void,
                "is_negative": polygon.is_negative,
                "has_voids": polygon.has_voids,
                "void_ids": list(polygon.void_ids or []),
                "voids": [_polygon_void_geometry(void) for void in polygon.voids],
            }
        ),
        source=source_ref(
            "aedb",
            f"{path_prefix}[{index}]",
            polygon.id or polygon.aedt_name or polygon.name,
        ),
    )


def _polygon_void_geometry(void) -> dict[str, Any]:
    return {
        "id": void.id,
        "raw_points": void.raw_points,
        "arc_count": len(void.arcs),
        "arcs": [_arc_geometry(arc) for arc in void.arcs],
        "bbox": void.bbox,
        "area": void.area,
    }


def _arc_geometry(arc) -> dict[str, Any]:
    return {
        "start": list(arc.start) if arc.start is not None else None,
        "end": list(arc.end) if arc.end is not None else None,
        "center": list(arc.center) if arc.center is not None else None,
        "mid_point": list(arc.mid_point) if arc.mid_point is not None else None,
        "height": arc.height,
        "radius": arc.radius,
        "length": arc.length,
        "is_segment": arc.is_segment,
        "is_point": arc.is_point,
        "is_ccw": arc.is_ccw,
    }
