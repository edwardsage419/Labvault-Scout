from __future__ import annotations

import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from . import __version__
from .report import inventory_sha256

COMPARISON_SCHEMA_VERSION = "1"
SUPPORTED_SCAN_SCHEMA_VERSIONS = {"1"}
ASSESSMENT_FIELDS = (
    "format",
    "signature",
    "signature_status",
    "container_type",
    "risk",
    "confidence",
    "priority_score",
    "priority",
    "priority_reason",
    "recommended_action",
    "open_copy",
    "relationship_strength",
    "relationship_evidence",
    "evidence",
    "reason",
)
CSV_FIELDS = (
    "change_type",
    "before_path",
    "after_path",
    "before_sha256",
    "after_sha256",
    "before_size",
    "after_size",
    "before_risk",
    "after_risk",
    "before_priority",
    "after_priority",
    "before_priority_score",
    "after_priority_score",
    "before_action",
    "after_action",
    "priority_direction",
    "priority_delta",
    "changed_fields",
)


def load_scan_report(path: Path) -> dict:
    """Load a LabVault Scout scan report without requiring a specific tool version."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read scan report: {path}") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("files"), list):
        raise ValueError(f"Invalid scan report: {path}")

    seen: set[str] = set()
    for row in payload["files"]:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not row["path"]:
            raise ValueError(f"Invalid file row in scan report: {path}")
        if row["path"] in seen:
            raise ValueError(f"Duplicate path in scan report: {row['path']}")
        seen.add(row["path"])
    return payload


def _file_index(payload: dict) -> tuple[dict[str, dict], bool]:
    """Index rows by path, normalizing pre-schema Windows separators conservatively."""
    legacy = "schema_version" not in payload
    indexed: dict[str, dict] = {}
    normalized = False
    for source_row in payload["files"]:
        path = source_row["path"]
        canonical = path.replace("\\", "/") if legacy else path
        if canonical in indexed:
            raise ValueError(f"Path collision after legacy normalization: {canonical}")
        row = dict(source_row)
        if canonical != path:
            row["path"] = canonical
            normalized = True
        indexed[canonical] = row
    return indexed, normalized


def scan_metrics(payload: dict) -> dict:
    """Derive comparable aggregate metrics, including for legacy reports."""
    risk_counts: dict[str, int] = {}
    priority_counts: dict[str, int] = {}
    total_bytes = 0
    for row in payload["files"]:
        try:
            total_bytes += int(row.get("size", 0))
        except (TypeError, ValueError):
            pass

        risk = str(row.get("risk", ""))
        if risk:
            risk_counts[risk] = risk_counts.get(risk, 0) + 1
        priority = str(row.get("priority", ""))
        if priority:
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

    return {
        "file_count": len(payload["files"]),
        "total_bytes": total_bytes,
        "risk_counts": dict(sorted(risk_counts.items())),
        "priority_counts": dict(sorted(priority_counts.items())),
    }


def _count_deltas(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    keys = sorted(set(before) | set(after))
    return {key: after.get(key, 0) - before.get(key, 0) for key in keys}


def metrics_delta(before: dict, after: dict) -> dict:
    """Return after-minus-before aggregate scan deltas."""
    return {
        "file_count": after["file_count"] - before["file_count"],
        "total_bytes": after["total_bytes"] - before["total_bytes"],
        "risk_counts": _count_deltas(before["risk_counts"], after["risk_counts"]),
        "priority_counts": _count_deltas(before["priority_counts"], after["priority_counts"]),
    }


def report_integrity_status(payload: dict) -> str:
    """Validate the embedded inventory fingerprint when the report provides one."""
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return "UNKNOWN"
    expected = summary.get("inventory_sha256")
    if not isinstance(expected, str) or not expected:
        return "UNKNOWN"
    try:
        actual = inventory_sha256(payload["files"])
    except (KeyError, TypeError, ValueError):
        return "MISMATCH"
    return "VERIFIED" if actual == expected else "MISMATCH"


def report_identity(payload: dict) -> dict:
    """Return non-sensitive compatibility metadata for a source report."""
    tool = payload.get("tool")
    if not isinstance(tool, dict):
        tool = {}
    errors = payload.get("errors")
    error_count = len(errors) if isinstance(errors, list) else 0
    summary = payload.get("summary")
    inventory = summary.get("inventory_sha256", "") if isinstance(summary, dict) else ""
    _, legacy_paths_normalized = _file_index(payload)
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        provenance = {}
    schema_version = str(payload.get("schema_version", "legacy"))
    schema_supported = schema_version == "legacy" or schema_version in SUPPORTED_SCAN_SCHEMA_VERSIONS
    return {
        "schema_version": schema_version,
        "schema_supported": schema_supported,
        "tool": {
            "name": str(tool.get("name", "LabVault Scout")),
            "version": str(tool.get("version", "unknown")),
        },
        "error_count": error_count,
        "inventory_sha256": str(inventory),
        "integrity_status": report_integrity_status(payload),
        "rules_sha256": str(provenance.get("rules_sha256", "")),
        "hash_algorithm": str(provenance.get("hash_algorithm", "")),
        "path_style": str(provenance.get("path_style", "")),
        "legacy_paths_normalized": legacy_paths_normalized,
        "metrics": scan_metrics(payload),
    }


def _changed_fields(before: dict, after: dict) -> list[str]:
    return [field for field in ASSESSMENT_FIELDS if before.get(field) != after.get(field)]


def _priority_change(before: dict | None, after: dict | None) -> tuple[str, int | None]:
    if not before or not after:
        return "", None

    before_score = before.get("priority_score")
    after_score = after.get("priority_score")
    try:
        delta = int(after_score) - int(before_score)
    except (TypeError, ValueError):
        delta = None

    if delta is not None:
        if delta > 0:
            return "ESCALATED", delta
        if delta < 0:
            return "DEESCALATED", delta
        return "UNCHANGED", 0

    rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    before_rank = rank.get(str(before.get("priority", "")))
    after_rank = rank.get(str(after.get("priority", "")))
    if before_rank is None or after_rank is None:
        return "", None
    if after_rank > before_rank:
        return "ESCALATED", None
    if after_rank < before_rank:
        return "DEESCALATED", None
    return "UNCHANGED", None


def _change(change_type: str, before: dict | None, after: dict | None) -> dict:
    changed_fields = _changed_fields(before or {}, after or {}) if before and after else []
    priority_direction, priority_delta = _priority_change(before, after)
    return {
        "change_type": change_type,
        "before_path": before.get("path", "") if before else "",
        "after_path": after.get("path", "") if after else "",
        "priority_direction": priority_direction,
        "priority_delta": priority_delta,
        "changed_fields": changed_fields,
        "before": before,
        "after": after,
    }


def compare_payloads(before: dict, after: dict) -> dict:
    """Compare two scan payloads using relative paths and SHA-256 content identity."""
    before_rows, before_paths_normalized = _file_index(before)
    after_rows, after_paths_normalized = _file_index(after)

    before_paths = set(before_rows)
    after_paths = set(after_rows)
    removed_paths = before_paths - after_paths
    added_paths = after_paths - before_paths

    before_hash_counts: dict[str, int] = defaultdict(int)
    after_hash_counts: dict[str, int] = defaultdict(int)
    for row in before_rows.values():
        digest = str(row.get("sha256", ""))
        if digest:
            before_hash_counts[digest] += 1
    for row in after_rows.values():
        digest = str(row.get("sha256", ""))
        if digest:
            after_hash_counts[digest] += 1

    removed_by_hash: dict[str, list[str]] = defaultdict(list)
    added_by_hash: dict[str, list[str]] = defaultdict(list)
    for path in removed_paths:
        digest = str(before_rows[path].get("sha256", ""))
        if digest:
            removed_by_hash[digest].append(path)
    for path in added_paths:
        digest = str(after_rows[path].get("sha256", ""))
        if digest:
            added_by_hash[digest].append(path)

    changes: list[dict] = []
    moved_before: set[str] = set()
    moved_after: set[str] = set()
    for digest in sorted(set(removed_by_hash) & set(added_by_hash)):
        old_paths = sorted(removed_by_hash[digest])
        new_paths = sorted(added_by_hash[digest])
        if (
            len(old_paths) == 1
            and len(new_paths) == 1
            and before_hash_counts[digest] == 1
            and after_hash_counts[digest] == 1
        ):
            old_path, new_path = old_paths[0], new_paths[0]
            changes.append(_change("MOVED", before_rows[old_path], after_rows[new_path]))
            moved_before.add(old_path)
            moved_after.add(new_path)

    for path in sorted(removed_paths - moved_before):
        changes.append(_change("REMOVED", before_rows[path], None))
    for path in sorted(added_paths - moved_after):
        changes.append(_change("ADDED", None, after_rows[path]))

    unchanged_count = 0
    for path in sorted(before_paths & after_paths):
        old = before_rows[path]
        new = after_rows[path]
        if old.get("sha256") != new.get("sha256"):
            changes.append(_change("CONTENT_CHANGED", old, new))
        else:
            fields = _changed_fields(old, new)
            if fields:
                changes.append(_change("ASSESSMENT_CHANGED", old, new))
            else:
                unchanged_count += 1

    order = {"MOVED": 0, "CONTENT_CHANGED": 1, "ASSESSMENT_CHANGED": 2, "ADDED": 3, "REMOVED": 4}
    changes.sort(key=lambda item: (
        order[item["change_type"]],
        item["after_path"] or item["before_path"],
        item["before_path"],
    ))

    counts = {name: 0 for name in ("ADDED", "REMOVED", "MOVED", "CONTENT_CHANGED", "ASSESSMENT_CHANGED")}
    priority_escalated_count = 0
    priority_deescalated_count = 0
    for item in changes:
        counts[item["change_type"]] += 1
        if item["priority_direction"] == "ESCALATED":
            priority_escalated_count += 1
        elif item["priority_direction"] == "DEESCALATED":
            priority_deescalated_count += 1

    before_identity = report_identity(before)
    after_identity = report_identity(after)
    has_scan_errors = bool(before_identity["error_count"] or after_identity["error_count"])
    unsupported_schema = not before_identity["schema_supported"] or not after_identity["schema_supported"]
    integrity_mismatch = (
        before_identity["integrity_status"] == "MISMATCH"
        or after_identity["integrity_status"] == "MISMATCH"
    )
    before_rules = before_identity["rules_sha256"]
    after_rules = after_identity["rules_sha256"]
    if before_rules and after_rules:
        rules_status = "SAME" if before_rules == after_rules else "CHANGED"
    else:
        rules_status = "UNKNOWN"

    partial = has_scan_errors or unsupported_schema or integrity_mismatch
    warnings = []
    if has_scan_errors:
        warnings.append(
            "One or both source scans contain errors; path additions/removals may be incomplete."
        )
    if unsupported_schema:
        warnings.append(
            "One or both source reports use an unsupported scan schema; comparison semantics may be incomplete."
        )
    if integrity_mismatch:
        warnings.append(
            "One or both source reports fail inventory fingerprint validation; report contents may have been modified or truncated."
        )
    if before_paths_normalized or after_paths_normalized:
        warnings.append(
            "Legacy pre-schema backslash paths were normalized to POSIX separators for comparison."
        )
    if rules_status == "CHANGED":
        warnings.append(
            "Rule-set fingerprint changed; assessment differences may reflect rule changes rather than file content."
        )

    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "tool": {"name": "LabVault Scout", "version": __version__},
        "comparison_status": "PARTIAL" if partial else "COMPLETE",
        "rules_status": rules_status,
        "warnings": warnings,
        "before": before_identity,
        "after": after_identity,
        "metrics_delta": metrics_delta(before_identity["metrics"], after_identity["metrics"]),
        "summary": {
            "added_count": counts["ADDED"],
            "removed_count": counts["REMOVED"],
            "moved_count": counts["MOVED"],
            "content_changed_count": counts["CONTENT_CHANGED"],
            "assessment_changed_count": counts["ASSESSMENT_CHANGED"],
            "priority_escalated_count": priority_escalated_count,
            "priority_deescalated_count": priority_deescalated_count,
            "unchanged_count": unchanged_count,
            "change_count": len(changes),
        },
        "changes": changes,
    }


def compare_reports(before_path: Path, after_path: Path) -> dict:
    return compare_payloads(load_scan_report(before_path), load_scan_report(after_path))


def comparison_exit_code(result: dict) -> int:
    """Return an opt-in automation exit code for a comparison result."""
    if result.get("comparison_status") == "PARTIAL":
        return 2
    if result.get("summary", {}).get("change_count", 0):
        return 1
    return 0


def _csv_row(item: dict) -> dict:
    before = item.get("before") or {}
    after = item.get("after") or {}
    return {
        "change_type": item["change_type"],
        "before_path": item["before_path"],
        "after_path": item["after_path"],
        "before_sha256": before.get("sha256", ""),
        "after_sha256": after.get("sha256", ""),
        "before_size": before.get("size", ""),
        "after_size": after.get("size", ""),
        "before_risk": before.get("risk", ""),
        "after_risk": after.get("risk", ""),
        "before_priority": before.get("priority", ""),
        "after_priority": after.get("priority", ""),
        "before_priority_score": before.get("priority_score", ""),
        "after_priority_score": after.get("priority_score", ""),
        "before_action": before.get("recommended_action", ""),
        "after_action": after.get("recommended_action", ""),
        "priority_direction": item.get("priority_direction", ""),
        "priority_delta": "" if item.get("priority_delta") is None else item["priority_delta"],
        "changed_fields": ";".join(item.get("changed_fields", [])),
    }


def write_comparison(result: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "comparison.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (output_dir / "changes.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(_csv_row(item) for item in result["changes"])

    rows = "".join(
        "<tr>"
        f"<td>{html.escape(item['change_type'])}</td>"
        f"<td>{html.escape(item['before_path'])}</td>"
        f"<td>{html.escape(item['after_path'])}</td>"
        f"<td>{html.escape(item.get('priority_direction', ''))}</td>"
        f"<td>{html.escape(str(item.get('priority_delta', '') if item.get('priority_delta') is not None else ''))}</td>"
        f"<td>{html.escape(';'.join(item.get('changed_fields', [])))}</td>"
        "</tr>"
        for item in result["changes"]
    )
    summary = result["summary"]
    delta = result["metrics_delta"]
    risk_delta = " | ".join(f"{html.escape(key)}: {value:+d}" for key, value in delta["risk_counts"].items()) or "none"
    priority_delta = " | ".join(f"{html.escape(key)}: {value:+d}" for key, value in delta["priority_counts"].items()) or "none"
    warning_html = "".join(
        f"<p><strong>Warning:</strong> {html.escape(message)}</p>"
        for message in result.get("warnings", [])
    )
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<title>LabVault Scout Comparison</title>
<style>body{{font-family:system-ui;max-width:1100px;margin:40px auto;padding:0 20px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:7px;text-align:left}}th{{background:#f5f5f5}}</style>
<h1>LabVault Scout Comparison</h1>
<p>Tool version: {html.escape(__version__)} | Comparison schema: {COMPARISON_SCHEMA_VERSION} | Status: {html.escape(result.get("comparison_status", "COMPLETE"))} | Rules: {html.escape(result.get("rules_status", "UNKNOWN"))}</p>
{warning_html}
<p>Changes: {summary['change_count']} | Added: {summary['added_count']} | Removed: {summary['removed_count']} | Moved: {summary['moved_count']} | Content changed: {summary['content_changed_count']} | Assessment changed: {summary['assessment_changed_count']} | Priority escalated: {summary['priority_escalated_count']} | Priority deescalated: {summary['priority_deescalated_count']} | Unchanged: {summary['unchanged_count']}</p>
<p>File count delta: {delta['file_count']:+d} | Total bytes delta: {delta['total_bytes']:+d}</p>
<p>Risk deltas: {risk_delta}</p>
<p>Priority deltas: {priority_delta}</p>
<table><thead><tr><th>change_type</th><th>before_path</th><th>after_path</th><th>priority_direction</th><th>priority_delta</th><th>changed_fields</th></tr></thead><tbody>{rows}</tbody></table></html>"""
    (output_dir / "comparison.html").write_text(page, encoding="utf-8")
