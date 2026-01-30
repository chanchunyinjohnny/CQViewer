"""Tests for services."""

import pytest
from io import StringIO
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
