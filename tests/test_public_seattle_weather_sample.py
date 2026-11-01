"""Offline real-data regression using a fixed public-domain NOAA-derived sample.

Source: vega/vega-datasets tag v3.3.1, data/seattle-weather.csv.
Upstream datapackage.json: U.S. Government Dataset, NOAA observations;
its categorical weather field is derived for instructional use.
SHA-256: 0845078a290b48e3149ab8639966824110a251db4e06fc144c06ebb534af23be.
The test never fetches network data or changes the fixture.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from labvault_scout.bundle import verify_bundle
from labvault_scout.cli import scan
from labvault_scout.compare import compare_reports, load_scan_report, verify_report


SAMPLE_SHA256 = "0845078a290b48e3149ab8639966824110a251db4e06fc144c06ebb534af23be"
SAMPLE_BYTES = 48219


def test_pinned_public_seattle_weather_offline_scan_and_verify(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "seattle-weather.csv"
    original = fixture.read_bytes()
    assert len(original) == SAMPLE_BYTES
    assert hashlib.sha256(original).hexdigest() == SAMPLE_SHA256

    root = tmp_path / "source"
    root.mkdir()
    source = root / fixture.name
    shutil.copyfile(fixture, source)
    source_stat_before = source.stat()

    first = tmp_path / "first-report"
    second = tmp_path / "second-report"
    assert scan(root, first) == 1
    assert scan(root, second) == 1

    first_report = load_scan_report(first / "scan.json")
    second_report = load_scan_report(second / "scan.json")
    assert first_report == second_report
    assert first_report["summary"]["file_count"] == 1
    assert first_report["summary"]["error_count"] == 0
    row = first_report["files"][0]
    assert row["path"] == "seattle-weather.csv"
    assert row["size"] == SAMPLE_BYTES
    assert row["sha256"] == SAMPLE_SHA256
    assert row["format"] == "CSV"
    assert row["risk"] == "SAFE"
    assert row["confidence"] == "MEDIUM"
    assert row["signature"] == ""
    assert row["container_type"] == ""

    for report_dir, report in ((first, first_report), (second, second_report)):
        assert verify_report(report)["status"] == "VERIFIED"
        assert verify_bundle(report_dir)["status"] == "VERIFIED"
    comparison = compare_reports(first / "scan.json", second / "scan.json")
    assert comparison["summary"]["change_count"] == 0

    assert source.stat().st_size == source_stat_before.st_size
    assert source.stat().st_mtime_ns == source_stat_before.st_mtime_ns
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SAMPLE_SHA256
    assert fixture.read_bytes() == original
