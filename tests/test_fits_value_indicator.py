import csv
from pathlib import Path

from labvault_scout.cli import scan
from labvault_scout.fits_validation import validate_fits_mandatory_value_indicators


def _value_card(keyword: bytes, value: bytes, indicator: bytes = b"= ") -> bytes:
    card = bytearray(b" " * 80)
    card[:8] = keyword.ljust(8, b" ")
    card[8:10] = indicator
    card[30 - len(value):30] = value
    return bytes(card)


def _primary_header(bitpix_indicator: bytes = b"= ", naxis_indicator: bytes = b"= ") -> bytes:
    header = (
        _value_card(b"SIMPLE", b"T")
        + _value_card(b"BITPIX", b"16", bitpix_indicator)
        + _value_card(b"NAXIS", b"0", naxis_indicator)
        + b"END".ljust(80, b" ")
    )
    return header + b" " * (2880 - len(header))


def test_fits_mandatory_value_indicator_validation_preserves_valid_header():
    status = "FITS primary HDU (SIMPLE=T)"
    assert validate_fits_mandatory_value_indicators(_primary_header(), status) == status


def test_scan_does_not_verify_fits_with_invalid_mandatory_value_indicators(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "bad-bitpix.fits").write_bytes(_primary_header(bitpix_indicator=b"XX"))
    (source / "bad-naxis.fits").write_bytes(_primary_header(naxis_indicator=b"XX"))
    output = tmp_path / "report"

    assert scan(source, output) == 2
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        rows = {row["path"]: row for row in csv.DictReader(handle)}

    assert rows["bad-bitpix.fits"]["container_type"] == "Invalid FITS BITPIX value indicator"
    assert rows["bad-naxis.fits"]["container_type"] == "Invalid FITS NAXIS value indicator"
    for row in rows.values():
        assert row["signature_status"] == "unverified: expected FITS structure"
        assert row["confidence"] == "LOW"
        assert row["recommended_action"] == "REVIEW_CONTAINER"
