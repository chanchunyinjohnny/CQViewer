"""Schema definitions for decoding binary messages.

Supports multiple encoding formats:
- BINARY_LIGHT: Chronicle's simple binary format
- THRIFT: Apache Thrift TCompactProtocol
- SBE: Simple Binary Encoding

Users can define message schemas in JSON format to decode binary messages.

Example schema file (schema.json):
{
    "messages": {
        "FxTick": {
            "fields": [
                {"name": "timestamp", "type": "int64"},
                {"name": "bid", "type": "float64"},
                {"name": "ask", "type": "float64"},
                {"name": "symbol", "type": "string"}
            ]
        },
        "Order": {
            "fields": [
                {"name": "orderId", "type": "int64"},
                {"name": "symbol", "type": "string"},
                {"name": "quantity", "type": "int32"},
                {"name": "price", "type": "float64"},
                {"name": "side", "type": "string"}
            ]
        }
    },
    "default": "FxTick"
}

Supported types:
- int8, int16, int32, int64 (signed integers)
- uint8, uint16, uint32, uint64 (unsigned integers)
- float32, float64 (floating point)
- string (length-prefixed UTF-8 string)
- bytes (length-prefixed binary data)
- bool (1 byte boolean)
- stop_bit (variable-length encoded integer)
- padding (skip N bytes, use "size" field)
"""

import json
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FieldDef:
    """Definition of a single field."""
    name: str
    type: str
    size: int = 0  # For padding or fixed-size fields
    optional: bool = False
    field_id: int | None = None  # Thrift field ID (1-based)


@dataclass
class MessageDef:
    """Definition of a message type."""
    name: str
    fields: list[FieldDef] = field(default_factory=list)


# Encoding format constants
ENCODING_BINARY = "binary"  # Simple sequential binary
ENCODING_THRIFT = "thrift"  # Apache Thrift TCompactProtocol
ENCODING_SBE = "sbe"        # Simple Binary Encoding


