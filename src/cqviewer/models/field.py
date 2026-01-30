"""Field model for Chronicle Queue messages."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class FieldType(Enum):
    """Type of a field value."""

    NULL = auto()
    STRING = auto()
    INTEGER = auto()
    FLOAT = auto()
    BOOLEAN = auto()
    BYTES = auto()
    OBJECT = auto()
    ARRAY = auto()
    TIMESTAMP = auto()
    UUID = auto()
    UNKNOWN = auto()


@dataclass
class Field:
    """A field within a Chronicle Queue message."""

    name: str
    value: Any
    field_type: FieldType

    @classmethod
    def from_value(cls, name: str, value: Any) -> "Field":
        """Create a Field from a name and value, inferring the type.

        Args:
            name: Field name
            value: Field value

        Returns:
            Field instance with inferred type
        """
        field_type = cls._infer_type(value)
        return cls(name=name, value=value, field_type=field_type)

    @staticmethod
    def _infer_type(value: Any) -> FieldType:
        """Infer the field type from a value."""
        if value is None:
            return FieldType.NULL
        if isinstance(value, str):
            # Check if it looks like a UUID
            if (
                len(value) == 36
                and value.count("-") == 4
                and all(c in "0123456789abcdef-" for c in value.lower())
            ):
                return FieldType.UUID
            return FieldType.STRING
        if isinstance(value, bool):
            return FieldType.BOOLEAN
        if isinstance(value, int):
            return FieldType.INTEGER
        if isinstance(value, float):
            return FieldType.FLOAT
        if isinstance(value, bytes):
            return FieldType.BYTES
        if isinstance(value, dict):
            return FieldType.OBJECT
        if isinstance(value, (list, tuple)):
            return FieldType.ARRAY
        return FieldType.UNKNOWN

    def format_value(self, max_length: int = 100) -> str:
        """Format value for display.

        Args:
            max_length: Maximum string length before truncation

        Returns:
            Formatted string representation
        """
        if self.value is None:
            return "<null>"

        if self.field_type == FieldType.BYTES:
            # Show hex preview for bytes
            hex_str = self.value.hex()
            if len(hex_str) > max_length:
                return f"<bytes:{len(self.value)}> {hex_str[:max_length]}..."
            return f"<bytes:{len(self.value)}> {hex_str}"

        if self.field_type == FieldType.OBJECT:
            # Show object summary
            keys = list(self.value.keys()) if isinstance(self.value, dict) else []
            type_hint = self.value.get("__type__", "") if isinstance(self.value, dict) else ""
            if type_hint:
                return f"{{{type_hint}: {len(keys)} fields}}"
            return f"{{object: {len(keys)} fields}}"

        if self.field_type == FieldType.ARRAY:
            return f"[{len(self.value)} items]"

        str_value = str(self.value)
        if len(str_value) > max_length:
            return str_value[:max_length] + "..."
        return str_value
