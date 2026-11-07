"""JSON floating-point tokens must have bounded length on all supported Pythons."""

import json
import sys
from pathlib import Path

import pytest

from labvault_scout.cli import main
from labvault_scout.compare import load_scan_report, report_integrity_status


@pytest.mark.parametrize(
    "number",
    [
        "0." + "0" * 4301,
        "-0." + "0" * 4301,
        "0e" + "9" * 4301,
        "-0e" + "9" * 4301,
    ],
    ids=["positive-decimal", "negative-decimal", "positive-exponent", "negative-exponent"],
)
def test_overlong_json_float_rejected_by_loader_and_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    number: str,
) -> None:
    # Zero-valued tokens previously bypassed overflow and underflow checks.
    report = tmp_path / "oversized-float.json"
    report.write_text(
        '{"schema_version":"2","files":[],"future_extension":{"number":'
        + number + "}}",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Cannot read scan report") as exc_info:
        load_scan_report(report)
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "Scan report JSON float exceeds 4300 characters" in str(exc_info.value.__cause__)

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


@pytest.mark.parametrize("number", ["0." + "0" * 4298, "0e" + "9" * 300, "1.25"])
def test_bounded_json_float_in_future_extension_remains_loadable(
    tmp_path: Path, number: str,
) -> None:
    report = tmp_path / "bounded-float.json"
    report.write_text(
        '{"schema_version":"2","files":[],"future_extension":{"number":'
        + number + "}}",
        encoding="utf-8",
    )
    payload = load_scan_report(report)
    assert payload["future_extension"]["number"] == float(number)
    assert report_integrity_status(payload) == "UNKNOWN"
