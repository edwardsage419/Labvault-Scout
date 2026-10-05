import csv
from pathlib import Path

from labvault_scout.cli import scan
from labvault_scout.stata_validation import validate_stata_k_header


def _stata_header(release: bytes = b"118", byteorder: bytes = b"LSF", suffix: bytes = b"<K>\x01\x00</K>") -> bytes:
    return (
        b"<stata_dta><header><release>"
        + release
        + b"</release><byteorder>"
        + byteorder
        + b"</byteorder>"
        + suffix
    )


def test_stata_k_header_validation_preserves_present_marker_pair():
    status = "Stata DTA release 118 (LSF)"
    assert validate_stata_k_header(_stata_header(), status) == status


def test_stata_k_header_validation_rejects_missing_and_truncated_marker_pair():
    status = "Stata DTA release 118 (LSF)"
    assert validate_stata_k_header(_stata_header(suffix=b""), status) == "Invalid Stata DTA K header"
    assert validate_stata_k_header(_stata_header(suffix=b"<K>\x01\x00"), status) == "Truncated Stata DTA K header"
    assert validate_stata_k_header(_stata_header(suffix=b"<K></K>"), status) == "Invalid Stata DTA K header"


def test_scan_does_not_verify_modern_stata_without_k_header(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "missing-k.dta").write_bytes(_stata_header(suffix=b""))
    (source / "truncated-k.dta").write_bytes(_stata_header(suffix=b"<K>\x01\x00"))
    output = tmp_path / "report"

    assert scan(source, output) == 2
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        rows = {row["path"]: row for row in csv.DictReader(handle)}

    assert rows["missing-k.dta"]["container_type"] == "Invalid Stata DTA K header"
    assert rows["truncated-k.dta"]["container_type"] == "Truncated Stata DTA K header"
    for row in rows.values():
        assert row["signature"] == "STATA_DTA"
        assert row["signature_status"] == "unverified: expected modern Stata DTA structure"
        assert row["confidence"] == "LOW"
        assert row["recommended_action"] == "REVIEW_CONTAINER"
