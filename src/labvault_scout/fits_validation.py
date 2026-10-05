from __future__ import annotations


def validate_fits_mandatory_value_indicators(header: bytes, container_type: str) -> str:
    """Reject verified FITS primary headers whose mandatory value cards lack '= '."""
    if container_type != "FITS primary HDU (SIMPLE=T)":
        return container_type
    if header[88:90] != b"= ":
        return "Invalid FITS BITPIX value indicator"
    if header[168:170] != b"= ":
        return "Invalid FITS NAXIS value indicator"
    return container_type
