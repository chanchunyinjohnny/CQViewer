"""Filter bar widget for filtering messages."""

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ...services.filter_service import FilterCriteria


class FilterBar(ttk.Frame):
    """Filter bar widget with search and type filter."""

    def __init__(
        self,
        parent: tk.Widget,
        on_search: Callable[[str], None] | None = None,
        on_filter: Callable[[FilterCriteria], None] | None = None,
    ):
        """Initialize filter bar.

        Args:
            parent: Parent widget
            on_search: Callback for search queries
            on_filter: Callback for filter criteria changes
        """
        super().__init__(parent)
        self._on_search = on_search
        self._on_filter = on_filter
        self._types: list[str] = []
        self._fields: list[str] = []

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the filter bar UI."""
        # Search section
        search_frame = ttk.LabelFrame(self, text="Search", padding=5)
        search_frame.pack(side="left", fill="x", expand=True, padx=5)

        self._search_var = tk.StringVar()
        self._search_entry = ttk.Entry(search_frame, textvariable=self._search_var, width=30)
        self._search_entry.pack(side="left", padx=5)
        self._search_entry.bind("<Return>", self._do_search)

        self._search_btn = ttk.Button(search_frame, text="Search", command=self._do_search)
        self._search_btn.pack(side="left", padx=5)

        self._clear_search_btn = ttk.Button(
            search_frame, text="Clear", command=self._clear_search
        )
        self._clear_search_btn.pack(side="left")

        # Type filter section
        type_frame = ttk.LabelFrame(self, text="Type Filter", padding=5)
        type_frame.pack(side="left", padx=5)

        self._type_var = tk.StringVar(value="All Types")
        self._type_combo = ttk.Combobox(
            type_frame,
            textvariable=self._type_var,
            values=["All Types"],
            width=25,
            state="readonly",
        )
        self._type_combo.pack(side="left", padx=5)
        self._type_combo.bind("<<ComboboxSelected>>", self._on_type_change)

        # Field filter section
        field_frame = ttk.LabelFrame(self, text="Field Filter", padding=5)
        field_frame.pack(side="left", padx=5)

        ttk.Label(field_frame, text="Has field:").pack(side="left")

        self._field_var = tk.StringVar(value="")
        self._field_combo = ttk.Combobox(
            field_frame,
            textvariable=self._field_var,
            values=[""],
            width=20,
        )
        self._field_combo.pack(side="left", padx=5)
        self._field_combo.bind("<<ComboboxSelected>>", self._on_field_change)
        self._field_combo.bind("<Return>", self._on_field_change)

        # Apply button
        self._apply_btn = ttk.Button(self, text="Apply Filters", command=self._apply_filters)
        self._apply_btn.pack(side="left", padx=10)

        # Reset button
        self._reset_btn = ttk.Button(self, text="Reset", command=self._reset_filters)
        self._reset_btn.pack(side="left")

    def set_types(self, types: list[str]) -> None:
        """Set available type options.

        Args:
            types: List of type hints
        """
        self._types = types
        values = ["All Types"] + types
        self._type_combo["values"] = values
        self._type_var.set("All Types")

    def set_fields(self, fields: list[str]) -> None:
        """Set available field options.

        Args:
            fields: List of field names
        """
        self._fields = fields
        values = [""] + fields
        self._field_combo["values"] = values
        self._field_var.set("")

    def _do_search(self, event: tk.Event | None = None) -> None:
        """Execute search."""
        query = self._search_var.get().strip()
        if self._on_search:
            self._on_search(query)

    def _clear_search(self) -> None:
        """Clear search field."""
        self._search_var.set("")
        if self._on_search:
            self._on_search("")

    def _on_type_change(self, event: tk.Event | None = None) -> None:
        """Handle type selection change."""
        self._apply_filters()

    def _on_field_change(self, event: tk.Event | None = None) -> None:
        """Handle field selection change."""
        self._apply_filters()

    def _apply_filters(self) -> None:
        """Apply current filter settings."""
        criteria = self.get_criteria()
        if self._on_filter:
            self._on_filter(criteria)

    def _reset_filters(self) -> None:
        """Reset all filters to defaults."""
        self._search_var.set("")
        self._type_var.set("All Types")
        self._field_var.set("")
        self._apply_filters()

    def get_criteria(self) -> FilterCriteria:
        """Get current filter criteria.

        Returns:
            FilterCriteria based on current selections
        """
        type_pattern = None
        if self._type_var.get() != "All Types":
            type_pattern = self._type_var.get()

        required_fields = []
        if self._field_var.get():
            required_fields = [self._field_var.get()]

        return FilterCriteria(
            type_pattern=type_pattern,
            required_fields=required_fields,
        )

    def get_search_query(self) -> str:
        """Get current search query."""
        return self._search_var.get().strip()
