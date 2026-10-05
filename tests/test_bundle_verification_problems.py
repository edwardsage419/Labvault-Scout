from pathlib import Path

from labvault_scout.bundle import verify_bundle
from labvault_scout.cli import scan


def _scanned_bundle(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "report"
    scan(source, output)
    return output


def test_verify_bundle_detects_non_regular_core_file(tmp_path: Path) -> None:
    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    target.unlink()
    target.mkdir()

    result = verify_bundle(output)

    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert {"path": "report.html", "issue": "NOT_REGULAR_FILE"} in result["problems"]


def test_verify_bundle_detects_size_mismatch(tmp_path: Path) -> None:
    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    expected_size = target.stat().st_size
    target.write_bytes(target.read_bytes() + b"x")

    result = verify_bundle(output)

    problem = next(item for item in result["problems"] if item["path"] == "report.html")
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert problem == {
        "path": "report.html",
        "issue": "SIZE_MISMATCH",
        "expected": expected_size,
        "actual": expected_size + 1,
    }
