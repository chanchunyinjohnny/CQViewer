"""Simple Binary Encoding (SBE) decoder.

Decodes SBE-serialized messages. SBE is a fixed-size binary format with
fields laid out sequentially according to a schema.

Reference: https://github.com/real-logic/simple-binary-encoding
"""

import struct
from dataclasses import dataclass
from typing import Any


@dataclass
class SBEField:
    """A field definition for SBE decoding."""
    name: str
    primitive_type: str  # "int8", "uint8", "int16", "uint16", "int32", "uint32", "int64", "uint64", "float", "double", "char"
    offset: int | None = None  # Byte offset from start (None = sequential)
    length: int = 1  # For char arrays / fixed strings
    optional: bool = False
    null_value: Any = None  # Value representing null


# SBE type sizes in bytes
SBE_TYPE_SIZES = {
    "int8": 1, "uint8": 1, "char": 1,
    "int16": 2, "uint16": 2,
    "int32": 4, "uint32": 4, "float": 4,
    "int64": 8, "uint64": 8, "double": 8,
}

# SBE struct format codes (little-endian)
SBE_TYPE_FORMATS = {
    "int8": "<b", "uint8": "<B", "char": "<c",
    "int16": "<h", "uint16": "<H",
    "int32": "<i", "uint32": "<I", "float": "<f",
    "int64": "<q", "uint64": "<Q", "double": "<d",
}

# SBE null values (IEEE-defined or max value)
SBE_NULL_VALUES = {
    "int8": -128,
    "uint8": 255,
    "int16": -32768,
    "uint16": 65535,
    "int32": -2147483648,
    "uint32": 4294967295,
    "int64": -9223372036854775808,
    "uint64": 18446744073709551615,
    "float": float('nan'),
    "double": float('nan'),
    "char": 0,
}


class SBEDecoder:
    """Decoder for Simple Binary Encoding (SBE) format."""

    def __init__(self, fields: list[SBEField], block_length: int | None = None):
        """Initialize decoder with field definitions.

        Args:
            fields: List of field definitions in order
            block_length: Fixed block length (None = calculate from fields)
        """
        self.fields = fields
        self.block_length = block_length

        # Calculate offsets if not specified
        offset = 0
        for f in self.fields:
            if f.offset is None:
                f.offset = offset
            size = SBE_TYPE_SIZES.get(f.primitive_type, 1) * f.length
            offset = f.offset + size

        if self.block_length is None:
            self.block_length = offset

    def decode(self, data: bytes, offset: int = 0) -> dict[str, Any]:
        """Decode SBE message.

        Args:
            data: Binary data to decode
            offset: Starting offset in data

        Returns:
            Dictionary of field names to decoded values
        """
        result = {}

        for field in self.fields:
            pos = offset + field.offset
            value = self._decode_field(data, pos, field)

            # Check for null value
            if field.optional and value == field.null_value:
                result[field.name] = None
            elif field.optional and field.null_value is None:
                # Use default null values
                null_val = SBE_NULL_VALUES.get(field.primitive_type)
                if value == null_val or (field.primitive_type in ("float", "double") and value != value):
                    result[field.name] = None
                else:
                    result[field.name] = value
            else:
                result[field.name] = value

        return result

    def _decode_field(self, data: bytes, pos: int, field: SBEField) -> Any:
        """Decode a single field."""
        ptype = field.primitive_type

        if ptype == "char" and field.length > 1:
            # Fixed-length string
            end = pos + field.length
            if end > len(data):
                return ""
            raw = data[pos:end]
            # Trim null bytes
            try:
                null_idx = raw.index(0)
                raw = raw[:null_idx]
            except ValueError:
                pass
            try:
                return raw.decode('utf-8')
            except UnicodeDecodeError:
                return raw.decode('latin-1')

        size = SBE_TYPE_SIZES.get(ptype, 1)
        if pos + size > len(data):
            return None

        fmt = SBE_TYPE_FORMATS.get(ptype)
        if fmt:
            if ptype == "char":
                return chr(data[pos])
            return struct.unpack(fmt, data[pos:pos + size])[0]

        return None


class SBEMessageDecoder:
    """Decoder for SBE messages with header."""

    def __init__(
        self,
        fields: list[SBEField],
        header_size: int = 8,
        schema_id: int | None = None,
        template_id: int | None = None,
    ):
        """Initialize decoder.

        Args:
            fields: Field definitions for the message body
            header_size: Size of message header (default 8 bytes)
            schema_id: Expected schema ID (for validation)
            template_id: Expected template ID (for validation)
        """
        self.body_decoder = SBEDecoder(fields)
        self.header_size = header_size
        self.schema_id = schema_id
        self.template_id = template_id

    def decode(self, data: bytes) -> dict[str, Any]:
        """Decode SBE message with header.

        Standard SBE header (8 bytes):
        - blockLength (uint16): Size of the root block
        - templateId (uint16): Message template ID
        - schemaId (uint16): Schema ID
        - version (uint16): Schema version

        Returns:
            Dictionary with header info and decoded fields
        """
        result = {}

        if len(data) < self.header_size:
            result["_error"] = "Data too short for header"
            return result

        # Parse header
        if self.header_size >= 8:
            block_length = struct.unpack('<H', data[0:2])[0]
            template_id = struct.unpack('<H', data[2:4])[0]
            schema_id = struct.unpack('<H', data[4:6])[0]
            version = struct.unpack('<H', data[6:8])[0]

            result["_blockLength"] = block_length
            result["_templateId"] = template_id
            result["_schemaId"] = schema_id
            result["_version"] = version

            # Validate if expected values provided
            if self.schema_id is not None and schema_id != self.schema_id:
                result["_warning"] = f"Schema ID mismatch: expected {self.schema_id}, got {schema_id}"
            if self.template_id is not None and template_id != self.template_id:
                result["_warning"] = f"Template ID mismatch: expected {self.template_id}, got {template_id}"

        # Decode body
        body = self.body_decoder.decode(data, self.header_size)
        result.update(body)

        return result


def create_sbe_decoder_from_java(java_fields: list) -> SBEDecoder:
    """Create an SBEDecoder from parsed Java fields.

    Args:
        java_fields: List of JavaField objects from java_parser

    Returns:
        SBEDecoder with field mappings
    """
    sbe_fields = []

    for jf in java_fields:
        # Skip internal fields
        if jf.name.startswith('_') or jf.name.startswith('__'):
            continue

        # Map Java type to SBE type
        java_type = jf.java_type.lower()
        if java_type in ('string', 'charsequence'):
            # Assume fixed-size string field
            primitive_type = "char"
            length = 32  # Default string length
        elif java_type in ('int', 'integer'):
            primitive_type = "int32"
            length = 1
        elif java_type in ('long',):
            primitive_type = "int64"
            length = 1
        elif java_type in ('short',):
            primitive_type = "int16"
            length = 1
        elif java_type in ('byte',):
            primitive_type = "int8"
            length = 1
        elif java_type in ('double',):
            primitive_type = "double"
            length = 1
        elif java_type in ('float',):
            primitive_type = "float"
            length = 1
        elif java_type in ('boolean', 'bool'):
            primitive_type = "uint8"  # SBE typically uses uint8 for bool
            length = 1
        elif java_type in ('char', 'character'):
            primitive_type = "char"
            length = 1
        else:
            # Unknown type - skip or treat as bytes
            continue

        sbe_fields.append(SBEField(
            name=jf.name,
            primitive_type=primitive_type,
            length=length,
        ))

    return SBEDecoder(sbe_fields)
