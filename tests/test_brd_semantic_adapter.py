from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = PROJECT_ROOT.parent

if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))


class BRDSemanticAdapterTests(unittest.TestCase):
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
            [layer.name for layer in board.layers], ["TOP", "L2", "BOTTOM"]
        )
        self.assertEqual(board.units, "mm")
        self.assertEqual(board.summary.component_count, 1)
        self.assertEqual(board.summary.pad_count, 1)
        self.assertEqual(board.summary.via_count, 1)
        self.assertEqual(board.summary.via_template_count, 1)
        self.assertEqual(board.components[0].package_name, "C01005")
        self.assertEqual(board.pads[0].net_id, board.nets[0].id)
        self.assertEqual(board.vias[0].template_id, board.via_templates[0].id)


if __name__ == "__main__":
    unittest.main()
