from __future__ import annotations

from collections.abc import Iterable

from aurora_translator.semantic.models import (
    ConnectivityEdge,
    SemanticBoard,
    SemanticDiagnostic,
    SourceRef,
)


def build_connectivity_edges(board: SemanticBoard) -> list[ConnectivityEdge]:
    """Build deterministic connectivity edges from semantic object references."""

    edges: list[ConnectivityEdge] = []
    seen: set[tuple[str, str, str]] = set()

    def add(kind: str, source_id: str | None, target_id: str | None) -> None:
        if not source_id or not target_id:
            return
        key = (kind, source_id, target_id)
        if key in seen:
            return
        seen.add(key)
        edges.append(
            ConnectivityEdge(
                kind=kind,  # type: ignore[arg-type]
                source_id=source_id,
                target_id=target_id,
            )
        )

    for component in board.components:
        add("component-footprint", component.id, component.footprint_id)
        for pin_id in component.pin_ids:
            add("component-pin", component.id, pin_id)
        for pad_id in component.pad_ids:
            add("component-pad", component.id, pad_id)

    for footprint in board.footprints:
        for pad_id in footprint.pad_ids:
            add("footprint-pad", footprint.id, pad_id)

    for pin in board.pins:
        add("component-pin", pin.component_id, pin.id)
        add("pin-net", pin.id, pin.net_id)
        for pad_id in pin.pad_ids:
            add("pin-pad", pin.id, pad_id)

    for pad in board.pads:
        add("component-pad", pad.component_id, pad.id)
        add("footprint-pad", pad.footprint_id, pad.id)
        add("pin-pad", pad.pin_id, pad.id)
        add("pad-net", pad.id, pad.net_id)

    for via in board.vias:
        add("via-net", via.id, via.net_id)

    for primitive in board.primitives:
        add("primitive-net", primitive.id, primitive.net_id)
        add("component-primitive", primitive.component_id, primitive.id)

    return edges


