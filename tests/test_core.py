import csv
import json
from pathlib import Path

from labvault_scout.cli import scan
from labvault_scout.hashing import sha256_file
from labvault_scout.report import duplicate_groups
from labvault_scout.risk import classify, load_rules
from labvault_scout.scanner import iter_files


def test_core(tmp_path: Path):
    f = tmp_path / "result.jnb"
    f.write_bytes(b"labvault")
    assert list(iter_files(tmp_path)) == [f]
    assert len(sha256_file(f)) == 64
    assert classify(f, load_rules())["risk"] == "RESCUE"


def test_unknown(tmp_path: Path):
    f = tmp_path / "sample.xyzunknown"
    f.write_text("x")
    assert classify(f, load_rules())["risk"] == "UNKNOWN"


def test_duplicate_groups():
    rows = [
        {"path": "a.csv", "size": 1, "sha256": "same"},
        {"path": "b.csv", "size": 1, "sha256": "same"},
        {"path": "c.csv", "size": 1, "sha256": "other"},
    ]
    result = duplicate_groups(rows)
    assert len(result) == 2
    assert {x["path"] for x in result} == {"a.csv", "b.csv"}


def test_end_to_end_reports(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.csv").write_text("x")
    (source / "copy.csv").write_text("x")
    (source / "project.jnb").write_bytes(b"jnb")
    output = tmp_path / "report"
    assert scan(source, output) == 3
    for name in ("report.html", "files.csv", "scan.json", "duplicates.csv"):
        assert (output / name).exists()
    payload = json.loads((output / "scan.json").read_text())
    assert len(payload["files"]) == 3
    with (output / "duplicates.csv").open(encoding="utf-8-sig") as f:
        assert len(list(csv.DictReader(f))) == 2


def test_open_copy_detection(tmp_path: Path):
    from labvault_scout.relationships import detect_open_copies
    rows = [
        {"path": "experiment.jnb", "risk": "RESCUE"},
        {"path": "experiment.csv", "risk": "SAFE"},
        {"path": "other.jnb", "risk": "RESCUE"},
    ]
    detect_open_copies(rows)
    assert rows[0]["open_copy"] == "experiment.csv"
    assert rows[1]["open_copy"] == ""
    assert rows[2]["open_copy"] == ""


def test_open_copy_requires_same_directory():
    from labvault_scout.relationships import detect_open_copies
    rows = [
        {"path": "a/experiment.jnb", "risk": "RESCUE"},
        {"path": "b/experiment.csv", "risk": "SAFE"},
    ]
    detect_open_copies(rows)
    assert rows[0]["open_copy"] == ""


def test_signature_detection(tmp_path: Path):
    from labvault_scout.identifier import extension_signature_status, inspect_signature
    z = tmp_path / "book.xlsx"
    z.write_bytes(b"PK\\x03\\x04" + b"x" * 8)
    assert inspect_signature(z) == "ZIP"
    assert extension_signature_status(z, "ZIP") == "verified"

    bad = tmp_path / "fake.pdf"
    bad.write_bytes(b"PK\\x03\\x04" + b"x" * 8)
    assert inspect_signature(bad) == "ZIP"
    assert "mismatch" in extension_signature_status(bad, "ZIP")


def test_hdf5_signature(tmp_path: Path):
    from labvault_scout.identifier import inspect_signature
    f = tmp_path / "data.h5"
    f.write_bytes(bytes.fromhex("894844460D0A1A0A") + b"x")
    assert inspect_signature(f) == "HDF5"
