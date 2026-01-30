"""Tests for wire types."""

import pytest
from cqviewer.parser.wire_types import (
    WireType,
    is_compact_field_name,
    compact_field_name_length,
    is_compact_string,
    compact_string_length,
)


class TestWireTypeConstants:
    """Test wire type constant values."""

    def test_null(self):
        assert WireType.NULL == 0x80

    def test_integers(self):
        assert WireType.INT8 == 0xA1
        assert WireType.INT16 == 0xA2
        assert WireType.INT32 == 0xA4
        assert WireType.INT64 == 0xA8

    def test_floats(self):
        assert WireType.FLOAT32 == 0x90
        assert WireType.FLOAT64 == 0x91

    def test_type_prefix(self):
        assert WireType.TYPE_PREFIX == 0xB6

    def test_nested_block(self):
        assert WireType.NESTED_BLOCK == 0x82


class TestCompactFieldName:
    """Test compact field name helpers."""

    def test_is_compact_field_name_valid(self):
        """Test valid compact field name codes."""
        assert is_compact_field_name(0xC0)
        assert is_compact_field_name(0xCF)
        assert is_compact_field_name(0xDF)

    def test_is_compact_field_name_invalid(self):
        """Test invalid compact field name codes."""
        assert not is_compact_field_name(0xBF)
        assert not is_compact_field_name(0xE0)
        assert not is_compact_field_name(0x00)

    def test_compact_field_name_length(self):
        """Test extracting length from compact code."""
        assert compact_field_name_length(0xC0) == 0
        assert compact_field_name_length(0xC1) == 1
        assert compact_field_name_length(0xCA) == 10
        assert compact_field_name_length(0xDF) == 31


class TestCompactString:
    """Test compact string helpers."""

    def test_is_compact_string_valid(self):
        """Test valid compact string codes."""
        assert is_compact_string(0xE0)
        assert is_compact_string(0xEF)
        assert is_compact_string(0xFF)

    def test_is_compact_string_invalid(self):
        """Test invalid compact string codes."""
        assert not is_compact_string(0xDF)
        assert not is_compact_string(0xC0)
        assert not is_compact_string(0x00)

    def test_compact_string_length(self):
        """Test extracting length from compact code."""
        assert compact_string_length(0xE0) == 0
        assert compact_string_length(0xE1) == 1
        assert compact_string_length(0xEA) == 10
        assert compact_string_length(0xFF) == 31
