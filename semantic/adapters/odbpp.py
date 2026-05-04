from __future__ import annotations

import math
import re
from typing import Any, TypeVar

from aurora_translator.sources.odbpp.models import (
    FeatureModel,
    LayerFeaturesModel,
    ODBLayout,
    SymbolDefinitionModel,
)
from aurora_translator.semantic.adapters.utils import (
    point_from_pair,
    role_from_layer_type,
    role_from_net_name,
    semantic_id,
    side_from_layer_name,
    source_ref,
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
    SemanticPoint,
    SemanticPrimitive,
    SemanticShape,
    SemanticSummary,
    SemanticVia,
    SemanticViaTemplate,
    SemanticViaTemplateGeometry,
    SemanticViaTemplateLayer,
)
from aurora_translator.semantic.passes import (
    build_connectivity_diagnostics,
    build_connectivity_edges,
)


T = TypeVar("T")
ODBPP_NO_NET_NAME = "NoNet"
_ODBPP_NO_NET_ALIASES = {"$none$", "$none", "none$", "nonet"}
_VIA_PAD_MATCH_TOLERANCE = 1e-3


def from_odbpp(payload: ODBLayout) -> SemanticBoard:
    layer_names_by_key = _matrix_layer_names_by_key(payload)
    drill_layer_spans = _drill_layer_spans(payload, layer_names_by_key)
    materials, layers = _semantic_stackup(payload)
    nets_by_id, _net_ids_by_name, feature_net_ids, pin_net_ids, feature_pin_keys = (
        _semantic_nets(
            payload,
            layer_names_by_key,
        )
    )
    symbol_definitions = {
        symbol.name.casefold(): symbol for symbol in payload.symbols or []
    }
    drill_tools_by_layer_symbol = _drill_tools_by_layer_symbol(payload)
    board_outline = _board_outline_from_odbpp(payload)

    shapes: list[SemanticShape] = []
    shape_ids_by_key: dict[tuple[str, tuple[str, ...]], str] = {}
    via_templates_by_id: dict[str, SemanticViaTemplate] = {}
    primitives: list[SemanticPrimitive] = []
    pads: list[SemanticPad] = []
    vias: list[SemanticVia] = []
    pad_features_by_pin_key: dict[tuple[str, int, int], list[dict[str, Any]]] = {}

    for layer_index, layer in enumerate(payload.layers or []):
        canonical_layer_name = _canonical_layer_name(
            layer.layer_name, layer_names_by_key
        )
        for feature_index, feature in enumerate(layer.features):
            net_id = feature_net_ids.get(
                (_layer_key(layer.layer_name), feature.feature_index)
            )
            symbol_name = _feature_symbol_name(layer, feature)
            shape_id = _shape_id_from_symbol(
                symbol_name,
                shapes,
                shape_ids_by_key,
                symbol_definitions=symbol_definitions,
                source_path=f"layers[{layer_index}].symbols[{feature.symbol}]",
            )

            feature_primitives = _primitives_from_feature(
                layer,
                feature,
                layer_index=layer_index,
                feature_index=feature_index,
                canonical_layer_name=canonical_layer_name,
                net_id=net_id,
                symbol_name=symbol_name,
                shape_id=shape_id,
            )
            primitives.extend(feature_primitives)
            if net_id:
                for primitive in feature_primitives:
                    nets_by_id[net_id].primitive_ids.append(primitive.id)

            if (
                feature.kind == "P"
                and feature.start is not None
                and net_id
                and shape_id
            ):
                if _is_drill_layer(layer.layer_name):
                    layer_span = drill_layer_spans.get(_layer_key(layer.layer_name), [])
                    tool_info = _drill_tool_info(
                        layer.layer_name,
                        symbol_name,
                        drill_tools_by_layer_symbol,
                    )
                    template_id = _upsert_via_template(
                        symbol_name,
                        shape_id,
                        via_templates_by_id,
                        layer_index,
                        layer.layer_name,
                        layer_span,
                        tool_info=tool_info,
                    )
                    via = SemanticVia(
                        id=semantic_id(
                            "via",
                            f"{layer.layer_name}:{feature.feature_index}",
                            f"{layer_index}_{feature_index}",
                        ),
                        name=feature.feature_id,
                        template_id=template_id,
                        net_id=net_id,
                        layer_names=layer_span,
                        position=point_from_pair(feature.start),
                        geometry={
                            "symbol": symbol_name,
                            "dcode": _token_at(feature.tokens, 5),
                            "orientation": _token_at(feature.tokens, 6),
                            "tool": tool_info,
                        },
                        source=source_ref(
                            "odbpp",
                            f"layers[{layer_index}].features[{feature_index}]",
                            feature.feature_id or feature.feature_index,
                        ),
                    )
                    vias.append(via)
                    nets_by_id[net_id].via_ids.append(via.id)
                else:
                    orientation = _feature_orientation(feature, symbol_name)
                    pad_info = {
                        "feature_key": (
                            _layer_key(canonical_layer_name),
                            feature.feature_index,
                        ),
                        "name": feature.feature_id or str(feature.feature_index),
                        "net_id": net_id,
                        "layer_name": canonical_layer_name,
                        "position": point_from_pair(feature.start),
                        "padstack_definition": symbol_name,
                        "geometry": {
                            "shape_id": shape_id,
                            "symbol": symbol_name,
                            "dcode": _token_at(feature.tokens, 5),
                            "orientation": orientation["text"],
                            "rotation": orientation["rotation"],
                            "polarity": feature.polarity,
                        },
                        "source": source_ref(
                            "odbpp",
                            f"layers[{layer_index}].features[{feature_index}]",
                            feature.feature_id or feature.feature_index,
                        ),
                    }
                    if orientation["mirror_x"]:
                        pad_info["geometry"]["mirror_x"] = True
                    pin_keys = feature_pin_keys.get(pad_info["feature_key"], [])
                    if pin_keys:
                        for pin_key in pin_keys:
                            pad_features_by_pin_key.setdefault(pin_key, []).append(
                                pad_info
                            )
                    else:
                        pad = SemanticPad(
                            id=semantic_id(
                                "pad",
                                f"{layer.layer_name}:{feature.feature_index}",
                                f"{layer_index}_{feature_index}",
                            ),
                            name=pad_info["name"],
                            net_id=net_id,
                            layer_name=canonical_layer_name,
                            position=pad_info["position"],
                            padstack_definition=symbol_name,
                            geometry=pad_info["geometry"],
                            source=pad_info["source"],
                        )
                        pads.append(pad)
                        nets_by_id[net_id].pad_ids.append(pad.id)
            elif (
                feature.kind == "L"
                and feature.start is not None
                and feature.end is not None
                and net_id
            ):
                if _is_drill_layer(layer.layer_name):
                    slot_shape_id, slot_geometry = _shape_id_from_drill_slot(
                        symbol_name,
                        feature,
                        shapes,
                        shape_ids_by_key,
                        source_path=f"layers[{layer_index}].features[{feature_index}]",
                    )
                    if slot_shape_id is not None and slot_geometry is not None:
                        layer_span = drill_layer_spans.get(
                            _layer_key(layer.layer_name), []
                        )
                        tool_info = _drill_tool_info(
                            layer.layer_name,
                            symbol_name,
                            drill_tools_by_layer_symbol,
                        )
                        template_symbol = _slot_via_template_symbol(
                            symbol_name, slot_geometry
                        )
                        template_id = _upsert_via_template(
                            template_symbol,
                            slot_shape_id,
                            via_templates_by_id,
                            layer_index,
                            layer.layer_name,
                            layer_span,
                            tool_info=tool_info,
                        )
                        via = SemanticVia(
                            id=semantic_id(
                                "via",
                                f"{layer.layer_name}:{feature.feature_index}",
                                f"{layer_index}_{feature_index}",
                            ),
                            name=feature.feature_id,
                            template_id=template_id,
                            net_id=net_id,
                            layer_names=layer_span,
                            position=slot_geometry["center"],
                            geometry={
                                "symbol": symbol_name,
                                "dcode": _token_at(feature.tokens, 6),
                                "orientation": _token_at(feature.tokens, 7),
                                "tool": tool_info,
                                "slot": True,
                                "slot_width": slot_geometry["width"],
                                "slot_centerline_length": slot_geometry[
                                    "centerline_length"
                                ],
                                "slot_total_length": slot_geometry["total_length"],
                                "rotation": slot_geometry["rotation"],
                            },
                            source=source_ref(
                                "odbpp",
                                f"layers[{layer_index}].features[{feature_index}]",
                                feature.feature_id or feature.feature_index,
                            ),
                        )
                        vias.append(via)
                        nets_by_id[net_id].via_ids.append(via.id)

    _promote_no_net_routable_primitives(nets_by_id, primitives, layers)

    components, footprints_by_id, pins = _semantic_components(
        payload,
        layer_names_by_key=layer_names_by_key,
        pin_net_ids=pin_net_ids,
        pad_features_by_pin_key=pad_features_by_pin_key,
        nets_by_id=nets_by_id,
        pads=pads,
        shapes=shapes,
        shape_ids_by_key=shape_ids_by_key,
    )
    _refine_via_templates_from_pads(via_templates_by_id, vias, pads, primitives, shapes)
    _dedupe_relationship_ids(
        nets=nets_by_id.values(),
        footprints=footprints_by_id.values(),
        components=components,
        pins=pins,
    )

    diagnostics = [
        SemanticDiagnostic(
            severity="warning",
            code="odbpp.source_diagnostic",
            message=message,
            source=source_ref("odbpp", "diagnostics"),
        )
        for message in payload.diagnostics
    ]

    board = SemanticBoard(
        metadata=SemanticMetadata(
            source_format="odbpp",
            source=payload.metadata.source,
            source_step=payload.metadata.selected_step,
            source_parser_version=payload.metadata.parser_version,
            source_schema_version=payload.metadata.output_schema_version,
        ),
        units=_selected_units(payload),
        summary=SemanticSummary(),
        layers=layers,
        materials=materials,
        shapes=shapes,
        via_templates=list(via_templates_by_id.values()),
        nets=list(nets_by_id.values()),
        components=components,
        footprints=list(footprints_by_id.values()),
        pins=pins,
        pads=pads,
        vias=vias,
        primitives=primitives,
        diagnostics=diagnostics,
        board_outline=board_outline,
    )
    board = board.model_copy(update={"connectivity": build_connectivity_edges(board)})
    board = board.model_copy(
        update={
            "diagnostics": [*board.diagnostics, *build_connectivity_diagnostics(board)]
        }
    )
    return board.with_computed_summary()


