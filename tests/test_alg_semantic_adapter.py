from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = PROJECT_ROOT.parent

if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))


def _minimal_alg_payload(
    *,
    pin_layer: str,
    padstack_start: str | None = None,
    padstack_end: str | None = None,
    shape_kind: str = "FIG_RECTANGLE",
) -> dict:
    padstack_start = padstack_start or pin_layer
    padstack_end = padstack_end or pin_layer
    return {
        "metadata": {
            "project_version": "1.0.44",
            "parser_version": "0.1.1",
            "output_schema_version": "0.2.0",
            "source": "sample.alg",
            "source_type": "file",
            "backend": "rust-cli",
            "rust_parser_version": "0.1.1",
        },
        "summary": {
            "line_count": 1,
            "section_count": 1,
            "data_record_count": 1,
            "board_record_count": 1,
            "layer_count": 5,
            "metal_layer_count": 3,
            "component_count": 1,
            "pin_count": 1,
            "padstack_count": 1,
            "pad_count": 1,
            "via_count": 0,
            "track_count": 0,
            "net_count": 1,
            "symbol_count": 1,
            "outline_count": 0,
            "diagnostic_count": 0,
            "units": "mm",
        },
        "board": {
            "name": "sample",
            "units": "mm",
            "extents": {"x1": 0.0, "y1": 0.0, "x2": 10.0, "y2": 10.0},
        },
        "layers": [
            {"name": "TOP", "conductor": True, "layer_type": "CONDUCTOR"},
            {"name": "D1", "conductor": False, "layer_type": "DIELECTRIC"},
            {"name": "L2", "conductor": True, "layer_type": "CONDUCTOR"},
            {"name": "D2", "conductor": False, "layer_type": "DIELECTRIC"},
            {"name": "BOTTOM", "conductor": True, "layer_type": "CONDUCTOR"},
        ],
        "components": [
            {
                "refdes": "U1",
                "class_name": "IC",
                "package": "PKG",
                "device_type": "PART",
            }
        ],
        "pins": [
            {
                "refdes": "U1",
                "pin_number": "1",
                "x": 1.0,
                "y": 2.0,
                "pad_stack_name": "PAD1",
                "net_name": "GND",
            }
        ],
        "padstacks": [
            {
                "name": "PAD1",
                "pad_stack_type": "SINGLE",
                "start_layer": padstack_start,
                "end_layer": padstack_end,
            }
        ],
        "pads": [
            {
                "refdes": "U1",
                "pin_number": "1",
                "layer_name": pin_layer,
                "pad_stack_name": "PAD1",
                "net_name": "GND",
                "x": 1.0,
                "y": 2.0,
                "pad_type": "REGULAR",
                "shape": {
                    "kind": shape_kind,
                    "x": 1.0,
                    "y": 2.0,
                    "width": 0.2,
                    "height": 0.3,
                },
                "source_section": "full_geometry",
            }
        ],
        "symbols": [
            {
                "sym_type": "PACKAGE",
                "sym_name": "PKG",
                "refdes": "U1",
                "mirror": False,
                "rotation": 0.0,
                "location": {"x": 1.0, "y": 2.0},
            }
        ],
        "section_counts": {},
        "diagnostics": [],
    }


