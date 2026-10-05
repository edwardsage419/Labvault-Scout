import json
import sys
from pathlib import Path

import pytest

from labvault_scout.cli import main


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
