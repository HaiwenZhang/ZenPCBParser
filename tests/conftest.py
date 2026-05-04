from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = PROJECT_ROOT.parent
GOLDEN_DIR = PROJECT_ROOT / "tests" / "fixtures" / "golden"

if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))


def load_golden_json(name: str) -> Any:
    return json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))


def assert_matches_golden_json(payload: Any, name: str) -> None:
    expected = load_golden_json(name)
    assert payload == expected
