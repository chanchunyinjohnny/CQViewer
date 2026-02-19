"""Tests for MessageService."""

import pytest
import struct
import tempfile
from pathlib import Path

from cqviewer.services.message_service import MessageService
from cqviewer.parser.cq4_reader import HEADER_METADATA_FLAG
from cqviewer.parser.wire_types import WireType
from cqviewer.parser.schema import Schema, MessageDef, FieldDef


def create_test_cq4_file(messages: list[bytes], include_header: bool = True) -> Path:
    """Create a test .cq4 file with given message data."""
    tmp = tempfile.NamedTemporaryFile(suffix=".cq4", delete=False)

    if include_header:
        nested_content = (
            bytes([0xC7]) + b"version"
            + bytes([WireType.INT32]) + struct.pack("<i", 5)
        )
        header_data = (
            bytes([0xC6]) + b"header"
            + bytes([WireType.NESTED_BLOCK, len(nested_content)])
            + nested_content
        )
        header_word = len(header_data) | HEADER_METADATA_FLAG
        tmp.write(struct.pack("<I", header_word))
        tmp.write(header_data)
        padding = (4 - (4 + len(header_data)) % 4) % 4
        tmp.write(b"\x00" * padding)

    for msg_data in messages:
        msg_word = len(msg_data)
        tmp.write(struct.pack("<I", msg_word))
        tmp.write(msg_data)
        padding = (4 - (4 + len(msg_data)) % 4) % 4
        tmp.write(b"\x00" * padding)

    tmp.close()
    return Path(tmp.name)


def create_simple_message(name: str, value: int) -> bytes:
    """Create a simple message with one field."""
    name_bytes = name.encode("utf-8")
    return (
        bytes([0xC0 + len(name_bytes)]) + name_bytes
        + bytes([WireType.INT32]) + struct.pack("<i", value)
    )


class TestMessageServiceBasic:
    """Tests for basic MessageService operations."""

    def test_initial_state(self):
        """Test service is not loaded initially."""
        service = MessageService()
        assert not service.is_loaded
        assert service.queue_info is None
        assert service.message_count == 0

    def test_load_file(self):
        """Test loading a .cq4 file."""
        msg = create_simple_message("count", 42)
        filepath = create_test_cq4_file([msg])

        try:
            service = MessageService()
            info = service.load_file(filepath)

            assert service.is_loaded
            assert info is not None
            assert info.message_count >= 1
            assert info.filepath == filepath
            assert info.file_size > 0
        finally:
            service.close()
            filepath.unlink()

    def test_load_file_not_found(self):
        """Test loading a non-existent file raises error."""
        service = MessageService()
        with pytest.raises(FileNotFoundError):
            service.load_file("/nonexistent/path.cq4")

    def test_close(self):
        """Test closing the service."""
        msg = create_simple_message("test", 1)
        filepath = create_test_cq4_file([msg])

        try:
            service = MessageService()
            service.load_file(filepath)
            assert service.is_loaded

            service.close()
            assert not service.is_loaded
            assert service.queue_info is None
            assert service.message_count == 0
        finally:
            filepath.unlink()

    def test_close_when_not_loaded(self):
        """Test closing an unloaded service is safe."""
        service = MessageService()
        service.close()  # Should not raise


class TestMessageServiceMessages:
    """Tests for message retrieval."""

    @pytest.fixture
    def loaded_service(self):
        """Create a loaded service with 5 messages."""
        messages = [create_simple_message("val", i) for i in range(5)]
        filepath = create_test_cq4_file(messages)

        service = MessageService()
        service.load_file(filepath)
        yield service

        service.close()
        filepath.unlink()

    def test_get_all_messages(self, loaded_service):
        """Test getting all messages."""
        msgs = loaded_service.get_all_messages()
        assert len(msgs) == 5

    def test_get_all_messages_returns_copy(self, loaded_service):
        """Test that get_all_messages returns a copy."""
        msgs1 = loaded_service.get_all_messages()
        msgs2 = loaded_service.get_all_messages()
        assert msgs1 is not msgs2

    def test_get_messages_paginated(self, loaded_service):
        """Test paginated message retrieval."""
        page1 = loaded_service.get_messages(start=0, limit=2)
        assert len(page1) == 2

        page2 = loaded_service.get_messages(start=2, limit=2)
        assert len(page2) == 2

        page3 = loaded_service.get_messages(start=4, limit=2)
        assert len(page3) == 1

    def test_get_message_by_index(self, loaded_service):
        """Test getting a single message by index."""
        msg = loaded_service.get_message(0)
        assert msg is not None
        assert msg.index == 0

    def test_get_message_not_found(self, loaded_service):
        """Test getting a non-existent message returns None."""
        msg = loaded_service.get_message(999)
        assert msg is None

    def test_iter_messages(self, loaded_service):
        """Test iterating over messages."""
        msgs = list(loaded_service.iter_messages())
        assert len(msgs) == 5

    def test_message_count(self, loaded_service):
        """Test message count property."""
        assert loaded_service.message_count == 5


