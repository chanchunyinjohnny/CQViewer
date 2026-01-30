"""Message model for Chronicle Queue excerpts."""

from dataclasses import dataclass, field
from typing import Any

from .field import Field


@dataclass
class Message:
    """A message (excerpt) from a Chronicle Queue."""

    index: int
    offset: int
    type_hint: str | None = None
    fields: dict[str, Field] = field(default_factory=dict)
    is_metadata: bool = False

    @classmethod
    def from_parsed(
        cls,
        index: int,
        offset: int,
        type_hint: str | None,
        fields_dict: dict[str, Any],
        is_metadata: bool = False,
    ) -> "Message":
        """Create a Message from parsed wire data.

        Args:
            index: Message index in queue
            offset: Byte offset in file
            type_hint: Optional type hint (e.g., '!types.Order')
            fields_dict: Dictionary of field names to values
            is_metadata: Whether this is a metadata message

        Returns:
            Message instance
        """
        fields = {}
        for name, value in fields_dict.items():
            if name == "__type__":
                continue  # Skip internal type marker
            fields[name] = Field.from_value(name, value)

        return cls(
            index=index,
            offset=offset,
            type_hint=type_hint,
            fields=fields,
            is_metadata=is_metadata,
        )

    def get_field(self, name: str) -> Field | None:
        """Get a field by name.

        Args:
            name: Field name (supports dot notation for nested access)

        Returns:
            Field or None if not found
        """
        if "." not in name:
            return self.fields.get(name)

        # Handle nested access
        parts = name.split(".")
        current = self.fields.get(parts[0])
        if current is None:
            return None

        for part in parts[1:]:
            if current.field_type.name != "OBJECT" or not isinstance(current.value, dict):
                return None
            if part not in current.value:
                return None
            current = Field.from_value(part, current.value[part])

        return current

    def has_field(self, name: str) -> bool:
        """Check if message has a field.

        Args:
            name: Field name (supports dot notation)

        Returns:
            True if field exists
        """
        return self.get_field(name) is not None

    def field_names(self, include_nested: bool = False) -> list[str]:
        """Get all field names.

        Args:
            include_nested: Whether to include nested field names with dot notation

        Returns:
            List of field names
        """
        names = list(self.fields.keys())

        if include_nested:
            for name, field_obj in self.fields.items():
                if field_obj.field_type.name == "OBJECT" and isinstance(field_obj.value, dict):
                    nested = self._get_nested_names(field_obj.value, name)
                    names.extend(nested)

        return names

    def _get_nested_names(self, obj: dict, prefix: str) -> list[str]:
        """Get nested field names recursively."""
        names = []
        for key, value in obj.items():
            if key == "__type__":
                continue
            full_name = f"{prefix}.{key}"
            names.append(full_name)
            if isinstance(value, dict):
                names.extend(self._get_nested_names(value, full_name))
        return names

    def flatten(self) -> dict[str, Any]:
        """Flatten message to a dictionary with dot notation for nested fields.

        Returns:
            Flat dictionary suitable for CSV export
        """
        result = {
            "_index": self.index,
            "_offset": self.offset,
            "_type": self.type_hint or "",
        }

        for name, field_obj in self.fields.items():
            self._flatten_field(result, name, field_obj.value)

        return result

    def _flatten_field(self, result: dict, prefix: str, value: Any) -> None:
        """Recursively flatten a field value."""
        if value is None:
            result[prefix] = None
        elif isinstance(value, dict):
            type_hint = value.get("__type__")
            if type_hint:
                result[f"{prefix}.__type__"] = type_hint
            for key, val in value.items():
                if key == "__type__":
                    continue
                self._flatten_field(result, f"{prefix}.{key}", val)
        elif isinstance(value, (list, tuple)):
            # Join array elements with comma
            formatted = []
            for item in value:
                if isinstance(item, dict):
                    formatted.append(str(item))
                else:
                    formatted.append(str(item) if item is not None else "")
            result[prefix] = ", ".join(formatted)
        elif isinstance(value, bytes):
            result[prefix] = value.hex()
        else:
            result[prefix] = value

    def matches_type(self, type_pattern: str) -> bool:
        """Check if message type matches a pattern.

        Args:
            type_pattern: Type pattern (case-insensitive substring match)

        Returns:
            True if type matches
        """
        if not self.type_hint:
            return False
        return type_pattern.lower() in self.type_hint.lower()

    def __str__(self) -> str:
        """String representation."""
        type_str = self.type_hint or "unknown"
        return f"Message[{self.index}] {type_str} ({len(self.fields)} fields)"
