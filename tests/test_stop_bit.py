"""Tests for stop-bit encoding decoder."""

import pytest
from cqviewer.parser.stop_bit import read_stop_bit, read_stop_bit_long


class TestReadStopBit:
    """Tests for read_stop_bit function."""

    def test_single_byte_zero(self):
        """Test decoding zero."""
        data = bytes([0x00])
        value, consumed = read_stop_bit(data)
        assert value == 0
        assert consumed == 1

    def test_single_byte_small(self):
        """Test decoding small values (< 128)."""
        # Value 42 = 0x2A
        data = bytes([0x2A])
        value, consumed = read_stop_bit(data)
        assert value == 42
        assert consumed == 1

    def test_single_byte_max(self):
        """Test decoding 127 (max single byte value)."""
        data = bytes([0x7F])
        value, consumed = read_stop_bit(data)
        assert value == 127
        assert consumed == 1

    def test_two_bytes(self):
        """Test decoding values 128-16383."""
        # Value 128 = 0x80 0x01 (1 in second byte, shifted left 7)
        data = bytes([0x80, 0x01])
        value, consumed = read_stop_bit(data)
        assert value == 128
        assert consumed == 2

        # Value 300 = 0xAC 0x02
        # 300 = 0b100101100 = 0b10 (high) + 0b0101100 (low)
        # Low byte: 0b10101100 = 0xAC (with high bit set)
        # High byte: 0b00000010 = 0x02
        data = bytes([0xAC, 0x02])
        value, consumed = read_stop_bit(data)
        assert value == 300
        assert consumed == 2

    def test_three_bytes(self):
        """Test decoding larger values."""
        # Value 16384 = 0x80 0x80 0x01
        data = bytes([0x80, 0x80, 0x01])
        value, consumed = read_stop_bit(data)
        assert value == 16384
        assert consumed == 3

    def test_offset(self):
        """Test reading from offset."""
        # Padding byte followed by value 42
        data = bytes([0xFF, 0x2A])
        value, consumed = read_stop_bit(data, offset=1)
        assert value == 42
        assert consumed == 1

    def test_truncated_raises(self):
        """Test truncated encoding raises error."""
        # High bit set but no continuation byte
        data = bytes([0x80])
        with pytest.raises(ValueError, match="Truncated"):
            read_stop_bit(data)

    def test_memoryview(self):
        """Test reading from memoryview."""
        data = memoryview(bytes([0x2A]))
        value, consumed = read_stop_bit(data)
        assert value == 42
        assert consumed == 1


class TestReadStopBitLong:
    """Tests for read_stop_bit_long (signed values)."""

    def test_positive_zero(self):
        """Test decoding signed zero."""
        # ZigZag: 0 -> 0
        data = bytes([0x00])
        value, consumed = read_stop_bit_long(data)
        assert value == 0
        assert consumed == 1

    def test_positive_small(self):
        """Test decoding small positive values."""
        # ZigZag: 1 -> 2
        data = bytes([0x02])
        value, consumed = read_stop_bit_long(data)
        assert value == 1
        assert consumed == 1

        # ZigZag: 21 -> 42
        data = bytes([0x2A])
        value, consumed = read_stop_bit_long(data)
        assert value == 21
        assert consumed == 1

    def test_negative_small(self):
        """Test decoding small negative values."""
        # ZigZag: -1 -> 1
        data = bytes([0x01])
        value, consumed = read_stop_bit_long(data)
        assert value == -1
        assert consumed == 1

        # ZigZag: -2 -> 3
        data = bytes([0x03])
        value, consumed = read_stop_bit_long(data)
        assert value == -2
        assert consumed == 1

    def test_larger_values(self):
        """Test decoding larger signed values."""
        # ZigZag: 64 -> 128 = 0x80 0x01
        data = bytes([0x80, 0x01])
        value, consumed = read_stop_bit_long(data)
        assert value == 64
        assert consumed == 2

        # ZigZag: -64 -> 127 = 0x7F
        data = bytes([0x7F])
        value, consumed = read_stop_bit_long(data)
        assert value == -64
        assert consumed == 1
