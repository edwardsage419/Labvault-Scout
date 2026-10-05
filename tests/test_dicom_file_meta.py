import csv
from pathlib import Path

from labvault_scout.cli import scan
from labvault_scout.dicom_validation import validate_dicom_file_meta


def _valid_part10_header() -> bytes:
    return (
        b"\x00" * 128
        + b"DICM"
        + b"\x02\x00\x00\x00"
        + b"UL"
        + (4).to_bytes(2, "little")
        + (12).to_bytes(4, "little")
        + b"\x00" * 12
    )


def test_dicom_file_meta_validation_preserves_valid_group_length_element():
    assert validate_dicom_file_meta(_valid_part10_header(), "DICOM Part 10 file") == "DICOM Part 10 file"


def test_dicom_file_meta_validation_rejects_marker_only_and_invalid_structure():
    marker_only = b"\x00" * 128 + b"DICM"
    assert validate_dicom_file_meta(marker_only, "DICOM Part 10 file") == "Truncated DICOM File Meta Information"

    base = bytearray(_valid_part10_header())
    bad_tag = bytearray(base)
    bad_tag[132:136] = b"\x02\x00\x01\x00"
    bad_vr = bytearray(base)
    bad_vr[136:138] = b"OB"
    bad_length = bytearray(base)
    bad_length[138:140] = (2).to_bytes(2, "little")

    assert "group length element" in validate_dicom_file_meta(bytes(bad_tag), "DICOM Part 10 file")
    assert "group length VR" in validate_dicom_file_meta(bytes(bad_vr), "DICOM Part 10 file")
    assert "value length" in validate_dicom_file_meta(bytes(bad_length), "DICOM Part 10 file")


def test_scan_does_not_verify_dicom_marker_without_valid_file_meta(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "valid.dcm").write_bytes(_valid_part10_header())
    (source / "marker-only.dcm").write_bytes(b"\x00" * 128 + b"DICM" + b"\x00" * 64)
    output = tmp_path / "report"

    assert scan(source, output) == 2
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        rows = {row["path"]: row for row in csv.DictReader(handle)}

    valid = rows["valid.dcm"]
    assert valid["container_type"] == "DICOM Part 10 file"
    assert valid["signature_status"] == "verified"
    assert valid["confidence"] == "HIGH"

    invalid = rows["marker-only.dcm"]
    assert invalid["container_type"] == "Invalid DICOM File Meta Information group length element"
    assert invalid["signature_status"] == "unverified: expected DICOM Part 10 structure"
    assert invalid["confidence"] == "LOW"
    assert invalid["recommended_action"] == "REVIEW_CONTAINER"
