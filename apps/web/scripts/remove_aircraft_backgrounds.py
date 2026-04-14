from __future__ import annotations

import struct
import zlib
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def paeth_predictor(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def read_png(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError(f"{path} is not a PNG")

    offset = len(PNG_SIGNATURE)
    width = height = 0
    idat_parts: list[bytes] = []

    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        offset += 12 + length

        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, compression, flt, interlace = struct.unpack(">IIBBBBB", chunk_data)
            if bit_depth != 8 or color_type != 2 or compression != 0 or flt != 0 or interlace != 0:
                raise ValueError(f"{path} must be RGB, 8-bit, non-interlaced")
        elif chunk_type == b"IDAT":
            idat_parts.append(chunk_data)
        elif chunk_type == b"IEND":
            break

    raw = zlib.decompress(b"".join(idat_parts))
    bytes_per_pixel = 3
    stride = width * bytes_per_pixel
    rows: list[bytearray] = []
    cursor = 0

    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        scanline = bytearray(raw[cursor : cursor + stride])
        cursor += stride
        previous = rows[-1] if rows else bytearray(stride)

        if filter_type == 1:
            for i in range(stride):
                left = scanline[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                scanline[i] = (scanline[i] + left) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                scanline[i] = (scanline[i] + previous[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = scanline[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                up = previous[i]
                scanline[i] = (scanline[i] + ((left + up) // 2)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                left = scanline[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                up = previous[i]
                up_left = previous[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                scanline[i] = (scanline[i] + paeth_predictor(left, up, up_left)) & 0xFF
        elif filter_type != 0:
            raise ValueError(f"Unsupported PNG filter {filter_type} in {path}")

        rows.append(scanline)

    return width, height, b"".join(rows)


def write_png(path: Path, width: int, height: int, rgba: bytes) -> None:
    stride = width * 4
    filtered = bytearray()
    for row in range(height):
        filtered.append(0)
        start = row * stride
        filtered.extend(rgba[start : start + stride])

    compressed = zlib.compress(bytes(filtered), level=9)

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    output = bytearray(PNG_SIGNATURE)
    output.extend(chunk(b"IHDR", ihdr))
    output.extend(chunk(b"IDAT", compressed))
    output.extend(chunk(b"IEND", b""))
    path.write_bytes(bytes(output))


def remove_background(path: Path) -> None:
    width, height, rgb = read_png(path)
    rgba = bytearray(width * height * 4)

    for i in range(width * height):
        r = rgb[i * 3]
        g = rgb[i * 3 + 1]
        b = rgb[i * 3 + 2]
        luminance = int(0.2126 * r + 0.7152 * g + 0.0722 * b)
        alpha = max(0, min(255, 255 - luminance))
        if r > 245 and g > 245 and b > 245:
            alpha = 0

        rgba[i * 4] = 255
        rgba[i * 4 + 1] = 255
        rgba[i * 4 + 2] = 255
        rgba[i * 4 + 3] = alpha

    write_png(path, width, height, bytes(rgba))


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "assets" / "aircraft"
    for png in sorted(root.glob("*.png")):
        remove_background(png)


if __name__ == "__main__":
    main()
