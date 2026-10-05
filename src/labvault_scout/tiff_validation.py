from __future__ import annotations


def validate_tiff_first_ifd_offset(header: bytes, container_type: str) -> str:
    """Reject TIFF first-IFD offsets that contradict the bounded header structure."""
    if container_type.startswith("TIFF classic"):
        byteorder = "little" if header[:2] == b"II" else "big"
        first_ifd_offset = int.from_bytes(header[4:8], byteorder)
        if first_ifd_offset < 8 or first_ifd_offset % 2:
            return "Invalid TIFF first IFD offset"
    elif container_type.startswith("BigTIFF"):
        byteorder = "little" if header[:2] == b"II" else "big"
        first_ifd_offset = int.from_bytes(header[8:16], byteorder)
        if first_ifd_offset < 16 or first_ifd_offset % 8:
            return "Invalid BigTIFF first IFD offset"
    return container_type
