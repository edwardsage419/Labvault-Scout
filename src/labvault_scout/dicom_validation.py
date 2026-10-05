from __future__ import annotations


def validate_dicom_file_meta(header: bytes, container_type: str) -> str:
    """Validate bounded DICOM Part 10 File Meta Information evidence."""
    if container_type != "DICOM Part 10 file":
        return container_type

    start = 132
    if len(header) < start + 12:
        return "Truncated DICOM File Meta Information"
    if header[start:start + 4] != b"\x02\x00\x00\x00":
        return "Invalid DICOM File Meta Information group length element"
    if header[start + 4:start + 6] != b"UL":
        return "Invalid DICOM File Meta Information group length VR"
    if int.from_bytes(header[start + 6:start + 8], "little") != 4:
        return "Invalid DICOM File Meta Information group length value length"
    if int.from_bytes(header[start + 8:start + 12], "little") == 0:
        return "Invalid DICOM File Meta Information group length value"
    return container_type
