from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = PROJECT_ROOT.parent

if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))


def _minimal_payload(source: str) -> dict:
    return {
        "metadata": {
            "project_version": "1.0.44",
            "parser_version": "0.7.0",
            "output_schema_version": "0.2.0",
            "source": source,
            "source_type": "file",
            "backend": "rust-cli",
            "rust_parser_version": "0.7.0",
        },
        "summary": {
            "file_size_bytes": 1,
            "record_count": 1,
            "text_record_count": 0,
            "binary_record_count": 1,
            "text_payload_bytes": 0,
            "binary_bytes": 1,
            "dsl_block_count": 0,
            "top_level_block_count": 0,
            "assignment_line_count": 0,
            "function_line_count": 0,
            "other_line_count": 0,
            "diagnostic_count": 0,
            "def_version": "12.1",
            "last_update_timestamp": None,
            "encrypted": False,
        },
        "domain": {
            "summary": {
                "layout_net_count": 1,
                "material_count": 0,
                "stackup_layer_count": 2,
                "board_metal_layer_count": 2,
                "dielectric_layer_count": 0,
                "padstack_count": 0,
                "padstack_layer_pad_count": 0,
                "multilayer_padstack_count": 0,
                "component_definition_count": 0,
                "component_pin_definition_count": 0,
                "component_placement_count": 0,
                "component_part_candidate_count": 0,
            },
            "layout_nets": [{"index": 0, "name": "GND"}],
            "materials": [],
            "stackup_layers": [
                {
                    "name": "TOP",
                    "id": 1,
                    "layer_type": "signal",
                    "top_bottom": "top",
                    "thickness": None,
                    "lower_elevation": None,
                    "material": None,
                    "fill_material": None,
                    "record_index": 0,
                },
                {
                    "name": "BOTTOM",
                    "id": 2,
                    "layer_type": "signal",
                    "top_bottom": "bottom",
                    "thickness": None,
                    "lower_elevation": None,
                    "material": None,
                    "fill_material": None,
                    "record_index": 0,
                },
            ],
            "board_metal_layers": [
                {
                    "name": "TOP",
                    "id": 1,
                    "layer_type": "signal",
                    "top_bottom": "top",
                    "thickness": None,
                    "lower_elevation": None,
                    "material": None,
                    "fill_material": None,
                    "record_index": 0,
                },
                {
                    "name": "BOTTOM",
                    "id": 2,
                    "layer_type": "signal",
                    "top_bottom": "bottom",
                    "thickness": None,
                    "lower_elevation": None,
                    "material": None,
                    "fill_material": None,
                    "record_index": 0,
                },
            ],
            "padstacks": [],
            "components": [],
            "component_placements": [],
            "binary_strings": {
                "string_count": 0,
                "unique_string_count": 0,
                "via_instance_name_count": 0,
                "unique_via_instance_name_count": 0,
                "line_instance_name_count": 0,
                "unique_line_instance_name_count": 0,
                "polygon_instance_name_count": 0,
                "unique_polygon_instance_name_count": 0,
                "polygon_void_instance_name_count": 0,
                "unique_polygon_void_instance_name_count": 0,
                "geometry_instance_name_count": 0,
                "unique_geometry_instance_name_count": 0,
            },
            "binary_geometry": {
                "padstack_instance_record_count": 1,
                "component_pin_padstack_instance_record_count": 0,
                "named_via_padstack_instance_record_count": 1,
                "unnamed_padstack_instance_record_count": 0,
                "padstack_instance_secondary_name_count": 0,
                "via_record_count": 0,
                "named_via_record_count": 0,
                "unnamed_via_record_count": 0,
                "unique_via_location_count": 1,
                "path_record_count": 0,
                "named_path_record_count": 0,
                "unnamed_path_record_count": 0,
                "path_line_segment_count": 0,
                "path_arc_segment_count": 0,
                "path_segment_count": 0,
                "path_width_count": 0,
                "polygon_record_count": 0,
                "polygon_outer_record_count": 0,
                "polygon_void_record_count": 0,
                "polygon_point_count": 0,
                "polygon_arc_segment_count": 0,
            },
            "binary_padstack_instance_records": [
                {
                    "offset": 1,
                    "geometry_id": 10,
                    "name": "via_1",
                    "name_kind": "via",
                    "net_index": 0,
                    "net_name": "GND",
                    "raw_owner_index": 0,
                    "raw_definition_index": 42,
                    "x": 0.001,
                    "y": 0.002,
                    "rotation": 0.0,
                    "drill_diameter": 0.0003,
                    "secondary_name": None,
                    "secondary_id": None,
                }
            ],
            "binary_path_records": [],
            "binary_polygon_records": [],
        },
        "records": None,
        "blocks": None,
        "diagnostics": [],
    }