def build_connectivity_diagnostics(board: SemanticBoard) -> list[SemanticDiagnostic]:
    """Report references that point to missing semantic objects."""

    layer_names = {layer.name for layer in board.layers}
    material_ids = {material.id for material in board.materials}
    shape_ids = {shape.id for shape in board.shapes}
    via_template_ids = {template.id for template in board.via_templates}
    net_ids = {net.id for net in board.nets}
    component_ids = {component.id for component in board.components}
    footprint_ids = {footprint.id for footprint in board.footprints}
    pin_ids = {pin.id for pin in board.pins}
    pad_ids = {pad.id for pad in board.pads}
    via_ids = {via.id for via in board.vias}
    primitive_ids = {primitive.id for primitive in board.primitives}

    diagnostics: list[SemanticDiagnostic] = []
    seen: set[tuple[str, str, str]] = set()

    def add(
        code: str,
        owner_id: str,
        missing_id: str,
        message: str,
        source: SourceRef | None,
    ) -> None:
        key = (code, owner_id, missing_id)
        if key in seen:
            return
        seen.add(key)
        diagnostics.append(
            SemanticDiagnostic(
                severity="warning",
                code=code,
                message=message,
                source=source,
            )
        )

    def check_ref(
        *,
        code: str,
        owner_type: str,
        owner_id: str,
        field_name: str,
        target_id: str | None,
        valid_ids: set[str],
        source: SourceRef | None,
    ) -> None:
        if not target_id or target_id in valid_ids:
            return
        add(
            code,
            owner_id,
            target_id,
            f"{owner_type} {owner_id} references missing {field_name} {target_id}.",
            source,
        )

    def check_refs(
        *,
        code: str,
        owner_type: str,
        owner_id: str,
        field_name: str,
        target_ids: Iterable[str],
        valid_ids: set[str],
        source: SourceRef | None,
    ) -> None:
        for target_id in target_ids:
            check_ref(
                code=code,
                owner_type=owner_type,
                owner_id=owner_id,
                field_name=field_name,
                target_id=target_id,
                valid_ids=valid_ids,
                source=source,
            )

    for layer in board.layers:
        check_ref(
            code="semantic.layer_material_missing_ref",
            owner_type="layer",
            owner_id=layer.id,
            field_name="material",
            target_id=layer.material_id,
            valid_ids=material_ids,
            source=layer.source,
        )
        check_ref(
            code="semantic.layer_fill_material_missing_ref",
            owner_type="layer",
            owner_id=layer.id,
            field_name="fill_material",
            target_id=layer.fill_material_id,
            valid_ids=material_ids,
            source=layer.source,
        )

    for template in board.via_templates:
        check_ref(
            code="semantic.via_template_barrel_shape_missing_ref",
            owner_type="via_template",
            owner_id=template.id,
            field_name="barrel_shape",
            target_id=template.barrel_shape_id,
            valid_ids=shape_ids,
            source=template.source,
        )
        for layer_pad in template.layer_pads:
            check_ref(
                code="semantic.via_template_pad_shape_missing_ref",
                owner_type="via_template",
                owner_id=template.id,
                field_name="pad_shape",
                target_id=layer_pad.pad_shape_id,
                valid_ids=shape_ids,
                source=template.source,
            )
            check_ref(
                code="semantic.via_template_antipad_shape_missing_ref",
                owner_type="via_template",
                owner_id=template.id,
                field_name="antipad_shape",
                target_id=layer_pad.antipad_shape_id,
                valid_ids=shape_ids,
                source=template.source,
            )
            check_ref(
                code="semantic.via_template_thermal_shape_missing_ref",
                owner_type="via_template",
                owner_id=template.id,
                field_name="thermal_shape",
                target_id=layer_pad.thermal_shape_id,
                valid_ids=shape_ids,
                source=template.source,
            )

    for net in board.nets:
        check_refs(
            code="semantic.net_pin_missing_ref",
            owner_type="net",
            owner_id=net.id,
            field_name="pin",
            target_ids=net.pin_ids,
            valid_ids=pin_ids,
            source=net.source,
        )
        check_refs(
            code="semantic.net_pad_missing_ref",
            owner_type="net",
            owner_id=net.id,
            field_name="pad",
            target_ids=net.pad_ids,
            valid_ids=pad_ids,
            source=net.source,
        )
        check_refs(
            code="semantic.net_via_missing_ref",
            owner_type="net",
            owner_id=net.id,
            field_name="via",
            target_ids=net.via_ids,
            valid_ids=via_ids,
            source=net.source,
        )
        check_refs(
            code="semantic.net_primitive_missing_ref",
            owner_type="net",
            owner_id=net.id,
            field_name="primitive",
            target_ids=net.primitive_ids,
            valid_ids=primitive_ids,
            source=net.source,
        )

    for component in board.components:
        check_ref(
            code="semantic.component_footprint_missing_ref",
            owner_type="component",
            owner_id=component.id,
            field_name="footprint",
            target_id=component.footprint_id,
            valid_ids=footprint_ids,
            source=component.source,
        )
        check_refs(
            code="semantic.component_pin_missing_ref",
            owner_type="component",
            owner_id=component.id,
            field_name="pin",
            target_ids=component.pin_ids,
            valid_ids=pin_ids,
            source=component.source,
        )
        check_refs(
            code="semantic.component_pad_missing_ref",
            owner_type="component",
            owner_id=component.id,
            field_name="pad",
            target_ids=component.pad_ids,
            valid_ids=pad_ids,
            source=component.source,
        )

    for footprint in board.footprints:
        check_refs(
            code="semantic.footprint_pad_missing_ref",
            owner_type="footprint",
            owner_id=footprint.id,
            field_name="pad",
            target_ids=footprint.pad_ids,
            valid_ids=pad_ids,
            source=footprint.source,
        )

    for pin in board.pins:
        check_ref(
            code="semantic.pin_component_missing_ref",
            owner_type="pin",
            owner_id=pin.id,
            field_name="component",
            target_id=pin.component_id,
            valid_ids=component_ids,
            source=pin.source,
        )
        check_ref(
            code="semantic.pin_net_missing_ref",
            owner_type="pin",
            owner_id=pin.id,
            field_name="net",
            target_id=pin.net_id,
            valid_ids=net_ids,
            source=pin.source,
        )
        check_refs(
            code="semantic.pin_pad_missing_ref",
            owner_type="pin",
            owner_id=pin.id,
            field_name="pad",
            target_ids=pin.pad_ids,
            valid_ids=pad_ids,
            source=pin.source,
        )
        check_ref(
            code="semantic.pin_layer_missing_ref",
            owner_type="pin",
            owner_id=pin.id,
            field_name="layer",
            target_id=pin.layer_name,
            valid_ids=layer_names,
            source=pin.source,
        )

    for pad in board.pads:
        check_ref(
            code="semantic.pad_footprint_missing_ref",
            owner_type="pad",
            owner_id=pad.id,
            field_name="footprint",
            target_id=pad.footprint_id,
            valid_ids=footprint_ids,
            source=pad.source,
        )
        check_ref(
            code="semantic.pad_component_missing_ref",
            owner_type="pad",
            owner_id=pad.id,
            field_name="component",
            target_id=pad.component_id,
            valid_ids=component_ids,
            source=pad.source,
        )
        check_ref(
            code="semantic.pad_pin_missing_ref",
            owner_type="pad",
            owner_id=pad.id,
            field_name="pin",
            target_id=pad.pin_id,
            valid_ids=pin_ids,
            source=pad.source,
        )
        check_ref(
            code="semantic.pad_net_missing_ref",
            owner_type="pad",
            owner_id=pad.id,
            field_name="net",
            target_id=pad.net_id,
            valid_ids=net_ids,
            source=pad.source,
        )
        check_ref(
            code="semantic.pad_layer_missing_ref",
            owner_type="pad",
            owner_id=pad.id,
            field_name="layer",
            target_id=pad.layer_name,
            valid_ids=layer_names,
            source=pad.source,
        )

    for via in board.vias:
        check_ref(
            code="semantic.via_net_missing_ref",
            owner_type="via",
            owner_id=via.id,
            field_name="net",
            target_id=via.net_id,
            valid_ids=net_ids,
            source=via.source,
        )
        check_ref(
            code="semantic.via_template_missing_ref",
            owner_type="via",
            owner_id=via.id,
            field_name="via_template",
            target_id=via.template_id,
            valid_ids=via_template_ids,
            source=via.source,
        )
        for layer_name in via.layer_names:
            check_ref(
                code="semantic.via_layer_missing_ref",
                owner_type="via",
                owner_id=via.id,
                field_name="layer",
                target_id=layer_name,
                valid_ids=layer_names,
                source=via.source,
            )

    for primitive in board.primitives:
        check_ref(
            code="semantic.primitive_net_missing_ref",
            owner_type="primitive",
            owner_id=primitive.id,
            field_name="net",
            target_id=primitive.net_id,
            valid_ids=net_ids,
            source=primitive.source,
        )
        check_ref(
            code="semantic.primitive_component_missing_ref",
            owner_type="primitive",
            owner_id=primitive.id,
            field_name="component",
            target_id=primitive.component_id,
            valid_ids=component_ids,
            source=primitive.source,
        )
        check_ref(
            code="semantic.primitive_layer_missing_ref",
            owner_type="primitive",
            owner_id=primitive.id,
            field_name="layer",
            target_id=primitive.layer_name,
            valid_ids=layer_names,
            source=primitive.source,
        )

    return diagnostics