def _line_contour_pad_payload() -> dict:
    payload = _minimal_alg_payload(pin_layer="L9")
    payload["layers"] = [
        {"name": "TOP", "conductor": True, "layer_type": "CONDUCTOR"},
        {"name": "L9", "conductor": True, "layer_type": "CONDUCTOR"},
        {"name": "BOTTOM", "conductor": True, "layer_type": "CONDUCTOR"},
    ]
    payload["summary"]["layer_count"] = 3
    payload["summary"]["metal_layer_count"] = 3
    payload["summary"]["component_count"] = 2
    payload["summary"]["pin_count"] = 2
    payload["summary"]["pad_count"] = 5
    payload["components"] = [
        {
            "refdes": "SH801",
            "class_name": "IC",
            "package": "PAD_DIFFERENT_L1",
            "device_type": "PAD_DIFFERENT_L1_PAD_DIFFERENT_",
        },
        {
            "refdes": "SH701",
            "class_name": "IC",
            "package": "PAD_DIFFERENT_L1",
            "device_type": "PAD_DIFFERENT_L1_PAD_DIFFERENT_",
        },
    ]
    payload["pins"] = [
        {
            "refdes": "SH801",
            "pin_number": "1",
            "x": 73.3213,
            "y": 17.9278,
            "pad_stack_name": "R0D15_NSP",
            "net_name": "GND",
        },
        {
            "refdes": "SH701",
            "pin_number": "1",
            "x": 71.2417,
            "y": 19.2409,
            "pad_stack_name": "R0D15_NSP",
            "net_name": "GND",
        },
    ]
    payload["padstacks"] = [
        {
            "name": "R0D15_NSP",
            "pad_stack_type": "SINGLE",
            "start_layer": "L9",
            "end_layer": "L9",
        }
    ]
    payload["pads"] = [
        {
            "refdes": "SH801",
            "pin_number": "1",
            "layer_name": "L9",
            "pad_stack_name": "R0D15_NSP",
            "net_name": "GND",
            "x": 73.3213,
            "y": 17.9278,
            "pad_type": "REGULAR",
            "shape": {
                "kind": "LINE",
                "x": 73.2152,
                "y": 17.9278,
                "width": 73.3213,
                "height": 17.8217,
                "rotation": 0.0,
            },
            "source_section": "full_geometry",
            "record_tag": "13155 1 0",
        },
        {
            "refdes": "SH801",
            "pin_number": "1",
            "layer_name": "L9",
            "pad_stack_name": "R0D15_NSP",
            "net_name": "GND",
            "x": 73.3213,
            "y": 17.9278,
            "pad_type": "REGULAR",
            "shape": {
                "kind": "LINE",
                "x": 73.3213,
                "y": 17.8217,
                "width": 73.4274,
                "height": 17.9278,
                "rotation": 0.0,
            },
            "source_section": "full_geometry",
            "record_tag": "13155 2 0",
        },
        {
            "refdes": "SH801",
            "pin_number": "1",
            "layer_name": "L9",
            "pad_stack_name": "R0D15_NSP",
            "net_name": "GND",
            "x": 73.3213,
            "y": 17.9278,
            "pad_type": "REGULAR",
            "shape": {
                "kind": "LINE",
                "x": 73.4274,
                "y": 17.9278,
                "width": 73.3213,
                "height": 18.0339,
                "rotation": 0.0,
            },
            "source_section": "full_geometry",
            "record_tag": "13155 3 0",
        },
        {
            "refdes": "SH801",
            "pin_number": "1",
            "layer_name": "L9",
            "pad_stack_name": "R0D15_NSP",
            "net_name": "GND",
            "x": 73.3213,
            "y": 17.9278,
            "pad_type": "REGULAR",
            "shape": {
                "kind": "LINE",
                "x": 73.3213,
                "y": 18.0339,
                "width": 73.2152,
                "height": 17.9278,
                "rotation": 0.0,
            },
            "source_section": "full_geometry",
            "record_tag": "13155 4 0",
        },
        {
            "refdes": "SH701",
            "pin_number": "1",
            "layer_name": "L9",
            "pad_stack_name": "R0D15_NSP",
            "net_name": "GND",
            "x": 71.2417,
            "y": 19.2409,
            "pad_type": "REGULAR",
            "shape": {
                "kind": "SQUARE",
                "x": 71.2417,
                "y": 19.2409,
                "width": 0.15,
                "height": 0.15,
            },
            "source_section": "full_geometry",
            "record_tag": "6703 1",
        },
    ]
    payload["symbols"] = [
        {
            "sym_type": "PACKAGE",
            "sym_name": "PAD_DIFFERENT_L1",
            "refdes": "SH801",
            "mirror": False,
            "rotation": 135.0,
            "location": {"x": 73.3651, "y": 17.8840},
        },
        {
            "sym_type": "PACKAGE",
            "sym_name": "PAD_DIFFERENT_L1",
            "refdes": "SH701",
            "mirror": False,
            "rotation": 180.0,
            "location": {"x": 71.3037, "y": 19.2409},
        },
    ]
    return payload


