"""Service for exporting Chronicle Queue data to CSV."""

import csv
from io import StringIO
from pathlib import Path
from typing import Any

from ..models.message import Message


class ExportService:
    """Service for exporting messages to CSV format."""

    def export_to_csv(
        self,
        messages: list[Message],
        output_path: str | Path | None = None,
        fields: list[str] | None = None,
        include_index: bool = True,
        include_offset: bool = False,
        include_type: bool = True,
    ) -> str:
        """Export messages to CSV format.

        Args:
            messages: Messages to export
            output_path: Path to write CSV file (None = return as string)
            fields: Specific fields to include (None = all fields)
            include_index: Include message index column
            include_offset: Include file offset column
            include_type: Include type hint column

        Returns:
            CSV content as string
        """
        if not messages:
            return ""

        # Determine columns
        columns = self._build_columns(
            messages, fields, include_index, include_offset, include_type
        )

        # Build rows
        rows = []
        for msg in messages:
            row = self._build_row(msg, columns, include_index, include_offset, include_type)
            rows.append(row)

        # Write CSV
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

        csv_content = output.getvalue()

        # Write to file if path provided
        if output_path:
            Path(output_path).write_text(csv_content, encoding="utf-8")

        return csv_content

    def _build_columns(
        self,
        messages: list[Message],
        fields: list[str] | None,
        include_index: bool,
        include_offset: bool,
        include_type: bool,
    ) -> list[str]:
        """Build list of CSV columns."""
        columns = []

        # Metadata columns
        if include_index:
            columns.append("_index")
        if include_offset:
            columns.append("_offset")
        if include_type:
            columns.append("_type")

        # Field columns
        if fields:
            # Use specified fields
            columns.extend(fields)
        else:
            # Collect all unique fields from messages
            all_fields = set()
            for msg in messages:
                flat = msg.flatten()
                for key in flat:
                    if not key.startswith("_"):
                        all_fields.add(key)
            columns.extend(sorted(all_fields))

        return columns

    def _build_row(
        self,
        msg: Message,
        columns: list[str],
        include_index: bool,
        include_offset: bool,
        include_type: bool,
    ) -> dict[str, Any]:
        """Build a CSV row for a message."""
        flat = msg.flatten()
        row = {}

        for col in columns:
            if col == "_index" and include_index:
                row[col] = msg.index
            elif col == "_offset" and include_offset:
                row[col] = msg.offset
            elif col == "_type" and include_type:
                row[col] = msg.type_hint or ""
            elif col in flat:
                value = flat[col]
                row[col] = self._format_value(value)
            else:
                row[col] = ""

        return row

    def _format_value(self, value: Any) -> str:
        """Format a value for CSV output."""
        if value is None:
            return ""
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, bytes):
            return value.hex()
        if isinstance(value, (list, tuple)):
            return ", ".join(str(v) if v is not None else "" for v in value)
        if isinstance(value, dict):
            # Shouldn't happen after flattening, but handle gracefully
            return str(value)
        return str(value)

    def get_available_fields(self, messages: list[Message]) -> list[str]:
        """Get list of all available fields for export.

        Args:
            messages: Messages to analyze

        Returns:
            Sorted list of field names (with dot notation for nested)
        """
        all_fields = set()
        for msg in messages:
            flat = msg.flatten()
            for key in flat:
                if not key.startswith("_"):
                    all_fields.add(key)
        return sorted(all_fields)

    def get_field_coverage(
        self, messages: list[Message], field_name: str
    ) -> tuple[int, int]:
        """Get coverage statistics for a field.

        Args:
            messages: Messages to analyze
            field_name: Field to check

        Returns:
            Tuple of (messages_with_field, total_messages)
        """
        count = 0
        for msg in messages:
            if msg.has_field(field_name):
                count += 1
        return count, len(messages)

    def preview_export(
        self,
        messages: list[Message],
        fields: list[str] | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Preview export data without writing.

        Args:
            messages: Messages to preview
            fields: Fields to include
            limit: Number of rows to preview

        Returns:
            List of row dictionaries
        """
        preview_messages = messages[:limit]
        columns = self._build_columns(
            preview_messages,
            fields,
            include_index=True,
            include_offset=False,
            include_type=True,
        )

        rows = []
        for msg in preview_messages:
            row = self._build_row(
                msg, columns,
                include_index=True,
                include_offset=False,
                include_type=True,
            )
            rows.append(row)

        return rows
