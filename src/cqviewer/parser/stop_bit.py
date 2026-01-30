"""Stop-bit encoding decoder for Chronicle Wire format.

Chronicle Queue uses stop-bit encoding for variable-length integers.
The high bit of each byte indicates if more bytes follow:
- 0xxxxxxx: Final byte, value in lower 7 bits
- 1xxxxxxx: More bytes follow, lower 7 bits are part of value
"""

from typing import BinaryIO


def read_stop_bit(data: bytes | memoryview, offset: int = 0) -> tuple[int, int]:
    """Read a stop-bit encoded integer from bytes.

    Args:
        data: Bytes or memoryview to read from
        offset: Starting position in data

    Returns:
        Tuple of (decoded_value, bytes_consumed)

    Raises:
        ValueError: If data is truncated or encoding is invalid
    """
    result = 0
    shift = 0
    pos = offset

    while True:
        if pos >= len(data):
            raise ValueError(f"Truncated stop-bit encoding at offset {offset}")

        byte = data[pos]
        pos += 1

        # Lower 7 bits contribute to value
        result |= (byte & 0x7F) << shift
        shift += 7

        # High bit clear means this is the last byte
        if (byte & 0x80) == 0:
            break

        # Sanity check: don't allow more than 10 bytes (70 bits)
        if shift > 63:
            raise ValueError(f"Stop-bit encoding too long at offset {offset}")

    return result, pos - offset


def read_stop_bit_long(data: bytes | memoryview, offset: int = 0) -> tuple[int, int]:
    """Read a stop-bit encoded long (signed) from bytes.

    For signed integers, the sign is encoded in the least significant bit:
    - Even values are positive: actual_value = encoded_value >> 1
    - Odd values are negative: actual_value = ~(encoded_value >> 1)

    Args:
        data: Bytes or memoryview to read from
        offset: Starting position in data

    Returns:
        Tuple of (decoded_signed_value, bytes_consumed)
    """
    unsigned, consumed = read_stop_bit(data, offset)

    # ZigZag decoding: map unsigned back to signed
    if unsigned & 1:
        # Odd = negative
        signed = ~(unsigned >> 1)
    else:
        # Even = positive
        signed = unsigned >> 1

    return signed, consumed


def read_stop_bit_from_stream(stream: BinaryIO) -> int:
    """Read a stop-bit encoded integer from a binary stream.

    Args:
        stream: Binary file-like object

    Returns:
        Decoded integer value

    Raises:
        ValueError: If stream ends unexpectedly
    """
    result = 0
    shift = 0

    while True:
        byte_data = stream.read(1)
        if not byte_data:
            raise ValueError("Unexpected end of stream in stop-bit encoding")

        byte = byte_data[0]
        result |= (byte & 0x7F) << shift
        shift += 7

        if (byte & 0x80) == 0:
            break

        if shift > 63:
            raise ValueError("Stop-bit encoding too long")

    return result
