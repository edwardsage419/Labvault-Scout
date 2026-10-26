"""Reject imprecise legacy floating-point file sizes without affecting exact integers."""

import json
import sys
from pathlib import Path

import pytest

from labvault_scout.cli import main
from labvault_scout.compare import (
    compare_payloads,
    load_scan_report,
    report_integrity_status,
    scan_metrics,
    verify_report,
)
from labvault_scout.report import build_summary


def _legacy_report(size: int | float) -> dict:
    row = {"path": "data.csv", "size": size, "sha256": "a" * 64}
    payload = {"files": [row], "errors": []}
    payload["summary"] = build_summary([row], [], [])
    return payload


@pytest.mark.parametrize(
    "number",
    ["9007199254740992.0", "9007199254740993.0", "1e308"],
    ids=["above-safe-range", "rounded-by-decoder", "large-exponent"],
)
def test_unsafe_legacy_float_size_cannot_verify(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    number: str,
) -> None:
    # Use the original JSON number to exercise float rounding in the decoder.
    path = tmp_path / "legacy-imprecise-size.json"
    path.write_text(
        '{"files":[{"path":"data.csv","size":' + number
        + ',"sha256":"' + "a" * 64 + '"}],"errors":[]}',
        encoding="utf-8",
    )
    loaded = load_scan_report(path)
    # A matching legacy inventory checksum must not certify a rounded byte count.
    loaded["summary"] = build_summary(loaded["files"], [], [])
    assert report_integrity_status(loaded) == "MISMATCH"
    assert scan_metrics(loaded)["total_bytes"] == 0
    assert verify_report(loaded)["status"] == "FAILED"

    before = _legacy_report(1.0)
    assert report_integrity_status(before) == "VERIFIED"
    compared = compare_payloads(before, loaded)
    assert compared["comparison_status"] == "PARTIAL"
    assert compared["after"]["integrity_status"] == "MISMATCH"

    path.write_text(json.dumps(loaded), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(path), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out)["status"] == "FAILED"


@pytest.mark.parametrize("size", [1.0, 9007199254740991.0, 9007199254740993])
def test_exact_legacy_sizes_remain_verifiable(size: int | float) -> None:
    payload = _legacy_report(size)
    assert report_integrity_status(payload) == "VERIFIED"
    assert scan_metrics(payload)["total_bytes"] == int(size)