def _semantic_stackup(
    payload: ODBLayout,
) -> tuple[list[SemanticMaterial], list[SemanticLayer]]:
    units = _selected_units(payload)
    layer_attributes_by_key = {
        _layer_key(layer.layer_name): layer.layer_attributes
        for layer in payload.layers or []
    }
    materials: list[SemanticMaterial] = []
    material_ids_by_name: dict[str, str] = {}
    layers: list[SemanticLayer] = []
    for index, row in enumerate(payload.matrix.rows if payload.matrix else []):
        if not row.name:
            continue
        attrs = layer_attributes_by_key.get(_layer_key(row.name), {})
        role = role_from_layer_type(
            row.layer_type, is_via_layer=_is_drill_layer(row.name)
        )
        material_name = (
            _odbpp_layer_material_name(row.name, role)
            if role in {"signal", "plane", "dielectric", "soldermask"}
            else None
        )
        material_id = (
            _ensure_odbpp_material(
                materials,
                material_ids_by_name,
                material_name,
                role=role,
                attrs=attrs,
                source_path=f"layers[{row.name}].attrlist",
            )
            if material_name
            else None
        )
        layers.append(
            SemanticLayer(
                id=semantic_id("layer", row.name, index),
                name=row.name or f"layer_{index}",
                layer_type=row.layer_type,
                role=role,
                side=side_from_layer_name(row.side or row.name),
                order_index=row.row if row.row is not None else index,
                material=material_name,
                material_id=material_id,
                thickness=_odbpp_layer_thickness(row.layer_type, attrs, units),
                source=source_ref(
                    "odbpp", f"matrix.rows[{index}]", row.name or row.row
                ),
            )
        )
    return materials, layers


def _odbpp_layer_material_name(layer_name: str | None, role: str | None) -> str:
    if role == "dielectric":
        return "ODBPP_DIELECTRIC"
    if role in {"signal", "plane"}:
        return "ODBPP_COPPER"
    if role == "soldermask":
        return "ODBPP_SOLDERMASK"
    return f"ODBPP_{_standard_material_token(layer_name or role or 'MATERIAL')}"


def _ensure_odbpp_material(
    materials: list[SemanticMaterial],
    material_ids_by_name: dict[str, str],
    name: str,
    *,
    role: str | None,
    attrs: dict[str, str],
    source_path: str,
) -> str:
    key = name.casefold()
    if key in material_ids_by_name:
        return material_ids_by_name[key]
    material_role = (
        "dielectric"
        if role == "dielectric"
        else "metal"
        if role in {"signal", "plane"}
        else "unknown"
    )
    material = SemanticMaterial(
        id=semantic_id("material", name, len(materials)),
        name=name,
        role=material_role,
        conductivity=_odbpp_conductivity(role),
        permittivity=_positive_number(attrs.get(".dielectric_constant")),
        dielectric_loss_tangent=_positive_number(attrs.get(".loss_tangent")),
        source=source_ref("odbpp", source_path, name),
    )
    materials.append(material)
    material_ids_by_name[key] = material.id
    return material.id


def _odbpp_conductivity(role: str | None) -> float | None:
    return 58_000_000.0 if role in {"signal", "plane"} else None


def _odbpp_layer_thickness(
    layer_type: str | None, attrs: dict[str, str], units: str | None
) -> float | None:
    layer_type_text = (layer_type or "").casefold()
    if "dielectric" in layer_type_text:
        return _positive_number(attrs.get(".layer_dielectric"))
    if (
        "signal" in layer_type_text
        or "power" in layer_type_text
        or "plane" in layer_type_text
    ):
        copper_weight_um = _positive_number(attrs.get(".copper_weight"))
        if copper_weight_um is None:
            return None
        # ODB++ attrlists commonly store copper_weight in micrometers even when layer units are MM.
        return (
            copper_weight_um / 1000.0
            if (units or "").upper() == "MM"
            else copper_weight_um
        )
    return None


def _positive_number(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _standard_material_token(value: str) -> str:
    return (
        re.sub(r"[^A-Za-z0-9_]+", "_", value.strip().upper()).strip("_") or "MATERIAL"
    )


def _semantic_nets(
    payload: ODBLayout,
    layer_names_by_key: dict[str, str],
) -> tuple[
    dict[str, SemanticNet],
    dict[str, str],
    dict[tuple[str, int], str],
    dict[tuple[str, int, int], str],
    dict[tuple[str, int], list[tuple[str, int, int]]],
]:
    nets_by_id: dict[str, SemanticNet] = {}
    net_ids_by_name: dict[str, str] = {}
    feature_net_ids: dict[tuple[str, int], str] = {}
    pin_net_ids: dict[tuple[str, int, int], str] = {}
    feature_pin_keys: dict[tuple[str, int], list[tuple[str, int, int]]] = {}

    for index, net in enumerate(payload.nets or []):
        net_name = ODBPP_NO_NET_NAME if _is_no_net_name(net.name) else net.name
        net_id = semantic_id("net", net_name, index)
        if net_id not in nets_by_id:
            nets_by_id[net_id] = SemanticNet(
                id=net_id,
                name=net_name,
                role="no_net"
                if _is_no_net_name(net.name)
                else role_from_net_name(net_name),
                source=source_ref("odbpp", f"nets[{index}]", net.name),
            )
        net_ids_by_name[net.name.casefold()] = net_id

        for ref in net.feature_refs:
            if ref.feature_index is None or not ref.layer_name:
                continue
            layer_name = _canonical_layer_name(ref.layer_name, layer_names_by_key)
            feature_key = (_layer_key(layer_name), ref.feature_index)
            feature_net_ids[feature_key] = net_id
            if (
                ref.pin_side
                and ref.net_component_index is not None
                and ref.net_pin_index is not None
            ):
                pin_key = (ref.pin_side, ref.net_component_index, ref.net_pin_index)
                feature_pin_keys.setdefault(feature_key, []).append(pin_key)
        for ref in net.pin_refs:
            if ref.net_component_index is None or ref.net_pin_index is None:
                continue
            side = ref.side or ""
            pin_net_ids[(side, ref.net_component_index, ref.net_pin_index)] = net_id

    for pin_keys in feature_pin_keys.values():
        dedupe_in_place(pin_keys)

    return nets_by_id, net_ids_by_name, feature_net_ids, pin_net_ids, feature_pin_keys


def _is_no_net_name(name: str | None) -> bool:
    return (name or "").strip().casefold() in _ODBPP_NO_NET_ALIASES


def _promote_no_net_routable_primitives(
    nets_by_id: dict[str, SemanticNet],
    primitives: list[SemanticPrimitive],
    layers: list[SemanticLayer],
) -> None:
    layer_roles = {
        _layer_key(layer.name): (layer.role or "").casefold() for layer in layers
    }
    no_net_id = semantic_id("net", ODBPP_NO_NET_NAME)
    no_net: SemanticNet | None = nets_by_id.get(no_net_id)

    for primitive in primitives:
        if not _should_promote_to_no_net(primitive, layer_roles):
            continue
        if no_net is None:
            no_net = SemanticNet(
                id=no_net_id,
                name=ODBPP_NO_NET_NAME,
                role="no_net",
                source=source_ref(
                    "odbpp", "semantic.no_net_routable_primitives", ODBPP_NO_NET_NAME
                ),
            )
            nets_by_id[no_net_id] = no_net
        primitive.net_id = no_net_id
        no_net.primitive_ids.append(primitive.id)


def _should_promote_to_no_net(
    primitive: SemanticPrimitive, layer_roles: dict[str, str]
) -> bool:
    if primitive.net_id:
        return False
    if primitive.kind.casefold() not in {"trace", "arc", "polygon", "zone"}:
        return False
    if layer_roles.get(_layer_key(primitive.layer_name)) not in {"signal", "plane"}:
        return False
    geometry = primitive.geometry
    if _is_negative_polarity(geometry.get("polarity")):
        return False
    if geometry.get("is_negative") is True or geometry.get("is_void") is True:
        return False
    return True


def _semantic_components(
    payload: ODBLayout,
    *,
    layer_names_by_key: dict[str, str],
    pin_net_ids: dict[tuple[str, int, int], str],
    pad_features_by_pin_key: dict[tuple[str, int, int], list[dict[str, Any]]],
    nets_by_id: dict[str, SemanticNet],
    pads: list[SemanticPad],
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[str, ...]], str],
) -> tuple[list[SemanticComponent], dict[str, SemanticFootprint], list[SemanticPin]]:
    components: list[SemanticComponent] = []
    footprints_by_id: dict[str, SemanticFootprint] = {}
    pins: list[SemanticPin] = []
    packages_by_index = {
        package.package_index: package
        for package in payload.packages or []
        if package.package_index is not None
    }
    for package_index, package in enumerate(payload.packages or []):
        footprint_name = _package_name(package) or (
            f"pkg_{package.package_index}"
            if package.package_index is not None
            else f"pkg_source_{package_index}"
        )
        footprint_id = semantic_id("footprint", footprint_name)
        if footprint_id in footprints_by_id:
            continue
        footprints_by_id[footprint_id] = SemanticFootprint(
            id=footprint_id,
            name=footprint_name,
            attributes=dict(package.properties),
            geometry=_footprint_geometry_from_package(package),
            source=source_ref(
                "odbpp",
                f"packages[{package_index}]",
                package.package_index or footprint_name,
            ),
        )

    for index, component in enumerate(payload.components or []):
        package = packages_by_index.get(component.package_index)
        footprint_id = None
        footprint_name = (
            component.package_name
            or _package_name(package)
            or (
                f"pkg_{component.package_index}"
                if component.package_index is not None
                else None
            )
        )
        if footprint_name:
            footprint_id = semantic_id("footprint", footprint_name)
            footprint_geometry = _footprint_geometry_from_package(package)
            if footprint_id not in footprints_by_id:
                footprints_by_id[footprint_id] = SemanticFootprint(
                    id=footprint_id,
                    name=footprint_name,
                    part_name=component.part_name,
                    attributes=dict(package.properties) if package is not None else {},
                    geometry=footprint_geometry,
                    source=source_ref(
                        "odbpp", f"components[{index}].package_name", footprint_name
                    ),
                )
            elif (
                component.part_name and footprints_by_id[footprint_id].part_name is None
            ):
                footprints_by_id[footprint_id].part_name = component.part_name
            if package is not None and not footprints_by_id[footprint_id].attributes:
                footprints_by_id[footprint_id].attributes = dict(package.properties)
            if footprint_geometry and not footprints_by_id[footprint_id].geometry:
                footprints_by_id[footprint_id].geometry = footprint_geometry

        side = side_from_layer_name(component.layer_name)
        pin_ids: list[str] = []
        component_pad_ids: list[str] = []
        component_pad_layers: list[str] = []
        has_unresolved_pin_pad_layer = False
        component_id = semantic_id("component", component.refdes, index)
        for pin_index, pin in enumerate(component.pins):
            side_key = side or ""
            net_id = None
            if component.component_index is not None and pin.pin_index is not None:
                net_id = pin_net_ids.get(
                    (side_key, component.component_index, pin.pin_index)
                )
            if (
                net_id is None
                and pin.net_component_index is not None
                and pin.net_pin_index is not None
            ):
                net_id = pin_net_ids.get(
                    (side_key, pin.net_component_index, pin.net_pin_index)
                )
            pin_id = semantic_id(
                "pin",
                f"{component.refdes or index}:{pin.name or pin.pin_index}",
                f"{index}_{pin_index}",
            )
            pin_pad_ids: list[str] = []
            pad_infos = _pad_infos_for_pin(
                side_key,
                component,
                pin,
                pad_features_by_pin_key,
            )
            if not pad_infos and package is not None:
                pad_infos = _package_pad_infos_for_pin(
                    package,
                    component,
                    pin,
                    side_key,
                    net_id=net_id,
                    shapes=shapes,
                    shape_ids_by_key=shape_ids_by_key,
                    component_index=index,
                    pin_index=pin_index,
                    layer_names_by_key=layer_names_by_key,
                )
            if net_id is None:
                net_id = next(
                    (info.get("net_id") for info in pad_infos if info.get("net_id")),
                    None,
                )
            pin_layer_name = _common_pad_layer_name(pad_infos, layer_names_by_key)
            if pin_layer_name:
                component_pad_layers.append(pin_layer_name)
            elif pad_infos:
                has_unresolved_pin_pad_layer = True
            else:
                has_unresolved_pin_pad_layer = True
            for pad_info_index, pad_info in enumerate(pad_infos):
                pad_net_id = pad_info.get("net_id") or net_id
                pad_id = semantic_id(
                    "pad",
                    f"{component.refdes or index}:{pin.name or pin.pin_index}:{pad_info['feature_key']}",
                    f"{index}_{pin_index}_{pad_info_index}",
                )
                pin_pad_ids.append(pad_id)
                component_pad_ids.append(pad_id)
                if footprint_id and footprint_id in footprints_by_id:
                    footprints_by_id[footprint_id].pad_ids.append(pad_id)
                if pad_net_id:
                    nets_by_id[pad_net_id].pad_ids.append(pad_id)
                pads.append(
                    SemanticPad(
                        id=pad_id,
                        name=pin.name or pad_info.get("name"),
                        footprint_id=footprint_id,
                        component_id=component_id,
                        pin_id=pin_id,
                        net_id=pad_net_id,
                        layer_name=pad_info.get("layer_name"),
                        position=pad_info.get("position"),
                        padstack_definition=pad_info.get("padstack_definition"),
                        geometry=pad_info.get("geometry") or {},
                        source=pad_info.get("source"),
                    )
                )
            pin_ids.append(pin_id)
            if net_id:
                nets_by_id[net_id].pin_ids.append(pin_id)
            pins.append(
                SemanticPin(
                    id=pin_id,
                    name=pin.name
                    or (str(pin.pin_index) if pin.pin_index is not None else None),
                    component_id=component_id,
                    net_id=net_id,
                    pad_ids=pin_pad_ids,
                    layer_name=pin_layer_name
                    or _side_pin_layer_name(side, layer_names_by_key),
                    position=point_from_pair(pin.position),
                    source=source_ref(
                        "odbpp",
                        f"components[{index}].pins[{pin_index}]",
                        pin.name or pin.pin_index,
                    ),
                )
            )

        component_layer_name = None
        if not has_unresolved_pin_pad_layer:
            component_layer_name = _common_layer_name(component_pad_layers)

        components.append(
            SemanticComponent(
                id=component_id,
                refdes=component.refdes,
                name=component.refdes,
                part_name=component.part_name or component.package_name,
                package_name=footprint_name,
                footprint_id=footprint_id,
                layer_name=component_layer_name or component.layer_name,
                side=side,
                value=component.properties.get("VALUE"),
                location=point_from_pair(component.location),
                rotation=_degrees_to_radians(component.rotation),
                attributes=_component_attributes(component, package),
                pin_ids=pin_ids,
                pad_ids=component_pad_ids,
                source=source_ref(
                    "odbpp",
                    f"components[{index}]",
                    component.refdes or component.line_number,
                ),
            )
        )

    return components, footprints_by_id, pins


