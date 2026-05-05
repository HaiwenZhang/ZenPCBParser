from aurora_translator.sources.auroradb.block import parse_block_text, split_reserved


def test_split_reserved_preserves_parentheses_inside_quoted_pair_value() -> None:
    values = split_reserved(
        'Attributes (COMPONENT_COUNT,16) (PART_NAME,"DDR5_FEMALE_(S1+S")',
        " ",
        reserve_pairs=(("(", ")"), ("[", "]"), ('"', '"')),
    )

    assert values == [
        "Attributes",
        "(COMPONENT_COUNT,16)",
        '(PART_NAME,"DDR5_FEMALE_(S1+S")',
    ]


def test_parse_block_text_allows_parentheses_inside_quoted_attribute_value() -> None:
    block = parse_block_text(
        """
CeParts {
    Parts {
        Part {
            Info {
                Attributes (COMPONENT_COUNT,16) (PART_NAME,"DDR5_FEMALE_(S1+S")
            }
        }
    }
}
""",
        root_name="CeParts",
    )

    parts = block.get_block("Parts")
    assert parts is not None
    part = parts.get_block("Part")
    assert part is not None
    info = part.get_block("Info")
    assert info is not None
    attributes = info.get_item("Attributes")
    assert attributes is not None
    assert attributes.values == [
        "(COMPONENT_COUNT,16)",
        '(PART_NAME,"DDR5_FEMALE_(S1+S")',
    ]
