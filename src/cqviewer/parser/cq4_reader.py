"""Chronicle Queue (.cq4) file reader.

Reads .cq4 files using memory-mapped I/O for efficient access.
"""

import mmap
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .wire_reader import WireReader, ParsedMessage


# Chronicle Queue message header format:
# 4 bytes: header word
#   - Bits 0-29: message length (30 bits, max ~1GB)
#   - Bit 30: metadata flag (1 = metadata, 0 = data)
#   - Bit 31: working/incomplete flag

HEADER_LENGTH_MASK = 0x3FFFFFFF  # 30 bits
HEADER_METADATA_FLAG = 0x40000000  # Bit 30
HEADER_WORKING_FLAG = 0x80000000  # Bit 31

# Special header values
HEADER_EOF = 0x00000000  # End of file/no more messages
HEADER_NOT_COMPLETE = 0x80000000  # Message being written


@dataclass
class QueueHeader:
    """Chronicle Queue file header information."""

    version: int = 0
    index: int = 0
    count: int = 0
    roll_cycle: str = ""
    index_count: int = 0
    index_spacing: int = 0


@dataclass
class Excerpt:
    """A single excerpt (message) from the queue."""

    index: int
    offset: int
    length: int
    is_metadata: bool
    data: ParsedMessage | None = None
    raw_bytes: bytes | None = None


class CQ4Reader:
    """Reader for Chronicle Queue .cq4 files."""

    def __init__(self, filepath: str | Path):
        """Initialize reader with file path.

        Args:
            filepath: Path to .cq4 file
        """
        self.filepath = Path(filepath)
        self._file = None
        self._mmap = None
        self._header: QueueHeader | None = None

    def __enter__(self) -> "CQ4Reader":
        """Open file for reading."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close file."""
        self.close()

    def open(self) -> None:
        """Open the .cq4 file."""
        if self._mmap is not None:
            return

        self._file = open(self.filepath, "rb")

        # Check file size - mmap cannot handle empty files
        file_size = self.filepath.stat().st_size
        if file_size == 0:
            self._header = QueueHeader()
            return

        self._mmap = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
        self._parse_file_header()

    def close(self) -> None:
        """Close the file and release resources."""
        if self._mmap is not None:
            self._mmap.close()
            self._mmap = None
        if self._file is not None:
            self._file.close()
            self._file = None

    @property
    def header(self) -> QueueHeader | None:
        """Get parsed file header."""
        return self._header

    def _parse_file_header(self) -> None:
        """Parse the Chronicle Queue file header."""
        if self._mmap is None or len(self._mmap) < 4:
            return

        self._header = QueueHeader()

        # The file starts with a metadata excerpt containing header info
        # Read the first message header
        header_word = struct.unpack_from("<I", self._mmap, 0)[0]

        if header_word == HEADER_EOF:
            return

        length = header_word & HEADER_LENGTH_MASK
        is_metadata = bool(header_word & HEADER_METADATA_FLAG)

        if is_metadata and length > 0 and length < len(self._mmap):
            # Parse header metadata
            try:
                data = self._mmap[4 : 4 + length]
                reader = WireReader(memoryview(data))
                fields = reader.read_object()

                # Extract header fields
                if "header" in fields:
                    header_data = fields["header"]
                    if isinstance(header_data, dict):
                        self._header.version = header_data.get("version", 0)
                        self._header.index = header_data.get("index", 0)
                        self._header.count = header_data.get("count", 0)
                        self._header.roll_cycle = header_data.get("rollCycle", "")
                        self._header.index_count = header_data.get("indexCount", 0)
                        self._header.index_spacing = header_data.get("indexSpacing", 0)
            except Exception:
                # Header parsing failed, use defaults
                pass

    def _read_header_at(self, offset: int) -> tuple[int, int, bool] | None:
        """Read message header at given offset.

        Returns:
            Tuple of (length, next_offset, is_metadata) or None if EOF
        """
        if self._mmap is None or offset + 4 > len(self._mmap):
            return None

        header_word = struct.unpack_from("<I", self._mmap, offset)[0]

        # Check for EOF or incomplete
        if header_word == HEADER_EOF:
            return None
        if header_word & HEADER_WORKING_FLAG:
            return None

        length = header_word & HEADER_LENGTH_MASK
        is_metadata = bool(header_word & HEADER_METADATA_FLAG)

        # Sanity check
        if length == 0 or offset + 4 + length > len(self._mmap):
            return None

        return length, offset + 4 + length, is_metadata

    def iter_excerpts(
        self, include_metadata: bool = False, start_index: int = 0
    ) -> Iterator[Excerpt]:
        """Iterate over excerpts in the file.

        Args:
            include_metadata: Whether to include metadata excerpts
            start_index: Starting excerpt index (for pagination)

        Yields:
            Excerpt objects
        """
        if self._mmap is None:
            return

        offset = 0
        index = 0

        while True:
            result = self._read_header_at(offset)
            if result is None:
                break

            length, next_offset, is_metadata = result

            if include_metadata or not is_metadata:
                if index >= start_index:
                    # Parse the message data
                    data_start = offset + 4
                    data_end = data_start + length
                    raw_data = self._mmap[data_start:data_end]

                    try:
                        reader = WireReader(memoryview(raw_data))
                        parsed = reader.read_message()
                    except Exception:
                        parsed = None

                    yield Excerpt(
                        index=index,
                        offset=offset,
                        length=length,
                        is_metadata=is_metadata,
                        data=parsed,
                        raw_bytes=bytes(raw_data),
                    )

                index += 1

            # Align to 4-byte boundary
            offset = (next_offset + 3) & ~3

    def read_excerpt(self, offset: int) -> Excerpt | None:
        """Read a single excerpt at the given offset.

        Args:
            offset: Byte offset in file

        Returns:
            Excerpt or None if invalid offset
        """
        result = self._read_header_at(offset)
        if result is None:
            return None

        length, _, is_metadata = result

        data_start = offset + 4
        data_end = data_start + length
        raw_data = self._mmap[data_start:data_end]

        try:
            reader = WireReader(memoryview(raw_data))
            parsed = reader.read_message()
        except Exception:
            parsed = None

        return Excerpt(
            index=-1,  # Unknown without iteration
            offset=offset,
            length=length,
            is_metadata=is_metadata,
            data=parsed,
            raw_bytes=bytes(raw_data),
        )

    def count_messages(self, include_metadata: bool = False) -> int:
        """Count total messages in the file.

        Args:
            include_metadata: Whether to count metadata excerpts

        Returns:
            Number of messages
        """
        count = 0
        offset = 0

        while True:
            result = self._read_header_at(offset)
            if result is None:
                break

            length, next_offset, is_metadata = result

            if include_metadata or not is_metadata:
                count += 1

            offset = (next_offset + 3) & ~3

        return count

    def get_messages(
        self, start: int = 0, limit: int = 100, include_metadata: bool = False
    ) -> list[Excerpt]:
        """Get a range of messages.

        Args:
            start: Starting index
            limit: Maximum number of messages to return
            include_metadata: Whether to include metadata

        Returns:
            List of Excerpt objects
        """
        results = []
        for i, excerpt in enumerate(self.iter_excerpts(include_metadata=include_metadata)):
            if i < start:
                continue
            if len(results) >= limit:
                break
            results.append(excerpt)
        return results
