from __future__ import annotations

import math
import logging
from typing import Any

from aurora_translator.sources.auroradb.block import (
    AuroraBlock,
    split_reserved,
    strip_wrapping_pair,
    strip_wrapping_quotes,
)
from aurora_translator.targets.auroradb.aaf.geometry import parse_geometry_option
from aurora_translator.targets.auroradb.direct import (
    _AedbComponentPlacement,
    _AedbExportPlan,
    _AedbPartVariant,
    _AedbPinFeature,
    _DirectPartIndexes,
    _DirectPartsBuilder,
    _PartExportPlan,
    _PartExportVariant,
    _SelectedFootprintPad,
    _direct_attribute_values,
    _direct_replace_item_before_block,
)
from aurora_translator.targets.auroradb.formatting import (
    _auroradb_output_unit,
    _format_number,
    _format_rotation,
    _is_finite,
    _normalize_degree,
    _number,
    _point_tuple,
    _source_unit_for_auroradb_output,
    _source_rotations_are_clockwise,
)
from aurora_translator.targets.auroradb.geometry import (
    _chunks,
    _component_name,
    _component_part_name,
    _direct_location_values,
    _footprint_geometry_commands,
    _geometry_signature,
    _odbpp_component_needs_bottom_flip,
    _outline_geometry_payload,
    _pad_flip_options,
    _pad_rotation,
    _pad_shape_id_for_layer,
    _pad_shape_ids_by_definition,
    _pin_name,
    _point_coordinates,
    _shape_auroradb_type,
    _shape_geometry_payload,
)
from aurora_translator.targets.auroradb.names import (
    _aaf_atom,
    _pin_sort_key,
    _quote_aaf,
    _standardize_name,
    _tuple_value,
)
from aurora_translator.semantic.models import (
    SemanticBoard,
    SemanticComponent,
    SemanticLayer,
    SemanticPad,
    SemanticPin,
    SemanticShape,
)

AEDB_COMPONENT_MATCH_TOLERANCE_MIL = 1e-3
logger = logging.getLogger("aurora_translator.targets.auroradb")


def _library_unit(board: SemanticBoard) -> str:
    return _auroradb_output_unit(board.units)


def _part_geometry_source_unit(board: SemanticBoard) -> str | None:
    return _source_unit_for_auroradb_output(board.units)


