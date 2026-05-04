from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = PROJECT_ROOT.parent

if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))


CASE_ROOT_ENV = "AURORA_TRANSLATOR_CASE_ROOT"
RUN_CASES_ENV = "AURORA_TRANSLATOR_RUN_CASES"
OUTPUT_ROOT_ENV = "AURORA_TRANSLATOR_CASE_OUTPUT_ROOT"
AEDB_SAMPLE_ENV = "AURORA_TRANSLATOR_AEDB_SAMPLE"
ODBPP_SAMPLE_ENV = "AURORA_TRANSLATOR_ODBPP_SAMPLE"


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def _case_root() -> Path:
    value = os.environ.get(CASE_ROOT_ENV)
    if not value:
        raise unittest.SkipTest(
            f"Set {CASE_ROOT_ENV} and {RUN_CASES_ENV}=1 to run private case tests."
        )
    return Path(value).expanduser().resolve()


def _sample_path(case_root: Path, env_name: str, pattern: str) -> Path:
    override = os.environ.get(env_name)
    if override:
        path = Path(override).expanduser()
        return path if path.is_absolute() else case_root / path
    matches = sorted(case_root.glob(pattern))
    if not matches:
        raise unittest.SkipTest(f"No {pattern} sample found under {CASE_ROOT_ENV}.")
    return matches[0]


def _run_dir(case_root: Path, name: str) -> Path:
    output_root = (
        Path(os.environ.get(OUTPUT_ROOT_ENV, case_root / "outputs"))
        .expanduser()
        .resolve()
    )
    path = output_root / "regression" / f"{name}_{uuid.uuid4().hex[:12]}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _run_cli(*args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "main.py", *map(str, args)],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=1200,
    )


def _tree_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


@unittest.skipUnless(
    _truthy_env(RUN_CASES_ENV), f"Set {RUN_CASES_ENV}=1 to run private case tests."
)
class PrivateCaseRegressionTests(unittest.TestCase):
    def test_odbpp_private_sample_end_to_end_counts(self) -> None:
        from aurora_translator.semantic.version import (
            SEMANTIC_JSON_SCHEMA_VERSION,
            SEMANTIC_PARSER_VERSION,
        )

        case_root = _case_root()
        sample = _sample_path(case_root, ODBPP_SAMPLE_ENV, "*.tgz")
        binary = (
            PROJECT_ROOT
            / "crates"
            / "odbpp_parser"
            / "target"
            / "release"
            / ("odbpp_parser.exe" if os.name == "nt" else "odbpp_parser")
        )
        if not binary.exists() and not os.environ.get("AURORA_ODBPP_PARSER"):
            raise unittest.SkipTest(
                "Build crates/odbpp_parser first or set AURORA_ODBPP_PARSER."
            )

        run_dir = _run_dir(case_root, "odbpp")
        semantic_output = run_dir / "semantic.json"
        _run_cli(
            "convert",
            "--from",
            "odbpp",
            "--to",
            "auroradb",
            sample,
            "-o",
            run_dir / "auroradb",
            "--source-output",
            run_dir / "source.json",
            "--semantic-output",
            semantic_output,
            "--coverage-output",
            run_dir / "coverage.json",
        )

        payload = json.loads(semantic_output.read_text(encoding="utf-8"))
        self.assertEqual(payload["metadata"]["parser_version"], SEMANTIC_PARSER_VERSION)
        self.assertEqual(
            payload["metadata"]["output_schema_version"], SEMANTIC_JSON_SCHEMA_VERSION
        )
        self.assertEqual(
            payload["summary"],
            {
                "layer_count": 32,
                "material_count": 2,
                "shape_count": 253,
                "via_template_count": 66,
                "net_count": 655,
                "component_count": 682,
                "footprint_count": 73,
                "pin_count": 3017,
                "pad_count": 24472,
                "via_count": 5466,
                "primitive_count": 111009,
                "edge_count": payload["summary"]["edge_count"],
                "diagnostic_count": 2,
            },
        )
        self.assertTrue((run_dir / "auroradb" / "layout.db").is_file())
        self.assertTrue((run_dir / "auroradb" / "parts.db").is_file())
        self.assertTrue((run_dir / "coverage.json").is_file())

    def test_aedb_private_sample_minimal_and_full_outputs_match(self) -> None:
        case_root = _case_root()
        sample = _sample_path(case_root, AEDB_SAMPLE_ENV, "*.aedb")
        run_dir = _run_dir(case_root, "aedb")
        minimal_output = run_dir / "minimal_auroradb"
        full_output = run_dir / "full_auroradb"

        _run_cli(
            "convert",
            "--from",
            "aedb",
            "--to",
            "auroradb",
            sample,
            "-o",
            minimal_output,
        )
        _run_cli(
            "convert",
            "--from",
            "aedb",
            "--to",
            "auroradb",
            "--aedb-parse-profile",
            "full",
            sample,
            "-o",
            full_output,
        )

        minimal_hashes = _tree_hashes(minimal_output)
        full_hashes = _tree_hashes(full_output)
        self.assertEqual(len(minimal_hashes), 14)
        self.assertEqual(minimal_hashes, full_hashes)


if __name__ == "__main__":
    unittest.main()