def _side_pin_layer_name(
    side: str | None, layer_names_by_key: dict[str, str]
) -> str | None:
    if side not in {"top", "bottom"}:
        return None
    return _canonical_layer_name(
        "TOP" if side == "top" else "BOTTOM", layer_names_by_key
    )


def _common_pad_layer_name(
    pad_infos: list[dict[str, Any]],
    layer_names_by_key: dict[str, str],
) -> str | None:
    layer_names: list[str] = []
    for pad_info in pad_infos:
        layer_name = _canonical_layer_name(
            pad_info.get("layer_name"), layer_names_by_key
        )
        if not layer_name:
            return None
        layer_names.append(layer_name)
    return _common_layer_name(layer_names)


def _common_layer_name(layer_names: list[str]) -> str | None:
    if not layer_names:
        return None
    first = layer_names[0]
    first_key = _layer_key(first)
    if not first_key:
        return None
    for layer_name in layer_names[1:]:
        if _layer_key(layer_name) != first_key:
            return None
    return first


def _pad_infos_for_pin(
    side_key: str,
    component: Any,
    pin: Any,
    pad_features_by_pin_key: dict[tuple[str, int, int], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    primary_keys: list[tuple[str, int, int]] = []
    if component.component_index is not None and pin.pin_index is not None:
        primary_keys.append((side_key, component.component_index, pin.pin_index))

    result = _pad_infos_for_keys(primary_keys, pad_features_by_pin_key)
    if result:
        return result

    fallback_keys: list[tuple[str, int, int]] = []
    if pin.net_component_index is not None and pin.net_pin_index is not None:
        fallback_keys.append((side_key, pin.net_component_index, pin.net_pin_index))
    return _pad_infos_for_keys(fallback_keys, pad_features_by_pin_key)


def _pad_infos_for_keys(
    candidate_keys: list[tuple[str, int, int]],
    pad_features_by_pin_key: dict[tuple[str, int, int], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for key in candidate_keys:
        for pad_info in pad_features_by_pin_key.get(key, []):
            feature_key = pad_info.get("feature_key")
            if not isinstance(feature_key, tuple) or len(feature_key) != 2:
                continue
            if feature_key in seen:
                continue
            seen.add(feature_key)
            result.append(pad_info)
    return result


def _package_name(package: Any | None) -> str | None:
    if package is None:
        return None
    return package.properties.get("PACKAGE_NAME") or package.name


def _component_attributes(component: Any, package: Any | None) -> dict[str, str]:
    attributes = {
        str(key): str(value) for key, value in dict(component.properties).items()
    }
    if component.component_index is not None:
        attributes.setdefault("ODBPP_COMPONENT_INDEX", str(component.component_index))
    if component.package_index is not None:
        attributes.setdefault("ODBPP_PACKAGE_INDEX", str(component.package_index))
    if component.layer_name not in {None, ""}:
        attributes.setdefault("ODBPP_COMPONENT_LAYER", str(component.layer_name))
    if component.mirror not in {None, ""}:
        attributes.setdefault("ODBPP_MIRROR", str(component.mirror))
    if package is not None:
        package_name = _package_name(package)
        if package_name:
            attributes.setdefault("PACKAGE_NAME", package_name)
        for key, value in dict(package.properties).items():
            attributes.setdefault(f"PACKAGE_{key}", str(value))
    return attributes


def _refine_via_templates_from_pads(
    via_templates_by_id: dict[str, SemanticViaTemplate],
    vias: list[SemanticVia],
    pads: list[SemanticPad],
    primitives: list[SemanticPrimitive],
    shapes: list[SemanticShape],
) -> None:
    shapes_by_id = {shape.id: shape for shape in shapes}
    pads_by_bucket: dict[tuple[str, str, int, int], list[SemanticPad]] = {}
    antipads_by_bucket: dict[tuple[str, str, int, int], list[SemanticPad]] = {}
    for pad in pads:
        if not pad.net_id or pad.position is None:
            continue
        shape_id = pad.geometry.get("shape_id")
        if not shape_id:
            continue
        target = (
            antipads_by_bucket
            if _is_negative_polarity(pad.geometry.get("polarity"))
            else pads_by_bucket
        )
        bucket_x, bucket_y = _coord_bucket(pad.position)
        target.setdefault(
            (pad.net_id, _layer_key(pad.layer_name), bucket_x, bucket_y), []
        ).append(pad)

    negative_primitives_by_bucket: dict[
        tuple[str, int, int], list[SemanticPrimitive]
    ] = {}
    for primitive in primitives:
        if primitive.kind != "pad" or primitive.net_id or primitive.component_id:
            continue
        shape_id = primitive.geometry.get("shape_id")
        if not shape_id or not _is_negative_polarity(
            primitive.geometry.get("polarity")
        ):
            continue
        start = _point_from_geometry(primitive.geometry.get("start"))
        if start is None:
            continue
        bucket_x, bucket_y = _coord_bucket(start)
        negative_primitives_by_bucket.setdefault(
            (_layer_key(primitive.layer_name), bucket_x, bucket_y), []
        ).append(primitive)

    refined_by_signature: dict[
        tuple[
            str, tuple[tuple[str, str | None, str | None, str | None, str | None], ...]
        ],
        str,
    ] = {}
    for via in vias:
        if not via.template_id or not via.net_id or via.position is None:
            continue
        base_template = via_templates_by_id.get(via.template_id)
        if base_template is None:
            continue
        via_rotation = _parse_float(via.geometry.get("rotation"))
        matched_by_layer: dict[str, dict[str, Any]] = {}
        matched_antipads_by_layer: dict[str, dict[str, Any]] = {}
        for layer_name in via.layer_names:
            layer_key = _layer_key(layer_name)
            candidates = _nearby_pad_candidates(
                pads_by_bucket, via.net_id, via.position, layer_key
            )
            match = _candidate_pad_match(candidates, via_rotation, shapes_by_id)
            if match:
                matched_by_layer[layer_key] = match

            antipad_candidates = _nearby_pad_candidates(
                antipads_by_bucket, via.net_id, via.position, layer_key
            )
            antipad_match = _candidate_pad_match(
                antipad_candidates, via_rotation, shapes_by_id
            )
            if antipad_match is None:
                primitive_candidates = _nearby_primitive_candidates(
                    negative_primitives_by_bucket, via.position, layer_key
                )
                antipad_match = _candidate_primitive_match(
                    primitive_candidates, via_rotation, shapes_by_id
                )
            if antipad_match:
                matched_antipads_by_layer[layer_key] = antipad_match
        if not matched_by_layer and not matched_antipads_by_layer:
            continue

        layer_signature = tuple(
            (
                layer_pad.layer_name,
                _matched_shape_id(
                    matched_by_layer, layer_pad.layer_name, layer_pad.pad_shape_id
                ),
                _matched_rotation_key(matched_by_layer, layer_pad.layer_name),
                _matched_shape_id(
                    matched_antipads_by_layer,
                    layer_pad.layer_name,
                    layer_pad.antipad_shape_id,
                ),
                _matched_rotation_key(matched_antipads_by_layer, layer_pad.layer_name),
            )
            for layer_pad in base_template.layer_pads
        )
        signature = (base_template.id, layer_signature)
        refined_id = refined_by_signature.get(signature)
        if refined_id is None:
            signature_text = "|".join(
                f"{name}:{pad_shape_id or ''}:{pad_rotation or ''}:{antipad_shape_id or ''}:{antipad_rotation or ''}"
                for name, pad_shape_id, pad_rotation, antipad_shape_id, antipad_rotation in layer_signature
            )
            layer_pad_rotations = _layer_pad_rotations_from_matches(
                base_template.layer_pads,
                matched_by_layer,
                matched_antipads_by_layer,
            )
            geometry = {
                **base_template.geometry,
                "matched_signal_layer_count": len(matched_by_layer),
                "matched_antipad_layer_count": len(matched_antipads_by_layer),
            }
            if layer_pad_rotations:
                geometry["layer_pad_rotations"] = layer_pad_rotations
            if matched_by_layer:
                geometry["layer_pad_source"] = "matched_signal_layer_pads"
            if matched_antipads_by_layer:
                geometry["antipad_source"] = "matched_negative_pad_primitives"
            refined_id = semantic_id(
                "via_template", f"{base_template.name}:{signature_text}"
            )
            refined_by_signature[signature] = refined_id
            via_templates_by_id[refined_id] = base_template.model_copy(
                deep=True,
                update={
                    "id": refined_id,
                    "name": f"{base_template.name}:matched_pads",
                    "layer_pads": [
                        SemanticViaTemplateLayer(
                            layer_name=layer_pad.layer_name,
                            pad_shape_id=_matched_shape_id(
                                matched_by_layer,
                                layer_pad.layer_name,
                                layer_pad.pad_shape_id,
                            ),
                            antipad_shape_id=_matched_shape_id(
                                matched_antipads_by_layer,
                                layer_pad.layer_name,
                                layer_pad.antipad_shape_id,
                            ),
                            thermal_shape_id=layer_pad.thermal_shape_id,
                        )
                        for layer_pad in base_template.layer_pads
                    ],
                    "geometry": SemanticViaTemplateGeometry.model_validate(geometry),
                },
            )
        via.template_id = refined_id
        via.geometry["template_refined_from"] = base_template.id
        via.geometry["matched_signal_layer_count"] = len(matched_by_layer)
        via.geometry["matched_antipad_layer_count"] = len(matched_antipads_by_layer)

    used_template_ids = {via.template_id for via in vias if via.template_id}
    for template_id in list(via_templates_by_id):
        if template_id not in used_template_ids:
            del via_templates_by_id[template_id]


def _coord_bucket(point: SemanticPoint) -> tuple[int, int]:
    return (
        math.floor(float(point.x) / _VIA_PAD_MATCH_TOLERANCE),
        math.floor(float(point.y) / _VIA_PAD_MATCH_TOLERANCE),
    )


def _nearby_pad_candidates(
    index: dict[tuple[str, str, int, int], list[SemanticPad]],
    net_id: str,
    position: SemanticPoint,
    layer_key: str,
) -> list[tuple[SemanticPad, float]]:
    bucket_x, bucket_y = _coord_bucket(position)
    tolerance_sq = _VIA_PAD_MATCH_TOLERANCE * _VIA_PAD_MATCH_TOLERANCE
    result: list[tuple[SemanticPad, float]] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for candidate in index.get(
                (net_id, layer_key, bucket_x + dx, bucket_y + dy), []
            ):
                if candidate.position is None:
                    continue
                distance_sq = _distance_sq(position, candidate.position)
                if distance_sq <= tolerance_sq:
                    result.append((candidate, distance_sq))
    return result


def _nearby_primitive_candidates(
    index: dict[tuple[str, int, int], list[SemanticPrimitive]],
    position: SemanticPoint,
    layer_key: str,
) -> list[tuple[SemanticPrimitive, float]]:
    bucket_x, bucket_y = _coord_bucket(position)
    tolerance_sq = _VIA_PAD_MATCH_TOLERANCE * _VIA_PAD_MATCH_TOLERANCE
    result: list[tuple[SemanticPrimitive, float]] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for candidate in index.get((layer_key, bucket_x + dx, bucket_y + dy), []):
                start = _point_from_geometry(candidate.geometry.get("start"))
                if start is None:
                    continue
                distance_sq = _distance_sq(position, start)
                if distance_sq <= tolerance_sq:
                    result.append((candidate, distance_sq))
    return result


def _candidate_pad_match(
    candidates: list[tuple[SemanticPad, float]],
    via_rotation: float | None,
    shapes_by_id: dict[str, SemanticShape],
) -> dict[str, Any] | None:
    best: tuple[tuple[float, int, int], dict[str, Any]] | None = None
    for index, (candidate, distance_sq) in enumerate(candidates):
        shape_id = candidate.geometry.get("shape_id")
        if not shape_id:
            continue
        shape = shapes_by_id.get(str(shape_id))
        score = (distance_sq, 0 if candidate.component_id else 1, index)
        match = {
            "shape_id": str(shape_id),
            "rotation": _relative_rotation(
                candidate.geometry.get("rotation"),
                via_rotation,
                half_turn_symmetric=_shape_is_half_turn_symmetric(shape),
            ),
            "component_id": candidate.component_id,
            "distance": math.sqrt(distance_sq),
        }
        if best is None or score < best[0]:
            best = (score, match)
    return best[1] if best is not None else None


def _candidate_primitive_match(
    candidates: list[tuple[SemanticPrimitive, float]],
    via_rotation: float | None,
    shapes_by_id: dict[str, SemanticShape],
) -> dict[str, Any] | None:
    best: tuple[tuple[float, int], dict[str, Any]] | None = None
    for index, (candidate, distance_sq) in enumerate(candidates):
        shape_id = candidate.geometry.get("shape_id")
        if not shape_id:
            continue
        shape = shapes_by_id.get(str(shape_id))
        score = (distance_sq, index)
        match = {
            "shape_id": str(shape_id),
            "rotation": _relative_rotation(
                candidate.geometry.get("rotation"),
                via_rotation,
                half_turn_symmetric=_shape_is_half_turn_symmetric(shape),
            ),
            "distance": math.sqrt(distance_sq),
        }
        if best is None or score < best[0]:
            best = (score, match)
    return best[1] if best is not None else None


def _matched_shape_id(
    matches: dict[str, dict[str, Any]], layer_name: str, fallback: str | None
) -> str | None:
    match = matches.get(_layer_key(layer_name))
    return str(match["shape_id"]) if match and match.get("shape_id") else fallback


def _matched_rotation_key(
    matches: dict[str, dict[str, Any]], layer_name: str
) -> str | None:
    match = matches.get(_layer_key(layer_name))
    rotation = match.get("rotation") if match else None
    return _rotation_key(rotation)


def _layer_pad_rotations_from_matches(
    layer_pads: list[SemanticViaTemplateLayer],
    pad_matches: dict[str, dict[str, Any]],
    antipad_matches: dict[str, dict[str, Any]],
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for layer_pad in layer_pads:
        layer_key = _layer_key(layer_pad.layer_name)
        pad_rotation = pad_matches.get(layer_key, {}).get("rotation")
        antipad_rotation = antipad_matches.get(layer_key, {}).get("rotation")
        values: dict[str, float] = {}
        if pad_rotation is not None:
            values["pad"] = float(pad_rotation)
        if antipad_rotation is not None:
            values["antipad"] = float(antipad_rotation)
        if values:
            result[layer_pad.layer_name] = values
    return result


def _relative_rotation(
    rotation: Any,
    reference_rotation: float | None,
    *,
    half_turn_symmetric: bool = False,
) -> float | None:
    rotation_value = _parse_float(rotation)
    if rotation_value is None:
        return None
    relative = rotation_value - (reference_rotation or 0.0)
    if half_turn_symmetric:
        return _normalize_symmetric_radians(relative)
    return _normalize_radians(relative)


def _shape_is_half_turn_symmetric(shape: SemanticShape | None) -> bool:
    if shape is None:
        return False
    geometry_type = (
        str(shape.auroradb_type or shape.kind or "").replace("_", "").casefold()
    )
    if geometry_type in {"circle", "rectangle", "roundedrectangle"}:
        return _shape_center_is_origin(shape.values)
    if geometry_type == "polygon":
        return _polygon_shape_is_half_turn_symmetric(shape.values)
    return False


def _shape_center_is_origin(values: list[Any]) -> bool:
    if len(values) < 2:
        return True
    x = _parse_float(values[0])
    y = _parse_float(values[1])
    return x is not None and y is not None and abs(x) <= 1e-12 and abs(y) <= 1e-12


def _polygon_shape_is_half_turn_symmetric(values: list[Any]) -> bool:
    if not values:
        return False
    count_value = _parse_float(values[0])
    count = (
        int(round(count_value))
        if count_value is not None
        and count_value >= 0
        and abs(count_value - round(count_value)) <= 1e-12
        else None
    )
    if count is not None and len(values) < 1 + count:
        return False
    coordinate_values = values[1 : 1 + count] if count is not None else values
    vertices: list[tuple[float, float]] = []
    for value in coordinate_values:
        point = _shape_vertex_point(value)
        if point is None:
            return False
        vertices.append(point)
    if not vertices:
        return False
    return all(
        any(
            abs(x + candidate_x) <= 1e-9 and abs(y + candidate_y) <= 1e-9
            for candidate_x, candidate_y in vertices
        )
        for x, y in vertices
    )


def _shape_vertex_point(value: Any) -> tuple[float, float] | None:
    text = str(value).strip()
    if not text.startswith("(") or not text.endswith(")"):
        return None
    parts = [part.strip() for part in text[1:-1].split(",")]
    if len(parts) != 2:
        return None
    x = _parse_float(parts[0])
    y = _parse_float(parts[1])
    if x is None or y is None:
        return None
    return x, y


def _rotation_key(rotation: Any) -> str | None:
    rotation_value = _parse_float(rotation)
    if rotation_value is None:
        return None
    return _shape_key_value(_normalize_radians(rotation_value))


def _normalize_radians(value: float) -> float:
    normalized = (float(value) + math.pi) % (2 * math.pi) - math.pi
    return 0.0 if abs(normalized) < 1e-12 else normalized


def _distance_sq(left: SemanticPoint, right: SemanticPoint) -> float:
    dx = float(left.x) - float(right.x)
    dy = float(left.y) - float(right.y)
    return dx * dx + dy * dy


def _is_negative_polarity(value: Any) -> bool:
    return str(value or "").strip().casefold() in {"n", "negative", "neg", "-"}


def _point_from_geometry(value: Any) -> SemanticPoint | None:
    if isinstance(value, dict):
        x = value.get("x")
        y = value.get("y")
        if x is not None and y is not None:
            try:
                return SemanticPoint(x=float(x), y=float(y))
            except (TypeError, ValueError):
                return None
    return point_from_pair(value)


def _footprint_geometry_from_package(package: Any | None) -> dict[str, Any]:
    if package is None:
        return {}
    outlines: list[dict[str, Any]] = []
    for index, package_shape in enumerate(package.outlines or []):
        outline = _package_outline_geometry(package_shape)
        if outline is None:
            continue
        outline["source_index"] = index
        outlines.append(outline)

    pads = _footprint_pad_geometry_from_package(package)
    bounds = None
    if package.bounds is not None:
        bounds = {
            "min": [package.bounds.min.x, package.bounds.min.y],
            "max": [package.bounds.max.x, package.bounds.max.y],
        }

    if not outlines and not pads and bounds is None:
        return {}
    return {
        "source": "odbpp_package",
        "package_index": package.package_index,
        "package_name": _package_name(package),
        "bounds": bounds,
        "outlines": outlines,
        "pads": pads,
    }


def _footprint_pad_geometry_from_package(package: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for pin_index, package_pin in enumerate(package.pins or []):
        for shape_index, package_shape in enumerate(package_pin.shapes or []):
            shape = _shape_from_package_shape(package_shape)
            if shape is None:
                continue
            _, auroradb_type, values = shape
            position = point_from_pair(package_shape.center) or point_from_pair(
                package_pin.position
            )
            if position is None:
                continue
            result.append(
                {
                    "pin_name": str(package_pin.name)
                    if package_pin.name is not None
                    else str(pin_index),
                    "shape_index": shape_index,
                    "shape": {
                        "auroradb_type": auroradb_type,
                        "values": values,
                    },
                    "position": position.model_dump(mode="json"),
                    "rotation": _degrees_to_radians(package_pin.rotation),
                    "source": "odbpp_package_pin",
                    "source_pin_index": pin_index,
                }
            )
    return result


def _package_outline_geometry(package_shape: Any) -> dict[str, Any] | None:
    kind = str(package_shape.kind or "").upper()
    center = point_from_pair(package_shape.center)
    cx = center.x if center is not None else 0.0
    cy = center.y if center is not None else 0.0
    if kind == "RC" and package_shape.width and package_shape.height:
        return {
            "kind": "rectangle",
            "auroradb_type": "Rectangle",
            "source_kind": kind,
            "values": [cx, cy, package_shape.width, package_shape.height],
        }
    if kind == "CR" and package_shape.radius:
        return {
            "kind": "circle",
            "auroradb_type": "Circle",
            "source_kind": kind,
            "values": [cx, cy, package_shape.radius * 2],
        }
    if kind == "SQ" and package_shape.size:
        return {
            "kind": "rectangle",
            "auroradb_type": "Rectangle",
            "source_kind": kind,
            "values": [cx, cy, package_shape.size, package_shape.size],
        }
    if package_shape.contours:
        values = _polygon_values_from_contour(package_shape.contours[0])
        if values:
            return {
                "kind": "polygon",
                "auroradb_type": "Polygon",
                "source_kind": kind or "CT",
                "values": values,
            }
    return None


def _package_pad_infos_for_pin(
    package: Any,
    component: Any,
    pin: Any,
    side_key: str,
    *,
    net_id: str | None,
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[str, ...]], str],
    component_index: int,
    pin_index: int,
    layer_names_by_key: dict[str, str],
) -> list[dict[str, Any]]:
    package_pin = _package_pin_for_component_pin(package, pin)
    if package_pin is None:
        return []
    candidate_shapes = list(package_pin.shapes)
    if not candidate_shapes and len(package.outlines) == 1:
        candidate_shapes = list(package.outlines)
    if not candidate_shapes:
        return []

    layer_name = _canonical_layer_name(
        "TOP" if side_key == "top" else "BOTTOM", layer_names_by_key
    )
    result: list[dict[str, Any]] = []
    for shape_index, package_shape in enumerate(candidate_shapes):
        shape_id = _shape_id_from_package_shape(
            package,
            package_pin,
            package_shape,
            shapes,
            shape_ids_by_key,
            source_path=f"packages[{package.package_index}].pins[{package_pin.name}].shapes[{shape_index}]",
        )
        if shape_id is None:
            continue
        package_point = point_from_pair(package_shape.center) or point_from_pair(
            package_pin.position
        )
        position = point_from_pair(pin.position) or _component_relative_point(
            component, package_point
        )
        geometry: dict[str, Any] = {
            "shape_id": shape_id,
            "package": _package_name(package),
            "package_pin": package_pin.name,
            "source": "package",
            "rotation": _degrees_to_radians(pin.rotation),
        }
        if package_shape.kind:
            geometry["shape_kind"] = package_shape.kind
        result.append(
            {
                "feature_key": (
                    "package",
                    package.package_index
                    if package.package_index is not None
                    else component.package_index,
                    package_pin.name or pin.name or pin.pin_index or pin_index,
                    shape_index,
                ),
                "name": pin.name or package_pin.name,
                "net_id": net_id,
                "layer_name": layer_name,
                "position": position,
                "padstack_definition": _package_name(package),
                "geometry": geometry,
                "source": source_ref(
                    "odbpp",
                    f"packages[{package.package_index}].pins[{package_pin.name}]",
                    package_pin.feature_id or package_pin.name,
                ),
            }
        )
    return result


def _package_pin_for_component_pin(package: Any, pin: Any) -> Any | None:
    package_pins = list(package.pins)
    if not package_pins:
        return None
    candidates = []
    if pin.name and not _is_no_net_name(str(pin.name)):
        candidates.append(str(pin.name).casefold())
    if pin.pin_index is not None:
        candidates.append(str(pin.pin_index).casefold())
        candidates.append(str(pin.pin_index + 1).casefold())
    for candidate in candidates:
        for package_pin in package_pins:
            if package_pin.name and str(package_pin.name).casefold() == candidate:
                return package_pin
    if len(package_pins) == 1:
        return package_pins[0]
    return None


def _component_relative_point(
    component: Any, point: SemanticPoint | None
) -> SemanticPoint | None:
    origin = point_from_pair(component.location)
    if origin is None or point is None:
        return None
    rotation = _degrees_to_radians(component.rotation) or 0.0
    mirror = str(component.mirror or "").upper()
    local_x = point.x
    local_y = point.y
    if side_from_layer_name(component.layer_name) == "bottom":
        local_y = -local_y
    cos_angle = math.cos(rotation)
    sin_angle = math.sin(rotation)
    rotated_x = local_x * cos_angle + local_y * sin_angle
    rotated_y = -local_x * sin_angle + local_y * cos_angle
    if mirror not in {"", "N", "NO", "NONE"}:
        rotated_x = -rotated_x
    return SemanticPoint.model_construct(
        x=origin.x + rotated_x,
        y=origin.y + rotated_y,
    )


def _primitives_from_feature(
    layer: LayerFeaturesModel,
    feature: FeatureModel,
    *,
    layer_index: int,
    feature_index: int,
    canonical_layer_name: str,
    net_id: str | None,
    symbol_name: str | None,
    shape_id: str | None,
) -> list[SemanticPrimitive]:
    if feature.kind == "S" and feature.contours:
        surface_groups = _surface_contour_groups(feature.contours)
        if surface_groups:
            return [
                _primitive_from_feature(
                    layer,
                    feature,
                    layer_index=layer_index,
                    feature_index=feature_index,
                    canonical_layer_name=canonical_layer_name,
                    net_id=net_id,
                    symbol_name=symbol_name,
                    shape_id=shape_id,
                    surface_group=surface_group,
                    surface_group_index=surface_group_index,
                    surface_group_count=len(surface_groups),
                )
                for surface_group_index, surface_group in enumerate(surface_groups)
            ]
    return [
        _primitive_from_feature(
            layer,
            feature,
            layer_index=layer_index,
            feature_index=feature_index,
            canonical_layer_name=canonical_layer_name,
            net_id=net_id,
            symbol_name=symbol_name,
            shape_id=shape_id,
        )
    ]


def _primitive_from_feature(
    layer: LayerFeaturesModel,
    feature: FeatureModel,
    *,
    layer_index: int,
    feature_index: int,
    canonical_layer_name: str,
    net_id: str | None,
    symbol_name: str | None,
    shape_id: str | None,
    surface_group: dict[str, Any] | None = None,
    surface_group_index: int | None = None,
    surface_group_count: int | None = None,
) -> SemanticPrimitive:
    feature_key = f"{layer.layer_name}:{feature.kind}:{feature.feature_index}"
    source_path = f"layers[{layer_index}].features[{feature_index}]"
    raw_id: Any = feature.feature_id or feature.feature_index
    if surface_group is not None and surface_group_count and surface_group_count > 1:
        outer_index = surface_group.get("outer_index")
        feature_key = f"{feature_key}:contour{outer_index}"
        source_path = f"{source_path}.contours[{outer_index}]"
        raw_id = feature.feature_id or f"{feature.feature_index}:{outer_index}"
    primitive_id = semantic_id(
        "primitive",
        feature_key,
        f"{layer_index}_{feature_index}",
    )
    geometry = _feature_geometry(
        feature,
        symbol_name,
        surface_group=surface_group,
        surface_group_index=surface_group_index,
        surface_group_count=surface_group_count,
    )
    if shape_id is not None:
        geometry["shape_id"] = shape_id
    return SemanticPrimitive(
        id=primitive_id,
        kind=_feature_kind(feature),
        layer_name=canonical_layer_name,
        net_id=net_id,
        geometry=geometry,
        source=source_ref("odbpp", source_path, raw_id),
    )


def _feature_geometry(
    feature: FeatureModel,
    symbol_name: str | None,
    *,
    surface_group: dict[str, Any] | None = None,
    surface_group_index: int | None = None,
    surface_group_count: int | None = None,
) -> dict[str, Any]:
    start = point_from_pair(feature.start)
    end = point_from_pair(feature.end)
    center = point_from_pair(feature.center)
    geometry: dict[str, Any] = {
        "record_kind": feature.kind,
        "feature_index": feature.feature_index,
        "feature_id": feature.feature_id,
        "line_number": feature.line_number,
        "tokens": feature.tokens,
        "polarity": feature.polarity,
        "symbol": symbol_name or feature.symbol,
        "start": _point_value(start),
        "end": _point_value(end),
        "center": _point_value(center),
    }
    if feature.kind == "P":
        geometry["dcode"] = _token_at(feature.tokens, 5)
        orientation = _feature_orientation(feature, symbol_name)
        geometry["orientation"] = orientation["text"]
        geometry["rotation"] = orientation["rotation"]
        if orientation["mirror_x"]:
            geometry["mirror_x"] = True
    if feature.kind == "L" and start is not None and end is not None:
        geometry["center_line"] = [[start.x, start.y], [end.x, end.y]]
        width = _diameter_from_symbol(symbol_name)
        if width is not None:
            geometry["width"] = width
    if (
        feature.kind == "A"
        and start is not None
        and end is not None
        and center is not None
    ):
        geometry["width"] = _diameter_from_symbol(symbol_name)
        geometry["dcode"] = _token_at(feature.tokens, 9)
        geometry["clockwise"] = _truthy_token(_token_at(feature.tokens, 10))
        geometry["is_ccw"] = (
            not geometry["clockwise"] if geometry["clockwise"] is not None else None
        )
    if feature.kind == "S" and feature.contours:
        if surface_group is None:
            surface_groups = _surface_contour_groups(feature.contours)
            surface_group = surface_groups[0] if surface_groups else None
            surface_group_index = 0
            surface_group_count = len(surface_groups) if surface_groups else 0
        if surface_group is not None:
            _apply_surface_group_geometry(
                geometry,
                feature,
                surface_group,
                surface_group_index=surface_group_index or 0,
                surface_group_count=surface_group_count or 1,
            )
    return geometry


def _surface_contour_groups(contours: list[Any]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for contour_index, contour in enumerate(contours):
        role = _surface_contour_role(contour)
        if role == "island" or not groups:
            groups.append(
                {
                    "outer_index": contour_index,
                    "outer": contour,
                    "holes": [],
                }
            )
            continue
        groups[-1]["holes"].append((contour_index, contour))
    return groups


def _surface_contour_role(contour: Any) -> str | None:
    polarity = str(getattr(contour, "polarity", "") or "").strip().casefold()
    if polarity in {"i", "island", "outer", "outside", "o", "p", "positive"}:
        return "island"
    if polarity in {"h", "hole", "void", "n", "negative"}:
        return "hole"
    return None


def _apply_surface_group_geometry(
    geometry: dict[str, Any],
    feature: FeatureModel,
    surface_group: dict[str, Any],
    *,
    surface_group_index: int,
    surface_group_count: int,
) -> None:
    outer = surface_group["outer"]
    outer_index = int(surface_group["outer_index"])
    geometry["raw_points"] = _contour_points(outer)
    geometry["arcs"] = _contour_arcs(outer)
    geometry["contour_polarity"] = getattr(outer, "polarity", None)
    geometry["source_contour_index"] = outer_index
    geometry["surface_group_index"] = surface_group_index
    geometry["surface_group_count"] = surface_group_count
    geometry["surface_contour_count"] = len(feature.contours)
    geometry["contour_polarities"] = [
        getattr(contour, "polarity", None) for contour in feature.contours
    ]
    geometry["is_negative"] = str(feature.polarity or "").upper() == "N"
    if _surface_contour_role(outer) == "hole":
        geometry["is_void"] = True

    voids: list[dict[str, Any]] = []
    for hole_index, hole in surface_group.get("holes", []):
        voids.append(
            {
                "raw_points": _contour_points(hole),
                "arcs": _contour_arcs(hole),
                "polarity": getattr(hole, "polarity", None),
                "source_contour_index": hole_index,
            }
        )
    if voids:
        geometry["voids"] = voids


def _feature_kind(feature: FeatureModel) -> str:
    if feature.kind == "S" and feature.contours:
        return "polygon"
    return {
        "L": "trace",
        "A": "arc",
        "P": "pad",
        "S": "symbol",
        "T": "text",
        "B": "boundary",
    }.get(feature.kind.upper(), "raw_feature")


def _matrix_layer_names_by_key(payload: ODBLayout) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in payload.matrix.rows if payload.matrix else []:
        if row.name:
            result[_layer_key(row.name)] = row.name
    return result


def _canonical_layer_name(
    layer_name: str | None, layer_names_by_key: dict[str, str]
) -> str:
    if not layer_name:
        return ""
    return layer_names_by_key.get(_layer_key(layer_name), layer_name)


def _feature_symbol_name(
    layer: LayerFeaturesModel, feature: FeatureModel
) -> str | None:
    if not feature.symbol:
        return None
    return layer.symbols.get(str(feature.symbol), feature.symbol)


def _shape_id_from_symbol(
    symbol_name: str | None,
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[str, ...]], str],
    *,
    symbol_definitions: dict[str, SymbolDefinitionModel],
    source_path: str,
) -> str | None:
    shape = _shape_from_symbol(symbol_name)
    if shape is None and symbol_name:
        shape = _shape_from_symbol_definition(
            symbol_definitions.get(symbol_name.casefold())
        )
    if shape is None:
        return None
    kind, auroradb_type, values = shape
    key = (auroradb_type, tuple(_shape_key_value(value) for value in values))
    existing = shape_ids_by_key.get(key)
    if existing is not None:
        return existing
    shape_id = semantic_id("shape", f"{auroradb_type}_{len(shapes)}")
    shapes.append(
        SemanticShape(
            id=shape_id,
            name=symbol_name,
            kind=kind,
            auroradb_type=auroradb_type,
            values=values,
            source=source_ref("odbpp", source_path, symbol_name),
        )
    )
    shape_ids_by_key[key] = shape_id
    return shape_id


def _shape_id_from_drill_slot(
    symbol_name: str | None,
    feature: FeatureModel,
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[str, ...]], str],
    *,
    source_path: str,
) -> tuple[str | None, dict[str, Any] | None]:
    geometry = _drill_slot_geometry(symbol_name, feature)
    if geometry is None:
        return None, None
    values = [0, 0, geometry["total_length"], geometry["width"], geometry["width"] / 2]
    key = ("RoundedRectangle", tuple(_shape_key_value(value) for value in values))
    existing = shape_ids_by_key.get(key)
    if existing is not None:
        return existing, geometry
    shape_id = semantic_id("shape", f"RoundedRectangle_{len(shapes)}")
    shapes.append(
        SemanticShape(
            id=shape_id,
            name=_slot_via_template_symbol(symbol_name, geometry),
            kind="rounded_rectangle",
            auroradb_type="RoundedRectangle",
            values=values,
            source=source_ref("odbpp", source_path, symbol_name),
        )
    )
    shape_ids_by_key[key] = shape_id
    return shape_id, geometry


def _drill_slot_geometry(
    symbol_name: str | None, feature: FeatureModel
) -> dict[str, Any] | None:
    width = _diameter_from_symbol(symbol_name)
    if width is None or width <= 0 or feature.start is None or feature.end is None:
        return None
    start = point_from_pair(feature.start)
    end = point_from_pair(feature.end)
    if start is None or end is None:
        return None
    dx = end.x - start.x
    dy = end.y - start.y
    centerline_length = math.hypot(dx, dy)
    if centerline_length <= 0:
        return None
    total_length = centerline_length + width
    return {
        "center": SemanticPoint(x=(start.x + end.x) / 2, y=(start.y + end.y) / 2),
        "width": width,
        "centerline_length": centerline_length,
        "total_length": total_length,
        "rotation": math.atan2(-dy, dx),
    }


def _slot_via_template_symbol(symbol_name: str | None, geometry: dict[str, Any]) -> str:
    width = _shape_key_value(float(geometry["width"]))
    total_length = _shape_key_value(float(geometry["total_length"]))
    base = symbol_name or "slot"
    return f"{base}:slot:{width}x{total_length}"


def _shape_from_symbol(
    symbol_name: str | None,
) -> tuple[str, str, list[str | float | int]] | None:
    if not symbol_name:
        return None
    text = symbol_name.casefold()
    circle = re.fullmatch(r"r([0-9][0-9r.]*)", text)
    if circle:
        diameter = _odb_symbol_number(circle.group(1))
        return ("circle", "Circle", [0, 0, diameter]) if diameter is not None else None
    square = re.fullmatch(r"s([0-9][0-9r.]*)", text)
    if square:
        size = _odb_symbol_number(square.group(1))
        return (
            ("rectangle", "Rectangle", [0, 0, size, size]) if size is not None else None
        )
    rounded_rect = re.search(
        r"rect([0-9][0-9r.]*)x([0-9][0-9r.]*)xr([0-9][0-9r.]*)", text
    )
    if rounded_rect:
        width = _odb_symbol_number(rounded_rect.group(1))
        height = _odb_symbol_number(rounded_rect.group(2))
        radius = _odb_symbol_number(rounded_rect.group(3))
        if width and height and radius is not None:
            width, height = _canonical_oriented_dimensions(width, height)
            return (
                "rounded_rectangle",
                "RoundedRectangle",
                [0, 0, width, height, radius],
            )
    rect = re.search(r"rect([0-9][0-9r.]*)x([0-9][0-9r.]*)", text)
    if rect:
        width = _odb_symbol_number(rect.group(1))
        height = _odb_symbol_number(rect.group(2))
        if width and height:
            width, height = _canonical_oriented_dimensions(width, height)
            return ("rectangle", "Rectangle", [0, 0, width, height])
        return None
    diamond = re.search(r"di([0-9][0-9r.]*)x([0-9][0-9r.]*)", text)
    if diamond:
        width = _odb_symbol_number(diamond.group(1))
        height = _odb_symbol_number(diamond.group(2))
        if width and height:
            half_width = width / 2
            half_height = height / 2
            return (
                "polygon",
                "Polygon",
                [
                    4,
                    _point_tuple_value([0, half_height]),
                    _point_tuple_value([half_width, 0]),
                    _point_tuple_value([0, -half_height]),
                    _point_tuple_value([-half_width, 0]),
                    "Y",
                    "Y",
                ],
            )
    oval = re.search(r"oval([0-9][0-9r.]*)x([0-9][0-9r.]*)", text)
    if oval:
        width = _odb_symbol_number(oval.group(1))
        height = _odb_symbol_number(oval.group(2))
        if width and height:
            width, height = _canonical_oriented_dimensions(width, height)
            return (
                "rounded_rectangle",
                "RoundedRectangle",
                [0, 0, width, height, min(width, height) / 2],
            )
        if width is not None and height is not None:
            diameter = max(width, height)
            if diameter > 0:
                return ("circle", "Circle", [0, 0, diameter])
    return None


def _canonical_oriented_dimensions(width: float, height: float) -> tuple[float, float]:
    if abs(height) > abs(width):
        return height, width
    return width, height


def _shape_from_symbol_definition(
    symbol: SymbolDefinitionModel | None,
) -> tuple[str, str, list[str | float | int]] | None:
    if symbol is None:
        return None
    for feature in symbol.features:
        if feature.kind != "S" or not feature.contours:
            continue
        values = _polygon_values_from_contour(feature.contours[0])
        if values:
            return ("polygon", "Polygon", values)
    return None


def _shape_id_from_package_shape(
    package: Any,
    package_pin: Any,
    package_shape: Any,
    shapes: list[SemanticShape],
    shape_ids_by_key: dict[tuple[str, tuple[str, ...]], str],
    *,
    source_path: str,
) -> str | None:
    shape = _shape_from_package_shape(package_shape)
    if shape is None:
        return None
    kind, auroradb_type, values = shape
    key = (auroradb_type, tuple(_shape_key_value(value) for value in values))
    existing = shape_ids_by_key.get(key)
    if existing is not None:
        return existing
    name = ":".join(
        part
        for part in [
            _package_name(package),
            str(package_pin.name) if package_pin.name is not None else None,
            package_shape.kind,
        ]
        if part
    )
    shape_id = semantic_id("shape", f"{auroradb_type}_{len(shapes)}")
    shapes.append(
        SemanticShape(
            id=shape_id,
            name=name or None,
            kind=kind,
            auroradb_type=auroradb_type,
            values=values,
            source=source_ref("odbpp", source_path, name or package_shape.kind),
        )
    )
    shape_ids_by_key[key] = shape_id
    return shape_id


def _shape_from_package_shape(
    package_shape: Any,
) -> tuple[str, str, list[str | float | int]] | None:
    kind = str(package_shape.kind or "").upper()
    if kind == "RC" and package_shape.width and package_shape.height:
        return (
            "rectangle",
            "Rectangle",
            [0, 0, package_shape.width, package_shape.height],
        )
    if kind == "CR" and package_shape.radius:
        return ("circle", "Circle", [0, 0, package_shape.radius * 2])
    if kind == "SQ" and package_shape.size:
        return (
            "rectangle",
            "Rectangle",
            [0, 0, package_shape.size, package_shape.size],
        )
    if package_shape.contours:
        origin = point_from_pair(package_shape.center)
        values = _polygon_values_from_contour(package_shape.contours[0], origin=origin)
        if values:
            return ("polygon", "Polygon", values)
    return None


def _polygon_values_from_contour(
    contour: Any,
    *,
    origin: SemanticPoint | None = None,
) -> list[str | float | int]:
    values = _polygon_vertex_values_from_contour(contour, origin=origin)
    if len(values) < 3:
        return []
    return [len(values), *values, "Y", "Y"]


def _diameter_from_symbol(symbol_name: str | None) -> float | None:
    shape = _shape_from_symbol(symbol_name)
    if shape is None or shape[0] != "circle" or len(shape[2]) < 3:
        return None
    value = shape[2][2]
    return float(value) if isinstance(value, (int, float)) else None


def _odb_symbol_number(value: str) -> float | None:
    text = value.replace("r", ".")
    try:
        return float(text) / 1000.0
    except ValueError:
        return None


def _shape_key_value(value: str | float | int) -> str:
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def dedupe_in_place(values: list[T]) -> None:
    seen: set[T] = set()
    write_index = 0
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        values[write_index] = value
        write_index += 1
    del values[write_index:]


def _dedupe_relationship_ids(
    *,
    nets: Any,
    footprints: Any,
    components: list[SemanticComponent],
    pins: list[SemanticPin],
) -> None:
    for net in nets:
        dedupe_in_place(net.pin_ids)
        dedupe_in_place(net.pad_ids)
        dedupe_in_place(net.via_ids)
        dedupe_in_place(net.primitive_ids)
    for footprint in footprints:
        dedupe_in_place(footprint.pad_ids)
    for component in components:
        dedupe_in_place(component.pin_ids)
        dedupe_in_place(component.pad_ids)
    for pin in pins:
        dedupe_in_place(pin.pad_ids)


def _upsert_via_template(
    symbol_name: str | None,
    shape_id: str,
    via_templates_by_id: dict[str, SemanticViaTemplate],
    layer_index: int,
    drill_layer_name: str,
    layer_span: list[str],
    *,
    tool_info: dict[str, Any] | None = None,
) -> str:
    name = f"{drill_layer_name}:{symbol_name or shape_id}"
    template_id = semantic_id("via_template", name)
    if template_id not in via_templates_by_id:
        via_templates_by_id[template_id] = SemanticViaTemplate(
            id=template_id,
            name=name,
            barrel_shape_id=shape_id,
            layer_pads=[
                SemanticViaTemplateLayer(layer_name=layer_name, pad_shape_id=shape_id)
                for layer_name in layer_span
            ],
            geometry={
                "source": "odbpp_drill_tool",
                "drill_layer": drill_layer_name,
                "symbol": symbol_name,
                "tool": tool_info,
            },
            source=source_ref("odbpp", f"layers[{layer_index}].symbols", name),
        )
    elif tool_info and not via_templates_by_id[template_id].geometry.get("tool"):
        via_templates_by_id[template_id].geometry["tool"] = tool_info
    return template_id


def _drill_tools_by_layer_symbol(
    payload: ODBLayout,
) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for drill_layer in payload.drill_tools or []:
        layer_key = _layer_key(drill_layer.layer_name)
        for tool in drill_layer.tools:
            symbol_name = _symbol_name_from_tool(tool)
            if not symbol_name:
                continue
            result[(layer_key, symbol_name.casefold())] = {
                "number": tool.number,
                "tool_type": tool.tool_type,
                "type2": tool.type2,
                "finish_size": tool.finish_size,
                "finish_size_normalized": _tool_size_to_units(tool.finish_size),
                "drill_size": tool.drill_size,
                "drill_size_normalized": _tool_size_to_units(tool.drill_size),
                "raw_fields": dict(tool.raw_fields),
            }
    return result


def _drill_tool_info(
    layer_name: str | None,
    symbol_name: str | None,
    drill_tools_by_layer_symbol: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any] | None:
    if not layer_name or not symbol_name:
        return None
    return drill_tools_by_layer_symbol.get(
        (_layer_key(layer_name), symbol_name.casefold())
    )


def _symbol_name_from_tool(tool: Any) -> str | None:
    for value in (tool.finish_size, tool.drill_size):
        normalized = _tool_size_to_symbol_value(value)
        if normalized:
            return f"r{normalized}"
    return None


def _tool_size_to_symbol_value(value: float | int | None) -> str | None:
    if value is None or value <= 0:
        return None
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.12g}".replace(".", "r")


