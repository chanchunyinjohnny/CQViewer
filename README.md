# CQViewer

A Python tool for inspecting and exporting Chronicle Queue (.cq4) data files. Automatically detects and decodes multiple binary encoding formats including Chronicle Wire, SBE (Simple Binary Encoding), and Apache Thrift.

## Features

- **Multi-Format Decoding**: Automatically detects and decodes Chronicle Wire binary, SBE, and Thrift-encoded messages
- **Java Schema Support**: Parse `.java` source files and `.class` bytecode to extract field definitions and detect encoding format
- **View Messages**: Browse messages with pagination, column selection, and nested field support (dot notation)
- **Search**: Find messages by field name, field value, or message type with match context and regex support
- **Filter**: Filter by type, field existence, or field value with operators (eq, ne, gt, gte, lt, lte, contains, regex)
- **Export**: Export to CSV with customizable field selection and nested object flattening
- **Detail View**: Inspect individual messages in JSON or flat view
- **Zero Core Dependencies**: Base functionality uses only the Python standard library; optional dependencies for enhanced CLI and Web UI

## Supported Encoding Formats

CQViewer automatically detects and decodes messages in the following formats:

| Format | Detection Method | Description |
|--------|-----------------|-------------|
| **Chronicle Wire Binary** | Native | Chronicle Queue's self-describing binary format with 40+ wire type codes |
| **SBE (Simple Binary Encoding)** | `@SbeField` annotations or `uk.co.real_logic.sbe` imports in Java schema | Fixed-size fields (int8–int64, float, double, char) with header parsing |
| **Apache Thrift (TCompactProtocol)** | `org.apache.thrift.TBase` or `TField` patterns in Java schema | Compact protocol with zigzag varint encoding, nested structs, and collections |

Encoding is auto-detected from Java source files, or can be explicitly specified with the `-E` flag.

## Requirements

- Python 3.10+
- No external dependencies for core functionality (works in air-gapped/intranet environments)
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
cqviewer list data.cq4 -S Order.java         # Load Java schema (auto-detects encoding)
cqviewer list data.cq4 -D ./model/ -E thrift # Load directory schema + explicit encoding
cqviewer list data.cq4 -D ./model/ -E sbe    # Load with SBE encoding override
cqviewer schema --parse Order.java           # Inspect parsed schema and detected encoding
```

#### Schema and Encoding Options

| Option | Description |
|--------|-------------|
| `-S, --schema FILE` | Load a Java source file (`.java`) or class file (`.class`) as schema |
| `-D, --schema-dir DIR` | Recursively scan a directory for `.java` and `.class` files |
| `-E, --encoding FORMAT` | Override encoding format: `binary`, `thrift`, or `sbe` |

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
- **Browse Messages**: Paginated table with configurable page size (25/50/100/200 rows) and column selection
- **Filter**: Filter by message type, field existence, or field value (eq, ne, gt, gte, lt, lte, contains, regex)
- **Search**: Search by field name, value, or message type with match context and result limit control
- **Export**: Export to CSV with field selection, optional Index/Type/Offset columns, and preview
- **Schema**: Auto-detected from directory; view loaded schema status (type count, encoding) and clear stale schemas
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
│   ├── parser/              # Binary format parsing
│   │   ├── wire_types.py        # Wire type code constants (40+)
│   │   ├── stop_bit.py          # Variable-length (stop-bit) integer decoder
│   │   ├── wire_reader.py       # Chronicle Wire binary parser
│   │   ├── cq4_reader.py        # .cq4 file reader (mmap-based)
│   │   ├── java_parser.py       # Java source/bytecode parser with encoding detection
│   │   ├── schema.py            # Schema definitions and BinaryDecoder
│   │   ├── sbe_decoder.py       # SBE (Simple Binary Encoding) decoder
│   │   └── thrift_decoder.py    # Apache Thrift TCompactProtocol decoder
│   ├── models/              # Data structures
│   │   ├── message.py           # Message with nested field support
│   │   ├── field.py             # Field with type inference and formatting
│   │   └── queue_info.py        # Queue metadata
│   └── services/            # Business logic
│       ├── message_service.py   # Load/cache/paginate/schema management
│       ├── search_service.py    # Multi-mode search with regex and match context
│       ├── filter_service.py    # Composite filtering with 8 operators
│       └── export_service.py    # CSV export with field flattening
├── run_cli.py               # Quick CLI (rich/tabulate)
├── run_ui.py                # Web UI (streamlit)
├── src/cqviewer/cli.py      # Advanced CLI (subcommands, schema, encoding)
└── tests/                   # 288 automated tests
```

## How It Works

1. **File Reading**: CQ4 files are read using memory-mapped I/O for efficient access. The reader parses the Chronicle Queue file header (version, roll cycle, index info) and iterates through excerpt headers to extract messages.

2. **Wire Format Parsing**: Messages in Chronicle Wire's self-describing binary format are decoded natively, supporting 40+ wire type codes including primitives, strings, timestamps, UUIDs, nested objects, and arrays.

3. **Schema-Based Decoding**: When Java source (`.java`) or bytecode (`.class`) files are provided, the parser:
   - Extracts field definitions (name, type, annotations)
   - Auto-detects the encoding format (SBE, Thrift, or plain binary) from imports and annotations
   - Uses the appropriate decoder (SBEDecoder, ThriftDecoder, or BinaryDecoder) to interpret the binary payload

4. **Search & Filter**: Messages can be searched by field name, value (with regex), or type. Filters support 8 comparison operators and can be combined with AND logic.

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
