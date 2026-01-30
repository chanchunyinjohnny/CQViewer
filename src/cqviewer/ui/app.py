"""Main CQViewer application."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

try:
    import ttkbootstrap as ttkb
    from ttkbootstrap.constants import *

    HAS_TTKBOOTSTRAP = True
except ImportError:
    HAS_TTKBOOTSTRAP = False

from ..parser.cq4_reader import CQ4Reader
from ..parser.schema import Schema, create_example_schema
from ..services.message_service import MessageService
from ..services.search_service import SearchService
from ..services.filter_service import FilterService, FilterCriteria
from ..services.export_service import ExportService
from ..models.message import Message
from .widgets.message_table import MessageTable
from .widgets.filter_bar import FilterBar
from .widgets.detail_panel import DetailPanel
from .widgets.export_dialog import ExportDialog


def read_tailer_metadata(tailer_file: str) -> dict:
    """Read metadata from .cq4t tailer file."""
    metadata = {}
    try:
        with CQ4Reader(tailer_file) as reader:
            for exc in reader.iter_excerpts(include_metadata=True):
                if exc.data and exc.data.fields:
                    for key, value in exc.data.fields.items():
                        if key == "header" and isinstance(value, dict):
                            metadata["header"] = value
                        elif key == "wireType":
                            metadata["wireType"] = value
                        elif key == "metadata" and isinstance(value, dict):
                            metadata["queueMetadata"] = value
                        elif not key.startswith("_"):
                            metadata[key] = value
    except Exception:
        pass
    return metadata


class CQViewerApp:
    """Main CQViewer application window."""

    def __init__(self, root: tk.Tk | None = None):
        """Initialize the application.

        Args:
            root: Optional existing Tk root window
        """
        # Create root window
        if root is None:
            if HAS_TTKBOOTSTRAP:
                self._root = ttkb.Window(themename="cosmo")
            else:
                self._root = tk.Tk()
        else:
            self._root = root

        self._root.title("CQViewer - Chronicle Queue Viewer")
        self._root.geometry("1200x800")

        # Initialize services
        self._message_service = MessageService()
        self._search_service = SearchService()
        self._filter_service = FilterService()
        self._export_service = ExportService()

        # State
        self._all_messages: list[Message] = []
        self._filtered_messages: list[Message] = []
        self._current_criteria = FilterCriteria()
        self._tailer_file: str | None = None
        self._tailer_metadata: dict = {}
        self._schema_file: str | None = None
        self._schema: Schema | None = None

        # Setup UI
        self._setup_menu()
        self._setup_ui()
        self._setup_bindings()

    def _setup_menu(self) -> None:
        """Set up the menu bar."""
        menubar = tk.Menu(self._root)
        self._root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open .cq4 File...", command=self._open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Open .cq4t Tailer File...", command=self._open_tailer_file)
        file_menu.add_command(label="Load Java Schema (.java/.class)...", command=self._load_schema_file)
        file_menu.add_command(label="Close File", command=self._close_file)
        file_menu.add_separator()
        file_menu.add_command(label="Export to CSV...", command=self._export_csv, accelerator="Ctrl+E")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._root.quit, accelerator="Ctrl+Q")

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        self._show_metadata_var = tk.BooleanVar(value=False)
        view_menu.add_checkbutton(
            label="Show Metadata Messages",
            variable=self._show_metadata_var,
            command=self._toggle_metadata,
        )
        view_menu.add_separator()
        view_menu.add_command(label="Refresh", command=self._refresh, accelerator="F5")

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

    def _setup_ui(self) -> None:
        """Set up the main UI."""
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(2, weight=1)

        # Toolbar
        toolbar = ttk.Frame(self._root, padding=5)
        toolbar.grid(row=0, column=0, sticky="ew")

        ttk.Button(toolbar, text="Open", command=self._open_any_file).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Export", command=self._export_csv).pack(side="left", padx=2)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=10)

        self._file_label = ttk.Label(toolbar, text="No file loaded")
        self._file_label.pack(side="left", padx=5)

        # Filter bar
        self._filter_bar = FilterBar(
            self._root,
            on_search=self._on_search,
            on_filter=self._on_filter,
        )
        self._filter_bar.grid(row=1, column=0, sticky="ew", padx=5, pady=5)

        # Main content - PanedWindow
        paned = ttk.PanedWindow(self._root, orient="horizontal")
        paned.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        # Left panel - Message table
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=3)

        self._message_table = MessageTable(
            left_frame,
            on_select=self._on_message_select,
            page_size=50,
        )
        self._message_table.pack(fill="both", expand=True)

        # Set default columns
        self._message_table.set_columns(["Index", "Type", "Fields"])

        # Right panel - Detail view
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)

        self._detail_panel = DetailPanel(right_frame)
        self._detail_panel.pack(fill="both", expand=True)

        # Status bar
        self._status_bar = ttk.Label(
            self._root, text="Ready", relief="sunken", anchor="w", padding=3
        )
        self._status_bar.grid(row=3, column=0, sticky="ew")

    def _setup_bindings(self) -> None:
        """Set up keyboard bindings."""
        self._root.bind("<Control-o>", lambda e: self._open_file())
        self._root.bind("<Control-e>", lambda e: self._export_csv())
        self._root.bind("<Control-q>", lambda e: self._root.quit())
        self._root.bind("<F5>", lambda e: self._refresh())

    def _open_any_file(self) -> None:
        """Open any supported file (.cq4, .cq4t, .java, .class)."""
        filepath = filedialog.askopenfilename(
            title="Open File",
            filetypes=[
                ("All supported", "*.cq4 *.cq4t *.java *.class"),
                ("CQ4 data files", "*.cq4"),
                ("CQ4 tailer files", "*.cq4t"),
                ("Java files", "*.java *.class"),
                ("All files", "*.*"),
            ],
        )

        if not filepath:
            return

        # Route to appropriate handler based on extension
        if filepath.endswith(".cq4"):
            self._open_cq4_file(filepath)
        elif filepath.endswith(".cq4t"):
            self._open_tailer_file_path(filepath)
        elif filepath.endswith((".java", ".class")):
            self._load_schema_file_path(filepath)
        else:
            messagebox.showwarning("Unknown File", f"Unknown file type: {filepath}")

    def _open_file(self) -> None:
        """Open a .cq4 file."""
        filepath = filedialog.askopenfilename(
            title="Open Chronicle Queue File",
            filetypes=[
                ("CQ4 files", "*.cq4"),
                ("All files", "*.*"),
            ],
        )

        if not filepath:
            return

        self._open_cq4_file(filepath)

    def _open_cq4_file(self, filepath: str) -> None:
        """Open a .cq4 file by path."""
        try:
            self._status_bar.config(text=f"Loading {filepath}...")
            self._root.update()

            queue_info = self._message_service.load_file(
                filepath, include_metadata=self._show_metadata_var.get()
            )

            self._all_messages = self._message_service.get_all_messages()
            self._filtered_messages = self._all_messages.copy()

            # Update UI
            self._file_label.config(text=str(queue_info))
            self._message_table.set_messages(self._filtered_messages)

            # Update filter options
            types = self._message_service.get_unique_types()
            fields = self._message_service.get_all_field_names()
            self._filter_bar.set_types(types)
            self._filter_bar.set_fields(fields)

            # Update columns if we have messages
            if self._all_messages:
                self._update_table_columns()

            self._status_bar.config(
                text=f"Loaded {queue_info.message_count} messages from {queue_info.filename}"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file:\n{e}")
            self._status_bar.config(text="Error loading file")

    def _open_tailer_file(self) -> None:
        """Open a .cq4t tailer/metadata file via dialog."""
        filepath = filedialog.askopenfilename(
            title="Open Tailer/Metadata File",
            filetypes=[
                ("CQ4T files", "*.cq4t"),
                ("All files", "*.*"),
            ],
        )

        if filepath:
            self._open_tailer_file_path(filepath)

    def _open_tailer_file_path(self, filepath: str) -> None:
        """Open a .cq4t tailer/metadata file by path."""
        try:
            self._tailer_file = filepath
            self._tailer_metadata = read_tailer_metadata(filepath)

            # Build info string
            info_parts = [f"Tailer: {Path(filepath).name}"]
            if "wireType" in self._tailer_metadata:
                info_parts.append(f"Wire: {self._tailer_metadata['wireType']}")

            # Update status
            tailer_info = " | ".join(info_parts)
            current_status = self._status_bar.cget("text")
            if "Tailer:" not in current_status:
                self._status_bar.config(text=f"{current_status} | {tailer_info}")
            else:
                # Replace existing tailer info
                base_status = current_status.split(" | Tailer:")[0]
                self._status_bar.config(text=f"{base_status} | {tailer_info}")

            messagebox.showinfo(
                "Tailer Loaded",
                f"Loaded tailer metadata:\n"
                f"File: {Path(filepath).name}\n"
                f"Wire Type: {self._tailer_metadata.get('wireType', 'unknown')}\n"
                f"Store Type: {self._tailer_metadata.get('header', {}).get('__type__', 'unknown')}"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open tailer file:\n{e}")

    def _load_schema_file(self) -> None:
        """Load a Java schema file (.java or .class) for decoding BINARY_LIGHT messages."""
        filepath = filedialog.askopenfilename(
            title="Load Java Schema File",
            filetypes=[
                ("Java files", "*.java *.class"),
                ("Java source", "*.java"),
                ("Java class", "*.class"),
                ("All files", "*.*"),
            ],
        )

        if filepath:
            self._load_schema_file_path(filepath)

    def _load_schema_file_path(self, filepath: str) -> None:
        """Load a Java schema file by path."""
        try:
            self._schema_file = filepath
            self._schema = self._message_service.load_schema_file(filepath)

            # Build info string
            msg_count = len(self._schema.messages)
            msg_names = ", ".join(sorted(self._schema.messages.keys())[:3])
            if len(self._schema.messages) > 3:
                msg_names += f" (+{len(self._schema.messages) - 3} more)"

            schema_info = f"Schema: {Path(filepath).name} ({msg_count} types)"

            # Update status
            current_status = self._status_bar.cget("text")
            if "Schema:" not in current_status:
                self._status_bar.config(text=f"{current_status} | {schema_info}")
            else:
                # Replace existing schema info
                parts = current_status.split(" | ")
                parts = [p for p in parts if not p.startswith("Schema:")]
                parts.append(schema_info)
                self._status_bar.config(text=" | ".join(parts))

            # Build field list for the message
            field_info = ""
            if self._schema.default_message and self._schema.default_message in self._schema.messages:
                msg_def = self._schema.messages[self._schema.default_message]
                fields = [f"{f.name}: {f.type}" for f in msg_def.fields[:10]]
                field_info = "\n".join(fields)
                if len(msg_def.fields) > 10:
                    field_info += f"\n... and {len(msg_def.fields) - 10} more fields"

            messagebox.showinfo(
                "Schema Loaded",
                f"Loaded schema from:\n{Path(filepath).name}\n\n"
                f"Message types: {msg_names}\n"
                f"Default: {self._schema.default_message or 'none'}\n\n"
                f"Fields:\n{field_info}\n\n"
                f"Reload the .cq4 file to apply schema."
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load schema file:\n{e}")

    def _update_table_columns(self) -> None:
        """Update table columns based on loaded messages."""
        # Always include index, type, and field count
        columns = ["Index", "Type", "Fields"]

        # Add common fields from messages (up to 5 additional)
        common_fields = self._get_common_fields(limit=5)
        columns.extend(common_fields)

        self._message_table.set_columns(columns)
        self._message_table.set_messages(self._filtered_messages)

    def _get_common_fields(self, limit: int = 5) -> list[str]:
        """Get the most common field names across messages."""
        field_counts: dict[str, int] = {}

        for msg in self._all_messages[:100]:  # Sample first 100
            for name in msg.fields.keys():
                field_counts[name] = field_counts.get(name, 0) + 1

        # Sort by count and return top fields
        sorted_fields = sorted(field_counts.items(), key=lambda x: -x[1])
        return [f[0] for f in sorted_fields[:limit]]

    def _close_file(self) -> None:
        """Close the current file."""
        self._message_service.close()
        self._all_messages = []
        self._filtered_messages = []
        self._tailer_file = None
        self._tailer_metadata = {}
        self._schema_file = None
        self._schema = None
        self._message_table.clear()
        self._detail_panel.clear()
        self._file_label.config(text="No file loaded")
        self._status_bar.config(text="Ready")

    def _export_csv(self) -> None:
        """Export current messages to CSV."""
        if not self._filtered_messages:
            messagebox.showwarning("No Data", "No messages to export.")
            return

        available_fields = self._export_service.get_available_fields(self._filtered_messages)

        dialog = ExportDialog(
            self._root,
            self._filtered_messages,
            available_fields,
            self._export_service,
        )
        self._root.wait_window(dialog)

    def _on_search(self, query: str) -> None:
        """Handle search query."""
        if not query:
            # No search query - apply just filters
            self._apply_filters()
            return

        # Search within currently filtered messages
        base_messages = self._filter_service.filter_messages(
            self._all_messages, self._current_criteria
        )
        results = self._search_service.search_combined(base_messages, query)
        self._filtered_messages = results
        self._message_table.set_filtered_messages(results)
        self._status_bar.config(text=f"Found {len(results)} matches for '{query}'")

    def _on_filter(self, criteria: FilterCriteria) -> None:
        """Handle filter criteria change."""
        self._current_criteria = criteria
        self._apply_filters()

    def _apply_filters(self) -> None:
        """Apply current filter criteria."""
        criteria = self._current_criteria

        # Also apply metadata filter
        criteria.include_metadata = self._show_metadata_var.get()

        self._filtered_messages = self._filter_service.filter_messages(
            self._all_messages, criteria
        )

        # If there's a search query, apply it too
        search_query = self._filter_bar.get_search_query()
        if search_query:
            self._filtered_messages = self._search_service.search_combined(
                self._filtered_messages, search_query
            )

        self._message_table.set_filtered_messages(self._filtered_messages)
        self._status_bar.config(
            text=f"Showing {len(self._filtered_messages)} of {len(self._all_messages)} messages"
        )

    def _on_message_select(self, message: Message) -> None:
        """Handle message selection."""
        self._detail_panel.show_message(message)

    def _toggle_metadata(self) -> None:
        """Toggle metadata message visibility."""
        if self._message_service.is_loaded:
            # Reload file with new setting
            filepath = self._message_service.queue_info.filepath
            self._message_service.load_file(
                filepath, include_metadata=self._show_metadata_var.get()
            )
            self._all_messages = self._message_service.get_all_messages()
            self._apply_filters()

    def _refresh(self) -> None:
        """Refresh the display."""
        if self._message_service.is_loaded:
            filepath = self._message_service.queue_info.filepath
            self._open_file_by_path(filepath)

    def _open_file_by_path(self, filepath: Path) -> None:
        """Open a specific file by path."""
        try:
            self._status_bar.config(text=f"Reloading {filepath}...")
            self._root.update()

            queue_info = self._message_service.load_file(
                filepath, include_metadata=self._show_metadata_var.get()
            )

            self._all_messages = self._message_service.get_all_messages()
            self._apply_filters()

            self._status_bar.config(text=f"Reloaded {queue_info.message_count} messages")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to reload file:\n{e}")

    def _show_about(self) -> None:
        """Show about dialog."""
        messagebox.showinfo(
            "About CQViewer",
            "CQViewer - Chronicle Queue Viewer\n\n"
            "Version 0.1.0\n\n"
            "A tool for inspecting and exporting\n"
            "Chronicle Queue (.cq4) data files.\n\n"
            "Features:\n"
            "- Search by field name or value\n"
            "- Filter by type or field existence\n"
            "- Export to CSV format",
        )

    def run(self) -> None:
        """Run the application main loop."""
        self._root.mainloop()


def main():
    """Main entry point."""
    app = CQViewerApp()
    app.run()


if __name__ == "__main__":
    main()