def _tool_size_to_units(value: float | int | None) -> float | None:
    if value is None or value <= 0:
        return None
    numeric = float(value)
    return numeric / 1000.0 if abs(numeric) >= 10 else numeric


def _contour_points(contour: Any) -> list[list[float]]:
    return [[vertex.point.x, vertex.point.y] for vertex in contour.vertices]


def _point_value(point: SemanticPoint | None) -> dict[str, float] | None:
    if point is None:
        return None
    return {"x": point.x, "y": point.y}


def _contour_arcs(
    contour: Any, *, origin: SemanticPoint | None = None
) -> list[dict[str, Any]]:
    vertices = list(getattr(contour, "vertices", []) or [])
    if len(vertices) < 2:
        return []
    arcs: list[dict[str, Any]] = []
    for previous, current in zip(vertices, vertices[1:]):
        start = _relative_point(previous.point, origin)
        end = _relative_point(current.point, origin)
        entry: dict[str, Any] = {
            "start": start,
            "end": end,
        }
        if str(current.record_type).upper() == "OC" and current.center is not None:
            entry["center"] = _relative_point(current.center, origin)
            clockwise = bool(current.clockwise)
            entry["clockwise"] = clockwise
            entry["is_ccw"] = not clockwise
        else:
            entry["is_segment"] = True
        arcs.append(entry)
    return arcs


