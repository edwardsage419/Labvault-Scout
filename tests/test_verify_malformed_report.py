import json
import sys
from pathlib import Path

import pytest

from labvault_scout.cli import main, scan
from labvault_scout.compare import load_scan_report


def test_cli_verify_malformed_json_is_concise_and_json_capable(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    bad = tmp_path / "malformed-report.json"
    bad.write_text("{not-json", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(bad)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "Cannot read scan report" in captured.err
    assert "Traceback" not in captured.err

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(bad), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2
    assert "Cannot read scan report" in result["error"]


@pytest.mark.parametrize(
    ("key", "marker"),
    [
        ("schema_version", '"schema_version": "1"'),
        ("name", '"name": "LabVault Scout"'),
        ("path", '"path": "data.csv"'),
    ],
)
def test_verify_rejects_duplicate_scan_report_json_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    key: str,
    marker: str,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "report"
    scan(source, output)
    report = output / "scan.json"

    original = report.read_text(encoding="utf-8")
    assert marker in original
    ambiguous = original.replace(marker, f"{marker}, {marker}", 1)
    # Default JSON decoding collapses the duplicate without changing the checksum-bearing payload.
    assert json.loads(ambiguous) == json.loads(original)
    report.write_text(ambiguous, encoding="utf-8")

    with pytest.raises(ValueError, match="Cannot read scan report") as exc_info:
        load_scan_report(report)
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert f"Duplicate scan report JSON key: {key}" in str(exc_info.value.__cause__)

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(report), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2
    assert "Cannot read scan report" in result["error"]
