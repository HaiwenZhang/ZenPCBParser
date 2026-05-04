from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

from aurora_translator.shared.logging import log_kv, log_timing
from aurora_translator.targets.auroradb.writer import write_auroradb

from .commands import AAFCommand
from .executor import AAFExecutionResult, AAFToAuroraExecutor, execute_aaf_commands
from .parser import (
    parse_command_file,
    parse_command_lines,
    parse_exported_command_line,
    parse_exported_command_lines,
)


logger = logging.getLogger("aurora_translator.targets.auroradb")


def translate_aaf_to_auroradb(
    *,
    layout: str | Path | None = None,
    part: str | Path | None = None,
    output: str | Path | None = None,
) -> AAFExecutionResult:
    commands: list[AAFCommand] = []
    diagnostics: list[str] = []
    log_kv(
        logger,
        "AAF translator settings",
        level=logging.DEBUG,
        layout=Path(layout).expanduser().resolve() if layout is not None else None,
        part=Path(part).expanduser().resolve() if part is not None else None,
        output=Path(output).expanduser().resolve() if output is not None else None,
    )

    if part is not None:
        part_file = parse_command_file(part)
        commands.extend(part_file.commands)
        diagnostics.extend(part_file.diagnostics)
    if layout is not None:
        layout_file = parse_command_file(layout)
        commands.extend(layout_file.commands)
        diagnostics.extend(layout_file.diagnostics)

    return _translate_commands_to_auroradb(commands, diagnostics, output=output)


def translate_aaf_text_to_auroradb(
    *,
    layout_text: str | None = None,
    part_text: str | None = None,
    output: str | Path | None = None,
) -> AAFExecutionResult:
    return translate_aaf_lines_to_auroradb(
        layout_lines=layout_text.splitlines() if layout_text is not None else None,
        part_lines=part_text.splitlines() if part_text is not None else None,
        output=output,
    )


def translate_aaf_lines_to_auroradb(
    *,
    layout_lines: Iterable[str] | None = None,
    part_lines: Iterable[str] | None = None,
    output: str | Path | None = None,
) -> AAFExecutionResult:
    commands: list[AAFCommand] = []
    diagnostics: list[str] = []
    log_kv(
        logger,
        "AAF line translator settings",
        level=logging.DEBUG,
        has_layout=layout_lines is not None,
        has_part=part_lines is not None,
        output=Path(output).expanduser().resolve() if output is not None else None,
    )

    if part_lines is not None:
        part_file = parse_command_lines(part_lines, source="memory_design.part")
        commands.extend(part_file.commands)
        diagnostics.extend(part_file.diagnostics)
    if layout_lines is not None:
        layout_file = parse_command_lines(layout_lines, source="memory_design.layout")
        commands.extend(layout_file.commands)
        diagnostics.extend(layout_file.diagnostics)

    return _translate_commands_to_auroradb(commands, diagnostics, output=output)


def translate_exported_aaf_lines_to_auroradb(
    *,
    layout_lines: Iterable[str] | None = None,
    part_lines: Iterable[str] | None = None,
    output: str | Path | None = None,
) -> AAFExecutionResult:
    commands: list[AAFCommand] = []
    diagnostics: list[str] = []
    log_kv(
        logger,
        "Exported AAF line translator settings",
        level=logging.DEBUG,
        has_layout=layout_lines is not None,
        has_part=part_lines is not None,
        output=Path(output).expanduser().resolve() if output is not None else None,
    )

    if part_lines is not None:
        part_file = parse_exported_command_lines(
            part_lines, source="memory_design.part"
        )
        commands.extend(part_file.commands)
        diagnostics.extend(part_file.diagnostics)
    if layout_lines is not None:
        layout_file = parse_exported_command_lines(
            layout_lines, source="memory_design.layout"
        )
        commands.extend(layout_file.commands)
        diagnostics.extend(layout_file.diagnostics)

    return _translate_commands_to_auroradb(commands, diagnostics, output=output)


def translate_exported_aaf_lines_stream_to_auroradb(
    *,
    layout_lines: Iterable[str] | None = None,
    part_lines: Iterable[str] | None = None,
    output: str | Path | None = None,
) -> AAFExecutionResult:
    diagnostics: list[str] = []
    executor = AAFToAuroraExecutor()
    log_kv(
        logger,
        "Exported AAF stream translator settings",
        level=logging.DEBUG,
        has_layout=layout_lines is not None,
        has_part=part_lines is not None,
        output=Path(output).expanduser().resolve() if output is not None else None,
    )

    with log_timing(
        logger,
        "execute exported AAF command stream",
        output=output,
        level=logging.DEBUG,
    ):
        if part_lines is not None:
            _execute_exported_command_lines(
                executor,
                part_lines,
                source="memory_design.part",
                diagnostics=diagnostics,
            )
        if layout_lines is not None:
            _execute_exported_command_lines(
                executor,
                layout_lines,
                source="memory_design.layout",
                diagnostics=diagnostics,
            )

    result = executor.result()
    result.diagnostics[:0] = diagnostics
    result.package.diagnostics[:0] = diagnostics

    if output is not None:
        with log_timing(
            logger,
            "write compiled AuroraDB package",
            output=Path(output).expanduser().resolve(),
            level=logging.DEBUG,
        ):
            write_auroradb(result.package, output)
    logger.debug(
        "Translated exported AAF stream to AuroraDB with supported:%s unsupported:%s diagnostics:%s",
        result.supported_commands,
        result.unsupported_commands,
        len(result.diagnostics),
    )
    return result


def _translate_commands_to_auroradb(
    commands: list[AAFCommand],
    diagnostics: list[str],
    *,
    output: str | Path | None = None,
) -> AAFExecutionResult:
    with log_timing(
        logger,
        "execute AAF commands",
        command_count=len(commands),
        output=output,
        level=logging.DEBUG,
    ):
        result = execute_aaf_commands(commands, root=output)
    result.diagnostics[:0] = diagnostics
    result.package.diagnostics[:0] = diagnostics

    if output is not None:
        with log_timing(
            logger,
            "write compiled AuroraDB package",
            output=Path(output).expanduser().resolve(),
            level=logging.DEBUG,
        ):
            write_auroradb(result.package, output)
    logger.debug(
        "Translated AAF to AuroraDB with supported:%s unsupported:%s diagnostics:%s",
        result.supported_commands,
        result.unsupported_commands,
        len(result.diagnostics),
    )
    return result


def _execute_exported_command_lines(
    executor: AAFToAuroraExecutor,
    lines: Iterable[str],
    *,
    source: str,
    diagnostics: list[str],
) -> None:
    source_path = Path(source)
    for line_no, raw in enumerate(lines, start=1):
        try:
            command = parse_exported_command_line(
                raw, line_no=line_no, source=source_path
            )
        except ValueError as exc:
            diagnostics.append(f"{source}:{line_no}: {exc}")
            continue
        if command is not None:
            executor.execute(command)
