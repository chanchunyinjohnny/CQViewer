"""Command-line interface for CQViewer.

This module provides a CLI that works without any GUI dependencies.
All functionality uses only the Python standard library.
"""

import argparse
import sys
import json
from pathlib import Path

from .parser.cq4_reader import CQ4Reader
from .parser.java_parser import parse_java_file
from .parser.schema import ENCODING_BINARY, ENCODING_THRIFT, ENCODING_SBE
from .models.message import Message
from .services.message_service import MessageService
from .services.search_service import SearchService
from .services.filter_service import FilterService, FilterCriteria
from .services.export_service import ExportService


def read_tailer_metadata(tailer_file: str) -> dict:
    """Read metadata from .cq4t tailer file.

    Args:
        tailer_file: Path to .cq4t file

    Returns:
        Dictionary with metadata info
    """
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


def format_table(rows: list[dict], columns: list[str], max_width: int = 40) -> str:
    """Format data as a text table with left-aligned columns and box-drawing borders.

    Args:
        rows: List of row dictionaries
        columns: Column names to display
        max_width: Maximum column width

    Returns:
        Formatted table string
    """
    if not rows:
        return "No data"

    # Box-drawing characters
    H_LINE = "─"
    V_LINE = "│"
    TOP_LEFT = "┌"
    TOP_RIGHT = "┐"
    BOTTOM_LEFT = "└"
    BOTTOM_RIGHT = "┘"
    T_DOWN = "┬"
    T_UP = "┴"
    T_RIGHT = "├"
    T_LEFT = "┤"
    CROSS = "┼"

    # Calculate column widths based on header and data
    widths = {}
    for col in columns:
        data_widths = [len(str(row.get(col, ""))[:max_width]) for row in rows]
        widths[col] = min(max_width, max(len(col), max(data_widths) if data_widths else 0))

    # Build top border
    top_border = TOP_LEFT + T_DOWN.join(H_LINE * (widths[col] + 2) for col in columns) + TOP_RIGHT

    # Build header row
    header_cells = []
    for col in columns:
        cell = " " + col[:widths[col]].ljust(widths[col]) + " "
        header_cells.append(cell)
    header = V_LINE + V_LINE.join(header_cells) + V_LINE

    # Build header separator
    header_sep = T_RIGHT + CROSS.join(H_LINE * (widths[col] + 2) for col in columns) + T_LEFT

    # Build data rows
    data_lines = []
    for row in rows:
        row_cells = []
        for col in columns:
            value = str(row.get(col, ""))[:widths[col]]
            cell = " " + value.ljust(widths[col]) + " "
            row_cells.append(cell)
        data_lines.append(V_LINE + V_LINE.join(row_cells) + V_LINE)

    # Build bottom border
    bottom_border = BOTTOM_LEFT + T_UP.join(H_LINE * (widths[col] + 2) for col in columns) + BOTTOM_RIGHT

    # Combine all parts
    lines = [top_border, header, header_sep] + data_lines + [bottom_border]
    return "\n".join(lines)


def load_schema_if_provided(args: argparse.Namespace, service: MessageService):
    """Load Java schema file(s) or directory if provided in args.

    Args:
        args: Parsed command line arguments
        service: MessageService instance

    Returns:
        Loaded Schema or None
    """
    # Get encoding override if provided
    encoding = getattr(args, "encoding", None)

    # Check for directory mode first
    schema_dir = getattr(args, "schema_dir", None)
    if schema_dir:
        try:
            return service.load_schema_directory(schema_dir, encoding=encoding)
        except Exception as e:
            print(f"Warning: Failed to load schema from directory: {e}", file=sys.stderr)
            return None

    # Check for individual schema files
    if not hasattr(args, "schema") or not args.schema:
        return None

    schema_files = args.schema  # List of files due to action="append"

    # Filter to only Java files
    java_files = [f for f in schema_files if f.endswith((".java", ".class"))]

    if not java_files:
        print("Warning: No valid Java schema files provided (.java or .class)", file=sys.stderr)
        return None

    try:
        if len(java_files) == 1:
            return service.load_schema_file(java_files[0], encoding=encoding)
        else:
            return service.load_java_files(java_files, encoding=encoding)
    except Exception as e:
        print(f"Warning: Failed to load schema: {e}", file=sys.stderr)

    return None