def _polygon_vertex_values_from_contour(
    contour: Any,
    *,
    origin: SemanticPoint | None = None,
) -> list[str | float | int]:
    vertices = list(getattr(contour, "vertices", []) or [])
    if len(vertices) < 3:
        return []
    first = vertices[0]
    values: list[str | float | int] = []
    first_point = _relative_point(first.point, origin)
    values.append(_point_tuple_value(first_point))
    for previous, current in zip(vertices, vertices[1:]):
        end = _relative_point(current.point, origin)
        is_closing_line = (
            str(current.record_type).upper() != "OC"
            and _same_source_point(current.point, first.point)
            and current is vertices[-1]
        )
        if is_closing_line:
            continue
        if str(current.record_type).upper() == "OC" and current.center is not None:
            start = _relative_point(previous.point, origin)
            center = _relative_point(current.center, origin)
            direction = "N" if bool(current.clockwise) else "Y"
            if _same_source_point(
                previous.point, current.point
            ) and not _same_source_point(previous.point, current.center):
                opposite = [2 * center[0] - start[0], 2 * center[1] - start[1]]
                values.append(_arc_tuple_value(opposite, center, direction))
                values.append(_arc_tuple_value(end, center, direction))
                continue
            values.append(_arc_tuple_value(end, center, direction))
        else:
            values.append(_point_tuple_value(end))
    if len(values) >= 2 and values[0] == values[-1]:
        values.pop()
    return values


