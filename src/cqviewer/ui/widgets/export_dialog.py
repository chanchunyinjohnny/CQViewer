"""Export dialog for CSV export configuration."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Callable

from ...models.message import Message
from ...services.export_service import ExportService


class ExportDialog(tk.Toplevel):
    """Dialog for configuring and executing CSV export."""

    def __init__(
        self,
        parent: tk.Widget,
        messages: list[Message],
        available_fields: list[str],
        export_service: ExportService,
    ):
        """Initialize export dialog.

        Args:
            parent: Parent widget
            messages: Messages to export
            available_fields: List of available field names
            export_service: Export service instance
        """
        super().__init__(parent)
        self._messages = messages
        self._available_fields = available_fields
        self._export_service = export_service
        self._selected_fields: list[str] = []

        self.title("Export to CSV")
        self.geometry("600x500")
        self.transient(parent)
        self.grab_set()

        self._setup_ui()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Info section
        info_frame = ttk.Frame(self, padding=10)
        info_frame.grid(row=0, column=0, sticky="ew")

        ttk.Label(
            info_frame,
            text=f"Exporting {len(self._messages)} messages",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            info_frame, text=f"{len(self._available_fields)} fields available"
        ).pack(anchor="w")

        # Field selection
        field_frame = ttk.LabelFrame(self, text="Select Fields to Export", padding=10)
        field_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        field_frame.columnconfigure(0, weight=1)
        field_frame.columnconfigure(2, weight=1)
        field_frame.rowconfigure(0, weight=1)

        # Available fields listbox
        avail_frame = ttk.Frame(field_frame)
        avail_frame.grid(row=0, column=0, sticky="nsew")
        avail_frame.rowconfigure(1, weight=1)

        ttk.Label(avail_frame, text="Available Fields:").grid(row=0, column=0, sticky="w")

        avail_scroll = ttk.Scrollbar(avail_frame, orient="vertical")
        avail_scroll.grid(row=1, column=1, sticky="ns")

        self._avail_listbox = tk.Listbox(
            avail_frame,
            selectmode="extended",
            yscrollcommand=avail_scroll.set,
            exportselection=False,
        )
        self._avail_listbox.grid(row=1, column=0, sticky="nsew")
        avail_scroll.config(command=self._avail_listbox.yview)

        for field in self._available_fields:
            self._avail_listbox.insert("end", field)

        # Buttons between lists
        btn_frame = ttk.Frame(field_frame)
        btn_frame.grid(row=0, column=1, padx=10)

        ttk.Button(btn_frame, text="Add >", command=self._add_fields).pack(pady=5)
        ttk.Button(btn_frame, text="< Remove", command=self._remove_fields).pack(pady=5)
        ttk.Button(btn_frame, text="Add All >>", command=self._add_all_fields).pack(pady=5)
        ttk.Button(btn_frame, text="<< Clear", command=self._clear_fields).pack(pady=5)

        # Selected fields listbox
        sel_frame = ttk.Frame(field_frame)
        sel_frame.grid(row=0, column=2, sticky="nsew")
        sel_frame.rowconfigure(1, weight=1)

        ttk.Label(sel_frame, text="Selected Fields:").grid(row=0, column=0, sticky="w")

        sel_scroll = ttk.Scrollbar(sel_frame, orient="vertical")
        sel_scroll.grid(row=1, column=1, sticky="ns")

        self._sel_listbox = tk.Listbox(
            sel_frame,
            selectmode="extended",
            yscrollcommand=sel_scroll.set,
            exportselection=False,
        )
        self._sel_listbox.grid(row=1, column=0, sticky="nsew")
        sel_scroll.config(command=self._sel_listbox.yview)

        # Options section
        options_frame = ttk.LabelFrame(self, text="Options", padding=10)
        options_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)

        self._include_index_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame, text="Include message index", variable=self._include_index_var
        ).pack(anchor="w")

        self._include_offset_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            options_frame, text="Include file offset", variable=self._include_offset_var
        ).pack(anchor="w")

        self._include_type_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame, text="Include message type", variable=self._include_type_var
        ).pack(anchor="w")

        # Action buttons
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.grid(row=3, column=0, sticky="ew")

        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Export", command=self._do_export).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Preview", command=self._show_preview).pack(side="right", padx=5)

    def _add_fields(self) -> None:
        """Add selected fields to export list."""
        selection = self._avail_listbox.curselection()
        for idx in selection:
            field = self._avail_listbox.get(idx)
            if field not in self._selected_fields:
                self._selected_fields.append(field)
                self._sel_listbox.insert("end", field)

    def _remove_fields(self) -> None:
        """Remove selected fields from export list."""
        selection = list(self._sel_listbox.curselection())
        for idx in reversed(selection):
            field = self._sel_listbox.get(idx)
            self._sel_listbox.delete(idx)
            if field in self._selected_fields:
                self._selected_fields.remove(field)

    def _add_all_fields(self) -> None:
        """Add all available fields to export list."""
        self._selected_fields = self._available_fields.copy()
        self._sel_listbox.delete(0, "end")
        for field in self._selected_fields:
            self._sel_listbox.insert("end", field)

    def _clear_fields(self) -> None:
        """Clear all selected fields."""
        self._selected_fields = []
        self._sel_listbox.delete(0, "end")

    def _show_preview(self) -> None:
        """Show preview of export."""
        fields = self._selected_fields if self._selected_fields else None
        preview = self._export_service.preview_export(self._messages, fields, limit=5)

        # Create preview window
        preview_win = tk.Toplevel(self)
        preview_win.title("Export Preview")
        preview_win.geometry("800x400")
        preview_win.transient(self)

        text = tk.Text(preview_win, wrap="none", font=("Courier", 10))
        text.pack(fill="both", expand=True, padx=10, pady=10)

        # Format preview
        if preview:
            headers = list(preview[0].keys())
            text.insert("end", "\t".join(headers) + "\n")
            text.insert("end", "-" * 80 + "\n")

            for row in preview:
                values = [str(row.get(h, ""))[:30] for h in headers]
                text.insert("end", "\t".join(values) + "\n")

        text.config(state="disabled")

        ttk.Button(preview_win, text="Close", command=preview_win.destroy).pack(pady=10)

    def _do_export(self) -> None:
        """Execute export."""
        # Get output path
        filepath = filedialog.asksaveasfilename(
            parent=self,
            title="Save CSV File",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )

        if not filepath:
            return

        try:
            fields = self._selected_fields if self._selected_fields else None
            self._export_service.export_to_csv(
                self._messages,
                output_path=filepath,
                fields=fields,
                include_index=self._include_index_var.get(),
                include_offset=self._include_offset_var.get(),
                include_type=self._include_type_var.get(),
            )

            messagebox.showinfo(
                "Export Complete",
                f"Successfully exported {len(self._messages)} messages to:\n{filepath}",
                parent=self,
            )
            self.destroy()

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {e}", parent=self)
