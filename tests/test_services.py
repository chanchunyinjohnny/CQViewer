"""Tests for services."""

import pytest
import tempfile
from pathlib import Path
from cqviewer.models.message import Message
from cqviewer.services.search_service import SearchService
from cqviewer.services.filter_service import FilterService, FilterCriteria
from cqviewer.services.export_service import ExportService


def create_test_message(
    index: int,
    type_hint: str | None = None,
    fields: dict | None = None,
) -> Message:
    """Helper to create test messages."""
    return Message.from_parsed(
        index=index,
        offset=index * 100,
        type_hint=type_hint,
        fields_dict=fields or {},
    )


class TestSearchService:
    """Tests for SearchService."""

    @pytest.fixture
    def service(self):
        return SearchService()

    @pytest.fixture
    def messages(self):
        return [
            create_test_message(0, "!types.Order", {"customerId": "C001", "amount": 100}),
            create_test_message(1, "!types.Order", {"customerId": "C002", "amount": 200}),
            create_test_message(2, "!types.Customer", {"name": "John", "email": "john@example.com"}),
            create_test_message(3, "!types.Customer", {"name": "Jane", "email": "jane@example.com"}),
            create_test_message(4, "!types.Product", {"name": "Widget", "price": 19.99}),
        ]

    def test_search_by_field_name(self, service, messages):
        """Test searching by field name."""
        results = service.search_by_field_name(messages, "customerId")
        assert len(results) == 2
        assert all(m.type_hint == "!types.Order" for m in results)

    def test_search_by_field_name_substring(self, service, messages):
        """Test searching by partial field name."""
        results = service.search_by_field_name(messages, "customer")
        assert len(results) == 2

    def test_search_by_field_name_exact(self, service, messages):
        """Test searching by exact field name."""
        results = service.search_by_field_name(messages, "customer", exact_match=True)
        assert len(results) == 0  # "customer" != "customerId"

    def test_search_by_field_value(self, service, messages):
        """Test searching by field value."""
        results = service.search_by_field_value(messages, "C001")
        assert len(results) == 1
        assert results[0].index == 0

    def test_search_by_field_value_regex(self, service, messages):
        """Test searching by regex pattern."""
        results = service.search_by_field_value(messages, r"C00\d")
        assert len(results) == 2

    def test_search_by_field_value_case_insensitive(self, service, messages):
        """Test case-insensitive search."""
        results = service.search_by_field_value(messages, "john", case_sensitive=False)
        assert len(results) == 1

    def test_search_by_field_value_specific_field(self, service, messages):
        """Test searching specific field."""
        results = service.search_by_field_value(messages, "John", field_name="name")
        assert len(results) == 1
        assert results[0].index == 2

    def test_search_by_type(self, service, messages):
        """Test searching by type."""
        results = service.search_by_type(messages, "Order")
        assert len(results) == 2

    def test_search_by_type_exact(self, service, messages):
        """Test searching by exact type."""
        results = service.search_by_type(messages, "!types.Order", exact_match=True)
        assert len(results) == 2

    def test_search_combined(self, service, messages):
        """Test combined search."""
        # Should find Order types and messages with "name" field
        results = service.search_combined(messages, "name")
        assert len(results) >= 2  # Customer and Product have "name" field

    def test_get_unique_field_values(self, service, messages):
        """Test getting unique field values."""
        values = service.get_unique_field_values(messages, "customerId")
        assert len(values) == 2
        assert "C001" in values
        assert "C002" in values

    def test_get_field_values(self, service, messages):
        """Test getting field values with messages."""
        results = service.get_field_values(messages, "customerId")
        assert len(results) == 2
        assert results[0][0].index == 0
        assert results[0][1] == "C001"
        assert results[1][1] == "C002"

    def test_get_field_values_missing_field(self, service, messages):
        """Test getting values for a field not present in any message."""
        results = service.get_field_values(messages, "nonexistent")
        assert len(results) == 0

    def test_search_by_field_value_invalid_regex(self, service, messages):
        """Test that invalid regex falls back to literal search."""
        # "[" is invalid regex; should be escaped and treated as literal
        results = service.search_by_field_value(messages, "[invalid")
        assert isinstance(results, list)

    def test_search_combined_types_only(self, service, messages):
        """Test combined search with only types enabled."""
        results = service.search_combined(
            messages, "Order",
            search_field_names=False,
            search_field_values=False,
            search_types=True,
        )
        assert len(results) == 2
        assert all(m.type_hint == "!types.Order" for m in results)

    def test_search_combined_deduplicates(self, service, messages):
        """Test combined search doesn't return duplicates."""
        # "name" matches both field name and field value for Customer/Product
        results = service.search_combined(messages, "name")
        indices = [m.index for m in results]
        assert len(indices) == len(set(indices))

    def test_search_by_field_value_nested(self, service):
        """Test searching nested object values."""
        msgs = [
            create_test_message(0, None, {"data": {"inner": "target"}}),
            create_test_message(1, None, {"other": "no match"}),
        ]
        results = service.search_by_field_value(msgs, "target")
        assert len(results) == 1
        assert results[0].index == 0

    def test_search_by_field_value_in_array(self, service):
        """Test searching values inside arrays."""
        msgs = [
            create_test_message(0, None, {"tags": ["alpha", "beta"]}),
            create_test_message(1, None, {"tags": ["gamma"]}),
        ]
        results = service.search_by_field_value(msgs, "alpha")
        assert len(results) == 1
        assert results[0].index == 0

    def test_get_unique_field_values_unhashable(self, service):
        """Test that unhashable values are excluded."""
        msgs = [
            create_test_message(0, None, {"data": {"nested": "dict"}}),
            create_test_message(1, None, {"data": "simple"}),
        ]
        values = service.get_unique_field_values(msgs, "data")
        # Only "simple" should be included (dict is unhashable)
        assert "simple" in values


