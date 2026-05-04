from __future__ import annotations

from aurora_translator.semantic.models import SemanticBoard

from conftest import assert_matches_golden_json, load_golden_json


def test_minimal_semantic_golden_fixture_validates() -> None:
    payload = load_golden_json("semantic_minimal.json")
    board = SemanticBoard.model_validate(payload).with_computed_summary()

    actual = {
        "summary": board.summary.model_dump(mode="json"),
        "primitive_geometry": board.primitives[0].geometry.model_dump(mode="json"),
        "net_primitive_ids": board.nets[0].primitive_ids,
    }

    assert_matches_golden_json(actual, "semantic_minimal_expected.json")
