"""Tests for data models."""

import pytest
from cqviewer.models.field import Field, FieldType
from cqviewer.models.message import Message
from cqviewer.models.queue_info import QueueInfo
from pathlib import Path


class TestField:
    """Tests for Field model."""

    def test_from_value_string(self):
        """Test creating field from string value."""
        field = Field.from_value("name", "John")
        assert field.name == "name"
        assert field.value == "John"
        assert field.field_type == FieldType.STRING

    def test_from_value_integer(self):
        """Test creating field from integer value."""
        field = Field.from_value("count", 42)
        assert field.value == 42
        assert field.field_type == FieldType.INTEGER

    def test_from_value_float(self):
        """Test creating field from float value."""
        field = Field.from_value("price", 19.99)
        assert field.value == 19.99
        assert field.field_type == FieldType.FLOAT

    def test_from_value_boolean(self):
        """Test creating field from boolean value."""
        field = Field.from_value("active", True)
        assert field.value is True
        assert field.field_type == FieldType.BOOLEAN

    def test_from_value_null(self):
        """Test creating field from None value."""
        field = Field.from_value("empty", None)
        assert field.value is None
        assert field.field_type == FieldType.NULL

    def test_from_value_dict(self):
        """Test creating field from dict value."""
        field = Field.from_value("data", {"key": "value"})
        assert field.field_type == FieldType.OBJECT

    def test_from_value_list(self):
        """Test creating field from list value."""
        field = Field.from_value("items", [1, 2, 3])
        assert field.field_type == FieldType.ARRAY

    def test_from_value_bytes(self):
        """Test creating field from bytes value."""
        field = Field.from_value("raw", b"\x00\x01\x02")
        assert field.field_type == FieldType.BYTES

    def test_from_value_uuid(self):
        """Test creating field from UUID string."""
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        field = Field.from_value("id", uuid_str)
        assert field.field_type == FieldType.UUID

    def test_format_value_string(self):
        """Test formatting string value."""
        field = Field.from_value("name", "Hello")
        assert field.format_value() == "Hello"

    def test_format_value_null(self):
        """Test formatting null value."""
        field = Field.from_value("empty", None)
        assert field.format_value() == "<null>"

    def test_format_value_truncation(self):
        """Test value truncation for display."""
        long_string = "x" * 200
        field = Field.from_value("text", long_string)
        formatted = field.format_value(max_length=50)
        assert len(formatted) <= 53  # 50 + "..."
        assert formatted.endswith("...")

    def test_format_value_bytes(self):
        """Test formatting bytes value shows hex."""
        field = Field.from_value("raw", b"\xde\xad\xbe\xef")
        formatted = field.format_value()
        assert "<bytes:4>" in formatted
        assert "deadbeef" in formatted

    def test_format_value_bytes_truncation(self):
        """Test formatting long bytes value truncates hex."""
        field = Field.from_value("raw", b"\x00" * 100)
        formatted = field.format_value(max_length=10)
        assert formatted.endswith("...")
        assert "<bytes:100>" in formatted

    def test_format_value_object(self):
        """Test formatting dict value as JSON."""
        field = Field.from_value("data", {"key": "value"})
        formatted = field.format_value()
        assert "key" in formatted
        assert "value" in formatted

    def test_format_value_array(self):
        """Test formatting list value as JSON."""
        field = Field.from_value("items", [1, 2, 3])
        formatted = field.format_value()
        assert "[1, 2, 3]" in formatted

    def test_format_value_integer(self):
        """Test formatting integer value."""
        field = Field.from_value("count", 42)
        assert field.format_value() == "42"

    def test_from_value_tuple(self):
        """Test creating field from tuple value (treated as ARRAY)."""
        field = Field.from_value("coords", (1, 2))
        assert field.field_type == FieldType.ARRAY

    def test_from_value_unknown(self):
        """Test creating field from unknown type."""
        field = Field.from_value("obj", object())
        assert field.field_type == FieldType.UNKNOWN


