from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = PROJECT_ROOT.parent

if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))


class AuroraDBComponentExportTests(unittest.TestCase):
    def test_odbpp_bottom_component_uses_auroradb_bottom_orientation(self) -> None:
        from aurora_translator.semantic.models import SemanticComponent, SemanticPoint
        from aurora_translator.targets.auroradb.geometry import _component_command

        component = SemanticComponent.model_construct(
            id="component:C1",
            refdes="C1",
            part_name="CAP",
            layer_name="signal_10",
            side="bottom",
            location=SemanticPoint.model_construct(x=1.0, y=2.0),
            rotation=math.radians(90.0),
        )

        command = _component_command(
            component,
            {"signal_10": "signal_10"},
            source_unit=None,
            source_format="odbpp",
        )

        self.assertIsNotNone(command)
        self.assertIn("-location <(1,2)>", command)
        self.assertIn("-rotation <-90>", command)
        self.assertIn("-flipY", command)
        self.assertNotIn("-flipX", command)

    def test_aedb_bottom_component_uses_auroradb_bottom_flip(self) -> None:
        from aurora_translator.semantic.models import SemanticComponent, SemanticPoint
        from aurora_translator.targets.auroradb.geometry import _component_command

        component = SemanticComponent.model_construct(
            id="component:C1",
            refdes="C1",
            part_name="CAP",
            layer_name="BOTTOM",
            side="bottom",
            location=SemanticPoint.model_construct(x=1.0, y=2.0),
            rotation=math.radians(270.0),
        )

        command = _component_command(
            component,
            {"bottom": "BOTTOM"},
            source_unit=None,
            source_format="aedb",
        )

        self.assertIsNotNone(command)
        self.assertIn("-rotation <90>", command)
        self.assertIn("-flipY", command)
        self.assertNotIn("-flipX", command)

    def test_odbpp_layout_preserves_mm_semantic_coordinates(self) -> None:
        from aurora_translator.semantic.models import SemanticBoard, SemanticMetadata
        from aurora_translator.targets.auroradb.layout import (
            _geometry_source_unit,
            _layout_unit,
        )

        board = SemanticBoard.model_construct(
            metadata=SemanticMetadata.model_construct(source_format="odbpp"),
            units="mm",
        )

        self.assertEqual(_layout_unit(board), "mm")
        self.assertIsNone(_geometry_source_unit(board))

    def test_aedb_layout_preserves_meter_semantic_coordinates(self) -> None:
        from aurora_translator.semantic.models import SemanticBoard, SemanticMetadata
        from aurora_translator.targets.auroradb.layout import (
            _geometry_source_unit,
            _layout_unit,
        )

        board = SemanticBoard.model_construct(
            metadata=SemanticMetadata.model_construct(source_format="aedb"),
            units="m",
        )

        self.assertEqual(_layout_unit(board), "m")
        self.assertIsNone(_geometry_source_unit(board))

    def test_aedb_def_binary_layout_exports_mils_from_meter_semantics(self) -> None:
        from aurora_translator.semantic.models import SemanticBoard, SemanticMetadata
        from aurora_translator.targets.auroradb.layout import (
            _geometry_source_unit,
            _layout_unit,
        )

        board = SemanticBoard.model_construct(
            metadata=SemanticMetadata.model_construct(
                source_format="aedb",
                source_step="def-binary",
            ),
            units="m",
        )

        self.assertEqual(_layout_unit(board), "mils")
        self.assertEqual(_geometry_source_unit(board), "m")

    def test_stackup_preserves_mm_source_unit(self) -> None:
        from aurora_translator.semantic.models import SemanticBoard, SemanticLayer
        from aurora_translator.targets.auroradb.stackup import (
            _export_layers,
            _stackup_dat,
            _stackup_json,
            _with_generated_dielectrics,
        )

        board = SemanticBoard.model_construct(
            units="mm",
            layers=[
                SemanticLayer.model_construct(
                    id="layer:top",
                    name="TOP",
                    role="signal",
                    thickness="0.035 mm",
                    order_index=0,
                )
            ],
        )

        layers = _with_generated_dielectrics(_export_layers(board))
        text = _stackup_dat(layers)
        payload = _stackup_json(layers)

        self.assertIn("Unit mm", text)
        self.assertIn("Metal TOP 0.035", text)
        self.assertEqual(payload["unit"], "mm")
        self.assertTrue(all(layer.unit == "mm" for layer in layers))

    def test_direct_outline_flattens_list_vertices(self) -> None:
        from aurora_translator.semantic.models import (
            SemanticBoard,
            SemanticBoardOutlineGeometry,
            SemanticMetadata,
        )
        from aurora_translator.sources.auroradb.block import format_block
        from aurora_translator.targets.auroradb.layout import _direct_outline_node

        board = SemanticBoard.model_construct(
            metadata=SemanticMetadata.model_construct(source_format="altium"),
            units="mil",
            board_outline=SemanticBoardOutlineGeometry.model_construct(
                kind="polygon",
                auroradb_type="Polygon",
                values=[
                    4,
                    [0.0, 0.0],
                    [10.0, 0.0],
                    [10.0, -5.0],
                    [0.0, -5.0],
                    "Y",
                    "Y",
                ],
            ),
        )

        outline = _direct_outline_node(board)
        text = format_block(outline)

        self.assertEqual(
            [item.values for item in outline.get_items("Pnt")],
            [["0", "0"], ["10", "0"], ["10", "-5"], ["0", "-5"]],
        )
        self.assertIn("Pnt 10 -5", text)
        self.assertNotIn("[", text)

    def test_polygon_parts_are_oriented_for_auroradb_ccw_flag(self) -> None:
        from aurora_translator.targets.auroradb.geometry import _polygon_vertex_parts

        parts = _polygon_vertex_parts(
            {
                "raw_points": [
                    [0.0, 0.0],
                    [1.0, 0.0],
                    [1.0, 1.0],
                    [0.0, 1.0],
                    [0.0, 0.0],
                ]
            },
            source_unit=None,
        )

        self.assertEqual(
            parts,
            [["0", "0"], ["0", "1"], ["1", "1"], ["1", "0"]],
        )

    def test_suppressed_pad_shape_does_not_emit_location_geometry(self) -> None:
        from aurora_translator.semantic.models import (
            SemanticPad,
            SemanticPadGeometry,
            SemanticPoint,
        )
        from aurora_translator.targets.auroradb.geometry import _pad_shape_command

        pad = SemanticPad.model_construct(
            id="pad:1",
            net_id="net:GND",
            layer_name="TOP",
            position=SemanticPoint.model_construct(x=1.0, y=2.0),
            geometry=SemanticPadGeometry.model_construct(
                shape_id="shape:1",
                suppress_shape_export=True,
            ),
        )

        command = _pad_shape_command(
            pad,
            {},
            {"net:GND": "GND"},
            {"shape:1": "1"},
            {},
            {"top": "TOP"},
            source_unit=None,
        )

        self.assertIsNone(command)

    def test_aedb_component_pin_padstack_records_do_not_export_as_net_vias(
        self,
    ) -> None:
        from aurora_translator.semantic.models import (
            SemanticBoard,
            SemanticPoint,
            SemanticVia,
            SemanticViaGeometry,
            SemanticViaTemplate,
            SemanticViaTemplateLayer,
            SourceRef,
        )
        from aurora_translator.targets.auroradb.geometry import (
            _semantic_via_can_emit_as_net_via,
            _via_templates_for_export,
        )

        source = SourceRef.model_construct(source_format="aedb")
        via_template = SemanticViaTemplate.model_construct(
            id="via_template:pad",
            name="PAD",
            layer_pads=[
                SemanticViaTemplateLayer.model_construct(
                    layer_name="TOP", pad_shape_id="shape:pad"
                )
            ],
            source=source,
        )
        component_pin = SemanticVia.model_construct(
            id="via:component_pin",
            template_id=via_template.id,
            net_id="net:gnd",
            position=SemanticPoint.model_construct(x=1.0, y=2.0),
            geometry=SemanticViaGeometry(via_usage="component_pin"),
            source=source,
        )
        through_component_pin = SemanticVia.model_construct(
            id="via:through_component_pin",
            template_id=via_template.id,
            net_id="net:gnd",
            position=SemanticPoint.model_construct(x=1.0, y=2.0),
            geometry=SemanticViaGeometry(via_usage="component_pin", via_type="through"),
            source=source,
        )
        routing_via = SemanticVia.model_construct(
            id="via:routing",
            template_id=via_template.id,
            net_id="net:gnd",
            position=SemanticPoint.model_construct(x=1.0, y=2.0),
            geometry=SemanticViaGeometry(via_usage="routing_via"),
            source=source,
        )

        component_pin_board = SemanticBoard.model_construct(
            via_templates=[via_template],
            vias=[component_pin],
            pads=[],
        )
        routing_board = SemanticBoard.model_construct(
            via_templates=[via_template],
            vias=[routing_via],
            pads=[],
        )

        self.assertFalse(_semantic_via_can_emit_as_net_via(component_pin))
        self.assertTrue(_semantic_via_can_emit_as_net_via(through_component_pin))
        self.assertTrue(_semantic_via_can_emit_as_net_via(routing_via))
        self.assertEqual(_via_templates_for_export(component_pin_board), [])
        self.assertEqual(_via_templates_for_export(routing_board), [via_template])

    def test_aedb_via_template_ids_reserve_hidden_mask_slots_after_routing(
        self,
    ) -> None:
        from aurora_translator.semantic.models import (
            SemanticViaTemplate,
            SemanticViaTemplateGeometry,
            SourceRef,
        )
        from aurora_translator.targets.auroradb.geometry import _aaf_via_template_ids

        source = SourceRef.model_construct(source_format="aedb")

        def template(name: str, group: int, order: int) -> SemanticViaTemplate:
            return SemanticViaTemplate.model_construct(
                id=f"via_template:{name}",
                name=name,
                geometry=SemanticViaTemplateGeometry.model_construct(
                    auroradb_sort_group=group,
                    auroradb_sort_order=order,
                    auroradb_hidden_id_reserve_after_group_0=3,
                ),
                source=source,
            )

        via8 = template("VIA8D16", 0, 0)
        via10 = template("VIA10D18", 0, 1)
        c060 = template("C060-040T", 1, 0)
        s060 = template("S060-040T", 1, 1)

        ids = _aaf_via_template_ids([via8, via10, c060, s060])

        self.assertEqual(ids[via8.id], "1")
        self.assertEqual(ids[via10.id], "2")
        self.assertEqual(ids[c060.id], "6")
        self.assertEqual(ids[s060.id], "7")


if __name__ == "__main__":
    unittest.main()
