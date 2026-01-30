"""Tests for wire reader."""

import pytest
import struct
from cqviewer.parser.wire_reader import WireReader, ParsedField
from cqviewer.parser.wire_types import WireType


class TestWireReaderBasics:
    """Test basic wire reader operations."""

    def test_read_byte(self):
        """Test reading a single byte."""
        reader = WireReader(bytes([0x42]))
        assert reader.read_byte() == 0x42
        assert reader.remaining == 0

    def test_read_bytes(self):
        """Test reading multiple bytes."""
        reader = WireReader(bytes([0x01, 0x02, 0x03, 0x04]))
        result = reader.read_bytes(3)
        assert result == bytes([0x01, 0x02, 0x03])
        assert reader.remaining == 1

    def test_peek_byte(self):
        """Test peeking without consuming."""
        reader = WireReader(bytes([0x42, 0x43]))
        assert reader.peek_byte() == 0x42
        assert reader.remaining == 2  # Not consumed

    def test_read_stop_bit(self):
        """Test reading stop-bit encoded value."""
        reader = WireReader(bytes([0x2A]))
        assert reader.read_stop_bit() == 42


class TestWireReaderIntegers:
    """Test reading integer types."""

    def test_read_int8(self):
        """Test reading signed 8-bit integer."""
        reader = WireReader(bytes([0x7F]))  # 127
        assert reader.read_int8() == 127

        reader = WireReader(bytes([0xFF]))  # -1
        assert reader.read_int8() == -1

    def test_read_uint8(self):
        """Test reading unsigned 8-bit integer."""
        reader = WireReader(bytes([0xFF]))
        assert reader.read_uint8() == 255

    def test_read_int16(self):
        """Test reading signed 16-bit integer."""
        data = struct.pack("<h", -12345)
        reader = WireReader(data)
        assert reader.read_int16() == -12345

    def test_read_int32(self):
        """Test reading signed 32-bit integer."""
        data = struct.pack("<i", 123456789)
        reader = WireReader(data)
        assert reader.read_int32() == 123456789

    def test_read_int64(self):
        """Test reading signed 64-bit integer."""
        data = struct.pack("<q", 9876543210)
        reader = WireReader(data)
        assert reader.read_int64() == 9876543210


class TestWireReaderFloats:
    """Test reading floating point types."""

    def test_read_float32(self):
        """Test reading 32-bit float."""
        data = struct.pack("<f", 3.14)
        reader = WireReader(data)
        assert abs(reader.read_float32() - 3.14) < 0.001

    def test_read_float64(self):
        """Test reading 64-bit float."""
        data = struct.pack("<d", 3.14159265359)
        reader = WireReader(data)
        assert abs(reader.read_float64() - 3.14159265359) < 0.0000001


class TestWireReaderStrings:
    """Test reading string types."""

    def test_read_string(self):
        """Test reading UTF-8 string."""
        data = b"Hello"
        reader = WireReader(data)
        assert reader.read_string(5) == "Hello"

    def test_read_compact_string(self):
        """Test reading compact string (0xE0-0xFF)."""
        # 0xE5 = compact string, length 5
        data = bytes([0xE5]) + b"Hello"
        reader = WireReader(data)
        assert reader.read_value() == "Hello"

    def test_read_empty_compact_string(self):
        """Test reading empty compact string."""
        data = bytes([0xE0])  # Length 0
        reader = WireReader(data)
        assert reader.read_value() == ""


class TestWireReaderFieldNames:
    """Test reading field names."""

    def test_read_compact_field_name(self):
        """Test reading compact field name (0xC0-0xDF)."""
        # 0xC4 = compact field name, length 4
        data = bytes([0xC4]) + b"name"
        reader = WireReader(data)
        assert reader.read_field_name() == "name"

    def test_read_empty_field_name(self):
        """Test reading empty field name."""
        data = bytes([0xC0])  # Length 0
        reader = WireReader(data)
        assert reader.read_field_name() == ""

    def test_read_field_name_any(self):
        """Test reading FIELD_NAME_ANY type."""
        # 0xB7 = FIELD_NAME_ANY, followed by stop-bit length, then string
        data = bytes([0xB7, 0x05]) + b"field"
        reader = WireReader(data)
        assert reader.read_field_name() == "field"


class TestWireReaderValues:
    """Test reading various value types."""

    def test_read_null(self):
        """Test reading NULL value."""
        data = bytes([WireType.NULL])
        reader = WireReader(data)
        assert reader.read_value() is None

    def test_read_int32_value(self):
        """Test reading INT32 value."""
        data = bytes([WireType.INT32]) + struct.pack("<i", 42)
        reader = WireReader(data)
        assert reader.read_value() == 42

    def test_read_int64_value(self):
        """Test reading INT64 value."""
        data = bytes([WireType.INT64]) + struct.pack("<q", 123456789012)
        reader = WireReader(data)
        assert reader.read_value() == 123456789012

    def test_read_float32_value(self):
        """Test reading FLOAT32 value."""
        data = bytes([WireType.FLOAT32]) + struct.pack("<f", 1.5)
        reader = WireReader(data)
        assert abs(reader.read_value() - 1.5) < 0.001

    def test_read_string_any_value(self):
        """Test reading STRING_ANY value."""
        # 0xB8 = STRING_ANY, followed by stop-bit length, then string
        data = bytes([0xB8, 0x05]) + b"hello"
        reader = WireReader(data)
        assert reader.read_value() == "hello"


class TestWireReaderField:
    """Test reading complete fields."""

    def test_read_field_with_string(self):
        """Test reading field with string value."""
        # Compact field name "name" + compact string "John"
        data = bytes([0xC4]) + b"name" + bytes([0xE4]) + b"John"
        reader = WireReader(data)
        field = reader.read_field()

        assert field is not None
        assert field.name == "name"
        assert field.value == "John"

    def test_read_field_with_int(self):
        """Test reading field with integer value."""
        # Compact field name "age" + INT32 25
        data = bytes([0xC3]) + b"age" + bytes([WireType.INT32]) + struct.pack("<i", 25)
        reader = WireReader(data)
        field = reader.read_field()

        assert field is not None
        assert field.name == "age"
        assert field.value == 25


class TestWireReaderObject:
    """Test reading complete objects."""

    def test_read_simple_object(self):
        """Test reading object with multiple fields."""
        # Two fields: name="John", age=25
        data = (
            bytes([0xC4]) + b"name" + bytes([0xE4]) + b"John"
            + bytes([0xC3]) + b"age" + bytes([WireType.INT32]) + struct.pack("<i", 25)
        )
        reader = WireReader(data)
        obj = reader.read_object()

        assert "name" in obj
        assert obj["name"] == "John"
        assert "age" in obj
        assert obj["age"] == 25

    def test_read_object_with_null(self):
        """Test reading object with null field."""
        data = bytes([0xC5]) + b"value" + bytes([WireType.NULL])
        reader = WireReader(data)
        obj = reader.read_object()

        assert "value" in obj
        assert obj["value"] is None
