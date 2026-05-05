from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Iterator, Literal, TextIO


NodeKind = Literal["block", "item"]


class AuroraBlockError(ValueError):
    """Raised when an AuroraDB block file cannot be parsed."""


@dataclass(slots=True)
class AuroraItem:
    name: str
    values: list[str] = field(default_factory=list)

    @property
    def kind(self) -> NodeKind:
        return "item"

    def to_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "name": self.name, "values": list(self.values)}


@dataclass(slots=True)
class AuroraBlock:
    name: str
    children: list["AuroraNode"] = field(default_factory=list)

    @property
    def kind(self) -> NodeKind:
        return "block"

    def add_item(
        self,
        name: str,
        values: str | int | float | bool | Iterable[object] | None = None,
    ) -> AuroraItem:
        if values is None:
            item_values: list[str] = []
        elif isinstance(values, bool):
            item_values = [_bool_to_text(values)]
        elif isinstance(values, (str, int, float)):
            item_values = [_value_to_text(values)]
        else:
            item_values = [_value_to_text(value) for value in values]
        item = AuroraItem(name, item_values)
        self.children.append(item)
        return item

    def add_block(self, name: str) -> "AuroraBlock":
        block = AuroraBlock(name)
        self.children.append(block)
        return block

    def append(self, node: "AuroraNode") -> "AuroraNode":
        self.children.append(node)
        return node

    def get_first(self, name: str) -> "AuroraNode | None":
        lowered = name.casefold()
        for child in self.children:
            if child.name.casefold() == lowered:
                return child
        return None

    def get_item(self, name: str) -> AuroraItem | None:
        node = self.get_first(name)
        return node if isinstance(node, AuroraItem) else None

    def get_block(self, name: str) -> "AuroraBlock | None":
        node = self.get_first(name)
        return node if isinstance(node, AuroraBlock) else None

    def get_items(self, name: str) -> list[AuroraItem]:
        lowered = name.casefold()
        return [
            child
            for child in self.children
            if isinstance(child, AuroraItem) and child.name.casefold() == lowered
        ]

    def get_blocks(self, name: str) -> list["AuroraBlock"]:
        lowered = name.casefold()
        return [
            child
            for child in self.children
            if isinstance(child, AuroraBlock) and child.name.casefold() == lowered
        ]

    def iter_items(self) -> Iterator[AuroraItem]:
        for child in self.children:
            if isinstance(child, AuroraItem):
                yield child

    def iter_blocks(self) -> Iterator["AuroraBlock"]:
        for child in self.children:
            if isinstance(child, AuroraBlock):
                yield child

    def replace_item(
        self, name: str, values: Iterable[object] | object | None
    ) -> AuroraItem:
        lowered = name.casefold()
        self.children = [
            child
            for child in self.children
            if not (isinstance(child, AuroraItem) and child.name.casefold() == lowered)
        ]
        return self.add_item(name, values)

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "name": self.name,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass(slots=True, init=False)
class AuroraRawBlock(AuroraBlock):
    """Block backed by preformatted AuroraDB lines.

    Large generated geometry blocks can contain hundreds of thousands of small
    items. Keeping them as raw lines avoids building equivalent Python object
    trees while still allowing lazy parsing for callers that inspect the block.
    """

    raw_lines: list[str]
    _parsed: AuroraBlock | None

    def __init__(self, name: str, raw_lines: Iterable[str]) -> None:
        AuroraBlock.__init__(self, name=name)
        self.raw_lines = list(raw_lines)
        self._parsed = None

    def _parsed_block(self) -> AuroraBlock:
        parsed = self._parsed
        if parsed is None:
            parsed = parse_block_text(
                "\n".join(self.raw_lines) + "\n", root_name=self.name
            )
            self._parsed = parsed
        return parsed

    def parsed_block(self) -> AuroraBlock:
        return self._parsed_block()

    def get_first(self, name: str) -> "AuroraNode | None":
        return self._parsed_block().get_first(name)

    def get_item(self, name: str) -> AuroraItem | None:
        return self._parsed_block().get_item(name)

    def get_block(self, name: str) -> AuroraBlock | None:
        return self._parsed_block().get_block(name)

    def get_items(self, name: str) -> list[AuroraItem]:
        return self._parsed_block().get_items(name)

    def get_blocks(self, name: str) -> list[AuroraBlock]:
        return self._parsed_block().get_blocks(name)

    def iter_items(self) -> Iterator[AuroraItem]:
        return self._parsed_block().iter_items()

    def iter_blocks(self) -> Iterator[AuroraBlock]:
        return self._parsed_block().iter_blocks()

    def to_dict(self) -> dict[str, object]:
        return self._parsed_block().to_dict()


