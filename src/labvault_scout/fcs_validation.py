from __future__ import annotations


def validate_fcs_offset_pairs(header: bytes, container_type: str) -> str:
    """Reject FCS HEADER begin/end offset pairs that contradict fixed-header rules."""
    if not container_type.startswith("FCS ") or len(header) < 58:
        return container_type

    def offset(start: int) -> int:
        field = header[start:start + 8].strip()
        return int(field) if field else 0

    data_begin = offset(26)
    data_end = offset(34)
    analysis_begin = offset(42)
    analysis_end = offset(50)

    if bool(data_begin) != bool(data_end):
        return "Invalid FCS DATA offsets"
    if bool(analysis_begin) != bool(analysis_end):
        return "Invalid FCS ANALYSIS offsets"
    if header.startswith(b"FCS2.0") and data_begin == 0:
        return "Invalid FCS DATA offsets"

    return container_type
