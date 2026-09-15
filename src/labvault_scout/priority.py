from __future__ import annotations

RISK_SCORE = {"SAFE": 0, "WATCH": 40, "RESCUE": 80, "UNKNOWN": 50}


def assign_priority(row: dict) -> tuple[int, str]:
    """Return a transparent preservation priority score and label."""
    score = RISK_SCORE.get(row.get("risk", "UNKNOWN"), 50)

    if row.get("open_copy"):
        score -= 25

    status = row.get("signature_status", "")
    if status.startswith("mismatch") or status.startswith("unverified"):
        score += 10

    if row.get("confidence") == "LOW" and row.get("risk") in {"RESCUE", "UNKNOWN"}:
        score += 5

    score = max(0, min(100, score))
    if score >= 75:
        label = "HIGH"
    elif score >= 40:
        label = "MEDIUM"
    else:
        label = "LOW"
    return score, label