class TestMessage:
    """Tests for Message model."""

    def test_from_parsed(self):
        """Test creating message from parsed data."""
        msg = Message.from_parsed(
            index=0,
            offset=100,
            type_hint="!types.Order",
            fields_dict={"customerId": "C123", "amount": 99.99},
        )

        assert msg.index == 0
        assert msg.offset == 100
        assert msg.type_hint == "!types.Order"
        assert len(msg.fields) == 2

    def test_get_field(self):
        """Test getting field by name."""
        msg = Message.from_parsed(
            index=0,
            offset=0,
            type_hint=None,
            fields_dict={"name": "John", "age": 30},
        )

        field = msg.get_field("name")
        assert field is not None
        assert field.value == "John"

        assert msg.get_field("missing") is None

    def test_get_field_nested(self):
        """Test getting nested field with dot notation."""
        msg = Message.from_parsed(
            index=0,
            offset=0,
            type_hint=None,
            fields_dict={"address": {"city": "NYC", "zip": "10001"}},
        )

        field = msg.get_field("address.city")
        assert field is not None
        assert field.value == "NYC"

    def test_has_field(self):
        """Test checking field existence."""
        msg = Message.from_parsed(
            index=0,
            offset=0,
            type_hint=None,
            fields_dict={"name": "John"},
        )

        assert msg.has_field("name")
        assert not msg.has_field("age")

    def test_field_names(self):
        """Test getting field names."""
        msg = Message.from_parsed(
            index=0,
            offset=0,
            type_hint=None,
            fields_dict={"name": "John", "age": 30},
        )

        names = msg.field_names()
        assert "name" in names
        assert "age" in names

    def test_field_names_nested(self):
        """Test getting nested field names."""
        msg = Message.from_parsed(
            index=0,
            offset=0,
            type_hint=None,
            fields_dict={"address": {"city": "NYC"}},
        )

        names = msg.field_names(include_nested=True)
        assert "address" in names
        assert "address.city" in names

    def test_flatten(self):
        """Test flattening message for export."""
        msg = Message.from_parsed(
            index=5,
            offset=1000,
            type_hint="!types.User",
            fields_dict={"name": "John", "address": {"city": "NYC"}},
        )

        flat = msg.flatten()
        assert flat["_index"] == 5
        assert flat["_offset"] == 1000
        assert flat["_type"] == "!types.User"
        assert flat["name"] == "John"
        assert flat["address.city"] == "NYC"

    def test_flatten_array(self):
        """Test flattening array field."""
        msg = Message.from_parsed(
            index=0,
            offset=0,
            type_hint=None,
            fields_dict={"tags": ["a", "b", "c"]},
        )

        flat = msg.flatten()
        assert flat["tags"] == "a, b, c"

    def test_matches_type(self):
        """Test type matching."""
        msg = Message.from_parsed(
            index=0,
            offset=0,
            type_hint="!types.Order",
            fields_dict={},
        )

        assert msg.matches_type("Order")
        assert msg.matches_type("order")  # Case insensitive
        assert not msg.matches_type("Customer")

    def test_matches_type_no_hint(self):
        """Test type matching with no type hint returns False."""
        msg = Message.from_parsed(index=0, offset=0, type_hint=None, fields_dict={})
        assert not msg.matches_type("Order")

    def test_from_parsed_skips_type_key(self):
        """Test that __type__ key is skipped during field creation."""
        msg = Message.from_parsed(
            index=0, offset=0, type_hint=None,
            fields_dict={"__type__": "Order", "name": "John"},
        )
        assert len(msg.fields) == 1
        assert "name" in msg.fields
        assert "__type__" not in msg.fields

    def test_from_parsed_is_metadata(self):
        """Test creating metadata message."""
        msg = Message.from_parsed(
            index=0, offset=0, type_hint=None,
            fields_dict={"data": "test"}, is_metadata=True,
        )
        assert msg.is_metadata is True

    def test_get_field_nested_non_object(self):
        """Test dot notation on non-object field returns None."""
        msg = Message.from_parsed(
            index=0, offset=0, type_hint=None,
            fields_dict={"name": "John"},
        )
        assert msg.get_field("name.first") is None

    def test_get_field_nested_missing_key(self):
        """Test dot notation with missing nested key returns None."""
        msg = Message.from_parsed(
            index=0, offset=0, type_hint=None,
            fields_dict={"address": {"city": "NYC"}},
        )
        assert msg.get_field("address.missing") is None

    def test_field_names_nested_skips_type(self):
        """Test nested field names skip __type__ keys."""
        msg = Message.from_parsed(
            index=0, offset=0, type_hint=None,
            fields_dict={"data": {"__type__": "Inner", "value": 1}},
        )
        names = msg.field_names(include_nested=True)
        assert "data.value" in names
        assert "data.__type__" not in names

    def test_flatten_no_type_hint(self):
        """Test flatten with no type hint gives empty string."""
        msg = Message.from_parsed(index=0, offset=0, type_hint=None, fields_dict={"x": 1})
        flat = msg.flatten()
        assert flat["_type"] == ""

    def test_flatten_null_value(self):
        """Test flatten preserves None values."""
        msg = Message.from_parsed(index=0, offset=0, type_hint=None, fields_dict={"x": None})
        flat = msg.flatten()
        assert flat["x"] is None

    def test_flatten_bytes_value(self):
        """Test flatten converts bytes to hex."""
        msg = Message.from_parsed(
            index=0, offset=0, type_hint=None, fields_dict={"raw": b"\xab\xcd"}
        )
        flat = msg.flatten()
        assert flat["raw"] == "abcd"

    def test_flatten_nested_with_type(self):
        """Test flatten includes __type__ from nested objects."""
        msg = Message.from_parsed(
            index=0, offset=0, type_hint=None,
            fields_dict={"nested": {"__type__": "Inner", "val": 1}},
        )
        flat = msg.flatten()
        assert flat["nested.__type__"] == "Inner"
        assert flat["nested.val"] == 1

    def test_str_representation(self):
        """Test Message __str__ output."""
        msg = Message.from_parsed(
            index=5, offset=0, type_hint="!types.Order",
            fields_dict={"a": 1, "b": 2},
        )
        s = str(msg)
        assert "5" in s
        assert "Order" in s
        assert "2 fields" in s

    def test_str_representation_no_type(self):
        """Test Message __str__ with no type hint."""
        msg = Message.from_parsed(index=0, offset=0, type_hint=None, fields_dict={})
        s = str(msg)
        assert "unknown" in s


