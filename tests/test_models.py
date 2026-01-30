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