def _relative_point(point: Any, origin: SemanticPoint | None = None) -> list[float]:
    x = float(point.x)
    y = float(point.y)
    if origin is not None:
        x -= origin.x
        y -= origin.y
    return [x, y]


def _point_tuple_value(point: list[float]) -> str:
    return f"({point[0]:.12g},{point[1]:.12g})"


def _arc_tuple_value(end: list[float], center: list[float], direction: str) -> str:
    return (
        f"({end[0]:.12g},{end[1]:.12g},{center[0]:.12g},{center[1]:.12g},{direction})"
    )


def _same_source_point(left: Any, right: Any) -> bool:
    return (
        abs(float(left.x) - float(right.x)) <= 1e-12
        and abs(float(left.y) - float(right.y)) <= 1e-12
    )


def _number_token(tokens: list[str], index: int) -> float | None:
    try:
        return float(str(tokens[index]).split(";")[0])
    except (IndexError, TypeError, ValueError):
        return None


def _token_at(tokens: list[str], index: int) -> str | None:
    try:
        return str(tokens[index]).split(";")[0]
    except (IndexError, TypeError):
        return None


def _truthy_token(value: str | None) -> bool | None:
    if value is None:
        return None
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}


def _feature_orientation(
    feature: FeatureModel, symbol_name: str | None = None
) -> dict[str, Any]:
    first = _token_at(feature.tokens, 6)
    if first is None:
        return {"text": None, "rotation": None, "mirror_x": False}

    code = _parse_orientation_code(first)
    if code is None:
        return {"text": first, "rotation": None, "mirror_x": False}

    if 0 <= code <= 7:
        rotation = math.radians((code % 4) * 90)
        rotation = _apply_symbol_axis_rotation(rotation, symbol_name)
        return {
            "text": str(code),
            "rotation": rotation,
            "mirror_x": code >= 4,
        }

    angle_token = _token_at(feature.tokens, 7)
    embedded_angle = first[1:].strip() if len(first) > 1 else None
    angle = (
        _parse_float(angle_token)
        if angle_token is not None
        else _parse_float(embedded_angle)
    )
    if code in {8, 9} and angle is not None:
        text = f"{code} {angle:g}"
        rotation = _apply_symbol_axis_rotation(math.radians(angle), symbol_name)
        return {
            "text": text,
            "rotation": rotation,
            "mirror_x": code == 9,
        }

    return {"text": first, "rotation": None, "mirror_x": False}


