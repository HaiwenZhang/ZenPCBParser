from __future__ import annotations

from aurora_translator.sources.auroradb.models import (
    AuroraDBModel,
    AuroraPartModel,
    AuroraPartPadModel,
)
from aurora_translator.semantic.adapters.utils import (
    point_from_pair,
    role_from_layer_type,
    role_from_net_name,
    semantic_id,
    side_from_layer_name,
    source_ref,
    unique_append,
)
from aurora_translator.semantic.models import (
    SemanticBoard,
    SemanticComponent,
    SemanticDiagnostic,
    SemanticFootprint,
    SemanticLayer,
    SemanticMetadata,
    SemanticNet,
    SemanticPad,
    SemanticPin,
    SemanticPrimitive,
    SemanticSummary,
    SemanticVia,
)
from aurora_translator.semantic.passes import (
    build_connectivity_diagnostics,
    build_connectivity_edges,
)


def from_auroradb(payload: AuroraDBModel) -> SemanticBoard:
    nets_by_id: dict[str, SemanticNet] = {}
    components_by_id: dict[str, SemanticComponent] = {}
    footprints_by_id: dict[str, SemanticFootprint] = {}
    component_part_by_id: dict[str, str | None] = {}
    component_footprint_symbol_by_id: dict[str, str | None] = {}
    pins: list[SemanticPin] = []
    pads: list[SemanticPad] = []
    vias: list[SemanticVia] = []
    primitives: list[SemanticPrimitive] = []

    parts = payload.parts.parts if payload.parts else []
    parts_by_name = {part.info.name: part for part in parts if part.info.name}
    part_index_by_name = {
        part.info.name: index for index, part in enumerate(parts) if part.info.name
    }

    def ensure_footprint(
        symbol_id: str | None,
        *,
        part_name: str | None = None,
        source_path: str | None = None,
        raw_id: object | None = None,
    ) -> str | None:
        if not symbol_id:
            return None
        footprint_id = semantic_id("footprint", symbol_id)
        if footprint_id not in footprints_by_id:
            footprints_by_id[footprint_id] = SemanticFootprint(
                id=footprint_id,
                name=symbol_id,
                part_name=part_name,
                source=source_ref("auroradb", source_path, raw_id or symbol_id),
            )
        elif part_name and footprints_by_id[footprint_id].part_name is None:
            footprints_by_id[footprint_id].part_name = part_name
        return footprint_id

    footprint_pad_templates: dict[
        tuple[str, str], tuple[AuroraPartPadModel, str | None, str]
    ] = {}
    if payload.parts is not None:
        for footprint_index, footprint in enumerate(payload.parts.footprints):
            ensure_footprint(
                footprint.symbol_id,
                source_path=f"parts.footprints[{footprint_index}]",
                raw_id=footprint.symbol_id,
            )
            for metal_index, metal_layer in enumerate(footprint.metal_layers):
                for pad_index, pad in enumerate(metal_layer.part_pads):
                    _record_footprint_pad_template(
                        footprint_pad_templates,
                        footprint.symbol_id,
                        pad,
                        metal_layer.name,
                        f"parts.footprints[{footprint_index}].metal_layers[{metal_index}].part_pads[{pad_index}]",
                    )
                for logic_index, logic_layer in enumerate(metal_layer.logic_layers):
                    for pad_index, pad in enumerate(logic_layer.part_pads):
                        _record_footprint_pad_template(
                            footprint_pad_templates,
                            footprint.symbol_id,
                            pad,
                            logic_layer.name or metal_layer.name,
                            (
                                f"parts.footprints[{footprint_index}].metal_layers[{metal_index}]"
                                f".logic_layers[{logic_index}].part_pads[{pad_index}]"
                            ),
                        )

    stack_order = (
        payload.layout.layer_stackup.metal_layers
        if payload.layout and payload.layout.layer_stackup
        else []
    )
    order_by_name = {name: index for index, name in enumerate(stack_order)}

    layers: list[SemanticLayer] = []
    for index, layer in enumerate(payload.layers):
        order_index = order_by_name.get(layer.name, index)
        layers.append(
            SemanticLayer(
                id=semantic_id("layer", layer.name, index),
                name=layer.name,
                layer_type=layer.type,
                role=role_from_layer_type(layer.type),
                side=side_from_layer_name(layer.name),
                order_index=order_index,
                source=source_ref(
                    "auroradb", f"layers[{index}]", layer.id or layer.name
                ),
            )
        )

    if payload.layout is not None:
        for net_index, net in enumerate(payload.layout.nets):
            net_id = semantic_id("net", net.name, net_index)
            nets_by_id[net_id] = SemanticNet(
                id=net_id,
                name=net.name,
                role=role_from_net_name(net.name, net.type),
                source=source_ref("auroradb", f"layout.nets[{net_index}]", net.name),
            )

    for layer_index, layer in enumerate(payload.layers):
        for component_index, component in enumerate(layer.components):
            component_id = semantic_id(
                "component", component.name, f"{layer_index}_{component_index}"
            )
            part = parts_by_name.get(component.part_name or "")
            part_index = part_index_by_name.get(component.part_name or "")
            footprint_symbol = _footprint_symbol_for_part(part) or component.part_name
            footprint_source_path = (
                f"parts.parts[{part_index}].footprint_symbols[0]"
                if part_index is not None and _footprint_symbol_for_part(part)
                else f"layers[{layer_index}].components[{component_index}]"
            )
            footprint_id = ensure_footprint(
                footprint_symbol,
                part_name=component.part_name,
                source_path=footprint_source_path,
                raw_id=footprint_symbol,
            )
            components_by_id[component_id] = SemanticComponent(
                id=component_id,
                refdes=component.name,
                name=component.name,
                part_name=component.part_name,
                package_name=footprint_symbol or component.part_name,
                footprint_id=footprint_id,
                layer_name=layer.name,
                side=side_from_layer_name(layer.name),
                value=component.value,
                location=point_from_pair(component.location),
                rotation=component.location.rotation if component.location else None,
                source=source_ref(
                    "auroradb",
                    f"layers[{layer_index}].components[{component_index}]",
                    component.name,
                ),
            )
            component_part_by_id[component_id] = component.part_name
            component_footprint_symbol_by_id[component_id] = footprint_symbol
        for net_geometry_index, net_geometry in enumerate(layer.net_geometries):
            net_id = semantic_id("net", net_geometry.net_name)
            for geometry_index, geometry in enumerate(net_geometry.geometries):
                primitive_id = semantic_id(
                    "primitive",
                    f"{layer.name}:{net_geometry.net_name}:{geometry.symbol_id}",
                    f"{layer_index}_{net_geometry_index}_{geometry_index}",
                )
                primitives.append(
                    SemanticPrimitive(
                        id=primitive_id,
                        kind="net_geometry",
                        layer_name=layer.name,
                        net_id=net_id,
                        geometry={
                            "symbol_id": geometry.symbol_id,
                            "location": geometry.location.model_dump(mode="json")
                            if geometry.location
                            else None,
                        },
                        source=source_ref(
                            "auroradb",
                            f"layers[{layer_index}].net_geometries[{net_geometry_index}].geometries[{geometry_index}]",
                            geometry.symbol_id,
                        ),
                    )
                )
                if net_id in nets_by_id:
                    unique_append(nets_by_id[net_id].primitive_ids, primitive_id)

    if payload.layout is not None:
        for net_index, net in enumerate(payload.layout.nets):
            net_id = semantic_id("net", net.name, net_index)
            for pin_index, pin in enumerate(net.pins):
                component_id = (
                    semantic_id("component", pin.component) if pin.component else None
                )
                pin_owner = component_id or pin.component or net.name
                pin_id = semantic_id(
                    "pin",
                    f"{pin_owner}:{pin.pin}" if pin.pin else None,
                    f"{net_index}_{pin_index}",
                )
                footprint_symbol = component_footprint_symbol_by_id.get(
                    component_id or ""
                )
                footprint_id = (
                    semantic_id("footprint", footprint_symbol)
                    if footprint_symbol
                    else None
                )
                part = parts_by_name.get(
                    component_part_by_id.get(component_id or "") or ""
                )
                mapped_pad_name = _mapped_pad_name(part, pin.pin, footprint_symbol)
                pad_name = mapped_pad_name or pin.pin
                template = (
                    footprint_pad_templates.get((footprint_symbol, pad_name))
                    if footprint_symbol and pad_name
                    else None
                )
                semantic_pin = SemanticPin(
                    id=pin_id,
                    name=pin.pin,
                    component_id=component_id,
                    net_id=net_id,
                    layer_name=pin.metal_layer or pin.component_layer,
                    source=source_ref(
                        "auroradb",
                        f"layout.nets[{net_index}].pins[{pin_index}]",
                        pin.pin,
                    ),
                )
                pins.append(semantic_pin)
                if component_id in components_by_id:
                    unique_append(components_by_id[component_id].pin_ids, pin_id)
                if net_id in nets_by_id:
                    unique_append(nets_by_id[net_id].pin_ids, pin_id)

                pad_id = semantic_id(
                    "pad",
                    f"{pin_owner}:{pad_name}" if pad_name else None,
                    f"{net_index}_{pin_index}",
                )
                semantic_pad = SemanticPad(
                    id=pad_id,
                    name=pad_name,
                    footprint_id=footprint_id,
                    component_id=component_id,
                    pin_id=pin_id,
                    net_id=net_id,
                    layer_name=pin.metal_layer
                    or pin.component_layer
                    or (template[1] if template else None),
                    padstack_definition=template[0].template_id if template else None,
                    geometry={
                        "source_pin_raw": list(pin.raw),
                        "footprint_pad_source": template[2] if template else None,
                        "footprint_pad_location": (
                            template[0].location.model_dump(mode="json")
                            if template and template[0].location
                            else None
                        ),
                    },
                    source=source_ref(
                        "auroradb",
                        f"layout.nets[{net_index}].pins[{pin_index}]",
                        pin.pin,
                    ),
                )
                pads.append(semantic_pad)
                unique_append(semantic_pin.pad_ids, pad_id)
                if component_id in components_by_id:
                    unique_append(components_by_id[component_id].pad_ids, pad_id)
                if footprint_id in footprints_by_id:
                    unique_append(footprints_by_id[footprint_id].pad_ids, pad_id)
                if net_id in nets_by_id:
                    unique_append(nets_by_id[net_id].pad_ids, pad_id)
            for via_index, via in enumerate(net.vias):
                via_id = semantic_id(
                    "via", f"{net.name}:{via.via_id}", f"{net_index}_{via_index}"
                )
                vias.append(
                    SemanticVia(
                        id=via_id,
                        net_id=net_id,
                        position=point_from_pair(via.location),
                        source=source_ref(
                            "auroradb",
                            f"layout.nets[{net_index}].vias[{via_index}]",
                            via.via_id,
                        ),
                    )
                )
                if net_id in nets_by_id:
                    unique_append(nets_by_id[net_id].via_ids, via_id)

    diagnostics = [
        SemanticDiagnostic(
            severity="warning",
            code="auroradb.source_diagnostic",
            message=message,
            source=source_ref("auroradb", "diagnostics"),
        )
        for message in payload.diagnostics
    ]

    board = SemanticBoard(
        metadata=SemanticMetadata(
            source_format="auroradb",
            source=payload.root,
            source_parser_version=payload.metadata.parser_version,
            source_schema_version=payload.metadata.output_schema_version,
        ),
        units=payload.layout.units if payload.layout else payload.summary.units,
        summary=SemanticSummary(),
        layers=layers,
        nets=list(nets_by_id.values()),
        components=list(components_by_id.values()),
        footprints=list(footprints_by_id.values()),
        pins=pins,
        pads=pads,
        vias=vias,
        primitives=primitives,
        diagnostics=diagnostics,
    )
    board = board.model_copy(update={"connectivity": build_connectivity_edges(board)})
    board = board.model_copy(
        update={
            "diagnostics": [*board.diagnostics, *build_connectivity_diagnostics(board)]
        }
    )
    return board.with_computed_summary()


def _record_footprint_pad_template(
    templates: dict[tuple[str, str], tuple[AuroraPartPadModel, str | None, str]],
    footprint_symbol: str | None,
    pad: AuroraPartPadModel,
    layer_name: str | None,
    source_path: str,
) -> None:
    if footprint_symbol and pad.pad_id:
        templates.setdefault(
            (footprint_symbol, pad.pad_id), (pad, layer_name, source_path)
        )


def _footprint_symbol_for_part(part: AuroraPartModel | None) -> str | None:
    if part is None:
        return None
    for symbol_id in part.footprint_symbols:
        if symbol_id:
            return symbol_id
    return None


def _mapped_pad_name(
    part: AuroraPartModel | None, pin_name: str | None, footprint_symbol: str | None
) -> str | None:
    if part is None or not pin_name:
        return None
    for part_pin in part.pins:
        if pin_name not in {part_pin.number, part_pin.name}:
            continue
        if footprint_symbol:
            for mapping in part_pin.footprint_pad_map:
                if mapping.footprint == footprint_symbol:
                    return mapping.pad_id
        for mapping in part_pin.footprint_pad_map:
            if mapping.pad_id:
                return mapping.pad_id
    return None
