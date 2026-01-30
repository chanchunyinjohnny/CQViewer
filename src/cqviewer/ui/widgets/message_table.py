"""Message table widget for displaying Chronicle Queue messages."""

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ...models.message import Message


class MessageTable(ttk.Frame):
    """Table widget for displaying messages with pagination."""

    def __init__(
        self,
        parent: tk.Widget,
        on_select: Callable[[Message], None] | None = None,
        page_size: int = 50,
    ):
        """Initialize message table.

        Args:
            parent: Parent widget
            on_select: Callback when message is selected
            page_size: Number of rows per page
        """
        super().__init__(parent)
        self._on_select = on_select
        self._page_size = page_size
        self._messages: list[Message] = []
        self._filtered_messages: list[Message] = []
        self._current_page = 0
        self._columns: list[str] = []

        self._setup_style()
        self._setup_ui()

    def _setup_style(self) -> None:
        """Configure table styling with alternating row colors and borders."""
        style = ttk.Style()

        # Configure Treeview colors
        style.configure(
            "MessageTable.Treeview",
            background="#ffffff",
            foreground="#000000",
            fieldbackground="#ffffff",
            rowheight=25,
        )

        # Configure header style
        style.configure(
            "MessageTable.Treeview.Heading",
            background="#e0e0e0",
            foreground="#000000",
            font=("TkDefaultFont", 10, "bold"),
            relief="solid",
            borderwidth=1,
        )

        # Map colors for selection and alternating rows
        style.map(
            "MessageTable.Treeview",
            background=[("selected", "#0078d7")],
            foreground=[("selected", "#ffffff")],
        )

        # Define tags for alternating row colors
        self._row_tags = ("evenrow", "oddrow")

    def _setup_ui(self) -> None:
        """Set up the table UI."""
        # Configure grid
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Create treeview with scrollbars
        tree_frame = ttk.Frame(self)
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        # Scrollbars
        y_scroll = ttk.Scrollbar(tree_frame, orient="vertical")
        y_scroll.grid(row=0, column=1, sticky="ns")

        x_scroll = ttk.Scrollbar(tree_frame, orient="horizontal")
        x_scroll.grid(row=1, column=0, sticky="ew")

        # Treeview with custom style
        self._tree = ttk.Treeview(
            tree_frame,
            show="headings",
            selectmode="browse",
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
            style="MessageTable.Treeview",
        )
        self._tree.grid(row=0, column=0, sticky="nsew")

        # Configure alternating row colors
        self._tree.tag_configure("evenrow", background="#ffffff")
        self._tree.tag_configure("oddrow", background="#f5f5f5")

        y_scroll.config(command=self._tree.yview)
        x_scroll.config(command=self._tree.xview)

        # Bind selection event
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self._tree.bind("<Double-1>", self._on_double_click)

        # Pagination controls
        self._pagination_frame = ttk.Frame(self)
        self._pagination_frame.grid(row=1, column=0, sticky="ew", pady=5)

        self._prev_btn = ttk.Button(
            self._pagination_frame, text="< Previous", command=self._prev_page
        )
        self._prev_btn.pack(side="left", padx=5)

        self._page_label = ttk.Label(self._pagination_frame, text="Page 0 of 0")
        self._page_label.pack(side="left", padx=10)

        self._next_btn = ttk.Button(
            self._pagination_frame, text="Next >", command=self._next_page
        )
        self._next_btn.pack(side="left", padx=5)

        # Page size selector
        ttk.Label(self._pagination_frame, text="   Rows per page:").pack(side="left", padx=5)
        self._page_size_var = tk.StringVar(value=str(self._page_size))
        page_size_combo = ttk.Combobox(
            self._pagination_frame,
            textvariable=self._page_size_var,
            values=["25", "50", "100", "200"],
            width=5,
            state="readonly",
        )
        page_size_combo.pack(side="left")
        page_size_combo.bind("<<ComboboxSelected>>", self._on_page_size_change)

        # Message count
        self._count_label = ttk.Label(self._pagination_frame, text="")
        self._count_label.pack(side="right", padx=10)

    def set_columns(self, columns: list[str]) -> None:
        """Set table columns.

        Args:
            columns: List of column names
        """
        self._columns = columns

        # Configure treeview columns
        self._tree["columns"] = columns
        for col in columns:
            # Add column header with sort functionality
            self._tree.heading(
                col,
                text=col,
                command=lambda c=col: self._sort_by(c),
                anchor="w",  # Left align header text
            )
            # Set column width based on content, with separator effect
            width = max(120, len(col) * 12)
            self._tree.column(
                col,
                width=width,
                minwidth=60,
                anchor="w",  # Left align cell content
                stretch=True,
            )

    def set_messages(self, messages: list[Message]) -> None:
        """Set messages to display.

        Args:
            messages: List of messages
        """
        self._messages = messages
        self._filtered_messages = messages
        self._current_page = 0
        self._refresh_display()

    def set_filtered_messages(self, messages: list[Message]) -> None:
        """Set filtered messages to display.

        Args:
            messages: Filtered list of messages
        """
        self._filtered_messages = messages
        self._current_page = 0
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the table display."""
        # Clear existing items
        for item in self._tree.get_children():
            self._tree.delete(item)

        # Calculate pagination
        total = len(self._filtered_messages)
        total_pages = max(1, (total + self._page_size - 1) // self._page_size)
        start = self._current_page * self._page_size
        end = min(start + self._page_size, total)

        # Insert rows with alternating colors
        page_messages = self._filtered_messages[start:end]
        for i, msg in enumerate(page_messages):
            values = self._message_to_row(msg)
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            self._tree.insert("", "end", iid=str(msg.index), values=values, tags=(tag,))

        # Update pagination controls
        self._page_label.config(text=f"Page {self._current_page + 1} of {total_pages}")
        self._prev_btn.config(state="normal" if self._current_page > 0 else "disabled")
        self._next_btn.config(
            state="normal" if self._current_page < total_pages - 1 else "disabled"
        )

        # Update count label
        self._count_label.config(text=f"Showing {start + 1}-{end} of {total} messages")

    def _message_to_row(self, msg: Message) -> tuple:
        """Convert message to table row values."""
        values = []
        for col in self._columns:
            if col == "Index":
                values.append(msg.index)
            elif col == "Type":
                values.append(msg.type_hint or "")
            elif col == "Fields":
                values.append(len(msg.fields))
            else:
                # Try to get field value
                field = msg.get_field(col)
                if field:
                    values.append(field.format_value(max_length=50))
                else:
                    values.append("")
        return tuple(values)

    def _prev_page(self) -> None:
        """Go to previous page."""
        if self._current_page > 0:
            self._current_page -= 1
            self._refresh_display()

    def _next_page(self) -> None:
        """Go to next page."""
        total_pages = (len(self._filtered_messages) + self._page_size - 1) // self._page_size
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._refresh_display()

    def _on_page_size_change(self, event: tk.Event) -> None:
        """Handle page size change."""
        try:
            self._page_size = int(self._page_size_var.get())
            self._current_page = 0
            self._refresh_display()
        except ValueError:
            pass

    def _sort_by(self, column: str) -> None:
        """Sort messages by column."""
        # Toggle sort direction
        reverse = getattr(self, "_sort_reverse", False)
        self._sort_reverse = not reverse
        self._sort_column = column

        def get_sort_key(msg: Message):
            if column == "Index":
                return msg.index
            if column == "Type":
                return msg.type_hint or ""
            if column == "Fields":
                return len(msg.fields)
            field = msg.get_field(column)
            if field:
                return str(field.value) if field.value else ""
            return ""

        self._filtered_messages.sort(key=get_sort_key, reverse=reverse)
        self._refresh_display()

    def _on_tree_select(self, event: tk.Event) -> None:
        """Handle tree selection."""
        selection = self._tree.selection()
        if selection and self._on_select:
            try:
                index = int(selection[0])
                for msg in self._filtered_messages:
                    if msg.index == index:
                        self._on_select(msg)
                        break
            except (ValueError, IndexError):
                pass

    def _on_double_click(self, event: tk.Event) -> None:
        """Handle double-click to show details."""
        self._on_tree_select(event)

    def get_selected_message(self) -> Message | None:
        """Get currently selected message."""
        selection = self._tree.selection()
        if not selection:
            return None

        try:
            index = int(selection[0])
            for msg in self._filtered_messages:
                if msg.index == index:
                    return msg
        except (ValueError, IndexError):
            pass

        return None

    def clear(self) -> None:
        """Clear all messages from table."""
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._messages = []
        self._filtered_messages = []
        self._current_page = 0
        self._page_label.config(text="Page 0 of 0")
        self._count_label.config(text="")
