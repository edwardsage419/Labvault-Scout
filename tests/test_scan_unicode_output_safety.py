"""Unicode report destinations preserve integrity and fail closed on write errors."""

import csv
from pathlib import Path

import pytest

import labvault_scout.safeio as safeio
from labvault_scout.bundle import verify_bundle
from labvault_scout.cli import scan
from labvault_scout.compare import compare_reports, load_scan_report, verify_report, write_comparison


def test_unicode_output_directories_support_scan_and_comparison(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = source / "sample.csv"
    target.write_bytes(b"value\n1\n")

    before_dir = tmp_path / "研究结果_β" / "扫描_🔬"
    assert scan(source, before_dir) == 1
    assert verify_report(load_scan_report(before_dir / "scan.json"))["status"] == "VERIFIED"
    assert verify_bundle(before_dir)["status"] == "VERIFIED"

    target.write_bytes(b"value\n2\n")
    after_dir = tmp_path / "研究结果_β" / "复测_é"
    assert scan(source, after_dir) == 1
    assert verify_bundle(after_dir)["status"] == "VERIFIED"

    result = compare_reports(before_dir / "scan.json", after_dir / "scan.json")
    assert result["comparison_status"] == "COMPLETE"
    assert result["summary"]["change_count"] == 1
    comparison_dir = tmp_path / "研究结果_β" / "比较_🔬"
    write_comparison(result, comparison_dir)
    with (comparison_dir / "changes.csv").open(encoding="utf-8-sig", newline="") as handle:
        changes = list(csv.DictReader(handle))
    assert len(changes) == 1
    assert changes[0]["before_path"] == "sample.csv"
    assert changes[0]["after_path"] == "sample.csv"
    assert (comparison_dir / "comparison.json").is_file()
    assert target.read_bytes() == b"value\n2\n"


def test_unicode_output_failed_replace_preserves_old_json_and_invalidates_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = source / "sample.csv"
    target.write_bytes(b"value\n1\n")
    output = tmp_path / "结果_é_🔬"
    assert scan(source, output) == 1
    assert verify_bundle(output)["status"] == "VERIFIED"
    old_json = (output / "scan.json").read_bytes()

    target.write_bytes(b"value\n2\n")
    original_replace = safeio.os.replace

    def fail_json_replace(src, dst):
        if Path(dst) == output / "scan.json":
            raise UnicodeEncodeError("utf-8", "\ud800", 0, 1, "synthetic path encoding failure")
        return original_replace(src, dst)

    monkeypatch.setattr(safeio.os, "replace", fail_json_replace)
    with pytest.raises(UnicodeEncodeError, match="synthetic path encoding failure"):
        scan(source, output)

    assert (output / "scan.json").read_bytes() == old_json
    assert list(output.glob(".scan.json.*.tmp")) == []
    assert verify_bundle(output)["status"] == "FAILED"
    assert target.read_bytes() == b"value\n2\n"
