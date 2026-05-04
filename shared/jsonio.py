from __future__ import annotations

from pathlib import Path
from typing import Protocol


class JsonSerializable(Protocol):
    def model_dump_json(self, *, indent: int | None = None) -> str:
        """Return a JSON representation."""


def write_json_file(
    payload: JsonSerializable, output_path: str | Path, *, indent: int | None = 2
) -> Path:
    """Write a Pydantic payload to a JSON file."""

    resolved_output = Path(output_path).expanduser().resolve()
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(payload.model_dump_json(indent=indent), encoding="utf-8")
    return resolved_output
