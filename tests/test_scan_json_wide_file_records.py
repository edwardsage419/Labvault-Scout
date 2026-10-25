"""Check that wide file inventories preserve late records and reject duplicates."""

import json
import sys
from pathlib import Path

import pytest

from labvault_scout.cli import main
from labvault_scout.compare import (
    compare_payloads,
    load_scan_report,
    report_integrity_status,
    verify_report,
)
from labvault_scout.report import build_summary, duplicate_groups


def _rows(width: int) -> list[dict]:
    return [
        {
            "path": f"dataset/file_{index:04d}.csv",
            "size": index + 1,
            "sha256": f"{index + 1:064x}",
            "risk": "SAFE",
            "priority": "LOW",
            "open_copy": "",
        }
        for index in range(width)
    ]


def _payload(rows: list[dict]) -> dict:
    errors: list[dict] = []
    return {
        "files": rows,
        "errors": errors,
        "summary": build_summary(rows, errors, duplicate_groups(rows)),
    }


def test_wide_legacy_file_inventory_remains_verifiable(tmp_path: Path) -> None:
    payload = _payload(_rows(1024))
    report = tmp_path / "wide-files.json"
    report.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_scan_report(report)
    assert len(loaded["files"]) == 1024
    assert loaded["files"][-1]["path"] == "dataset/file_1023.csv"
    assert report_integrity_status(loaded) == "VERIFIED"
    assert verify_report(loaded)["status"] == "VERIFIED"

    comparison = compare_payloads(loaded, loaded)
    assert comparison["comparison_status"] == "COMPLETE"
    assert comparison["summary"]["unchanged_count"] == 1024
    assert comparison["summary"]["change_count"] == 0


def test_wide_legacy_inventory_detects_last_record_change(tmp_path: Path) -> None:
    before = _payload(_rows(1024))
    after_rows = _rows(1024)
    after_rows[-1]["sha256"] = "f" * 64
    after = _payload(after_rows)
    before_path = tmp_path / "before.json"
    after_path = tmp_path / "after.json"
    before_path.write_text(json.dumps(before), encoding="utf-8")
    after_path.write_text(json.dumps(after), encoding="utf-8")

    loaded_before = load_scan_report(before_path)
    loaded_after = load_scan_report(after_path)
    assert report_integrity_status(loaded_before) == "VERIFIED"
    assert report_integrity_status(loaded_after) == "VERIFIED"
    comparison = compare_payloads(loaded_before, loaded_after)
    assert comparison["comparison_status"] == "COMPLETE"
    assert comparison["summary"]["content_changed_count"] == 1
    assert comparison["summary"]["unchanged_count"] == 1023
    assert comparison["changes"][0]["after_path"] == "dataset/file_1023.csv"


def test_wide_legacy_inventory_rejects_last_duplicate_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rows = _rows(1024)
    rows.append(dict(rows[-1]))
    report = tmp_path / "wide-duplicate-file-path.json"
    report.write_text(json.dumps({"files": rows, "errors": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate path in scan report"):
        load_scan_report(report)

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(report), "--json"])
    with pytest.raises(SystemExit) as exit_info:
        main()
    assert exit_info.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2
