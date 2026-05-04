from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Event, Thread
from time import perf_counter
from typing import Iterable, Iterator, Mapping, TypeVar

from aurora_translator.shared.metrics import (
    current_process_memory,
    current_runtime_metrics_recorder,
    format_bytes,
)


DEFAULT_LOG_FILE = Path("logs") / "aurora_translator.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
BANNER_WIDTH = 96
PROJECT_DISPLAY_NAME = "Aurora Translator"
DEFAULT_HEARTBEAT_SECONDS = 10.0
DEFAULT_PROGRESS_PERCENT_STEP = 10.0
DEFAULT_PROGRESS_MIN_LOG_SECONDS = 5.0

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class HeartbeatHandle:
    stop_event: Event
    thread: Thread

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=1.0)


def configure_logging(
    *,
    log_file: str | Path | None = None,
    level: str = "INFO",
) -> Path:
    """Configure console and rotating file logging for the parser."""

    resolved_log_file = Path(log_file).expanduser() if log_file else DEFAULT_LOG_FILE
    resolved_log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("aurora_translator")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = RotatingFileHandler(
        resolved_log_file,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return resolved_log_file.resolve()


def format_fields(**fields: object) -> str:
    """Format structured fields into a compact space-separated suffix."""

    clean_fields = {key: value for key, value in fields.items() if value is not None}
    if not clean_fields:
        return ""
    return " " + " ".join(
        f"{key}={_format_value(value)}" for key, value in clean_fields.items()
    )


def log_run_start(
    logger: logging.Logger,
    title: str,
    *,
    log_path: str | Path | None = None,
    **fields: object,
) -> None:
    """Write a consistent command/run start block."""

    log_banner(logger, title, heading=PROJECT_DISPLAY_NAME)
    logger.info("Run started: %s", _capitalize_first(title))
    if log_path is not None:
        logger.info("Log file: %s", log_path)
    if fields:
        log_kv(logger, "Settings", **fields)


def log_run_complete(logger: logging.Logger, title: str = "run") -> None:
    """Write a consistent command/run completion line."""

    logger.info("Run completed: %s", _capitalize_first(title))


def log_banner(
    logger: logging.Logger, title: str, *, heading: str | None = None
) -> None:
    """Write a visually distinct section banner."""

    logger.info("%s", "*" * BANNER_WIDTH)
    if heading:
        logger.info("*%s*", f" {heading} ".center(BANNER_WIDTH - 2))
    logger.info("*%s*", f" {_capitalize_first(title)} ".center(BANNER_WIDTH - 2))
    logger.info("%s", "*" * BANNER_WIDTH)


def log_section(logger: logging.Logger, title: str) -> None:
    """Write a compact section separator inside a run log."""

    log_banner(logger, title)


def log_kv(logger: logging.Logger, title: str, **fields: object) -> None:
    """Write a compact, aligned key/value block."""

    level = int(fields.pop("level", logging.INFO))
    clean_fields = {key: value for key, value in fields.items() if value is not None}
    if not clean_fields:
        logger.log(level, "%s", title)
        return

    logger.log(level, "%s", title)
    key_width = max(len(key) for key in clean_fields)
    for key, value in clean_fields.items():
        logger.log(level, "  %-*s : %s", key_width, key, _format_value(value))


def log_field_block(
    logger: logging.Logger,
    title: str,
    *,
    fields: Mapping[str, object] | None = None,
    sections: Mapping[str, Mapping[str, object]] | None = None,
    indent: int = 2,
    level: int = logging.INFO,
) -> None:
    """Write a grouped field block so repeated prefixes become indentation."""

    logger.log(level, "%s", title)
    if fields:
        _log_aligned_fields(logger, fields, indent=indent, level=level)
    if sections:
        for section_title, section_fields in sections.items():
            clean_fields = {
                key: value for key, value in section_fields.items() if value is not None
            }
            if not clean_fields:
                continue
            logger.log(level, "%s%s", " " * indent, section_title)
            _log_aligned_fields(logger, clean_fields, indent=indent * 2, level=level)


@contextmanager
def log_timing(
    logger: logging.Logger,
    operation: str,
    *,
    banner: bool = False,
    heartbeat: bool = True,
    heartbeat_seconds: float = DEFAULT_HEARTBEAT_SECONDS,
    level: int = logging.INFO,
    **fields: object,
) -> Iterator[None]:
    """Log an operation with consistent start/progress/done status keywords."""

    display_operation = _capitalize_first(operation)
    suffix = format_fields(**fields)
    enabled = logger.isEnabledFor(level)
    if enabled:
        if banner:
            log_banner(logger, display_operation)
        logger.log(level, "Start: %s%s", display_operation, suffix)
    recorder = current_runtime_metrics_recorder()
    metric_event = (
        recorder.start(display_operation, fields) if recorder is not None else None
    )
    started_at = perf_counter()
    heartbeat_handle = (
        _start_heartbeat(
            logger,
            display_operation,
            started_at,
            interval_seconds=heartbeat_seconds,
            level=level,
        )
        if heartbeat and enabled
        else None
    )
    try:
        yield
    except Exception:
        elapsed = perf_counter() - started_at
        if heartbeat_handle is not None:
            heartbeat_handle.stop()
        if recorder is not None and metric_event is not None:
            recorder.finish(metric_event, failed=True)
        logger.exception(
            "Failed: %s%s elapsed=%.3fs", display_operation, suffix, elapsed
        )
        raise
    else:
        elapsed = perf_counter() - started_at
        if heartbeat_handle is not None:
            heartbeat_handle.stop()
        if recorder is not None and metric_event is not None:
            recorder.finish(metric_event)
        if enabled:
            logger.log(level, "Done: %s elapsed=%.3fs", display_operation, elapsed)


def iter_progress(
    values: Iterable[T],
    logger: logging.Logger,
    operation: str,
    *,
    total: int | None = None,
    interval_seconds: float = DEFAULT_HEARTBEAT_SECONDS,
    percent_step: float = DEFAULT_PROGRESS_PERCENT_STEP,
    min_log_spacing_seconds: float = DEFAULT_PROGRESS_MIN_LOG_SECONDS,
) -> Iterator[T]:
    """Yield items while periodically logging processed/total progress."""

    reporter = ProgressReporter(
        logger,
        _capitalize_first(operation),
        total=total,
        interval_seconds=interval_seconds,
        percent_step=percent_step,
        min_log_spacing_seconds=min_log_spacing_seconds,
    )
    for index, value in enumerate(values, start=1):
        yield value
        reporter.update(index)


class ProgressReporter:
    """Time- and percent-based progress logging for long loops."""

    def __init__(
        self,
        logger: logging.Logger,
        operation: str,
        *,
        total: int | None,
        interval_seconds: float = DEFAULT_HEARTBEAT_SECONDS,
        percent_step: float = DEFAULT_PROGRESS_PERCENT_STEP,
        min_log_spacing_seconds: float = DEFAULT_PROGRESS_MIN_LOG_SECONDS,
    ) -> None:
        self._logger = logger
        self._operation = operation
        self._total = total if total and total > 0 else None
        self._interval_seconds = interval_seconds
        self._percent_step = percent_step
        self._min_log_spacing_seconds = max(0.0, min_log_spacing_seconds)
        self._started_at = perf_counter()
        self._last_logged_at = self._started_at
        self._next_percent = percent_step

    def update(self, processed: int) -> None:
        now = perf_counter()
        elapsed = now - self._started_at
        if elapsed < self._min_log_spacing_seconds:
            return

        percent = (processed / self._total * 100.0) if self._total else None
        reached_interval = now - self._last_logged_at >= self._interval_seconds
        reached_percent = percent is not None and percent >= self._next_percent
        reached_final = self._total is not None and processed >= self._total
        too_soon = now - self._last_logged_at < self._min_log_spacing_seconds
        if not reached_final and too_soon:
            return
        if not reached_final and not reached_interval and not reached_percent:
            return

        self._last_logged_at = now
        if percent is not None:
            while self._next_percent <= percent:
                self._next_percent += self._percent_step
        self._logger.info(
            "Progress: %s%s",
            self._operation,
            format_fields(
                processed=f"{processed}/{self._total}"
                if self._total is not None
                else processed,
                percent=f"{percent:.1f}" if percent is not None else None,
                elapsed=f"{int(elapsed)}s",
                rate=f"{processed / elapsed:.1f}/s" if elapsed > 0 else "0.0/s",
                rss=_current_rss_text(),
            ),
        )


def _start_heartbeat(
    logger: logging.Logger,
    operation: str,
    started_at: float,
    *,
    interval_seconds: float,
    level: int = logging.INFO,
) -> HeartbeatHandle | None:
    if interval_seconds <= 0:
        return None

    stop_event = Event()

    def _run() -> None:
        while not stop_event.wait(interval_seconds):
            elapsed = int(perf_counter() - started_at)
            logger.log(
                level,
                "Progress: %s%s",
                operation,
                format_fields(elapsed=f"{elapsed}s", rss=_current_rss_text()),
            )

    thread = Thread(target=_run, name=f"aurora-log-heartbeat-{operation}", daemon=True)
    thread.start()
    return HeartbeatHandle(stop_event=stop_event, thread=thread)


def _current_rss_text() -> str:
    return format_bytes(current_process_memory().working_set_bytes).replace(" ", "")


def _format_value(value: object) -> str:
    if isinstance(value, (list, tuple, set)):
        return "[" + ", ".join(str(item) for item in value) + "]"
    return str(value)


def _log_aligned_fields(
    logger: logging.Logger,
    fields: Mapping[str, object],
    *,
    indent: int,
    level: int,
) -> None:
    clean_fields = {key: value for key, value in fields.items() if value is not None}
    if not clean_fields:
        return
    key_width = max(len(key) for key in clean_fields)
    padding = " " * indent
    for key, value in clean_fields.items():
        logger.log(level, "%s%-*s : %s", padding, key_width, key, _format_value(value))


def _capitalize_first(value: str) -> str:
    if not value:
        return value
    return value[:1].upper() + value[1:]
