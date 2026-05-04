from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
import ctypes
import os
from ctypes import wintypes
from time import perf_counter
from typing import Iterator


_CURRENT_RECORDER: ContextVar[RuntimeMetricsRecorder | None] = ContextVar(
    "aurora_runtime_metrics_recorder",
    default=None,
)


@dataclass(frozen=True, slots=True)
class MemorySnapshot:
    """Current process memory sample."""

    working_set_bytes: int | None = None
    peak_working_set_bytes: int | None = None
    private_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class RuntimeMetricEvent:
    """One timed operation with sampled process memory."""

    start_order: int
    operation: str
    fields: dict[str, object]
    depth: int
    elapsed_seconds: float
    started_memory: MemorySnapshot
    ended_memory: MemorySnapshot
    failed: bool = False

    @property
    def working_set_delta_bytes(self) -> int | None:
        start = self.started_memory.working_set_bytes
        end = self.ended_memory.working_set_bytes
        if start is None or end is None:
            return None
        return end - start

    @property
    def private_delta_bytes(self) -> int | None:
        start = self.started_memory.private_bytes
        end = self.ended_memory.private_bytes
        if start is None or end is None:
            return None
        return end - start


@dataclass(frozen=True, slots=True)
class _ActiveMetricEvent:
    start_order: int
    operation: str
    fields: dict[str, object]
    depth: int
    started_at: float
    started_memory: MemorySnapshot


@dataclass(slots=True)
class RuntimeMetricsRecorder:
    """Collect timing and memory samples for one CLI run."""

    started_at: datetime = field(default_factory=lambda: datetime.now().astimezone())
    started_memory: MemorySnapshot = field(
        default_factory=lambda: current_process_memory()
    )
    events: list[RuntimeMetricEvent] = field(default_factory=list)
    _depth: int = 0
    _start_order: int = 0

    def start(
        self, operation: str, fields: dict[str, object] | None = None
    ) -> _ActiveMetricEvent:
        start_order = self._start_order
        self._start_order += 1
        active = _ActiveMetricEvent(
            start_order=start_order,
            operation=operation,
            fields=dict(fields or {}),
            depth=self._depth,
            started_at=perf_counter(),
            started_memory=current_process_memory(),
        )
        self._depth += 1
        return active

    def finish(
        self, active: _ActiveMetricEvent, *, failed: bool = False
    ) -> RuntimeMetricEvent:
        event = RuntimeMetricEvent(
            start_order=active.start_order,
            operation=active.operation,
            fields=active.fields,
            depth=active.depth,
            elapsed_seconds=perf_counter() - active.started_at,
            started_memory=active.started_memory,
            ended_memory=current_process_memory(),
            failed=failed,
        )
        self._depth = active.depth
        self.events.append(event)
        return event

    def snapshot(self) -> MemorySnapshot:
        return current_process_memory()


@contextmanager
def runtime_metrics_context(
    recorder: RuntimeMetricsRecorder,
) -> Iterator[RuntimeMetricsRecorder]:
    token = _CURRENT_RECORDER.set(recorder)
    try:
        yield recorder
    finally:
        _CURRENT_RECORDER.reset(token)


def current_runtime_metrics_recorder() -> RuntimeMetricsRecorder | None:
    return _CURRENT_RECORDER.get()


def current_process_memory() -> MemorySnapshot:
    if os.name == "nt":
        return _windows_process_memory()
    return MemorySnapshot()


def format_bytes(value: int | None) -> str:
    if value is None:
        return "n/a"
    return f"{value / (1024 * 1024):.1f} MiB"


def format_signed_bytes(value: int | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else "-"
    return f"{sign}{abs(value) / (1024 * 1024):.1f} MiB"


def _windows_process_memory() -> MemorySnapshot:
    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(ProcessMemoryCounters)
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        process_handle = kernel32.GetCurrentProcess()
        success = psapi.GetProcessMemoryInfo(
            process_handle,
            ctypes.byref(counters),
            counters.cb,
        )
    except Exception:
        return MemorySnapshot()

    if not success:
        return MemorySnapshot()

    return MemorySnapshot(
        working_set_bytes=int(counters.WorkingSetSize),
        peak_working_set_bytes=int(counters.PeakWorkingSetSize),
        private_bytes=int(counters.PagefileUsage),
    )
