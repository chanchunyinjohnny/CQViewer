"""Apache Thrift TCompactProtocol decoder.

Decodes Thrift-serialized messages using the compact protocol format.
Reference: https://github.com/apache/thrift/blob/master/doc/specs/thrift-compact-protocol.md
"""

import struct
from dataclasses import dataclass
from typing import Any


# Thrift compact protocol type IDs
COMPACT_BOOLEAN_TRUE = 1
COMPACT_BOOLEAN_FALSE = 2
COMPACT_BYTE = 3
COMPACT_I16 = 4
COMPACT_I32 = 5
COMPACT_I64 = 6
COMPACT_DOUBLE = 7
COMPACT_BINARY = 8  # Also used for STRING
COMPACT_LIST = 9
COMPACT_SET = 10
COMPACT_MAP = 11
COMPACT_STRUCT = 12


@dataclass
class ThriftField:
    """A field definition for Thrift decoding."""
    field_id: int
    name: str
    thrift_type: str  # "bool", "byte", "i16", "i32", "i64", "double", "string", "binary", "struct", "list", "map"


class ThriftDecoder:
    """Decoder for Thrift TCompactProtocol format."""

    def __init__(self, fields: list[ThriftField] | None = None):
        """Initialize decoder with optional field definitions.

        Args:
            fields: List of field definitions mapping field IDs to names
        """
        self.field_map = {}
        if fields:
            for f in fields:
                self.field_map[f.field_id] = f

    def decode(self, data: bytes) -> dict[str, Any]:
        """Decode Thrift compact protocol data.

        Args:
            data: Binary data to decode

        Returns:
            Dictionary of field names/IDs to decoded values
        """
        result = {}
        pos = 0
        last_field_id = 0

        while pos < len(data):
            if data[pos] == 0:  # STOP field
                break

            # Read field header
            type_and_delta = data[pos]
            pos += 1

            field_delta = (type_and_delta >> 4) & 0x0F
            field_type = type_and_delta & 0x0F

            if field_delta == 0:
                # Long form - field ID follows as zigzag varint
                field_id, bytes_read = self._read_zigzag_varint(data, pos)
                pos += bytes_read
            else:
                # Short form - delta encoded
                field_id = last_field_id + field_delta

            last_field_id = field_id

            # Decode value based on type
            value, bytes_read = self._decode_value(data, pos, field_type)
            pos += bytes_read

            # Get field name from map or use field ID
            if field_id in self.field_map:
                field_name = self.field_map[field_id].name
            else:
                field_name = f"field_{field_id}"

            result[field_name] = value

        return result

    def _decode_value(self, data: bytes, pos: int, field_type: int) -> tuple[Any, int]:
        """Decode a value based on its type.

        Returns:
            Tuple of (decoded_value, bytes_consumed)
        """
        if field_type == COMPACT_BOOLEAN_TRUE:
            return True, 0
        elif field_type == COMPACT_BOOLEAN_FALSE:
            return False, 0
        elif field_type == COMPACT_BYTE:
            return data[pos], 1
        elif field_type == COMPACT_I16:
            value, bytes_read = self._read_zigzag_varint(data, pos)
            return value, bytes_read
        elif field_type == COMPACT_I32:
            value, bytes_read = self._read_zigzag_varint(data, pos)
            return value, bytes_read
        elif field_type == COMPACT_I64:
            value, bytes_read = self._read_zigzag_varint(data, pos)
            return value, bytes_read
        elif field_type == COMPACT_DOUBLE:
            if pos + 8 > len(data):
                return None, 0
            value = struct.unpack('<d', data[pos:pos + 8])[0]
            return value, 8
        elif field_type == COMPACT_BINARY:
            # Length-prefixed binary/string
            length, len_bytes = self._read_varint(data, pos)
            pos += len_bytes
            if pos + length > len(data):
                return None, len_bytes
            try:
                value = data[pos:pos + length].decode('utf-8')
            except UnicodeDecodeError:
                value = data[pos:pos + length].hex()
            return value, len_bytes + length
        elif field_type == COMPACT_STRUCT:
            # Nested struct - recursively decode
            nested_result = {}
            bytes_consumed = 0
            nested_last_field_id = 0

            while pos + bytes_consumed < len(data):
                if data[pos + bytes_consumed] == 0:  # STOP
                    bytes_consumed += 1
                    break

                type_and_delta = data[pos + bytes_consumed]
                bytes_consumed += 1

                field_delta = (type_and_delta >> 4) & 0x0F
                nested_type = type_and_delta & 0x0F

                if field_delta == 0:
                    nested_field_id, vb = self._read_zigzag_varint(data, pos + bytes_consumed)
                    bytes_consumed += vb
                else:
                    nested_field_id = nested_last_field_id + field_delta

                nested_last_field_id = nested_field_id

                value, vb = self._decode_value(data, pos + bytes_consumed, nested_type)
                bytes_consumed += vb
                nested_result[f"field_{nested_field_id}"] = value

            return nested_result, bytes_consumed
        elif field_type == COMPACT_LIST:
            # List header: size and element type
            size_and_type = data[pos]
            pos += 1
            bytes_consumed = 1

            elem_type = size_and_type & 0x0F
            size = (size_and_type >> 4) & 0x0F

            if size == 15:  # Large list
                size, vb = self._read_varint(data, pos)
                bytes_consumed += vb

            items = []
            for _ in range(size):
                value, vb = self._decode_value(data, pos + bytes_consumed - 1, elem_type)
                bytes_consumed += vb
                items.append(value)

            return items, bytes_consumed
        elif field_type == COMPACT_MAP:
            # Map: size, then key/value type, then pairs
            size, size_bytes = self._read_varint(data, pos)
            bytes_consumed = size_bytes

            if size == 0:
                return {}, bytes_consumed

            kv_type = data[pos + bytes_consumed]
            bytes_consumed += 1
            key_type = (kv_type >> 4) & 0x0F
            val_type = kv_type & 0x0F

            result_map = {}
            for _ in range(size):
                key, kb = self._decode_value(data, pos + bytes_consumed, key_type)
                bytes_consumed += kb
                val, vb = self._decode_value(data, pos + bytes_consumed, val_type)
                bytes_consumed += vb
                result_map[str(key)] = val

            return result_map, bytes_consumed
        else:
            # Unknown type - skip
            return None, 0

    def _read_varint(self, data: bytes, pos: int) -> tuple[int, int]:
        """Read an unsigned varint."""
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

    def _read_zigzag_varint(self, data: bytes, pos: int) -> tuple[int, int]:
        """Read a zigzag-encoded signed varint."""
        value, bytes_read = self._read_varint(data, pos)
        # Decode zigzag
        return (value >> 1) ^ -(value & 1), bytes_read


