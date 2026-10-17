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


def test_load_scan_report_wraps_json_parser_recursion_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = tmp_path / "deeply-nested-report.json"
    report.write_text("[" * 4000 + "0" + "]" * 4000, encoding="utf-8")
    original_loads = json.loads

    def raise_recursion_error(
        text: str, *, object_pairs_hook: object = None,
        parse_constant: object = None, parse_float: object = None
    ) -> object:
        assert text.startswith("[" * 4000)
        assert callable(object_pairs_hook)
        assert callable(parse_constant)
        assert callable(parse_float)
        raise RecursionError("JSON nesting exceeds parser recursion limit")

    with monkeypatch.context() as patched:
        patched.setattr(json, "loads", raise_recursion_error)

        with pytest.raises(ValueError, match="Cannot read scan report") as exc_info:
            load_scan_report(report)
        assert isinstance(exc_info.value.__cause__, RecursionError)

        patched.setattr(sys, "argv", ["labvault-scout", "verify", str(report)])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err.startswith("Error:")
        assert "Cannot read scan report" in captured.err
        assert "Traceback" not in captured.err

        patched.setattr(sys, "argv", ["labvault-scout", "verify", str(report), "--json"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
        captured = capsys.readouterr()
        assert captured.err == ""

    result = original_loads(captured.out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2
    assert "Cannot read scan report" in result["error"]


@pytest.mark.parametrize(
    ("number", "expected_cause"),
    [
        ("NaN", "Non-standard scan report JSON constant: NaN"),
        ("Infinity", "Non-standard scan report JSON constant: Infinity"),
        ("-Infinity", "Non-standard scan report JSON constant: -Infinity"),
        ("1e999", "Scan report JSON number exceeds floating-point range"),
        ("-1e999", "Scan report JSON number exceeds floating-point range"),
    ],
)
def test_invalid_nonfinite_scan_number_is_rejected_by_verify_and_compare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    number: str,
    expected_cause: str,
) -> None:
    bad = tmp_path / "invalid-numeric-report.json"
    bad.write_text(
        '{"files": [{"path": "data.csv", "size": ' + number + '}], "errors": []}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Cannot read scan report") as exc_info:
        load_scan_report(bad)
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert expected_cause in str(exc_info.value.__cause__)

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(bad), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2
    assert "Cannot read scan report" in result["error"]

    good = tmp_path / "good-legacy-report.json"
    good.write_text('{"files": [{"path": "data.csv", "size": 1}], "errors": []}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["labvault-scout", "compare", str(bad), str(good)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "Cannot read scan report" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("number", ["1e-999", "-1e-999", "1E-999"])
def test_scan_report_rejects_nonzero_float_underflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    number: str,
) -> None:
    bad = tmp_path / "underflow-report.json"
    bad.write_text(
        '{"files": [{"path": "data.csv", "size": ' + number + '}], "errors": []}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Cannot read scan report") as exc_info:
        load_scan_report(bad)
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "Scan report JSON number underflows floating-point range" in str(
        exc_info.value.__cause__
    )

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(bad), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2
    assert "Cannot read scan report" in result["error"]

    good = tmp_path / "good-legacy-report.json"
    good.write_text('{"files": [], "errors": []}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["labvault-scout", "compare", str(bad), str(good)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "Cannot read scan report" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("number", ["0e-999", "-0e-999", "0.000e-999"])
def test_scan_report_exact_float_zero_is_not_underflow(
    tmp_path: Path, number: str
) -> None:
    report = tmp_path / "zero-legacy-report.json"
    report.write_text(
        '{"files": [{"path": "data.csv", "size": ' + number + '}], "errors": []}',
        encoding="utf-8",
    )

    parsed = load_scan_report(report)

    assert parsed["files"][0]["size"] == 0.0
