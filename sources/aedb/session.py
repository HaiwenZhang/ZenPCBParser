from __future__ import annotations

from pathlib import Path
from typing import Any

from pyedb import Edb


def open_aedb_session(source: Path, *, version: str) -> Any:
    """Open an AEDB directory through PyEDB's local .NET backend."""

    return Edb(edbpath=str(source), grpc=False, isreadonly=True, version=version)


def close_aedb_session(pedb: Any) -> None:
    """Close a PyEDB session."""

    pedb.close()
