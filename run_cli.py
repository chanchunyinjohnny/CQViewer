#!/usr/bin/env python3
"""
CQViewer CLI - Easy-to-use command line interface for Chronicle Queue files.

Uses only company-approved dependencies:
- rich: Beautiful terminal output
- tabulate: Table formatting

Usage:
    python run_cli.py <folder_or_file> [options]

Examples:
    python run_cli.py ./data/                    # Open folder with .cq4 files
    python run_cli.py ./data/queue.cq4           # Open specific file
    python run_cli.py ./data/ --search "orderId" # Search for field
    python run_cli.py ./data/ --export out.csv   # Export to CSV
"""

import sys
import argparse
from pathlib import Path

# Add src to path for direct execution
sys.path.insert(0, str(Path(__file__).parent / "src"))

from cqviewer.services.message_service import MessageService
from cqviewer.services.search_service import SearchService
from cqviewer.services.filter_service import FilterService, FilterCriteria
from cqviewer.services.export_service import ExportService

# Try to import rich for beautiful output (company-approved)
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import print as rprint
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# Try to import tabulate as fallback (company-approved)
try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False


class CQViewerCLI:
    """Simple CLI for viewing Chronicle Queue files."""

    def __init__(self):
        self.service = MessageService()
        self.search_service = SearchService()
        self.filter_service = FilterService()
        self.export_service = ExportService()
        self.console = Console() if HAS_RICH else None
        self.messages = []

    def print_info(self, text: str, style: str = ""):
        """Print informational text."""
        if HAS_RICH:
            self.console.print(text, style=style)
        else:
            print(text)

    def print_table(self, rows: list[dict], columns: list[str], title: str = ""):
        """Print a table of data."""
        if not rows:
            self.print_info("No data to display", style="yellow")
            return

        if HAS_RICH:
            table = Table(title=title, show_header=True, header_style="bold cyan")
            for col in columns:
                table.add_column(col)
            for row in rows:
                table.add_row(*[str(row.get(col, ""))[:50] for col in columns])
            self.console.print(table)
        elif HAS_TABULATE:
            headers = columns
            data = [[str(row.get(col, ""))[:50] for col in columns] for row in rows]
            print(tabulate(data, headers=headers, tablefmt="grid"))
            if title:
                print(f"\n{title}")
        else:
            # Fallback: simple text output
            if title:
                print(f"\n{title}")
            print("-" * 80)
            print(" | ".join(col.ljust(15) for col in columns))
            print("-" * 80)
            for row in rows:
                print(" | ".join(str(row.get(col, ""))[:15].ljust(15) for col in columns))

    def load_path(self, path: str, include_metadata: bool = False) -> bool:
        """Load a file or folder."""
        p = Path(path)

        if p.is_dir():
            return self._load_folder(p, include_metadata)
        elif p.is_file() and p.suffix == ".cq4":
            return self._load_file(p, include_metadata)
        else:
            self.print_info(f"Error: Invalid path or not a .cq4 file: {path}", style="red")
            return False

    def _load_folder(self, folder: Path, include_metadata: bool) -> bool:
        """Load all files from a folder."""
        cq4_files = list(folder.glob("*.cq4"))
        java_files = list(folder.rglob("*.java")) + list(folder.rglob("*.class"))

        if not cq4_files:
            self.print_info(f"No .cq4 files found in {folder}", style="red")
            return False

        # Load Java schema if available
        if java_files:
            try:
                schema = self.service.load_schema_directory(str(folder))
                self.print_info(f"Loaded schema: {len(schema.messages)} message types", style="green")
            except Exception as e:
                self.print_info(f"Warning: Could not load schema: {e}", style="yellow")

        # Load the first .cq4 file
        cq4_file = cq4_files[0]
        return self._load_file(cq4_file, include_metadata)

    def _load_file(self, file_path: Path, include_metadata: bool) -> bool:
        """Load a single .cq4 file."""
        try:
            if HAS_RICH:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=self.console,
                ) as progress:
                    progress.add_task(description=f"Loading {file_path.name}...", total=None)
                    info = self.service.load_file(str(file_path), include_metadata=include_metadata)
            else:
                print(f"Loading {file_path.name}...")
                info = self.service.load_file(str(file_path), include_metadata=include_metadata)

            self.messages = self.service.get_all_messages()

            if HAS_RICH:
                self.console.print(Panel(
                    f"[bold]File:[/bold] {info.filepath}\n"
                    f"[bold]Size:[/bold] {info.file_size_str}\n"
                    f"[bold]Messages:[/bold] {info.message_count}",
                    title="Loaded",
                    border_style="green"
                ))
            else:
                print(f"\nLoaded: {info.filepath}")
                print(f"Size: {info.file_size_str}")
                print(f"Messages: {info.message_count}")

            return True
        except Exception as e:
            self.print_info(f"Error loading file: {e}", style="red")
            return False

    def list_messages(self, offset: int = 0, limit: int = 50, type_filter: str = None):
        """List messages with pagination."""
        messages = self.messages

        if type_filter:
            messages = self.filter_service.filter_by_type(messages, type_filter)

        total = len(messages)
        page = messages[offset:offset + limit]

        if not page:
            self.print_info("No messages found", style="yellow")
            return

        # Build table data
        rows = []
        columns = ["Index", "Type"]

        # Find common fields from first few messages
        common_fields = set()
        for msg in page[:10]:
            for key in msg.fields.keys():
                if not key.startswith("_"):
                    common_fields.add(key)
        extra_cols = sorted(common_fields)[:3]
        columns.extend(extra_cols)

        for msg in page:
            row = {
                "Index": msg.index,
                "Type": msg.type_hint or "unknown"
            }
            for col in extra_cols:
                field = msg.get_field(col)
                row[col] = field.format_value(max_length=30) if field else ""
            rows.append(row)

        self.print_table(rows, columns, title=f"Messages {offset + 1}-{min(offset + limit, total)} of {total}")

    def show_message(self, index: int):
        """Show detailed view of a single message."""
        msg = self.service.get_message(index)
        if not msg:
            self.print_info(f"Message {index} not found", style="red")
            return

        if HAS_RICH:
            self.console.print(Panel(
                f"[bold]Index:[/bold] {msg.index}\n"
                f"[bold]Offset:[/bold] {msg.offset}\n"
                f"[bold]Type:[/bold] {msg.type_hint or 'unknown'}",
                title=f"Message #{index}",
                border_style="blue"
            ))

            for name, field in msg.fields.items():
                value = field.format_value(max_length=100)
                self.console.print(f"  [cyan]{name}[/cyan]: {value}")
        else:
            print(f"\nMessage #{msg.index}")
            print(f"Offset: {msg.offset}")
            print(f"Type: {msg.type_hint or 'unknown'}")
            print("-" * 60)
            for name, field in msg.fields.items():
                value = field.format_value(max_length=100)
                print(f"  {name}: {value}")

    def _get_match_context(self, msg, query: str) -> str:
        """Get brief description of why a message matched."""
        query_lower = query.lower()
        if msg.type_hint and query_lower in msg.type_hint.lower():
            return f"type: {msg.type_hint}"
        for name in msg.field_names(include_nested=True):
            if query_lower in name.lower():
                return f"field: {name}"
        for name, field in msg.fields.items():
            val_str = str(field.value) if field.value is not None else ""
            if query_lower in val_str.lower():
                preview = val_str[:30] + "..." if len(val_str) > 30 else val_str
                return f"{name}={preview}"
        return ""

    def search(self, query: str, limit: int = 20):
        """Search messages."""
        results = self.search_service.search_combined(self.messages, query)

        self.print_info(f"\nFound {len(results)} matches for '{query}'", style="bold")

        if results:
            rows = []
            for m in results[:limit]:
                rows.append({
                    "Index": m.index,
                    "Type": m.type_hint or "unknown",
                    "Match": self._get_match_context(m, query),
                })
            self.print_table(rows, ["Index", "Type", "Match"])

            if len(results) > limit:
                self.print_info(f"... and {len(results) - limit} more", style="dim")

    def show_types(self):
        """Show all message types."""
        types = self.service.get_unique_types()
        rows = []
        for t in types:
            count = sum(1 for m in self.messages if m.type_hint == t)
            rows.append({"Type": t, "Count": count})
        self.print_table(rows, ["Type", "Count"], title=f"{len(types)} Message Types")

    def show_fields(self):
        """Show all unique field names."""
        fields = self.service.get_all_field_names()
        self.print_info(f"\n{len(fields)} Unique Fields:", style="bold")
        for f in fields:
            self.print_info(f"  {f}")

    def export(self, output: str, type_filter: str = None, fields: list[str] = None):
        """Export messages to CSV."""
        messages = self.messages

        if type_filter:
            messages = self.filter_service.filter_by_type(messages, type_filter)

        if not messages:
            self.print_info("No messages to export", style="red")
            return

        self.export_service.export_to_csv(messages, output, fields=fields)
        self.print_info(f"Exported {len(messages)} messages to {output}", style="green")

    def close(self):
        """Clean up resources."""
        self.service.close()