def create_thrift_decoder_from_java(java_fields: list) -> ThriftDecoder:
    """Create a ThriftDecoder from parsed Java fields.

    Extracts field IDs from Thrift-generated Java class patterns.

    Args:
        java_fields: List of JavaField objects from java_parser

    Returns:
        ThriftDecoder with field mappings
    """
    # Thrift-generated classes have field IDs in the _Fields enum
    # and field descriptors like: TField("fieldName", TType.STRING, (short)2)
    # For now, we'll use field order as ID (1-based)

    thrift_fields = []
    field_id = 1

    for jf in java_fields:
        # Skip internal fields
        if jf.name.startswith('_') or jf.name.startswith('__'):
            continue

        # Map Java type to Thrift type
        java_type = jf.java_type.lower()
        if java_type in ('string', 'charsequence'):
            thrift_type = 'string'
        elif java_type in ('int', 'integer'):
            thrift_type = 'i32'
        elif java_type in ('long',):
            thrift_type = 'i64'
        elif java_type in ('short',):
            thrift_type = 'i16'
        elif java_type in ('byte',):
            thrift_type = 'byte'
        elif java_type in ('double',):
            thrift_type = 'double'
        elif java_type in ('float',):
            thrift_type = 'double'  # Thrift uses double
        elif java_type in ('boolean', 'bool'):
            thrift_type = 'bool'
        else:
            thrift_type = 'struct'  # Nested object

        thrift_fields.append(ThriftField(
            field_id=field_id,
            name=jf.name,
            thrift_type=thrift_type,
        ))
        field_id += 1

    return ThriftDecoder(thrift_fields)
