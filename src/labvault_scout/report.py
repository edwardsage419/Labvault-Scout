from __future__ import annotations

import csv
import html
import json
from pathlib import Path


def write_reports(rows: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = ["path", "size", "sha256", "format", "risk", "reason"]

    with (output_dir / "files.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    (output_dir / "scan.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["risk"]] = counts.get(row["risk"], 0) + 1

    table_rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row[k]))}</td>" for k in fields) + "</tr>"
        for row in rows
    )
    summary = " ".join(f"{html.escape(k)}: {v}" for k, v in sorted(counts.items()))
    page = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><title>LabVault Scout Report</title>
<style>body{{font-family:system-ui;max-width:1200px;margin:40px auto;padding:0 20px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:7px;text-align:left}}th{{background:#f5f5f5}}</style>
<h1>LabVault Scout Report</h1><p>Files: {len(rows)} | {summary}</p>
<table><thead><tr>{''.join(f"<th>{k}</th>" for k in fields)}</tr></thead><tbody>{table_rows}</tbody></table></html>"""
    (output_dir / "report.html").write_text(page, encoding="utf-8")
