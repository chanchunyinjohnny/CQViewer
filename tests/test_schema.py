"""Tests for schema module."""

import pytest
import struct
import json

from cqviewer.parser.schema import (
    Schema, MessageDef, FieldDef, BinaryDecoder, create_example_schema
)


class TestFieldDef:
    """Tests for FieldDef dataclass."""

    def test_basic_field(self):
        field = FieldDef(name="timestamp", type="int64")
        assert field.name == "timestamp"
        assert field.type == "int64"
        assert field.size == 0
        assert field.optional is False

    def test_optional_field(self):
        field = FieldDef(name="notes", type="string", optional=True)
        assert field.optional is True

    def test_padding_field(self):
        field = FieldDef(name="reserved", type="padding", size=4)
        assert field.size == 4


class TestMessageDef:
    """Tests for MessageDef dataclass."""

    def test_basic_message(self):
        fields = [
            FieldDef(name="id", type="int64"),
            FieldDef(name="name", type="string"),
        ]
        msg = MessageDef(name="Order", fields=fields)
        assert msg.name == "Order"
        assert len(msg.fields) == 2

    def test_empty_fields(self):
        msg = MessageDef(name="Empty")
        assert msg.fields == []


class TestSchema:
    """Tests for Schema class."""

    def test_from_dict_basic(self):
        data = {
            "messages": {
                "Order": {
                    "fields": [
                        {"name": "id", "type": "int64"},
                        {"name": "amount", "type": "float64"},
                    ]
                }
            }
        }
        schema = Schema.from_dict(data)
        assert "Order" in schema.messages
        assert len(schema.messages["Order"].fields) == 2

    def test_from_dict_with_default(self):
        data = {
            "messages": {
                "Tick": {"fields": [{"name": "price", "type": "float64"}]},
                "Trade": {"fields": [{"name": "qty", "type": "int32"}]},
            },
            "default": "Tick"
        }
        schema = Schema.from_dict(data)
        assert schema.default_message == "Tick"

    def test_from_json(self):
        json_str = '{"messages": {"Test": {"fields": [{"name": "val", "type": "int32"}]}}}'
        schema = Schema.from_json(json_str)
        assert "Test" in schema.messages

    def test_get_message_by_name(self):
        data = {
            "messages": {
                "Order": {"fields": [{"name": "id", "type": "int64"}]},
                "Trade": {"fields": [{"name": "qty", "type": "int32"}]},
            }
        }
        schema = Schema.from_dict(data)
        order = schema.get_message("Order")
        assert order is not None
        assert order.name == "Order"

    def test_get_message_default(self):
        data = {
            "messages": {
                "Tick": {"fields": [{"name": "price", "type": "float64"}]},
            },
            "default": "Tick"
        }
        schema = Schema.from_dict(data)
        msg = schema.get_message()  # No name, should return default
        assert msg is not None
        assert msg.name == "Tick"

    def test_get_message_single(self):
        data = {
            "messages": {
                "OnlyOne": {"fields": [{"name": "val", "type": "int32"}]},
            }
        }
        schema = Schema.from_dict(data)
        msg = schema.get_message()  # No name, no default, but only one message
        assert msg is not None
        assert msg.name == "OnlyOne"

    def test_get_message_not_found(self):
        data = {"messages": {}}
        schema = Schema.from_dict(data)
        assert schema.get_message("NonExistent") is None


