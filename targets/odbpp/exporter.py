from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from aurora_translator.semantic.models import SemanticBoard
from aurora_translator.shared.logging import log_kv, log_timing


logger = logging.getLogger("aurora_translator.targets.odbpp")


class ODBPPExporterError(ValueError):
    """Raised when the Rust ODB++ exporter cannot write a target package."""


@dataclass(slots=True)
class SemanticOdbppExport:
    root: Path
    odbpp: Path


def write_odbpp_from_semantic(
    board: SemanticBoard,
    path: str | Path,
    *,
    rust_binary: str | Path | None = None,
    step: str | None = None,
) -> SemanticOdbppExport:
    """Write an ODB++ directory package from a SemanticBoard via the Rust exporter."""

    root = Path(path).expanduser().resolve()
    binary = resolve_rust_binary(rust_binary)
    log_kv(
        logger,
        "ODB++ target export settings",
        output=root,
        source_format=board.metadata.source_format,
        unit=board.units,
        layers=board.summary.layer_count,
        nets=board.summary.net_count,
        components=board.summary.component_count,
        primitives=board.summary.primitive_count,
        rust_binary=binary,
        step=step or "pcb",
    )

    with tempfile.TemporaryDirectory(prefix="aurora_odbpp_export_") as temp_dir:
        semantic_json = Path(temp_dir) / "semantic.json"
        semantic_json.write_text(board.model_dump_json(), encoding="utf-8")
        command = [
            str(binary),
            str(semantic_json),
            "--output",
            str(root),
        ]
        if step:
            command.extend(["--step", step])

        try:
            with log_timing(logger, "run Rust ODB++ exporter", output=root):
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
        except OSError as exc:
            raise ODBPPExporterError(
                f"Failed to execute Rust ODB++ exporter {binary}: {exc}"
            ) from exc

    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        raise ODBPPExporterError(
            "Rust ODB++ exporter failed with exit code "
            f"{completed.returncode}: {stderr or stdout}"
        )

    logger.info("ODB++ exporter completed: %s", completed.stdout.strip())
    return SemanticOdbppExport(root=root, odbpp=root)


def resolve_rust_binary(rust_binary: str | Path | None = None) -> Path:
    """Resolve the odbpp_exporter executable from an explicit path, env var, build, or PATH."""

    candidates: list[Path] = []
    if rust_binary is not None:
        candidates.append(Path(rust_binary).expanduser())

    env_binary = os.environ.get("AURORA_ODBPP_EXPORTER")
    if env_binary:
        candidates.append(Path(env_binary).expanduser())

    repo_root = Path(__file__).resolve().parents[2]
    executable_name = "odbpp_exporter.exe" if os.name == "nt" else "odbpp_exporter"
    candidates.extend(
        [
            repo_root
            / "crates"
            / "odbpp_exporter"
            / "target"
            / "release"
            / executable_name,
            repo_root
            / "crates"
            / "odbpp_exporter"
            / "target"
            / "debug"
            / executable_name,
            repo_root / "target" / "release" / executable_name,
            repo_root / "target" / "debug" / executable_name,
        ]
    )

    path_binary = shutil.which("odbpp_exporter")
    if path_binary:
        candidates.append(Path(path_binary))

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

    searched = "\n  - ".join(str(candidate) for candidate in candidates)
    raise ODBPPExporterError(
        "Rust ODB++ exporter executable was not found. Build it with "
        "`cargo build --release --manifest-path crates/odbpp_exporter/Cargo.toml`, "
        "or set AURORA_ODBPP_EXPORTER to the executable path. Searched:\n  - "
        f"{searched}"
    )