def main():
    parser = argparse.ArgumentParser(
        description="CQViewer CLI - Chronicle Queue file viewer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_cli.py ./data/                    Open folder with .cq4 files
  python run_cli.py ./data/queue.cq4           Open specific file
  python run_cli.py ./data/ -n 100             Show first 100 messages
  python run_cli.py ./data/ --search orderId   Search for 'orderId'
  python run_cli.py ./data/ --types            List message types
  python run_cli.py ./data/ --export out.csv   Export to CSV
  python run_cli.py ./data/ --show 5           Show message at index 5
        """
    )

    parser.add_argument("path", help="Path to .cq4 file or folder containing .cq4 files")
    parser.add_argument("-n", "--limit", type=int, default=50, help="Number of messages to show (default: 50)")
    parser.add_argument("-o", "--offset", type=int, default=0, help="Starting offset (default: 0)")
    parser.add_argument("-t", "--type", help="Filter by message type")
    parser.add_argument("-s", "--search", help="Search query")
    parser.add_argument("--show", type=int, metavar="INDEX", help="Show detailed view of message at INDEX")
    parser.add_argument("--types", action="store_true", help="List all message types")
    parser.add_argument("--fields", action="store_true", help="List all unique field names")
    parser.add_argument("--export", metavar="FILE", help="Export to CSV file")
    parser.add_argument("--export-fields", help="Comma-separated fields to export")
    parser.add_argument("-m", "--metadata", action="store_true", help="Include metadata messages")

    args = parser.parse_args()

    cli = CQViewerCLI()

    try:
        if not cli.load_path(args.path, include_metadata=args.metadata):
            return 1

        # Handle different modes
        if args.show is not None:
            cli.show_message(args.show)
        elif args.search:
            cli.search(args.search, limit=args.limit)
        elif args.types:
            cli.show_types()
        elif args.fields:
            cli.show_fields()
        elif args.export:
            export_fields = [f.strip() for f in args.export_fields.split(",")] if args.export_fields else None
            cli.export(args.export, type_filter=args.type, fields=export_fields)
        else:
            cli.list_messages(offset=args.offset, limit=args.limit, type_filter=args.type)

        return 0

    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())