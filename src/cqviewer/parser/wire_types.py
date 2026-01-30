"""Chronicle Wire binary format type codes.

Based on Chronicle Wire Binary Format specification.
"""

from enum import IntEnum


class WireType(IntEnum):
    """Wire format type codes for Chronicle Queue binary encoding."""

    # Special values
    PADDING = 0x00
    NULL = 0x80
    BYTES_LENGTH32 = 0x81
    NESTED_BLOCK = 0x82
    I64_ARRAY = 0x83
    U8_ARRAY = 0x84
    I8_ARRAY = 0x85
    PADDING32 = 0x8E
    PADDING_END = 0x8F

    # Floating point
    FLOAT32 = 0x90
    FLOAT64 = 0x91
    FLOAT_STOP2 = 0x92
    FLOAT_STOP4 = 0x94
    FLOAT_STOP6 = 0x96
    FLOAT_SET_LOW0 = 0x9A
    FLOAT_SET_LOW2 = 0x9C
    FLOAT_SET_LOW4 = 0x9E

    # Fixed-width integers
    INT8 = 0xA1
    INT16 = 0xA2
    INT32 = 0xA4
    INT64 = 0xA8
    UINT8 = 0xA5
    UINT16 = 0xA6

    # Timestamps and UUIDs
    TIMESTAMP = 0xB0
    DATE_TIME = 0xB1
    ZONED_DATE_TIME = 0xB2
    DATE = 0xB3
    TIME = 0xB4
    UUID = 0xB5

    # Type prefix and string types
    TYPE_PREFIX = 0xB6  # !types.ClassName
    FIELD_NAME_ANY = 0xB7
    STRING_ANY = 0xB8
    FIELD_NUMBER = 0xB9
    FIELD_NAME_LITERAL = 0xBA
    EVENT_NAME = 0xBB
    FIELD_ANCHOR = 0xBC
    ANCHOR = 0xBD
    UPDATE_ALIAS = 0xBE
    COMMENT = 0xBF

    # Compact field names (0xC0-0xDF)
    # Actual field name is encoded in lower 5 bits as length
    FIELD_NAME_0 = 0xC0  # Empty field name (length 0)

    # Compact strings (0xE0-0xFF)
    # String length is encoded in lower 5 bits
    STRING_0 = 0xE0  # Empty string (length 0)


# Ranges for compact encodings
COMPACT_FIELD_NAME_MIN = 0xC0
COMPACT_FIELD_NAME_MAX = 0xDF
COMPACT_STRING_MIN = 0xE0
COMPACT_STRING_MAX = 0xFF


def is_compact_field_name(code: int) -> bool:
    """Check if type code is a compact field name (0xC0-0xDF)."""
    return COMPACT_FIELD_NAME_MIN <= code <= COMPACT_FIELD_NAME_MAX


def compact_field_name_length(code: int) -> int:
    """Get field name length from compact field name code."""
    return code - COMPACT_FIELD_NAME_MIN


def is_compact_string(code: int) -> bool:
    """Check if type code is a compact string (0xE0-0xFF)."""
    return COMPACT_STRING_MIN <= code <= COMPACT_STRING_MAX


def compact_string_length(code: int) -> int:
    """Get string length from compact string code."""
    return code - COMPACT_STRING_MIN
