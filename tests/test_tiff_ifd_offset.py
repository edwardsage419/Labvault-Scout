import csv
from pathlib import Path

from labvault_scout.cli import scan
from labvault_scout.tiff_validation import validate_tiff_first_ifd_offset


def test_tiff_first_ifd_offset_validation_rejects_invalid_header_offsets():
    classic_inside = bytes.fromhex("49492A00") + (6).to_bytes(4, "little")
    classic_unaligned = bytes.fromhex("4D4D002A") + (9).to_bytes(4, "big")
    big_inside = bytes.fromhex("49492B0008000000") + (8).to_bytes(8, "little")
    big_unaligned = bytes.fromhex("4D4D002B00080000") + (20).to_bytes(8, "big")

    assert validate_tiff_first_ifd_offset(classic_inside, "TIFF classic (little-endian)") == "Invalid TIFF first IFD offset"
    assert validate_tiff_first_ifd_offset(classic_unaligned, "TIFF classic (big-endian)") == "Invalid TIFF first IFD offset"
    assert validate_tiff_first_ifd_offset(big_inside, "BigTIFF (little-endian)") == "Invalid BigTIFF first IFD offset"
    assert validate_tiff_first_ifd_offset(big_unaligned, "BigTIFF (big-endian)") == "Invalid BigTIFF first IFD offset"


def test_tiff_first_ifd_offset_validation_preserves_valid_offsets():
    classic = bytes.fromhex("49492A00") + (8).to_bytes(4, "little")
    big = bytes.fromhex("49492B0008000000") + (16).to_bytes(8, "little")

    assert validate_tiff_first_ifd_offset(classic, "TIFF classic (little-endian)") == "TIFF classic (little-endian)"
    assert validate_tiff_first_ifd_offset(big, "BigTIFF (little-endian)") == "BigTIFF (little-endian)"


def test_scan_does_not_verify_tiff_with_invalid_first_ifd_offset(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "classic.tif").write_bytes(bytes.fromhex("49492A00") + (6).to_bytes(4, "little") + b"\x00" * 32)
    (source / "large.tiff").write_bytes(bytes.fromhex("49492B0008000000") + (20).to_bytes(8, "little") + b"\x00" * 32)
    output = tmp_path / "report"

    assert scan(source, output) == 2
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        rows = {row["path"]: row for row in csv.DictReader(handle)}

    assert rows["classic.tif"]["container_type"] == "Invalid TIFF first IFD offset"
    assert rows["large.tiff"]["container_type"] == "Invalid BigTIFF first IFD offset"
    for row in rows.values():
        assert row["signature_status"] == "unverified: expected TIFF structure"
        assert row["confidence"] == "LOW"
        assert row["recommended_action"] == "REVIEW_CONTAINER"
