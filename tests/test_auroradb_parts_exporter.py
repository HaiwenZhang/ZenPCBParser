from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = PROJECT_ROOT.parent

if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))


class AuroraDBPartsExporterTests(unittest.TestCase):
    def test_part_export_plan_canonicalizes_footprint_name_case(self) -> None:
        from aurora_translator.semantic.models import (
            SemanticBoard,
            SemanticComponent,
            SemanticMetadata,
        )
        from aurora_translator.targets.auroradb.parts import _part_export_plan

        board = SemanticBoard.model_construct(
            metadata=SemanticMetadata.model_construct(source_format="altium"),
            components=[
                SemanticComponent.model_construct(
                    id="component:a",
                    part_name="A",
                    package_name="sot23-5",
                ),
                SemanticComponent.model_construct(
                    id="component:b",
                    part_name="B",
                    package_name="SOT23-5",
                ),
            ],
            footprints=[],
        )

        plan = _part_export_plan(board)

        self.assertEqual(
            {variant.footprint_name for variant in plan.variants}, {"sot23-5"}
        )

    def test_part_plan_footprint_names_use_variant_exact_case(self) -> None:
        from aurora_translator.semantic.models import SemanticBoard, SemanticFootprint
        from aurora_translator.targets.auroradb.direct import (
            _PartExportPlan,
            _PartExportVariant,
        )
        from aurora_translator.targets.auroradb.parts import _part_plan_footprint_names

        board = SemanticBoard.model_construct(
            components=[],
            footprints=[
                SemanticFootprint.model_construct(
                    id="footprint:SOT23-5",
                    name="SOT23-5",
                )
            ],
        )
        plan = _PartExportPlan(
            part_names_by_component_id={},
            variants=[
                _PartExportVariant(
                    export_part_name="SP4446",
                    source_part_name="SP4446",
                    footprint_name="sot23-5",
                    representative_component_id="component:1",
                    component_ids=["component:1"],
                    source_footprint_name="sot23-5",
                )
            ],
        )

        self.assertEqual(
            _part_plan_footprint_names(board, plan)["sot23-5"],
            ("sot23-5", "sot23-5"),
        )

    def test_odbpp_part_export_prefers_component_pads_over_package_pads(
        self,
    ) -> None:
        from aurora_translator.semantic.models import (
            SemanticBoard,
            SemanticComponent,
            SemanticFootprint,
            SemanticFootprintGeometry,
            SemanticLayer,
            SemanticMetadata,
            SemanticPad,
            SemanticPadGeometry,
            SemanticPin,
            SemanticPoint,
            SemanticShape,
            SourceRef,
        )
        from aurora_translator.targets.auroradb.parts import _design_part_lines

        source = SourceRef.model_construct(source_format="odbpp")
        board = SemanticBoard.model_construct(
            metadata=SemanticMetadata.model_construct(source_format="odbpp"),
            units="mm",
            layers=[
                SemanticLayer.model_construct(
                    id="layer:top",
                    name="TOP",
                    role="signal",
                    side="top",
                    source=source,
                )
            ],
            shapes=[
                SemanticShape.model_construct(
                    id="shape:pad",
                    kind="rectangle",
                    auroradb_type="Rectangle",
                    values=[0.0, 0.0, 0.25, 0.25],
                    source=source,
                )
            ],
            footprints=[
                SemanticFootprint.model_construct(
                    id="footprint:pkg",
                    name="PKG",
                    geometry=SemanticFootprintGeometry.model_construct(
                        outlines=[
                            {
                                "auroradb_type": "Rectangle",
                                "values": [0.18, 0.0, 0.4, 0.2],
                            }
                        ],
                        pads=[
                            {
                                "pin_name": "1",
                                "position": [10.0, 0.0],
                                "shape": {
                                    "auroradb_type": "Rectangle",
                                    "values": [0.0, 0.0, 9.0, 9.0],
                                },
                            }
                        ],
                    ),
                    source=source,
                )
            ],
            components=[
                SemanticComponent.model_construct(
                    id="component:R1",
                    refdes="R1",
                    part_name="PN",
                    package_name="PKG",
                    footprint_id="footprint:pkg",
                    layer_name="TOP",
                    side="top",
                    attributes={"COMPONENT_AI_ORIGIN": "0.1,0"},
                    location=SemanticPoint.model_construct(x=1.0, y=1.0),
                    pin_ids=["pin:R1:1"],
                    pad_ids=["pad:R1:1"],
                    source=source,
                )
            ],
            pins=[
                SemanticPin.model_construct(
                    id="pin:R1:1",
                    name="1",
                    component_id="component:R1",
                    pad_ids=["pad:R1:1"],
                    layer_name="TOP",
                    position=SemanticPoint.model_construct(x=0.9, y=1.0),
                    source=source,
                )
            ],
            pads=[
                SemanticPad.model_construct(
                    id="pad:R1:1",
                    name="1",
                    component_id="component:R1",
                    pin_id="pin:R1:1",
                    layer_name="TOP",
                    position=SemanticPoint.model_construct(x=0.9, y=1.0),
                    geometry=SemanticPadGeometry.model_construct(shape_id="shape:pad"),
                    source=source,
                )
            ],
        )

        text = "\n".join(_design_part_lines(board))

        self.assertIn("library set -unit <mm>", text)
        self.assertIn("library add -g <{1:Rectangle,(0,0,0.25,0.25)}>", text)
        self.assertIn("-fpn <1>", text)
        self.assertIn("-location <(-0.1,0)>", text)
        self.assertNotIn("Rectangle,(0,0,9,9)", text)
        self.assertNotIn("library add -g <{B1:", text)

    def test_odbpp_part_export_splits_footprints_by_local_pad_locations(self) -> None:
        from aurora_translator.semantic.models import (
            SemanticBoard,
            SemanticComponent,
            SemanticFootprint,
            SemanticLayer,
            SemanticMetadata,
            SemanticPad,
            SemanticPadGeometry,
            SemanticPin,
            SemanticPoint,
            SemanticShape,
            SourceRef,
        )
        from aurora_translator.targets.auroradb.parts import _design_part_lines

        source = SourceRef.model_construct(source_format="odbpp")
        board = SemanticBoard.model_construct(
            metadata=SemanticMetadata.model_construct(source_format="odbpp"),
            units="mm",
            layers=[
                SemanticLayer.model_construct(
                    id="layer:top",
                    name="TOP",
                    role="signal",
                    side="top",
                    source=source,
                )
            ],
            shapes=[
                SemanticShape.model_construct(
                    id="shape:pad",
                    kind="rectangle",
                    auroradb_type="Rectangle",
                    values=[0.0, 0.0, 0.25, 0.25],
                    source=source,
                )
            ],
            footprints=[
                SemanticFootprint.model_construct(
                    id="footprint:pkg",
                    name="PKG",
                    source=source,
                )
            ],
            components=[
                SemanticComponent.model_construct(
                    id="component:R1",
                    refdes="R1",
                    part_name="PN",
                    package_name="PKG",
                    footprint_id="footprint:pkg",
                    layer_name="TOP",
                    side="top",
                    location=SemanticPoint.model_construct(x=1.0, y=1.0),
                    pin_ids=["pin:R1:1", "pin:R1:2"],
                    pad_ids=["pad:R1:1", "pad:R1:2"],
                    source=source,
                ),
                SemanticComponent.model_construct(
                    id="component:R2",
                    refdes="R2",
                    part_name="PN",
                    package_name="PKG",
                    footprint_id="footprint:pkg",
                    layer_name="TOP",
                    side="top",
                    location=SemanticPoint.model_construct(x=2.0, y=1.0),
                    pin_ids=["pin:R2:1", "pin:R2:2"],
                    pad_ids=["pad:R2:1", "pad:R2:2"],
                    source=source,
                ),
            ],
            pins=[
                SemanticPin.model_construct(
                    id="pin:R1:1",
                    name="1",
                    component_id="component:R1",
                    pad_ids=["pad:R1:1"],
                    layer_name="TOP",
                    source=source,
                ),
                SemanticPin.model_construct(
                    id="pin:R1:2",
                    name="2",
                    component_id="component:R1",
                    pad_ids=["pad:R1:2"],
                    layer_name="TOP",
                    source=source,
                ),
                SemanticPin.model_construct(
                    id="pin:R2:1",
                    name="1",
                    component_id="component:R2",
                    pad_ids=["pad:R2:1"],
                    layer_name="TOP",
                    source=source,
                ),
                SemanticPin.model_construct(
                    id="pin:R2:2",
                    name="2",
                    component_id="component:R2",
                    pad_ids=["pad:R2:2"],
                    layer_name="TOP",
                    source=source,
                ),
            ],
            pads=[
                SemanticPad.model_construct(
                    id="pad:R1:1",
                    name="1",
                    component_id="component:R1",
                    pin_id="pin:R1:1",
                    layer_name="TOP",
                    position=SemanticPoint.model_construct(x=0.82, y=1.0),
                    geometry=SemanticPadGeometry.model_construct(shape_id="shape:pad"),
                    source=source,
                ),
                SemanticPad.model_construct(
                    id="pad:R1:2",
                    name="2",
                    component_id="component:R1",
                    pin_id="pin:R1:2",
                    layer_name="TOP",
                    position=SemanticPoint.model_construct(x=1.18, y=1.0),
                    geometry=SemanticPadGeometry.model_construct(shape_id="shape:pad"),
                    source=source,
                ),
                SemanticPad.model_construct(
                    id="pad:R2:1",
                    name="1",
                    component_id="component:R2",
                    pin_id="pin:R2:1",
                    layer_name="TOP",
                    position=SemanticPoint.model_construct(x=2.18, y=1.0),
                    geometry=SemanticPadGeometry.model_construct(shape_id="shape:pad"),
                    source=source,
                ),
                SemanticPad.model_construct(
                    id="pad:R2:2",
                    name="2",
                    component_id="component:R2",
                    pin_id="pin:R2:2",
                    layer_name="TOP",
                    position=SemanticPoint.model_construct(x=1.82, y=1.0),
                    geometry=SemanticPadGeometry.model_construct(shape_id="shape:pad"),
                    source=source,
                ),
            ],
        )

        text = "\n".join(_design_part_lines(board))

        self.assertIn('library add -footprint <"PKG__pad2">', text)
        self.assertIn("-location <(-0.18,0)>", text)
        self.assertIn("-location <(0.18,0)>", text)


if __name__ == "__main__":
    unittest.main()
