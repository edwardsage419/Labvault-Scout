from __future__ import annotations

import csv
import hashlib
import html
import json
from collections import defaultdict
from pathlib import Path

from . import __version__

REPORT_SCHEMA_VERSION = "1"

FIELDS = ["path", "size", "sha256", "format", "signature", "signature_status", "container_type", "risk", "confidence", "priority_score", "priority", "priority_reason", "recommended_action", "open_copy", "relationship_strength", "relationship_evidence", "evidence", "reason"]


def duplicate_groups(rows: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["sha256"]].append(row)
    output = []
    group_id = 0
    for digest, members in groups.items():
        if len(members) < 2:
            continue
        group_id += 1
        for member in members:
            output.append({"group": group_id, "sha256": digest, "path": member["path"], "size": member["size"]})
    return output


def report_payload_sha256(payload: dict) -> str:
    """Return a deterministic checksum of a report payload excluding its checksum field."""
    clean = dict(payload)
    clean.pop("report_sha256", None)
    encoded = json.dumps(
        clean,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def inventory_sha256(rows: list[dict]) -> str:
    """Return a deterministic fingerprint of relative paths, sizes, and content hashes."""
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda item: item["path"]):
        record = f"{row['path']}\0{row['size']}\0{row['sha256']}\n".encode("utf-8")
        digest.update(record)
    return digest.hexdigest()


def build_summary(rows: list[dict], errors: list[dict], duplicates: list[dict]) -> dict:
    """Build deterministic project-level scan summary counts."""
    risk_counts: dict[str, int] = {}
    priority_counts: dict[str, int] = {}
    for row in rows:
        risk = row["risk"]
        priority = row["priority"]
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
        priority_counts[priority] = priority_counts.get(priority, 0) + 1

    return {
        "file_count": len(rows),
        "total_bytes": sum(int(row["size"]) for row in rows),
        "inventory_sha256": inventory_sha256(rows),
        "error_count": len(errors),
        "risk_counts": dict(sorted(risk_counts.items())),
        "priority_counts": dict(sorted(priority_counts.items())),
        "open_copy_count": sum(bool(row["open_copy"]) for row in rows),
        "duplicate_group_count": len({item["group"] for item in duplicates}),
    }


def write_reports(
    rows: list[dict],
    output_dir: Path,
    errors: list[dict] | None = None,
    provenance: dict | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    errors = errors or []
    duplicates = duplicate_groups(rows)
    summary_data = build_summary(rows, errors, duplicates)
    with (output_dir / "files.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "tool": {"name": "LabVault Scout", "version": __version__},
        "provenance": provenance or {},
        "summary": summary_data,
        "files": rows,
        "errors": errors,
    }
    payload["report_sha256"] = report_payload_sha256(payload)
    (output_dir / "scan.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    migration_rows = sorted(
        (row for row in rows if row["priority"] in {"HIGH", "MEDIUM"}),
        key=lambda row: (-int(row["priority_score"]), row["path"].lower()),
    )
    migration_fields = ["priority_score", "priority", "path", "format", "risk", "confidence", "priority_reason", "recommended_action", "open_copy", "relationship_strength", "relationship_evidence", "evidence", "reason"]
    with (output_dir / "migration_plan.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=migration_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(migration_rows)

    with (output_dir / "duplicates.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["group", "sha256", "path", "size"])
        writer.writeheader()
        writer.writerows(duplicates)

    counts = summary_data["risk_counts"]
    open_copy_count = summary_data["open_copy_count"]
    high_priority_count = summary_data["priority_counts"].get("HIGH", 0)
    table_rows = "".join("<tr>" + "".join(f"<td>{html.escape(str(row[k]))}</td>" for k in FIELDS) + "</tr>" for row in rows)
    summary = " | ".join(f"{html.escape(k)}: {v}" for k, v in sorted(counts.items()))
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>LabVault Scout Report</title>
<style>body{{font-family:system-ui;max-width:1200px;margin:40px auto;padding:0 20px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:7px;text-align:left}}th{{background:#f5f5f5}}</style>
<h1>LabVault Scout Report</h1><p>Tool version: {html.escape(__version__)} | Report schema: {REPORT_SCHEMA_VERSION}</p><p>Rules fingerprint: {html.escape(str((provenance or {}).get("rules_sha256", "unknown")))}</p><p>Files: {len(rows)} | High priority: {high_priority_count} | Open copies detected: {open_copy_count} | Duplicate entries: {len(duplicates)} | Scan errors: {summary_data["error_count"]}</p><p>{summary}</p>
<table><thead><tr>{''.join(f"<th>{k}</th>" for k in FIELDS)}</tr></thead><tbody>{table_rows}</tbody></table></html>"""
    (output_dir / "report.html").write_text(page, encoding="utf-8")
