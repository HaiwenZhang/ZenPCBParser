from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = PROJECT_ROOT.parent

if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))


class AltiumSemanticAdapterTests(unittest.TestCase):
    def test_altium_pad_solder_layer_maps_to_metal_side(self) -> None:
        from aurora_translator.semantic.adapters.altium import _pad_layer_name

        top_pad = SimpleNamespace(layer_name="Top Solder")
        bottom_pad = SimpleNamespace(layer_name="Bottom Solder")

        self.assertEqual(
            _pad_layer_name(top_pad, None, {}, "TopLayer", "BottomLayer"),
            "TopLayer",
        )
        self.assertEqual(
            _pad_layer_name(bottom_pad, None, {}, "TopLayer", "BottomLayer"),
            "BottomLayer",
        )

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
                    "class_count": 1,
                    "rule_count": 0,
                    "polygon_count": 0,
                    "component_count": 1,
                    "pad_count": 1,
                    "via_count": 1,
                    "track_count": 1,
                    "arc_count": 0,
                    "fill_count": 0,
                    "region_count": 0,
                    "text_count": 1,
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
                "classes": [
                    {
                        "index": 0,
                        "name": "Inside Board Components",
                        "unique_id": None,
                        "kind": 4,
                        "members": ["U1", "LOGO1"],
                        "properties": {},
                    }
                ],
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
                        "source_designator": None,
                        "source_unique_id": "ABC",
                        "source_hierarchical_path": None,
                        "source_footprint_library": "lib.PcbLib",
                        "pattern": "QFN",
                        "source_component_library": None,
                        "source_lib_reference": None,
                        "properties": {},
                    },
                    {
                        "index": 1,
                        "layer_id": 1,
                        "layer_name": "TopLayer",
                        "position": {
                            "x_raw": 30000,
                            "y_raw": -40000,
                            "x": 3.0,
                            "y": 4.0,
                        },
                        "rotation": 0.0,
                        "locked": False,
                        "name_on": True,
                        "comment_on": True,
                        "source_designator": "LOGO1",
                        "source_unique_id": "LOGO",
                        "source_hierarchical_path": None,
                        "source_footprint_library": "lib.PcbLib",
                        "pattern": "LOGO",
                        "source_component_library": None,
                        "source_lib_reference": "LOGO",
                        "properties": {},
                    },
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
                "texts": [
                    {
                        "index": 0,
                        "layer_id": 1,
                        "layer_name": "TopLayer",
                        "component": 0,
                        "position": point,
                        "height": 1.0,
                        "rotation": 0.0,
                        "stroke_width": 0.1,
                        "font_type": "stroke",
                        "font_name": None,
                        "text": "MCU",
                        "is_bold": False,
                        "is_italic": False,
                        "is_mirrored": False,
                        "is_comment": True,
                        "is_designator": False,
                    }
                ],
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
        self.assertEqual(board.components[0].part_name, "MCU")
        self.assertEqual(board.pads[0].net_id, board.nets[0].id)
        self.assertEqual(board.vias[0].template_id, board.via_templates[0].id)
        self.assertEqual(board.primitives[0].kind, "trace")
        self.assertEqual(board.board_outline.kind, "polygon")
        self.assertEqual(
            board.board_outline.values,
            [4, "(0,0)", "(10,0)", "(10,-5)", "(0,-5)", "Y", "Y"],
        )

    def test_altium_adapter_normalizes_outline_points(self) -> None:
        from aurora_translator.semantic.adapters.altium import _vertex_points
        from aurora_translator.sources.altium.models import AltiumVertex

        vertices = [
            AltiumVertex.model_validate(
                {
                    "is_round": False,
                    "radius": 0.0,
                    "start_angle": 0.0,
                    "end_angle": 0.0,
                    "position": {
                        "x_raw": 10000,
                        "y_raw": 20000,
                        "x": 1.0,
                        "y": -2.0,
                    },
                }
            ),
            AltiumVertex.model_validate(
                {
                    "is_round": False,
                    "radius": 0.0,
                    "start_angle": 0.0,
                    "end_angle": 0.0,
                    "position": {
                        "x_raw": 2147483647,
                        "y_raw": 2147483647,
                        "x": 214748.3647,
                        "y": -214748.3647,
                    },
                }
            ),
        ]

        self.assertEqual(_vertex_points(vertices), [[1.0, 2.0]])

    def test_altium_adapter_normalizes_legacy_via_layer_diameters(self) -> None:
        from aurora_translator.semantic.adapters.altium import (
            _via_layer_diameter,
            _via_template_key,
        )
        from aurora_translator.sources.altium.models import AltiumVia

        via = AltiumVia.model_validate(
            {
                "index": 0,
                "net": 0,
                "position": {
                    "x_raw": 10000,
                    "y_raw": 20000,
                    "x": 1.0,
                    "y": 2.0,
                },
                "diameter": 18.0,
                "hole_size": 10.0,
                "start_layer_id": 1,
                "start_layer_name": "TOP",
                "end_layer_id": 32,
                "end_layer_name": "BOTTOM",
                "via_mode": "full",
                "diameter_by_layer": [4608.0, 5120.0, 20.0],
                "is_locked": False,
                "is_tent_top": False,
                "is_tent_bottom": False,
            }
        )

        self.assertEqual(_via_layer_diameter(via, 0, 18.0), 18.0)
        self.assertEqual(_via_layer_diameter(via, 1, 18.0), 20.0)
        self.assertEqual(_via_layer_diameter(via, 2, 18.0), 20.0)
        self.assertEqual(_via_template_key(via)[5], (18.0, 20.0, 20.0))

    def test_altium_region_inherits_polygon_net_and_keeps_voids(self) -> None:
        from aurora_translator.semantic.adapters.altium import _region_primitive
        from aurora_translator.sources.altium.models import AltiumRegion

        def vertex(x_raw: int, y_raw: int) -> dict[str, object]:
            return {
                "is_round": False,
                "radius": 0.0,
                "start_angle": 0.0,
                "end_angle": 0.0,
                "position": {
                    "x_raw": x_raw,
                    "y_raw": y_raw,
                    "x": x_raw / 10000.0,
                    "y": -(y_raw / 10000.0),
                },
                "center": None,
            }

        region = AltiumRegion.model_validate(
            {
                "index": 10,
                "layer_id": 2,
                "layer_name": "L2_GND_1",
                "net": 65535,
                "component": 65535,
                "polygon": 39,
                "subpolygon": 0,
                "kind": "copper",
                "outline": [
                    vertex(0, 0),
                    vertex(10000, 0),
                    vertex(10000, 10000),
                ],
                "holes": [
                    [
                        vertex(2000, 2000),
                        vertex(3000, 2000),
                        vertex(3000, 3000),
                    ]
                ],
                "is_locked": False,
                "is_keepout": False,
                "is_shape_based": False,
                "keepout_restrictions": 0,
            }
        )

        primitive = _region_primitive(
            region,
            0,
            {209: "net:GND", 65535: "net:NoNet"},
            {},
            {39: 209},
        )

        self.assertIsNotNone(primitive)
        assert primitive is not None
        self.assertEqual(primitive.net_id, "net:GND")
        self.assertTrue(primitive.geometry.has_voids)
        self.assertEqual(len(primitive.geometry.voids), 1)
        self.assertEqual(primitive.geometry.raw_points[2], [1.0, 1.0])

    def test_altium_polygon_uses_stackup_layer_name(self) -> None:
        from aurora_translator.semantic.adapters.altium import _polygon_primitive
        from aurora_translator.sources.altium.models import AltiumPolygon

        def vertex(x_raw: int, y_raw: int) -> dict[str, object]:
            return {
                "is_round": False,
                "radius": 0.0,
                "start_angle": 0.0,
                "end_angle": 0.0,
                "position": {
                    "x_raw": x_raw,
                    "y_raw": y_raw,
                    "x": x_raw / 10000.0,
                    "y": -(y_raw / 10000.0),
                },
                "center": None,
            }

        polygon = AltiumPolygon.model_validate(
            {
                "index": 31,
                "layer_id": 5,
                "layer_name": "MID4",
                "net": 12,
                "locked": False,
                "hatch_style": "Solid",
                "use_octagons": False,
                "pour_index": 30,
                "vertices": [vertex(0, 0), vertex(10000, 0), vertex(0, 10000)],
                "properties": {},
            }
        )

        primitive = _polygon_primitive(
            polygon, 0, {12: "net:NVCC_1V8"}, {5: "L5_PWR_1"}
        )

        self.assertIsNotNone(primitive)
        assert primitive is not None
        self.assertEqual(primitive.layer_name, "L5_PWR_1")
        self.assertEqual(primitive.net_id, "net:NVCC_1V8")

    def test_altium_board_outline_preserves_round_corner_arcs(self) -> None:
        from aurora_translator.semantic.adapters.altium import _board_outline_values
        from aurora_translator.sources.altium.models import AltiumVertex

        def vertex(
            x: float,
            y: float,
            *,
            round_: bool = False,
            center: tuple[float, float] | None = None,
        ) -> AltiumVertex:
            payload: dict[str, object] = {
                "is_round": round_,
                "radius": 10.0 if round_ else 0.0,
                "start_angle": 0.0,
                "end_angle": 0.0,
                "position": {
                    "x_raw": int(x * 10000),
                    "y_raw": int(-y * 10000),
                    "x": x,
                    "y": -y,
                },
                "center": None,
            }
            if center is not None:
                cx, cy = center
                payload["center"] = {
                    "x_raw": int(cx * 10000),
                    "y_raw": int(-cy * 10000),
                    "x": cx,
                    "y": -cy,
                }
            return AltiumVertex.model_validate(payload)

        values = _board_outline_values(
            [
                vertex(0.0, 10.0),
                vertex(0.0, 90.0, round_=True, center=(10.0, 90.0)),
                vertex(10.0, 100.0),
                vertex(90.0, 100.0, round_=True, center=(90.0, 90.0)),
                vertex(100.0, 90.0),
                vertex(100.0, 10.0, round_=True, center=(90.0, 10.0)),
                vertex(90.0, 0.0),
                vertex(10.0, 0.0, round_=True, center=(10.0, 10.0)),
                vertex(0.0, 10.0),
            ]
        )

        self.assertEqual(
            values,
            [
                "(0,10)",
                [10.0, 0.0, 10.0, 10.0, "Y"],
                "(90,0)",
                [100.0, 10.0, 90.0, 10.0, "Y"],
                "(100,90)",
                [90.0, 100.0, 90.0, 90.0, "Y"],
                "(10,100)",
                [0.0, 90.0, 10.0, 90.0, "Y"],
                "(0,10)",
            ],
        )

    def test_altium_polygon_path_interleaves_round_vertices(self) -> None:
        from aurora_translator.semantic.adapters.altium import _vertex_path_values
        from aurora_translator.sources.altium.models import AltiumVertex

        def vertex(
            x: float,
            y: float,
            *,
            round_: bool = False,
            center: tuple[float, float] | None = None,
            start_angle: float = 0.0,
            end_angle: float = 0.0,
        ) -> AltiumVertex:
            payload: dict[str, object] = {
                "is_round": round_,
                "radius": 10.0 if round_ else 0.0,
                "start_angle": start_angle,
                "end_angle": end_angle,
                "position": {
                    "x_raw": int(x * 10000),
                    "y_raw": int(-y * 10000),
                    "x": x,
                    "y": -y,
                },
                "center": None,
            }
            if center is not None:
                cx, cy = center
                payload["center"] = {
                    "x_raw": int(cx * 10000),
                    "y_raw": int(-cy * 10000),
                    "x": cx,
                    "y": -cy,
                }
            return AltiumVertex.model_validate(payload)

        values = _vertex_path_values(
            [
                vertex(
                    10.0,
                    0.0,
                    round_=True,
                    center=(10.0, 10.0),
                    start_angle=180.0,
                    end_angle=270.0,
                ),
                vertex(0.0, 10.0),
                vertex(0.0, 20.0),
            ]
        )

        self.assertEqual(values, [[10.0, 0.0], [0.0, 10.0, 10.0, 10.0, 0], [0.0, 20.0]])

    def test_altium_adapter_uses_board_stackup_chain_for_copper_layers(self) -> None:
        from aurora_translator.semantic.adapters.altium import from_altium
        from aurora_translator.sources.altium.models import AltiumLayout

        def layer(
            layer_id: int,
            name: str,
            *,
            next_id: int | None = None,
            prev_id: int | None = None,
        ) -> dict[str, object]:
            return {
                "layer_id": layer_id,
                "name": name,
                "next_id": next_id,
                "prev_id": prev_id,
                "copper_thickness": 1.4,
                "dielectric_constant": None,
                "dielectric_thickness": None,
                "dielectric_material": None,
                "mechanical_enabled": False,
                "mechanical_kind": None,
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
                    "stream_count": 1,
                    "parsed_stream_count": 1,
                    "layer_count": 6,
                    "net_count": 0,
                    "class_count": 0,
                    "rule_count": 0,
                    "polygon_count": 0,
                    "component_count": 0,
                    "pad_count": 0,
                    "via_count": 0,
                    "track_count": 0,
                    "arc_count": 0,
                    "fill_count": 0,
                    "region_count": 0,
                    "text_count": 0,
                    "board_outline_vertex_count": 0,
                    "diagnostic_count": 0,
                    "units": "mil",
                    "format": "altium-pcbdoc",
                },
                "board": {"layer_count_declared": 5, "outline": [], "properties": {}},
                "layers": [
                    layer(1, "Top", next_id=39),
                    layer(2, "Inner1", next_id=40, prev_id=39),
                    layer(3, "UnusedMid"),
                    layer(32, "Bottom", prev_id=40),
                    layer(39, "GND02", next_id=2, prev_id=1),
                    layer(40, "PWR05", next_id=32, prev_id=2),
                ],
                "stream_counts": {},
                "diagnostics": [],
            }
        )

        board = from_altium(payload)

        self.assertEqual(
            [layer.name for layer in board.layers],
            ["Top", "GND02", "Inner1", "PWR05", "Bottom"],
        )
        self.assertEqual(
            [layer.role for layer in board.layers],
            ["signal", "plane", "signal", "plane", "signal"],
        )


if __name__ == "__main__":
    unittest.main()
