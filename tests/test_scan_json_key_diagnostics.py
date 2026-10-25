"""Malformed JSON keys must produce UTF-8-safe errors in report commands."""

import io
import json
import sys
from pathlib import Path

import pytest

from labvault_scout.cli import main, scan
from labvault_scout.compare import load_scan_report


@pytest.mark.parametrize("codepoint", [0xD800, 0xDCFF])
@pytest.mark.parametrize("location", ["top_level", "file_row", "duplicate_key"])
def test_invalid_unicode_json_keys_have_safe_cli_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    codepoint: int,
    location: str,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.csv").write_text("value\\n1\\n", encoding="utf-8")
    output = tmp_path / "scan"
    assert scan(source, output) == 1
    valid_path = output / "scan.json"
    valid = load_scan_report(valid_path)

    bad_key = "invalid" + chr(codepoint)
    escaped_key = bad_key.encode("utf-8", errors="backslashreplace").decode("utf-8")
    if location == "duplicate_key":
        quoted_key = json.dumps(bad_key, ensure_ascii=True)
        raw = (
            '{"schema_version":"1","files":[],'
            + quoted_key + ":1," + quoted_key + ":2}"
        )
        expected = "Duplicate scan report JSON key"
    else:
        malformed = json.loads(json.dumps(valid))
        if location == "top_level":
            malformed[bad_key] = "extra"
            expected = "unexpected top-level fields"
        else:
            malformed["files"][0][bad_key] = "extra"
            expected = "unexpected fields"
        raw = json.dumps(malformed, ensure_ascii=True)

    report = tmp_path / "malformed-key.json"
    report.write_text(raw, encoding="utf-8")
    # Parser errors are intentionally wrapped by the report loader.
    diagnostic = "Cannot read scan report" if location == "duplicate_key" else expected
    with pytest.raises(ValueError, match=diagnostic) as exc_info:
        load_scan_report(report)
    detail = exc_info.value.__cause__ if location == "duplicate_key" else exc_info.value
    assert isinstance(detail, ValueError)
    assert escaped_key in str(detail)
    str(detail).encode("utf-8", errors="strict")

    # Simulate a strict UTF-8 terminal. An unpaired surrogate in an error
    # message used to raise UnicodeEncodeError while printing the CLI error.
    stdout_bytes = io.BytesIO()
    stderr_bytes = io.BytesIO()
    stdout = io.TextIOWrapper(stdout_bytes, encoding="utf-8", errors="strict")
    stderr = io.TextIOWrapper(stderr_bytes, encoding="utf-8", errors="strict")
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(report)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    stderr.flush()
    message = stderr_bytes.getvalue().decode("utf-8")
    assert diagnostic in message
    if location != "duplicate_key":
        assert escaped_key in message
    assert "Traceback" not in message

    monkeypatch.setattr(
        sys, "argv", ["labvault-scout", "verify", str(report), "--json"]
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    stdout.flush()
    response = json.loads(stdout_bytes.getvalue().decode("utf-8"))
    assert response["status"] == "INVALID"
    assert response["exit_code"] == 2
    assert diagnostic in response["error"]
    if location != "duplicate_key":
        assert escaped_key in response["error"]

    monkeypatch.setattr(
        sys, "argv", ["labvault-scout", "compare", str(report), str(valid_path)]
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    stderr.flush()
    compare_error = stderr_bytes.getvalue().decode("utf-8")
    assert diagnostic in compare_error
    if location != "duplicate_key":
        assert escaped_key in compare_error
    assert "Traceback" not in compare_error
