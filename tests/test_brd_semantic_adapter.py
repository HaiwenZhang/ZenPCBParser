from __future__ import annotations

import io
from math import radians
import sys
import tempfile
import unittest
from pathlib import Path
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = PROJECT_ROOT.parent

if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))


class BRDSemanticAdapterTests(unittest.TestCase):
    def test_brd_mil_source_units_are_preserved(self) -> None:
        from types import SimpleNamespace

        from aurora_translator.semantic.adapters.brd import (
            _raw_coord_to_semantic,
            _semantic_units,
        )

        payload = SimpleNamespace(
            header=SimpleNamespace(
                board_units="mils",
                units_divisor=100,
                coordinate_scale_nm=None,
            )
        )

        self.assertEqual(_semantic_units(payload), "mil")
        self.assertEqual(_raw_coord_to_semantic(payload, 1234), 12.34)

    def test_brd_adapter_ignores_stale_embedded_brd_stackup(self) -> None:
        from aurora_translator.semantic.adapters.brd import (
            _stackup_layers_from_design_xml,
        )

        xml_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<root><xs><c P="PRIMARY">
<o><a N="CDS_LAYER_NAME"><v V="TOP"/></a><a N="CDS_LAYER_THICKNESS"><v V="0.031"/></a><a N="CDS_LAYER_FUNCTION"><v V="CONDUCTOR"/></a></o>
<o><a N="CDS_LAYER_THICKNESS"><v V="0.05"/></a><a N="CDS_LAYER_FUNCTION"><v V="DIELECTRIC_PREPREG"/></a></o>
<o><a N="CDS_LAYER_NAME"><v V="L2"/></a><a N="CDS_LAYER_THICKNESS"><v V="0.018"/></a><a N="CDS_LAYER_FUNCTION"><v V="CONDUCTOR"/></a></o>
<o><a N="CDS_LAYER_THICKNESS"><v V="0.08"/></a><a N="CDS_LAYER_FUNCTION"><v V="DIELECTRIC_CORE"/></a></o>
<o><a N="CDS_LAYER_NAME"><v V="BOTTOM"/></a><a N="CDS_LAYER_THICKNESS"><v V="0.031"/></a><a N="CDS_LAYER_FUNCTION"><v V="CONDUCTOR"/></a></o>
</c></xs></root>"""

        self.assertEqual(
            _stackup_layers_from_design_xml(
                xml_bytes,
                ["TOP", "L2", "L3", "BOTTOM"],
                "mm",
            ),
            [],
        )

    def test_brd_adapter_uses_matching_embedded_brd_stackup(self) -> None:
        from aurora_translator.semantic.adapters.brd import from_brd
        from aurora_translator.sources.brd.models import BRDLayout

        with tempfile.TemporaryDirectory() as tmp:
            brd_path = Path(tmp) / "sample.brd"
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w") as zipper:
                zipper.writestr(
                    "Header.xml",
                    '<root><precision units="mm" numberOfDecimalPlaces="4"/></root>',
                )
                zipper.writestr(
                    "objects/Design.xml",
                    """<?xml version="1.0" encoding="UTF-8"?>
