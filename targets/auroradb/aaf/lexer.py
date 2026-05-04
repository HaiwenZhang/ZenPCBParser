from __future__ import annotations

from aurora_translator.sources.auroradb.block import split_reserved


def tokenize_command(line: str) -> list[str]:
    return split_reserved(
        line,
        delimiters=" ,<>",
        reserve_pairs=(("(", ")"), ("[", "]"), ("{", "}"), ('"', '"')),
    )


def is_option_token(token: str, raw_line: str) -> bool:
    if not token.startswith("-") or len(token) <= 1:
        return False
    if token[1].isdigit():
        return False
    if "," in token or " " in token:
        return False

    pos = raw_line.find(token)
    if pos > 0 and raw_line[pos - 1] in {"<", '"'}:
        return False
    return True
