"""Tests for CQ4 file reader."""

import pytest
import tempfile
import struct
from pathlib import Path
from cqviewer.parser.cq4_reader import CQ4Reader, HEADER_METADATA_FLAG
from cqviewer.parser.wire_types import WireType


def create_test_cq4_file(messages: list[bytes], include_header: bool = True) -> Path:
    """Create a test .cq4 file with given message data.

    Args:
        messages: List of message payloads
        include_header: Whether to include a metadata header

    Returns:
        Path to temporary file
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".cq4", delete=False)

    if include_header:
        # Create a simple metadata header
        # Nested content: field name "version" (8 bytes) + INT32 value (5 bytes) = 13 bytes
        nested_content = (
            bytes([0xC7]) + b"version"  # Compact field name "version" (1 + 7 = 8 bytes)
            + bytes([WireType.INT32]) + struct.pack("<i", 5)  # INT32 5 (1 + 4 = 5 bytes)
        )
        # Field: header with nested content
        header_data = (
            bytes([0xC6]) + b"header"  # Compact field name "header" (1 + 6 = 7 bytes)
            + bytes([WireType.NESTED_BLOCK, len(nested_content)])  # Nested block with correct length
            + nested_content
        )

        # Write header message
        header_word = len(header_data) | HEADER_METADATA_FLAG
        tmp.write(struct.pack("<I", header_word))
        tmp.write(header_data)

        # Align to 4 bytes
        padding = (4 - (4 + len(header_data)) % 4) % 4
        tmp.write(b"\x00" * padding)

    # Write data messages
    for msg_data in messages:
        msg_word = len(msg_data)  # Data message (no metadata flag)
        tmp.write(struct.pack("<I", msg_word))
        tmp.write(msg_data)

        # Align to 4 bytes
        padding = (4 - (4 + len(msg_data)) % 4) % 4
        tmp.write(b"\x00" * padding)

    tmp.close()
    return Path(tmp.name)


def create_simple_message(name: str, value: int) -> bytes:
    """Create a simple message with one field."""
    # Compact field name + INT32 value
    name_bytes = name.encode("utf-8")
    return (
        bytes([0xC0 + len(name_bytes)]) + name_bytes
        + bytes([WireType.INT32]) + struct.pack("<i", value)
    )


class TestCQ4Reader:
    """Tests for CQ4Reader."""

    def test_open_close(self):
        """Test opening and closing file."""
        msg = create_simple_message("test", 42)
        filepath = create_test_cq4_file([msg])

        try:
            reader = CQ4Reader(filepath)
            reader.open()
            assert reader._mmap is not None
            reader.close()
            assert reader._mmap is None
        finally:
            filepath.unlink()

    def test_context_manager(self):
        """Test using reader as context manager."""
        msg = create_simple_message("test", 42)
        filepath = create_test_cq4_file([msg])

        try:
            with CQ4Reader(filepath) as reader:
                assert reader._mmap is not None
            assert reader._mmap is None
        finally:
            filepath.unlink()

    def test_read_single_message(self):
        """Test reading a single message."""
        msg = create_simple_message("count", 42)
        filepath = create_test_cq4_file([msg])

        try:
            with CQ4Reader(filepath) as reader:
                messages = reader.get_messages()
                assert len(messages) == 1

                excerpt = messages[0]
                assert excerpt.data is not None
                assert "count" in excerpt.data.fields
                assert excerpt.data.fields["count"] == 42
        finally:
            filepath.unlink()

    def test_read_multiple_messages(self):
        """Test reading multiple messages."""
        messages_data = [
            create_simple_message("a", 1),
            create_simple_message("b", 2),
            create_simple_message("c", 3),
        ]
        filepath = create_test_cq4_file(messages_data)

        try:
            with CQ4Reader(filepath) as reader:
                messages = reader.get_messages()
                assert len(messages) == 3

                values = [m.data.fields.get("a") or m.data.fields.get("b") or m.data.fields.get("c")
                          for m in messages]
                assert values == [1, 2, 3]
        finally:
            filepath.unlink()

    def test_count_messages(self):
        """Test counting messages."""
        messages_data = [create_simple_message("x", i) for i in range(5)]
        filepath = create_test_cq4_file(messages_data)

        try:
            with CQ4Reader(filepath) as reader:
                count = reader.count_messages()
                assert count == 5
        finally:
            filepath.unlink()

    def test_iterate_excerpts(self):
        """Test iterating over excerpts."""
        messages_data = [create_simple_message("val", i) for i in range(3)]
        filepath = create_test_cq4_file(messages_data)

        try:
            with CQ4Reader(filepath) as reader:
                excerpts = list(reader.iter_excerpts())
                assert len(excerpts) == 3

                for i, excerpt in enumerate(excerpts):
                    assert excerpt.index == i
                    assert not excerpt.is_metadata
        finally:
            filepath.unlink()

    def test_include_metadata(self):
        """Test including metadata messages."""
        messages_data = [create_simple_message("data", 1)]
        filepath = create_test_cq4_file(messages_data, include_header=True)

        try:
            with CQ4Reader(filepath) as reader:
                # Without metadata
                without = reader.count_messages(include_metadata=False)

                # With metadata
                with_meta = reader.count_messages(include_metadata=True)

                assert with_meta > without
        finally:
            filepath.unlink()

    def test_pagination(self):
        """Test paginated message retrieval."""
        messages_data = [create_simple_message("n", i) for i in range(10)]
        filepath = create_test_cq4_file(messages_data)

        try:
            with CQ4Reader(filepath) as reader:
                # Get first page
                page1 = reader.get_messages(start=0, limit=3)
                assert len(page1) == 3
                assert page1[0].data.fields["n"] == 0

                # Get second page
                page2 = reader.get_messages(start=3, limit=3)
                assert len(page2) == 3
                assert page2[0].data.fields["n"] == 3

                # Get last page (partial)
                page4 = reader.get_messages(start=9, limit=3)
                assert len(page4) == 1
        finally:
            filepath.unlink()

    def test_header_parsing(self):
        """Test parsing file header."""
        msg = create_simple_message("test", 1)
        filepath = create_test_cq4_file([msg], include_header=True)

        try:
            with CQ4Reader(filepath) as reader:
                header = reader.header
                assert header is not None
                assert header.version == 5
        finally:
            filepath.unlink()

    def test_file_not_found(self):
        """Test handling missing file."""
        reader = CQ4Reader("/nonexistent/path/file.cq4")
        with pytest.raises(FileNotFoundError):
            reader.open()

    def test_empty_file(self):
        """Test handling empty file."""
        tmp = tempfile.NamedTemporaryFile(suffix=".cq4", delete=False)
        tmp.close()
        filepath = Path(tmp.name)

        try:
            with CQ4Reader(filepath) as reader:
                messages = reader.get_messages()
                assert len(messages) == 0
        finally:
            filepath.unlink()

    def test_read_excerpt_at_offset(self):
        """Test reading a single excerpt at a specific offset."""
        msg = create_simple_message("val", 99)
        filepath = create_test_cq4_file([msg])

        try:
            with CQ4Reader(filepath) as reader:
                # First find offset of data message by iterating
                excerpts = list(reader.iter_excerpts())
                assert len(excerpts) >= 1
                offset = excerpts[0].offset

                # Now read at that offset
                excerpt = reader.read_excerpt(offset)
                assert excerpt is not None
                assert excerpt.data is not None
                assert excerpt.data.fields.get("val") == 99
        finally:
            filepath.unlink()

    def test_read_excerpt_invalid_offset(self):
        """Test reading excerpt at invalid offset returns None."""
        msg = create_simple_message("test", 1)
        filepath = create_test_cq4_file([msg])

        try:
            with CQ4Reader(filepath) as reader:
                result = reader.read_excerpt(999999)
                assert result is None
        finally:
            filepath.unlink()

    def test_iter_excerpts_with_start_index(self):
        """Test iterating excerpts starting from a specific index."""
        messages_data = [create_simple_message("n", i) for i in range(5)]
        filepath = create_test_cq4_file(messages_data)

        try:
            with CQ4Reader(filepath) as reader:
                excerpts = list(reader.iter_excerpts(start_index=2))
                assert len(excerpts) == 3
                assert excerpts[0].index == 2
        finally:
            filepath.unlink()

    def test_get_messages_with_metadata(self):
        """Test getting messages including metadata."""
        msg = create_simple_message("data", 1)
        filepath = create_test_cq4_file([msg], include_header=True)

        try:
            with CQ4Reader(filepath) as reader:
                without = reader.get_messages(include_metadata=False)
                with_meta = reader.get_messages(include_metadata=True)
                assert len(with_meta) > len(without)
        finally:
            filepath.unlink()

    def test_double_open(self):
        """Test opening an already-open reader is a no-op."""
        msg = create_simple_message("test", 1)
        filepath = create_test_cq4_file([msg])

        try:
            reader = CQ4Reader(filepath)
            reader.open()
            mmap_ref = reader._mmap
            reader.open()  # Should not re-open
            assert reader._mmap is mmap_ref
            reader.close()
        finally:
            filepath.unlink()

    def test_double_close(self):
        """Test closing an already-closed reader is safe."""
        msg = create_simple_message("test", 1)
        filepath = create_test_cq4_file([msg])

        try:
            reader = CQ4Reader(filepath)
            reader.open()
            reader.close()
            reader.close()  # Should not raise
        finally:
            filepath.unlink()