class TestFilterService:
    """Tests for FilterService."""

    @pytest.fixture
    def service(self):
        return FilterService()

    @pytest.fixture
    def messages(self):
        return [
            create_test_message(0, "!types.Order", {"customerId": "C001", "amount": 100}),
            create_test_message(1, "!types.Order", {"customerId": "C002", "amount": 200}),
            create_test_message(2, "!types.Customer", {"name": "John"}),
            create_test_message(3, None, {"data": "test"}),  # No type
        ]

    def test_filter_by_type(self, service, messages):
        """Test filtering by type."""
        results = service.filter_by_type(messages, "Order")
        assert len(results) == 2

    def test_filter_by_type_exact(self, service, messages):
        """Test filtering by exact type."""
        results = service.filter_by_type(messages, "!types.Order", exact=True)
        assert len(results) == 2

    def test_filter_by_field_exists(self, service, messages):
        """Test filtering by field existence."""
        results = service.filter_by_field_exists(messages, "customerId")
        assert len(results) == 2

    def test_filter_by_field_value_eq(self, service, messages):
        """Test filtering by field value equality."""
        results = service.filter_by_field_value(messages, "customerId", "eq", "C001")
        assert len(results) == 1
        assert results[0].index == 0

    def test_filter_by_field_value_gt(self, service, messages):
        """Test filtering by field value greater than."""
        results = service.filter_by_field_value(messages, "amount", "gt", 150)
        assert len(results) == 1
        assert results[0].index == 1

    def test_filter_by_field_value_contains(self, service, messages):
        """Test filtering by field value contains."""
        results = service.filter_by_field_value(messages, "customerId", "contains", "C00")
        assert len(results) == 2

    def test_filter_messages_combined(self, service, messages):
        """Test filtering with multiple criteria."""
        criteria = FilterCriteria(
            type_pattern="Order",
            field_filters={"amount": ("gte", 100)},
        )
        results = service.filter_messages(messages, criteria)
        assert len(results) == 2

    def test_filter_empty_criteria(self, service, messages):
        """Test with empty criteria returns all (non-metadata)."""
        criteria = FilterCriteria()
        results = service.filter_messages(messages, criteria)
        assert len(results) == 4

    def test_filter_by_field_value_ne(self, service, messages):
        """Test filtering by field value not-equal."""
        results = service.filter_by_field_value(messages, "customerId", "ne", "C001")
        assert len(results) == 1
        assert results[0].index == 1

    def test_filter_by_field_value_lte(self, service, messages):
        """Test filtering by field value less-than-or-equal."""
        results = service.filter_by_field_value(messages, "amount", "lte", 100)
        assert len(results) == 1
        assert results[0].index == 0

    def test_filter_by_field_value_lt(self, service, messages):
        """Test filtering by field value less-than."""
        results = service.filter_by_field_value(messages, "amount", "lt", 200)
        assert len(results) == 1
        assert results[0].index == 0

    def test_filter_by_field_value_gte(self, service, messages):
        """Test filtering by field value greater-than-or-equal."""
        results = service.filter_by_field_value(messages, "amount", "gte", 200)
        assert len(results) == 1
        assert results[0].index == 1

    def test_filter_by_field_value_regex(self, service, messages):
        """Test filtering by regex match."""
        results = service.filter_by_field_value(messages, "customerId", "regex", r"C00\d")
        assert len(results) == 2

    def test_filter_by_field_value_regex_invalid(self, service, messages):
        """Test filtering with invalid regex returns no matches."""
        results = service.filter_by_field_value(messages, "customerId", "regex", "[invalid")
        assert len(results) == 0

    def test_filter_metadata_excluded_by_default(self, service):
        """Test metadata messages are excluded by default."""
        msgs = [
            create_test_message(0, "!types.Order", {"x": 1}),
            Message.from_parsed(index=1, offset=100, type_hint=None,
                                fields_dict={"meta": "data"}, is_metadata=True),
        ]
        criteria = FilterCriteria()
        results = service.filter_messages(msgs, criteria)
        assert len(results) == 1
        assert results[0].index == 0

    def test_filter_metadata_included(self, service):
        """Test including metadata messages."""
        msgs = [
            create_test_message(0, "!types.Order", {"x": 1}),
            Message.from_parsed(index=1, offset=100, type_hint=None,
                                fields_dict={"meta": "data"}, is_metadata=True),
        ]
        criteria = FilterCriteria(include_metadata=True)
        results = service.filter_messages(msgs, criteria)
        assert len(results) == 2

    def test_filter_field_missing_returns_empty(self, service, messages):
        """Test filtering by value on missing field excludes message."""
        results = service.filter_by_field_value(messages, "nonexistent", "eq", "x")
        assert len(results) == 0

    def test_combine_filters(self, service, messages):
        """Test combining multiple filter criteria."""
        criteria1 = FilterCriteria(type_pattern="Order")
        criteria2 = FilterCriteria(field_filters={"amount": ("gt", 150)})
        results = service.combine_filters(messages, criteria1, criteria2)
        assert len(results) == 1
        assert results[0].index == 1

    def test_criteria_is_empty(self):
        """Test FilterCriteria.is_empty()."""
        assert FilterCriteria().is_empty()
        assert not FilterCriteria(type_pattern="Order").is_empty()
        assert not FilterCriteria(required_fields=["x"]).is_empty()
        assert not FilterCriteria(field_filters={"x": ("eq", 1)}).is_empty()

    def test_filter_contains_case_insensitive(self, service, messages):
        """Test contains operator is case-insensitive."""
        results = service.filter_by_field_value(messages, "customerId", "contains", "c00")
        assert len(results) == 2

    def test_filter_contains_on_none(self, service):
        """Test contains operator on None value returns False."""
        msgs = [create_test_message(0, None, {"val": None})]
        results = service.filter_by_field_value(msgs, "val", "contains", "x")
        assert len(results) == 0


