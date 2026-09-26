from __future__ import annotations

from .priority import has_structural_warning


def recommended_action(row: dict) -> str:
    """Return a conservative, actionable preservation recommendation."""
    risk = row.get("risk", "UNKNOWN")
    open_copy = bool(row.get("open_copy"))
    strength = row.get("relationship_strength", "")
    priority = row.get("priority", "")

    if has_structural_warning(row):
        return "REVIEW_CONTAINER"

    if row.get("format") in {"TIFF", "FITS"} and row.get("signature_status", "").startswith("mismatch"):
        return "REVIEW_FORMAT"

    if risk == "SAFE" and priority == "LOW":
        return "KEEP"

    if open_copy and strength == "EXACT":
        return "VERIFY_OPEN_COPY"

    if open_copy and strength == "DERIVATIVE":
        return "VERIFY_DERIVATIVE_EXPORT"

    if risk == "RESCUE" and priority == "HIGH":
        return "EXPORT_OPEN_FORMAT"

    if risk in {"WATCH", "UNKNOWN"}:
        return "REVIEW_FORMAT"

    return "REVIEW"
