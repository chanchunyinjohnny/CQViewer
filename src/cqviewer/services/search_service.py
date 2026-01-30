"""Service for searching Chronicle Queue messages."""

import re
from typing import Any

from ..models.message import Message
from ..models.field import FieldType


class SearchService:
    """Service for searching messages by field names, values, and types."""

    def search_by_field_name(
        self, messages: list[Message], field_name: str, exact_match: bool = False
    ) -> list[Message]:
        """Find messages that have a specific field.

        Args:
            messages: Messages to search
            field_name: Field name to search for
            exact_match: If True, require exact name match; otherwise substring

        Returns:
            List of matching messages
        """
        results = []
        field_lower = field_name.lower()

        for msg in messages:
            all_names = msg.field_names(include_nested=True)
            for name in all_names:
                if exact_match:
                    if name == field_name:
                        results.append(msg)
                        break
                else:
                    if field_lower in name.lower():
                        results.append(msg)
                        break

        return results

    def search_by_field_value(
        self,
        messages: list[Message],
        value_pattern: str,
        field_name: str | None = None,
        case_sensitive: bool = False,
    ) -> list[Message]:
        """Find messages where a field value matches a pattern.

        Args:
            messages: Messages to search
            value_pattern: Pattern to match (substring or regex)
            field_name: Optional specific field to search (None = all fields)
            case_sensitive: Whether search is case-sensitive

        Returns:
            List of matching messages
        """
        results = []

        # Compile regex pattern
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(value_pattern, flags)
        except re.error:
            # Fall back to literal string search if invalid regex
            pattern = re.compile(re.escape(value_pattern), flags)

        for msg in messages:
            if field_name:
                # Search specific field
                field = msg.get_field(field_name)
                if field and self._value_matches(field.value, pattern):
                    results.append(msg)
            else:
                # Search all fields
                if self._any_field_matches(msg, pattern):
                    results.append(msg)

        return results

    def _value_matches(self, value: Any, pattern: re.Pattern) -> bool:
        """Check if a value matches the pattern."""
        if value is None:
            return False

        if isinstance(value, str):
            return pattern.search(value) is not None

        if isinstance(value, (int, float)):
            return pattern.search(str(value)) is not None

        if isinstance(value, dict):
            # Search nested object values
            for v in value.values():
                if self._value_matches(v, pattern):
                    return True
            return False

        if isinstance(value, (list, tuple)):
            # Search array elements
            for item in value:
                if self._value_matches(item, pattern):
                    return True
            return False

        # Try string conversion for other types
        try:
            return pattern.search(str(value)) is not None
        except Exception:
            return False

    def _any_field_matches(self, msg: Message, pattern: re.Pattern) -> bool:
        """Check if any field in message matches pattern."""
        for field in msg.fields.values():
            if self._value_matches(field.value, pattern):
                return True
        return False

    def search_by_type(
        self, messages: list[Message], type_pattern: str, exact_match: bool = False
    ) -> list[Message]:
        """Find messages of a specific type.

        Args:
            messages: Messages to search
            type_pattern: Type name or pattern
            exact_match: If True, require exact type match

        Returns:
            List of matching messages
        """
        results = []
        type_lower = type_pattern.lower()

        for msg in messages:
            if not msg.type_hint:
                continue

            if exact_match:
                if msg.type_hint == type_pattern:
                    results.append(msg)
            else:
                if type_lower in msg.type_hint.lower():
                    results.append(msg)

        return results

    def search_combined(
        self,
        messages: list[Message],
        query: str,
        search_field_names: bool = True,
        search_field_values: bool = True,
        search_types: bool = True,
    ) -> list[Message]:
        """Combined search across field names, values, and types.

        Args:
            messages: Messages to search
            query: Search query
            search_field_names: Include field name matches
            search_field_values: Include field value matches
            search_types: Include type matches

        Returns:
            List of unique matching messages (preserving order)
        """
        seen_indices = set()
        results = []

        # Search types first (usually most specific)
        if search_types:
            for msg in self.search_by_type(messages, query):
                if msg.index not in seen_indices:
                    seen_indices.add(msg.index)
                    results.append(msg)

        # Search field names
        if search_field_names:
            for msg in self.search_by_field_name(messages, query):
                if msg.index not in seen_indices:
                    seen_indices.add(msg.index)
                    results.append(msg)

        # Search field values
        if search_field_values:
            for msg in self.search_by_field_value(messages, query):
                if msg.index not in seen_indices:
                    seen_indices.add(msg.index)
                    results.append(msg)

        return results

    def get_field_values(
        self, messages: list[Message], field_name: str
    ) -> list[tuple[Message, Any]]:
        """Get all values for a specific field across messages.

        Args:
            messages: Messages to search
            field_name: Field name to extract

        Returns:
            List of (message, value) tuples
        """
        results = []

        for msg in messages:
            field = msg.get_field(field_name)
            if field is not None:
                results.append((msg, field.value))

        return results

    def get_unique_field_values(self, messages: list[Message], field_name: str) -> list[Any]:
        """Get unique values for a field.

        Args:
            messages: Messages to search
            field_name: Field name

        Returns:
            List of unique values (unhashable values excluded)
        """
        values = set()

        for msg in messages:
            field = msg.get_field(field_name)
            if field is not None and field.value is not None:
                try:
                    # Only add hashable values
                    values.add(field.value)
                except TypeError:
                    pass

        return sorted(values, key=lambda x: str(x))
