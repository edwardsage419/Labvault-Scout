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
    z.write_bytes(bytes.fromhex("504B0304") + b"x" * 8)
    assert inspect_signature(z) == "ZIP"
    assert extension_signature_status(z, "ZIP") == "verified"

    bad = tmp_path / "fake.pdf"
    bad.write_bytes(bytes.fromhex("504B0304") + b"x" * 8)
    assert inspect_signature(bad) == "ZIP"
    assert "mismatch" in extension_signature_status(bad, "ZIP")


def test_hdf5_signature(tmp_path: Path):
    from labvault_scout.identifier import inspect_signature
    f = tmp_path / "data.h5"
    f.write_bytes(bytes.fromhex("894844460D0A1A0A") + b"x")
    assert inspect_signature(f) == "HDF5"


def test_zip_container_inspection(tmp_path: Path):
    import zipfile
    from labvault_scout.identifier import inspect_zip_container

    xlsx = tmp_path / "book.xlsx"
    with zipfile.ZipFile(xlsx, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", "<workbook/>")
    assert inspect_zip_container(xlsx) == "OOXML Excel"

    generic = tmp_path / "archive.zip"
    with zipfile.ZipFile(generic, "w") as z:
        z.writestr("data.txt", "x")
    assert inspect_zip_container(generic) == "ZIP archive"


def test_end_to_end_container_report(tmp_path: Path):
    import csv
    import zipfile
    source = tmp_path / "source_container"
    source.mkdir()
    xlsx = source / "book.xlsx"
    with zipfile.ZipFile(xlsx, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", "<workbook/>")
    output = tmp_path / "container_report"
    scan(source, output)
    with (output / "files.csv").open(encoding="utf-8-sig") as f:
        row = next(csv.DictReader(f))
    assert row["signature"] == "ZIP"
    assert row["signature_status"] == "verified"
    assert row["container_type"] == "OOXML Excel"


def test_ole_container_header_validation(tmp_path: Path):
    from labvault_scout.identifier import inspect_ole_container
    ole = tmp_path / "legacy.xls"
    header = bytearray(512)
    header[:8] = bytes.fromhex("D0CF11E0A1B11AE1")
    header[28:30] = (0xFFFE).to_bytes(2, "little")
    header[30:32] = (9).to_bytes(2, "little")
    ole.write_bytes(header)
    assert inspect_ole_container(ole) == "OLE Compound File (512-byte sectors)"

    short = tmp_path / "short.xls"
    short.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1"))
    assert inspect_ole_container(short) == "Truncated OLE container"


def test_evidence_confidence():
    from labvault_scout.evidence import build_evidence

    evidence, confidence = build_evidence({
        "format": "Excel Workbook",
        "signature": "ZIP",
        "signature_status": "verified",
        "container_type": "OOXML Excel",
        "open_copy": "",
    })
    assert confidence == "HIGH"
    assert "OOXML Excel" in evidence

    evidence, confidence = build_evidence({
        "format": "PDF",
        "signature": "ZIP",
        "signature_status": "mismatch: expected PDF, detected ZIP",
        "container_type": "ZIP archive",
        "open_copy": "",
    })
    assert confidence == "LOW"
    assert "mismatch" in evidence


def test_scan_evidence_end_to_end(tmp_path: Path):
    import csv
    import zipfile

    source = tmp_path / "evidence_source"
    source.mkdir()
    xlsx = source / "book.xlsx"
    with zipfile.ZipFile(xlsx, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", "<workbook/>")

    output = tmp_path / "evidence_report"
    scan(source, output)
    with (output / "files.csv").open(encoding="utf-8-sig") as f:
        row = next(csv.DictReader(f))

    assert row["confidence"] == "HIGH"
    assert "extension rule: Excel Workbook" in row["evidence"]
    assert "signature: ZIP" in row["evidence"]
    assert "container: OOXML Excel" in row["evidence"]


def test_priority_prefers_rescue_without_open_copy():
    from labvault_scout.priority import assign_priority

    exposed = {"risk": "RESCUE", "open_copy": "", "signature_status": "", "confidence": "MEDIUM"}
    protected = {"risk": "RESCUE", "open_copy": "data.csv", "signature_status": "", "confidence": "MEDIUM"}

    exposed_score, exposed_label = assign_priority(exposed)
    protected_score, protected_label = assign_priority(protected)

    assert exposed_score > protected_score
    assert exposed_label == "HIGH"
    assert protected_label == "MEDIUM"


def test_priority_penalizes_signature_mismatch():
    from labvault_scout.priority import assign_priority

    normal = {"risk": "WATCH", "open_copy": "", "signature_status": "verified", "confidence": "HIGH"}
    mismatch = {"risk": "WATCH", "open_copy": "", "signature_status": "mismatch: expected PDF, detected ZIP", "confidence": "LOW"}

    assert assign_priority(mismatch)[0] > assign_priority(normal)[0]