def _aaf_text(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def _design_part(
    board: SemanticBoard,
    aedb_plan: _AedbExportPlan | None = None,
    part_export_plan: _PartExportPlan | None = None,
) -> str:
    return _aaf_text(_design_part_lines(board, aedb_plan, part_export_plan))


def _design_part_lines(
    board: SemanticBoard,
    aedb_plan: _AedbExportPlan | None = None,
    part_export_plan: _PartExportPlan | None = None,
) -> list[str]:
    geometry_source_unit = _part_geometry_source_unit(board)
    lines = [f"library set -unit <{_library_unit(board)}>"]
    components_by_id = {component.id: component for component in board.components}
    pad_shape_ids = _pad_shape_ids_by_definition(board)
    if aedb_plan is not None:
        part_names_by_component_id = {
            component_id: placement.export_part_name
            for component_id, placement in aedb_plan.placements_by_component_id.items()
        }
        pins_by_part = _pins_by_part(
            board.pins,
            components_by_id,
            part_names_by_component_id=part_names_by_component_id,
        )
        footprint_names = {variant.footprint_name for variant in aedb_plan.variants}
        for footprint_name in sorted(footprint_names, key=str.casefold):
            lines.append(f"library add -footprint <{_quote_aaf(footprint_name)}>")

        emitted_footprint_pads: set[str] = set()
        for variant in sorted(
            aedb_plan.variants, key=lambda item: item.export_part_name.casefold()
        ):
            component = components_by_id.get(variant.representative_component_id)
            footprint_key = variant.footprint_name.casefold()
            if footprint_key not in emitted_footprint_pads:
                lines.extend(
                    _footprint_pad_commands(
                        component,
                        variant.footprint_name,
                        board,
                        pad_shape_ids,
                        source_unit=geometry_source_unit,
                        normalize_rotation=variant.canonical_rotation,
                        source_format=board.metadata.source_format,
                    )
                )
                emitted_footprint_pads.add(footprint_key)
            lines.append(
                "library add "
                f"-p <{_quote_aaf(variant.export_part_name)}> "
                f"-t <{_quote_aaf('')}> "
                f"-d <{_quote_aaf('')}> "
                f"-footprint <{_quote_aaf(variant.footprint_name)}>"
            )
            part_pins = pins_by_part.get(variant.export_part_name.casefold(), [])
            for chunk in _chunks(part_pins, 64):
                pin_values = " ".join(f"<{_part_pin_tuple(pin)}>" for pin in chunk)
                lines.append(
                    f"library add -pin {pin_values} -p <{_quote_aaf(variant.export_part_name)}>"
                )
        return lines

    if part_export_plan is None:
        part_export_plan = _part_export_plan(board)
    pins_by_part = _pins_by_part(
        board.pins,
        components_by_id,
        part_names_by_component_id=part_export_plan.part_names_by_component_id,
    )
    footprint_names = _part_plan_footprint_names(board, part_export_plan)
    footprints_by_name = _footprints_by_name(board)

    export_footprint_geometry = _board_exports_footprint_layer_geometry(board)
    for footprint_name, source_footprint_name in sorted(
        footprint_names.values(),
        key=lambda item: item[0].casefold(),
    ):
        lines.append(f"library add -footprint <{_quote_aaf(footprint_name)}>")
        if export_footprint_geometry:
            footprint = footprints_by_name.get(source_footprint_name.casefold())
            lines.extend(
                _footprint_geometry_commands(
                    footprint, footprint_name, source_unit=geometry_source_unit
                )
            )

    emitted_footprint_pads: set[str] = set()
    for variant in sorted(
        part_export_plan.variants, key=lambda item: item.export_part_name.casefold()
    ):
        part_name = variant.export_part_name
        footprint_name = variant.footprint_name
        footprint_key = footprint_name.casefold()
        if footprint_key not in emitted_footprint_pads:
            component = components_by_id.get(variant.representative_component_id)
            lines.extend(
                _footprint_pad_commands(
                    component,
                    footprint_name,
                    board,
                    pad_shape_ids,
                    source_footprint_name=variant.source_footprint_name,
                    source_unit=geometry_source_unit,
                    source_format=board.metadata.source_format,
                )
            )
            emitted_footprint_pads.add(footprint_key)
        variant_components = [
            components_by_id[component_id]
            for component_id in variant.component_ids
            if component_id in components_by_id
        ]
        part_type = (
            ""
            if _minimal_part_info(board)
            else _part_type_for_components(variant_components)
        )
        part_description = (
            ""
            if _minimal_part_info(board)
            else _part_description_for_components(
                variant_components, variant.source_footprint_name or footprint_name
            )
        )
        lines.append(
            "library add "
            f"-p <{_quote_aaf(part_name)}> "
            f"-t <{_quote_aaf(part_type)}> "
            f"-d <{_quote_aaf(part_description)}> "
            f"-footprint <{_quote_aaf(footprint_name)}>"
            f"{_part_attribute_options(_part_attributes_for_components(variant, variant_components, board))}"
        )
        part_pins = pins_by_part.get(part_name.casefold(), [])
        for chunk in _chunks(part_pins, 64):
            pin_values = " ".join(f"<{_part_pin_tuple(pin)}>" for pin in chunk)
            lines.append(f"library add -pin {pin_values} -p <{_quote_aaf(part_name)}>")

    return lines


def _build_direct_parts_block(
    board: SemanticBoard,
    aedb_plan: _AedbExportPlan | None,
    part_export_plan: _PartExportPlan | None,
) -> AuroraBlock:
    builder = _DirectPartsBuilder()
    components_by_id = {component.id: component for component in board.components}
    pad_shape_ids = _pad_shape_ids_by_definition(board)
    indexes = _DirectPartIndexes(
        pads_by_id={pad.id: pad for pad in board.pads},
        pins_by_id={pin.id: pin for pin in board.pins},
        shapes_by_id={shape.id: shape for shape in board.shapes},
        footprints_by_name={
            footprint.name.casefold(): footprint
            for footprint in board.footprints
            if footprint.name
        },
    )
    geometry_source_unit = _part_geometry_source_unit(board)

    if aedb_plan is not None:
        part_names_by_component_id = {
            component_id: placement.export_part_name
            for component_id, placement in aedb_plan.placements_by_component_id.items()
        }
        pins_by_part = _pins_by_part(
            board.pins,
            components_by_id,
            part_names_by_component_id=part_names_by_component_id,
        )
        footprint_names = {variant.footprint_name for variant in aedb_plan.variants}
        for footprint_name in sorted(footprint_names, key=str.casefold):
            builder.find_or_create_footprint(footprint_name)

        emitted_footprint_pads: set[str] = set()
        for variant in sorted(
            aedb_plan.variants, key=lambda item: item.export_part_name.casefold()
        ):
            component = components_by_id.get(variant.representative_component_id)
            footprint_key = variant.footprint_name.casefold()
            if footprint_key not in emitted_footprint_pads:
                _direct_add_footprint_pads(
                    builder,
                    component,
                    variant.footprint_name,
                    board,
                    pad_shape_ids,
                    indexes,
                    source_unit=geometry_source_unit,
                    normalize_rotation=variant.canonical_rotation,
                    source_format=board.metadata.source_format,
                )
                emitted_footprint_pads.add(footprint_key)
            part = builder.find_or_create_part(variant.export_part_name)
            _direct_replace_item_before_block(
                part, "FootPrintSymbols", [variant.footprint_name], "PinList"
            )
            _direct_add_part_pins(
                part, pins_by_part.get(variant.export_part_name.casefold(), [])
            )
        _direct_ensure_footprints_have_metal_layer(builder)
        _direct_repair_part_footprint_pin_ids(builder)
        return builder.block()

    if part_export_plan is None:
        part_export_plan = _part_export_plan(board)
    pins_by_part = _pins_by_part(
        board.pins,
        components_by_id,
        part_names_by_component_id=part_export_plan.part_names_by_component_id,
    )
    footprint_names = _part_plan_footprint_names(board, part_export_plan)

    emitted_footprint_pads: set[str] = set()
    for footprint_name, _source_footprint_name in sorted(
        footprint_names.values(),
        key=lambda item: item[0].casefold(),
    ):
        builder.find_or_create_footprint(footprint_name)

    for variant in sorted(
        part_export_plan.variants, key=lambda item: item.export_part_name.casefold()
    ):
        part_name = variant.export_part_name
        footprint_name = variant.footprint_name
        footprint_key = footprint_name.casefold()
        if footprint_key not in emitted_footprint_pads:
            component = components_by_id.get(variant.representative_component_id)
            _direct_add_footprint_pads(
                builder,
                component,
                footprint_name,
                board,
                pad_shape_ids,
                indexes,
                source_footprint_name=variant.source_footprint_name,
                source_unit=geometry_source_unit,
                source_format=board.metadata.source_format,
            )
            emitted_footprint_pads.add(footprint_key)
        variant_components = [
            components_by_id[component_id]
            for component_id in variant.component_ids
            if component_id in components_by_id
        ]
        part = builder.find_or_create_part(part_name)
        info = part.get_block("PartInfo")
        if info is not None:
            info.replace_item(
                "Type",
                ""
                if _minimal_part_info(board)
                else _part_type_for_components(variant_components),
            )
            info.replace_item(
                "Description",
                (
                    ""
                    if _minimal_part_info(board)
                    else _part_description_for_components(
                        variant_components,
                        variant.source_footprint_name or footprint_name,
                    )
                ),
            )
            attributes = _part_attributes_for_components(
                variant, variant_components, board
            )
            if attributes:
                info.replace_item("Attributes", _direct_attribute_values(attributes))
        _direct_replace_item_before_block(
            part, "FootPrintSymbols", [footprint_name], "PinList"
        )
        _direct_add_part_pins(part, pins_by_part.get(part_name.casefold(), []))
    _direct_ensure_footprints_have_metal_layer(builder)
    _direct_repair_part_footprint_pin_ids(builder)
    return builder.block()


def _direct_add_footprint_pads(
    builder: _DirectPartsBuilder,
    component: SemanticComponent | None,
    footprint_name: str,
    board: SemanticBoard,
    pad_shape_ids: dict[tuple[str, str], str],
    indexes: _DirectPartIndexes,
    *,
    source_footprint_name: str | None = None,
    source_unit: str | None,
    normalize_rotation: float | None = None,
    source_format: str | None = None,
) -> None:
    footprint_model = indexes.footprints_by_name.get(
        (source_footprint_name or footprint_name).casefold()
    )
    if _component_prefers_component_footprint_pads(
        component, source_format
    ) and _direct_add_component_footprint_pads(
        builder,
        component,
        footprint_name,
        board,
        pad_shape_ids,
        indexes,
        source_unit=source_unit,
        normalize_rotation=normalize_rotation,
        source_format=source_format,
    ):
        return
    if _direct_add_package_footprint_pads(
        builder,
        footprint_model,
        footprint_name,
        component=component,
        pads_by_id=indexes.pads_by_id,
        pins_by_id=indexes.pins_by_id,
        source_unit=source_unit,
        source_format=source_format,
    ):
        return
    if component is None:
        return

    builder.find_or_create_footprint(footprint_name)
    _direct_add_component_footprint_pads(
        builder,
        component,
        footprint_name,
        board,
        pad_shape_ids,
        indexes,
        source_unit=source_unit,
        normalize_rotation=normalize_rotation,
        source_format=source_format,
    )


def _direct_add_component_footprint_pads(
    builder: _DirectPartsBuilder,
    component: SemanticComponent | None,
    footprint_name: str,
    board: SemanticBoard,
    pad_shape_ids: dict[tuple[str, str], str],
    indexes: _DirectPartIndexes,
    *,
    source_unit: str | None,
    normalize_rotation: float | None = None,
    source_format: str | None = None,
) -> bool:
    if component is None:
        return False
    selected_pads = _select_component_footprint_pads(
        component,
        board,
        pad_shape_ids,
        indexes,
    )
    if not selected_pads:
        return False

    footprint = builder.find_or_create_footprint(footprint_name)
    template_by_shape: dict[str, str] = {}

    for selected in selected_pads:
        pad = selected.pad
        semantic_shape_id = selected.semantic_shape_id
        shape = indexes.shapes_by_id.get(semantic_shape_id)
        if shape is None:
            continue

        template_id = template_by_shape.get(semantic_shape_id)
        if template_id is None:
            template_id = str(len(template_by_shape) + 1)
            payload = _shape_geometry_payload(
                shape, template_id, source_unit=source_unit
            )
            if payload is None:
                continue
            template_by_shape[semantic_shape_id] = template_id
            _direct_add_pad_template_geometry(builder, footprint, template_id, payload)

        x, y = _relative_pad_location(
            component,
            pad,
            source_unit=source_unit,
            normalize_rotation=normalize_rotation,
            source_format=source_format,
        )
        rotation = _format_footprint_pad_rotation(
            pad,
            component,
            normalize_rotation=normalize_rotation,
            source_format=source_format,
        )
        _direct_add_footprint_pad(
            builder,
            footprint,
            selected.pin_name,
            template_id,
            x,
            y,
            rotation=rotation,
            flip_x="-flipX" in _pad_flip_options(pad),
            flip_y="-flipY" in _pad_flip_options(pad),
        )
    return bool(template_by_shape)


def _direct_add_package_footprint_pads(
    builder: _DirectPartsBuilder,
    footprint_model: Any,
    footprint_name: str,
    *,
    component: SemanticComponent | None = None,
    pads_by_id: dict[str, SemanticPad] | None = None,
    pins_by_id: dict[str, SemanticPin] | None = None,
    source_unit: str | None,
    source_format: str | None = None,
) -> bool:
    geometry = getattr(footprint_model, "geometry", None)
    if not geometry:
        return False
    package_pads = geometry.get("pads")
    if not isinstance(package_pads, list):
        return False

    footprint = builder.find_or_create_footprint(footprint_name)
    pin_name_aliases = _package_pin_name_aliases(
        component,
        package_pads,
        pads_by_id or {},
        pins_by_id or {},
        source_unit=source_unit,
        source_format=source_format,
    )
    template_by_signature: dict[tuple[str, tuple[str, ...]], str] = {}
    emitted = False
    emitted_pad_count = 0
    for package_pad in package_pads:
        if not isinstance(package_pad, dict):
            continue
        shape = package_pad.get("shape")
        if not isinstance(shape, dict):
            continue
        signature = _geometry_signature(shape, source_unit=source_unit)
        if signature is None:
            continue
        template_id = template_by_signature.get(signature)
        if template_id is None:
            template_id = str(len(template_by_signature) + 1)
            payload = _outline_geometry_payload(
                shape, template_id, source_unit=source_unit
            )
            if payload is None:
                continue
            template_by_signature[signature] = template_id
            _direct_add_pad_template_geometry(builder, footprint, template_id, payload)

        point = _point_tuple(package_pad.get("position"), source_unit=source_unit)
        if point is None:
            continue
        pin_name = _package_pad_pin_name(
            package_pad, pin_name_aliases, emitted_pad_count + 1
        )
        _direct_add_footprint_pad(
            builder,
            footprint,
            pin_name,
            template_id,
            point[0],
            point[1],
            rotation=_format_rotation(
                package_pad.get("rotation"), source_format=source_format
            ),
        )
        emitted = True
        emitted_pad_count += 1
    return emitted


def _direct_add_pad_template_geometry(
    builder: _DirectPartsBuilder,
    footprint: AuroraBlock,
    template_id: str,
    payload: str,
) -> None:
    pad_template = builder.find_or_create_pad_template(footprint, template_id)
    geometry_list = pad_template.get_block("GeometryList")
    if geometry_list is None:
        geometry_list = pad_template.add_block("GeometryList")
    if geometry_list.children:
        return
    geometry = parse_geometry_option([payload])
    if geometry is not None:
        geometry_list.append(geometry.node)


def _direct_add_footprint_pad(
    builder: _DirectPartsBuilder,
    footprint: AuroraBlock,
    pin_name: str,
    template_id: str,
    x: float,
    y: float,
    *,
    rotation: str | float | int | None = None,
    flip_x: bool = False,
    flip_y: bool = False,
) -> None:
    metal_layer = builder.find_or_create_footprint_metal_layer(footprint, "top", "1")
    pad_block = AuroraBlock("PartPad")
    pad_block.add_item("PadIDs", [pin_name, template_id])
    pad_block.add_item(
        "Location",
        _direct_location_values(x, y, rotation=rotation, flip_x=flip_x, flip_y=flip_y),
    )
    metal_layer.append(pad_block)


def _direct_add_part_pins(part: AuroraBlock, pin_names: list[str]) -> None:
    pins = part.get_block("PinList")
    if pins is None:
        pins = part.add_block("PinList")
    for pin_name in pin_names:
        fields = split_reserved(
            strip_wrapping_pair(_part_pin_tuple(pin_name), "(", ")"), delimiters=","
        )
        while len(fields) < 4:
            fields.append("")
        pin = AuroraBlock("Pin")
        pin.add_item("DefData", ",".join(fields[:4]))
        pins.append(pin)


def _direct_ensure_footprints_have_metal_layer(builder: _DirectPartsBuilder) -> None:
    for footprint in builder.footprints_by_name.values():
        if not footprint.get_blocks("MetalLayer"):
            builder.find_or_create_footprint_metal_layer(footprint, "top", "1")


def _direct_repair_part_footprint_pin_ids(builder: _DirectPartsBuilder) -> None:
    repaired = 0
    for part in builder.parts_by_name.values():
        pin_numbers = _direct_part_pin_numbers(part)
        missing_pin_names: list[str] = []
        for footprint_name in _direct_part_footprint_names(part):
            footprint = builder.footprints_by_name.get(footprint_name.casefold())
            if footprint is None:
                continue
            for pad_id in _direct_footprint_part_pad_ids(footprint):
                key = pad_id.casefold()
                if key in pin_numbers:
                    continue
                pin_numbers.add(key)
                missing_pin_names.append(pad_id)
        if missing_pin_names:
            _direct_add_part_pins(part, missing_pin_names)
            repaired += len(missing_pin_names)
    if repaired:
        logger.info(
            "Repaired AuroraDB part footprint pin references: added_pins=%s", repaired
        )


def _direct_part_footprint_names(part: AuroraBlock) -> list[str]:
    item = part.get_item("FootPrintSymbols")
    return list(item.values) if item else []


def _direct_part_pin_numbers(part: AuroraBlock) -> set[str]:
    pins = part.get_block("PinList")
    if pins is None:
        return set()
    pin_numbers: set[str] = set()
    for pin in pins.get_blocks("Pin"):
        item = pin.get_item("DefData")
        if item is None or not item.values:
            continue
        fields = split_reserved(
            strip_wrapping_pair(item.values[0], "(", ")"), delimiters=","
        )
        if fields:
            pin_numbers.add(strip_wrapping_quotes(fields[0]).casefold())
    return pin_numbers


def _direct_footprint_part_pad_ids(footprint: AuroraBlock) -> list[str]:
    pad_ids: list[str] = []
    seen: set[str] = set()
    for metal_layer in footprint.get_blocks("MetalLayer"):
        for part_pad in metal_layer.get_blocks("PartPad"):
            _direct_collect_part_pad_id(part_pad, pad_ids, seen)
        for logic_layer in metal_layer.get_blocks("LogicLayer"):
            for part_pad in logic_layer.get_blocks("PartPad"):
                _direct_collect_part_pad_id(part_pad, pad_ids, seen)
    return pad_ids


def _direct_collect_part_pad_id(
    part_pad: AuroraBlock, pad_ids: list[str], seen: set[str]
) -> None:
    item = part_pad.get_item("PadIDs")
    if item is None or not item.values:
        return
    pad_id = strip_wrapping_quotes(item.values[0])
    if not pad_id:
        return
    key = pad_id.casefold()
    if key in seen:
        return
    seen.add(key)
    pad_ids.append(pad_id)


def _footprint_pad_commands(
    component: SemanticComponent | None,
    footprint_name: str,
    board: SemanticBoard,
    pad_shape_ids: dict[tuple[str, str], str],
    *,
    source_footprint_name: str | None = None,
    source_unit: str | None,
    normalize_rotation: float | None = None,
    source_format: str | None = None,
) -> list[str]:
    footprint = _footprint_by_name(board, source_footprint_name or footprint_name)
    pads_by_id = {pad.id: pad for pad in board.pads}
    pins_by_id = {pin.id: pin for pin in board.pins}
    shapes_by_id = {shape.id: shape for shape in board.shapes}
    if _component_prefers_component_footprint_pads(component, source_format):
        component_pad_commands = _component_footprint_pad_commands(
            component,
            footprint_name,
            board,
            pad_shape_ids,
            pads_by_id,
            pins_by_id,
            shapes_by_id,
            source_unit=source_unit,
            normalize_rotation=normalize_rotation,
            source_format=source_format,
        )
        if component_pad_commands:
            return component_pad_commands
    package_pad_commands = _package_footprint_pad_commands(
        footprint,
        footprint_name,
        component=component,
        pads_by_id=pads_by_id,
        pins_by_id=pins_by_id,
        source_unit=source_unit,
        source_format=source_format,
    )
    if package_pad_commands:
        return package_pad_commands
    if component is None:
        return []

    component_pad_commands = _component_footprint_pad_commands(
        component,
        footprint_name,
        board,
        pad_shape_ids,
        pads_by_id,
        pins_by_id,
        shapes_by_id,
        source_unit=source_unit,
        normalize_rotation=normalize_rotation,
        source_format=source_format,
    )
    if component_pad_commands:
        return component_pad_commands
    return []


def _component_footprint_pad_commands(
    component: SemanticComponent | None,
    footprint_name: str,
    board: SemanticBoard,
    pad_shape_ids: dict[tuple[str, str], str],
    pads_by_id: dict[str, SemanticPad],
    pins_by_id: dict[str, SemanticPin],
    shapes_by_id: dict[str, SemanticShape],
    *,
    source_unit: str | None,
    normalize_rotation: float | None = None,
    source_format: str | None = None,
) -> list[str]:
    if component is None:
        return []
    selected_pads = _select_component_footprint_pads(
        component,
        board,
        pad_shape_ids,
        _DirectPartIndexes(
            pads_by_id=pads_by_id,
            pins_by_id=pins_by_id,
            shapes_by_id=shapes_by_id,
            footprints_by_name={},
        ),
    )
    if not selected_pads:
        return []

    template_by_shape: dict[str, str] = {}
    template_commands: list[str] = []
    pad_commands: list[str] = []

    for selected in selected_pads:
        pad = selected.pad
        semantic_shape_id = selected.semantic_shape_id
        shape = shapes_by_id.get(semantic_shape_id)
        if shape is None:
            continue

        template_id = template_by_shape.get(semantic_shape_id)
        if template_id is None:
            template_id = str(len(template_by_shape) + 1)
            payload = _shape_geometry_payload(
                shape, template_id, source_unit=source_unit
            )
            if payload is None:
                continue
            template_by_shape[semantic_shape_id] = template_id
            template_commands.append(
                f"library add -pad <{template_id}> -footprint <{_quote_aaf(footprint_name)}>"
            )
            template_commands.append(
                f"library add -g <{payload}> -pad <{template_id}> -footprint <{_quote_aaf(footprint_name)}>"
            )

        x, y = _relative_pad_location(
            component,
            pad,
            source_unit=source_unit,
            normalize_rotation=normalize_rotation,
            source_format=source_format,
        )
        rotation = _format_footprint_pad_rotation(
            pad,
            component,
            normalize_rotation=normalize_rotation,
            source_format=source_format,
        )
        flip_options = _pad_flip_options(pad)
        pad_commands.append(
            "library add "
            f"-fpn <{_aaf_atom(selected.pin_name)}> "
            f"-pad <{template_id}> "
            f"-location <({_format_number(x)},{_format_number(y)})> "
            f"-rotation <{rotation}> "
            f"{flip_options}"
            "-layer <top:1> "
            f"-footprint <{_quote_aaf(footprint_name)}>"
        )

    return [*template_commands, *pad_commands]


def _select_component_footprint_pads(
    component: SemanticComponent,
    board: SemanticBoard,
    pad_shape_ids: dict[tuple[str, str], str],
    indexes: _DirectPartIndexes,
) -> list[_SelectedFootprintPad]:
    metal_layer_keys, layer_sides = _metal_layer_lookups(board.layers)
    selected: dict[str, tuple[tuple[int, int], _SelectedFootprintPad]] = {}
    for pad_index, pad_id in enumerate(component.pad_ids):
        pad = indexes.pads_by_id.get(pad_id)
        if pad is None or not pad.layer_name:
            continue
        if pad.layer_name.casefold() not in metal_layer_keys:
            continue
        semantic_shape_id = _pad_shape_id_for_layer(pad, pad_shape_ids, pad.layer_name)
        if not semantic_shape_id or semantic_shape_id not in indexes.shapes_by_id:
            continue
        pin_name = _pad_pin_name(pad, indexes.pins_by_id)
        if not pin_name:
            continue
        score = (
            _component_footprint_pad_score(component, pad, layer_sides),
            -pad_index,
        )
        key = pin_name.casefold()
        candidate = _SelectedFootprintPad(
            pin_name=pin_name, pad=pad, semantic_shape_id=semantic_shape_id
        )
        current = selected.get(key)
        if current is None or score > current[0]:
            selected[key] = (score, candidate)
    return [
        item[1]
        for item in sorted(
            selected.values(),
            key=lambda entry: _pin_sort_key(entry[1].pin_name),
        )
    ]


def _metal_layer_lookups(
    layers: list[SemanticLayer],
) -> tuple[set[str], dict[str, str | None]]:
    keys: set[str] = set()
    sides: dict[str, str | None] = {}
    for layer in layers:
        role = (layer.role or "").casefold()
        layer_type = (layer.layer_type or "").casefold()
        if role not in {"signal", "plane"} and layer_type not in {"signal", "plane"}:
            continue
        key = layer.name.casefold()
        keys.add(key)
        sides[key] = layer.side
    return keys, sides


def _component_footprint_pad_score(
    component: SemanticComponent,
    pad: SemanticPad,
    layer_sides: dict[str, str | None],
) -> int:
    score = 0
    geometry = pad.geometry
    if geometry.get("source") != "package":
        score += 1000
    if component.layer_name and pad.layer_name:
        if component.layer_name.casefold() == pad.layer_name.casefold():
            score += 200
    side = layer_sides.get((pad.layer_name or "").casefold())
    if component.side and side == component.side:
        score += 100
    elif side in {"top", "bottom"}:
        score += 50
    if pad.net_id:
        score += 1
    return score


def _source_prefers_component_footprint_pads(source_format: str | None) -> bool:
    return False


def _component_prefers_component_footprint_pads(
    component: SemanticComponent | None, source_format: str | None
) -> bool:
    if _source_prefers_component_footprint_pads(source_format):
        return True
    if (source_format or "").casefold() != "odbpp" or component is None:
        return False
    return _component_has_xpedition_pad_origin(component)


def _board_prefers_component_footprint_pads(board: SemanticBoard) -> bool:
    if _source_prefers_component_footprint_pads(board.metadata.source_format):
        return True
    if (board.metadata.source_format or "").casefold() != "odbpp":
        return False
    return any(
        _component_has_xpedition_pad_origin(component) for component in board.components
    )


def _component_has_xpedition_pad_origin(component: SemanticComponent) -> bool:
    attribute_keys = {key.casefold() for key in component.attributes}
    return bool(attribute_keys & {"refloc", "component_ai_origin"})


def _source_uses_component_pad_shape_variants(source_format: str | None) -> bool:
    return (source_format or "").casefold() in {"odbpp"}


def _source_exports_footprint_layer_geometry(source_format: str | None) -> bool:
    return not _source_prefers_component_footprint_pads(source_format)


def _board_exports_footprint_layer_geometry(board: SemanticBoard) -> bool:
    return not _board_prefers_component_footprint_pads(board)


def _footprint_has_package_pads(footprint: Any) -> bool:
    geometry = getattr(footprint, "geometry", None)
    if not geometry:
        return False
    package_pads = geometry.get("pads")
    return isinstance(package_pads, list) and bool(package_pads)


def _package_footprint_pad_commands(
    footprint: Any,
    footprint_name: str,
    *,
    component: SemanticComponent | None = None,
    pads_by_id: dict[str, SemanticPad] | None = None,
    pins_by_id: dict[str, SemanticPin] | None = None,
    source_unit: str | None,
    source_format: str | None = None,
) -> list[str]:
    geometry = getattr(footprint, "geometry", None)
    if not geometry:
        return []
    package_pads = geometry.get("pads")
    if not isinstance(package_pads, list):
        return []

    pin_name_aliases = _package_pin_name_aliases(
        component,
        package_pads,
        pads_by_id or {},
        pins_by_id or {},
        source_unit=source_unit,
        source_format=source_format,
    )
    template_by_signature: dict[tuple[str, tuple[str, ...]], str] = {}
    template_commands: list[str] = []
    pad_commands: list[str] = []
    for package_pad in package_pads:
        if not isinstance(package_pad, dict):
            continue
        shape = package_pad.get("shape")
        if not isinstance(shape, dict):
            continue
        signature = _geometry_signature(shape, source_unit=source_unit)
        if signature is None:
            continue
        template_id = template_by_signature.get(signature)
        if template_id is None:
            template_id = str(len(template_by_signature) + 1)
            payload = _outline_geometry_payload(
                shape, template_id, source_unit=source_unit
            )
            if payload is None:
                continue
            template_by_signature[signature] = template_id
            template_commands.append(
                f"library add -pad <{template_id}> -footprint <{_quote_aaf(footprint_name)}>"
            )
            template_commands.append(
                f"library add -g <{payload}> -pad <{template_id}> -footprint <{_quote_aaf(footprint_name)}>"
            )

        point = _point_tuple(package_pad.get("position"), source_unit=source_unit)
        if point is None:
            continue
        rotation = _format_rotation(
            package_pad.get("rotation"), source_format=source_format
        )
        pin_name = _package_pad_pin_name(
            package_pad, pin_name_aliases, len(pad_commands) + 1
        )
        pad_commands.append(
            "library add "
            f"-fpn <{_aaf_atom(pin_name)}> "
            f"-pad <{template_id}> "
            f"-location <({_format_number(point[0])},{_format_number(point[1])})> "
            f"-rotation <{rotation}> "
            "-layer <top:1> "
            f"-footprint <{_quote_aaf(footprint_name)}>"
        )

    return [*template_commands, *pad_commands]


def _package_pin_name_aliases(
    component: SemanticComponent | None,
    package_pads: list[Any],
    pads_by_id: dict[str, SemanticPad],
    pins_by_id: dict[str, SemanticPin],
    *,
    source_unit: str | None,
    source_format: str | None = None,
) -> dict[str, str]:
    if component is None:
        return {}
    aliases: dict[str, str] = {}
    component_pin_names = [
        _pin_name(pin)
        for pin_id in component.pin_ids
        if (pin := pins_by_id.get(pin_id)) is not None
    ]
    for package_pad in package_pads:
        if not isinstance(package_pad, dict):
            continue
        raw_name = package_pad.get("pin_name")
        if raw_name in {None, ""}:
            continue
        source_pin_index = _int_value(package_pad.get("source_pin_index"))
        if source_pin_index is not None and 0 <= source_pin_index < len(
            component_pin_names
        ):
            aliases[str(raw_name).casefold()] = component_pin_names[source_pin_index]

    position_aliases = _package_pin_position_aliases(
        component,
        package_pads,
        pads_by_id,
        pins_by_id,
        source_unit=source_unit,
        source_format=source_format,
    )
    aliases.update(position_aliases)

    for pad_id in component.pad_ids:
        pad = pads_by_id.get(pad_id)
        if pad is None or not pad.geometry:
            continue
        package_pin = pad.geometry.get("package_pin")
        if package_pin in {None, ""}:
            continue
        pin_name = _pad_pin_name(pad, pins_by_id)
        if not pin_name:
            continue
        aliases.setdefault(str(package_pin).casefold(), pin_name)
    return aliases


def _package_pin_position_aliases(
    component: SemanticComponent,
    package_pads: list[Any],
    pads_by_id: dict[str, SemanticPad],
    pins_by_id: dict[str, SemanticPin],
    *,
    source_unit: str | None,
    source_format: str | None = None,
) -> dict[str, str]:
    pins_by_position: dict[tuple[int, int], str] = {}
    for pad_id in component.pad_ids:
        pad = pads_by_id.get(pad_id)
        if (
            pad is None
            or not pad.pin_id
            or component.location is None
            or pad.position is None
        ):
            continue
        pin_name = _pad_pin_name(pad, pins_by_id)
        if not pin_name:
            continue
        x, y = _relative_pad_location(
            component, pad, source_unit=source_unit, source_format=source_format
        )
        pins_by_position.setdefault(_location_match_key(x, y), pin_name)

    aliases: dict[str, str] = {}
    for package_pad in package_pads:
        if not isinstance(package_pad, dict):
            continue
        raw_name = package_pad.get("pin_name")
        if raw_name in {None, ""}:
            continue
        point = _point_tuple(package_pad.get("position"), source_unit=source_unit)
        if point is None:
            continue
        pin_name = pins_by_position.get(_location_match_key(point[0], point[1]))
        if pin_name:
            aliases[str(raw_name).casefold()] = pin_name
    return aliases


def _location_match_key(x: float, y: float) -> tuple[int, int]:
    tolerance = AEDB_COMPONENT_MATCH_TOLERANCE_MIL
    return (round(float(x) / tolerance), round(float(y) / tolerance))


def _int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _package_pad_pin_name(
    package_pad: dict[str, Any],
    pin_name_aliases: dict[str, str] | None,
    fallback_index: int,
) -> str:
    raw_name = package_pad.get("pin_name")
    pin_name = str(raw_name) if raw_name not in {None, ""} else str(fallback_index)
    if pin_name_aliases:
        return pin_name_aliases.get(pin_name.casefold(), pin_name)
    return pin_name


def _part_names(board: SemanticBoard) -> set[str]:
    names = {_component_part_name(component) for component in board.components}
    return {name for name in names if name}


def _part_export_plan(board: SemanticBoard) -> _PartExportPlan:
    footprint_by_id = {
        footprint.id: footprint.name for footprint in board.footprints if footprint.name
    }
    footprint_by_name = {
        footprint.name.casefold(): footprint.name
        for footprint in board.footprints
        if footprint.name
    }
    groups: dict[str, dict[str, list[SemanticComponent]]] = {}
    part_names: dict[str, str] = {}
    footprint_names: dict[tuple[str, str], str] = {}
    use_pad_shape_variants = _source_uses_component_pad_shape_variants(
        board.metadata.source_format
    )
    component_pad_signatures: dict[
        str, tuple[tuple[str, str, str, tuple[str, ...]], ...]
    ] = {}
    default_pad_signatures: dict[
        str, tuple[tuple[str, str, str, tuple[str, ...]], ...]
    ] = {}
    export_footprint_names: dict[
        tuple[str, tuple[tuple[str, str, str, tuple[str, ...]], ...]], str
    ] = {}
    seen_footprint_names = {name.casefold() for name in _footprint_names(board)}

    if use_pad_shape_variants:
        pad_shape_ids = _pad_shape_ids_by_definition(board)
        indexes = _DirectPartIndexes(
            pads_by_id={pad.id: pad for pad in board.pads},
            pins_by_id={pin.id: pin for pin in board.pins},
            shapes_by_id={shape.id: shape for shape in board.shapes},
            footprints_by_name={
                footprint.name.casefold(): footprint
                for footprint in board.footprints
                if footprint.name
            },
        )
        signature_counts: dict[
            str, dict[tuple[tuple[str, str, str, tuple[str, ...]], ...], int]
        ] = {}
        for component in board.components:
            prefer_component_pads = _component_prefers_component_footprint_pads(
                component, board.metadata.source_format
            )
            footprint_name = _component_footprint_name(
                component, footprint_by_id, footprint_by_name
            ) or _component_part_name(component)
            footprint_key = footprint_name.casefold()
            if not prefer_component_pads and _footprint_has_package_pads(
                indexes.footprints_by_name.get(footprint_key)
            ):
                signature = ()
            else:
                signature = _component_footprint_shape_signature(
                    component,
                    board,
                    pad_shape_ids,
                    indexes,
                    source_unit=_part_geometry_source_unit(board),
                    source_format=board.metadata.source_format,
                )
            component_pad_signatures[component.id] = signature
            signature_counts.setdefault(footprint_key, {}).setdefault(signature, 0)
            signature_counts[footprint_key][signature] += 1
        default_pad_signatures = {
            footprint_key: max(
                counts,
                key=lambda signature: (
                    counts[signature],
                    _footprint_shape_signature_sort_text(signature),
                ),
            )
            for footprint_key, counts in signature_counts.items()
        }

    for component in board.components:
        source_part_name = _component_part_name(component)
        footprint_name = (
            _component_footprint_name(component, footprint_by_id, footprint_by_name)
            or source_part_name
        )
        part_key = source_part_name.casefold()
        footprint_key = footprint_name.casefold()
        part_names.setdefault(part_key, source_part_name)
        footprint_names.setdefault((part_key, footprint_key), footprint_name)
        groups.setdefault(part_key, {}).setdefault(footprint_key, []).append(component)

    seen_export_names: set[str] = set()
    part_names_by_component_id: dict[str, str] = {}
    variants: list[_PartExportVariant] = []
    canonical_footprint_names: dict[str, str] = {}
    for part_key in sorted(groups, key=lambda key: part_names[key].casefold()):
        footprint_groups = groups[part_key]
        source_part_name = part_names[part_key]
        needs_footprint_variant = len(footprint_groups) > 1
        for footprint_key in sorted(
            footprint_groups,
            key=lambda key: footprint_names[(part_key, key)].casefold(),
        ):
            components = footprint_groups[footprint_key]
            source_footprint_name = footprint_names[(part_key, footprint_key)]
            shape_groups = _part_shape_variant_groups(
                components, component_pad_signatures
            )
            needs_pad_shape_variant = len(shape_groups) > 1
            for shape_signature, shape_components in shape_groups:
                export_footprint_name = _part_export_footprint_name(
                    source_footprint_name,
                    footprint_key,
                    shape_signature,
                    default_pad_signatures.get(footprint_key, shape_signature),
                    export_footprint_names,
                    seen_footprint_names,
                )
                export_footprint_name = canonical_footprint_names.setdefault(
                    export_footprint_name.casefold(), export_footprint_name
                )
                export_part_name = _part_export_name(
                    source_part_name,
                    export_footprint_name,
                    needs_footprint_variant=needs_footprint_variant
                    or needs_pad_shape_variant,
                    seen=seen_export_names,
                )
                for component in shape_components:
                    part_names_by_component_id[component.id] = export_part_name
                variants.append(
                    _PartExportVariant(
                        export_part_name=export_part_name,
                        source_part_name=source_part_name,
                        footprint_name=export_footprint_name,
                        representative_component_id=shape_components[0].id,
                        component_ids=[component.id for component in shape_components],
                        source_footprint_name=source_footprint_name,
                    )
                )
    return _PartExportPlan(
        part_names_by_component_id=part_names_by_component_id, variants=variants
    )


def _component_footprint_shape_signature(
    component: SemanticComponent,
    board: SemanticBoard,
    pad_shape_ids: dict[tuple[str, str], str],
    indexes: _DirectPartIndexes,
    *,
    source_unit: str | None,
    source_format: str | None,
) -> tuple[tuple[str, str, str, tuple[str, ...]], ...]:
    selected_pads = _select_component_footprint_pads(
        component, board, pad_shape_ids, indexes
    )
    result: list[tuple[str, str, str, tuple[str, ...]]] = []
    for selected in selected_pads:
        shape = indexes.shapes_by_id.get(selected.semantic_shape_id)
        if shape is None:
            continue
        x, y = _relative_pad_location(
            component,
            selected.pad,
            source_unit=source_unit,
            source_format=source_format,
        )
        rotation = _format_footprint_pad_rotation(
            selected.pad,
            component,
            source_format=source_format,
        )
        flip_options = _pad_flip_options(selected.pad).strip()
        result.append(
            (
                selected.pin_name.casefold(),
                shape.kind.casefold(),
                _shape_auroradb_type(shape).casefold(),
                (
                    *(_shape_signature_value(value) for value in shape.values),
                    f"x={_footprint_signature_number(x)}",
                    f"y={_footprint_signature_number(y)}",
                    f"rotation={rotation}",
                    f"flip={flip_options}",
                ),
            )
        )
    return tuple(sorted(result, key=lambda item: _pin_sort_key(item[0])))


def _part_shape_variant_groups(
    components: list[SemanticComponent],
    component_pad_signatures: dict[
        str, tuple[tuple[str, str, str, tuple[str, ...]], ...]
    ],
) -> list[
    tuple[tuple[tuple[str, str, str, tuple[str, ...]], ...], list[SemanticComponent]]
]:
    if not component_pad_signatures:
        return [((), components)]
    groups: dict[
        tuple[tuple[str, str, str, tuple[str, ...]], ...], list[SemanticComponent]
    ] = {}
    for component in components:
        signature = component_pad_signatures.get(component.id, ())
        groups.setdefault(signature, []).append(component)
    return [
        (signature, groups[signature])
        for signature in sorted(
            groups,
            key=lambda signature: (
                -len(groups[signature]),
                _footprint_shape_signature_sort_text(signature),
            ),
        )
    ]


def _part_export_footprint_name(
    source_footprint_name: str,
    footprint_key: str,
    shape_signature: tuple[tuple[str, str, str, tuple[str, ...]], ...],
    default_shape_signature: tuple[tuple[str, str, str, tuple[str, ...]], ...],
    export_footprint_names: dict[
        tuple[str, tuple[tuple[str, str, str, tuple[str, ...]], ...]], str
    ],
    seen_footprint_names: set[str],
) -> str:
    if shape_signature == default_shape_signature:
        return source_footprint_name
    key = (footprint_key, shape_signature)
    export_name = export_footprint_names.get(key)
    if export_name is not None:
        return export_name
    suffix = (
        len([entry for entry in export_footprint_names if entry[0] == footprint_key])
        + 2
    )
    export_name = _unique_export_footprint_name(
        f"{source_footprint_name}__pad{suffix}", seen_footprint_names
    )
    export_footprint_names[key] = export_name
    return export_name


def _footprint_shape_signature_sort_text(
    signature: tuple[tuple[str, str, str, tuple[str, ...]], ...],
) -> str:
    return "|".join(
        f"{pin}:{kind}:{aurora_type}:{','.join(values)}"
        for pin, kind, aurora_type, values in signature
    )


def _shape_signature_value(value: str | float | int) -> str:
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def _footprint_signature_number(value: float) -> str:
    if abs(value) < 5e-7:
        return "0"
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _part_export_name(
    source_part_name: str,
    footprint_name: str,
    *,
    needs_footprint_variant: bool,
    seen: set[str],
) -> str:
    if needs_footprint_variant:
        candidate = f"{source_part_name}_{_standardize_name(footprint_name)}"
    else:
        candidate = source_part_name
    return _unique_export_part_name(candidate, seen)


def _unique_export_part_name(name: str, seen: set[str]) -> str:
    candidate = name or "Unknown"
    suffix = 2
    while candidate.casefold() in seen:
        candidate = f"{name or 'Unknown'}_{suffix}"
        suffix += 1
    seen.add(candidate.casefold())
    return candidate


def _unique_export_footprint_name(name: str, seen: set[str]) -> str:
    candidate = name or "Unknown"
    suffix = 2
    while candidate.casefold() in seen:
        candidate = f"{name or 'Unknown'}_{suffix}"
        suffix += 1
    seen.add(candidate.casefold())
    return candidate


def _components_for_part(
    part_name: str, components: list[SemanticComponent]
) -> list[SemanticComponent]:
    return [
        component
        for component in components
        if _component_part_name(component).casefold() == part_name.casefold()
    ]


def _part_type(part_name: str, board: SemanticBoard) -> str:
    return _part_type_for_components(_components_for_part(part_name, board.components))


def _part_description(part_name: str, board: SemanticBoard, footprint_name: str) -> str:
    return _part_description_for_components(
        _components_for_part(part_name, board.components), footprint_name
    )


def _part_type_for_components(components: list[SemanticComponent]) -> str:
    values = sorted(
        {
            str(component.value)
            for component in components
            if component.value not in {None, ""}
        },
        key=str.casefold,
    )
    return values[0] if len(values) == 1 else ""


def _part_description_for_components(
    components: list[SemanticComponent], footprint_name: str
) -> str:
    package_names = {
        str(component.package_name)
        for component in components
        if component.package_name not in {None, ""}
    }
    if len(package_names) == 1:
        return next(iter(package_names))
    return footprint_name


def _part_attributes(
    part_name: str, board: SemanticBoard, footprint_name: str
) -> dict[str, str]:
    components = _components_for_part(part_name, board.components)
    variant = _PartExportVariant(
        export_part_name=part_name,
        source_part_name=part_name,
        footprint_name=footprint_name,
        representative_component_id=components[0].id if components else "",
        component_ids=[component.id for component in components],
    )
    return _part_attributes_for_components(variant, components, board)


def _part_attributes_for_components(
    variant: _PartExportVariant,
    components: list[SemanticComponent],
    board: SemanticBoard,
) -> dict[str, str]:
    if _minimal_part_info(board):
        return _minimal_component_part_attributes(components)

    source_footprint_name = variant.source_footprint_name or variant.footprint_name
    attributes: dict[str, str] = {
        "PART_NAME": variant.source_part_name,
        "FOOTPRINT": source_footprint_name,
        "COMPONENT_COUNT": str(len(components)),
    }
    if variant.export_part_name != variant.source_part_name:
        attributes.setdefault("EXPORT_PART_NAME", variant.export_part_name)
    if variant.footprint_name != source_footprint_name:
        attributes.setdefault("EXPORT_FOOTPRINT", variant.footprint_name)
    common = _common_component_attributes(components)
    for key, value in common.items():
        if value not in {None, ""}:
            attributes.setdefault(str(key), str(value))
    values = sorted(
        {
            str(component.value)
            for component in components
            if component.value not in {None, ""}
        },
        key=str.casefold,
    )
    if len(values) == 1:
        attributes.setdefault("VALUE", values[0])
    elif values:
        attributes.setdefault("VALUE_SET", "|".join(values))
    packages = sorted(
        {
            str(component.package_name)
            for component in components
            if component.package_name not in {None, ""}
        },
        key=str.casefold,
    )
    if len(packages) == 1:
        attributes.setdefault("PACKAGE_NAME", packages[0])
    elif packages:
        attributes.setdefault("PACKAGE_NAME_SET", "|".join(packages))
    footprint = _footprints_by_name(board).get(source_footprint_name.casefold())
    footprint_attributes = (
        getattr(footprint, "attributes", {}) if footprint is not None else {}
    )
    if isinstance(footprint_attributes, dict):
        for key, value in footprint_attributes.items():
            if value not in {None, ""}:
                attributes.setdefault(str(key), str(value))
    return dict(sorted(attributes.items(), key=lambda item: item[0].casefold()))


def _minimal_part_info(board: SemanticBoard) -> bool:
    return (board.metadata.source_format or "").casefold() == "alg"


def _minimal_component_part_attributes(
    components: list[SemanticComponent],
) -> dict[str, str]:
    value = _first_component_value(components)
    part_number = _first_component_attribute(components, "part_number")
    return {
        "Value": value.replace("-", "_") if value else "",
        "PART_NUMBER": part_number or "",
    }


def _first_component_value(components: list[SemanticComponent]) -> str:
    for component in components:
        if component.value not in {None, ""}:
            return str(component.value)
    return ""


def _first_component_attribute(
    components: list[SemanticComponent], attribute_name: str
) -> str:
    for component in components:
        attributes = getattr(component, "attributes", {})
        if not isinstance(attributes, dict):
            continue
        value = attributes.get(attribute_name)
        if value not in {None, ""}:
            return str(value)
    return ""


def _common_component_attributes(components: list[SemanticComponent]) -> dict[str, str]:
    common: dict[str, str] = {}
    initialized = False
    for component in components:
        component_attributes = getattr(component, "attributes", {})
        if not isinstance(component_attributes, dict):
            continue
        normalized = {
            str(key): str(value)
            for key, value in component_attributes.items()
            if value not in {None, ""}
        }
        if not initialized:
            common = normalized
            initialized = True
            continue
        common = {
            key: value for key, value in common.items() if normalized.get(key) == value
        }
    return common if initialized else {}


def _part_attribute_options(attributes: dict[str, str]) -> str:
    if not attributes:
        return ""
    values = " ".join(
        f"<({_tuple_value(key)},{_tuple_value(value)})>"
        for key, value in attributes.items()
        if key
    )
    return f" -a {values}" if values else ""


def _footprint_names(board: SemanticBoard) -> set[str]:
    names = {footprint.name for footprint in board.footprints if footprint.name}
    footprint_by_id = {
        footprint.id: footprint.name for footprint in board.footprints if footprint.name
    }
    footprint_by_name = {
        footprint.name.casefold(): footprint.name
        for footprint in board.footprints
        if footprint.name
    }
    for component in board.components:
        if component.footprint_id and component.footprint_id in footprint_by_id:
            continue
        fallback_name = _component_footprint_name(
            component, footprint_by_id, footprint_by_name
        )
        if fallback_name:
            names.add(fallback_name)
    return names


def _part_plan_footprint_names(
    board: SemanticBoard,
    part_export_plan: _PartExportPlan,
) -> dict[str, tuple[str, str]]:
    result = {name.casefold(): (name, name) for name in _footprint_names(board)}
    for variant in part_export_plan.variants:
        source_footprint_name = variant.source_footprint_name or variant.footprint_name
        result[variant.footprint_name.casefold()] = (
            variant.footprint_name,
            source_footprint_name,
        )
    return result


def _footprints_by_name(board: SemanticBoard) -> dict[str, Any]:
    return {
        footprint.name.casefold(): footprint
        for footprint in board.footprints
        if footprint.name
    }


def _footprint_by_name(board: SemanticBoard, footprint_name: str) -> Any | None:
    return _footprints_by_name(board).get(footprint_name.casefold())


def _part_footprint_name(part_name: str, board: SemanticBoard) -> str:
    footprint_by_id = {
        footprint.id: footprint.name for footprint in board.footprints if footprint.name
    }
    footprint_by_name = {
        footprint.name.casefold(): footprint.name
        for footprint in board.footprints
        if footprint.name
    }
    for component in board.components:
        if _component_part_name(component).casefold() != part_name.casefold():
            continue
        footprint_name = _component_footprint_name(
            component, footprint_by_id, footprint_by_name
        )
        if footprint_name:
            return footprint_name
    return part_name


def _component_for_part(
    part_name: str, components: list[SemanticComponent]
) -> SemanticComponent | None:
    for component in components:
        if _component_part_name(component).casefold() == part_name.casefold():
            return component
    return None


def _pins_by_part(
    pins: list[SemanticPin],
    components_by_id: dict[str, SemanticComponent],
    *,
    part_names_by_component_id: dict[str, str] | None = None,
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {}
    for pin in pins:
        if not pin.component_id:
            continue
        component = components_by_id.get(pin.component_id)
        if component is None:
            continue
        part_name = (
            part_names_by_component_id.get(component.id)
            if part_names_by_component_id is not None
            else None
        ) or _component_part_name(component)
        key = part_name.casefold()
        pin_name = _pin_name(pin)
        if key not in result:
            result[key] = []
            seen[key] = set()
        if pin_name.casefold() in seen[key]:
            continue
        seen[key].add(pin_name.casefold())
        result[key].append(pin_name)

    for key, values in result.items():
        result[key] = sorted(values, key=_pin_sort_key)
    return result


def _pads_by_pin_id(pads: list[SemanticPad]) -> dict[str, list[SemanticPad]]:
    result: dict[str, list[SemanticPad]] = {}
    for pad in pads:
        if not pad.pin_id:
            continue
        result.setdefault(pad.pin_id, []).append(pad)
    return result


def _pads_by_component_id(pads: list[SemanticPad]) -> dict[str, list[SemanticPad]]:
    result: dict[str, list[SemanticPad]] = {}
    for pad in pads:
        if not pad.component_id:
            continue
        result.setdefault(pad.component_id, []).append(pad)
    return result


def _part_pin_tuple(pin_name: str) -> str:
    value = _tuple_value(pin_name)
    return f"({value},{value},S)"


def _pad_pin_name(pad: SemanticPad, pins_by_id: dict[str, SemanticPin]) -> str:
    if pad.name not in {None, ""}:
        return str(pad.name)
    pin = pins_by_id.get(pad.pin_id or "")
    if pin is not None:
        return _pin_name(pin)
    return pad.id


def _relative_pad_location(
    component: SemanticComponent,
    pad: SemanticPad,
    *,
    source_unit: str | None,
    normalize_rotation: float | None = None,
    source_format: str | None = None,
) -> tuple[float, float]:
    component_x, component_y = _point_coordinates(
        component.location, source_unit=source_unit
    )
    pad_x, pad_y = _point_coordinates(pad.position, source_unit=source_unit)
    dx = pad_x - component_x
    dy = pad_y - component_y
    rotation = (
        normalize_rotation
        if normalize_rotation is not None
        else (_number(component.rotation) or 0.0)
    )
    if not _is_finite(rotation):
        return dx, dy
    if _source_rotations_are_clockwise(source_format):
        x = dx * math.cos(rotation) - dy * math.sin(rotation)
        y = dx * math.sin(rotation) + dy * math.cos(rotation)
    else:
        x = dx * math.cos(rotation) + dy * math.sin(rotation)
        y = -dx * math.sin(rotation) + dy * math.cos(rotation)
    if _odbpp_component_needs_bottom_flip(component, source_format=source_format):
        y = -y
    return x, y


def _format_footprint_pad_rotation(
    pad: SemanticPad,
    component: SemanticComponent,
    *,
    normalize_rotation: float | None = None,
    source_format: str | None = None,
) -> str:
    footprint_rotation = pad.geometry.get("footprint_rotation")
    if footprint_rotation is not None:
        rotation = math.degrees(_number(footprint_rotation) or 0.0)
        if abs(rotation) < 1e-9:
            return "0"
        if _source_rotations_are_clockwise(source_format):
            return _format_number(_normalize_degree(rotation))
        return _format_number(_normalize_degree(360.0 - rotation))

    pad_rotation = _number(_pad_rotation(pad)) or 0.0
    component_rotation = (
        normalize_rotation
        if normalize_rotation is not None
        else (_number(component.rotation) or 0.0)
    )
    rotation = math.degrees(pad_rotation - component_rotation)
    if abs(rotation) < 1e-9:
        return "0"
    if _source_rotations_are_clockwise(source_format):
        return _format_number(_normalize_degree(rotation))
    return _format_number(_normalize_degree(360.0 - rotation))


def _aedb_export_plan(board: SemanticBoard) -> _AedbExportPlan | None:
    if board.metadata.source_format != "aedb":
        return None

    components_by_part: dict[str, list[SemanticComponent]] = {}
    for component in board.components:
        key = _component_part_name(component).casefold()
        components_by_part.setdefault(key, []).append(component)

    pins_by_id = {pin.id: pin for pin in board.pins}
    pads_by_component_id = _pads_by_component_id(board.pads)
    footprint_names_by_id = {
        footprint.id: footprint.name for footprint in board.footprints if footprint.name
    }
    placements_by_component_id: dict[str, _AedbComponentPlacement] = {}
    variants: list[_AedbPartVariant] = []

    for components in components_by_part.values():
        local_variants: list[_AedbPartVariant] = []
        for component in components:
            pin_features = _aedb_pin_features_for_component(
                component,
                pads_by_component_id.get(component.id, []),
                pins_by_id,
                source_unit=board.units,
            )
            matched_variant: _AedbPartVariant | None = None
            matched_rotation = 0.0
            matched_flip_y = False
            for variant in local_variants:
                match = _match_aedb_component_to_variant(
                    variant.pin_features, pin_features
                )
                if match is None:
                    continue
                matched_rotation, matched_flip_y = match
                matched_variant = variant
                break

            if matched_variant is None:
                part_name = _component_part_name(component)
                footprint_name = _component_footprint_name(
                    component, footprint_names_by_id
                )
                component_name = _component_name(component)
                export_part_name = (
                    part_name if not local_variants else f"{part_name}_{component_name}"
                )
                export_footprint_name = (
                    footprint_name
                    if not local_variants
                    else f"{footprint_name}_{component_name}"
                )
                canonical_rotation = _aedb_canonical_rotation(
                    pin_features, fallback=component.rotation
                )
                variant = _AedbPartVariant(
                    export_part_name=export_part_name,
                    footprint_name=export_footprint_name,
                    representative_component_id=component.id,
                    canonical_rotation=canonical_rotation,
                    pin_features=pin_features,
                )
                local_variants.append(variant)
                variants.append(variant)
                placements_by_component_id[component.id] = _AedbComponentPlacement(
                    export_part_name=export_part_name,
                    footprint_name=export_footprint_name,
                    rotation=canonical_rotation,
                )
                continue

            placements_by_component_id[component.id] = _AedbComponentPlacement(
                export_part_name=matched_variant.export_part_name,
                footprint_name=matched_variant.footprint_name,
                rotation=matched_variant.canonical_rotation + matched_rotation,
                flip_y=matched_flip_y,
            )

    return _AedbExportPlan(
        placements_by_component_id=placements_by_component_id,
        variants=variants,
    )


def _aedb_pin_features_for_component(
    component: SemanticComponent,
    pads: list[SemanticPad],
    pins_by_id: dict[str, SemanticPin],
    *,
    source_unit: str | None,
) -> dict[str, _AedbPinFeature]:
    component_x, component_y = _point_coordinates(
        component.location, source_unit=source_unit
    )
    features: dict[str, _AedbPinFeature] = {}
    for pad in pads:
        pad_x, pad_y = _point_coordinates(pad.position, source_unit=source_unit)
        pin_name = _pad_pin_name(pad, pins_by_id)
        if pin_name in features:
            continue
        features[pin_name] = _AedbPinFeature(
            x=pad_x - component_x,
            y=pad_y - component_y,
            rotation=_number(_pad_rotation(pad)) or 0.0,
        )
    return features


def _component_footprint_name(
    component: SemanticComponent,
    footprint_names_by_id: dict[str, str],
    footprint_names_by_name: dict[str, str] | None = None,
) -> str:
    if component.footprint_id and component.footprint_id in footprint_names_by_id:
        return footprint_names_by_id[component.footprint_id]
    if component.package_name:
        package_name = str(component.package_name)
        if footprint_names_by_name is not None:
            return footprint_names_by_name.get(package_name.casefold(), package_name)
        return package_name
    return _component_part_name(component)


def _aedb_canonical_rotation(
    pin_features: dict[str, _AedbPinFeature],
    *,
    fallback: Any,
) -> float:
    for pin_name in sorted(pin_features, key=_pin_sort_key):
        rotation = pin_features[pin_name].rotation
        if _is_finite(rotation):
            return float(rotation)
    value = _number(fallback)
    if value is None or not _is_finite(value):
        return 0.0
    return float(value)


def _match_aedb_component_to_variant(
    base: dict[str, _AedbPinFeature],
    candidate: dict[str, _AedbPinFeature],
) -> tuple[float, bool] | None:
    if set(base) != set(candidate):
        return None
    if not base:
        return 0.0, False

    rotation = _match_aedb_component_rotation(base, candidate, flip_y=False)
    if rotation is not None:
        return rotation, False
    rotation = _match_aedb_component_rotation(base, candidate, flip_y=True)
    if rotation is not None:
        return rotation, True
    return None


def _match_aedb_component_rotation(
    base: dict[str, _AedbPinFeature],
    candidate: dict[str, _AedbPinFeature],
    *,
    flip_y: bool,
) -> float | None:
    reference_name = _aedb_reference_pin_name(base, candidate)
    if reference_name is None:
        return (
            0.0 if _aedb_positions_match(base, candidate, 0.0, flip_y=flip_y) else None
        )

    base_feature = base[reference_name]
    candidate_feature = candidate[reference_name]
    x1 = -base_feature.x if flip_y else base_feature.x
    y1 = base_feature.y
    x2 = candidate_feature.x
    y2 = candidate_feature.y
    if (
        abs(x1) <= AEDB_COMPONENT_MATCH_TOLERANCE_MIL
        and abs(y1) <= AEDB_COMPONENT_MATCH_TOLERANCE_MIL
    ):
        rotation = 0.0
    else:
        rotation = math.atan2(y2, x2) - math.atan2(y1, x1)
    if not _aedb_positions_match(base, candidate, rotation, flip_y=flip_y):
        return None
    return _normalize_angle(rotation)


def _aedb_reference_pin_name(
    base: dict[str, _AedbPinFeature],
    candidate: dict[str, _AedbPinFeature],
) -> str | None:
    names = sorted(set(base) & set(candidate), key=_pin_sort_key)
    if not names:
        return None
    reference = None
    best_radius = -1.0
    for name in names:
        radius = max(
            math.hypot(base[name].x, base[name].y),
            math.hypot(candidate[name].x, candidate[name].y),
        )
        if radius > best_radius + AEDB_COMPONENT_MATCH_TOLERANCE_MIL:
            reference = name
            best_radius = radius
    return reference


def _aedb_positions_match(
    base: dict[str, _AedbPinFeature],
    candidate: dict[str, _AedbPinFeature],
    rotation: float,
    *,
    flip_y: bool,
) -> bool:
    sin_angle = math.sin(rotation)
    cos_angle = math.cos(rotation)
    for pin_name, base_feature in base.items():
        x = -base_feature.x if flip_y else base_feature.x
        y = base_feature.y
        transformed_x = x * cos_angle - y * sin_angle
        transformed_y = y * cos_angle + x * sin_angle
        candidate_feature = candidate[pin_name]
        if (
            abs(transformed_x - candidate_feature.x)
            > AEDB_COMPONENT_MATCH_TOLERANCE_MIL
        ):
            return False
        if (
            abs(transformed_y - candidate_feature.y)
            > AEDB_COMPONENT_MATCH_TOLERANCE_MIL
        ):
            return False
    return True


def _normalize_angle(value: float) -> float:
    angle = math.fmod(value, math.tau)
    if angle < 0:
        angle += math.tau
    if abs(angle - math.tau) < 1e-9:
        return 0.0
    return angle
