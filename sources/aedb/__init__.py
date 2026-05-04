from .errors import AEDBParserError
from .models import AEDBLayout
from .version import AEDB_JSON_SCHEMA_VERSION, AEDB_PARSER_VERSION


def parse_aedb(*args, **kwargs):
    from .parser import parse_aedb as _parse_aedb

    return _parse_aedb(*args, **kwargs)


__all__ = [
    "AEDBLayout",
    "AEDBParserError",
    "AEDB_JSON_SCHEMA_VERSION",
    "AEDB_PARSER_VERSION",
    "parse_aedb",
]
