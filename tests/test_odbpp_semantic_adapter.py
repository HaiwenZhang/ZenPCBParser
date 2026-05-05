from __future__ import annotations

import sys
import unittest
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = PROJECT_ROOT.parent

if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))


def _minimal_odbpp_payload() -> dict:
    def component(refdes: str, layer_name: str, component_index: int) -> dict:
        return {
            "step_name": "pcb",
            "layer_name": layer_name,
            "line_number": 1 + component_index,
            "record_type": "CMP",
            "component_index": component_index,
            "refdes": refdes,
            "location": {"x": 0.0, "y": 0.0},
            "rotation": 0.0,
            "pins": [
                {
                    "line_number": 10 + component_index,
                    "record_type": "TOP",
                    "pin_index": 0,
                    "name": "1",
                    "position": {"x": float(component_index), "y": 1.0},
                }
            ],
        }

    return {
        "metadata": {
            "project_version": "1.0.44",
            "parser_version": "0.6.3",
            "output_schema_version": "0.6.0",
            "source": "sample.tgz",
            "source_type": "tgz",
            "selected_step": "pcb",
            "backend": "rust-cli",
            "rust_parser_version": "0.6.3",
        },
        "summary": {
            "step_count": 1,
            "layer_count": 7,
            "board_layer_count": 7,
            "signal_layer_count": 2,
            "component_layer_count": 2,
            "feature_layer_count": 0,
            "feature_count": 0,
            "symbol_count": 0,
            "drill_tool_count": 0,
            "package_count": 0,
            "component_count": 2,
            "net_count": 0,
            "profile_record_count": 0,
            "diagnostic_count": 0,
            "step_names": ["pcb"],
            "layer_names": [
                "comp_+_top",
                "signal_1",
                "dielectric_1",
                "l2_plane",
                "dielectric_2",
                "signal_2",
                "comp_+_bot",
            ],
            "net_names": [],
        },
        "matrix": {
            "rows": [
                {
                    "row": 1,
                    "name": "comp_+_top",
                    "context": "BOARD",
                    "layer_type": "COMPONENT",
                },
                {
                    "row": 2,
                    "name": "signal_1",
                    "context": "BOARD",
                    "layer_type": "SIGNAL",
                },
                {
                    "row": 3,
                    "name": "dielectric_1",
                    "context": "BOARD",
                    "layer_type": "DIELECTRIC",
                },
                {
                    "row": 4,
                    "name": "l2_plane",
                    "context": "BOARD",
                    "layer_type": "POWER_GROUND",
                },
                {
                    "row": 5,
                    "name": "dielectric_2",
                    "context": "BOARD",
                    "layer_type": "DIELECTRIC",
                },
                {
                    "row": 6,
                    "name": "signal_2",
                    "context": "BOARD",
                    "layer_type": "SIGNAL",
                },
                {
                    "row": 7,
                    "name": "comp_+_bot",
                    "context": "BOARD",
                    "layer_type": "COMPONENT",
                },
            ]
        },
        "steps": [{"name": "pcb", "profile": {"units": "MM", "records": []}}],
        "symbols": [],
        "drill_tools": [],
        "packages": [],
        "layers": [],
        "components": [
            component("JTOP", "comp_+_top", 0),
            component("JBOT", "comp_+_bot", 1),
        ],
        "nets": [],
        "diagnostics": [],
    }


def _minimal_odbpp_payload_with_xpedition_drill_layer() -> dict:
    payload = _minimal_odbpp_payload()
    payload["matrix"]["rows"].append(
        {
            "row": 8,
            "name": "d_1_2",
            "context": "BOARD",
            "layer_type": "DRILL",
            "start_name": "signal_1",
            "end_name": "signal_2",
        }
    )
    payload["layers"] = [
        {
            "step_name": "pcb",
            "layer_name": "d_1_2",
            "units": "MM",
            "symbols": {"1": "r0.2"},
            "features": [
                {
                    "feature_index": 0,
                    "kind": "P",
                    "line_number": 1,
                    "tokens": ["P", "1.0", "2.0", "1"],
                    "symbol": "1",
                    "start": {"x": 1.0, "y": 2.0},
                    "polarity": "P",
                }
            ],
        }
    ]
    payload["nets"] = [
        {
            "step_name": "pcb",
            "name": "VIA_NET",
            "source_file": "netlists/cadnet/netlist",
            "line_number": 1,
            "feature_refs": [
                {
                    "line_number": 2,
                    "class_code": "H",
                    "layer_name": "d_1_2",
                    "feature_index": 0,
                }
            ],
        }
    ]
    return payload


