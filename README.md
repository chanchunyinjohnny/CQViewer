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
- No external dependencies for CLI mode (works in air-gapped/intranet environments)
- tkinter + ttkbootstrap for GUI mode (optional)

## Installation

### Standard Installation

```bash
# Clone or download this repository
git clone <repo-url>
cd CQViewer

# Create virtual environment (optional)
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux

# Install (CLI only, no external dependencies)
pip install -e .
```

### Air-Gapped / Intranet Installation (No pip)

For environments without internet access or pip, you can run directly from source:

```bash
# Copy the entire CQViewer folder to your machine
# Then run directly using Python:

# Add src to PYTHONPATH and run CLI
cd /path/to/CQViewer
PYTHONPATH=src python -m cqviewer.cli info data.cq4
PYTHONPATH=src python -m cqviewer.cli list data.cq4
PYTHONPATH=src python -m cqviewer.cli export data.cq4 -o output.csv

# Or create a simple wrapper script (run_cqviewer.sh):
# #!/bin/bash
# SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# PYTHONPATH="$SCRIPT_DIR/src" python -m cqviewer.cli "$@"
```

On Windows (PowerShell):
```powershell
$env:PYTHONPATH = "src"
python -m cqviewer.cli info data.cq4
```

## Command Line Usage

The CLI works without any external dependencies:

```bash
# Open a folder (loads .cq4, .cq4t, and Java classes automatically)
cqviewer open ./my-data-folder/

# Show file information
cqviewer info data.cq4

# Show file info with tailer metadata (.cq4t file)
cqviewer info data.cq4 -T metadata.cq4t

# List messages (paginated)
cqviewer list data.cq4
cqviewer list data.cq4 -n 50 -o 100    # 50 messages starting at offset 100
cqviewer list data.cq4 -t Order        # filter by type
cqviewer list data.cq4 -f customerId   # filter by field existence
cqviewer list data.cq4 -s "C001"       # search

# Show single message details
cqviewer show data.cq4 42              # show message #42
cqviewer show data.cq4 42 --json       # output as JSON

# Search messages
cqviewer search data.cq4 "customer"
cqviewer search data.cq4 "Order" --type-only
cqviewer search data.cq4 "C001" --field-value customerId

# Export to CSV
cqviewer export data.cq4
cqviewer export data.cq4 -o output.csv
cqviewer export data.cq4 -t Order --fields customerId,amount

# List all field names
cqviewer fields data.cq4

# List all message types
cqviewer types data.cq4
```

### CLI Commands Reference

| Command | Description |
|---------|-------------|
| `open` | Open a folder containing .cq4, .cq4t, and Java class files |
| `info` | Show file information and type summary |
| `list` | List messages with pagination |
| `show` | Show details of a single message |
| `search` | Search messages by query |
| `export` | Export messages to CSV |
| `fields` | List all unique field names |
| `types` | List all message types with counts |
| `schema` | Show or generate example schema file |

### Common CLI Options

| Option | Description |
|--------|-------------|
| `-T, --tailer FILE` | Path to .cq4t tailer/metadata file |
| `-S, --schema FILE` | Java schema file (.java or .class) for BINARY_LIGHT decoding |
| `-D, --schema-dir DIR` | Directory containing Java files (loads all including nested classes) |
| `-E, --encoding` | Force encoding format: `binary`, `thrift`, or `sbe` |
| `-m, --metadata` | Include metadata messages |
| `-n, --limit N` | Limit number of results |
| `-o, --offset N` | Start from offset N |
| `-t, --type TYPE` | Filter by message type |
| `-f, --has-field FIELD` | Filter by field existence |
| `-s, --search QUERY` | Search query |

### Schema Support for BINARY_LIGHT Format

When Chronicle Queue uses BINARY_LIGHT wire format, messages are serialized without field names. To decode these messages, provide your Java bean class files directly:

```bash
# Use a single Java source file
cqviewer list data.cq4 -S FxTick.java

# Use a compiled class file
cqviewer list data.cq4 -S FxTick.class

# Use multiple Java files for different message types
cqviewer list data.cq4 -S FxTick.java -S Order.java -S Trade.java

# Parse a Java file and see extracted fields
cqviewer schema --parse FxTick.java
```

#### Directory Mode (Recommended for Nested Classes)

When your data structures include nested or inner classes, use directory mode to load all related class definitions at once:

