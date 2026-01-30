"""Service for filtering Chronicle Queue messages."""

from dataclasses import dataclass, field
from typing import Any, Callable

from ..models.message import Message
from ..models.field import FieldType


@dataclass
class FilterCriteria:
    """Criteria for filtering messages."""

    # Type filter
    type_pattern: str | None = None
    type_exact_match: bool = False

    # Field existence filter
    required_fields: list[str] = field(default_factory=list)

    # Field value filters (field_name -> (operator, value))
    # Operators: "eq", "ne", "gt", "gte", "lt", "lte", "contains", "regex"
    field_filters: dict[str, tuple[str, Any]] = field(default_factory=dict)

    # Metadata filter
    include_metadata: bool = False

    def is_empty(self) -> bool:
        """Check if no filters are set."""
        return (
            self.type_pattern is None
            and not self.required_fields
            and not self.field_filters
        )


class FilterService:
    """Service for filtering messages based on criteria."""

    def __init__(self):
        """Initialize filter service."""
        self._operators: dict[str, Callable[[Any, Any], bool]] = {
            "eq": lambda a, b: a == b,
            "ne": lambda a, b: a != b,
            "gt": lambda a, b: a > b if self._comparable(a, b) else False,
            "gte": lambda a, b: a >= b if self._comparable(a, b) else False,
            "lt": lambda a, b: a < b if self._comparable(a, b) else False,
            "lte": lambda a, b: a <= b if self._comparable(a, b) else False,
            "contains": self._contains,
            "regex": self._regex_match,
        }

    @staticmethod
    def _comparable(a: Any, b: Any) -> bool:
        """Check if two values can be compared."""
        try:
            _ = a < b
            return True
        except TypeError:
            return False

    @staticmethod
    def _contains(value: Any, pattern: Any) -> bool:
        """Check if value contains pattern."""
        if value is None:
            return False
        return str(pattern).lower() in str(value).lower()

    @staticmethod
    def _regex_match(value: Any, pattern: str) -> bool:
        """Check if value matches regex pattern."""
        import re

        if value is None:
            return False
        try:
            return re.search(pattern, str(value), re.IGNORECASE) is not None
        except re.error:
            return False

    def filter_messages(
        self, messages: list[Message], criteria: FilterCriteria
    ) -> list[Message]:
        """Filter messages based on criteria.

        Args:
            messages: Messages to filter
            criteria: Filter criteria

        Returns:
            List of messages matching all criteria
        """
        if criteria.is_empty():
            # Only filter by metadata if no other criteria
            if not criteria.include_metadata:
                return [m for m in messages if not m.is_metadata]
            return messages

        results = []

        for msg in messages:
            # Skip metadata if not included
            if msg.is_metadata and not criteria.include_metadata:
                continue

            # Check type filter
            if criteria.type_pattern:
                if not self._matches_type(msg, criteria.type_pattern, criteria.type_exact_match):
                    continue

            # Check required fields
            if criteria.required_fields:
                if not self._has_required_fields(msg, criteria.required_fields):
                    continue

            # Check field value filters
            if criteria.field_filters:
                if not self._matches_field_filters(msg, criteria.field_filters):
                    continue

            results.append(msg)

        return results

    def _matches_type(self, msg: Message, pattern: str, exact: bool) -> bool:
        """Check if message type matches."""
        if not msg.type_hint:
            return False

        if exact:
            return msg.type_hint == pattern
        return pattern.lower() in msg.type_hint.lower()

    def _has_required_fields(self, msg: Message, fields: list[str]) -> bool:
        """Check if message has all required fields."""
        for field_name in fields:
            if not msg.has_field(field_name):
                return False
        return True

    def _matches_field_filters(
        self, msg: Message, filters: dict[str, tuple[str, Any]]
    ) -> bool:
        """Check if message matches all field filters."""
        for field_name, (operator, expected) in filters.items():
            field = msg.get_field(field_name)

            if field is None:
                return False

            op_func = self._operators.get(operator)
            if op_func is None:
                continue

            if not op_func(field.value, expected):
                return False

        return True

    def filter_by_type(
        self, messages: list[Message], type_pattern: str, exact: bool = False
    ) -> list[Message]:
        """Filter messages by type.

        Args:
            messages: Messages to filter
            type_pattern: Type pattern to match
            exact: Require exact match

        Returns:
            Matching messages
        """
        criteria = FilterCriteria(type_pattern=type_pattern, type_exact_match=exact)
        return self.filter_messages(messages, criteria)

    def filter_by_field_exists(
        self, messages: list[Message], field_name: str
    ) -> list[Message]:
        """Filter messages that have a specific field.

        Args:
            messages: Messages to filter
            field_name: Field that must exist

        Returns:
            Messages with the field
        """
        criteria = FilterCriteria(required_fields=[field_name])
        return self.filter_messages(messages, criteria)

    def filter_by_field_value(
        self,
        messages: list[Message],
        field_name: str,
        operator: str,
        value: Any,
    ) -> list[Message]:
        """Filter messages by field value.

        Args:
            messages: Messages to filter
            field_name: Field to check
            operator: Comparison operator
            value: Value to compare against

        Returns:
            Matching messages
        """
        criteria = FilterCriteria(field_filters={field_name: (operator, value)})
        return self.filter_messages(messages, criteria)

    def combine_filters(
        self, messages: list[Message], *criteria_list: FilterCriteria
    ) -> list[Message]:
        """Apply multiple filter criteria (AND logic).

        Args:
            messages: Messages to filter
            criteria_list: Multiple criteria to apply

        Returns:
            Messages matching all criteria
        """
        result = messages
        for criteria in criteria_list:
            result = self.filter_messages(result, criteria)
        return result
