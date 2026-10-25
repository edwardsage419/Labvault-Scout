"""Malformed legacy paths must produce UTF-8-safe CLI diagnostics."""

import io
import json
import sys
from pathlib import Path

import pytest

from labvault_scout.cli import main
from labvault_scout.compare import compare_reports, load_scan_report


@pytest.mark.parametrize("codepoint", [0xD800, 0xDCFF])
@pytest.mark.parametrize("case", ["duplicate", "normalized_collision"])
def test_unencodable_legacy_path_errors_are_safe_for_utf8_terminals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    codepoint: int,
    case: str,
) -> None:
    invalid = "unsafe" + chr(codepoint)
    if case == "duplicate":
        paths = [invalid + ".csv", invalid + ".csv"]
        expected = "Duplicate path in scan report"
        expected_path = paths[0]
    else:
        paths = [invalid + "\\data.csv", invalid + "/data.csv"]
        expected = "Path collision after legacy normalization"
        expected_path = paths[1]

    report = tmp_path / "malformed-legacy.json"
    report.write_text(
        json.dumps(
            {"files": [{"path": path, "sha256": "a" * 64} for path in paths], "errors": []},
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    other = tmp_path / "other-legacy.json"
    other.write_text('{"files":[],"errors":[]}', encoding="utf-8")

    if case == "duplicate":
        with pytest.raises(ValueError, match=expected) as exc_info:
            load_scan_report(report)
    else:
        assert len(load_scan_report(report)["files"]) == 2
        with pytest.raises(ValueError, match=expected) as exc_info:
            compare_reports(report, other)

    escaped = expected_path.encode("utf-8", errors="backslashreplace").decode("utf-8")
    assert escaped in str(exc_info.value)
    str(exc_info.value).encode("utf-8", errors="strict")

    stdout_bytes = io.BytesIO()
    stderr_bytes = io.BytesIO()
    stdout = io.TextIOWrapper(stdout_bytes, encoding="utf-8", errors="strict")
    stderr = io.TextIOWrapper(stderr_bytes, encoding="utf-8", errors="strict")
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    if case == "duplicate":
        monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(report), "--json"])
    else:
        monkeypatch.setattr(sys, "argv", ["labvault-scout", "compare", str(report), str(other)])
    with pytest.raises(SystemExit) as exit_info:
        main()
    assert exit_info.value.code == 2
    stdout.flush()
    stderr.flush()
    if case == "duplicate":
        result = json.loads(stdout_bytes.getvalue().decode("utf-8"))
        assert result["status"] == "INVALID"
        assert expected in result["error"]
        assert escaped in result["error"]
        assert stderr_bytes.getvalue() == b""
    else:
        diagnostic = stderr_bytes.getvalue().decode("utf-8")
        assert expected in diagnostic
        assert escaped in diagnostic
        assert "Traceback" not in diagnostic
        assert stdout_bytes.getvalue() == b""
