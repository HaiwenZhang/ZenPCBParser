from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from aurora_translator.sources.auroradb.block import (
    AuroraBlock,
    AuroraItem,
    split_reserved,
    strip_wrapping_pair,
    strip_wrapping_quotes,
)
from aurora_translator.sources.auroradb.models import AuroraDBPackage

from .commands import AAFCommand
from .geometry import (
    GeometryParseResult,
    location_values,
    parse_geometry_option,
    split_tuple,
)


AURORADB_NO_NET_KEYWORD = "NoNet"


@dataclass(slots=True)
class LayerState:
    name: str
    layer_type: str
    layer_id: int
    components: AuroraBlock | None = None
    logic_layers: dict[str, AuroraBlock] = field(default_factory=dict)
    net_geometry: AuroraBlock = field(
        default_factory=lambda: AuroraBlock("NetGeometry")
    )
    net_geometry_by_name: dict[str, AuroraBlock] = field(default_factory=dict)

    def to_block(self) -> AuroraBlock:
        block = AuroraBlock("MetalLayer")
        block.add_item("Type", self.layer_type)
        block.add_item("NameID", [self.name, self.layer_id])
        if self.components is not None:
            block.append(self.components)
        for logic_layer in self.logic_layers.values():
            block.append(logic_layer)
        block.append(self.net_geometry)
        return block


@dataclass(slots=True)
class AAFExecutionResult:
    package: AuroraDBPackage
    supported_commands: int
    unsupported_commands: int
    diagnostics: list[str]


