import json
import sys
from pathlib import Path

import pytest

from labvault_scout.cli import main


@pytest.mark.parametrize("bad_side", ["before", "after"])
def test_cli_compare_malformed_json_exits_two_without_traceback(
    tmp_path: Path,
    monkeypatch,
    capsys,
    bad_side: str,
) -> None:
    bad = tmp_path / "malformed-compare.json"
    good = tmp_path / "good-legacy.json"
    bad.write_text("{not-json", encoding="utf-8")
    good.write_text(
        json.dumps({"files": [{"path": "data.csv", "sha256": "x"}], "errors": []}),
        encoding="utf-8",
    )

    before = bad if bad_side == "before" else good
    after = good if bad_side == "before" else bad
    monkeypatch.setattr(sys, "argv", ["labvault-scout", "compare", str(before), str(after)])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "Cannot read scan report" in captured.err
    assert "Traceback" not in captured.err
