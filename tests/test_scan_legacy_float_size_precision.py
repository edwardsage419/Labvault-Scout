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
    row = {
        "path": "data.csv", "size": size, "sha256": "a" * 64,
        "risk": "SAFE", "priority": "LOW", "open_copy": "",
    }
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
        + ',"sha256":"' + "a" * 64
        + '","risk":"SAFE","priority":"LOW","open_copy":""}],"errors":[]}',
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


@pytest.mark.parametrize(
    "number",
    [
        "9007199254740990.5",
        "9007199254740991.0000000000000001",
        "1.0000000000000000000001",
    ],
    ids=["near-safe-integer", "safe-boundary-fraction", "tiny-fraction"],
)
def test_rounded_fractional_legacy_size_is_rejected_before_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    number: str,
) -> None:
    # The decoder previously rounded these nonintegers to whole floats,
    # allowing a matching legacy checksum to certify a false byte count.
    path = tmp_path / "rounded-fraction.json"
    path.write_text(
        '{"files":[{"path":"data.csv","size":' + number
        + ',"sha256":"' + "a" * 64
        + '","risk":"SAFE","priority":"LOW","open_copy":""}],"errors":[]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Cannot read scan report") as exc_info:
        load_scan_report(path)
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "fractional number loses precision" in str(exc_info.value.__cause__)

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(path), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out)["status"] == "INVALID"


@pytest.mark.parametrize(
    "number,expected",
    [("1.0", 1.0), ("1.20e1", 12.0), ("1.25", 1.25), ("0e300", 0.0)],
)
def test_exact_or_fractional_floats_remain_compatible(
    tmp_path: Path, number: str, expected: float,
) -> None:
    path = tmp_path / "future-numeric-metadata.json"
    path.write_text(
        '{"schema_version":"2","files":[],"extension":{"value":' + number + "}}",
        encoding="utf-8",
    )
    payload = load_scan_report(path)
    assert payload["extension"]["value"] == expected
    assert report_integrity_status(payload) == "UNKNOWN"


def test_future_metadata_cannot_silently_round_fraction_to_integer(tmp_path: Path) -> None:
    path = tmp_path / "future-lossy-float.json"
    path.write_text(
        '{"schema_version":"2","files":[],"extension":{"value":'
        '1.0000000000000000000001}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Cannot read scan report"):
        load_scan_report(path)