class TestExportService:
    """Tests for ExportService."""

    @pytest.fixture
    def service(self):
        return ExportService()

    @pytest.fixture
    def messages(self):
        return [
            create_test_message(0, "!types.Order", {"customerId": "C001", "amount": 100}),
            create_test_message(1, "!types.Order", {"customerId": "C002", "amount": 200}),
        ]

    def test_export_to_csv_string(self, service, messages):
        """Test exporting to CSV string."""
        csv = service.export_to_csv(messages)
        assert "_index" in csv
        assert "_type" in csv
        assert "customerId" in csv
        assert "C001" in csv
        assert "C002" in csv

    def test_export_with_selected_fields(self, service, messages):
        """Test exporting with specific fields."""
        csv = service.export_to_csv(messages, fields=["customerId"])
        assert "customerId" in csv
        assert "amount" not in csv  # Not selected

    def test_export_without_index(self, service, messages):
        """Test exporting without index column."""
        csv = service.export_to_csv(messages, include_index=False)
        lines = csv.strip().split("\n")
        header = lines[0]
        assert "_index" not in header

    def test_get_available_fields(self, service, messages):
        """Test getting available fields."""
        fields = service.get_available_fields(messages)
        assert "customerId" in fields
        assert "amount" in fields

    def test_get_field_coverage(self, service, messages):
        """Test getting field coverage."""
        count, total = service.get_field_coverage(messages, "customerId")
        assert count == 2
        assert total == 2

    def test_preview_export(self, service, messages):
        """Test preview export."""
        preview = service.preview_export(messages, limit=1)
        assert len(preview) == 1
        assert "_index" in preview[0]

    def test_export_nested_fields(self, service):
        """Test exporting nested fields."""
        messages = [
            create_test_message(
                0, "!types.User", {"name": "John", "address": {"city": "NYC", "zip": "10001"}}
            ),
        ]
        csv = service.export_to_csv(messages)
        assert "address.city" in csv
        assert "NYC" in csv

    def test_export_array_fields(self, service):
        """Test exporting array fields."""
        messages = [
            create_test_message(0, "!types.Item", {"tags": ["a", "b", "c"]}),
        ]
        csv = service.export_to_csv(messages)
        assert "a, b, c" in csv

    def test_export_null_values(self, service):
        """Test exporting null values."""
        messages = [
            create_test_message(0, "!types.Test", {"value": None, "other": "text"}),
        ]
        csv = service.export_to_csv(messages)
        # Null values should be empty in CSV
        lines = csv.strip().split("\n")
        assert len(lines) == 2  # Header + 1 row

    def test_export_empty_messages(self, service):
        """Test exporting empty message list returns empty string."""
        csv = service.export_to_csv([])
        assert csv == ""

    def test_export_to_file(self, service, messages):
        """Test exporting to a file."""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            tmp_path = Path(f.name)

        try:
            csv_content = service.export_to_csv(messages, output_path=tmp_path)
            assert tmp_path.exists()
            file_content = tmp_path.read_text(encoding="utf-8")
            # Normalize line endings for comparison (csv module uses \r\n)
            assert file_content.replace("\r\n", "\n") == csv_content.replace("\r\n", "\n")
            assert "C001" in file_content
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_export_with_offset(self, service, messages):
        """Test exporting with offset column."""
        csv = service.export_to_csv(messages, include_offset=True)
        lines = csv.strip().split("\n")
        header = lines[0]
        assert "_offset" in header

    def test_export_without_type(self, service, messages):
        """Test exporting without type column."""
        csv = service.export_to_csv(messages, include_type=False)
        lines = csv.strip().split("\n")
        header = lines[0]
        assert "_type" not in header

    def test_export_bool_value(self, service):
        """Test exporting boolean values as lowercase."""
        messages = [create_test_message(0, None, {"flag": True, "other": False})]
        csv = service.export_to_csv(messages)
        # Booleans are flattened, they should appear as "true"/"false"
        # (flatten passes through the raw value, _format_value handles it)
        assert "true" in csv.lower()

    def test_get_field_coverage_partial(self, service):
        """Test field coverage when not all messages have the field."""
        messages = [
            create_test_message(0, None, {"a": 1, "b": 2}),
            create_test_message(1, None, {"a": 3}),
        ]
        count, total = service.get_field_coverage(messages, "b")
        assert count == 1
        assert total == 2

    def test_preview_export_limits_rows(self, service):
        """Test preview limits the number of rows."""
        messages = [create_test_message(i, None, {"x": i}) for i in range(10)]
        preview = service.preview_export(messages, limit=3)
        assert len(preview) == 3