class TestQueueInfo:
    """Tests for QueueInfo model."""

    def test_file_size_str_bytes(self):
        """Test file size formatting for bytes."""
        info = QueueInfo(filepath=Path("test.cq4"), file_size=500, message_count=10)
        assert info.file_size_str == "500.0 B"

    def test_file_size_str_kb(self):
        """Test file size formatting for KB."""
        info = QueueInfo(filepath=Path("test.cq4"), file_size=2048, message_count=10)
        assert info.file_size_str == "2.0 KB"

    def test_file_size_str_mb(self):
        """Test file size formatting for MB."""
        info = QueueInfo(
            filepath=Path("test.cq4"), file_size=2 * 1024 * 1024, message_count=10
        )
        assert info.file_size_str == "2.0 MB"

    def test_filename(self):
        """Test extracting filename."""
        info = QueueInfo(
            filepath=Path("/data/queues/test.cq4"), file_size=100, message_count=5
        )
        assert info.filename == "test.cq4"

    def test_str_representation(self):
        """Test QueueInfo __str__ output."""
        info = QueueInfo(filepath=Path("test.cq4"), file_size=500, message_count=10)
        s = str(info)
        assert "test.cq4" in s
        assert "500.0 B" in s
        assert "10 messages" in s

    def test_file_size_str_gb(self):
        """Test file size formatting for GB."""
        info = QueueInfo(
            filepath=Path("test.cq4"), file_size=2 * 1024 ** 3, message_count=10
        )
        assert info.file_size_str == "2.0 GB"

    def test_default_values(self):
        """Test QueueInfo default values."""
        info = QueueInfo(filepath=Path("test.cq4"), file_size=0, message_count=0)
        assert info.version == 0
        assert info.roll_cycle == ""
        assert info.index_count == 0
        assert info.index_spacing == 0