```bash
# Load all Java files from a directory (including nested classes)
cqviewer list data.cq4 -D ./src/main/java/com/example/model/

# Load compiled classes from target directory
cqviewer list data.cq4 -D ./target/classes/com/example/model/

# Scan a directory to see all discovered classes
cqviewer schema --scan-dir ./src/main/java/com/example/model/

# Force specific encoding for directory
cqviewer list data.cq4 -D ./models/ -E thrift
cqviewer list data.cq4 -D ./models/ -E sbe
```

Directory mode benefits:
- Automatically discovers all `.java` and `.class` files recursively
- Extracts inner/nested classes from `.java` source files
- Merges all class definitions into a single schema
- Enables proper decoding of complex nested data structures

#### Supported Field Types

| Java Type | Binary Size |
|-----------|-------------|
| `byte` | 1 byte |
| `short` | 2 bytes |
| `int` | 4 bytes |
| `long` | 8 bytes |
| `float` | 4 bytes |
| `double` | 8 bytes |
| `boolean` | 1 byte |
| `String` | length-prefixed |
| `byte[]` | length-prefixed |

Note: Static and transient fields are automatically excluded.

## GUI Usage

To use the graphical interface, install with GUI support:

```bash
pip install -e ".[gui]"
cqviewer-gui
```

### Opening a File

1. Click **File > Open .cq4 File** or press `Ctrl+O`
2. Select a `.cq4` file from your filesystem
3. Messages will load in the table view

### Opening a Folder (Recommended)

Put your `.cq4` data file, `.cq4t` metadata file, and Java class definitions all in one folder, then:

1. Click **Open Folder** button or **File > Open Folder...** or press `Ctrl+Shift+O`
2. Select the folder
3. The tool automatically loads:
   - The `.cq4` data file
   - The `.cq4t` tailer/metadata file (if present)
   - All `.java` and `.class` files for schema (including nested classes)

This is the easiest way to work with BINARY_LIGHT encoded data that requires Java class definitions.

### Searching

Use the search bar to find messages:

- **By field name**: Type a field name (e.g., `customerId`) to find messages containing that field
- **By value**: Type a value to search across all fields (supports regex)
- **By type**: Type part of a type name (e.g., `Order`)

### Filtering

Use the filter dropdowns to narrow results:

- **Type Filter**: Select a specific message type from the dropdown
- **Field Filter**: Show only messages that have a specific field

Click **Apply Filters** to apply, or **Reset** to clear all filters.

### Viewing Message Details

Click on any message row to see its details in the right panel:

- **Tree View**: Hierarchical view of fields and nested objects
- **JSON View**: JSON representation of the message
- **Flat View**: Flattened key-value pairs (useful for seeing nested field paths)

### Exporting to CSV

1. Click **File > Export to CSV** or press `Ctrl+E`
2. Select which fields to include:
   - Use **Add >** to add selected fields
   - Use **Add All >>** to include all fields
   - Use **< Remove** to remove fields
3. Configure options:
   - Include message index
   - Include file offset
   - Include message type
4. Click **Preview** to see a sample of the output
5. Click **Export** and choose a save location

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open file |
| `Ctrl+E` | Export to CSV |
| `Ctrl+Q` | Quit |
| `F5` | Refresh |

## Programmatic Usage

You can also use CQViewer as a library:

```python
from cqviewer.parser import CQ4Reader
from cqviewer.services import SearchService, FilterService, ExportService

# Read a .cq4 file
with CQ4Reader("path/to/file.cq4") as reader:
    for excerpt in reader.iter_excerpts():
        print(f"Message {excerpt.index}: {excerpt.data.fields}")

# Using services
from cqviewer.services import MessageService

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
│   ├── services/        # Business logic
│   │   ├── message_service.py   # Load/cache/paginate
│   │   ├── search_service.py    # Search functionality
│   │   ├── filter_service.py    # Filter criteria
│   │   └── export_service.py    # CSV export
│   └── ui/              # User interface
│       ├── app.py           # Main application
│       └── widgets/         # UI components
└── tests/               # Automated tests
```

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

## Troubleshooting

### "No module named '_tkinter'"

tkinter is not installed. On macOS:
```bash
brew install python-tk@3.13
```

On Ubuntu/Debian:
```bash
sudo apt-get install python3-tk
```

### File won't open

- Ensure the file is a valid Chronicle Queue `.cq4` file
- Check that the file is not currently being written to by another process
- Try with a smaller file first to verify the installation works

## License

MIT License - Copyright (c) 2026 Chan Chun Yin Johnny
