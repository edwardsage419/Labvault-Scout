"""Ensure CSV exports neutralize spreadsheet formulas while JSON retains exact paths."""

import csv
import json
from pathlib import Path

import pytest

from labvault_scout.compare import compare_payloads, write_comparison
from labvault_scout.report import FIELDS, build_summary, write_reports


def _row(path: str, digest: str = "a" * 64) -> dict:
    row = {field: "" for field in FIELDS}
    row.update(
        path=path,
        size=1,
        sha256=digest,
        risk="SAFE",
        confidence="HIGH",
        priority_score=10,
        priority="HIGH",
        open_copy="",
    )
    return row


def _csv_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.mark.parametrize(
    "name,escaped",
    [
        ("=1+1", True),
        ("+1+1", True),
        ("-1+1", True),
        ("@SUM(1,2)", True),
        (" \t=1+1", True),
        ("\v=1+1", True),
        ("\f=1+1", True),
        ("\u00a0=1+1", True),
        ("\u2003=1+1", True),
        ("\u2003ordinary.csv", False),
        ("ordinary.csv", False),
    ],
)
def test_scan_csv_exports_escape_formula_paths_only(
    tmp_path: Path, name: str, escaped: bool,
) -> None:
    rows = [_row(name), _row("ordinary-second.csv")]
    output = tmp_path / "scan"
    write_reports(rows, output)

    expected = "'" + name if escaped else name
    for filename in ("files.csv", "migration_plan.csv", "duplicates.csv"):
        assert expected in [row["path"] for row in _csv_rows(output / filename)]
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert payload["files"][0]["path"] == name
    assert rows[0]["path"] == name


@pytest.mark.parametrize(
    "name,escaped",
    [
        ("=1+1", True),
        ("+1+1", True),
        ("-1+1", True),
        ("@SUM(1,2)", True),
        (" \t=1+1", True),
        ("\v=1+1", True),
        ("\f=1+1", True),
        ("\u00a0=1+1", True),
        ("\u2003=1+1", True),
        ("\u2003ordinary.csv", False),
        ("ordinary.csv", False),
    ],
)
def test_comparison_csv_escapes_formula_paths_without_changing_json(
    tmp_path: Path, name: str, escaped: bool,
) -> None:
    before_rows = [_row(name)]
    after_rows = [_row(name, "b" * 64)]
    before = {
        "files": before_rows,
        "errors": [],
        "summary": build_summary(before_rows, [], []),
    }
    after = {
        "files": after_rows,
        "errors": [],
        "summary": build_summary(after_rows, [], []),
    }
    comparison = compare_payloads(before, after)
    assert comparison["comparison_status"] == "COMPLETE"
    output = tmp_path / "comparison"
    write_comparison(comparison, output)

    expected = "'" + name if escaped else name
    rows = _csv_rows(output / "changes.csv")
    assert len(rows) == 1
    assert rows[0]["before_path"] == expected
    assert rows[0]["after_path"] == expected
    payload = json.loads((output / "comparison.json").read_text(encoding="utf-8"))
    assert payload["changes"][0]["before_path"] == name
    assert payload["changes"][0]["after_path"] == name