class ALGSemanticAdapterTests(unittest.TestCase):
    def test_component_layer_uses_single_layer_pin_pad(self) -> None:
        from aurora_translator.semantic.adapters.alg import from_alg
        from aurora_translator.sources.alg.models import ALGLayout

        board = from_alg(
            ALGLayout.model_validate(_minimal_alg_payload(pin_layer="L2")),
            build_connectivity=False,
        )

        self.assertEqual(board.components[0].layer_name, "L2")
        self.assertEqual(board.components[0].side, "internal")
        self.assertEqual(board.pins[0].layer_name, "L2")
        self.assertEqual(board.pads[0].layer_name, "L2")

    def test_through_pin_keeps_initial_side_layer(self) -> None:
        from aurora_translator.semantic.adapters.alg import from_alg
        from aurora_translator.sources.alg.models import ALGLayout

        board = from_alg(
            ALGLayout.model_validate(
                _minimal_alg_payload(
                    pin_layer="TOP",
                    padstack_start="TOP",
                    padstack_end="BOTTOM",
                )
            ),
            build_connectivity=False,
        )

        self.assertEqual(board.components[0].layer_name, "TOP")
        self.assertEqual(board.components[0].side, "top")

    def test_oblong_pad_shape_maps_to_rounded_rectangle(self) -> None:
        from aurora_translator.semantic.adapters.alg import from_alg
        from aurora_translator.sources.alg.models import ALGLayout

        board = from_alg(
            ALGLayout.model_validate(
                _minimal_alg_payload(pin_layer="TOP", shape_kind="OBLONG_X")
            ),
            build_connectivity=False,
        )

        pad_shape = next(
            shape
            for shape in board.shapes
            if shape.id == board.pads[0].geometry.shape_id
        )
        self.assertEqual(pad_shape.kind, "rounded_rectangle")
        self.assertEqual(pad_shape.auroradb_type, "RoundedRectangle")

    def test_line_contour_pad_uses_padstack_simple_shape(self) -> None:
        from aurora_translator.semantic.adapters.alg import from_alg
        from aurora_translator.sources.alg.models import ALGLayout

        board = from_alg(
            ALGLayout.model_validate(_line_contour_pad_payload()),
            build_connectivity=False,
        )

        sh801_component = next(
            component for component in board.components if component.refdes == "SH801"
        )
        sh801_pads = [
            pad for pad in board.pads if pad.component_id == sh801_component.id
        ]
        self.assertEqual(len(sh801_pads), 1)

        pad_shape = next(
            shape
            for shape in board.shapes
            if shape.id == sh801_pads[0].geometry.shape_id
        )
        self.assertEqual(pad_shape.auroradb_type, "Rectangle")
        self.assertEqual(pad_shape.values, [0.0, 0.0, 0.15, 0.15])
        self.assertEqual(
            sh801_pads[0].geometry.source, "alg_full_geometry_padstack_shape"
        )
        self.assertEqual(sh801_pads[0].geometry.get("footprint_rotation"), 0.0)

    def test_footprint_pad_score_prefers_exact_component_layer(self) -> None:
        from aurora_translator.semantic.models import (
            SemanticComponent,
            SemanticPad,
            SemanticPadGeometry,
        )
        from aurora_translator.targets.auroradb.parts import (
            _component_footprint_pad_score,
        )

        component = SemanticComponent(
            id="component:u1",
            refdes="U1",
            layer_name="L2",
            side="internal",
            source={"source_format": "alg", "path": "components"},
        )
        top_pad = SemanticPad(
            id="pad:u1:1:top",
            layer_name="TOP",
            geometry=SemanticPadGeometry(source="alg_full_geometry_pad"),
            source={"source_format": "alg", "path": "pads"},
        )
        l2_pad = SemanticPad(
            id="pad:u1:1:l2",
            layer_name="L2",
            geometry=SemanticPadGeometry(source="alg_full_geometry_pad"),
            source={"source_format": "alg", "path": "pads"},
        )

        layer_sides = {"top": "top", "l2": "internal"}

        self.assertGreater(
            _component_footprint_pad_score(component, l2_pad, layer_sides),
            _component_footprint_pad_score(component, top_pad, layer_sides),
        )


if __name__ == "__main__":
    unittest.main()