<root><xs><c P="PRIMARY">
<o><a N="CDS_LAYER_MATERIAL"><v V="AIR"/></a><a N="CDS_LAYER_THICKNESS"><v V="0"/></a><a N="CDS_LAYER_FUNCTION"><v V="SURFACE"/></a></o>
<o><a N="CDS_LAYER_NAME"><v V="TOP"/></a><a N="CDS_LAYER_MATERIAL"><v V="COPPER"/></a><a N="CDS_LAYER_ELECTRICAL_CONDUCTIVITY"><v V="595900"/></a><a N="CDS_LAYER_THICKNESS"><v V="0.031"/></a><a N="CDS_LAYER_FUNCTION"><v V="CONDUCTOR"/></a></o>
<o><a N="CDS_LAYER_MATERIAL"><v V="FR-4"/></a><a N="CDS_LAYER_DIELECTRIC_CONSTANT"><v V="3.37"/></a><a N="CDS_LAYER_LOSS_TANGENT"><v V="0.015"/></a><a N="CDS_LAYER_THICKNESS"><v V="0.05"/></a><a N="CDS_LAYER_FUNCTION"><v V="DIELECTRIC_PREPREG"/></a></o>
<o><a N="CDS_LAYER_NAME"><v V="L2"/></a><a N="CDS_LAYER_MATERIAL"><v V="COPPER"/></a><a N="CDS_LAYER_ELECTRICAL_CONDUCTIVITY"><v V="596000"/></a><a N="CDS_LAYER_THICKNESS"><v V="0.018"/></a><a N="CDS_LAYER_FUNCTION"><v V="CONDUCTOR"/></a></o>
<o><a N="CDS_LAYER_MATERIAL"><v V="FR-4"/></a><a N="CDS_LAYER_DIELECTRIC_CONSTANT"><v V="4.5"/></a><a N="CDS_LAYER_LOSS_TANGENT"><v V="0.035"/></a><a N="CDS_LAYER_THICKNESS"><v V="0.08"/></a><a N="CDS_LAYER_FUNCTION"><v V="DIELECTRIC_CORE"/></a></o>
<o><a N="CDS_LAYER_NAME"><v V="BOTTOM"/></a><a N="CDS_LAYER_MATERIAL"><v V="COPPER"/></a><a N="CDS_LAYER_ELECTRICAL_CONDUCTIVITY"><v V="595900"/></a><a N="CDS_LAYER_THICKNESS"><v V="0.031"/></a><a N="CDS_LAYER_FUNCTION"><v V="CONDUCTOR"/></a></o>
</c></xs></root>""",
                )
            payload_bytes = archive.getvalue()
            property_name = b"DBPartitionAttachment"
            block = (
                b"\x3b\x00\x00\x00"
                + len(payload_bytes).to_bytes(4, "little")
                + property_name
                + b"\0" * (128 - len(property_name))
                + b"\0" * 32
                + b"\0" * 12
                + payload_bytes
            )
            brd_path.write_bytes(block)

            payload = BRDLayout.model_validate(
                {
                    "metadata": {
                        "project_version": "1.0.44",
                        "parser_version": "0.1.7",
                        "output_schema_version": "0.5.0",
                        "source": str(brd_path),
                        "source_type": "file",
                        "backend": "rust-cli",
                        "rust_parser_version": "0.1.7",
                    },
                    "summary": {
                        "object_count_declared": 0,
                        "object_count_parsed": 0,
                        "string_count": 3,
                        "layer_count": 1,
                        "net_count": 0,
                        "padstack_count": 0,
                        "footprint_count": 0,
                        "placed_pad_count": 0,
                        "via_count": 0,
                        "track_count": 0,
                        "segment_count": 0,
                        "shape_count": 0,
                        "keepout_count": 0,
                        "net_assignment_count": 0,
                        "text_count": 0,
                        "diagnostic_count": 0,
                        "format_version": "V_172",
                        "allegro_version": "",
                        "units": "millimeters",
                    },
                    "header": {
                        "magic": 0x00140400,
                        "format_version": "V_172",
                        "file_role": 0,
                        "writer_program": 0,
                        "object_count": 0,
                        "max_key": 0,
                        "allegro_version": "",
                        "board_units_code": 3,
                        "board_units": "millimeters",
                        "units_divisor": 10000,
                        "coordinate_scale_nm": 2.54,
                        "string_count": 3,
                        "x27_end": 0,
                        "linked_lists": {},
                        "layer_map": [
                            {"index": 0, "class_code": 6, "layer_list_key": 100}
                        ],
                    },
                    "strings": [
                        {"id": 1, "value": "TOP"},
                        {"id": 2, "value": "L2"},
                        {"id": 3, "value": "BOTTOM"},
                    ],
                    "layers": [
                        {
                            "key": 100,
                            "class_code": 0,
                            "names": ["string:1", "string:2", "string:3"],
                        }
                    ],
                    "nets": [],
                    "padstacks": [],
                    "footprints": [],
                    "placed_pads": [],
                    "vias": [],
                    "tracks": [],
                    "shapes": [],
                    "texts": [],
                    "blocks": [
                        {
                            "block_type": 59,
                            "type_name": "PROPERTY",
                            "offset": 0,
                            "length": len(block),
                            "key": None,
                            "next": None,
                        }
                    ],
                    "block_counts": {},
                    "diagnostics": [],
                }
            )

            board = from_brd(payload)

        self.assertEqual(
            [layer.name for layer in board.layers],
            ["TOP", "D0", "L2", "D1", "BOTTOM"],
        )
        self.assertEqual(
            [layer.thickness for layer in board.layers],
            ["0.031 mm", "0.05 mm", "0.018 mm", "0.08 mm", "0.031 mm"],
        )
        self.assertEqual(len(board.materials), 4)

    def test_brd_adapter_prefers_exact_physical_stackup_layer_list(self) -> None:
        from aurora_translator.semantic.adapters.brd import from_brd
        from aurora_translator.sources.brd.models import BRDLayout

        payload = BRDLayout.model_validate(
            {
                "metadata": {
                    "project_version": "1.0.44",
                    "parser_version": "0.1.6",
                    "output_schema_version": "0.5.0",
                    "source": "sample.brd",
                    "source_type": "file",
                    "backend": "rust-cli",
                    "rust_parser_version": "0.1.6",
                },
                "summary": {
                    "object_count_declared": 0,
                    "object_count_parsed": 0,
                    "string_count": 8,
                    "layer_count": 2,
                    "net_count": 0,
                    "padstack_count": 0,
                    "footprint_count": 0,
                    "placed_pad_count": 0,
                    "via_count": 0,
                    "track_count": 0,
                    "segment_count": 0,
                    "shape_count": 0,
                    "keepout_count": 0,
                    "net_assignment_count": 0,
                    "text_count": 0,
                    "diagnostic_count": 0,
                    "format_version": "V_172",
                    "allegro_version": "",
                    "units": "millimeters",
                },
                "header": {
                    "magic": 0x00140400,
                    "format_version": "V_172",
                    "file_role": 0,
                    "writer_program": 0,
                    "object_count": 0,
                    "max_key": 0,
                    "allegro_version": "",
                    "board_units_code": 3,
                    "board_units": "millimeters",
                    "units_divisor": 10000,
                    "coordinate_scale_nm": 2.54,
                    "string_count": 8,
                    "x27_end": 0,
                    "linked_lists": {},
                    "layer_map": [
                        {"index": 0, "class_code": 6, "layer_list_key": 100},
                        {"index": 1, "class_code": 6, "layer_list_key": 200},
                    ],
                },
                "strings": [
                    {"id": 1, "value": "TOP_VIEW"},
                    {"id": 2, "value": "ASSY_TITLE"},
                    {"id": 3, "value": "FAB_TITLE"},
                    {"id": 4, "value": "BOTTOM_VIEW"},
                    {"id": 5, "value": "TOP"},
                    {"id": 6, "value": "L2"},
                    {"id": 7, "value": "L3"},
                    {"id": 8, "value": "BOTTOM"},
                ],
                "layers": [
                    {
                        "key": 100,
                        "class_code": 0,
                        "names": ["string:1", "string:2", "string:3", "string:4"],
                    },
                    {
                        "key": 200,
                        "class_code": 0,
                        "names": ["string:5", "string:6", "string:7", "string:8"],
                    },
                ],
                "nets": [],
                "padstacks": [],
                "footprints": [],
                "placed_pads": [],
                "vias": [],
                "tracks": [],
                "shapes": [],
                "texts": [],
                "blocks": [],
                "block_counts": {},
                "diagnostics": [],
            }
        )

        board = from_brd(payload)

        self.assertEqual(
            [layer.name for layer in board.layers],
            ["TOP", "D0", "L2", "D1", "L3", "D2", "BOTTOM"],
        )

    def test_brd_refdes_field_chain_uses_custom_inner_layer_list(self) -> None:
        from aurora_translator.semantic.adapters.brd import (
            _component_layer_from_refdes_text,
            _component_text_layer,
            _refdes_inner_layer_map,
        )
        from aurora_translator.sources.brd.models import (
            BRDLayerInfo,
            BRDLayout,
            BRDText,
        )

        payload = BRDLayout.model_validate(
            {
                "metadata": {
                    "project_version": "1.0.44",
                    "parser_version": "0.1.6",
                    "output_schema_version": "0.5.0",
                    "source": "sample.brd",
                    "source_type": "file",
                    "backend": "rust-cli",
                    "rust_parser_version": "0.1.6",
                },
                "summary": {
                    "object_count_declared": 0,
                    "object_count_parsed": 0,
                    "string_count": 5,
                    "layer_count": 1,
                    "net_count": 0,
                    "padstack_count": 0,
                    "footprint_count": 0,
                    "placed_pad_count": 0,
                    "via_count": 0,
                    "track_count": 0,
                    "segment_count": 0,
                    "shape_count": 0,
                    "keepout_count": 0,
                    "net_assignment_count": 0,
                    "text_count": 0,
                    "diagnostic_count": 0,
                    "format_version": "V_172",
                    "allegro_version": "",
                    "units": "millimeters",
                },
                "header": {
                    "magic": 0x00140400,
                    "format_version": "V_172",
                    "file_role": 0,
                    "writer_program": 0,
                    "object_count": 0,
                    "max_key": 0,
                    "allegro_version": "",
                    "board_units_code": 3,
                    "board_units": "millimeters",
                    "units_divisor": 10000,
                    "coordinate_scale_nm": 2.54,
                    "string_count": 5,
                    "x27_end": 0,
                    "linked_lists": {},
                    "layer_map": [],
                },
                "strings": [
                    {"id": 1, "value": "ASSEMBLY_L2"},
                    {"id": 2, "value": "DISPLAY_L2"},
                    {"id": 3, "value": "ASSEMBLY_L3"},
                    {"id": 4, "value": "DISPLAY_L3"},
                    {"id": 5, "value": "ASSEMBLY_L9"},
                ],
                "layers": [
                    {
                        "key": 100,
                        "class_code": 0,
                        "names": [
                            "string:1",
                            "string:2",
                            "string:3",
                            "string:4",
                            "string:5",
                        ],
                    }
                ],
                "nets": [],
                "padstacks": [],
                "footprints": [],
                "placed_pads": [],
                "vias": [],
                "tracks": [],
                "shapes": [],
                "texts": [],
                "blocks": [],
                "block_counts": {},
                "diagnostics": [],
            }
        )
        refdes_map = _refdes_inner_layer_map(
            payload,
            ["TOP", "L2", "L3", "L9", "BOTTOM"],
            {entry.id: entry.value for entry in payload.strings or []},
        )
        text_layer = _component_text_layer(
            10,
            {
                20: BRDText(
                    key=20,
                    layer=BRDLayerInfo(
                        class_code=13,
                        subclass_code=4,
                        class_name="REF_DES",
                    ),
                )
            },
            {10: 20},
        )

        self.assertEqual(refdes_map[2], "L2")
        self.assertEqual(refdes_map[4], "L3")
        self.assertEqual(refdes_map[6], "L9")
        self.assertEqual(
            _component_layer_from_refdes_text(
                text_layer,
                ["TOP", "L2", "L3", "L9", "BOTTOM"],
                "TOP",
                "BOTTOM",
                refdes_map,
            ),
            "L3",
        )

    def test_brd_adapter_maps_basic_pad_via_geometry(self) -> None:
        from aurora_translator.semantic.adapters.brd import from_brd
        from aurora_translator.sources.brd.models import BRDLayout

        payload = BRDLayout.model_validate(
            {
                "metadata": {
                    "project_version": "1.0.43",
                    "parser_version": "0.1.2",
                    "output_schema_version": "0.1.0",
                    "source": "sample.brd",
                    "source_type": "file",
                    "backend": "rust-cli",
                    "rust_parser_version": "0.1.2",
                },
                "summary": {
                    "object_count_declared": 1,
                    "object_count_parsed": 1,
                    "string_count": 3,
                    "layer_count": 1,
                    "net_count": 1,
                    "padstack_count": 1,
                    "footprint_count": 1,
                    "placed_pad_count": 1,
                    "via_count": 1,
                    "track_count": 0,
                    "segment_count": 0,
                    "shape_count": 0,
                    "keepout_count": 0,
                    "net_assignment_count": 0,
                    "text_count": 0,
                    "diagnostic_count": 0,
                    "format_version": "V_181",
                    "allegro_version": "",
                    "units": "unknown",
                },
                "header": {
                    "magic": 0x00160100,
                    "format_version": "V_181",
                    "file_role": 0,
                    "writer_program": 0,
                    "object_count": 1,
                    "max_key": 900,
                    "allegro_version": "",
                    "board_units_code": 0,
                    "board_units": "unknown",
                    "units_divisor": 0,
                    "coordinate_scale_nm": None,
                    "string_count": 3,
                    "x27_end": 0,
                    "linked_lists": {},
                    "layer_map": [{"index": 0, "class_code": 6, "layer_list_key": 100}],
                },
                "strings": [
                    {"id": 1, "value": "TOP"},
                    {"id": 2, "value": "L2"},
                    {"id": 3, "value": "BOTTOM"},
                ],
                "layers": [
                    {
                        "key": 100,
                        "class_code": 0,
                        "names": ["string:1", "string:2", "string:3"],
                    }
                ],
                "nets": [
                    {
                        "key": 10,
                        "next": 0,
                        "name_string_id": 0,
                        "name": "GND",
                        "assignment": 200,
                        "fields": 0,
                        "match_group": 0,
                    }
                ],
                "padstacks": [
                    {
                        "key": 300,
                        "next": 0,
                        "name_string_id": 0,
                        "name": "VIA_0D1",
                        "layer_count": 3,
                        "drill_size_raw": 1000,
                        "fixed_component_count": 21,
                        "components_per_layer": 4,
                    }
                ],
                "footprints": [
                    {
                        "key": 400,
                        "next": 0,
                        "name_string_id": 0,
                        "name": "C01005",
                        "first_instance": 500,
                        "sym_lib_path_string_id": 0,
                        "sym_lib_path": None,
                        "coords_raw": [0, 0, 0, 0],
                    }
                ],
                "placed_pads": [
                    {
                        "key": 600,
                        "next": 0,
                        "layer": {
                            "class_code": 12,
                            "subclass_code": 0,
                            "class_name": "PIN",
                            "subclass_name": None,
                        },
                        "net_assignment": 200,
                        "parent_footprint": 500,
                        "pad": 700,
                        "pin_number": 1,
                        "name_text": 0,
                        "coords_raw": [10000, 20000, 11000, 21000],
                    }
                ],
                "vias": [
                    {
                        "key": 800,
                        "next": 0,
                        "layer": {
                            "class_code": 18,
                            "subclass_code": 0,
                            "class_name": "VIA_CLASS",
                            "subclass_name": None,
                        },
                        "net_assignment": 200,
                        "padstack": 300,
                        "x_raw": 10500,
                        "y_raw": 20500,
                    }
                ],
                "tracks": [],
                "shapes": [],
                "texts": [],
                "blocks": [
                    {
                        "block_type": 45,
                        "type_name": "FOOTPRINT_INST",
                        "offset": 0,
                        "length": 72,
                        "key": 500,
                        "next": 400,
                    }
                ],
                "block_counts": {},
                "diagnostics": [],
            }
        )

        board = from_brd(payload)

        self.assertEqual(
            [layer.name for layer in board.layers],
            ["TOP", "D0", "L2", "D1", "BOTTOM"],
        )
        self.assertEqual(board.units, "mm")
        self.assertEqual(board.summary.component_count, 1)
        self.assertEqual(board.summary.pad_count, 1)
        self.assertEqual(board.summary.via_count, 1)
        self.assertEqual(board.summary.via_template_count, 1)
        self.assertEqual(board.components[0].package_name, "C01005")
        self.assertEqual(board.pads[0].net_id, board.nets[0].id)
        self.assertEqual(board.vias[0].template_id, board.via_templates[0].id)

    def test_brd_partpad_rotation_uses_footprint_local_hint(self) -> None:
        from aurora_translator.semantic.models import (
            SemanticComponent,
            SemanticPad,
            SemanticPadGeometry,
        )
        from aurora_translator.targets.auroradb.parts import (
            _format_footprint_pad_rotation,
        )

        component = SemanticComponent(
            id="component:j4802",
            refdes="J4802",
            rotation=radians(90),
            source={"source_format": "brd", "path": "component"},
        )
        pad = SemanticPad(
            id="pad:j4802:1",
            geometry=SemanticPadGeometry(
                rotation=radians(90),
                footprint_rotation=0,
            ),
            source={"source_format": "brd", "path": "pad"},
        )

        self.assertEqual(
            _format_footprint_pad_rotation(pad, component, source_format="brd"),
            "0",
        )

    def test_brd_rectangular_pad_rotation_is_half_turn_symmetric(self) -> None:
        from aurora_translator.semantic.adapters.brd import (
            _pad_local_rotation_for_footprint,
        )
        from aurora_translator.sources.brd.models import (
            BRDPadDefinition,
            BRDPadstack,
            BRDPadstackComponent,
        )

        padstack = BRDPadstack(
            key=1,
            next=0,
            name_string_id=0,
            name="R0D95X0D3",
            layer_count=1,
            fixed_component_count=1,
            components_per_layer=1,
            components=[
                BRDPadstackComponent(
                    slot_index=0,
                    layer_index=0,
                    role="pad",
                    component_type=1,
                    type_name="rectangle",
                    width_raw=9500,
                    height_raw=3000,
                    x_offset_raw=0,
                    y_offset_raw=0,
                    shape_key=0,
                )
            ],
        )
        pad_definition = BRDPadDefinition(
            key=2,
            next=0,
            name_string_id=0,
            x_raw=0,
            y_raw=0,
            padstack=1,
            flags=0,
            rotation_mdeg=180000,
        )

        self.assertEqual(
            _pad_local_rotation_for_footprint(pad_definition, padstack),
            0,
        )


if __name__ == "__main__":
    unittest.main()
