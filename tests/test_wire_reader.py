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

    def test_read_object_empty_data_produces_raw(self):
        """Test that unreadable data produces _raw_hex."""
        # Data that can't be parsed as fields (no valid field name prefix)
        data = bytes([0x01, 0x02, 0x03, 0x04])
        reader = WireReader(data)
        obj = reader.read_object()

        assert "_raw_hex" in obj
        assert "_raw_length" in obj
        assert obj["_raw_length"] == 4


class TestWireReaderMessage:
    """Test reading complete messages."""

    def test_read_message_simple(self):
        """Test reading a message without type prefix."""
        data = bytes([0xC4]) + b"name" + bytes([0xE4]) + b"John"
        reader = WireReader(data)
        msg = reader.read_message()

        assert msg is not None
        assert msg.type_hint is None
        assert "name" in msg.fields
        assert msg.fields["name"] == "John"

    def test_read_message_with_type_prefix(self):
        """Test reading a message with type prefix."""
        type_name = b"!types.Order"
        # TYPE_PREFIX (0xB6) + stop-bit length + type string + field data
        data = (
            bytes([WireType.TYPE_PREFIX, len(type_name)]) + type_name
            + bytes([0xC2]) + b"id" + bytes([WireType.INT32]) + struct.pack("<i", 42)
        )
        reader = WireReader(data)
        msg = reader.read_message()

        assert msg is not None
        assert msg.type_hint == "!types.Order"

    def test_read_message_empty(self):
        """Test reading message from empty data."""
        reader = WireReader(b"")
        msg = reader.read_message()
        assert msg is None

    def test_read_message_raw_offset_and_size(self):
        """Test that message tracks raw offset and size."""
        data = bytes([0xC3]) + b"val" + bytes([WireType.INT32]) + struct.pack("<i", 1)
        reader = WireReader(data)
        msg = reader.read_message()

        assert msg is not None
        assert msg.raw_offset == 0
        assert msg.raw_size == len(data)


class TestWireReaderAdditionalValues:
    """Test reading additional value types."""

    def test_read_uint8_value(self):
        """Test reading UINT8 value."""
        data = bytes([WireType.UINT8, 0xFF])
        reader = WireReader(data)
        assert reader.read_value() == 255

    def test_read_uint16_value(self):
        """Test reading UINT16 value."""
        data = bytes([WireType.UINT16]) + struct.pack("<H", 65535)
        reader = WireReader(data)
        assert reader.read_value() == 65535

    def test_read_int8_value(self):
        """Test reading INT8 value."""
        data = bytes([WireType.INT8, 0xFF])  # -1 signed
        reader = WireReader(data)
        assert reader.read_value() == -1

    def test_read_int16_value(self):
        """Test reading INT16 value."""
        data = bytes([WireType.INT16]) + struct.pack("<h", -100)
        reader = WireReader(data)
        assert reader.read_value() == -100

    def test_read_float64_value(self):
        """Test reading FLOAT64 value."""
        data = bytes([WireType.FLOAT64]) + struct.pack("<d", 2.71828)
        reader = WireReader(data)
        assert abs(reader.read_value() - 2.71828) < 0.00001

    def test_read_nested_block(self):
        """Test reading NESTED_BLOCK value."""
        # Nested block: field "x" = 42
        nested_content = bytes([0xC1]) + b"x" + bytes([WireType.INT32]) + struct.pack("<i", 42)
        data = bytes([WireType.NESTED_BLOCK, len(nested_content)]) + nested_content
        reader = WireReader(data)
        result = reader.read_value()

        assert isinstance(result, dict)
        assert result["x"] == 42

    def test_read_bytes_length32(self):
        """Test reading BYTES_LENGTH32 value."""
        payload = b"\xDE\xAD\xBE\xEF"
        data = bytes([WireType.BYTES_LENGTH32]) + struct.pack("<i", len(payload)) + payload
        reader = WireReader(data)
        result = reader.read_value()
        assert result == payload

    def test_read_unknown_type(self):
        """Test reading unknown type code."""
        # 0xAA is not a defined WireType
        data = bytes([0xAA])
        reader = WireReader(data)
        result = reader.read_value()
        assert "<unknown:" in str(result)

    def test_read_value_at_end(self):
        """Test reading value when no data remains."""
        reader = WireReader(b"")
        assert reader.read_value() is None

    def test_skip(self):
        """Test skipping bytes."""
        reader = WireReader(bytes([1, 2, 3, 4, 5]))
        reader.skip(3)
        assert reader.remaining == 2
        assert reader.read_byte() == 4
