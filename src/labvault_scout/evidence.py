from __future__ import annotations


def build_evidence(row: dict) -> tuple[str, str]:
    """Return a compact evidence summary and confidence label."""
    items = []
    confidence = "LOW"

    fmt = row.get("format", "Unknown")
    if fmt != "Unknown":
        items.append(f"extension rule: {fmt}")
        confidence = "MEDIUM"

    signature = row.get("signature", "")
    status = row.get("signature_status", "")
    if signature:
        items.append(f"signature: {signature}")
    if status:
        items.append(f"signature status: {status}")

    container = row.get("container_type", "")
    if container:
        items.append(f"container: {container}")

    if status == "verified" and container:
        confidence = "HIGH"
    elif status == "verified":
        confidence = "HIGH"
    elif status.startswith("mismatch") or status.startswith("unverified"):
        confidence = "LOW"

    relationship = row.get("relationship_evidence", "")
    if relationship:
        items.append(f"relationship: {relationship}")

    open_copy = row.get("open_copy", "")
    if open_copy:
        items.append(f"possible open copy: {open_copy}")

    return " | ".join(items), confidence
