# CQViewer

A Python tool for inspecting and exporting Chronicle Queue (.cq4) data files.

## Features

- **View Messages**: Browse Chronicle Queue messages with pagination (50-100 rows per page)
- **Search**: Find messages by field name, field value, or message type
- **Filter**: Filter messages by type or field existence
- **Export**: Export messages to CSV with customizable field selection
- **Detail View**: Inspect individual messages in tree, JSON, or flat view

## Requirements

- Python 3.10+
- No external dependencies for standard CLI mode (works in air-gapped/intranet environments)
- Optional dependencies:
  - `rich` + `tabulate`: Enhanced CLI output (`run_cli.py`)
  - `streamlit` + `pandas`: Web UI (`run_ui.py`)

## Installation

```bash
# Clone or download this repository
git clone <repo-url>
cd CQViewer
```

## Command Line Usage

CQViewer provides two CLI interfaces:

### Quick CLI (`run_cli.py`)

Best for quick one-off commands. Requires `rich` and `tabulate` for formatted output (falls back to plain text if unavailable).

```bash
python run_cli.py ./data/                    # Open folder
python run_cli.py ./data/queue.cq4           # Open specific file
python run_cli.py ./data/ -n 100             # Show first 100 messages
python run_cli.py ./data/ --search orderId   # Search for 'orderId'
python run_cli.py ./data/ --types            # List message types
python run_cli.py ./data/ --fields           # List all field names
python run_cli.py ./data/ --export out.csv   # Export to CSV
python run_cli.py ./data/ --show 5           # Show message at index 5
```

| Option | Description |
|--------|-------------|
| `-n, --limit N` | Number of messages to show (default: 50) |
| `-o, --offset N` | Starting offset (default: 0) |
| `-t, --type TYPE` | Filter by message type |
| `-s, --search QUERY` | Search query |
| `--show INDEX` | Show detailed view of message at INDEX |
| `--types` | List all message types |
| `--fields` | List all unique field names |
| `--export FILE` | Export to CSV file |
| `--export-fields` | Comma-separated fields to export |
| `-m, --metadata` | Include metadata messages |

### Advanced CLI (`cqviewer` / `cli.py`)

Subcommand-based CLI with additional features: Java schema loading, tailer metadata, encoding override, and more. No external dependencies required.

```bash
# Run via: PYTHONPATH=src python -m cqviewer.cli <command> [options]
cqviewer open ./data/                        # Open folder (auto-finds .cq4, .cq4t, Java files)
cqviewer info data.cq4                       # Show file info
cqviewer list data.cq4 -n 50                 # List messages with pagination
cqviewer show data.cq4 3                     # Show message at index 3
cqviewer search data.cq4 "orderId"           # Search messages
cqviewer export data.cq4 -o out.csv          # Export to CSV
cqviewer list data.cq4 -S Order.java         # Load with Java schema
cqviewer list data.cq4 -D ./model/ -E thrift # Load with directory schema + encoding
cqviewer schema --parse Order.java           # Inspect parsed schema
```

## Web UI Usage

Run the Streamlit web interface:

```bash
python run_ui.py
```

Or with a specific port:
```bash
python run_ui.py -- --server.port 8501
```

### Features

- **File Browser**: Navigate folders with parent directory, Home, and Desktop shortcuts
- **Browse Messages**: View messages in a paginated table with column selection
- **Filter**: Filter by message type, field existence, or field value (eq, gt, contains, regex, etc.)
- **Search**: Search by field name, value, or message type with match context
- **Export**: Export to CSV with field selection (consistent with CLI export)
- **Schema**: View loaded schema status and clear stale schemas
- **Cell Viewer**: Inspect full values of truncated cells

## Programmatic Usage

You can also use CQViewer as a library (run with `PYTHONPATH=src`):

```python
from cqviewer.services.message_service import MessageService
from cqviewer.services.search_service import SearchService
from cqviewer.services.filter_service import FilterService
from cqviewer.services.export_service import ExportService

service = MessageService()
service.load_file("path/to/file.cq4")

# Get all messages
messages = service.get_all_messages()

# Search
search = SearchService()
results = search.search_by_field_name(messages, "customerId")

# Filter
filter_svc = FilterService()
orders = filter_svc.filter_by_type(messages, "Order")

# Export
export = ExportService()
export.export_to_csv(orders, "output.csv", fields=["customerId", "amount"])
```

## Project Structure

```
cqviewer/
├── src/cqviewer/
│   ├── parser/          # Binary format parsing
│   │   ├── wire_types.py    # Type code constants
│   │   ├── stop_bit.py      # Variable-length integer decoder
│   │   ├── wire_reader.py   # Chronicle Wire binary parser
│   │   └── cq4_reader.py    # .cq4 file reader (mmap-based)
│   ├── models/          # Data structures
│   │   ├── message.py       # Message representation
│   │   ├── field.py         # Field with type info
│   │   └── queue_info.py    # Queue metadata
│   └── services/        # Business logic
│       ├── message_service.py   # Load/cache/paginate
│       ├── search_service.py    # Search functionality
│       ├── filter_service.py    # Filter criteria
│       └── export_service.py    # CSV export
├── run_cli.py           # Quick CLI (rich/tabulate)
├── run_ui.py            # Web UI (streamlit)
├── src/cqviewer/cli.py  # Advanced CLI (subcommands, schema support)
└── tests/               # Automated tests
```

## Running Tests

```bash
pip install pytest
PYTHONPATH=src pytest tests/ -v
```

## Troubleshooting

### File won't open

- Ensure the file is a valid Chronicle Queue `.cq4` file
- Check that the file is not currently being written to by another process
- Try with a smaller file first to verify the installation works

## Support

If you find this project useful, consider supporting its development:

- [GitHub Sponsors](https://github.com/sponsors/chanchunyinjohnny)
- [Buy Me a Coffee](https://buymeacoffee.com/chanchunyinjohnny)
- [Ko-fi](https://ko-fi.com/chanchunyinjohnny)

## License

MIT License - Copyright (c) 2026 Chan Chun Yin Johnny
