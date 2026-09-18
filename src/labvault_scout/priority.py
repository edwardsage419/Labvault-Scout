from __future__ import annotations

RISK_SCORE = {"SAFE": 0, "WATCH": 40, "RESCUE": 80, "UNKNOWN": 50}
OPEN_COPY_CREDIT = {"EXACT": 25, "DERIVATIVE": 15}
PRESERVATION_PACKAGE_CREDIT = {
    "RO-Crate Research Object": 10,
    "BagIt Research Package": 10,
}


def priority_reason(row: dict) -> str:
    """Explain the score inputs in a stable machine-readable string."""
    reasons = [f"base={RISK_SCORE.get(row.get('risk', 'UNKNOWN'), 50)}"]
    if row.get("open_copy"):
        strength = row.get("relationship_strength", "")
        reasons.append(f"open_copy=-{OPEN_COPY_CREDIT.get(strength, 10)}:{strength or 'UNCLASSIFIED'}")
    package_credit = PRESERVATION_PACKAGE_CREDIT.get(row.get("container_type", ""), 0)
    if package_credit:
        reasons.append(f"preservation_package=-{package_credit}")
    status = row.get("signature_status", "")
    if status.startswith("mismatch") or status.startswith("unverified"):
        reasons.append("signature=+10")
    if row.get("confidence") == "LOW" and row.get("risk") in {"RESCUE", "UNKNOWN"}:
        reasons.append("low_confidence=+5")
    return ";".join(reasons)


def assign_priority(row: dict) -> tuple[int, str]:
    """Return a transparent preservation priority score and label."""
    score = RISK_SCORE.get(row.get("risk", "UNKNOWN"), 50)

    if row.get("open_copy"):
        strength = row.get("relationship_strength", "")
        score -= OPEN_COPY_CREDIT.get(strength, 10)

    package_credit = PRESERVATION_PACKAGE_CREDIT.get(row.get("container_type", ""), 0)
    score -= package_credit

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
