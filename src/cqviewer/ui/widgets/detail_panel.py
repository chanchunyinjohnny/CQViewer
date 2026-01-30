"""Detail panel widget for showing message details."""

import json
import tkinter as tk
from tkinter import ttk

from ...models.message import Message


class DetailPanel(ttk.Frame):
    """Panel for displaying detailed message information."""

    def __init__(self, parent: tk.Widget):
        """Initialize detail panel.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._current_message: Message | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Header with message info
        header_frame = ttk.Frame(self)
        header_frame.grid(row=0, column=0, sticky="ew", pady=5)

        self._header_label = ttk.Label(
            header_frame, text="Select a message to view details", font=("TkDefaultFont", 10, "bold")
        )
        self._header_label.pack(side="left", padx=5)

        # Notebook for different views
        self._notebook = ttk.Notebook(self)
        self._notebook.grid(row=1, column=0, sticky="nsew")

        # Tree view tab
        tree_frame = ttk.Frame(self._notebook)
        self._notebook.add(tree_frame, text="Tree View")

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical")
        tree_scroll.pack(side="right", fill="y")

        self._tree = ttk.Treeview(tree_frame, yscrollcommand=tree_scroll.set)
        self._tree.pack(side="left", fill="both", expand=True)
        tree_scroll.config(command=self._tree.yview)

        self._tree.heading("#0", text="Field / Value")
        self._tree.column("#0", width=400)

        # JSON view tab
        json_frame = ttk.Frame(self._notebook)
        self._notebook.add(json_frame, text="JSON View")

        json_scroll = ttk.Scrollbar(json_frame, orient="vertical")
        json_scroll.pack(side="right", fill="y")

        self._json_text = tk.Text(
            json_frame,
            wrap="none",
            yscrollcommand=json_scroll.set,
            font=("Courier", 10),
        )
        self._json_text.pack(side="left", fill="both", expand=True)
        json_scroll.config(command=self._json_text.yview)

        # Raw view tab
        raw_frame = ttk.Frame(self._notebook)
        self._notebook.add(raw_frame, text="Flat View")

        raw_scroll = ttk.Scrollbar(raw_frame, orient="vertical")
        raw_scroll.pack(side="right", fill="y")

        self._raw_text = tk.Text(
            raw_frame,
            wrap="word",
            yscrollcommand=raw_scroll.set,
            font=("Courier", 10),
        )
        self._raw_text.pack(side="left", fill="both", expand=True)
        raw_scroll.config(command=self._raw_text.yview)

    def show_message(self, message: Message) -> None:
        """Display message details.

        Args:
            message: Message to display
        """
        self._current_message = message

        # Update header
        type_str = message.type_hint or "Unknown Type"
        self._header_label.config(
            text=f"Message #{message.index}: {type_str} ({len(message.fields)} fields)"
        )

        # Update tree view
        self._update_tree_view(message)

        # Update JSON view
        self._update_json_view(message)

        # Update flat view
        self._update_flat_view(message)

    def _update_tree_view(self, message: Message) -> None:
        """Update tree view with message fields."""
        # Clear existing items
        for item in self._tree.get_children():
            self._tree.delete(item)

        # Add metadata
        meta_id = self._tree.insert("", "end", text="[Metadata]", open=True)
        self._tree.insert(meta_id, "end", text=f"Index: {message.index}")
        self._tree.insert(meta_id, "end", text=f"Offset: {message.offset}")
        if message.type_hint:
            self._tree.insert(meta_id, "end", text=f"Type: {message.type_hint}")

        # Add fields
        fields_id = self._tree.insert("", "end", text="[Fields]", open=True)
        for name, field in message.fields.items():
            self._add_field_to_tree(fields_id, name, field.value)

    def _add_field_to_tree(self, parent: str, name: str, value) -> None:
        """Add a field to the tree view recursively."""
        if value is None:
            self._tree.insert(parent, "end", text=f"{name}: <null>")
        elif isinstance(value, dict):
            type_hint = value.get("__type__", "")
            display = f"{name} {{{type_hint}}}" if type_hint else f"{name} {{}}"
            node_id = self._tree.insert(parent, "end", text=display)
            for k, v in value.items():
                if k != "__type__":
                    self._add_field_to_tree(node_id, k, v)
        elif isinstance(value, (list, tuple)):
            node_id = self._tree.insert(parent, "end", text=f"{name} [{len(value)} items]")
            for i, item in enumerate(value):
                self._add_field_to_tree(node_id, f"[{i}]", item)
        elif isinstance(value, bytes):
            hex_preview = value.hex()[:50]
            if len(value) > 25:
                hex_preview += "..."
            self._tree.insert(parent, "end", text=f"{name}: <bytes:{len(value)}> {hex_preview}")
        else:
            # Truncate long values
            str_val = str(value)
            if len(str_val) > 100:
                str_val = str_val[:100] + "..."
            self._tree.insert(parent, "end", text=f"{name}: {str_val}")

    def _update_json_view(self, message: Message) -> None:
        """Update JSON view with message data."""
        self._json_text.config(state="normal")
        self._json_text.delete("1.0", "end")

        # Build JSON-like structure
        data = {
            "_index": message.index,
            "_offset": message.offset,
            "_type": message.type_hint,
        }

        for name, field in message.fields.items():
            data[name] = self._convert_for_json(field.value)

        try:
            json_str = json.dumps(data, indent=2, default=str)
        except (TypeError, ValueError):
            json_str = str(data)

        self._json_text.insert("1.0", json_str)
        self._json_text.config(state="disabled")

    def _convert_for_json(self, value):
        """Convert value for JSON serialization."""
        if isinstance(value, bytes):
            return f"<bytes:{len(value)}>"
        if isinstance(value, dict):
            return {k: self._convert_for_json(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._convert_for_json(v) for v in value]
        return value

    def _update_flat_view(self, message: Message) -> None:
        """Update flat view with flattened fields."""
        self._raw_text.config(state="normal")
        self._raw_text.delete("1.0", "end")

        flat = message.flatten()
        lines = []
        for key, value in sorted(flat.items()):
            lines.append(f"{key}: {value}")

        self._raw_text.insert("1.0", "\n".join(lines))
        self._raw_text.config(state="disabled")

    def clear(self) -> None:
        """Clear the detail panel."""
        self._current_message = None
        self._header_label.config(text="Select a message to view details")

        for item in self._tree.get_children():
            self._tree.delete(item)

        self._json_text.config(state="normal")
        self._json_text.delete("1.0", "end")
        self._json_text.config(state="disabled")

        self._raw_text.config(state="normal")
        self._raw_text.delete("1.0", "end")
        self._raw_text.config(state="disabled")
