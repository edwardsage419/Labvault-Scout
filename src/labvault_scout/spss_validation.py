from __future__ import annotations


SPSS_PRODUCT_PREFIX = b"@(#) SPSS DATA FILE"


def validate_spss_product_identifier(header: bytes, container_type: str) -> str:
    """Reject otherwise valid SPSS fixed headers without the required product identifier."""
    if not container_type.startswith("SPSS ") or len(header) < 64:
        return container_type
    if not header[4:64].startswith(SPSS_PRODUCT_PREFIX):
        return "Invalid SPSS product identifier"
    return container_type
