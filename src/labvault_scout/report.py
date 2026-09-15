from __future__ import annotations

import csv
import html
import json
from collections import defaultdict
from pathlib import Path


FIELDS = ["path", "size", "sha256", "format", "risk", "reason"]


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
            output.append({
                "group": group_id,
                "sha256": digest,
                "path": member["path"],
                "size": member["size"],
            })
    return output


def write_reports(rows: list[dict], output_dir: Path, errors: list[dict] | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    with (output_dir / "files.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    payload = {"files": rows, "errors": errors or []}
    (output_dir / "scan.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    duplicates = duplicate_groups(rows)
    with (output_dir / "duplicates.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["group", "sha256", "path", "size"])
        writer.writeheader()
        writer.writerows(duplicates)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["risk"]] = counts.get(row["risk"], 0) + 1

    table_rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row[k]))}</td>" for k in FIELDS) + "</tr>"
        for row in rows
    )
    summary = " | ".join(f"{html.escape(k)}: {v}" for k, v in sorted(counts.items()))
    page = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><title>LabVault Scout Report</title>
<style>body{{font-family:system-ui;max-width:1200px;margin:40px auto;padding:0 20px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:7px;text-align:left}}th{{background:#f5f5f5}}</style>
<h1>LabVault Scout Report</h1>
<p>Files: {len(rows)} | Duplicate entries: {len(duplicates)} | Scan errors: {len(errors or [])}</p>
<p>{summary}</p>
<table><thead><tr>{''.join(f"<th>{k}</th>" for k in FIELDS)}</tr></thead><tbody>{table_rows}</tbody></table></html>"""
    (output_dir / "report.html").write_text(page, encoding="utf-8")