class AEDBDefBinarySemanticAdapterTests(unittest.TestCase):
    def test_anf_sidecar_enriches_templates_shapes_and_polygon_voids(self) -> None:
        from aurora_translator.semantic.adapters.aedb_def_binary import (
            from_aedb_def_binary,
        )
        from aurora_translator.sources.aedb.def_models import AEDBDefBinaryLayout

        with TemporaryDirectory() as tmp:
            def_path = Path(tmp) / "case.def"
            def_path.write_bytes(b"\0")
            def_path.with_suffix(".anf").write_text(
                """
                $begin 'Padstacks'
                    $begin 'PAD1'
                        Hole(Circle(0.0003))
                        Signal('Rectangle0.001x0.002', 0, 0, 0, 0.0001)
                    $end 'PAD1'
                $end 'Padstacks'
                Graphics('Outline', Polygon(99, 0, vertex(0, 0), vertex(0.01, 0), vertex(0.01, 0.02), vertex(0, 0.02)))
                $begin 'LayoutNet'
                    Name='GND'
                    via(10, 'TOP', 'BOTTOM', 0.001, 0.002, 'PAD1', 0)
                    $begin 'PolygonWithVoids'
                        Layer='TOP'
                        Polygon(20, 0, vertex(0, 0), vertex(1, 0), vertex(1, 1))
                        $begin 'Voids'
                            Polygon(21, 0, vertex(0.1, 0.1), vertex(0.2, 0.1), vertex(0.2, 0.2))
                        $end 'Voids'
                    $end 'PolygonWithVoids'
                $end 'LayoutNet'
                """,
                encoding="utf-8",
            )
            payload = AEDBDefBinaryLayout.model_validate(
                _minimal_payload(str(def_path))
            )

            board = from_aedb_def_binary(payload, build_connectivity=False)

        self.assertEqual(board.via_templates[0].name, "PAD1")
        self.assertEqual(
            [layer.layer_name for layer in board.via_templates[0].layer_pads],
            ["TOP", "BOTTOM"],
        )
        self.assertIn(
            ("Rectangle", [0, 0, 0.001, 0.002]),
            [(shape.auroradb_type, shape.values) for shape in board.shapes],
        )
        self.assertEqual(board.vias[0].layer_names, ["TOP", "BOTTOM"])
        self.assertEqual(board.vias[0].geometry.get("via_type"), "through")
        self.assertEqual(board.vias[0].geometry.get("via_usage"), "routing_via")
        self.assertEqual(
            board.via_templates[0].geometry.get("via_type"),
            "through",
        )
        polygons = [
            primitive for primitive in board.primitives if primitive.kind == "polygon"
        ]
        self.assertEqual(len(polygons), 1)
        self.assertTrue(polygons[0].geometry.voids)
        self.assertEqual(board.board_outline.source, "anf_outline_sidecar")
        self.assertEqual(board.board_outline.values[0], 4)

    def test_anf_sidecar_polygon_padstack_shape(self) -> None:
        from aurora_translator.semantic.adapters.aedb_def_binary import (
            from_aedb_def_binary,
        )
        from aurora_translator.sources.aedb.def_models import AEDBDefBinaryLayout

        with TemporaryDirectory() as tmp:
            def_path = Path(tmp) / "case.def"
            def_path.write_bytes(b"\0")
            def_path.with_suffix(".anf").write_text(
                """
                $begin 'Padstacks'
                    $begin 'POLYPAD'
                        Hole(Circle(0))
                        Signal('Polygon-0.1x-0.05x0.1x-0.05x0.1x0.05x-0.1x0.05', 0, 0, 0)
                    $end 'POLYPAD'
                $end 'Padstacks'
                $begin 'LayoutNet'
                    Name='GND'
                    via(10, 'TOP', 'BOTTOM', 0.001, 0.002, 'POLYPAD', 0)
                $end 'LayoutNet'
                """,
                encoding="utf-8",
            )
            payload = AEDBDefBinaryLayout.model_validate(
                _minimal_payload(str(def_path))
            )

            board = from_aedb_def_binary(payload, build_connectivity=False)

        polygon_shapes = [
            shape for shape in board.shapes if shape.auroradb_type == "Polygon"
        ]
        self.assertEqual(len(polygon_shapes), 1)
        self.assertEqual(polygon_shapes[0].values[0], 4)

    def test_binary_records_export_polygons_voids_outline_and_drill_without_anf(
        self,
    ) -> None:
        from aurora_translator.semantic.adapters.aedb_def_binary import (
            from_aedb_def_binary,
        )
        from aurora_translator.sources.aedb.def_models import AEDBDefBinaryLayout

        with TemporaryDirectory() as tmp:
            def_path = Path(tmp) / "case.def"
            def_path.write_bytes(b"\0")
            payload_dict = _minimal_payload(str(def_path))
            payload_dict["domain"]["binary_padstack_instance_records"][0][
                "raw_definition_index"
            ] = 1000
            payload_dict["domain"]["padstacks"] = [
                {
                    "id": 42,
                    "name": "TEXTRECT",
                    "layer_pads": [
                        {
                            "layer_name": "TOP",
                            "id": 1,
                            "pad_shape": "Rct",
                            "pad_parameters": ["47.244mil", "74.803mil"],
                            "pad_offset_x": "0mil",
                            "pad_offset_y": "0mil",
                            "pad_rotation": "0deg",
                            "antipad_shape": "No",
                            "thermal_shape": "No",
                        }
                    ],
                    "record_index": 0,
                }
            ]
            payload_dict["domain"]["padstack_instance_definitions"] = [
                {
                    "record_index": 1,
                    "raw_definition_index": 1000,
                    "padstack_id": 42,
                    "padstack_name": "TEXTRECT",
                    "first_layer_id": 15,
                    "first_layer_name": "TOP",
                    "last_layer_id": 15,
                    "last_layer_name": "TOP",
                    "first_layer_positive": False,
                    "solder_ball_layer_id": None,
                    "solder_ball_layer_name": None,
                }
            ]
            payload_dict["domain"]["binary_geometry"].update(
                {
                    "polygon_record_count": 2,
                    "polygon_outer_record_count": 1,
                    "polygon_void_record_count": 1,
                    "polygon_point_count": 8,
                }
            )
            payload_dict["domain"]["binary_polygon_records"] = [
                {
                    "offset": 100,
                    "count_offset": 120,
                    "coordinate_offset": 128,
                    "geometry_id": 20,
                    "parent_geometry_id": None,
                    "is_void": False,
                    "layer_id": 1,
                    "layer_name": "TOP",
                    "net_index": 0,
                    "net_name": "GND",
                    "item_count": 4,
                    "point_count": 4,
                    "arc_segment_count": 0,
                    "items": [
                        {"kind": "point", "x": 0.0, "y": 0.0},
                        {"kind": "point", "x": 0.01, "y": 0.0},
                        {"kind": "point", "x": 0.01, "y": 0.02},
                        {"kind": "point", "x": 0.0, "y": 0.02},
                    ],
                },
                {
                    "offset": 200,
                    "count_offset": 220,
                    "coordinate_offset": 228,
                    "geometry_id": 21,
                    "parent_geometry_id": 20,
                    "is_void": True,
                    "layer_id": 1,
                    "layer_name": "TOP",
                    "net_index": 0,
                    "net_name": "GND",
                    "item_count": 4,
                    "point_count": 4,
                    "arc_segment_count": 0,
                    "items": [
                        {"kind": "point", "x": 0.001, "y": 0.001},
                        {"kind": "point", "x": 0.002, "y": 0.001},
                        {"kind": "point", "x": 0.002, "y": 0.002},
                        {"kind": "point", "x": 0.001, "y": 0.002},
                    ],
                },
            ]
            payload = AEDBDefBinaryLayout.model_validate(payload_dict)

            board = from_aedb_def_binary(payload, build_connectivity=False)

        polygons = [
            primitive for primitive in board.primitives if primitive.kind == "polygon"
        ]
        self.assertEqual(len(polygons), 1)
        self.assertEqual(polygons[0].geometry.record_kind, "binary_polygon")
        self.assertTrue(polygons[0].geometry.voids)
        self.assertEqual(polygons[0].geometry.void_ids, [21])
        self.assertEqual(board.board_outline.source, "aedb_def_binary_polygon_bbox")
        self.assertEqual(board.board_outline.values[0], 4)
        self.assertEqual(
            board.via_templates[0].geometry.source,
            "aedb_def_binary_instance_drill",
        )
        self.assertEqual(
            board.via_templates[0].geometry.get("via_type"),
            "single_layer",
        )
        self.assertEqual(board.vias[0].geometry.get("via_type"), "single_layer")
        self.assertEqual(board.vias[0].geometry.get("start_layer"), "TOP")
        self.assertEqual(board.vias[0].geometry.get("stop_layer"), "TOP")
        self.assertEqual(board.via_templates[0].name, "TEXTRECT")
        self.assertIsNotNone(board.via_templates[0].barrel_shape_id)
        self.assertTrue(
            any(
                shape.auroradb_type == "Rectangle"
                and abs(shape.values[2] - 0.0011999976) < 1e-12
                and abs(shape.values[3] - 0.0018999962) < 1e-12
                for shape in board.shapes
            )
        )

    def test_binary_polygon_synthesizes_clearance_void_for_crossing_via(self) -> None:
        from aurora_translator.semantic.adapters.aedb_def_binary import (
            from_aedb_def_binary,
        )
        from aurora_translator.sources.aedb.def_models import AEDBDefBinaryLayout

        payload_dict = _minimal_payload("case.def")
        payload_dict["domain"]["layout_nets"] = [
            {"index": 0, "name": "GND"},
            {"index": 1, "name": "SIG"},
        ]
        payload_dict["domain"]["binary_padstack_instance_records"][0].update(
            {
                "net_index": 1,
                "net_name": "SIG",
                "raw_definition_index": 42,
                "x": 0.005,
                "y": 0.005,
                "drill_diameter": 0.0002032,
            }
        )
        payload_dict["domain"]["padstacks"] = [
            {
                "id": 42,
                "name": "VIA8D16",
                "layer_pads": [
                    {
                        "layer_name": "TOP",
                        "id": 1,
                        "pad_shape": "Cir",
                        "pad_parameters": ["16mil"],
                        "pad_offset_x": "0mil",
                        "pad_offset_y": "0mil",
                        "pad_rotation": "0deg",
                        "antipad_shape": "Cir",
                        "thermal_shape": "No",
                    },
                    {
                        "layer_name": "BOTTOM",
                        "id": 2,
                        "pad_shape": "Cir",
                        "pad_parameters": ["16mil"],
                        "pad_offset_x": "0mil",
                        "pad_offset_y": "0mil",
                        "pad_rotation": "0deg",
                        "antipad_shape": "Cir",
                        "thermal_shape": "No",
                    },
                ],
                "record_index": 0,
            }
        ]
        payload_dict["domain"]["padstack_instance_definitions"] = [
            {
                "record_index": 1,
                "raw_definition_index": 42,
                "padstack_id": 42,
                "padstack_name": "VIA8D16",
                "first_layer_id": 1,
                "first_layer_name": "TOP",
                "last_layer_id": 2,
                "last_layer_name": "BOTTOM",
                "first_layer_positive": False,
                "solder_ball_layer_id": None,
                "solder_ball_layer_name": None,
            }
        ]
        payload_dict["domain"]["binary_geometry"].update(
            {
                "polygon_record_count": 1,
                "polygon_outer_record_count": 1,
                "polygon_void_record_count": 0,
                "polygon_point_count": 4,
            }
        )
        payload_dict["domain"]["binary_polygon_records"] = [
            {
                "offset": 100,
                "count_offset": 120,
                "coordinate_offset": 128,
                "geometry_id": 20,
                "parent_geometry_id": None,
                "is_void": False,
                "layer_id": 1,
                "layer_name": "TOP",
                "net_index": 0,
                "net_name": "GND",
                "item_count": 4,
                "point_count": 4,
                "arc_segment_count": 0,
                "items": [
                    {"kind": "point", "x": 0.0, "y": 0.0},
                    {"kind": "point", "x": 0.01, "y": 0.0},
                    {"kind": "point", "x": 0.01, "y": 0.01},
                    {"kind": "point", "x": 0.0, "y": 0.01},
                ],
            }
        ]
        payload = AEDBDefBinaryLayout.model_validate(payload_dict)

        board = from_aedb_def_binary(payload, build_connectivity=False)

        polygon = next(
            primitive for primitive in board.primitives if primitive.kind == "polygon"
        )
        self.assertTrue(polygon.geometry.has_voids)
        self.assertEqual(len(polygon.geometry.voids), 1)
        void = polygon.geometry.voids[0]
        self.assertEqual(void.get("polarity"), "synthetic_clearance")
        self.assertEqual(void.get("source_padstack_geometry_id"), 10)
        self.assertEqual(void.raw_points[1][4], 0)
        self.assertAlmostEqual(void.bbox[0], 0.005 - 0.0003307, places=7)
        self.assertAlmostEqual(void.bbox[2], 0.005 + 0.0003307, places=7)

    def test_trailing_arc_native_void_suppresses_clearance_void(self) -> None:
        from aurora_translator.semantic.adapters.aedb_def_binary import (
            from_aedb_def_binary,
        )
        from aurora_translator.sources.aedb.def_models import AEDBDefBinaryLayout

        mil = 25.4e-6
        payload_dict = _minimal_payload("case.def")
        payload_dict["domain"]["layout_nets"] = [
            {"index": 0, "name": "GND"},
            {"index": 1, "name": "SIG"},
        ]
        payload_dict["domain"]["binary_padstack_instance_records"][0].update(
            {
                "net_index": 1,
                "net_name": "SIG",
                "raw_definition_index": 42,
                "x": 730.0 * mil,
                "y": 190.0 * mil,
                "drill_diameter": 8.0 * mil,
            }
        )
        payload_dict["domain"]["padstacks"] = [
            {
                "id": 42,
                "name": "VIA8D16",
                "layer_pads": [
                    {
                        "layer_name": "TOP",
                        "id": 1,
                        "pad_shape": "Cir",
                        "pad_parameters": ["16mil"],
                        "pad_offset_x": "0mil",
                        "pad_offset_y": "0mil",
                        "pad_rotation": "0deg",
                        "antipad_shape": "Cir",
                        "thermal_shape": "No",
                    },
                    {
                        "layer_name": "BOTTOM",
                        "id": 2,
                        "pad_shape": "Cir",
                        "pad_parameters": ["16mil"],
                        "pad_offset_x": "0mil",
                        "pad_offset_y": "0mil",
                        "pad_rotation": "0deg",
                        "antipad_shape": "Cir",
                        "thermal_shape": "No",
                    },
                ],
                "record_index": 0,
            }
        ]
        payload_dict["domain"]["padstack_instance_definitions"] = [
            {
                "record_index": 1,
                "raw_definition_index": 42,
                "padstack_id": 42,
                "padstack_name": "VIA8D16",
                "first_layer_id": 1,
                "first_layer_name": "TOP",
                "last_layer_id": 2,
                "last_layer_name": "BOTTOM",
                "first_layer_positive": False,
                "solder_ball_layer_id": None,
                "solder_ball_layer_name": None,
            }
        ]
        payload_dict["domain"]["binary_geometry"].update(
            {
                "polygon_record_count": 2,
                "polygon_outer_record_count": 1,
                "polygon_void_record_count": 1,
                "polygon_point_count": 8,
                "polygon_arc_segment_count": 4,
            }
        )
        payload_dict["domain"]["binary_polygon_records"] = [
            {
                "offset": 100,
                "count_offset": 120,
                "coordinate_offset": 128,
                "geometry_id": 20,
                "parent_geometry_id": None,
                "is_void": False,
                "layer_id": 2,
                "layer_name": "BOTTOM",
                "net_index": 0,
                "net_name": "GND",
                "item_count": 4,
                "point_count": 4,
                "arc_segment_count": 0,
                "items": [
                    {"kind": "point", "x": 0.0, "y": 0.0},
                    {"kind": "point", "x": 0.05, "y": 0.0},
                    {"kind": "point", "x": 0.05, "y": 0.05},
                    {"kind": "point", "x": 0.0, "y": 0.05},
                ],
            },
            {
                "offset": 200,
                "count_offset": 220,
                "coordinate_offset": 228,
                "geometry_id": 21,
                "parent_geometry_id": 20,
                "is_void": True,
                "layer_id": 2,
                "layer_name": "BOTTOM",
                "net_index": 0,
                "net_name": "GND",
                "item_count": 8,
                "point_count": 4,
                "arc_segment_count": 4,
                "items": [
                    {"kind": "point", "x": 739.3 * mil, "y": 180.89 * mil},
                    {"kind": "arc_height", "arc_height": -0.571 * mil},
                    {"kind": "point", "x": 739.3 * mil, "y": 178.09 * mil},
                    {"kind": "arc_height", "arc_height": 22.129 * mil},
                    {"kind": "point", "x": 720.7 * mil, "y": 178.09 * mil},
                    {"kind": "arc_height", "arc_height": -0.571 * mil},
                    {"kind": "point", "x": 720.7 * mil, "y": 180.89 * mil},
                    {"kind": "arc_height", "arc_height": 22.129 * mil},
                ],
            },
        ]
        payload = AEDBDefBinaryLayout.model_validate(payload_dict)

        board = from_aedb_def_binary(payload, build_connectivity=False)

        polygon = next(
            primitive for primitive in board.primitives if primitive.kind == "polygon"
        )
        self.assertEqual(len(polygon.geometry.voids), 1)
        self.assertNotEqual(
            polygon.geometry.voids[0].get("polarity"), "synthetic_clearance"
        )

    def test_binary_padstack_hole_text_uses_standard_c200_barrel(self) -> None:
        from aurora_translator.semantic.adapters.aedb_def_binary import (
            from_aedb_def_binary,
        )
        from aurora_translator.sources.aedb.def_models import AEDBDefBinaryLayout

        payload_dict = _minimal_payload("case.def")
        payload_dict["domain"]["padstacks"] = [
            {
                "id": 42,
                "name": "C200-109T",
                "hole_shape": "Cir",
                "hole_parameters": ["109mil"],
                "layer_pads": [
                    {
                        "layer_name": "TOP",
                        "id": 1,
                        "pad_shape": "Cir",
                        "pad_parameters": ["200mil"],
                        "antipad_shape": "Cir",
                        "antipad_parameters": ["220mil"],
                        "thermal_shape": "No",
                    },
                    {
                        "layer_name": "BOTTOM",
                        "id": 2,
                        "pad_shape": "Cir",
                        "pad_parameters": ["200mil"],
                        "antipad_shape": "Cir",
                        "antipad_parameters": ["220mil"],
                        "thermal_shape": "No",
                    },
                ],
                "record_index": 0,
            }
        ]
        payload_dict["domain"]["padstack_instance_definitions"] = [
            {
                "record_index": 1,
                "raw_definition_index": 42,
                "padstack_id": 42,
                "padstack_name": "C200-109T",
                "first_layer_id": 1,
                "first_layer_name": "TOP",
                "last_layer_id": 2,
                "last_layer_name": "BOTTOM",
                "first_layer_positive": False,
                "solder_ball_layer_id": None,
                "solder_ball_layer_name": None,
            }
        ]
        payload = AEDBDefBinaryLayout.model_validate(payload_dict)

        board = from_aedb_def_binary(payload, build_connectivity=False)

        template = next(
            via_template
            for via_template in board.via_templates
            if via_template.name == "C200-109T"
        )
        barrel = next(shape for shape in board.shapes if shape.id == template.barrel_shape_id)
        self.assertEqual(barrel.auroradb_type, "RectCutCorner")
        self.assertEqual(barrel.kind, "rectcutcorner_y")
        self.assertAlmostEqual(barrel.values[2], 150 * 0.0000254, places=12)
        self.assertAlmostEqual(barrel.values[3], 200 * 0.0000254, places=12)
        self.assertAlmostEqual(barrel.values[4], 75 * 0.0000254, places=12)

    def test_nonrouting_clearance_uses_padstack_antipad_source_shape(self) -> None:
        from aurora_translator.semantic.adapters.aedb_def_binary import (
            _synthetic_clearance_diameter,
            _template_infos,
        )
        from aurora_translator.sources.aedb.def_models import AEDBDefBinaryLayout

        payload_dict = _minimal_payload("case.def")
        payload_dict["domain"]["stackup_layers"].insert(
            1,
            {
                "name": "L2",
                "id": 3,
                "layer_type": "signal",
                "top_bottom": "inner",
                "thickness": None,
                "lower_elevation": None,
                "material": None,
                "fill_material": None,
                "record_index": 0,
            },
        )
        payload_dict["domain"]["board_metal_layers"].insert(
            1,
            payload_dict["domain"]["stackup_layers"][1],
        )
        payload_dict["domain"]["binary_padstack_instance_records"][0].update(
            {
                "name": "UNNAMED_1",
                "name_kind": "unnamed",
                "raw_definition_index": 64,
                "net_index": None,
                "net_name": None,
                "drill_diameter": 64 * 0.0000254,
            }
        )
        payload_dict["domain"]["padstacks"] = [
            {
                "id": 64,
                "name": "HOLE64N",
                "hole_shape": "Cir",
                "hole_parameters": ["64mil"],
                "layer_pads": [
                    {
                        "layer_name": layer_name,
                        "id": index,
                        "pad_shape": "Cir",
                        "pad_parameters": ["64mil"],
                        "antipad_shape": "Cir",
                        "antipad_parameters": ["84mil"],
                        "thermal_shape": "No",
                    }
                    for index, layer_name in enumerate(["TOP", "L2", "BOTTOM"], 1)
                ],
                "record_index": 0,
            }
        ]
        payload_dict["domain"]["padstack_instance_definitions"] = [
            {
                "record_index": 1,
                "raw_definition_index": 64,
                "padstack_id": 64,
                "padstack_name": "HOLE64N",
                "first_layer_id": 1,
                "first_layer_name": "TOP",
                "last_layer_id": 2,
                "last_layer_name": "BOTTOM",
                "first_layer_positive": False,
                "solder_ball_layer_id": None,
                "solder_ball_layer_name": None,
            }
        ]
        payload = AEDBDefBinaryLayout.model_validate(payload_dict)
        board_metal_layers = ["TOP", "L2", "BOTTOM"]
        template_infos = _template_infos(
            payload,
            board_metal_layers,
            {layer.casefold(): index for index, layer in enumerate(board_metal_layers)},
            {},
            {},
        )

        diameter = _synthetic_clearance_diameter(
            payload.domain.binary_padstack_instance_records[0],
            "L2",
            template_infos,
        )

        self.assertAlmostEqual(diameter, 84 * 0.0000254 + 0.000001, places=12)

    def test_padstack_name_shape_hints_cover_metric_and_imperial_names(self) -> None:
        from aurora_translator.semantic.adapters.aedb_def_binary import (
            _shape_from_padstack_name,
        )

        cases = {
            "SMD50REC12": ("Rectangle", (0, 0, 0.00127, 0.0003048)),
            "2P6X2P5SMD": ("Rectangle", (0, 0, 0.0026, 0.0025)),
            "3MM175X3MM175": ("Rectangle", (0, 0, 0.003175, 0.003175)),
            "S_RCT_0-60_X_0-20": ("Rectangle", (0, 0, 0.0006, 0.0002)),
            "120SMD190_01": ("Rectangle", (0, 0, 0.0012, 0.0019)),
            "S_OBL_0-75_X_0-30": (
                "RoundedRectangle",
                (0, 0, 0.00075, 0.0003, 0.00015),
            ),
        }
        for name, (auroradb_type, values) in cases.items():
            with self.subTest(name=name):
                shape = _shape_from_padstack_name(name)
                self.assertIsNotNone(shape)
                self.assertEqual(shape.auroradb_type, auroradb_type)
                self.assertEqual(len(shape.values), len(values))
                for actual, expected in zip(shape.values, values, strict=True):
                    self.assertAlmostEqual(actual, expected, places=12)

    def test_padstack_layer_pad_oval_uses_explicit_radius(self) -> None:
        from aurora_translator.semantic.adapters.aedb_def_binary import (
            _shape_from_padstack_layer_pad,
        )

        shape = _shape_from_padstack_layer_pad(
            SimpleNamespace(
                layer_name="TOP",
                pad_shape="Ov",
                pad_parameters=["12mil", "63mil", "6mil"],
            )
        )

        self.assertIsNotNone(shape)
        self.assertEqual(shape.auroradb_type, "RoundedRectangle")
        self.assertEqual(len(shape.values), 5)
        self.assertAlmostEqual(shape.values[2], 0.0003048, places=12)
        self.assertAlmostEqual(shape.values[3], 0.0016002, places=12)
        self.assertAlmostEqual(shape.values[4], 0.0001524, places=12)

    def test_padstack_layer_pad_square_uses_single_parameter(self) -> None:
        from aurora_translator.semantic.adapters.aedb_def_binary import (
            _shape_from_padstack_layer_pad,
        )

        shape = _shape_from_padstack_layer_pad(
            SimpleNamespace(
                layer_name="TOP",
                pad_shape="Sq",
                pad_parameters=["56.299mil"],
            )
        )

        self.assertIsNotNone(shape)
        self.assertEqual(shape.auroradb_type, "Rectangle")
        self.assertAlmostEqual(shape.values[2], 0.001430, places=6)
        self.assertAlmostEqual(shape.values[3], 0.001430, places=6)

    def test_component_side_is_inferred_from_pin_primary_layers(self) -> None:
        from aurora_translator.semantic.adapters.aedb_def_binary import (
            from_aedb_def_binary,
        )
        from aurora_translator.sources.aedb.def_models import AEDBDefBinaryLayout

        payload_dict = _minimal_payload("case.def")
        payload_dict["domain"]["component_placements"] = [
            {
                "refdes": "U1",
                "component_class": "IO",
                "device_type": "DEV",
                "value": "VAL",
                "package": "PKG",
                "part_number": "PN",
                "symbol_box": None,
                "part_name_candidates": [],
                "record_index": 1,
            }
        ]
        payload_dict["domain"]["padstack_instance_definitions"] = [
            {
                "record_index": 1,
                "raw_definition_index": 42,
                "padstack_id": None,
                "padstack_name": "BOTPAD",
                "first_layer_id": 2,
                "first_layer_name": "BOTTOM",
                "last_layer_id": 2,
                "last_layer_name": "BOTTOM",
                "first_layer_positive": False,
                "solder_ball_layer_id": None,
                "solder_ball_layer_name": None,
            }
        ]
        payload_dict["domain"]["binary_padstack_instance_records"][0].update(
            {"name": "U1-1", "name_kind": "component_pin", "rotation": math.pi}
        )
        payload = AEDBDefBinaryLayout.model_validate(payload_dict)

        board = from_aedb_def_binary(payload, build_connectivity=False)

        self.assertEqual(board.components[0].side, "bottom")
        self.assertEqual(board.components[0].layer_name, "BOTTOM")
        self.assertAlmostEqual(board.components[0].rotation, math.pi)
        self.assertEqual(board.pins[0].layer_name, "BOTTOM")

    def test_no_net_unnamed_records_emit_pads_without_net_pins(self) -> None:
        from aurora_translator.semantic.adapters.aedb_def_binary import (
            from_aedb_def_binary,
        )
        from aurora_translator.sources.aedb.def_models import AEDBDefBinaryLayout

        payload_dict = _minimal_payload("case.def")
        payload_dict["domain"]["layout_nets"] = [{"index": 0, "name": "GND"}]
        payload_dict["domain"]["component_placements"] = [
            {
                "refdes": "U1",
                "component_class": "IO",
                "device_type": "DEV",
                "value": "VAL",
                "package": "PKG",
                "part_number": "PN",
                "symbol_box": None,
                "part_name_candidates": [],
                "record_index": 1,
            }
        ]
        payload_dict["domain"]["padstack_instance_definitions"] = [
            {
                "record_index": 1,
                "raw_definition_index": 42,
                "padstack_id": None,
                "padstack_name": "BOTPAD",
                "first_layer_id": 2,
                "first_layer_name": "BOTTOM",
                "last_layer_id": 2,
                "last_layer_name": "BOTTOM",
                "first_layer_positive": False,
                "solder_ball_layer_id": None,
                "solder_ball_layer_name": None,
            }
        ]
        payload_dict["domain"]["binary_padstack_instance_records"] = [
            {
                "offset": 1,
                "geometry_id": 10,
                "name": "U1-UNNAMED_1",
                "name_kind": "component_pin",
                "net_index": None,
                "net_name": None,
                "raw_owner_index": 0,
                "raw_definition_index": 42,
                "x": 0.001,
                "y": 0.002,
                "rotation": 0.0,
                "drill_diameter": None,
                "secondary_name": "UNNAMED_1",
                "secondary_id": None,
            },
            {
                "offset": 2,
                "geometry_id": 11,
                "name": "UNNAMED_2",
                "name_kind": "unnamed",
                "net_index": None,
                "net_name": None,
                "raw_owner_index": 0,
                "raw_definition_index": 42,
                "x": 0.003,
                "y": 0.004,
                "rotation": 0.0,
                "drill_diameter": None,
                "secondary_name": "UNNAMED_2",
                "secondary_id": None,
            },
        ]
        payload = AEDBDefBinaryLayout.model_validate(payload_dict)

        board = from_aedb_def_binary(payload, build_connectivity=False)

        nonet = next(net for net in board.nets if net.name == "NONET")
        self.assertEqual(board.pins, [])
        self.assertEqual(len(board.pads), 2)
        self.assertEqual(len(nonet.pad_ids), 2)
        self.assertTrue(all(pad.net_id == nonet.id for pad in board.pads))

    def test_via_taxonomy_classifies_layer_spans(self) -> None:
        from aurora_translator.semantic.adapters.aedb_def_binary import _via_taxonomy

        metal_layers = ["TOP", "L2", "L3", "BOTTOM"]
        cases = {
            ("TOP", "L2", "L3", "BOTTOM"): "through",
            ("TOP", "L2"): "blind",
            ("L3", "BOTTOM"): "blind",
            ("L2", "L3"): "buried",
            ("L2",): "single_layer",
            (): "unknown",
        }
        for layer_names, via_type in cases.items():
            with self.subTest(layer_names=layer_names):
                taxonomy = _via_taxonomy(list(layer_names), metal_layers)
                self.assertEqual(taxonomy.via_type, via_type)

    def test_suppressed_component_pad_does_not_emit_extra_via(self) -> None:
        from aurora_translator.semantic.models import SemanticPad, SemanticPadGeometry
        from aurora_translator.targets.auroradb.geometry import (
            _component_pad_can_emit_as_via,
        )

        pad = SemanticPad.model_construct(
            component_id="component:U1",
            pin_id="pin:U1:1",
            net_id="net:GND",
            padstack_definition="PAD1",
            geometry=SemanticPadGeometry.model_construct(suppress_via_export=True),
        )

        self.assertFalse(_component_pad_can_emit_as_via(pad))


if __name__ == "__main__":
    unittest.main()