def cmd_info(args: argparse.Namespace) -> int:
    """Show file information."""
    service = MessageService()
    try:
        # Load schema if provided
        schema = load_schema_if_provided(args, service)

        info = service.load_file(args.file, include_metadata=args.metadata)
        print(f"File: {info.filepath}")
        print(f"Size: {info.file_size_str}")
        print(f"Messages: {info.message_count}")
        if info.version:
            print(f"Version: {info.version}")
        if info.roll_cycle:
            print(f"Roll Cycle: {info.roll_cycle}")

        # Show schema info if loaded
        if schema:
            if args.schema:
                schema_files = ", ".join(args.schema)
            elif getattr(args, "schema_dir", None):
                schema_files = args.schema_dir
            else:
                schema_files = "auto-detected"
            print(f"\nSchema: {schema_files}")
            print(f"Encoding: {schema.encoding}")
            print(f"Message Types Defined: {len(schema.messages)}")
            for name in sorted(schema.messages.keys()):
                msg_def = schema.messages[name]
                field_names = ", ".join(f.name for f in msg_def.fields[:5])
                if len(msg_def.fields) > 5:
                    field_names += ", ..."
                print(f"  {name}: {len(msg_def.fields)} fields ({field_names})")
            if schema.default_message:
                print(f"Default Message: {schema.default_message}")

        # Show tailer/metadata file info if provided
        if args.tailer:
            print(f"\nTailer File: {args.tailer}")
            tailer_meta = read_tailer_metadata(args.tailer)
            if tailer_meta:
                if "wireType" in tailer_meta:
                    print(f"Wire Type: {tailer_meta['wireType']}")
                if "header" in tailer_meta:
                    header = tailer_meta["header"]
                    if isinstance(header, dict) and "__type__" in header:
                        print(f"Store Type: {header['__type__']}")
                if "queueMetadata" in tailer_meta:
                    qm = tailer_meta["queueMetadata"]
                    if isinstance(qm, dict):
                        if "__type__" in qm:
                            print(f"Queue Metadata Type: {qm['__type__']}")
                        if "roll" in qm and isinstance(qm["roll"], dict):
                            roll = qm["roll"]
                            if "length" in roll:
                                print(f"Roll Length: {roll['length']}")

        # Show type summary
        types = service.get_unique_types()
        if types:
            print(f"\nMessage Types ({len(types)}):")
            for t in types[:20]:  # Limit to 20
                count = sum(1 for m in service.get_all_messages() if m.type_hint == t)
                print(f"  {t}: {count}")
            if len(types) > 20:
                print(f"  ... and {len(types) - 20} more")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        service.close()


def cmd_list(args: argparse.Namespace) -> int:
    """List messages."""
    service = MessageService()
    search = SearchService()
    filter_svc = FilterService()

    try:
        load_schema_if_provided(args, service)
        service.load_file(args.file, include_metadata=args.metadata)
        messages = service.get_all_messages()

        # Apply type filter
        if args.type:
            messages = filter_svc.filter_by_type(messages, args.type)

        # Apply field filter
        if args.has_field:
            messages = filter_svc.filter_by_field_exists(messages, args.has_field)

        # Apply search
        if args.search:
            messages = search.search_combined(messages, args.search)

        # Pagination
        total = len(messages)
        start = args.offset
        end = start + args.limit
        page_messages = messages[start:end]

        if not page_messages:
            print("No messages found")
            return 0

        # Determine columns
        if args.fields:
            columns = [f.strip() for f in args.fields.split(",")]
        else:
            columns = ["index", "type"]
            # Add common fields (excluding internal ones for cleaner display)
            common = set()
            for msg in page_messages[:10]:
                for key in msg.fields.keys():
                    # Skip internal fields for default display
                    if not key.startswith("_"):
                        common.add(key)
            # If no regular fields, show _strings
            if common:
                columns.extend(sorted(common)[:3])
            else:
                # For binary messages, show useful fields
                for msg in page_messages[:1]:
                    if "_strings" in msg.fields:
                        columns.append("_strings")
                    elif "_raw_length" in msg.fields:
                        columns.append("_raw_length")

        # Build rows
        rows = []
        for msg in page_messages:
            row = {"index": msg.index, "type": msg.type_hint or ""}
            for col in columns:
                if col not in ["index", "type"]:
                    field = msg.get_field(col)
                    row[col] = field.format_value(max_length=30) if field else ""
            rows.append(row)

        print(format_table(rows, columns))
        print(f"\nShowing {start + 1}-{min(end, total)} of {total} messages")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        service.close()