class ODBPPSemanticAdapterTests(unittest.TestCase):
    def test_component_pin_fallback_layers_use_outer_metal_layers(self) -> None:
        from aurora_translator.semantic.adapters.odbpp import from_odbpp
        from aurora_translator.sources.odbpp.models import ODBLayout

        board = from_odbpp(ODBLayout.model_validate(_minimal_odbpp_payload()))

        pins_by_id = {pin.id: pin for pin in board.pins}
        self.assertEqual(pins_by_id["pin:JTOP:1"].layer_name, "signal_1")
        self.assertEqual(pins_by_id["pin:JBOT:1"].layer_name, "signal_2")
        self.assertNotIn(
            "semantic.pin_layer_missing_ref",
            {diagnostic.code for diagnostic in board.diagnostics},
        )

    def test_package_pad_fallback_layers_use_outer_metal_layers(self) -> None:
        from aurora_translator.semantic.adapters.odbpp import from_odbpp
        from aurora_translator.sources.odbpp.models import ODBLayout

        payload = _minimal_odbpp_payload()
        payload["packages"] = [
            {
                "step_name": "pcb",
                "line_number": 1,
                "package_index": 1,
                "name": "PKG",
                "pins": [
                    {
                        "line_number": 2,
                        "name": "1",
                        "position": {"x": 0.0, "y": 0.0},
                        "shapes": [
                            {
                                "line_number": 3,
                                "kind": "SQ",
                                "center": {"x": 0.0, "y": 0.0},
                                "size": 0.1,
                            }
                        ],
                    }
                ],
            }
        ]
        payload["components"][1]["package_index"] = 1
        payload["components"][1]["package_name"] = "PKG"

        board = from_odbpp(ODBLayout.model_validate(payload))

        pads_by_component_id = {}
        for pad in board.pads:
            pads_by_component_id.setdefault(pad.component_id, []).append(pad)
        bottom_component = next(
            component for component in board.components if component.refdes == "JBOT"
        )
        self.assertEqual(
            [pad.layer_name for pad in pads_by_component_id[bottom_component.id]],
            ["signal_2"],
        )
        self.assertNotIn(
            "semantic.pad_layer_missing_ref",
            {diagnostic.code for diagnostic in board.diagnostics},
        )

    def test_package_names_and_unit_part_names_are_canonicalized(self) -> None:
        from aurora_translator.semantic.adapters.odbpp import (
            _normalize_odbpp_part_name,
            from_odbpp,
        )
        from aurora_translator.sources.odbpp.models import ODBLayout

        payload = _minimal_odbpp_payload()
        payload["packages"] = [
            {
                "step_name": "pcb",
                "line_number": 1,
                "package_index": 1,
                "name": "0402_CC",
                "pins": [
                    {
                        "line_number": 3,
                        "name": "1",
                        "position": {"x": 0.0, "y": 0.0},
                    }
                ],
            },
            {
                "step_name": "pcb",
                "line_number": 2,
                "package_index": 2,
                "name": "0402_CC_1_2",
                "pins": [
                    {
                        "line_number": 4,
                        "name": "1",
                        "position": {"x": 0.0, "y": 0.0},
                    }
                ],
            },
        ]
        payload["components"][0]["package_index"] = 2
        payload["components"][0]["part_name"] = "CAP_NP_0402_CC_DISCRETE_0.65_MM"
        payload["components"][0]["pins"][0]["name"] = "JTOP-1"

        board = from_odbpp(ODBLayout.model_validate(payload))

        component = next(item for item in board.components if item.refdes == "JTOP")
        pin = next(item for item in board.pins if item.component_id == component.id)
        self.assertEqual(component.package_name, "0402_CC")
        self.assertEqual(component.footprint_id, "footprint:0402_CC")
        self.assertEqual(component.part_name, "CAP_NP_0402_CC_DISCRETE_0.65 MM")
        self.assertEqual(pin.name, "1")
        self.assertEqual(
            [footprint.name for footprint in board.footprints], ["0402_CC"]
        )
        self.assertEqual(
            _normalize_odbpp_part_name("HDR_2X50_M_CON100_0P4_21P7X2P05"),
            "HDR_2X50_M_CON100_0P4_21P7X2P05",
        )
        self.assertEqual(
            _normalize_odbpp_part_name("T_POINT_R_TESTPOINT_35MIL_IC_0."),
            "T POINT R_TESTPOINT_35MIL_IC_0.",
        )

    def test_xpedition_drill_matrix_rows_emit_vias(self) -> None:
        from aurora_translator.semantic.adapters.odbpp import from_odbpp
        from aurora_translator.sources.odbpp.models import ODBLayout

        board = from_odbpp(
            ODBLayout.model_validate(
                _minimal_odbpp_payload_with_xpedition_drill_layer()
            )
        )

        self.assertEqual(len(board.vias), 1)
        self.assertEqual(board.vias[0].layer_names, ["signal_1", "signal_2"])
        self.assertEqual(len(board.via_templates), 1)
        self.assertEqual(
            [layer.layer_name for layer in board.via_templates[0].layer_pads],
            ["signal_1", "signal_2"],
        )
        self.assertEqual(
            {layer.name: layer.role for layer in board.layers}["d_1_2"],
            "drill",
        )

    def test_xpedition_no_net_drill_rows_emit_no_net_vias(self) -> None:
        from aurora_translator.semantic.adapters.odbpp import from_odbpp
        from aurora_translator.sources.odbpp.models import ODBLayout

        payload = _minimal_odbpp_payload_with_xpedition_drill_layer()
        payload["nets"] = []

        board = from_odbpp(ODBLayout.model_validate(payload))

        nets_by_id = {net.id: net for net in board.nets}
        self.assertEqual(len(board.vias), 1)
        self.assertEqual(
            nets_by_id[board.vias[0].net_id].name,
            "NoNet",
        )
        self.assertEqual(nets_by_id[board.vias[0].net_id].role, "no_net")

    def test_xpedition_none_id_nets_collapse_to_no_net(self) -> None:
        from aurora_translator.semantic.adapters.odbpp import from_odbpp
        from aurora_translator.sources.odbpp.models import ODBLayout

        payload = _minimal_odbpp_payload()
        payload["nets"] = [
            {
                "step_name": "pcb",
                "name": "$NONE$;;ID=184240",
                "source_file": "netlists/cadnet/netlist",
                "line_number": 1,
            }
        ]

        board = from_odbpp(ODBLayout.model_validate(payload))

        self.assertEqual(
            [(net.name, net.role) for net in board.nets], [("NoNet", "no_net")]
        )

    def test_xpedition_refloc_offsets_component_location(self) -> None:
        from aurora_translator.semantic.adapters.odbpp import from_odbpp
        from aurora_translator.sources.odbpp.models import ODBLayout

        payload = _minimal_odbpp_payload()
        payload["components"][0]["location"] = {"x": 10.0, "y": 20.0}
        payload["components"][0]["properties"] = {
            "REFLOC": "MM,0.180000,-0.050000,0,CC,0.250000,0.250000,0.050000,vf_std"
        }

        board = from_odbpp(ODBLayout.model_validate(payload))

        component = {component.refdes: component for component in board.components}[
            "JTOP"
        ]
        self.assertAlmostEqual(component.location.x, 10.18)
        self.assertAlmostEqual(component.location.y, 19.95)

    def test_via_template_pad_matching_prefers_non_component_land(self) -> None:
        from aurora_translator.semantic.adapters.odbpp import _candidate_pad_match
        from aurora_translator.semantic.models import (
            SemanticPad,
            SemanticPoint,
            SemanticShape,
        )

        component_pad = SemanticPad.model_construct(
            id="pad:component",
            component_id="component:C1",
            position=SemanticPoint.model_construct(x=1.0, y=2.0),
            geometry={"shape_id": "shape:component"},
        )
        via_land = SemanticPad.model_construct(
            id="pad:via_land",
            position=SemanticPoint.model_construct(x=1.0, y=2.0),
            geometry={"shape_id": "shape:via_land"},
        )
        shapes = {
            "shape:component": SemanticShape.model_construct(
                id="shape:component", auroradb_type="Rectangle"
            ),
            "shape:via_land": SemanticShape.model_construct(
                id="shape:via_land", auroradb_type="Circle"
            ),
        }

        match = _candidate_pad_match(
            [(component_pad, 0.0), (via_land, 0.0)], None, shapes
        )

        self.assertEqual(match["shape_id"], "shape:via_land")

    def test_via_template_pad_matching_ignores_circle_rotation(self) -> None:
        from aurora_translator.semantic.adapters.odbpp import _matched_pad_rotation
        from aurora_translator.semantic.models import SemanticShape

        rotation = _matched_pad_rotation(
            math.radians(90),
            None,
            SemanticShape.model_construct(
                id="shape:circle", auroradb_type="Circle", values=[0, 0, 0.18]
            ),
        )

        self.assertIsNone(rotation)


if __name__ == "__main__":
    unittest.main()
