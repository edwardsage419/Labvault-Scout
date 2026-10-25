"""Exercise wide JSON structures without imposing a new report-size policy."""

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


@pytest.mark.parametrize("schema", ["legacy", "future"])
@pytest.mark.parametrize("kind", ["array", "object"])
def test_wide_json_extension_preserves_all_members(
    tmp_path: Path, schema: str, kind: str,
) -> None:
    # Width is independent of the decoder recursion limit. Keep the fixture
    # modest so the test remains cheap on Windows, Linux, and macOS.
    width = 1024
    extension = (
        list(range(width))
        if kind == "array"
        else {f"item_{i:04d}": i for i in range(width)}
    )
    payload = {"files": [], "errors": [], "extension": extension}
    if schema == "future":
        payload["schema_version"] = "2"
    report = tmp_path / "wide.json"
    report.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_scan_report(report)
    assert loaded["extension"] == extension
    assert len(loaded["extension"]) == width
    assert report_integrity_status(loaded) == "UNKNOWN"

    checked = verify_report(loaded)
    assert checked["status"] == ("UNKNOWN" if schema == "legacy" else "UNSUPPORTED")
    assert checked["exit_code"] == (1 if schema == "legacy" else 2)

    comparison = compare_payloads(loaded, loaded)
    assert comparison["comparison_status"] == ("COMPLETE" if schema == "legacy" else "PARTIAL")
    assert comparison["summary"]["change_count"] == 0
    assert comparison["changes"] == []


@pytest.mark.parametrize("schema", ["legacy", "future"])
def test_late_duplicate_in_wide_json_object_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    schema: str,
) -> None:
    # A repeated key after many unique siblings must still be rejected.
    prefix = '{"files":[],"errors":[],"extension":{' if schema == "legacy" else (
        '{"schema_version":"2","files":[],"errors":[],"extension":{'
    )
    members = ",".join(f'"item_{i:04d}":{i}' for i in range(1024))
    report = tmp_path / "wide-duplicate.json"
    report.write_text(prefix + members + ',"item_1023":-1}}', encoding="utf-8")

    with pytest.raises(ValueError, match="Cannot read scan report") as exc_info:
        load_scan_report(report)
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "Duplicate scan report JSON key: item_1023" in str(exc_info.value.__cause__)

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(report), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out)["status"] == "INVALID"

    good = tmp_path / "good.json"
    good.write_text('{"files":[],"errors":[]}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["labvault-scout", "compare", str(report), str(good)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Cannot read scan report" in captured.err
    assert "Traceback" not in captured.err
