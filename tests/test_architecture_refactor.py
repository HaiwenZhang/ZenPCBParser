from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = PROJECT_ROOT.parent

if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))


class ArchitectureRefactorTests(unittest.TestCase):
    def test_primitive_models_do_not_define_auroradb_private_attrs(self) -> None:
        from aurora_translator.semantic.models import SemanticPrimitive
        from aurora_translator.sources.aedb.models import (
            PathPrimitiveModel,
            PolygonPrimitiveModel,
        )

        for model_class in (
            SemanticPrimitive,
            PathPrimitiveModel,
            PolygonPrimitiveModel,
        ):
            private_attrs = getattr(model_class, "__private_attributes__", {})
            names = set(model_class.model_fields) | set(private_attrs)
            self.assertFalse(
                any("_auroradb" in name for name in names),
                f"{model_class.__name__} still exposes AuroraDB-specific fields: {sorted(names)}",
            )

    def test_semantic_primitive_json_round_trips_explicit_geometry(self) -> None:
        from aurora_translator.semantic.models import SemanticPrimitive, SourceRef

        primitive = SemanticPrimitive(
            id="primitive.trace.1",
            kind="trace",
            layer_name="TOP",
            geometry={
                "width": 5.0,
                "center_line": [[0.0, 0.0], [10.0, 0.0]],
            },
            source=SourceRef(
                source_format="aedb", path="primitives.paths[0]", raw_id="1"
            ),
        )

        payload = primitive.model_dump(mode="json")
        self.assertEqual(payload["geometry"]["center_line"], [[0.0, 0.0], [10.0, 0.0]])
        self.assertNotIn("_auroradb", str(payload))

    def test_main_cli_import_does_not_load_pyedb(self) -> None:
        script = (
            "import sys\n"
            f"sys.path.insert(0, {str(PROJECT_PARENT)!r})\n"
            "import aurora_translator.cli.main\n"
            "print('pyedb' in sys.modules)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout.strip(), "False")

    def test_direct_trace_exporter_uses_explicit_center_line_geometry(self) -> None:
        from aurora_translator.semantic.models import SemanticPrimitive, SourceRef
        from aurora_translator.sources.auroradb.block import AuroraBlock
        from aurora_translator.targets.auroradb.direct import (
            _DirectLayoutBuilder,
            _TraceShape,
        )
        from aurora_translator.targets.auroradb.layout import (
            _direct_add_trace_geometries,
        )

        builder = _DirectLayoutBuilder()
        primitive = SemanticPrimitive(
            id="primitive.trace.1",
            kind="trace",
            layer_name="TOP",
            net_id="net.1",
            geometry={
                "width": 5.0,
                "center_line": [[0.0, 0.0], [10.0, 0.0]],
            },
            source=SourceRef(
                source_format="aedb", path="primitives.paths[0]", raw_id="1"
            ),
        )

        emitted = _direct_add_trace_geometries(
            builder,
            primitive,
            "N1",
            "TOP",
            {"5": _TraceShape("TRACE_5", 5.0)},
            start_index=0,
            source_unit="mil",
        )

        self.assertEqual(emitted, 1)
        layer = builder.layers_by_key["top"]
        net_block = layer.net_geometry_by_name["n1"]
        geometry_blocks = [
            child for child in net_block.children if isinstance(child, AuroraBlock)
        ]
        self.assertEqual(len(geometry_blocks), 1)
        self.assertIsNotNone(geometry_blocks[0].get_item("Line"))

    def test_aedb_arc_height_direction_matches_pre_refactor_cache(self) -> None:
        from aurora_translator.semantic.adapters import aedb as aedb_adapter
        from aurora_translator.targets.auroradb.direct import _TracePoint
        from aurora_translator.targets.auroradb.geometry import (
            _arc_center,
            _arc_direction_flag,
            _polygon_vertex_parts_from_arcs,
            _polygon_vertex_parts_from_raw_points,
        )

        self.assertEqual(
            _arc_center(_TracePoint(x=0, y=0), _TracePoint(x=10, y=0), -5)[2],
            "Y",
        )
        self.assertEqual(
            _arc_center(_TracePoint(x=0, y=0), _TracePoint(x=10, y=0), 5)[2],
            "N",
        )
        self.assertEqual(aedb_adapter._ccw_flag_from_arc_height(-5), "Y")
        self.assertEqual(aedb_adapter._ccw_flag_from_arc_height(5), "N")

        raw_points = [[0, 0], [-5, 1e101], [10, 0]]
        point_parts = _polygon_vertex_parts_from_raw_points(
            raw_points, source_unit="mil"
        )
        self.assertEqual(point_parts[1][-1], "Y")

        arc_parts = _polygon_vertex_parts_from_arcs(
            [{"start": [0, 0], "end": [10, 0], "height": -5}],
            source_unit="mil",
        )
        self.assertEqual(arc_parts[1][-1], "Y")

        explicit_arc = {
            "start": [0, 0],
            "end": [10, 0],
            "center": [5, 5],
            "height": 5,
            "is_ccw": True,
        }
        self.assertEqual(_arc_direction_flag(explicit_arc, source_unit="mil"), "Y")

    def test_auroradb_formatting_helpers_are_exporter_neutral(self) -> None:
        from aurora_translator.targets.auroradb.formatting import (
            _format_rotation,
            _length_to_mil,
            _point_tuple,
        )

        self.assertAlmostEqual(
            _length_to_mil("1mm", source_unit=None), 39.37007874015748
        )
        self.assertEqual(
            _point_tuple({"x": "1mm", "y": 2}, source_unit="mm"),
            (39.37007874015748, 78.74015748031496),
        )
        self.assertEqual(
            _format_rotation(1.5707963267948966, source_format="odbpp"), "90"
        )
        self.assertEqual(
            _format_rotation(1.5707963267948966, source_format="aedb"), "-90"
        )

    def test_auroradb_name_helpers_are_exporter_neutral(self) -> None:
        from aurora_translator.targets.auroradb.names import (
            _aaf_atom,
            _auroradb_net_name,
            _pin_sort_key,
            _standardize_name,
            _tuple_value,
            _unique_name,
        )

        self.assertEqual(_standardize_name("R 1/A-B"), "R_1_A_B")
        self.assertEqual(_auroradb_net_name('"NoNet"'), "NoNet")
        self.assertEqual(_tuple_value("A,B"), '"A,B"')
        self.assertEqual(_aaf_atom("U 1"), '"U 1"')
        self.assertLess(_pin_sort_key("2"), _pin_sort_key("10"))
        seen = {"net"}
        self.assertEqual(_unique_name("NET", seen), "NET_2")

    def test_auroradb_stackup_helpers_are_exporter_neutral(self) -> None:
        from aurora_translator.targets.auroradb.stackup import (
            _ExportLayer,
            _stackup_dat,
            _stackup_json,
        )

        layers = [
            _ExportLayer(
                source_name="TOP",
                name="TOP",
                kind="Metal",
                thickness_mil=1.2,
                material_name="COPPER_AURORA",
                conductivity=5.8e7,
            )
        ]

        self.assertIn("Metal TOP 1.2 58000000", _stackup_dat(layers))
        payload = _stackup_json(layers)
        self.assertEqual(payload["version"], "1.1")
        self.assertEqual(payload["layers"][0]["roughness"], {"type": "no"})


if __name__ == "__main__":
    unittest.main()