def cmd_show(args: argparse.Namespace) -> int:
    """Show message details."""
    service = MessageService()

    try:
        load_schema_if_provided(args, service)
        service.load_file(args.file, include_metadata=args.metadata)
        msg = service.get_message(args.index)

        if not msg:
            print(f"Message {args.index} not found", file=sys.stderr)
            return 1

        if args.json:
            # JSON output
            data = msg.flatten()
            print(json.dumps(data, indent=2, default=str))
        else:
            # Pretty print
            print(f"Message #{msg.index}")
            print(f"Offset: {msg.offset}")
            print(f"Type: {msg.type_hint or 'unknown'}")
            print(f"Fields: {len(msg.fields)}")
            print("-" * 60)

            for name, field in msg.fields.items():
                value = field.value

                # Special handling for certain fields
                if name == "_raw_hex":
                    # Show truncated hex with byte count
                    hex_str = str(value)
                    if len(hex_str) > 60:
                        print(f"  {name}: {hex_str[:60]}...")
                        print(f"           ({len(hex_str) // 2} bytes)")
                    else:
                        print(f"  {name}: {hex_str}")
                elif name == "_json" and isinstance(value, dict):
                    # Pretty print JSON
                    print(f"  {name}:")
                    for k, v in value.items():
                        print(f"    {k}: {v}")
                elif isinstance(value, dict):
                    # Nested object
                    print(f"  {name}:")
                    for k, v in value.items():
                        print(f"    {k}: {v}")
                elif isinstance(value, list):
                    print(f"  {name}: [{len(value)} items]")
                    for i, item in enumerate(value[:5]):
                        print(f"    [{i}] {item}")
                    if len(value) > 5:
                        print(f"    ... and {len(value) - 5} more")
                else:
                    formatted = field.format_value(max_length=100)
                    print(f"  {name}: {formatted}")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        service.close()


def _get_match_context(msg: Message, query_lower: str) -> str:
    """Get brief description of why a message matched a search query."""
    if msg.type_hint and query_lower in msg.type_hint.lower():
        return f"type: {msg.type_hint}"
    for name in msg.field_names(include_nested=True):
        if query_lower in name.lower():
            return f"field: {name}"
    for name, field in msg.fields.items():
        val_str = str(field.value) if field.value is not None else ""
        if query_lower in val_str.lower():
            preview = val_str[:40] + "..." if len(val_str) > 40 else val_str
            return f"{name}={preview}"
    return ""


def cmd_search(args: argparse.Namespace) -> int:
    """Search messages."""
    service = MessageService()
    search = SearchService()

    try:
        load_schema_if_provided(args, service)
        service.load_file(args.file, include_metadata=args.metadata)
        messages = service.get_all_messages()

        if args.field_name:
            results = search.search_by_field_name(messages, args.query)
        elif args.field_value:
            results = search.search_by_field_value(
                messages, args.query, field_name=args.field_value
            )
        elif args.type_only:
            results = search.search_by_type(messages, args.query)
        else:
            results = search.search_combined(messages, args.query)

        print(f"Found {len(results)} matches for '{args.query}'")

        # Show first N results with match context
        limit = min(args.limit, len(results))
        query_lower = args.query.lower()
        for msg in results[:limit]:
            type_str = msg.type_hint or "unknown"
            context = _get_match_context(msg, query_lower)
            if context:
                print(f"  [{msg.index}] {type_str}  ({context})")
            else:
                print(f"  [{msg.index}] {type_str}")

        if len(results) > limit:
            print(f"  ... and {len(results) - limit} more")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        service.close()


