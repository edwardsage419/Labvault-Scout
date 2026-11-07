"""Ensure malformed legacy priority score strings cannot produce numeric deltas."""

import csv
import json
from pathlib import Path

import pytest

from labvault_scout.compare import (
    compare_payloads,
    compare_reports,
    report_integrity_status,
    write_comparison,
)
from labvault_scout.report import build_summary


def _legacy_report(score: object, priority: str) -> dict:
    row = {
        "path": "data.csv",
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": priority,
        "priority_score": score,
        "open_copy": "",
    }
    return {
        "files": [row],
        "errors": [],
        "summary": build_summary([row], [], []),
    }


@pytest.mark.parametrize(
    "invalid_score",
    ["1_0", "+10", " 10 ", "\u0661\u0660"],
    ids=["underscore", "leading-plus", "whitespace", "unicode-digits"],
)
def test_invalid_legacy_score_uses_category_fallback_in_comparison(
    tmp_path: Path, invalid_score: str,
) -> None:
    before = _legacy_report(invalid_score, "LOW")
    after = _legacy_report("12", "HIGH")
    assert report_integrity_status(before) == "MISMATCH"
    assert report_integrity_status(after) == "VERIFIED"

    before_path = tmp_path / "before.json"
    after_path = tmp_path / "after.json"
    before_path.write_text(json.dumps(before), encoding="utf-8")
    after_path.write_text(json.dumps(after), encoding="utf-8")
    result = compare_reports(before_path, after_path)

    assert result["comparison_status"] == "PARTIAL"
    assert result["before"]["integrity_status"] == "MISMATCH"
    assert result["after"]["integrity_status"] == "VERIFIED"
    assert result["summary"]["assessment_changed_count"] == 1
    change = result["changes"][0]
    assert change["change_type"] == "ASSESSMENT_CHANGED"
    assert change["priority_direction"] == "ESCALATED"
    assert change["priority_delta"] is None

    output_dir = tmp_path / "comparison"
    write_comparison(result, output_dir)
    exported = json.loads((output_dir / "comparison.json").read_text(encoding="utf-8"))
    assert exported["changes"][0]["priority_delta"] is None
    with (output_dir / "changes.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["priority_delta"] == ""


@pytest.mark.parametrize("valid_score", ["10", "010", 10, 10.0])
def test_valid_legacy_score_still_produces_numeric_delta(valid_score: object) -> None:
    before = _legacy_report(valid_score, "LOW")
    after = _legacy_report("12", "HIGH")
    assert report_integrity_status(before) == "VERIFIED"
    result = compare_payloads(before, after)
    assert result["comparison_status"] == "COMPLETE"
    assert result["changes"][0]["priority_direction"] == "ESCALATED"
    assert result["changes"][0]["priority_delta"] == 2