class TestMessageServiceMetadata:
    """Tests for metadata and type operations."""

    @pytest.fixture
    def loaded_service(self):
        """Create a loaded service."""
        messages = [
            create_simple_message("a", 1),
            create_simple_message("b", 2),
        ]
        filepath = create_test_cq4_file(messages)

        service = MessageService()
        service.load_file(filepath)
        yield service

        service.close()
        filepath.unlink()

    def test_get_unique_types(self, loaded_service):
        """Test getting unique types (may be empty for simple messages)."""
        types = loaded_service.get_unique_types()
        assert isinstance(types, list)

    def test_get_all_field_names(self, loaded_service):
        """Test getting all field names."""
        names = loaded_service.get_all_field_names()
        assert isinstance(names, list)
        assert len(names) > 0

    def test_get_page_count(self, loaded_service):
        """Test page count calculation."""
        assert loaded_service.get_page_count(page_size=1) == 2
        assert loaded_service.get_page_count(page_size=50) == 1

    def test_get_page_count_empty(self):
        """Test page count when no messages loaded."""
        service = MessageService()
        assert service.get_page_count() == 0


class TestMessageServiceSchema:
    """Tests for schema operations."""

    def test_set_schema(self):
        """Test setting a schema."""
        service = MessageService()
        schema = Schema.from_dict({
            "messages": {"Test": {"fields": [{"name": "x", "type": "int32"}]}},
            "default": "Test",
        })
        service.set_schema(schema)
        assert service._schema is schema
        assert service._decoder is not None

    def test_clear_schema(self):
        """Test clearing a schema."""
        service = MessageService()
        schema = Schema.from_dict({
            "messages": {"Test": {"fields": [{"name": "x", "type": "int32"}]}},
        })
        service.set_schema(schema)
        service.set_schema(None)
        assert service._schema is None
        assert service._decoder is None

    def test_load_schema_file(self):
        """Test loading schema from a .java file."""
        java_code = """
        public class Order {
            private long orderId;
            private double price;
        }
        """
        with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f:
            f.write(java_code)
            f.flush()
            filepath = Path(f.name)

        try:
            service = MessageService()
            schema = service.load_schema_file(filepath)

            assert "Order" in schema.messages
            assert service._schema is schema
        finally:
            filepath.unlink()

    def test_load_schema_file_unsupported(self):
        """Test loading unsupported file type raises error."""
        service = MessageService()
        with pytest.raises(ValueError, match="Unsupported file type"):
            service.load_schema_file("test.txt")

    def test_load_schema_directory(self):
        """Test loading schema from a directory."""
        java_code = """
        public class Trade {
            private long tradeId;
        }
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Trade.java").write_text(java_code)

            service = MessageService()
            schema = service.load_schema_directory(tmpdir)

            assert "Trade" in schema.messages

    def test_load_schema_directory_not_found(self):
        """Test loading from non-existent directory."""
        service = MessageService()
        with pytest.raises(ValueError, match="Directory not found"):
            service.load_schema_directory("/nonexistent/dir")

    def test_load_schema_directory_not_a_dir(self):
        """Test loading from a file path (not directory)."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            filepath = Path(f.name)

        try:
            service = MessageService()
            with pytest.raises(ValueError, match="Not a directory"):
                service.load_schema_directory(filepath)
        finally:
            filepath.unlink()

    def test_schema_preserved_across_file_loads(self):
        """Test that schema is preserved when loading a new file."""
        schema = Schema.from_dict({
            "messages": {"Test": {"fields": [{"name": "x", "type": "int32"}]}},
        })

        msg = create_simple_message("test", 1)
        filepath = create_test_cq4_file([msg])

        try:
            service = MessageService()
            service.set_schema(schema)
            service.load_file(filepath)
            assert service._schema is schema

            service.close()
            # Schema should still be set after close
            assert service._schema is schema
        finally:
            filepath.unlink()

    def test_load_java_files(self):
        """Test loading schema from multiple Java files."""
        order_code = "public class Order { private long orderId; }"
        trade_code = "public class Trade { private long tradeId; }"

        with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f1:
            f1.write(order_code)
            f1.flush()
            path1 = Path(f1.name)

        with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f2:
            f2.write(trade_code)
            f2.flush()
            path2 = Path(f2.name)

        try:
            service = MessageService()
            schema = service.load_java_files([path1, path2])

            assert "Order" in schema.messages
            assert "Trade" in schema.messages
        finally:
            path1.unlink()
            path2.unlink()

    def test_load_file_with_schema(self):
        """Test loading a file with a schema passed directly."""
        schema = Schema.from_dict({
            "messages": {"Test": {"fields": [{"name": "x", "type": "int32"}]}},
        })

        msg = create_simple_message("test", 1)
        filepath = create_test_cq4_file([msg])

        try:
            service = MessageService()
            service.load_file(filepath, schema=schema)
            assert service._schema is schema
        finally:
            service.close()
            filepath.unlink()

    def test_load_file_with_metadata(self):
        """Test loading a file with metadata included."""
        msg = create_simple_message("data", 1)
        filepath = create_test_cq4_file([msg], include_header=True)

        try:
            service = MessageService()
            info = service.load_file(filepath, include_metadata=True)
            # With metadata, count should be higher than data-only
            count_with = info.message_count

            service.close()
            info2 = service.load_file(filepath, include_metadata=False)
            count_without = info2.message_count

            assert count_with > count_without
        finally:
            service.close()
            filepath.unlink()