class AAFToAuroraExecutor:
    """Execute ASIV-compatible AAF command files into AuroraDB block trees.

    This intentionally starts with the stable ASIV surface used by
    design.layout and the core part commands. Unsupported commands are
    reported with source locations instead of being silently ignored.
    """

    def __init__(self) -> None:
        self.units = "mil"
        self.outline: AuroraBlock | AuroraItem | None = None
        self.shape_list = AuroraBlock("ShapeList")
        self.via_list = AuroraBlock("ViaList")
        self.nets = AuroraBlock("Nets")
        self.layers: dict[str, LayerState] = {}
        self.layers_by_key: dict[str, LayerState] = {}
        self.layer_name_ids: dict[str, int] = {}
        self.layer_name_ids_by_key: dict[str, int] = {}
        self.component_layers_by_key: dict[str, LayerState] = {}
        self.nets_by_key: dict[str, AuroraBlock] = {}
        self.net_pins_by_key: dict[str, AuroraBlock] = {}
        self.net_vias_by_key: dict[str, AuroraBlock] = {}
        self.next_layer_id = 0

        self.part_list = AuroraBlock("PartList")
        self.symbol_list = AuroraBlock("SymbolList")
        self.footprint_list = AuroraBlock("FootprintList")
        self.parts_by_name: dict[str, AuroraBlock] = {}
        self.symbols_by_name: dict[str, AuroraBlock] = {}
        self.footprints_by_name: dict[str, AuroraBlock] = {}
        self.geom_container: dict[str, AuroraBlock | AuroraItem] = {}

        self.diagnostics: list[str] = []
        self.supported_commands = 0
        self.unsupported_commands = 0
        self.saw_layout_command = False
        self.saw_library_command = False

    def execute_many(self, commands: list[AAFCommand]) -> AAFExecutionResult:
        for command in commands:
            self.execute(command)
        return self.result()

    def execute(self, command: AAFCommand) -> None:
        handled = False
        words = command._word_keys
        try:
            if words and words[0] == "layout":
                self.saw_layout_command = True
                handled = self._execute_layout(command)
            elif words and words[0] == "library":
                self.saw_library_command = True
                handled = self._execute_library(command)
        except Exception as exc:  # noqa: BLE001 - diagnostics must keep the translation moving.
            self.diagnostics.append(f"{command.location_label()}: {exc}")
            handled = True

        if handled:
            self.supported_commands += 1
        else:
            self.unsupported_commands += 1
            self.diagnostics.append(
                f"{command.location_label()}: unsupported command: {command.raw.strip()}"
            )

    def result(self) -> AAFExecutionResult:
        package = AuroraDBPackage(
            layout=self._build_layout_block() if self.saw_layout_command else None,
            parts=self._build_parts_block() if self.saw_library_command else None,
            layers={name: state.to_block() for name, state in self.layers.items()}
            if self.saw_layout_command
            else {},
            diagnostics=list(self.diagnostics),
        )
        return AAFExecutionResult(
            package=package,
            supported_commands=self.supported_commands,
            unsupported_commands=self.unsupported_commands,
            diagnostics=list(self.diagnostics),
        )

    def _execute_layout(self, command: AAFCommand) -> bool:
        words = command._word_keys
        if len(words) >= 2 and words[1] == "set":
            if command.has_option("-unit"):
                self.units = _normalize_layout_unit(command.option_string("-unit"))
                return True
            if command.has_option("-profile"):
                geometry = parse_geometry_option(command.option_values("-g"))
                if geometry is None:
                    self._warn(command, "layout profile command is missing -g geometry")
                    return True
                self._extend_geometry_diagnostics(command, geometry)
                geometry.node.name = "Outline"
                self.outline = geometry.node
                return True
            if command.has_option("-layerstack"):
                for layer_def in command.option_values("-layerstack"):
                    parts = split_tuple(layer_def)
                    if len(parts) >= 3:
                        self._add_metal_layer(parts[0], parts[1])
                    else:
                        self._warn(command, f"invalid layerstack entry {layer_def!r}")
                return True

        if len(words) < 2 or words[1] != "add":
            return False

        if command.has_option("-net") and command.has_option("-component"):
            return self._add_net_pin(command)
        if command.has_option("-net") and command.has_option("-via"):
            return self._add_net_via(command)
        if (
            command.has_option("-net")
            and (command.has_option("-g") or command.has_option("-shape"))
            and command.has_option("-layer")
        ):
            return self._add_net_geometry(command)
        if (
            command.has_option("-logic")
            and (command.has_option("-g") or command.has_option("-shape"))
            and command.has_option("-layer")
        ):
            return self._add_logic_geometry(command)
        if (
            command.has_option("-shape")
            and command.has_option("-id")
            and command.has_option("-g")
            and not command.has_option("-layer")
        ):
            return self._add_shape(command)
        if command.has_option("-container") and command.has_option("-g"):
            return self._add_container_geometry(command)
        if (
            command.has_option("-layer")
            and not command.has_option("-net")
            and not command.has_option("-logic")
            and not command.has_option("-component")
        ):
            self._add_metal_layer(
                command.option_string("-layer"),
                command.option_string("-type")
                or command.option_string("-t")
                or "Signal",
            )
            return True
        if command.has_option("-doc"):
            self._add_layer_id(command.option_string("-doc"))
            return True
        if command.has_option("-complayer"):
            return self._add_component_layer(command)
        if command.has_option("-logic"):
            return self._add_logic_layer(command)
        if command.has_option("-component"):
            return self._add_component(command)
        if command.has_option("-net"):
            return self._add_net(command)
        if command.has_option("-via"):
            return self._add_via_template(command)

        return False

    def _execute_library(self, command: AAFCommand) -> bool:
        words = command._word_keys
        if len(words) >= 2 and words[1] == "set" and command.has_option("-unit"):
            return True
        if len(words) >= 2 and words[1] == "load" and command.has_option("-path"):
            self._warn(
                command,
                "library load -path is parsed but external DB merge is not implemented",
            )
            return True
        if len(words) < 2 or words[1] not in {"add", "set"}:
            return False

        first = command.first_option.name.casefold() if command.first_option else ""
        if command.has_option("-p") and first in {"-p", "-pin"}:
            part = self._find_or_create_part(command.option_string("-p"))
            if first == "-pin":
                self._add_part_pins(command, part)
            else:
                self._set_part_fields(command, part)
            return True
        if command.has_option("-symbol") and first == "-symbol":
            self._find_or_create_symbol(command.option_string("-symbol"))
            return True
        if command.has_option("-footprint"):
            if first == "-footprint":
                self._find_or_create_footprint(command.option_string("-footprint"))
                return True
            if first == "-pad" and command.has_option("-pad"):
                return self._add_footprint_pad_template(command)
            if first == "-g" and command.has_option("-pad"):
                return self._add_footprint_pad_template_geometry(command)
            if (
                first == "-fpn"
                and command.has_option("-pad")
                and command.has_option("-layer")
            ):
                return self._add_footprint_pad(command)
            if first == "-g" and command.has_option("-layer"):
                return self._add_footprint_layer_geometry(command)

        self._warn(
            command,
            "library command parsed but this detailed library branch is not implemented yet",
        )
        return True

    def _add_shape(self, command: AAFCommand) -> bool:
        geometry = parse_geometry_option(command.option_values("-g"))
        if geometry is None:
            self._warn(command, "shape command is missing -g geometry")
            return True
        self._extend_geometry_diagnostics(command, geometry)
        shape_id = command.option_string("-id") or (
            str(geometry.geometry_id) if geometry.geometry_id is not None else ""
        )
        shape_name = command.option_string("-shape")
        self.shape_list.add_item("IdName", [shape_id, shape_name])
        self.shape_list.append(geometry.node)
        return True

    def _add_container_geometry(self, command: AAFCommand) -> bool:
        geometry = parse_geometry_option(
            command.option_values("-g"),
            container=self.geom_container,
            copy_container_nodes=False,
        )
        if geometry is None:
            self._warn(command, "container command is missing -g geometry")
            return True
        self._extend_geometry_diagnostics(command, geometry)
        if geometry.geometry_id:
            self.geom_container[geometry.geometry_id] = geometry.node
        return True

    def _add_component_layer(self, command: AAFCommand) -> bool:
        component_layer = command.option_string("-complayer")
        metal_layer = command.option_string("-layer")
        layer = self._get_layer(metal_layer)
        layer_id = self._add_layer_id(component_layer)
        block = AuroraBlock("Components")
        block.add_item("Type", "Component")
        block.add_item("NameID", [component_layer, layer_id])
        layer.components = block
        self.component_layers_by_key[component_layer.casefold()] = layer
        return True

    def _add_logic_layer(self, command: AAFCommand) -> bool:
        logic_data = command.option_string("-logic")
        if ":" in logic_data:
            logic_name, logic_type = logic_data.split(":", 1)
        else:
            logic_name, logic_type = logic_data, "Document"
        metal_layer = command.option_string("-layer")
        layer = self._get_layer(metal_layer)
        layer_id = self._add_layer_id(logic_name)
        block = AuroraBlock("LogicLayer")
        block.add_item("Type", logic_type)
        block.add_item("NameID", [logic_name, layer_id])
        layer.logic_layers[logic_name.casefold()] = block
        return True

    def _add_component(self, command: AAFCommand) -> bool:
        component_name = command.option_string("-component")
        part_name = _clean_aaf_string(command.option_string("-part")) or "Unknown"
        component_layer_name = command.option_string("-layer")
        layer = self._find_layer_by_component_layer(component_layer_name)
        if layer.components is None:
            layer_id = self._add_layer_id(component_layer_name)
            layer.components = AuroraBlock("Components")
            layer.components.add_item("Type", "Component")
            layer.components.add_item("NameID", [component_layer_name, layer_id])
            self.component_layers_by_key[component_layer_name.casefold()] = layer
        loc = location_values(
            command.option_values("-location"),
            rotation=command.option_string("-rotation") or "0",
            flip_x=command.has_option("-flipX") or command.has_option("-flipx"),
            flip_y=command.has_option("-flipY") or command.has_option("-flipy"),
        )
        values = [part_name, component_layer_name, *loc]
        value = command.option_string("-value")
        if value:
            values.append(value)
        layer.components.add_item(component_name, values)
        return True

    def _add_net(self, command: AAFCommand) -> bool:
        net_name = _normalize_net_name(command.option_string("-net"))
        net_block = self._find_or_create_net(net_name)
        net_type = command.option_string("-t") or "Signal"
        voltage = command.option_string("-voltage")
        net_block.replace_item("Type", net_type)
        net_block.replace_item("Voltage", voltage)
        return True

    def _add_via_template(self, command: AAFCommand) -> bool:
        via_data = command.option_string("-via")
        items = split_reserved(via_data, delimiters=" ,<>()")
        if len(items) < 2:
            self._warn(command, "via template has fewer than two fields")
            return True
        via_id = items[0]
        via_name = command.option_string("-name") or _default_via_name(via_id)
        via_block = AuroraBlock("Via")
        via_block.add_item("IdName", [via_id, via_name])
        via_block.add_item("Barrel", [items[1], "0", "Y"])
        for pad_item in items[2:]:
            pad_parts = split_reserved(pad_item, delimiters=" :")
            if not pad_parts:
                continue
            layer_name = pad_parts[0]
            pad_shape = (
                pad_parts[1]
                if len(pad_parts) > 1 and pad_parts[1].casefold() != "null"
                else "-1"
            )
            if len(pad_parts) >= 5:
                pad_rotation = (
                    pad_parts[2] if len(pad_parts) > 2 and pad_parts[2] else "0"
                )
                pad_ccw = pad_parts[3] if len(pad_parts) > 3 and pad_parts[3] else "Y"
                anti_shape = (
                    pad_parts[4]
                    if len(pad_parts) > 4 and pad_parts[4].casefold() != "null"
                    else None
                )
                anti_rotation = (
                    pad_parts[5] if len(pad_parts) > 5 and pad_parts[5] else "0"
                )
                anti_ccw = pad_parts[6] if len(pad_parts) > 6 and pad_parts[6] else "Y"
            else:
                pad_rotation = "0"
                pad_ccw = "Y"
                anti_shape = (
                    pad_parts[2]
                    if len(pad_parts) > 2 and pad_parts[2].casefold() != "null"
                    else None
                )
                anti_rotation = "0"
                anti_ccw = "Y"
            values = [pad_shape, pad_rotation, pad_ccw]
            if anti_shape is not None:
                values.extend([anti_shape, anti_rotation, anti_ccw])
            via_block.add_item(layer_name, values)
        self.via_list.append(via_block)
        return True

    def _add_net_via(self, command: AAFCommand) -> bool:
        net_name = command.option_string("-net")
        net = self._find_or_create_net(net_name)
        net_key = _normalize_net_name(net_name).casefold()
        vias = self.net_vias_by_key.get(net_key)
        if vias is None:
            vias = net.get_block("NetVias")
            if vias is None:
                vias = net.add_block("NetVias")
            self.net_vias_by_key[net_key] = vias
        loc = location_values(
            command.option_values("-location"),
            rotation=command.option_string("-rotation") or "0",
        )
        vias.add_item("Via", [command.option_string("-via"), *loc])
        return True

    def _add_net_pin(self, command: AAFCommand) -> bool:
        net_name = command.option_string("-net")
        net = self._find_or_create_net(net_name)
        net_key = _normalize_net_name(net_name).casefold()
        pins = self.net_pins_by_key.get(net_key)
        if pins is None:
            pins = net.get_block("NetPins")
            if pins is None:
                pins = net.add_block("NetPins")
            self.net_pins_by_key[net_key] = pins
        pins.add_item(
            "Pin",
            [
                command.option_string("-layer"),
                command.option_string("-component"),
                command.option_string("-pin"),
                command.option_string("-metal"),
            ],
        )
        return True

    def _add_net_geometry(self, command: AAFCommand) -> bool:
        net_name = _normalize_net_name(command.option_string("-net"))
        layer_name = command.option_string("-layer")
        layer = self._get_layer(layer_name)
        net_key = net_name.casefold()
        net_block = layer.net_geometry_by_name.get(net_key)
        if net_block is None:
            net_block = AuroraBlock(net_name)
            layer.net_geometry.append(net_block)
            layer.net_geometry_by_name[net_key] = net_block
        geom_block = self._ref_geometry_block(command, "NetGeom")
        net_block.append(geom_block)
        self.geom_container.clear()
        return True

    def _add_logic_geometry(self, command: AAFCommand) -> bool:
        layer = self._get_layer(command.option_string("-layer"))
        logic_name = command.option_string("-logic").split(":", 1)[0]
        logic = layer.logic_layers.get(logic_name.casefold())
        if logic is None:
            self._add_logic_layer(command)
            logic = layer.logic_layers[logic_name.casefold()]
        logic.append(self._ref_geometry_block(command, "Geometry"))
        self.geom_container.clear()
        return True

    def _ref_geometry_block(self, command: AAFCommand, name: str) -> AuroraBlock:
        block = AuroraBlock(name)
        shape_id = (
            command.option_string("-shape") if command.has_option("-shape") else "-1"
        )
        block.add_item("SymbolID", shape_id)
        if command.has_option("-location"):
            block.add_item(
                "Location",
                location_values(
                    command.option_values("-location"),
                    rotation=command.option_string("-rotation") or "0",
                    flip_x=command.has_option("-flipX") or command.has_option("-flipx"),
                    flip_y=command.has_option("-flipY") or command.has_option("-flipy"),
                ),
            )
        geometry = parse_geometry_option(
            command.option_values("-g"),
            container=self.geom_container,
            copy_container_nodes=False,
        )
        if geometry is not None:
            self._extend_geometry_diagnostics(command, geometry)
            block.append(geometry.node)
        return block

    def _build_layout_block(self) -> AuroraBlock:
        layout = AuroraBlock("CeLayout")
        layout.add_item("Units", self.units)
        if self.outline is not None:
            layout.append(self.outline)
        else:
            outline = AuroraBlock("Outline")
            outline.add_item("Solid", "Y")
            outline.add_item("CCW", "Y")
            layout.append(outline)
            self.diagnostics.append(
                "layout profile was not provided; wrote an empty Outline block"
            )

        symbols = AuroraBlock("GeomSymbols")
        symbols.append(self.shape_list)
        symbols.append(self.via_list)
        layout.append(symbols)
        layout.append(self.nets)

        stack = AuroraBlock("LayerStackup")
        stack.add_item("MetalLayers", list(self.layers.keys()))
        stack.add_item("NextLayerID", self.next_layer_id)
        layer_pairs: list[str] = []
        for name, layer_id in sorted(
            self.layer_name_ids.items(), key=lambda item: item[1]
        ):
            layer_pairs.extend([name, str(layer_id)])
        stack.add_item("LayerNameIDs", layer_pairs)
        layout.append(stack)
        return layout

    def _build_parts_block(self) -> AuroraBlock:
        self._ensure_footprints_have_metal_layer()
        self._repair_part_footprint_pin_ids()
        parts = AuroraBlock("CeParts")
        parts.append(self.part_list)
        if self.symbol_list.children:
            parts.append(self.symbol_list)
        if self.footprint_list.children:
            parts.append(self.footprint_list)
        return parts

    def _repair_part_footprint_pin_ids(self) -> None:
        repaired = 0
        for part in self.parts_by_name.values():
            pin_numbers = self._part_pin_numbers(part)
            missing_pin_names: list[str] = []
            for footprint_name in self._part_footprint_names(part):
                footprint = self.footprints_by_name.get(footprint_name.casefold())
                if footprint is None:
                    continue
                for pad_id in self._footprint_part_pad_ids(footprint):
                    key = pad_id.casefold()
                    if key in pin_numbers:
                        continue
                    pin_numbers.add(key)
                    missing_pin_names.append(pad_id)
            if missing_pin_names:
                self._add_raw_part_pins(part, missing_pin_names)
                repaired += len(missing_pin_names)
        if repaired:
            self.diagnostics.append(
                f"Repaired AuroraDB part footprint pin references: added_pins={repaired}"
            )

    def _ensure_footprints_have_metal_layer(self) -> None:
        for footprint in self.footprints_by_name.values():
            if not footprint.get_blocks("MetalLayer"):
                self._find_or_create_footprint_metal_layer(footprint, "top", "1")

    @staticmethod
    def _part_footprint_names(part: AuroraBlock) -> list[str]:
        item = part.get_item("FootPrintSymbols")
        return list(item.values) if item else []

    @staticmethod
    def _part_pin_numbers(part: AuroraBlock) -> set[str]:
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

    @staticmethod
    def _footprint_part_pad_ids(footprint: AuroraBlock) -> list[str]:
        pad_ids: list[str] = []
        seen: set[str] = set()
        for metal_layer in footprint.get_blocks("MetalLayer"):
            for part_pad in metal_layer.get_blocks("PartPad"):
                AAFToAuroraExecutor._collect_part_pad_id(part_pad, pad_ids, seen)
            for logic_layer in metal_layer.get_blocks("LogicLayer"):
                for part_pad in logic_layer.get_blocks("PartPad"):
                    AAFToAuroraExecutor._collect_part_pad_id(part_pad, pad_ids, seen)
        return pad_ids

    @staticmethod
    def _collect_part_pad_id(
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

    @staticmethod
    def _add_raw_part_pins(part: AuroraBlock, pin_names: list[str]) -> None:
        pins = part.get_block("PinList")
        if pins is None:
            pins = part.add_block("PinList")
        for pin_name in pin_names:
            fields = split_reserved(
                strip_wrapping_pair(f"({pin_name},{pin_name},S)", "(", ")"),
                delimiters=",",
            )
            while len(fields) < 4:
                fields.append("")
            pin = AuroraBlock("Pin")
            pin.add_item("DefData", ",".join(fields[:4]))
            pins.append(pin)

    def _find_or_create_part(self, part_name: str) -> AuroraBlock:
        part_name = _clean_aaf_string(part_name)
        key = part_name.casefold()
        if key in self.parts_by_name:
            return self.parts_by_name[key]
        part = AuroraBlock("Part")
        info = part.add_block("PartInfo")
        info.add_item("Name", part_name)
        info.add_item("Vendor", "Unknown")
        info.add_item("Type", "")
        info.add_item("Description", "")
        info.add_item("Attributes", [])
        part.append(AuroraBlock("PinList"))
        self.part_list.append(part)
        self.parts_by_name[key] = part
        return part

    def _set_part_fields(self, command: AAFCommand, part: AuroraBlock) -> None:
        info = part.get_block("PartInfo")
        if info is None:
            info = part.add_block("PartInfo")
        vendor = _clean_aaf_string(command.option_string("-m"))
        if vendor:
            info.replace_item("Vendor", vendor)
        part_type = _clean_aaf_string(command.option_string("-t"))
        if part_type:
            info.replace_item("Type", part_type)
        description = _clean_aaf_string(command.option_string("-d"))
        if description:
            info.replace_item("Description", description)
        if command.option_values("-a"):
            info.replace_item("Attributes", command.option_values("-a"))
        footprint_symbols = [
            _clean_aaf_string(value) for value in command.option_values("-footprint")
        ]
        if footprint_symbols:
            _replace_item_before_block(
                part, "FootPrintSymbols", footprint_symbols, "PinList"
            )
        for group in command.option_values("-symbol_group"):
            part.add_item("SymbolGroup", split_tuple(group))

    def _add_part_pins(self, command: AAFCommand, part: AuroraBlock) -> None:
        pins = part.get_block("PinList")
        if pins is None:
            pins = part.add_block("PinList")
        for pin_value in command.option_values("-pin"):
            fields = split_reserved(
                strip_wrapping_pair(pin_value, "(", ")"), delimiters=","
            )
            if len(fields) < 3:
                self._warn(
                    command, f"part pin has fewer than three fields: {pin_value!r}"
                )
                continue
            pin = AuroraBlock("Pin")
            while len(fields) < 4:
                fields.append("")
            pin.add_item("DefData", ",".join(fields[:4]))
            pins.append(pin)

    def _find_or_create_symbol(self, symbol_name: str) -> AuroraBlock:
        symbol_name = _clean_aaf_string(symbol_name)
        key = symbol_name.casefold()
        if key in self.symbols_by_name:
            return self.symbols_by_name[key]
        symbol = AuroraBlock("SchematicSymbol")
        symbol.add_item("SymbolID", symbol_name)
        symbol.append(AuroraBlock("PinTemplates"))
        symbol.append(AuroraBlock("Geometry"))
        self.symbol_list.append(symbol)
        self.symbols_by_name[key] = symbol
        return symbol

    def _find_or_create_footprint(self, footprint_name: str) -> AuroraBlock:
        footprint_name = _clean_aaf_string(footprint_name)
        key = footprint_name.casefold()
        if key in self.footprints_by_name:
            return self.footprints_by_name[key]
        footprint = AuroraBlock("FootPrintSymbol")
        footprint.add_item("SymbolID", footprint_name)
        self.footprint_list.append(footprint)
        self.footprints_by_name[key] = footprint
        return footprint

    def _add_footprint_pad_template(self, command: AAFCommand) -> bool:
        footprint = self._find_or_create_footprint(command.option_string("-footprint"))
        pad_id = _clean_aaf_string(command.option_string("-pad"))
        self._find_or_create_pad_template(footprint, pad_id)
        return True

    def _add_footprint_pad_template_geometry(self, command: AAFCommand) -> bool:
        footprint = self._find_or_create_footprint(command.option_string("-footprint"))
        pad_id = _clean_aaf_string(command.option_string("-pad"))
        pad_template = self._find_or_create_pad_template(footprint, pad_id)
        geometry_list = pad_template.get_block("GeometryList")
        if geometry_list is None:
            geometry_list = pad_template.add_block("GeometryList")
        if geometry_list.children:
            return True
        geometry = parse_geometry_option(command.option_values("-g"))
        if geometry is None:
            self._warn(command, "footprint pad template command is missing -g geometry")
            return True
        self._extend_geometry_diagnostics(command, geometry)
        geometry_list.append(geometry.node)
        return True

    def _add_footprint_pad(self, command: AAFCommand) -> bool:
        footprint = self._find_or_create_footprint(command.option_string("-footprint"))
        pad_id = _clean_aaf_string(command.option_string("-fpn"))
        template_id = _clean_aaf_string(command.option_string("-pad"))
        layer_name, layer_position = _split_name_type(command.option_string("-layer"))
        if not layer_name or not layer_position:
            self._warn(command, "footprint pad command has an invalid -layer value")
            return True
        metal_layer = self._find_or_create_footprint_metal_layer(
            footprint, layer_name, layer_position
        )
        pad_block = AuroraBlock("PartPad")
        pad_block.add_item("PadIDs", [pad_id, template_id])
        pad_block.add_item(
            "Location",
            location_values(
                command.option_values("-location"),
                rotation=command.option_string("-rotation") or "0",
                flip_x=command.has_option("-flipX") or command.has_option("-flipx"),
                flip_y=command.has_option("-flipY") or command.has_option("-flipy"),
            ),
        )
        if command.has_option("-logic"):
            logic_name, logic_type = _split_name_type(command.option_string("-logic"))
            logic_layer = self._find_or_create_footprint_logic_layer(
                metal_layer, logic_name, logic_type
            )
            logic_layer.append(pad_block)
        else:
            metal_layer.append(pad_block)
        return True

    def _add_footprint_layer_geometry(self, command: AAFCommand) -> bool:
        footprint = self._find_or_create_footprint(command.option_string("-footprint"))
        layer_name, layer_position = _split_name_type(command.option_string("-layer"))
        if not layer_name or not layer_position:
            self._warn(
                command, "footprint geometry command has an invalid -layer value"
            )
            return True
        geometry = parse_geometry_option(command.option_values("-g"))
        if geometry is None:
            self._warn(command, "footprint geometry command is missing -g geometry")
            return True
        self._extend_geometry_diagnostics(command, geometry)
        metal_layer = self._find_or_create_footprint_metal_layer(
            footprint, layer_name, layer_position
        )
        if command.has_option("-logic"):
            logic_name, logic_type = _split_name_type(command.option_string("-logic"))
            logic_layer = self._find_or_create_footprint_logic_layer(
                metal_layer, logic_name, logic_type
            )
            geom_ref = AuroraBlock("Geometry")
            geom_ref.add_item("SymbolID", "-1")
            geom_ref.append(geometry.node)
            logic_layer.append(geom_ref)
        else:
            geometry_list = metal_layer.get_block("GeometryList")
            if geometry_list is None:
                geometry_list = AuroraBlock("GeometryList")
                _insert_before_first_named_block(
                    metal_layer, geometry_list, {"PartPad", "LogicLayer"}
                )
            geometry_list.append(geometry.node)
        return True

    def _find_or_create_pad_template(
        self, footprint: AuroraBlock, pad_id: str
    ) -> AuroraBlock:
        for child in footprint.iter_blocks():
            if child.name.casefold() != "padtemplate":
                continue
            template_item = child.get_item("TemplateID")
            if (
                template_item
                and template_item.values
                and template_item.values[0].casefold() == pad_id.casefold()
            ):
                return child
        pad_template = AuroraBlock("PadTemplate")
        pad_template.add_item("TemplateID", pad_id)
        pad_template.add_block("GeometryList")
        _insert_before_first_named_block(
            footprint, pad_template, {"MetalLayer", "DrillHole", "Outline"}
        )
        return pad_template

    def _find_or_create_footprint_metal_layer(
        self, footprint: AuroraBlock, layer_name: str, layer_position: str
    ) -> AuroraBlock:
        for child in footprint.iter_blocks():
            if child.name.casefold() != "metallayer":
                continue
            name_type = child.get_item("NameType")
            if (
                name_type
                and len(name_type.values) >= 2
                and name_type.values[0].casefold() == layer_name.casefold()
                and name_type.values[1].casefold() == layer_position.casefold()
            ):
                return child
        metal_layer = AuroraBlock("MetalLayer")
        metal_layer.add_item("NameType", [layer_name, layer_position])
        footprint.append(metal_layer)
        return metal_layer

    def _find_or_create_footprint_logic_layer(
        self, metal_layer: AuroraBlock, logic_name: str, logic_type: str
    ) -> AuroraBlock:
        logic_type = logic_type or "Document"
        for child in metal_layer.iter_blocks():
            if child.name.casefold() != "logiclayer":
                continue
            name_id = child.get_item("NameID")
            type_item = child.get_item("Type")
            if (
                name_id
                and name_id.values
                and name_id.values[0].casefold() == logic_name.casefold()
                and type_item
                and type_item.values
                and type_item.values[0].casefold() == logic_type.casefold()
            ):
                return child
        logic_layer = AuroraBlock("LogicLayer")
        logic_layer.add_item("Type", logic_type)
        logic_layer.add_item("NameID", [logic_name, "-1"])
        metal_layer.append(logic_layer)
        return logic_layer

    def _find_or_create_net(self, net_name: str) -> AuroraBlock:
        normalized = _normalize_net_name(net_name)
        key = normalized.casefold()
        block = self.nets_by_key.get(key)
        if block is None:
            block = AuroraBlock(normalized)
            self.nets.append(block)
            self.nets_by_key[key] = block
        return block

    def _find_or_create_child_block(
        self, parent: AuroraBlock, name: str
    ) -> AuroraBlock:
        block = parent.get_block(name)
        if block is None:
            block = AuroraBlock(name)
            parent.append(block)
        return block

    def _add_metal_layer(self, name: str, layer_type: str) -> LayerState:
        if not name:
            name = f"Layer_{len(self.layers)}"
        key = name.casefold()
        layer = self.layers_by_key.get(key)
        if layer is not None:
            return layer
        layer_id = self._add_layer_id(name)
        state = LayerState(
            name=name, layer_type=layer_type or "Signal", layer_id=layer_id
        )
        self.layers[name] = state
        self.layers_by_key[key] = state
        return state

    def _get_layer(self, name: str) -> LayerState:
        if name:
            layer = self.layers_by_key.get(name.casefold())
            if layer is not None:
                return layer
        return self._add_metal_layer(name or f"Layer_{len(self.layers)}", "Signal")

    def _find_layer_by_component_layer(self, component_layer_name: str) -> LayerState:
        key = component_layer_name.casefold()
        layer = self.component_layers_by_key.get(key)
        if layer is not None:
            return layer
        for layer in self.layers.values():
            if layer.components is None:
                continue
            name_id = layer.components.get_item("NameID")
            if (
                name_id
                and name_id.values
                and name_id.values[0].casefold() == component_layer_name.casefold()
            ):
                self.component_layers_by_key[key] = layer
                return layer
        return self._get_layer(
            component_layer_name.replace("COMP_", "") if component_layer_name else ""
        )

    def _add_layer_id(self, name: str) -> int:
        key = name.casefold()
        existing_layer_id = self.layer_name_ids_by_key.get(key)
        if existing_layer_id is not None:
            return existing_layer_id
        layer_id = self.next_layer_id
        self.layer_name_ids[name] = layer_id
        self.layer_name_ids_by_key[key] = layer_id
        self.next_layer_id += 1
        return layer_id

    def _warn(self, command: AAFCommand, message: str) -> None:
        self.diagnostics.append(f"{command.location_label()}: {message}")

    def _extend_geometry_diagnostics(
        self, command: AAFCommand, geometry: GeometryParseResult
    ) -> None:
        for diagnostic in geometry.diagnostics:
            self._warn(command, diagnostic)


def _default_via_name(via_id: str) -> str:
    try:
        return f"Via_{int(via_id) + 1}"
    except ValueError:
        return f"Via_{via_id}"


def _normalize_layout_unit(unit: str) -> str:
    lowered = unit.casefold()
    if lowered in {"mil", "mils", "i"}:
        return "mils"
    if lowered in {"inch", "inches"}:
        return "inch"
    if lowered == "u":
        return "um"
    return unit


def _normalize_net_name(net_name: str) -> str:
    cleaned = strip_wrapping_quotes(net_name.strip())
    if cleaned.casefold() == AURORADB_NO_NET_KEYWORD.casefold():
        return AURORADB_NO_NET_KEYWORD
    return cleaned.upper()


def _clean_aaf_string(value: str) -> str:
    return strip_wrapping_quotes(value.strip())


def _split_name_type(value: str) -> tuple[str, str]:
    parts = split_reserved(_clean_aaf_string(value), delimiters=" :")
    if len(parts) < 2:
        return "", ""
    return _clean_aaf_string(parts[0]), _clean_aaf_string(parts[1])


def _replace_item_before_block(
    block: AuroraBlock, item_name: str, values: list[str], before_block: str
) -> None:
    lowered_item = item_name.casefold()
    block.children = [
        child
        for child in block.children
        if not (isinstance(child, AuroraItem) and child.name.casefold() == lowered_item)
    ]
    item = AuroraItem(item_name, values)
    before_lowered = before_block.casefold()
    for index, child in enumerate(block.children):
        if isinstance(child, AuroraBlock) and child.name.casefold() == before_lowered:
            block.children.insert(index, item)
            return
    block.append(item)


def _insert_before_first_named_block(
    block: AuroraBlock, node: AuroraBlock, before_names: set[str]
) -> None:
    lowered_names = {name.casefold() for name in before_names}
    for index, child in enumerate(block.children):
        if isinstance(child, AuroraBlock) and child.name.casefold() in lowered_names:
            block.children.insert(index, node)
            return
    block.append(node)


def execute_aaf_commands(
    commands: list[AAFCommand], *, root: str | Path | None = None
) -> AAFExecutionResult:
    executor = AAFToAuroraExecutor()
    result = executor.execute_many(commands)
    if root is not None:
        result.package.root = Path(root).expanduser().resolve()
    return result
