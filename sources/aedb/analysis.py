from __future__ import annotations

from pathlib import Path

from aurora_translator.sources.aedb.models import AEDBLayout
from aurora_translator.shared.metrics import (
    RuntimeMetricEvent,
    RuntimeMetricsRecorder,
    format_bytes,
    format_signed_bytes,
)


def default_analysis_log_path(
    *,
    output_path: str | Path | None,
    log_path: str | Path | None,
) -> Path:
    if output_path:
        path = Path(output_path).expanduser().resolve()
        return path.with_name(f"{path.stem}_analysis.log")
    if log_path:
        path = Path(log_path).expanduser().resolve()
        return path.with_name(f"{path.stem}_analysis.log")
    return (Path("logs") / "aurora_translator_analysis.log").resolve()


def write_aedb_analysis_log(
    payload: AEDBLayout,
    recorder: RuntimeMetricsRecorder,
    path: str | Path,
    *,
    output_path: str | Path | None,
    log_path: str | Path | None,
) -> Path:
    analysis_path = Path(path).expanduser().resolve()
    analysis_path.parent.mkdir(parents=True, exist_ok=True)
    analysis_path.write_text(
        "\n".join(
            _analysis_lines(
                payload, recorder, output_path=output_path, log_path=log_path
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return analysis_path


def _analysis_lines(
    payload: AEDBLayout,
    recorder: RuntimeMetricsRecorder,
    *,
    output_path: str | Path | None,
    log_path: str | Path | None,
) -> list[str]:
    metadata = payload.metadata
    summary = payload.summary
    ended_memory = recorder.snapshot()
    total_delta = _memory_delta(
        recorder.started_memory.working_set_bytes, ended_memory.working_set_bytes
    )
    events = sorted(recorder.events, key=lambda event: event.start_order)
    top_level_events = [event for event in events if event.depth == 0]

    lines = [
        "AEDB parse analysis",
        "=" * 96,
        f"Generated at              : {recorder.started_at.isoformat(timespec='seconds')}",
        f"Source                    : {metadata.source}",
        f"JSON output               : {Path(output_path).expanduser().resolve() if output_path else 'not written'}",
        f"Parser log                : {Path(log_path).expanduser().resolve() if log_path else 'not written'}",
        f"Project version           : {metadata.project_version}",
        f"AEDB parser version       : {metadata.parser_version}",
        f"AEDB JSON schema version  : {metadata.output_schema_version}",
        f"Backend                   : {metadata.backend}",
        f"PyEDB version             : {metadata.pyedb_version}",
        f"AEDT version              : {metadata.aedt_version}",
        "",
        "Layout counts",
        "-" * 96,
        f"Layers                    : {summary.layer_count}",
        f"Nets                      : {summary.net_count}",
        f"Components                : {summary.component_count}",
        f"Paths                     : {summary.path_count}",
        f"Polygons                  : {summary.polygon_count}",
        f"Padstack definitions      : {summary.padstack_definition_count}",
        f"Padstack instances        : {summary.padstack_instance_count}",
        "",
        "Process memory summary",
        "-" * 96,
        f"Working set at start      : {format_bytes(recorder.started_memory.working_set_bytes)}",
        f"Working set at end        : {format_bytes(ended_memory.working_set_bytes)}",
        f"Working set delta         : {format_signed_bytes(total_delta)}",
        f"Peak working set          : {format_bytes(ended_memory.peak_working_set_bytes)}",
        f"Private bytes at end      : {format_bytes(ended_memory.private_bytes)}",
        "",
        "Top-level stage summary",
        "-" * 96,
        _stage_header(),
    ]
    lines.extend(_stage_line(event) for event in top_level_events)
    lines.extend(
        [
            "",
            "Detailed stage tree",
            "-" * 96,
            _stage_header(),
        ]
    )
    lines.extend(_stage_line(event) for event in events)
    lines.extend(
        [
            "",
            "Slowest detailed stages",
            "-" * 96,
            _slow_stage_header(),
        ]
    )
    lines.extend(
        _slow_stage_line(event)
        for event in sorted(
            events, key=lambda item: item.elapsed_seconds, reverse=True
        )[:12]
    )
    lines.extend(
        [
            "",
            "Largest working set changes",
            "-" * 96,
            _memory_stage_header(),
        ]
    )
    lines.extend(
        _memory_stage_line(event) for event in _largest_memory_delta_events(events)[:12]
    )
    lines.extend(
        [
            "",
            "Notes",
            "-" * 96,
            "Rows are ordered by stage start time, so parent stages appear before their child stages.",
            "Memory is sampled from the current process working set, so it includes Python, pythonnet, .NET, and AEDB runtime allocations.",
            "Stage memory delta is the sampled end working set minus the sampled start working set; it is not an exact retained object size for that stage.",
            "Nested stage times overlap with their parent stage. Do not add nested rows to compute total runtime.",
        ]
    )
    return lines


def _stage_header() -> str:
    return (
        f"{'Stage':<46} {'Time':>10} {'Start RSS':>12} {'End RSS':>12} "
        f"{'Delta RSS':>12} {'Peak RSS':>12}"
    )


def _stage_line(event: RuntimeMetricEvent) -> str:
    indent = "  " * event.depth
    name = f"{indent}{event.operation}"
    if event.failed:
        name = f"{name} failed"
    return (
        f"{_truncate(name, 46):<46} "
        f"{event.elapsed_seconds:>9.3f}s "
        f"{format_bytes(event.started_memory.working_set_bytes):>12} "
        f"{format_bytes(event.ended_memory.working_set_bytes):>12} "
        f"{format_signed_bytes(event.working_set_delta_bytes):>12} "
        f"{format_bytes(event.ended_memory.peak_working_set_bytes):>12}"
    )


def _slow_stage_header() -> str:
    return f"{'Stage':<46} {'Time':>10} {'Depth':>8} {'Delta RSS':>12}"


def _slow_stage_line(event: RuntimeMetricEvent) -> str:
    return (
        f"{_truncate(event.operation, 46):<46} "
        f"{event.elapsed_seconds:>9.3f}s "
        f"{event.depth:>8} "
        f"{format_signed_bytes(event.working_set_delta_bytes):>12}"
    )


def _memory_stage_header() -> str:
    return f"{'Stage':<46} {'Time':>10} {'Delta RSS':>12} {'End RSS':>12}"


def _memory_stage_line(event: RuntimeMetricEvent) -> str:
    return (
        f"{_truncate(event.operation, 46):<46} "
        f"{event.elapsed_seconds:>9.3f}s "
        f"{format_signed_bytes(event.working_set_delta_bytes):>12} "
        f"{format_bytes(event.ended_memory.working_set_bytes):>12}"
    )


def _largest_memory_delta_events(
    events: list[RuntimeMetricEvent],
) -> list[RuntimeMetricEvent]:
    return sorted(
        [event for event in events if event.working_set_delta_bytes is not None],
        key=lambda event: abs(event.working_set_delta_bytes or 0),
        reverse=True,
    )


def _memory_delta(start: int | None, end: int | None) -> int | None:
    if start is None or end is None:
        return None
    return end - start


def _truncate(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    return value[: max(width - 3, 0)] + "..."
