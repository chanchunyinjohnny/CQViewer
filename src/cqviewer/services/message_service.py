"""Service for loading and managing Chronicle Queue messages."""

from pathlib import Path
from typing import Iterator

from ..parser.cq4_reader import CQ4Reader, Excerpt
from ..parser.schema import Schema, BinaryDecoder
from ..parser.java_parser import parse_java_file, merge_schemas, parse_directory
from ..models.message import Message
from ..models.queue_info import QueueInfo


class MessageService:
    """Service for loading, caching, and paginating messages."""

    def __init__(self):
        """Initialize the message service."""
        self._reader: CQ4Reader | None = None
        self._messages: list[Message] = []
        self._queue_info: QueueInfo | None = None
        self._is_loaded = False
        self._schema: Schema | None = None
        self._decoder: BinaryDecoder | None = None

    @property
    def is_loaded(self) -> bool:
        """Check if a file is currently loaded."""
        return self._is_loaded

    @property
    def queue_info(self) -> QueueInfo | None:
        """Get queue information."""
        return self._queue_info

    @property
    def message_count(self) -> int:
        """Get total number of loaded messages."""
        return len(self._messages)

    def set_schema(self, schema: Schema | None) -> None:
        """Set schema for decoding BINARY_LIGHT messages.

        Args:
            schema: Schema object or None to clear
        """
        self._schema = schema
        self._decoder = BinaryDecoder(schema) if schema else None

    def load_schema_file(self, filepath: str | Path, encoding: str | None = None) -> Schema:
        """Load schema from a .java or .class file.

        Args:
            filepath: Path to Java schema file (.java or .class)
            encoding: Force specific encoding (auto-detected if None)

        Returns:
            Loaded Schema object
        """
        filepath = Path(filepath)

        if filepath.suffix not in (".java", ".class"):
            raise ValueError(f"Unsupported file type: {filepath.suffix}. Use .java or .class files.")

        schema = parse_java_file(filepath, encoding=encoding)
        self.set_schema(schema)
        return schema

    def load_java_files(self, filepaths: list[str | Path], encoding: str | None = None) -> Schema:
        """Load schema from multiple .java or .class files.

        Args:
            filepaths: List of paths to .java or .class files
            encoding: Force specific encoding (auto-detected if None)

        Returns:
            Merged Schema object with all message types
        """
        schemas = []
        for filepath in filepaths:
            schema = parse_java_file(filepath, encoding=encoding)
            schemas.append(schema)

        merged = merge_schemas(*schemas)
        self.set_schema(merged)
        return merged

    def load_schema_directory(
        self,
        directory: str | Path,
        encoding: str | None = None,
        include_inner_classes: bool = True
    ) -> Schema:
        """Load schema from all Java files in a directory.

        Recursively scans the directory for .java and .class files,
        parses them (including inner classes), and merges into a single schema.

        This is useful when:
        - Your data structures reference multiple classes
        - You have nested/inner classes that need to be decoded
        - You want to load an entire model package at once

        Args:
            directory: Path to directory containing Java files
            encoding: Force specific encoding (auto-detected if None)
            include_inner_classes: Whether to extract inner classes from .java files

        Returns:
            Merged Schema object with all message types

        Raises:
            ValueError: If directory doesn't exist or contains no valid Java files
        """
        directory = Path(directory)
        if not directory.exists():
            raise ValueError(f"Directory not found: {directory}")
        if not directory.is_dir():
            raise ValueError(f"Not a directory: {directory}")

        schema = parse_directory(
            directory,
            encoding=encoding,
            include_inner_classes=include_inner_classes
        )
        self.set_schema(schema)
        return schema

    def load_file(
        self,
        filepath: str | Path,
        include_metadata: bool = False,
        schema: Schema | None = None,
    ) -> QueueInfo:
        """Load a .cq4 file.

        Args:
            filepath: Path to .cq4 file
            include_metadata: Whether to include metadata messages
            schema: Optional schema for decoding BINARY_LIGHT messages

        Returns:
            QueueInfo with file details

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is invalid
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        # Set schema if provided
        if schema is not None:
            self.set_schema(schema)

        # Close any existing reader
        self.close()

        # Open new reader
        self._reader = CQ4Reader(filepath)
        self._reader.open()

        # Load all messages into memory
        self._messages = []
        for excerpt in self._reader.iter_excerpts(include_metadata=include_metadata):
            message = self._excerpt_to_message(excerpt)
            self._messages.append(message)

        # Build queue info
        header = self._reader.header
        self._queue_info = QueueInfo(
            filepath=filepath,
            file_size=filepath.stat().st_size,
            message_count=len(self._messages),
            version=header.version if header else 0,
            roll_cycle=header.roll_cycle if header else "",
            index_count=header.index_count if header else 0,
            index_spacing=header.index_spacing if header else 0,
        )

        self._is_loaded = True
        return self._queue_info

    def close(self) -> None:
        """Close current file and release resources."""
        if self._reader is not None:
            self._reader.close()
            self._reader = None
        self._messages = []
        self._queue_info = None
        self._is_loaded = False
        # Note: schema is preserved across file loads

    def _excerpt_to_message(self, excerpt: Excerpt) -> Message:
        """Convert an Excerpt to a Message."""
        fields_dict = {}
        type_hint = None

        if excerpt.data is not None:
            type_hint = excerpt.data.type_hint
            fields_dict = excerpt.data.fields.copy()

            # If we have a schema and raw binary data, try to decode it
            if self._decoder and "_raw_hex" in fields_dict:
                raw_hex = fields_dict.get("_raw_hex", "")
                if raw_hex:
                    try:
                        raw_bytes = bytes.fromhex(raw_hex)
                        # Use type hint to determine message type, or use default
                        msg_type = None
                        if type_hint:
                            # Extract class name from type hint like "!types.ClassName"
                            msg_type = type_hint.split(".")[-1] if "." in type_hint else type_hint
                            msg_type = msg_type.lstrip("!")

                        decoded = self._decoder.decode(raw_bytes, msg_type)

                        # Replace raw fields with decoded fields
                        if decoded and "_error" not in decoded:
                            # Keep original _raw_hex for reference
                            original_raw = fields_dict.get("_raw_hex")
                            original_len = fields_dict.get("_raw_length")
                            fields_dict.clear()
                            fields_dict.update(decoded)
                            if original_raw:
                                fields_dict["_original_hex"] = original_raw
                            if original_len:
                                fields_dict["_original_length"] = original_len

                            # Set type_hint from schema if not already set
                            if not type_hint and self._schema:
                                # Use the message type we decoded with, or the default
                                if msg_type and msg_type in self._schema.messages:
                                    type_hint = msg_type
                                elif self._schema.default_message:
                                    type_hint = self._schema.default_message
                    except Exception:
                        pass  # Keep original fields on decode error

        return Message.from_parsed(
            index=excerpt.index,
            offset=excerpt.offset,
            type_hint=type_hint,
            fields_dict=fields_dict,
            is_metadata=excerpt.is_metadata,
        )

    def get_messages(self, start: int = 0, limit: int = 100) -> list[Message]:
        """Get a page of messages.

        Args:
            start: Starting index
            limit: Maximum number of messages

        Returns:
            List of messages
        """
        return self._messages[start : start + limit]

    def get_all_messages(self) -> list[Message]:
        """Get all loaded messages.

        Returns:
            List of all messages
        """
        return self._messages.copy()

    def get_message(self, index: int) -> Message | None:
        """Get a single message by index.

        Args:
            index: Message index

        Returns:
            Message or None if not found
        """
        for msg in self._messages:
            if msg.index == index:
                return msg
        return None

    def iter_messages(self) -> Iterator[Message]:
        """Iterate over all messages.

        Yields:
            Message objects
        """
        yield from self._messages

    def get_unique_types(self) -> list[str]:
        """Get list of unique type hints in loaded messages.

        Returns:
            Sorted list of unique type hints
        """
        types = set()
        for msg in self._messages:
            if msg.type_hint:
                types.add(msg.type_hint)
        return sorted(types)

    def get_all_field_names(self) -> list[str]:
        """Get list of all unique field names across all messages.

        Returns:
            Sorted list of unique field names
        """
        names = set()
        for msg in self._messages:
            names.update(msg.field_names(include_nested=True))
        return sorted(names)

    def get_page_count(self, page_size: int = 50) -> int:
        """Get total number of pages.

        Args:
            page_size: Number of messages per page

        Returns:
            Total page count
        """
        if not self._messages:
            return 0
        return (len(self._messages) + page_size - 1) // page_size