def _apply_symbol_axis_rotation(rotation: float, symbol_name: str | None) -> float:
    axis_rotation = _symbol_axis_rotation(symbol_name)
    if axis_rotation is None:
        return rotation
    return _normalize_symmetric_radians(rotation - axis_rotation)


def _symbol_axis_rotation(symbol_name: str | None) -> float | None:
    dimensions = _oriented_symbol_dimensions(symbol_name)
    if dimensions is None:
        return None
    width, height = dimensions
    if abs(height) <= abs(width) or abs(width - height) < 1e-12:
        return None
    return math.pi / 2


def _oriented_symbol_dimensions(symbol_name: str | None) -> tuple[float, float] | None:
    if not symbol_name:
        return None
    text = symbol_name.casefold()
    for pattern in (
        r"rect([0-9][0-9r.]*)x([0-9][0-9r.]*)xr[0-9][0-9r.]*",
        r"rect([0-9][0-9r.]*)x([0-9][0-9r.]*)",
        r"oval([0-9][0-9r.]*)x([0-9][0-9r.]*)",
    ):
        match = re.search(pattern, text)
        if match:
            width = _odb_symbol_number(match.group(1))
            height = _odb_symbol_number(match.group(2))
            if width and height:
                return width, height
    return None


def _normalize_symmetric_radians(value: float) -> float:
    normalized = math.remainder(float(value), math.pi)
    return 0.0 if abs(normalized) < 1e-12 else normalized