def cmd_export(args: argparse.Namespace) -> int:
    """Export to CSV."""
    service = MessageService()
    search = SearchService()
    filter_svc = FilterService()
    export = ExportService()

    try:
        load_schema_if_provided(args, service)
        service.load_file(args.file, include_metadata=args.metadata)
        messages = service.get_all_messages()

        # Apply filters
        if args.type:
            messages = filter_svc.filter_by_type(messages, args.type)

        if args.has_field:
            messages = filter_svc.filter_by_field_exists(messages, args.has_field)

        if args.search:
            messages = search.search_combined(messages, args.search)

        if not messages:
            print("No messages to export", file=sys.stderr)
            return 1

        # Parse fields
        fields = [f.strip() for f in args.fields.split(",")] if args.fields else None

        # Export
        output = args.output or str(Path(args.file).with_suffix(".csv"))
        export.export_to_csv(
            messages,
            output_path=output,
            fields=fields,
            include_index=not args.no_index,
            include_offset=args.include_offset,
            include_type=not args.no_type,
        )

        print(f"Exported {len(messages)} messages to {output}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        service.close()


def cmd_fields(args: argparse.Namespace) -> int:
    """List all field names."""
    service = MessageService()

    try:
        load_schema_if_provided(args, service)
        service.load_file(args.file, include_metadata=args.metadata)
        fields = service.get_all_field_names()

        print(f"Found {len(fields)} unique fields:")
        for field in fields:
            print(f"  {field}")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        service.close()


def cmd_types(args: argparse.Namespace) -> int:
    """List all message types."""
    service = MessageService()

    try:
        load_schema_if_provided(args, service)
        service.load_file(args.file, include_metadata=args.metadata)
        messages = service.get_all_messages()
        types = service.get_unique_types()

        print(f"Found {len(types)} message types:")
        for t in types:
            count = sum(1 for m in messages if m.type_hint == t)
            print(f"  {t}: {count}")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        service.close()


def cmd_open(args: argparse.Namespace) -> int:
    """Open a folder containing .cq4, .cq4t, and Java class files."""
    from pathlib import Path

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"Error: Not a directory: {folder}", file=sys.stderr)
        return 1

    # Find all relevant files
    cq4_files = list(folder.glob("*.cq4"))
    cq4t_files = list(folder.glob("*.cq4t"))
    java_files = list(folder.rglob("*.java")) + list(folder.rglob("*.class"))

    if not cq4_files:
        print(f"Error: No .cq4 file found in {folder}", file=sys.stderr)
        return 1

    # Report what we found
    print(f"Folder: {folder}")
    print(f"Found: {len(cq4_files)} .cq4, {len(cq4t_files)} .cq4t, {len(java_files)} Java files")

    # Use first .cq4 file (or specified one)
    cq4_file = cq4_files[0]
    if len(cq4_files) > 1:
        print(f"\nMultiple .cq4 files found, using: {cq4_file.name}")
        for f in cq4_files:
            print(f"  - {f.name}")

    service = MessageService()

    try:
        # Load Java schema first (if any)
        encoding = getattr(args, "encoding", None)
        if java_files:
            try:
                schema = service.load_schema_directory(str(folder), encoding=encoding)
                print(f"\nSchema: {len(schema.messages)} message types loaded")
                for name in sorted(schema.messages.keys())[:10]:
                    msg_def = schema.messages[name]
                    print(f"  {name}: {len(msg_def.fields)} fields")
                if len(schema.messages) > 10:
                    print(f"  ... and {len(schema.messages) - 10} more")
            except Exception as e:
                print(f"\nWarning: Failed to load schema: {e}", file=sys.stderr)

        # Load tailer metadata (if any)
        if cq4t_files:
            cq4t_file = cq4t_files[0]
            tailer_meta = read_tailer_metadata(str(cq4t_file))
            if tailer_meta:
                print(f"\nTailer: {cq4t_file.name}")
                if "wireType" in tailer_meta:
                    print(f"  Wire Type: {tailer_meta['wireType']}")

        # Load the .cq4 file
        info = service.load_file(str(cq4_file), include_metadata=args.metadata)
        print(f"\nData File: {cq4_file.name}")
        print(f"Size: {info.file_size_str}")
        print(f"Messages: {info.message_count}")

        # Show type summary
        types = service.get_unique_types()
        if types:
            print(f"\nMessage Types ({len(types)}):")
            messages = service.get_all_messages()
            for t in types[:10]:
                count = sum(1 for m in messages if m.type_hint == t)
                print(f"  {t}: {count}")
            if len(types) > 10:
                print(f"  ... and {len(types) - 10} more")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        service.close()


