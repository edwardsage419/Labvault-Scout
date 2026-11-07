"""Bound legacy numeric strings before integer conversion on all Python versions."""

import json
import sys
from pathlib import Path

import pytest

from labvault_scout.cli import main
from labvault_scout.compare import (
    compare_payloads,
    load_scan_report,
    report_integrity_status,
    scan_metrics,
    verify_report,
)
from labvault_scout.report import build_summary


def _row() -> dict:
    return {
        "path": "dataset/sample.csv",
        "size": "1",
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "priority_score": "0",
        "open_copy": "",
    }


@pytest.mark.parametrize("field", ["size", "priority_score"])
@pytest.mark.parametrize("digits", ["0" * 4301, "9" * 4301], ids=["zeros", "nines"])
def test_overlong_legacy_numeric_string_is_untrusted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    field: str,
    digits: str,
) -> None:
    original = _row()
    changed = {**original, field: digits}
    payload = {"files": [changed], "errors": []}
    path = tmp_path / "oversized-legacy-numeric-string.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_scan_report(path)
    assert loaded["files"][0][field] == digits
    assert report_integrity_status(loaded) == "MISMATCH"
    checked = verify_report(loaded)
    assert checked["status"] == "FAILED"
    assert checked["exit_code"] == 2
    if field == "size":
        assert scan_metrics(loaded)["total_bytes"] == 0

    before = {"files": [original], "errors": []}
    compared = compare_payloads(before, loaded)
    assert compared["comparison_status"] == "PARTIAL"
    assert compared["after"]["integrity_status"] == "MISMATCH"

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(path), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2


@pytest.mark.parametrize("field", ["size", "priority_score"])
def test_bounded_legacy_numeric_string_remains_verifiable(field: str) -> None:
    row = _row()
    row[field] = "0" * 4300
    payload = {"files": [row], "errors": []}
    payload["summary"] = build_summary([row], [], [])
    assert report_integrity_status(payload) == "VERIFIED"
    assert verify_report(payload)["status"] == "VERIFIED"