class TestBinaryDecoder:
    """Tests for BinaryDecoder class."""

    @pytest.fixture
    def simple_schema(self):
        """Create a simple schema for testing."""
        return Schema.from_dict({
            "messages": {
                "Test": {
                    "fields": [
                        {"name": "int_val", "type": "int32"},
                        {"name": "float_val", "type": "float64"},
                    ]
                }
            },
            "default": "Test"
        })

    def test_decode_int32(self, simple_schema):
        decoder = BinaryDecoder(simple_schema)
        # Pack int32 + float64
        data = struct.pack("<i", 42) + struct.pack("<d", 3.14)
        result = decoder.decode(data)
        assert result["int_val"] == 42
        assert abs(result["float_val"] - 3.14) < 0.001

    def test_decode_all_int_types(self):
        schema = Schema.from_dict({
            "messages": {
                "Ints": {
                    "fields": [
                        {"name": "i8", "type": "int8"},
                        {"name": "u8", "type": "uint8"},
                        {"name": "i16", "type": "int16"},
                        {"name": "u16", "type": "uint16"},
                        {"name": "i32", "type": "int32"},
                        {"name": "u32", "type": "uint32"},
                        {"name": "i64", "type": "int64"},
                        {"name": "u64", "type": "uint64"},
                    ]
                }
            },
            "default": "Ints"
        })
        decoder = BinaryDecoder(schema)
        data = struct.pack("<bBhHiIqQ", -1, 255, -1000, 65000, -100000, 4000000000, -1, 18446744073709551615)
        result = decoder.decode(data)
        assert result["i8"] == -1
        assert result["u8"] == 255
        assert result["i16"] == -1000
        assert result["u16"] == 65000
        assert result["i32"] == -100000
        assert result["u32"] == 4000000000
        assert result["i64"] == -1
        assert result["u64"] == 18446744073709551615

    def test_decode_floats(self):
        schema = Schema.from_dict({
            "messages": {
                "Floats": {
                    "fields": [
                        {"name": "f32", "type": "float32"},
                        {"name": "f64", "type": "float64"},
                    ]
                }
            },
            "default": "Floats"
        })
        decoder = BinaryDecoder(schema)
        data = struct.pack("<fd", 1.5, 2.75)
        result = decoder.decode(data)
        assert abs(result["f32"] - 1.5) < 0.0001
        assert abs(result["f64"] - 2.75) < 0.0001

    def test_decode_bool(self):
        schema = Schema.from_dict({
            "messages": {
                "Bools": {
                    "fields": [
                        {"name": "flag1", "type": "bool"},
                        {"name": "flag2", "type": "bool"},
                    ]
                }
            },
            "default": "Bools"
        })
        decoder = BinaryDecoder(schema)
        data = struct.pack("<?", True) + struct.pack("<?", False)
        result = decoder.decode(data)
        assert result["flag1"] is True
        assert result["flag2"] is False

    def test_decode_string(self):
        schema = Schema.from_dict({
            "messages": {
                "Strings": {
                    "fields": [
                        {"name": "text", "type": "string"},
                    ]
                }
            },
            "default": "Strings"
        })
        decoder = BinaryDecoder(schema)
        text = "hello"
        # Length byte + string
        data = bytes([len(text)]) + text.encode("utf-8")
        result = decoder.decode(data)
        assert result["text"] == "hello"

    def test_decode_bytes(self):
        schema = Schema.from_dict({
            "messages": {
                "Binary": {
                    "fields": [
                        {"name": "data", "type": "bytes"},
                    ]
                }
            },
            "default": "Binary"
        })
        decoder = BinaryDecoder(schema)
        binary = bytes([0xDE, 0xAD, 0xBE, 0xEF])
        data = bytes([len(binary)]) + binary
        result = decoder.decode(data)
        assert result["data"] == "deadbeef"

    def test_decode_padding(self):
        schema = Schema.from_dict({
            "messages": {
                "Padded": {
                    "fields": [
                        {"name": "val1", "type": "int32"},
                        {"name": "_pad", "type": "padding", "size": 4},
                        {"name": "val2", "type": "int32"},
                    ]
                }
            },
            "default": "Padded"
        })
        decoder = BinaryDecoder(schema)
        data = struct.pack("<i", 100) + bytes(4) + struct.pack("<i", 200)
        result = decoder.decode(data)
        assert result["val1"] == 100
        assert result["val2"] == 200
        assert result["_pad"] is None

    def test_decode_no_matching_message(self):
        schema = Schema.from_dict({"messages": {}})
        decoder = BinaryDecoder(schema)
        data = bytes([1, 2, 3, 4])
        result = decoder.decode(data)
        assert "_error" in result
        assert "_raw_hex" in result

    def test_decode_remaining_bytes(self, simple_schema):
        decoder = BinaryDecoder(simple_schema)
        # More data than schema expects
        data = struct.pack("<i", 42) + struct.pack("<d", 3.14) + bytes([1, 2, 3])
        result = decoder.decode(data)
        assert result["int_val"] == 42
        assert "_remaining_bytes" in result
        assert result["_remaining_bytes"] == 3

    def test_decode_optional_field(self):
        schema = Schema.from_dict({
            "messages": {
                "Optional": {
                    "fields": [
                        {"name": "required", "type": "int32"},
                        {"name": "optional", "type": "int32", "optional": True},
                    ]
                }
            },
            "default": "Optional"
        })
        decoder = BinaryDecoder(schema)
        # Only enough data for required field
        data = struct.pack("<i", 42)
        result = decoder.decode(data)
        assert result["required"] == 42
        assert "optional" not in result  # Optional field not present

    def test_decode_nested_object(self):
        """Test decoding a message with nested object fields."""
        # Define a schema with a parent message containing a nested child message
        # Child: HeaderThrift with trackingId (int64), messageId (int64), timestamp (int64)
        # Parent: Order with header (object -> HeaderThrift), orderId (int64)
        header_fields = [
            FieldDef(name="trackingId", type="int64"),
            FieldDef(name="messageId", type="int64"),
            FieldDef(name="timestamp", type="int64"),
        ]
        header_msg = MessageDef(name="HeaderThrift", fields=header_fields)

        order_fields = [
            FieldDef(name="header", type="object", nested_type="HeaderThrift"),
            FieldDef(name="orderId", type="int64"),
        ]
        order_msg = MessageDef(name="Order", fields=order_fields)

        schema = Schema(
            messages={
                "HeaderThrift": header_msg,
                "Order": order_msg,
            },
            default_message="Order",
        )

        decoder = BinaryDecoder(schema)

        # Create binary data: header (3 x int64) + orderId (int64)
        # trackingId=123, messageId=456, timestamp=789, orderId=999
        data = struct.pack("<q", 123) + struct.pack("<q", 456) + struct.pack("<q", 789) + struct.pack("<q", 999)

        result = decoder.decode(data)

        # The nested header should be decoded as a dict
        assert "header" in result
        assert isinstance(result["header"], dict)
        assert result["header"]["trackingId"] == 123
        assert result["header"]["messageId"] == 456
        assert result["header"]["timestamp"] == 789
        assert result["orderId"] == 999


class TestCreateExampleSchema:
    """Tests for create_example_schema function."""

    def test_returns_valid_json(self):
        example = create_example_schema()
        # Should be valid JSON
        data = json.loads(example)
        assert "messages" in data
        assert "default" in data

    def test_has_message_types(self):
        example = create_example_schema()
        data = json.loads(example)
        assert "FxTick" in data["messages"]
        assert "Trade" in data["messages"]

    def test_can_create_schema(self):
        example = create_example_schema()
        schema = Schema.from_json(example)
        assert len(schema.messages) == 2
        assert schema.default_message == "FxTick"
