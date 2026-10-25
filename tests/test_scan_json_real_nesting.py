"""Exercise real JSON decoder nesting limits across supported Python versions."""

import json
import sys
from pathlib import Path

import pytest

from labvault_scout.cli import main
from labvault_scout.compare import load_scan_report, report_integrity_status


def _nested_json(kind: str, depth: int) -> str:
    if kind == "array":
        return "[" * depth + "0" + "]" * depth
    return '{"nested":' * depth + "0" + "}" * depth


@pytest.mark.parametrize("kind", ["array", "object"])
@pytest.mark.parametrize("schema", ["legacy", "future"])
def test_real_deep_json_nesting_rejected_by_loader_verify_and_compare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    kind: str,
    schema: str,
) -> None:
    # Real decoding, with no mocked json.loads or artificial RecursionError.
    prefix = '{"files":[],"errors":[],"extension":' if schema == "legacy" else (
        '{"schema_version":"2","files":[],"extension":'
    )
    report = tmp_path / "deep.json"
    report.write_text(prefix + _nested_json(kind, 12000) + "}", encoding="utf-8")

    with pytest.raises(ValueError, match="Cannot read scan report") as exc_info:
        load_scan_report(report)
    assert isinstance(exc_info.value.__cause__, RecursionError)

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(report), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2

    good = tmp_path / "good.json"
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


@pytest.mark.parametrize("kind", ["array", "object"])
def test_moderate_future_schema_nesting_remains_loadable(
    tmp_path: Path, kind: str,
) -> None:
    report = tmp_path / "nested.json"
    report.write_text(
        '{"schema_version":"2","files":[],"extension":'
        + _nested_json(kind, 24) + "}",
        encoding="utf-8",
    )
    payload = load_scan_report(report)
    assert payload["schema_version"] == "2"
    assert report_integrity_status(payload) == "UNKNOWN"
