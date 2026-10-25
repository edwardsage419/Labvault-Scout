"""Oversized JSON integer tokens must be bounded on all supported Python versions."""

import json
import sys
from pathlib import Path

import pytest

from labvault_scout.cli import main
from labvault_scout.compare import load_scan_report, report_integrity_status


@pytest.mark.parametrize("sign", ["", "-"])
def test_overlong_json_integer_rejected_by_loader_and_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    sign: str,
) -> None:
    # Place the number in an unknown schema extension to exercise the JSON
    # parser independently of Schema 1's integer field validation.
    report = tmp_path / "oversized-integer.json"
    report.write_text(
        '{"schema_version":"2","files":[],"future_extension":{"number":'
        + sign + "9" * 4301 + "}}",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Cannot read scan report") as exc_info:
        load_scan_report(report)
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "Scan report JSON integer exceeds 4300 digits" in str(exc_info.value.__cause__)

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(report), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2

    good = tmp_path / "good-legacy.json"
    good.write_text('{"files":[],"errors":[]}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["labvault-scout", "compare", str(report), str(good)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "Cannot read scan report" in captured.err
    assert "Traceback" not in captured.err


def test_large_bounded_integer_in_future_extension_remains_loadable(tmp_path: Path) -> None:
    report = tmp_path / "bounded-integer.json"
    report.write_text(
        '{"schema_version":"2","files":[],"future_extension":{"number":'
        + "9" * 300 + "}}",
        encoding="utf-8",
    )
    payload = load_scan_report(report)
    assert payload["future_extension"]["number"] == int("9" * 300)
    assert report_integrity_status(payload) == "UNKNOWN"