@dataclass
class Schema:
    """Schema containing multiple message definitions."""
    messages: dict[str, MessageDef] = field(default_factory=dict)
    default_message: str | None = None
    encoding: str = ENCODING_BINARY  # Default encoding format

    @classmethod
    def from_file(cls, filepath: str | Path) -> "Schema":
        """Load schema from JSON file."""
        with open(filepath, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_json(cls, json_str: str) -> "Schema":
        """Load schema from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "Schema":
        """Load schema from dictionary."""
        schema = cls()

        messages_data = data.get("messages", {})
        for msg_name, msg_def in messages_data.items():
            fields = []
            for field_def in msg_def.get("fields", []):
                fields.append(FieldDef(
                    name=field_def["name"],
                    type=field_def["type"],
                    size=field_def.get("size", 0),
                    optional=field_def.get("optional", False),
                ))
            schema.messages[msg_name] = MessageDef(name=msg_name, fields=fields)

        schema.default_message = data.get("default")
        return schema

    def get_message(self, name: str | None = None) -> MessageDef | None:
        """Get message definition by name or default."""
        if name:
            return self.messages.get(name)
        if self.default_message:
            return self.messages.get(self.default_message)
        # Return first message if only one defined
        if len(self.messages) == 1:
            return next(iter(self.messages.values()))
        return None


class BinaryDecoder:
    """Decoder for binary formats using a schema.

    Supports multiple encoding formats:
    - binary: Simple sequential binary (Chronicle BINARY_LIGHT)
    - thrift: Apache Thrift TCompactProtocol
    - sbe: Simple Binary Encoding
    """

    # Type sizes in bytes
    TYPE_SIZES = {
        "int8": 1, "uint8": 1, "bool": 1,
        "int16": 2, "uint16": 2,
        "int32": 4, "uint32": 4, "float32": 4,
        "int64": 8, "uint64": 8, "float64": 8,
    }

    # Struct format codes
    TYPE_FORMATS = {
        "int8": "b", "uint8": "B", "bool": "?",
        "int16": "h", "uint16": "H",
        "int32": "i", "uint32": "I", "float32": "f",
        "int64": "q", "uint64": "Q", "float64": "d",
    }

    def __init__(self, schema: Schema):
        """Initialize decoder with schema."""
        self.schema = schema
        self._thrift_decoder = None
        self._sbe_decoder = None

    def decode(self, data: bytes, message_name: str | None = None) -> dict[str, Any]:
        """Decode binary data using schema.

        Uses the encoding format specified in the schema.
        """
        encoding = self.schema.encoding

        if encoding == ENCODING_THRIFT:
            return self._decode_thrift(data, message_name)
        elif encoding == ENCODING_SBE:
            return self._decode_sbe(data, message_name)
        else:
            return self._decode_binary(data, message_name)

    def _decode_thrift(self, data: bytes, message_name: str | None = None) -> dict[str, Any]:
        """Decode using Thrift TCompactProtocol."""
        from .thrift_decoder import ThriftDecoder, ThriftField

        msg_def = self.schema.get_message(message_name)
        if not msg_def:
            return {"_error": "No matching message definition", "_raw_hex": data.hex()}

        # Build Thrift field map - use actual field IDs if available
        thrift_fields = []
        for i, field_def in enumerate(msg_def.fields, start=1):
            # Use the field's actual Thrift ID if available, otherwise use sequential
            field_id = field_def.field_id if field_def.field_id is not None else i
            thrift_fields.append(ThriftField(
                field_id=field_id,
                name=field_def.name,
                thrift_type=self._to_thrift_type(field_def.type),
            ))

        decoder = ThriftDecoder(thrift_fields)
        return decoder.decode(data)

    def _decode_sbe(self, data: bytes, message_name: str | None = None) -> dict[str, Any]:
        """Decode using Simple Binary Encoding."""
        from .sbe_decoder import SBEDecoder, SBEField

        msg_def = self.schema.get_message(message_name)
        if not msg_def:
            return {"_error": "No matching message definition", "_raw_hex": data.hex()}

        # Build SBE field list
        sbe_fields = []
        for field_def in msg_def.fields:
            primitive_type, length = self._to_sbe_type(field_def.type)
            sbe_fields.append(SBEField(
                name=field_def.name,
                primitive_type=primitive_type,
                length=length,
            ))

        decoder = SBEDecoder(sbe_fields)
        return decoder.decode(data)

    def _to_thrift_type(self, schema_type: str) -> str:
        """Convert schema type to Thrift type."""
        mapping = {
            "int8": "byte", "uint8": "byte",
            "int16": "i16", "uint16": "i16",
            "int32": "i32", "uint32": "i32",
            "int64": "i64", "uint64": "i64",
            "float32": "double", "float64": "double",
            "bool": "bool",
            "string": "string",
            "bytes": "binary",
        }
        return mapping.get(schema_type.lower(), "binary")

    def _to_sbe_type(self, schema_type: str) -> tuple[str, int]:
        """Convert schema type to SBE type and length."""
        mapping = {
            "int8": ("int8", 1), "uint8": ("uint8", 1),
            "int16": ("int16", 1), "uint16": ("uint16", 1),
            "int32": ("int32", 1), "uint32": ("uint32", 1),
            "int64": ("int64", 1), "uint64": ("uint64", 1),
            "float32": ("float", 1), "float64": ("double", 1),
            "bool": ("uint8", 1),
            "string": ("char", 32),  # Default string length
            "bytes": ("int8", 32),   # Default byte array length
        }
        return mapping.get(schema_type.lower(), ("int8", 1))

    def _decode_binary(self, data: bytes, message_name: str | None = None) -> dict[str, Any]:
        """Decode using simple sequential binary format."""
        msg_def = self.schema.get_message(message_name)
        if not msg_def:
            return {"_error": "No matching message definition", "_raw_hex": data.hex()}

        result = {}
        pos = 0

        for field_def in msg_def.fields:
            if pos >= len(data):
                if field_def.optional:
                    continue
                result[field_def.name] = None
                continue

            try:
                value, bytes_read = self._decode_field(data, pos, field_def)
                result[field_def.name] = value
                pos += bytes_read
            except Exception as e:
                result[field_def.name] = f"<decode_error: {e}>"
                break

        # Add remaining bytes if any
        if pos < len(data):
            result["_remaining_bytes"] = len(data) - pos
            result["_remaining_hex"] = data[pos:].hex()

        return result

    def _decode_field(self, data: bytes, pos: int, field_def: FieldDef) -> tuple[Any, int]:
        """Decode a single field.

        Returns:
            Tuple of (decoded_value, bytes_consumed)
        """
        field_type = field_def.type.lower()

        # Fixed-size types
        if field_type in self.TYPE_FORMATS:
            size = self.TYPE_SIZES[field_type]
            if pos + size > len(data):
                # Try to read smaller integer type if not enough data
                # This handles cases where Chronicle encodes int32 as int8
                remaining = len(data) - pos
                if remaining > 0 and field_type in ("int32", "uint32"):
                    if remaining >= 2:
                        fmt = "<h" if field_type == "int32" else "<H"
                        value = struct.unpack_from(fmt, data, pos)[0]
                        return value, 2
                    else:
                        fmt = "<b" if field_type == "int32" else "<B"
                        value = struct.unpack_from(fmt, data, pos)[0]
                        return value, 1
                elif remaining > 0 and field_type in ("int16", "uint16"):
                    fmt = "<b" if field_type == "int16" else "<B"
                    value = struct.unpack_from(fmt, data, pos)[0]
                    return value, 1
                raise ValueError(f"Not enough data for {field_type}")
            fmt = "<" + self.TYPE_FORMATS[field_type]
            value = struct.unpack_from(fmt, data, pos)[0]
            return value, size

        # String (length-prefixed)
        if field_type == "string":
            # Try stop-bit length first, then fall back to 1-byte length
            length, len_bytes = self._read_length(data, pos)
            if pos + len_bytes + length > len(data):
                raise ValueError("String extends beyond data")
            value = data[pos + len_bytes:pos + len_bytes + length].decode("utf-8", errors="replace")
            return value, len_bytes + length

        # Bytes (length-prefixed)
        if field_type == "bytes":
            length, len_bytes = self._read_length(data, pos)
            if pos + len_bytes + length > len(data):
                raise ValueError("Bytes extends beyond data")
            value = data[pos + len_bytes:pos + len_bytes + length].hex()
            return value, len_bytes + length

        # Stop-bit encoded integer
        if field_type == "stop_bit":
            value, bytes_read = self._read_stop_bit(data, pos)
            return value, bytes_read

        # Padding (skip bytes)
        if field_type == "padding":
            size = field_def.size or 1
            return None, size

        # Skip (like padding but explicit size)
        if field_type == "skip":
            size = field_def.size or 1
            return None, size

        # Nested object - try to detect boundaries
        # Chronicle BINARY_LIGHT nested objects don't have length prefixes
        # If a size is specified, skip that many bytes
        if field_type in ("object", "struct", "nested"):
            size = field_def.size
            if size:
                return f"<nested:{size}bytes>", size
            # Try to detect the end of the nested object by looking for
            # a valid string length prefix (a byte that matches the pattern
            # of being followed by ASCII printable characters)
            detected_size = self._detect_nested_object_size(data, pos)
            if detected_size > 0:
                return f"<nested:{detected_size}bytes>", detected_size
            # Without explicit size and no detection, return raw hex
            remaining = min(32, len(data) - pos)  # Show first 32 bytes
            return f"<nested:0x{data[pos:pos+remaining].hex()}>", remaining

        raise ValueError(f"Unknown type: {field_type}")

    def _detect_nested_object_size(self, data: bytes, pos: int) -> int:
        """Try to detect the size of a nested object.

        Looks for the boundary where multiple consecutive valid string fields start.
        Requires finding at least 2 consecutive valid string-like fields.
        Returns 0 if cannot detect.
        """
        min_scan = 8  # Minimum nested object size
        max_scan = min(256, len(data) - pos - 20)  # Max scan distance

        for offset in range(min_scan, max_scan):
            test_pos = pos + offset
            if test_pos >= len(data) - 10:
                break

            # Try to find 2 consecutive valid strings starting at this position
            consecutive_valid = 0
            check_pos = test_pos

            for _ in range(3):  # Try to find up to 3 consecutive strings
                if check_pos >= len(data) - 1:
                    break

                length_byte = data[check_pos]
                # Check if this could be a string length (reasonable range, not 0)
                if 2 <= length_byte <= 100:  # Min length 2 to avoid false positives
                    str_start = check_pos + 1
                    str_end = str_start + length_byte
                    if str_end <= len(data):
                        str_bytes = data[str_start:str_end]
                        # Check if all bytes are printable ASCII or reasonable UTF-8
                        printable = sum(1 for b in str_bytes if 32 <= b < 127)
                        if printable == len(str_bytes):  # 100% printable
                            consecutive_valid += 1
                            check_pos = str_end
                            continue
                break

            # Require at least 2 consecutive valid strings
            if consecutive_valid >= 2:
                return offset

        return 0

    def _read_length(self, data: bytes, pos: int) -> tuple[int, int]:
        """Read a length prefix (1 byte or stop-bit encoded)."""
        if pos >= len(data):
            return 0, 0

        first_byte = data[pos]

        # Check for stop-bit encoding (high bit set means more bytes)
        if first_byte & 0x80:
            return self._read_stop_bit(data, pos)

        # Simple 1-byte length
        return first_byte, 1

    def _read_stop_bit(self, data: bytes, pos: int) -> tuple[int, int]:
        """Read stop-bit encoded integer."""
        result = 0
        shift = 0
        bytes_read = 0

        while pos + bytes_read < len(data):
            byte = data[pos + bytes_read]
            bytes_read += 1
            result |= (byte & 0x7F) << shift
            shift += 7
            if (byte & 0x80) == 0:
                break

        return result, bytes_read


def create_example_schema() -> str:
    """Create an example schema JSON string."""
    example = {
        "messages": {
            "FxTick": {
                "fields": [
                    {"name": "timestamp", "type": "int64"},
                    {"name": "bid", "type": "float64"},
                    {"name": "ask", "type": "float64"},
                    {"name": "symbol", "type": "string"}
                ]
            },
            "Trade": {
                "fields": [
                    {"name": "tradeId", "type": "int64"},
                    {"name": "timestamp", "type": "int64"},
                    {"name": "symbol", "type": "string"},
                    {"name": "price", "type": "float64"},
                    {"name": "quantity", "type": "int32"},
                    {"name": "side", "type": "string"}
                ]
            }
        },
        "default": "FxTick"
    }
    return json.dumps(example, indent=2)