def _parse_orientation_code(value: str) -> int | None:
    text = str(value).strip()
    if not text:
        return None
    first = text[0]
    return int(first) if first.isdigit() else None


def _parse_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(str(value).split(";")[0])
    except (TypeError, ValueError):
        return None


def _degrees_to_radians(value: float | int | None) -> float | None:
    if value is None:
        return None
    return math.radians(float(value))


def _is_drill_layer(layer_name: str | None) -> bool:
    return bool(layer_name and layer_name.casefold().startswith("drill"))


def _layer_key(layer_name: str | None) -> str:
    return (layer_name or "").casefold()


def _drill_layer_spans(
    payload: ODBLayout, layer_names_by_key: dict[str, str]
) -> dict[str, list[str]]:
    rows = list(payload.matrix.rows if payload.matrix else [])
    signal_rows = [
        row
        for row in rows
        if str(row.layer_type or "").casefold() == "signal" and row.name
    ]
    result: dict[str, list[str]] = {}
    for row in rows:
        if not row.name or str(row.layer_type or "").casefold() != "drill":
            continue
        start = _canonical_layer_name(row.start_name, layer_names_by_key)
        end = _canonical_layer_name(row.end_name, layer_names_by_key)
        if not start or not end:
            result[_layer_key(row.name)] = []
            continue
        start_order = _matrix_row_order(rows, start)
        end_order = _matrix_row_order(rows, end)
        if start_order is None or end_order is None:
            result[_layer_key(row.name)] = [start, end] if start != end else [start]
            continue
        low, high = sorted((start_order, end_order))
        span = [
            signal_row.name
            for signal_row in signal_rows
            if signal_row.row is not None
            and low <= signal_row.row <= high
            and signal_row.name
        ]
        result[_layer_key(row.name)] = span or (
            [start, end] if start != end else [start]
        )
    return result


def _matrix_row_order(rows: list[Any], layer_name: str) -> int | None:
    key = _layer_key(layer_name)
    for row in rows:
        if row.name and _layer_key(row.name) == key:
            return row.row
    return None


def _selected_units(payload: ODBLayout) -> str | None:
    selected_step = payload.metadata.selected_step
    for step in payload.steps:
        if step.name == selected_step and step.profile and step.profile.units:
            return step.profile.units
    for layer in payload.layers or []:
        if layer.units:
            return layer.units
    return None


def _board_outline_from_odbpp(payload: ODBLayout) -> dict[str, Any]:
    outline = _board_outline_from_profile_layer(payload)
    if outline:
        return outline
    return _board_outline_from_step_profile(payload)


def _board_outline_from_profile_layer(payload: ODBLayout) -> dict[str, Any]:
    for layer_index, layer in enumerate(payload.layers or []):
        if _layer_key(layer.layer_name) != "profile":
            continue
        paths = _profile_paths_from_features(layer.features)
        selected = _select_outline_path(paths)
        if selected:
            return {
                "source": "odbpp_profile_layer",
                "layer_name": layer.layer_name,
                "layer_index": layer_index,
                "kind": "polygon",
                "auroradb_type": "Polygon",
                "values": _profile_path_values(selected),
                "path_count": len(paths),
            }
    return {}


def _board_outline_from_step_profile(payload: ODBLayout) -> dict[str, Any]:
    selected_step = payload.metadata.selected_step
    for step_index, step in enumerate(payload.steps):
        if selected_step and step.name != selected_step:
            continue
        if not step.profile:
            continue
        contours = _profile_contours_from_records(step.profile.records)
        contour = _select_profile_contour(contours)
        if contour:
            return {
                "source": "odbpp_step_profile",
                "step_name": step.name,
                "step_index": step_index,
                "kind": "polygon",
                "auroradb_type": "Polygon",
                "values": contour["values"],
                "path_count": len(contours),
                "profile_polarity": contour.get("polarity"),
            }
    return {}


def _profile_paths_from_features(
    features: list[FeatureModel],
) -> list[list[dict[str, Any]]]:
    paths: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_end: list[float] | None = None
    for feature in features:
        if feature.kind not in {"L", "A"}:
            continue
        if feature.start is None or feature.end is None:
            continue
        start = [feature.start.x, feature.start.y]
        end = [feature.end.x, feature.end.y]
        if _same_point_values(start, end):
            continue
        segment: dict[str, Any] = {
            "kind": feature.kind,
            "start": start,
            "end": end,
        }
        if feature.kind == "A" and feature.center is not None:
            clockwise = _truthy_token(_token_at(feature.tokens, 10))
            segment["center"] = [feature.center.x, feature.center.y]
            segment["clockwise"] = bool(clockwise)
        if (
            current
            and current_end is not None
            and not _same_point_values(current_end, start)
        ):
            paths.append(current)
            current = []
        current.append(segment)
        current_end = end
    if current:
        paths.append(current)
    return paths


def _profile_contours_from_records(records: list[Any]) -> list[dict[str, Any]]:
    contours: list[dict[str, Any]] = []
    values: list[str | float | int] = []
    points: list[list[float]] = []
    polarity: str | None = None

    def finish_contour() -> None:
        nonlocal values, points, polarity
        if len(values) >= 2 and values[0] == values[-1]:
            values.pop()
        if len(values) >= 3:
            contours.append(
                {
                    "values": [len(values), *values, "Y", "Y"],
                    "polarity": polarity,
                    "closed": bool(points)
                    and _same_point_values(points[0], points[-1]),
                    "score": abs(_polygon_area(points)),
                }
            )
        values = []
        points = []
        polarity = None

    for record in records:
        tokens = list(getattr(record, "tokens", []) or [])
        if not tokens:
            continue
        kind = str(tokens[0]).upper()
        if kind == "OB" and len(tokens) >= 3:
            finish_contour()
            point = [_number_token(tokens, 1), _number_token(tokens, 2)]
            if point[0] is not None and point[1] is not None:
                coordinates = [float(point[0]), float(point[1])]
                values = [_point_tuple_value(coordinates)]
                points = [coordinates]
                polarity_token = _token_at(tokens, 3)
                polarity = polarity_token.upper() if polarity_token else None
        elif kind == "OS" and len(tokens) >= 3 and values:
            point = [_number_token(tokens, 1), _number_token(tokens, 2)]
            if point[0] is not None and point[1] is not None:
                coordinates = [float(point[0]), float(point[1])]
                tuple_value = _point_tuple_value(coordinates)
                if not _same_point_values(coordinates, points[0]):
                    values.append(tuple_value)
                points.append(coordinates)
        elif kind == "OC" and len(tokens) >= 6 and values:
            end = [_number_token(tokens, 1), _number_token(tokens, 2)]
            center = [_number_token(tokens, 3), _number_token(tokens, 4)]
            clockwise = _truthy_token(tokens[5])
            if None not in (*end, *center):
                direction = "N" if clockwise else "Y"
                tuple_value = _arc_tuple_value(
                    [float(end[0]), float(end[1])],
                    [float(center[0]), float(center[1])],
                    direction,
                )
                values.append(tuple_value)
                points.append([float(end[0]), float(end[1])])
        elif kind in {"OE", "SE"}:
            finish_contour()
    finish_contour()
    return contours


def _select_profile_contour(contours: list[dict[str, Any]]) -> dict[str, Any]:
    island_contours = [
        contour
        for contour in contours
        if str(contour.get("polarity") or "").upper() == "I"
    ]
    non_hole_contours = [
        contour
        for contour in contours
        if str(contour.get("polarity") or "").upper() != "H"
    ]
    candidates = island_contours or non_hole_contours or contours
    if not candidates:
        return {}
    return max(candidates, key=_profile_contour_score)


def _profile_contour_score(contour: dict[str, Any]) -> tuple[int, float, int]:
    values = contour.get("values")
    value_count = int(values[0]) if isinstance(values, list) and values else 0
    return (
        1 if contour.get("closed") else 0,
        float(contour.get("score") or 0.0),
        value_count,
    )


def _profile_contour_from_records(records: list[Any]) -> list[str | float | int]:
    contour = _select_profile_contour(_profile_contours_from_records(records))
    values = contour.get("values") if contour else None
    return values if isinstance(values, list) else []


def _select_outline_path(paths: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    closed_paths = [path for path in paths if _profile_path_closed(path)]
    candidates = closed_paths or paths
    if not candidates:
        return []
    return max(candidates, key=_profile_path_score)


def _profile_path_closed(path: list[dict[str, Any]]) -> bool:
    if not path:
        return False
    return _same_point_values(path[0]["start"], path[-1]["end"])


def _profile_path_score(path: list[dict[str, Any]]) -> float:
    points = [path[0]["start"], *[segment["end"] for segment in path]]
    return abs(_polygon_area(points))


def _profile_path_values(path: list[dict[str, Any]]) -> list[str | float | int]:
    if not path:
        return []
    first = path[0]["start"]
    values: list[str | float | int] = [_point_tuple_value(first)]
    for segment in path:
        end = segment["end"]
        if segment["kind"] == "A" and "center" in segment:
            direction = "N" if segment.get("clockwise") else "Y"
            values.append(_arc_tuple_value(end, segment["center"], direction))
            continue
        if _same_point_values(end, first) and segment is path[-1]:
            continue
        values.append(_point_tuple_value(end))
    if len(values) >= 2 and values[0] == values[-1]:
        values.pop()
    return [len(values), *values, "Y", "Y"] if len(values) >= 3 else []


def _same_point_values(left: list[float], right: list[float]) -> bool:
    return (
        abs(float(left[0]) - float(right[0])) <= 1e-9
        and abs(float(left[1]) - float(right[1])) <= 1e-9
    )


def _polygon_area(points: list[list[float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for left, right in zip(points, [*points[1:], points[0]]):
        area += float(left[0]) * float(right[1]) - float(right[0]) * float(left[1])
    return area / 2.0
