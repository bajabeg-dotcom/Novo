from .errors import SmfStructureError


def decode_vlq(data: bytes, offset: int = 0) -> tuple[int, int]:
    value = 0
    for index in range(4):
        position = offset + index
        if position >= len(data):
            raise SmfStructureError("truncated variable-length quantity")
        byte = data[position]
        value = (value << 7) | (byte & 0x7F)
        if byte < 0x80:
            return value, position + 1
    raise SmfStructureError("variable-length quantity exceeds four bytes")


def encode_vlq(value: int) -> bytes:
    if not 0 <= value <= 0x0FFFFFFF:
        raise ValueError("VLQ value outside SMF range")
    buffer = [value & 0x7F]
    value >>= 7
    while value:
        buffer.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(buffer))