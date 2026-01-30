"""Chronicle Wire binary format parser.

Parses self-describing binary wire format used by Chronicle Queue.
"""

import struct
from dataclasses import dataclass, field
from typing import Any

from .wire_types import (
    WireType,
    is_compact_field_name,
    compact_field_name_length,
    is_compact_string,
    compact_string_length,
)
from .stop_bit import read_stop_bit


@dataclass
class ParsedField:
    """A parsed field from wire format."""

    name: str
    value: Any
    type_hint: str | None = None


@dataclass
class ParsedMessage:
    """A parsed message from wire format."""

    type_hint: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)
    raw_offset: int = 0
    raw_size: int = 0


class WireReader:
    """Parser for Chronicle Wire binary format."""

    def __init__(self, data: bytes | memoryview):
        """Initialize reader with binary data.

        Args:
            data: Binary data to parse
        """
        self.data = data
        self.pos = 0

    @property
    def remaining(self) -> int:
        """Number of bytes remaining to read."""
        return len(self.data) - self.pos

    def read_byte(self) -> int:
        """Read a single byte."""
        if self.pos >= len(self.data):
            raise ValueError("Unexpected end of data")
        byte = self.data[self.pos]
        self.pos += 1
        return byte

    def read_bytes(self, count: int) -> bytes:
        """Read specified number of bytes."""
        if self.pos + count > len(self.data):
            raise ValueError(f"Cannot read {count} bytes, only {self.remaining} remaining")
        result = bytes(self.data[self.pos : self.pos + count])
        self.pos += count
        return result

    def peek_byte(self) -> int | None:
        """Peek at next byte without consuming it."""
        if self.pos >= len(self.data):
            return None
        return self.data[self.pos]

    def skip(self, count: int) -> None:
        """Skip specified number of bytes."""
        self.pos += count

    def read_stop_bit(self) -> int:
        """Read a stop-bit encoded integer."""
        value, consumed = read_stop_bit(self.data, self.pos)
        self.pos += consumed
        return value

    def read_int8(self) -> int:
        """Read signed 8-bit integer."""
        value = struct.unpack_from("b", self.data, self.pos)[0]
        self.pos += 1
        return value

    def read_uint8(self) -> int:
        """Read unsigned 8-bit integer."""
        value = struct.unpack_from("B", self.data, self.pos)[0]
        self.pos += 1
        return value

    def read_int16(self) -> int:
        """Read signed 16-bit integer (little-endian)."""
        value = struct.unpack_from("<h", self.data, self.pos)[0]
        self.pos += 2
        return value

    def read_uint16(self) -> int:
        """Read unsigned 16-bit integer (little-endian)."""
        value = struct.unpack_from("<H", self.data, self.pos)[0]
        self.pos += 2
        return value

    def read_int32(self) -> int:
        """Read signed 32-bit integer (little-endian)."""
        value = struct.unpack_from("<i", self.data, self.pos)[0]
        self.pos += 4
        return value

    def read_int64(self) -> int:
        """Read signed 64-bit integer (little-endian)."""
        value = struct.unpack_from("<q", self.data, self.pos)[0]
        self.pos += 8
        return value

    def read_float32(self) -> float:
        """Read 32-bit float (little-endian)."""
        value = struct.unpack_from("<f", self.data, self.pos)[0]
        self.pos += 4
        return value

    def read_float64(self) -> float:
        """Read 64-bit float (little-endian)."""
        value = struct.unpack_from("<d", self.data, self.pos)[0]
        self.pos += 8
        return value

    def read_string(self, length: int) -> str:
        """Read a UTF-8 string of specified length."""
        data = self.read_bytes(length)
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            # Fall back to latin-1 for binary data
            return data.decode("latin-1")

    def read_type_prefix(self) -> str:
        """Read a type prefix (e.g., '!types.Order')."""
        # Type prefix is a stop-bit length followed by string
        length = self.read_stop_bit()
        return self.read_string(length)

    def read_field_name(self) -> str | None:
        """Read a field name from the current position.

        Returns None if at end of data or at a non-field-name marker.
        """
        code = self.peek_byte()
        if code is None:
            return None

        if is_compact_field_name(code):
            self.read_byte()  # Consume the code
            length = compact_field_name_length(code)
            if length == 0:
                return ""
            return self.read_string(length)

        if code == WireType.FIELD_NAME_ANY:
            self.read_byte()  # Consume the code
            length = self.read_stop_bit()
            return self.read_string(length)

        if code == WireType.FIELD_NAME_LITERAL:
            self.read_byte()  # Consume the code
            length = self.read_stop_bit()
            return self.read_string(length)

        # FIELD_NUMBER is used as event name in Chronicle Queue
        if code == WireType.FIELD_NUMBER:
            self.read_byte()  # Consume the code
            length = self.read_stop_bit()
            return self.read_string(length)

        # EVENT_NAME
        if code == WireType.EVENT_NAME:
            self.read_byte()  # Consume the code
            length = self.read_stop_bit()
            return self.read_string(length)

        return None

    def read_value(self) -> Any:
        """Read a value from the current position."""
        code = self.peek_byte()
        if code is None:
            return None

        # Compact strings (0xE0-0xFF)
        if is_compact_string(code):
            self.read_byte()
            length = compact_string_length(code)
            if length == 0:
                return ""
            return self.read_string(length)

        self.read_byte()  # Consume the type code

        # NULL
        if code == WireType.NULL:
            return None

        # Fixed-width integers
        if code == WireType.INT8:
            return self.read_int8()
        if code == WireType.UINT8:
            return self.read_uint8()
        if code == WireType.INT16:
            return self.read_int16()
        if code == WireType.UINT16:
            return self.read_uint16()
        if code == WireType.INT32:
            return self.read_int32()
        if code == WireType.INT64:
            return self.read_int64()

        # Floating point
        if code == WireType.FLOAT32:
            return self.read_float32()
        if code == WireType.FLOAT64:
            return self.read_float64()

        # String types
        if code == WireType.STRING_ANY:
            length = self.read_stop_bit()
            return self.read_string(length)

        # Bytes/binary data
        if code == WireType.BYTES_LENGTH32:
            length = self.read_int32()
            return self.read_bytes(length)

        # Nested block (object)
        if code == WireType.NESTED_BLOCK:
            length = self.read_stop_bit()
            # Parse nested content
            nested_data = self.data[self.pos : self.pos + length]
            self.pos += length
            nested_reader = WireReader(nested_data)
            return nested_reader.read_object()

        # Type prefix
        if code == WireType.TYPE_PREFIX:
            type_name = self.read_type_prefix()
            # After type prefix, read the actual value (usually nested block)
            value = self.read_value()
            if isinstance(value, dict):
                value["__type__"] = type_name
            return value

        # Arrays
        if code == WireType.I64_ARRAY:
            count = self.read_int32()
            return [self.read_int64() for _ in range(count)]

        if code == WireType.U8_ARRAY:
            length = self.read_int32()
            return list(self.read_bytes(length))

        if code == WireType.I8_ARRAY:
            length = self.read_int32()
            return [struct.unpack_from("b", self.data, self.pos + i)[0] for i in range(length)]

        # Timestamps
        if code == WireType.TIMESTAMP:
            return self.read_int64()  # Epoch millis

        if code == WireType.DATE_TIME:
            # Encoded as nano timestamp
            return self.read_int64()

        if code == WireType.UUID:
            # 16 bytes
            uuid_bytes = self.read_bytes(16)
            # Format as standard UUID string
            import uuid

            return str(uuid.UUID(bytes=uuid_bytes))

        # Padding - skip
        if code == WireType.PADDING:
            return None

        if code == WireType.PADDING32:
            # Skip padding bytes
            length = self.read_int32()
            self.skip(length)
            return None

        if code == WireType.PADDING_END:
            # End of padding
            return None

        # Event name (like field name but for events)
        if code == WireType.EVENT_NAME:
            length = self.read_stop_bit()
            return self.read_string(length)

        # Comment
        if code == WireType.COMMENT:
            length = self.read_stop_bit()
            return self.read_string(length)

        # Unknown type - return hex representation
        return f"<unknown:0x{code:02X}>"

    def read_field(self) -> ParsedField | None:
        """Read a complete field (name + value).

        Returns None if no more fields available.
        """
        name = self.read_field_name()
        if name is None:
            return None

        value = self.read_value()
        return ParsedField(name=name, value=value)

    def read_object(self) -> dict[str, Any]:
        """Read all fields as a dictionary."""
        result = {}
        start_pos = self.pos

        while self.remaining > 0:
            # Check for padding
            code = self.peek_byte()
            if code is None:
                break

            if code == WireType.PADDING:
                self.read_byte()
                continue

            if code == WireType.PADDING32:
                self.read_byte()
                length = self.read_int32()
                self.skip(length)
                continue

            if code == WireType.PADDING_END:
                self.read_byte()
                break

            field = self.read_field()
            if field is None:
                break

            result[field.name] = field.value

        # If no fields parsed but there was data, extract raw info
        if not result and len(self.data) > 0:
            raw_data = bytes(self.data)
            result["_raw_hex"] = raw_data.hex()
            result["_raw_length"] = len(raw_data)

            # Extract readable ASCII strings (4+ chars)
            extracted = self._extract_strings(raw_data)
            if extracted:
                if isinstance(extracted, dict):
                    # JSON was found - add fields directly
                    result["_json"] = extracted
                    for key, value in extracted.items():
                        result[key] = value
                else:
                    result["_strings"] = extracted

        return result

    def _extract_strings(self, data: bytes, min_length: int = 4) -> str | dict | list[str]:
        """Extract readable ASCII strings from binary data.

        If a JSON object is found, returns it parsed.
        Otherwise returns a comma-separated string of extracted strings.
        """
        strings = []
        current = []

        for byte in data:
            if 32 <= byte < 127:  # Printable ASCII
                current.append(chr(byte))
            else:
                if len(current) >= min_length:
                    strings.append("".join(current))
                current = []

        if len(current) >= min_length:
            strings.append("".join(current))

        # Check if any string looks like JSON
        for s in strings:
            if s.startswith("{") and s.endswith("}"):
                try:
                    import json
                    return json.loads(s)
                except (json.JSONDecodeError, ValueError):
                    pass

        # Return as comma-separated string for readability
        if strings:
            return ", ".join(strings)
        return []

    def read_message(self) -> ParsedMessage | None:
        """Read a complete message with optional type hint.

        Returns None if no data available.
        """
        if self.remaining == 0:
            return None

        start_pos = self.pos
        type_hint = None

        # Check for type prefix at start
        code = self.peek_byte()
        if code == WireType.TYPE_PREFIX:
            self.read_byte()
            type_hint = self.read_type_prefix()

        fields = self.read_object()

        return ParsedMessage(
            type_hint=type_hint,
            fields=fields,
            raw_offset=start_pos,
            raw_size=self.pos - start_pos,
        )
