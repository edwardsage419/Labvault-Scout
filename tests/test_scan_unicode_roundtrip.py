"""Unicode source paths survive scan, verification, and comparison unchanged."""

import csv
import hashlib
from pathlib import Path

import pytest

from labvault_scout.bundle import verify_bundle
from labvault_scout.cli import scan
from labvault_scout.compare import compare_reports, load_scan_report, verify_report, write_comparison


@pytest.mark.parametrize(
    "relative_path",
    [
        "研究/样本_β.csv",
        "資料/測定_é_🔬.csv",
    ],
)
def test_unicode_paths_roundtrip_across_reports(
    tmp_path: Path, relative_path: str,
) -> None:
    source = tmp_path / "source"
    target = source.joinpath(*relative_path.split("/"))
    target.parent.mkdir(parents=True)
    original = b"sample,measurement\n1,2\n"
    updated = b"sample,measurement\n1,3\n"
    target.write_bytes(original)

    before_dir = tmp_path / "before"
    assert scan(source, before_dir) == 1
    before = load_scan_report(before_dir / "scan.json")
    assert verify_report(before)["status"] == "VERIFIED"
    assert verify_bundle(before_dir)["status"] == "VERIFIED"
    assert before["files"][0]["path"] == relative_path
    assert before["files"][0]["sha256"] == hashlib.sha256(original).hexdigest()
    assert before["errors"] == []
    with (before_dir / "files.csv").open(encoding="utf-8-sig", newline="") as handle:
        assert list(csv.DictReader(handle))[0]["path"] == relative_path
    assert relative_path in (before_dir / "report.html").read_text(encoding="utf-8")
    assert target.read_bytes() == original

    target.write_bytes(updated)
    after_dir = tmp_path / "after"
    assert scan(source, after_dir) == 1
    after = load_scan_report(after_dir / "scan.json")
    assert verify_report(after)["status"] == "VERIFIED"
    assert verify_bundle(after_dir)["status"] == "VERIFIED"
    assert after["files"][0]["path"] == relative_path
    assert target.read_bytes() == updated

    comparison = compare_reports(before_dir / "scan.json", after_dir / "scan.json")
    assert comparison["comparison_status"] == "COMPLETE"
    assert comparison["summary"]["change_count"] == 1
    assert comparison["changes"][0]["change_type"] == "CONTENT_CHANGED"
    assert comparison["changes"][0]["before_path"] == relative_path
    assert comparison["changes"][0]["after_path"] == relative_path

    comparison_dir = tmp_path / "comparison"
    write_comparison(comparison, comparison_dir)
    with (comparison_dir / "changes.csv").open(encoding="utf-8-sig", newline="") as handle:
        csv_change = list(csv.DictReader(handle))[0]
    assert csv_change["before_path"] == relative_path
    assert csv_change["after_path"] == relative_path
