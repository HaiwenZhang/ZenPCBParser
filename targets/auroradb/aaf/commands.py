from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class CommandOption:
    name: str
    values: list[str] = field(default_factory=list)
    _name_key: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._name_key = self.name.casefold()

    def is_option(self, name: str) -> bool:
        return self._name_key == name.casefold()


@dataclass(slots=True)
class AAFCommand:
    words: list[str]
    options: list[CommandOption]
    raw: str
    line_no: int
    source: Path | None = None
    _word_keys: tuple[str, ...] = field(init=False, repr=False)
    _option_cache: dict[str, list[str]] | None = field(
        default=None, init=False, repr=False
    )
    _first_option_cache: dict[str, CommandOption] | None = field(
        default=None, init=False, repr=False
    )
    _option_string_cache: dict[str, str] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        self._word_keys = tuple(word.casefold() for word in self.words)

    def is_cmd(self, *words: str) -> bool:
        if len(self._word_keys) < len(words):
            return False
        return all(
            left == right.casefold() for left, right in zip(self._word_keys, words)
        )

    def has_option(self, name: str) -> bool:
        return name.casefold() in self._options_by_key()

    def option(self, name: str) -> CommandOption | None:
        return self._first_options_by_key().get(name.casefold())

    def option_values(self, name: str) -> list[str]:
        return self._options_by_key().get(name.casefold(), [])

    def option_string(self, name: str) -> str:
        key = name.casefold()
        if key not in self._option_string_cache:
            values = self.option_values(name)
            self._option_string_cache[key] = " ".join(values) if values else ""
        return self._option_string_cache[key]

    @property
    def first_option(self) -> CommandOption | None:
        return self.options[0] if self.options else None

    @property
    def last_option(self) -> CommandOption | None:
        return self.options[-1] if self.options else None

    def location_label(self) -> str:
        if self.source:
            return f"{self.source}:{self.line_no}"
        return f"line {self.line_no}"

    def _options_by_key(self) -> dict[str, list[str]]:
        if self._option_cache is None:
            cache: dict[str, list[str]] = {}
            for option in self.options:
                cache.setdefault(option._name_key, []).extend(option.values)
            self._option_cache = cache
        return self._option_cache

    def _first_options_by_key(self) -> dict[str, CommandOption]:
        if self._first_option_cache is None:
            cache: dict[str, CommandOption] = {}
            for option in self.options:
                cache.setdefault(option._name_key, option)
            self._first_option_cache = cache
        return self._first_option_cache


@dataclass(slots=True)
class AAFCommandFile:
    path: Path
    commands: list[AAFCommand]
    diagnostics: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, object]:
        counts: dict[str, int] = {}
        for command in self.commands:
            key = (
                " ".join(command.words[:2])
                if len(command.words) >= 2
                else " ".join(command.words)
            )
            counts[key] = counts.get(key, 0) + 1
        return {
            "path": str(self.path),
            "command_count": len(self.commands),
            "command_counts": counts,
            "diagnostics": list(self.diagnostics),
        }
