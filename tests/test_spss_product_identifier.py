import csv
from pathlib import Path

from labvault_scout.cli import scan
from labvault_scout.spss_validation import validate_spss_product_identifier


def _spss_header(magic: bytes, product: bytes = b"@(#) SPSS DATA FILE synthetic") -> bytes:
    header = bytearray(176)
    header[:4] = magic
    header[4:4 + len(product)] = product
    header[64:68] = (2).to_bytes(4, "little", signed=True)
    header[68:72] = (1).to_bytes(4, "little", signed=True)
    header[72:76] = (2 if magic == b"$FL3" else 0).to_bytes(4, "little", signed=True)
    header[76:80] = (0).to_bytes(4, "little", signed=True)
    header[80:84] = (1).to_bytes(4, "little", signed=True)
    return bytes(header)


def test_spss_product_identifier_validation_preserves_valid_headers():
    assert validate_spss_product_identifier(
        _spss_header(b"$FL2"), "SPSS SAV $FL2 fixed header (little-endian)"
    ) == "SPSS SAV $FL2 fixed header (little-endian)"
    assert validate_spss_product_identifier(
        _spss_header(b"$FL3"), "SPSS ZSAV $FL3 fixed header (little-endian)"
    ) == "SPSS ZSAV $FL3 fixed header (little-endian)"


def test_spss_product_identifier_validation_rejects_missing_prefix():
    assert validate_spss_product_identifier(
        _spss_header(b"$FL2", b"not an SPSS product identifier"),
        "SPSS SAV $FL2 fixed header (little-endian)",
    ) == "Invalid SPSS product identifier"


def test_scan_does_not_verify_spss_without_product_identifier(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "bad.sav").write_bytes(_spss_header(b"$FL2", b"not an SPSS product identifier"))
    (source / "bad.zsav").write_bytes(_spss_header(b"$FL3", b"not an SPSS product identifier"))
    output = tmp_path / "report"

    assert scan(source, output) == 2
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        rows = {row["path"]: row for row in csv.DictReader(handle)}

    assert rows["bad.sav"]["container_type"] == "Invalid SPSS product identifier"
    assert rows["bad.zsav"]["container_type"] == "Invalid SPSS product identifier"
    assert rows["bad.sav"]["signature_status"] == "unverified: expected SPSS $FL2 fixed header"
    assert rows["bad.zsav"]["signature_status"] == "unverified: expected SPSS $FL3 fixed header"
    for row in rows.values():
        assert row["signature"] == "SPSS"
        assert row["confidence"] == "LOW"
        assert row["recommended_action"] == "REVIEW_CONTAINER"
