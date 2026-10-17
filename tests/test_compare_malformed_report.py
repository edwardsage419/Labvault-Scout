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


@pytest.mark.parametrize("fractional_size", [7.9, 0.9, -0.9])
def test_compare_legacy_fractional_size_is_not_truncated_into_byte_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fractional_size: float,
) -> None:
    before = tmp_path / "fractional-legacy.json"
    after = tmp_path / "integer-legacy.json"
    output = tmp_path / "comparison"
    before.write_text(
        json.dumps({"files": [
            {"path": "fractional.csv", "sha256": "before", "size": fractional_size}
        ], "errors": []}),
        encoding="utf-8",
    )
    after.write_text(
        json.dumps({"files": [
            {"path": "whole.csv", "sha256": "after", "size": "7"}
        ], "errors": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys, "argv",
        ["labvault-scout", "compare", str(before), str(after), "-o", str(output)],
    )

    main()

    result = json.loads((output / "comparison.json").read_text(encoding="utf-8"))
    assert result["before"]["metrics"]["file_count"] == 1
    assert result["before"]["metrics"]["total_bytes"] == 0
    assert result["after"]["metrics"]["total_bytes"] == 7
    assert result["metrics_delta"]["total_bytes"] == 7


@pytest.mark.parametrize(
    ("before_score", "after_score", "before_priority", "after_priority",
     "expected_direction", "expected_delta"),
    [
        (7.9, 7.1, "LOW", "HIGH", "ESCALATED", None),
        (7.9, 8.1, "HIGH", "HIGH", "UNCHANGED", None),
        (7, "8", "LOW", "LOW", "ESCALATED", 1),
        (7.0, 8.0, "LOW", "LOW", "ESCALATED", 1),
    ],
)
def test_compare_legacy_fractional_priority_score_uses_category_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    before_score: object,
    after_score: object,
    before_priority: str,
    after_priority: str,
    expected_direction: str,
    expected_delta: int | None,
) -> None:
    before = tmp_path / "before-legacy.json"
    after = tmp_path / "after-legacy.json"
    output = tmp_path / "comparison"
    before.write_text(
        json.dumps({"files": [{
            "path": "data.csv", "sha256": "same",
            "priority": before_priority, "priority_score": before_score,
        }], "errors": []}),
        encoding="utf-8",
    )
    after.write_text(
        json.dumps({"files": [{
            "path": "data.csv", "sha256": "same",
            "priority": after_priority, "priority_score": after_score,
        }], "errors": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys, "argv",
        ["labvault-scout", "compare", str(before), str(after), "-o", str(output)],
    )

    main()

    result = json.loads((output / "comparison.json").read_text(encoding="utf-8"))
    assert result["summary"]["assessment_changed_count"] == 1
    change = result["changes"][0]
    assert change["change_type"] == "ASSESSMENT_CHANGED"
    assert change["priority_direction"] == expected_direction
    assert change["priority_delta"] == expected_delta
