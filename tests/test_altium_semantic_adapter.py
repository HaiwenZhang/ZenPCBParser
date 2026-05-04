from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = PROJECT_ROOT.parent

if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))


class AltiumSemanticAdapterTests(unittest.TestCase):
    def test_altium_adapter_maps_basic_board_objects(self) -> None:
        from aurora_translator.semantic.adapters.altium import from_altium
        from aurora_translator.sources.altium.models import AltiumLayout

        point = {
            "x_raw": 0,
            "y_raw": 0,
            "x": 0.0,
            "y": 0.0,
        }
        payload = AltiumLayout.model_validate(
            {
                "metadata": {
                    "project_version": "1.0.44",
                    "parser_version": "0.1.0",
                    "output_schema_version": "0.1.0",
                    "source": "sample.PcbDoc",
                    "source_type": "file",
                    "backend": "rust-cli",
                    "rust_parser_version": "0.1.0",
                },
                "summary": {
                    "stream_count": 8,
                    "parsed_stream_count": 8,
                    "layer_count": 2,
                    "net_count": 1,
                    "class_count": 0,
                    "rule_count": 0,
                    "polygon_count": 0,
                    "component_count": 1,
                    "pad_count": 1,
                    "via_count": 1,
                    "track_count": 1,
                    "arc_count": 0,
                    "fill_count": 0,
                    "region_count": 0,
                    "text_count": 0,
                    "board_outline_vertex_count": 4,
                    "diagnostic_count": 0,
                    "units": "mil",
                    "format": "altium-pcbdoc",
                },
                "file_header": "PCB 6.0",
                "board": {
                    "sheet_position": point,
                    "sheet_size": {
                        "x_raw": 100000,
                        "y_raw": 50000,
                        "x": 10.0,
                        "y": 5.0,
                    },
                    "layer_count_declared": 2,
                    "outline": [
                        {
                            "is_round": False,
                            "radius": 0.0,
                            "start_angle": 0.0,
                            "end_angle": 0.0,
                            "position": {
                                "x_raw": 0,
                                "y_raw": 0,
                                "x": 0.0,
                                "y": 0.0,
                            },
                        },
                        {
                            "is_round": False,
                            "radius": 0.0,
                            "start_angle": 0.0,
                            "end_angle": 0.0,
                            "position": {
                                "x_raw": 100000,
                                "y_raw": 0,
                                "x": 10.0,
                                "y": 0.0,
                            },
                        },
                        {
                            "is_round": False,
                            "radius": 0.0,
                            "start_angle": 0.0,
                            "end_angle": 0.0,
                            "position": {
                                "x_raw": 100000,
                                "y_raw": -50000,
                                "x": 10.0,
                                "y": 5.0,
                            },
                        },
                        {
                            "is_round": False,
                            "radius": 0.0,
                            "start_angle": 0.0,
                            "end_angle": 0.0,
                            "position": {
                                "x_raw": 0,
                                "y_raw": -50000,
                                "x": 0.0,
                                "y": 5.0,
                            },
                        },
                    ],
                    "properties": {},
                },
                "layers": [
                    {
                        "layer_id": 1,
                        "name": "TopLayer",
                        "next_id": 32,
                        "prev_id": None,
                        "copper_thickness": 1.4,
                        "dielectric_constant": None,
                        "dielectric_thickness": None,
                        "dielectric_material": None,
                        "mechanical_enabled": False,
                        "mechanical_kind": None,
                    },
                    {
                        "layer_id": 32,
                        "name": "BottomLayer",
                        "next_id": None,
                        "prev_id": 1,
                        "copper_thickness": 1.4,
                        "dielectric_constant": None,
                        "dielectric_thickness": None,
                        "dielectric_material": None,
                        "mechanical_enabled": False,
                        "mechanical_kind": None,
                    },
                ],
                "nets": [{"index": 0, "name": "GND", "properties": {}}],
                "classes": [],
                "rules": [],
                "polygons": [],
                "components": [
                    {
                        "index": 0,
                        "layer_id": 1,
                        "layer_name": "TopLayer",
                        "position": {
                            "x_raw": 10000,
                            "y_raw": -20000,
                            "x": 1.0,
                            "y": 2.0,
                        },
                        "rotation": 90.0,
                        "locked": False,
                        "name_on": True,
                        "comment_on": True,
                        "source_designator": "U1",
                        "source_unique_id": "ABC",
                        "source_hierarchical_path": None,
                        "source_footprint_library": "lib.PcbLib",
                        "pattern": "QFN",
                        "source_component_library": None,
                        "source_lib_reference": "MCU",
                        "properties": {},
                    }
                ],
                "pads": [
                    {
                        "index": 0,
                        "name": "1",
                        "layer_id": 74,
                        "layer_name": "MultiLayer",
                        "net": 0,
                        "component": 0,
                        "position": {
                            "x_raw": 10000,
                            "y_raw": -20000,
                            "x": 1.0,
                            "y": 2.0,
                        },
                        "top_size": {
                            "x_raw": 400000,
                            "y_raw": 400000,
                            "x": 40.0,
                            "y": 40.0,
                        },
                        "mid_size": {
                            "x_raw": 350000,
                            "y_raw": 350000,
                            "x": 35.0,
                            "y": 35.0,
                        },
                        "bottom_size": {
                            "x_raw": 300000,
                            "y_raw": 300000,
                            "x": 30.0,
                            "y": 30.0,
                        },
                        "hole_size": 12.0,
                        "top_shape": "Round",
                        "mid_shape": "Round",
                        "bottom_shape": "Round",
                        "direction": 0.0,
                        "plated": True,
                        "pad_mode": "thru_hole",
                        "hole_rotation": 0.0,
                        "from_layer_id": 1,
                        "to_layer_id": 32,
                        "size_and_shape": None,
                        "is_locked": False,
                        "is_tent_top": False,
                        "is_tent_bottom": False,
                        "is_test_fab_top": False,
                        "is_test_fab_bottom": False,
                    }
                ],
                "vias": [
                    {
                        "index": 0,
                        "net": 0,
                        "position": {
                            "x_raw": 20000,
                            "y_raw": -30000,
                            "x": 2.0,
                            "y": 3.0,
                        },
                        "diameter": 24.0,
                        "hole_size": 10.0,
                        "start_layer_id": 1,
                        "start_layer_name": "TopLayer",
                        "end_layer_id": 32,
                        "end_layer_name": "BottomLayer",
                        "via_mode": "thru",
                        "diameter_by_layer": [],
                        "is_locked": False,
                        "is_tent_top": False,
                        "is_tent_bottom": False,
                    }
                ],
                "tracks": [
                    {
                        "index": 0,
                        "layer_id": 1,
                        "layer_name": "TopLayer",
                        "net": 0,
                        "component": 65535,
                        "polygon": 65535,
                        "subpolygon": 65535,
                        "start": {
                            "x_raw": 0,
                            "y_raw": 0,
                            "x": 0.0,
                            "y": 0.0,
                        },
                        "end": {
                            "x_raw": 10000,
                            "y_raw": -10000,
                            "x": 1.0,
                            "y": 1.0,
                        },
                        "width": 5.0,
                        "is_locked": False,
                        "is_keepout": False,
                        "is_polygon_outline": False,
                        "keepout_restrictions": 0,
                    }
                ],
                "arcs": [],
                "fills": [],
                "regions": [],
                "texts": [],
                "streams": [],
                "stream_counts": {},
                "diagnostics": [],
            }
        )

        board = from_altium(payload)

        self.assertEqual(board.metadata.source_format, "altium")
        self.assertEqual(board.units, "mil")
        self.assertEqual(
            [layer.name for layer in board.layers], ["TopLayer", "BottomLayer"]
        )
        self.assertEqual(board.summary.component_count, 1)
        self.assertEqual(board.summary.footprint_count, 1)
        self.assertEqual(board.summary.pin_count, 1)
        self.assertEqual(board.summary.pad_count, 1)
        self.assertEqual(board.summary.via_count, 1)
        self.assertEqual(board.summary.primitive_count, 1)
        self.assertEqual(board.components[0].refdes, "U1")
        self.assertEqual(board.pads[0].net_id, board.nets[0].id)
        self.assertEqual(board.vias[0].template_id, board.via_templates[0].id)
        self.assertEqual(board.primitives[0].kind, "trace")
        self.assertEqual(board.board_outline.kind, "polygon")


if __name__ == "__main__":
    unittest.main()