AuroraNode = AuroraBlock | AuroraItem | AuroraRawBlock


def read_block_file(path: str | Path, root_name: str | None = None) -> AuroraBlock:
    """Read one AuroraDB block file.

    The parser mirrors ASIV's CeIODataBlock rules: block item lines are split
    on spaces while preserving quoted text plus parenthesized and bracketed
    expressions. Lines starting with # are comments.
    """

    file_path = Path(path).expanduser()
    text = file_path.read_text(encoding="utf-8-sig")
    return parse_block_text(text, root_name=root_name, source=str(file_path))


def write_block_file(block: AuroraBlock, path: str | Path) -> Path:
    file_path = Path(path).expanduser()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8", newline="\n") as handle:
        buffer: list[str] = []
        _write_block_stream(handle, block, 0, buffer)
        if buffer:
            handle.writelines(buffer)
    return file_path


def parse_block_text(
    text: str, root_name: str | None = None, source: str = "<string>"
) -> AuroraBlock:
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = _clean_line(lines[index])
        index += 1
        if not line:
            continue
        block_name = _find_block_start(line)
        if not block_name:
            continue
        if root_name is None or block_name.casefold() == root_name.casefold():
            block, index = _parse_block_body(block_name, lines, index, source)
            return block
    expected = f" named {root_name!r}" if root_name else ""
    raise AuroraBlockError(f"No AuroraDB root block{expected} found in {source}.")


def format_block(block: AuroraBlock, indent: int = 0) -> str:
    lines: list[str] = []
    _write_block(lines, block, indent)
    return "\n".join(lines) + "\n"


def split_reserved(
    text: str,
    delimiters: str = " ",
    reserve_pairs: tuple[tuple[str, str], ...] = (("(", ")"), ("[", "]"), ('"', '"')),
) -> list[str]:
    """Split text with ASIV-style reserved pairs.

    Delimiter characters are dropped unless they appear inside one of the
    reserved pairs. Reserved-pair delimiters themselves are kept in the token,
    which matches ASIV command and block data behavior closely enough for
    round-tripping.
    """

    tokens: list[str] = []
    buf: list[str] = []
    stack: list[str] = []
    opener_to_closer = {opener: closer for opener, closer in reserve_pairs}
    closers = set(opener_to_closer.values())

    i = 0
    while i < len(text):
        char = text[i]
        if stack:
            if stack[-1] == '"' and char == "\\" and i + 1 < len(text):
                buf.append(char)
                i += 1
                buf.append(text[i])
                i += 1
                continue
            buf.append(char)
            if char == stack[-1]:
                stack.pop()
            elif stack[-1] != '"' and char in opener_to_closer:
                stack.append(opener_to_closer[char])
            i += 1
            continue

        if char in opener_to_closer:
            buf.append(char)
            stack.append(opener_to_closer[char])
        elif char in closers:
            buf.append(char)
        elif char in delimiters:
            if buf:
                tokens.append("".join(buf).strip())
                buf.clear()
        else:
            buf.append(char)
        i += 1

    if stack:
        raise AuroraBlockError(f"Unclosed reserved expression in: {text}")
    if buf:
        tokens.append("".join(buf).strip())
    return [token for token in tokens if token != ""]


def strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('\\"', '"')
    return value