def cmd_schema(args: argparse.Namespace) -> int:
    """Parse Java file or directory and show extracted schema."""
    if args.parse:
        # Parse a Java file and show the extracted schema
        try:
            schema = parse_java_file(args.parse)
            print(f"Parsed schema from: {args.parse}")
            print(f"Class: {schema.default_message}")
            print(f"Encoding: {schema.encoding}")
            print(f"Fields ({len(schema.messages[schema.default_message].fields)}):")
            for field in schema.messages[schema.default_message].fields:
                field_id_str = f" (id={field.field_id})" if field.field_id else ""
                print(f"  {field.name}: {field.type}{field_id_str}")

        except Exception as e:
            print(f"Error parsing Java file: {e}", file=sys.stderr)
            return 1
    elif args.scan_dir:
        # Scan a directory and show all discovered classes
        try:
            from .parser.java_parser import parse_directory
            schema = parse_directory(args.scan_dir)
            print(f"Scanned directory: {args.scan_dir}")
            print(f"Found {len(schema.messages)} message types:")
            for name, msg_def in sorted(schema.messages.items()):
                field_names = ", ".join(f.name for f in msg_def.fields[:5])
                if len(msg_def.fields) > 5:
                    field_names += ", ..."
                print(f"  {name}: {len(msg_def.fields)} fields ({field_names})")

        except Exception as e:
            print(f"Error scanning directory: {e}", file=sys.stderr)
            return 1
    else:
        # Print usage info
        print("Schema Support for Binary Message Decoding")
        print("=" * 60)
        print("\nSupported encoding formats (auto-detected):")
        print("  binary  - Chronicle's simple sequential binary")
        print("  thrift  - Apache Thrift TCompactProtocol")
        print("  sbe     - Simple Binary Encoding")
        print("\nSingle file mode:")
        print("  cqviewer list data.cq4 -S MyMessage.java")
        print("  cqviewer list data.cq4 -S MyMessage.class")
        print("  cqviewer list data.cq4 -S Order.java -S Trade.java")
        print("\nDirectory mode (loads all classes including nested):")
        print("  cqviewer list data.cq4 -D ./src/main/java/com/example/model/")
        print("  cqviewer list data.cq4 -D ./target/classes/com/example/model/")
        print("\nForce specific encoding:")
        print("  cqviewer list data.cq4 -S MyThrift.java -E thrift")
        print("  cqviewer list data.cq4 -D ./models/ -E sbe")
        print("\nParse and inspect schema:")
        print("  cqviewer schema --parse MyMessage.java")
        print("  cqviewer schema --scan-dir ./src/main/java/com/example/model/")
        print("\n" + "=" * 60)
        print("\nSupported Java field types:")
        print("  byte, short, int, long       - integers")
        print("  float, double                - floating point")
        print("  boolean                      - boolean")
        print("  String                       - string")
        print("  byte[]                       - binary data")
        print("\nNote: static and transient fields are excluded.")
        print("\nDirectory mode benefits:")
        print("  - Automatically discovers all Java classes")
        print("  - Extracts inner/nested classes from .java files")
        print("  - Merges all class definitions into one schema")
        print("  - Enables decoding of complex nested data structures")

    return 0


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="cqviewer",
        description="Chronicle Queue (.cq4) file viewer and exporter",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s 0.1.0"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Common arguments
    def add_common_args(p):
        p.add_argument("file", help="Path to .cq4 file")
        p.add_argument(
            "-T", "--tailer", metavar="FILE",
            help="Path to .cq4t tailer/metadata file"
        )
        p.add_argument(
            "-S", "--schema", metavar="FILE", action="append",
            help="Java schema file (.java or .class) for decoding BINARY_LIGHT messages. Can be specified multiple times."
        )
        p.add_argument(
            "-D", "--schema-dir", metavar="DIR",
            help="Directory containing Java class files. Recursively loads all .java and .class files, including inner classes."
        )
        p.add_argument(
            "-E", "--encoding", choices=["binary", "thrift", "sbe"],
            help="Force encoding format (auto-detected from Java file if not specified)"
        )
        p.add_argument(
            "-m", "--metadata", action="store_true",
            help="Include metadata messages"
        )

    # open command (folder mode)
    open_parser = subparsers.add_parser(
        "open",
        help="Open a folder containing .cq4, .cq4t, and Java class files"
    )
    open_parser.add_argument("folder", help="Path to folder")
    open_parser.add_argument(
        "-E", "--encoding", choices=["binary", "thrift", "sbe"],
        help="Force encoding format for Java schema"
    )
    open_parser.add_argument(
        "-m", "--metadata", action="store_true",
        help="Include metadata messages"
    )
    open_parser.set_defaults(func=cmd_open)

    # info command
    info_parser = subparsers.add_parser("info", help="Show file information")
    add_common_args(info_parser)
    info_parser.set_defaults(func=cmd_info)

    # list command
    list_parser = subparsers.add_parser("list", help="List messages")
    add_common_args(list_parser)
    list_parser.add_argument(
        "-n", "--limit", type=int, default=20,
        help="Number of messages to show (default: 20)"
    )
    list_parser.add_argument(
        "-o", "--offset", type=int, default=0,
        help="Starting offset (default: 0)"
    )
    list_parser.add_argument(
        "-t", "--type", help="Filter by message type"
    )
    list_parser.add_argument(
        "-f", "--has-field", help="Filter by field existence"
    )
    list_parser.add_argument(
        "-s", "--search", help="Search query"
    )
    list_parser.add_argument(
        "--fields", help="Comma-separated list of fields to display"
    )
    list_parser.set_defaults(func=cmd_list)

    # show command
    show_parser = subparsers.add_parser("show", help="Show message details")
    add_common_args(show_parser)
    show_parser.add_argument("index", type=int, help="Message index")
    show_parser.add_argument(
        "-j", "--json", action="store_true", help="Output as JSON"
    )
    show_parser.set_defaults(func=cmd_show)

    # search command
    search_parser = subparsers.add_parser("search", help="Search messages")
    add_common_args(search_parser)
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "-n", "--limit", type=int, default=20,
        help="Number of results to show (default: 20)"
    )
    search_parser.add_argument(
        "--field-name", action="store_true",
        help="Search field names only"
    )
    search_parser.add_argument(
        "--field-value", metavar="FIELD",
        help="Search within specific field"
    )
    search_parser.add_argument(
        "--type-only", action="store_true",
        help="Search message types only"
    )
    search_parser.set_defaults(func=cmd_search)

    # export command
    export_parser = subparsers.add_parser("export", help="Export to CSV")
    add_common_args(export_parser)
    export_parser.add_argument(
        "-o", "--output", help="Output file path (default: <input>.csv)"
    )
    export_parser.add_argument(
        "-t", "--type", help="Filter by message type"
    )
    export_parser.add_argument(
        "-f", "--has-field", help="Filter by field existence"
    )
    export_parser.add_argument(
        "-s", "--search", help="Search query"
    )
    export_parser.add_argument(
        "--fields", help="Comma-separated list of fields to export"
    )
    export_parser.add_argument(
        "--no-index", action="store_true", help="Exclude index column"
    )
    export_parser.add_argument(
        "--no-type", action="store_true", help="Exclude type column"
    )
    export_parser.add_argument(
        "--include-offset", action="store_true", help="Include offset column"
    )
    export_parser.set_defaults(func=cmd_export)

    # fields command
    fields_parser = subparsers.add_parser("fields", help="List all field names")
    add_common_args(fields_parser)
    fields_parser.set_defaults(func=cmd_fields)

    # types command
    types_parser = subparsers.add_parser("types", help="List all message types")
    add_common_args(types_parser)
    types_parser.set_defaults(func=cmd_types)

    # schema command
    schema_parser = subparsers.add_parser(
        "schema",
        help="Parse Java file or directory and show extracted schema"
    )
    schema_parser.add_argument(
        "--parse", metavar="FILE",
        help="Parse a .java or .class file and show extracted fields"
    )
    schema_parser.add_argument(
        "--scan-dir", metavar="DIR",
        help="Scan a directory for Java files and show all discovered classes"
    )
    schema_parser.set_defaults(func=cmd_schema)

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
