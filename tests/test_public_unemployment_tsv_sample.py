"""Offline real-data regression using public-domain BLS-derived county rates.

Source: vega/vega-datasets v3.3.1 data/unemployment.tsv (BLS LAUS).
The file is a historical transformed dataset, not current unemployment data.
No network calls are performed by this test or by the scanner.
"""

import csv
import hashlib
import shutil
from pathlib import Path

from labvault_scout.bundle import verify_bundle
from labvault_scout.cli import scan
from labvault_scout.compare import compare_reports, load_scan_report, verify_report


SHA256 = "f82bff0a9745cc9e9997c0b83a02ecc77cea7b1d6acbbc4b404bff293e95bb6e"
SIZE = 34739


def test_pinned_public_bls_unemployment_tsv_offline_scan(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "unemployment.tsv"
    original = fixture.read_bytes()
    assert len(original) == SIZE
    assert hashlib.sha256(original).hexdigest() == SHA256
    with fixture.open("r", encoding="ascii", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert len(rows) == 3218
    assert set(rows[0]) == {"id", "rate"}

    source_root = tmp_path / "source"
    source_root.mkdir()
    source = source_root / fixture.name
    shutil.copyfile(fixture, source)
    original_stat = source.stat()

    first = tmp_path / "first"
    second = tmp_path / "second"
    assert scan(source_root, first) == 1
    assert scan(source_root, second) == 1
    before = load_scan_report(first / "scan.json")
    after = load_scan_report(second / "scan.json")
    assert before == after
    assert before["summary"]["file_count"] == 1
    assert before["summary"]["error_count"] == 0
    row = before["files"][0]
    assert row["path"] == "unemployment.tsv"
    assert row["size"] == SIZE
    assert row["sha256"] == SHA256
    assert row["format"] == "TSV"
    assert row["risk"] == "SAFE"
    assert row["confidence"] == "MEDIUM"
    assert row["signature"] == ""
    for folder, payload in ((first, before), (second, after)):
        assert verify_report(payload)["status"] == "VERIFIED"
        assert verify_bundle(folder)["status"] == "VERIFIED"
    assert compare_reports(first / "scan.json", second / "scan.json")["summary"]["change_count"] == 0
    assert source.stat().st_size == original_stat.st_size
    assert source.stat().st_mtime_ns == original_stat.st_mtime_ns
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SHA256
    assert fixture.read_bytes() == original
