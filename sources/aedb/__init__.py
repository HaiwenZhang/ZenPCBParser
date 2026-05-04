from .errors import AEDBParserError
from .def_models import AEDBDefBinaryLayout
from .models import AEDBLayout
from .version import (
    AEDB_DEF_BINARY_JSON_SCHEMA_VERSION,
    AEDB_DEF_BINARY_PARSER_VERSION,
    AEDB_JSON_SCHEMA_VERSION,
    AEDB_PARSER_VERSION,
)


def parse_aedb(*args, **kwargs):
    from .parser import parse_aedb as _parse_aedb

    return _parse_aedb(*args, **kwargs)


def parse_aedb_def_binary(*args, **kwargs):
    from .def_binary import parse_aedb_def_binary as _parse_aedb_def_binary

    return _parse_aedb_def_binary(*args, **kwargs)


__all__ = [
    "AEDBDefBinaryLayout",
    "AEDBLayout",
    "AEDB_DEF_BINARY_JSON_SCHEMA_VERSION",
    "AEDB_DEF_BINARY_PARSER_VERSION",
    "AEDBParserError",
    "AEDB_JSON_SCHEMA_VERSION",
    "AEDB_PARSER_VERSION",
    "parse_aedb",
    "parse_aedb_def_binary",
]