def strip_wrapping_pair(value: str, opener: str, closer: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == opener and stripped[-1] == closer:
        return stripped[1:-1].strip()
    return stripped


def canonical_block_dict(block: AuroraBlock) -> dict[str, object]:
    return block.to_dict()


def _parse_block_body(
    name: str, lines: list[str], index: int, source: str
) -> tuple[AuroraBlock, int]:
    block = AuroraBlock(name)
    while index < len(lines):
        raw_line = lines[index]
        index += 1
        line = _clean_line(raw_line)
        if not line:
            continue
        if line == "}":
            return block, index
        child_name = _find_block_start(line)
        if child_name:
            child, index = _parse_block_body(child_name, lines, index, source)
            block.children.append(child)
            continue
        values = split_reserved(
            line, " ", reserve_pairs=(("(", ")"), ("[", "]"), ('"', '"'))
        )
        if values:
            block.children.append(
                AuroraItem(
                    strip_wrapping_quotes(values[0]),
                    [strip_wrapping_quotes(value) for value in values[1:]],
                )
            )
    raise AuroraBlockError(f"Block {name!r} was not closed in {source}.")


def _write_block(lines: list[str], block: AuroraBlock, indent: int) -> None:
    if isinstance(block, AuroraRawBlock):
        _write_raw_block_lines(lines, block, indent)
        return
    prefix = "\t" * indent
    lines.append(f"{prefix}{_format_name(block.name)} {{")
    for child in block.children:
        if isinstance(child, AuroraRawBlock):
            _write_raw_block_lines(lines, child, indent + 1)
        elif isinstance(child, AuroraBlock):
            _write_block(lines, child, indent + 1)
        else:
            value_text = " ".join(_format_value(value) for value in child.values)
            line = f"{prefix}\t{_format_name(child.name)}"
            if value_text:
                line += f" {value_text}"
            lines.append(line)
    lines.append(f"{prefix}}}")


def _write_block_stream(
    handle: TextIO, block: AuroraBlock, indent: int, buffer: list[str] | None = None
) -> None:
    if isinstance(block, AuroraRawBlock):
        _write_raw_block_stream(handle, block, indent, buffer)
        return
    prefix = "\t" * indent
    if buffer is None:
        handle.write(f"{prefix}{_format_name(block.name)} {{\n")
        for child in block.children:
            if isinstance(child, AuroraRawBlock):
                _write_raw_block_stream(handle, child, indent + 1)
            elif isinstance(child, AuroraBlock):
                _write_block_stream(handle, child, indent + 1)
            else:
                line = f"{prefix}\t{_format_name(child.name)}"
                if child.values:
                    line += (
                        f" {' '.join(_format_value(value) for value in child.values)}"
                    )
                handle.write(f"{line}\n")
        handle.write(f"{prefix}}}\n")
        return

    _buffered_write(handle, buffer, f"{prefix}{_format_name(block.name)} {{\n")
    for child in block.children:
        if isinstance(child, AuroraRawBlock):
            _write_raw_block_stream(handle, child, indent + 1, buffer)
        elif isinstance(child, AuroraBlock):
            _write_block_stream(handle, child, indent + 1, buffer)
        else:
            line = f"{prefix}\t{_format_name(child.name)}"
            if child.values:
                line += f" {' '.join(_format_value(value) for value in child.values)}"
            _buffered_write(handle, buffer, f"{line}\n")
    _buffered_write(handle, buffer, f"{prefix}}}\n")


def _write_raw_block_lines(
    lines: list[str], block: AuroraRawBlock, indent: int
) -> None:
    prefix = "\t" * indent
    lines.extend(f"{prefix}{line}" for line in block.raw_lines)


def _write_raw_block_stream(
    handle: TextIO,
    block: AuroraRawBlock,
    indent: int,
    buffer: list[str] | None = None,
) -> None:
    prefix = "\t" * indent
    if buffer is None:
        for line in block.raw_lines:
            handle.write(f"{prefix}{line}\n")
        return
    for line in block.raw_lines:
        _buffered_write(handle, buffer, f"{prefix}{line}\n")


def _buffered_write(handle: TextIO, buffer: list[str], text: str) -> None:
    buffer.append(text)
    if len(buffer) >= 8192:
        handle.writelines(buffer)
        buffer.clear()


def _clean_line(line: str) -> str:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return ""
    return stripped


def _find_block_start(line: str) -> str:
    if not line.endswith("{"):
        return ""
    name = line[:-1].strip()
    return strip_wrapping_quotes(name)


def _format_name(name: str) -> str:
    return _format_name_cached(name)


def _format_value(value: str) -> str:
    return _format_value_cached(value)


@lru_cache(maxsize=65536)
def _format_name_cached(name: str) -> str:
    if _needs_whitespace_quote(name):
        return f'"{name}"'
    return name


@lru_cache(maxsize=262144)
def _format_value_cached(value: str) -> str:
    if value == "":
        return '""'
    if _is_wrapped(value):
        return value
    if _needs_value_quote(value):
        return '"' + value.replace('"', '\\"') + '"'
    return value


def _needs_whitespace_quote(value: str) -> bool:
    for char in value:
        if char.isspace():
            return True
    return False


def _needs_value_quote(value: str) -> bool:
    for char in value:
        if char.isspace() or char in '<>{}()"':
            return True
    return False


def _is_wrapped(value: str) -> bool:
    return len(value) >= 2 and (
        (value[0] == '"' and value[-1] == '"')
        or (value[0] == "(" and value[-1] == ")")
        or (value[0] == "[" and value[-1] == "]")
    )


def _value_to_text(value: object) -> str:
    if isinstance(value, bool):
        return _bool_to_text(value)
    return str(value)


def _bool_to_text(value: bool) -> str:
    return "Y" if value else "N"
