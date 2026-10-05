from __future__ import annotations


def validate_stata_k_header(header: bytes, container_type: str) -> str:
    """Require the mandatory K marker pair after a valid modern Stata byteorder header."""
    if not container_type.startswith("Stata DTA release "):
        return container_type

    byteorder_end_tag = b"</byteorder>"
    byteorder_end = header.find(byteorder_end_tag, 0, 128)
    if byteorder_end < 0:
        return container_type

    k_start = byteorder_end + len(byteorder_end_tag)
    if not header.startswith(b"<K>", k_start):
        return "Invalid Stata DTA K header"

    value_start = k_start + len(b"<K>")
    value_end = header.find(b"</K>", value_start, value_start + 16)
    if value_end < 0:
        return "Truncated Stata DTA K header"
    if value_end == value_start:
        return "Invalid Stata DTA K header"

    return container_type
