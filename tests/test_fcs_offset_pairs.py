import csv
from pathlib import Path

from labvault_scout.cli import scan
from labvault_scout.fcs_validation import validate_fcs_offset_pairs


def _fcs_header(
    version: bytes = b"FCS3.1",
    *,
    data_begin: int = 128,
    data_end: int = 255,
    analysis_begin: int = 0,
    analysis_end: int = 0,
) -> bytes:
    offsets = (58, 127, data_begin, data_end, analysis_begin, analysis_end)
    return version + b"    " + b"".join(f"{value:>8}".encode("ascii") for value in offsets)


def test_fcs_offset_pair_validation_rejects_half_zero_pairs():
    status = "FCS 3.1 fixed header"
    assert validate_fcs_offset_pairs(_fcs_header(data_begin=0, data_end=255), status) == "Invalid FCS DATA offsets"
    assert validate_fcs_offset_pairs(_fcs_header(analysis_begin=128, analysis_end=0), status) == "Invalid FCS ANALYSIS offsets"


def test_fcs_offset_pair_validation_preserves_legal_fcs3_zero_pairs():
    status = "FCS 3.1 fixed header"
    header = _fcs_header(data_begin=0, data_end=0, analysis_begin=0, analysis_end=0)
    assert validate_fcs_offset_pairs(header, status) == status


def test_fcs2_data_offsets_cannot_both_be_zero():
    status = "FCS 2.0 fixed header"
    header = _fcs_header(b"FCS2.0", data_begin=0, data_end=0)
    assert validate_fcs_offset_pairs(header, status) == "Invalid FCS DATA offsets"


def test_scan_does_not_verify_fcs_with_inconsistent_offset_pairs(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "bad-data.fcs").write_bytes(
        _fcs_header(data_begin=0, data_end=255) + b"/$TOT/1/" + b" " * 190
    )
    (source / "bad-analysis.fcs").write_bytes(
        _fcs_header(analysis_begin=128, analysis_end=0) + b"/$TOT/1/" + b" " * 190
    )
    (source / "bad-fcs2.fcs").write_bytes(
        _fcs_header(b"FCS2.0", data_begin=0, data_end=0) + b"/$TOT/1/" + b" " * 190
    )
    output = tmp_path / "report"

    assert scan(source, output) == 3
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        rows = {row["path"]: row for row in csv.DictReader(handle)}

    assert rows["bad-data.fcs"]["container_type"] == "Invalid FCS DATA offsets"
    assert rows["bad-analysis.fcs"]["container_type"] == "Invalid FCS ANALYSIS offsets"
    assert rows["bad-fcs2.fcs"]["container_type"] == "Invalid FCS DATA offsets"
    for row in rows.values():
        assert row["signature"] == "FCS"
        assert row["signature_status"] == "unverified: expected FCS fixed header"
        assert row["confidence"] == "LOW"
        assert row["recommended_action"] == "REVIEW_CONTAINER"
