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


if __name__ == "__main__":
    unittest.main()
