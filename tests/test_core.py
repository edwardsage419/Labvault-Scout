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


def test_migration_plan_is_actionable_and_sorted(tmp_path: Path):
    import csv

    source = tmp_path / "migration_source"
    source.mkdir()
    (source / "urgent.jnb").write_bytes(b"urgent")
    (source / "protected.jnb").write_bytes(b"protected")
    (source / "protected.csv").write_text("protected")
    (source / "safe.csv").write_text("safe")

    output = tmp_path / "migration_report"
    scan(source, output)

    with (output / "migration_plan.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    assert rows
    scores = [int(row["priority_score"]) for row in rows]
    assert scores == sorted(scores, reverse=True)
    assert rows[0]["path"] == "urgent.jnb"
    assert "safe.csv" not in {row["path"] for row in rows}


def test_output_directory_inside_source_is_excluded(tmp_path: Path):
    source = tmp_path / "research"
    source.mkdir()
    (source / "data.csv").write_text("x")
    output = source / "labvault-report"

    assert scan(source, output) == 1
    assert (output / "files.csv").exists()

    assert scan(source, output) == 1


def test_empty_directory_scan(tmp_path: Path):
    source = tmp_path / "empty"
    source.mkdir()
    output = tmp_path / "empty-report"
    assert scan(source, output) == 0
    assert (output / "report.html").exists()
    assert (output / "migration_plan.csv").exists()


def test_scanner_skips_symlinked_files(tmp_path: Path):
    source = tmp_path / "links"
    source.mkdir()
    target = source / "target.csv"
    target.write_text("x")
    link = source / "link.csv"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        return
    files = list(iter_files(source))
    assert target in files
    assert link not in files


def test_derivative_suffix_open_copy_family():
    from labvault_scout.relationships import detect_open_copies

    rows = [
        {"path": "run/experiment.jnb", "risk": "RESCUE"},
        {"path": "run/experiment_export.csv", "risk": "SAFE"},
        {"path": "run/experiment_notes.csv", "risk": "SAFE"},
    ]
    detect_open_copies(rows)
    assert rows[0]["open_copy"] == "run/experiment_export.csv"
    assert rows[0]["relationship_evidence"] == "same-directory derivative-suffix open copy"
    assert rows[0]["relationship_strength"] == "DERIVATIVE"


def test_family_detection_remains_same_directory_only():
    from labvault_scout.relationships import detect_open_copies

    rows = [
        {"path": "a/experiment.jnb", "risk": "RESCUE"},
        {"path": "b/experiment_export.csv", "risk": "SAFE"},
    ]
    detect_open_copies(rows)
    assert rows[0]["open_copy"] == ""
    assert rows[0]["relationship_evidence"] == ""
    assert rows[0]["relationship_strength"] == ""


def test_exact_open_copy_has_stronger_relationship():
    from labvault_scout.relationships import detect_open_copies

    rows = [
        {"path": "run/experiment.jnb", "risk": "RESCUE"},
        {"path": "run/experiment.csv", "risk": "SAFE"},
    ]
    detect_open_copies(rows)
    assert rows[0]["relationship_strength"] == "EXACT"
    assert rows[0]["relationship_evidence"] == "same-directory same-stem open copy"


def test_priority_distinguishes_relationship_strength():
    from labvault_scout.priority import assign_priority

    exact = {
        "risk": "RESCUE", "open_copy": "experiment.csv",
        "relationship_strength": "EXACT", "signature_status": "", "confidence": "MEDIUM",
    }
    derivative = {
        "risk": "RESCUE", "open_copy": "experiment_export.csv",
        "relationship_strength": "DERIVATIVE", "signature_status": "", "confidence": "MEDIUM",
    }
    none = {
        "risk": "RESCUE", "open_copy": "",
        "relationship_strength": "", "signature_status": "", "confidence": "MEDIUM",
    }

    exact_score = assign_priority(exact)[0]
    derivative_score = assign_priority(derivative)[0]
    none_score = assign_priority(none)[0]

    assert exact_score < derivative_score < none_score
    assert exact_score == 55
    assert derivative_score == 65
    assert none_score == 80


def test_priority_reason_is_machine_readable():
    from labvault_scout.priority import priority_reason

    row = {
        "risk": "RESCUE",
        "open_copy": "experiment_export.csv",
        "relationship_strength": "DERIVATIVE",
        "signature_status": "unverified: expected ZIP",
        "confidence": "LOW",
    }
    reason = priority_reason(row)
    assert reason == "base=80;open_copy=-15:DERIVATIVE;signature=+10;low_confidence=+5"


def test_recommended_actions_are_conservative():
    from labvault_scout.actions import recommended_action

    assert recommended_action({"risk": "RESCUE", "priority": "HIGH", "open_copy": "", "relationship_strength": ""}) == "EXPORT_OPEN_FORMAT"
    assert recommended_action({"risk": "RESCUE", "priority": "MEDIUM", "open_copy": "x.csv", "relationship_strength": "EXACT"}) == "VERIFY_OPEN_COPY"
    assert recommended_action({"risk": "RESCUE", "priority": "MEDIUM", "open_copy": "x_export.csv", "relationship_strength": "DERIVATIVE"}) == "VERIFY_DERIVATIVE_EXPORT"
    assert recommended_action({"risk": "WATCH", "priority": "MEDIUM", "open_copy": "", "relationship_strength": ""}) == "REVIEW_FORMAT"
    assert recommended_action({"risk": "SAFE", "priority": "LOW", "open_copy": "", "relationship_strength": ""}) == "KEEP"


def test_zip_container_identifies_open_document_spreadsheet(tmp_path: Path):
    import zipfile
    from labvault_scout.identifier import inspect_zip_container

    path = tmp_path / "data.ods"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
        archive.writestr("content.xml", "<office:document-content/>")

    assert inspect_zip_container(path) == "OpenDocument Spreadsheet"


def test_hdf5_superblock_evidence(tmp_path: Path):
    from labvault_scout.identifier import inspect_hdf5_container

    path = tmp_path / "data.h5"
    path.write_bytes(bytes.fromhex("894844460D0A1A0A") + bytes([2]) + b"\x00" * 7)
    assert inspect_hdf5_container(path) == "HDF5 superblock v2"


def test_hdf5_unknown_superblock_version(tmp_path: Path):
    from labvault_scout.identifier import inspect_hdf5_container

    path = tmp_path / "odd.h5"
    path.write_bytes(bytes.fromhex("894844460D0A1A0A") + bytes([9]) + b"\x00" * 7)
    assert inspect_hdf5_container(path) == "Unknown HDF5 superblock version 9"


def test_scan_reports_hdf5_superblock(tmp_path: Path):
    import csv

    source = tmp_path / "hdf5_source"
    source.mkdir()
    path = source / "data.h5"
    path.write_bytes(bytes.fromhex("894844460D0A1A0A") + bytes([2]) + b"\x00" * 7)

    output = tmp_path / "hdf5_report"
    scan(source, output)
    with (output / "files.csv").open(encoding="utf-8-sig") as f:
        row = next(csv.DictReader(f))

    assert row["signature"] == "HDF5"
    assert row["signature_status"] == "verified"
    assert row["container_type"] == "HDF5 superblock v2"
    assert row["confidence"] == "HIGH"


def test_zip_container_identifies_ro_crate(tmp_path: Path):
    import zipfile
    from labvault_scout.identifier import inspect_zip_container

    path = tmp_path / "research.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ro-crate-metadata.json", "{}")
        archive.writestr("data/results.csv", "x,y\n1,2\n")
    assert inspect_zip_container(path) == "RO-Crate Research Object"


def test_zip_container_identifies_bagit_package(tmp_path: Path):
    import zipfile
    from labvault_scout.identifier import inspect_zip_container

    path = tmp_path / "archive.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("bagit.txt", "BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n")
        archive.writestr("bag-info.txt", "Source-Organization: Lab\n")
        archive.writestr("data/results.csv", "x,y\n1,2\n")
    assert inspect_zip_container(path) == "BagIt Research Package"


def test_preservation_package_is_positive_but_bounded_evidence():
    from labvault_scout.priority import assign_priority, priority_reason

    plain = {"risk": "UNKNOWN", "open_copy": "", "container_type": "", "signature_status": "", "confidence": "MEDIUM"}
    crate = {"risk": "UNKNOWN", "open_copy": "", "container_type": "RO-Crate Research Object", "signature_status": "", "confidence": "MEDIUM"}
    bag = {"risk": "UNKNOWN", "open_copy": "", "container_type": "BagIt Research Package", "signature_status": "", "confidence": "MEDIUM"}

    assert assign_priority(plain)[0] == 50
    assert assign_priority(crate)[0] == 40
    assert assign_priority(bag)[0] == 40
    assert priority_reason(crate) == "base=50;preservation_package=-10"


def test_signature_from_head_matches_file_inspection(tmp_path: Path):
    from labvault_scout.identifier import inspect_signature, signature_from_head

    samples = [
        ("a.zip", bytes.fromhex("504B0304") + b"1234"),
        ("a.h5", bytes.fromhex("894844460D0A1A0A")),
        ("a.pdf", b"%PDF-1.7"),
    ]
    for name, content in samples:
        path = tmp_path / name
        path.write_bytes(content)
        assert signature_from_head(content[:8]) == inspect_signature(path)


def test_scanner_handles_large_flat_directory(tmp_path: Path):
    from labvault_scout.scanner import iter_files

    source = tmp_path / "large"
    source.mkdir()
    for index in range(1000):
        (source / f"sample_{index:04d}.csv").write_text("x,y\n1,2\n", encoding="utf-8")

    paths = list(iter_files(source))
    assert len(paths) == 1000
    assert len({p.name for p in paths}) == 1000


def test_header_helpers_match_file_helpers(tmp_path: Path):
    from labvault_scout.identifier import (
        hdf5_container_from_header, inspect_hdf5_container,
        inspect_ole_container, ole_container_from_header,
    )

    hdf = tmp_path / "data.h5"
    hdf.write_bytes(bytes.fromhex("894844460D0A1A0A") + bytes([2]) + b"\x00" * 503)
    header = hdf.read_bytes()[:512]
    assert hdf5_container_from_header(header) == inspect_hdf5_container(hdf)

    ole = tmp_path / "data.xls"
    ole_header = bytearray(512)
    ole_header[:8] = bytes.fromhex("D0CF11E0A1B11AE1")
    ole_header[28:30] = (0xFFFE).to_bytes(2, "little")
    ole_header[30:32] = (9).to_bytes(2, "little")
    ole.write_bytes(ole_header)
    assert ole_container_from_header(bytes(ole_header), 512) == inspect_ole_container(ole)


def test_hash_and_header_are_collected_in_one_pass(tmp_path: Path):
    import hashlib
    from labvault_scout.hashing import sha256_with_head

    content = bytes(range(256)) * 5000
    path = tmp_path / "large.bin"
    path.write_bytes(content)

    digest, head = sha256_with_head(path)
    assert digest == hashlib.sha256(content).hexdigest()
    assert head == content[:512]


def test_hash_and_header_handles_small_files(tmp_path: Path):
    import hashlib
    from labvault_scout.hashing import sha256_with_head

    content = b"small"
    path = tmp_path / "small.bin"
    path.write_bytes(content)

    digest, head = sha256_with_head(path)
    assert digest == hashlib.sha256(content).hexdigest()
    assert head == content


def test_sha256_file_compatibility_after_one_pass_refactor(tmp_path: Path):
    import hashlib
    from labvault_scout.hashing import sha256_file

    content = b"compatibility" * 1000
    path = tmp_path / "compat.bin"
    path.write_bytes(content)
    assert sha256_file(path) == hashlib.sha256(content).hexdigest()


def test_scan_zero_byte_file_has_known_sha256(tmp_path: Path):
    import csv

    source = tmp_path / "zero_source"
    source.mkdir()
    (source / "empty.bin").write_bytes(b"")
    output = tmp_path / "zero_report"

    scan(source, output)
    with (output / "files.csv").open(encoding="utf-8-sig") as f:
        row = next(csv.DictReader(f))

    assert row["size"] == "0"
    assert row["sha256"] == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert row["signature"] == ""


def test_scan_truncated_hdf5_reports_container_problem(tmp_path: Path):
    import csv

    source = tmp_path / "truncated_source"
    source.mkdir()
    (source / "broken.h5").write_bytes(bytes.fromhex("894844460D0A1A0A"))
    output = tmp_path / "truncated_report"

    scan(source, output)
    with (output / "files.csv").open(encoding="utf-8-sig") as f:
        row = next(csv.DictReader(f))

    assert row["signature"] == "HDF5"
    assert row["signature_status"] == "verified"
    assert row["container_type"] == "Truncated HDF5 container"


def test_scan_invalid_zip_is_nonfatal_and_evidenced(tmp_path: Path):
    import csv

    source = tmp_path / "zip_source"
    source.mkdir()
    (source / "broken.zip").write_bytes(bytes.fromhex("504B0304") + b"not-a-real-zip")
    output = tmp_path / "zip_report"

    scan(source, output)
    with (output / "files.csv").open(encoding="utf-8-sig") as f:
        row = next(csv.DictReader(f))

    assert row["signature"] == "ZIP"
    assert row["signature_status"] == "verified"
    assert row["container_type"] == "Invalid ZIP container"


def test_scan_zero_byte_file_is_reported(tmp_path: Path):
    import csv

    source = tmp_path / "empty_source"
    source.mkdir()
    (source / "empty.bin").write_bytes(b"")
    output = tmp_path / "empty_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as f:
        row = next(csv.DictReader(f))
    assert row["size"] == "0"
    assert row["signature"] == ""
    assert len(row["sha256"]) == 64


def test_scan_truncated_hdf5_is_nonfatal(tmp_path: Path):
    import csv

    source = tmp_path / "truncated_source"
    source.mkdir()
    (source / "broken.h5").write_bytes(bytes.fromhex("894844460D0A1A0A"))
    output = tmp_path / "truncated_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as f:
        row = next(csv.DictReader(f))
    assert row["signature"] == "HDF5"
    assert row["container_type"] == "Truncated HDF5 container"


def test_output_inside_source_is_excluded(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = source / "labvault-report"

    assert scan(source, output) == 1
    assert (output / "files.csv").exists()


def test_corrupt_zip_is_reported_without_crashing(tmp_path: Path):
    import csv

    source = tmp_path / "bad_zip_source"
    source.mkdir()
    (source / "broken.zip").write_bytes(bytes.fromhex("504B0304") + b"not-a-valid-zip")
    output = tmp_path / "bad_zip_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as f:
        row = next(csv.DictReader(f))
    assert row["signature"] == "ZIP"
    assert row["signature_status"] == "verified"
    assert row["container_type"] == "Invalid ZIP container"


def test_disguised_extension_reports_signature_mismatch(tmp_path: Path):
    import csv

    source = tmp_path / "mismatch_source"
    source.mkdir()
    (source / "fake.pdf").write_bytes(bytes.fromhex("504B0304") + b"not-a-valid-zip")
    output = tmp_path / "mismatch_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as f:
        row = next(csv.DictReader(f))
    assert row["signature"] == "ZIP"
    assert row["signature_status"] == "mismatch: expected PDF, detected ZIP"
    assert row["confidence"] == "LOW"


def test_duplicate_grouping_uses_content_hash(tmp_path: Path):
    import csv

    source = tmp_path / "duplicates_source"
    source.mkdir()
    content = b"x,y\n1,2\n"
    (source / "first.csv").write_bytes(content)
    (source / "second.txt").write_bytes(content)
    (source / "different.csv").write_bytes(b"x,y\n3,4\n")
    output = tmp_path / "duplicates_report"

    assert scan(source, output) == 3
    with (output / "duplicates.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert {row["path"] for row in rows} == {"first.csv", "second.txt"}
    assert len({row["group"] for row in rows}) == 1
    assert len({row["sha256"] for row in rows}) == 1


def test_similar_names_do_not_create_derivative_relationship():
    from labvault_scout.relationships import detect_open_copies

    rows = [
        {"path": "run/experiment.jnb", "risk": "RESCUE"},
        {"path": "run/experiment_notes.csv", "risk": "SAFE"},
        {"path": "run/experiment_export_notes.csv", "risk": "SAFE"},
    ]
    detect_open_copies(rows)
    assert rows[0]["open_copy"] == ""
    assert rows[0]["relationship_strength"] == ""


def test_csv_and_json_share_core_scan_values(tmp_path: Path):
    import csv
    import json

    source = tmp_path / "consistency_source"
    source.mkdir()
    (source / "data.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    output = tmp_path / "consistency_report"
    scan(source, output)

    with (output / "files.csv").open(encoding="utf-8-sig") as f:
        csv_row = next(csv.DictReader(f))
    json_row = json.loads((output / "scan.json").read_text(encoding="utf-8"))["files"][0]

    for key in ("path", "sha256", "format", "risk", "confidence", "priority", "priority_reason", "recommended_action"):
        assert csv_row[key] == str(json_row[key])


def test_structural_container_warning_increases_priority():
    from labvault_scout.priority import assign_priority, priority_reason

    row = {
        "risk": "UNKNOWN",
        "container_type": "Invalid ZIP container",
        "signature_status": "verified",
        "confidence": "HIGH",
        "open_copy": "",
    }
    score, label = assign_priority(row)
    assert score == 60
    assert label == "MEDIUM"
    assert priority_reason(row) == "base=50;container=+10"


def test_truncated_container_recommends_review():
    from labvault_scout.actions import recommended_action

    row = {
        "risk": "RESCUE",
        "container_type": "Truncated HDF5 container",
        "priority": "HIGH",
        "open_copy": "",
    }
    assert recommended_action(row) == "REVIEW_CONTAINER"


def test_runtime_version_matches_installed_metadata():
    from importlib.metadata import version
    import labvault_scout

    assert labvault_scout.__version__ == version("labvault-scout")


def test_scan_error_paths_are_relative(tmp_path: Path, monkeypatch):
    import json
    import labvault_scout.cli as cli

    source = tmp_path / "error_source"
    nested = source / "nested"
    nested.mkdir(parents=True)
    (nested / "broken.bin").write_bytes(b"data")
    output = tmp_path / "error_report"

    def fail_hash(path):
        raise OSError("simulated read failure")

    monkeypatch.setattr(cli, "sha256_with_head", fail_hash)
    assert cli.scan(source, output) == 0

    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert payload["errors"] == [{"path": str(Path("nested") / "broken.bin"), "error": "OSError"}]
    assert str(source) not in payload["errors"][0]["path"]


def test_hdf5_user_block_is_detected_end_to_end(tmp_path: Path):
    import csv
    from labvault_scout.cli import scan

    source = tmp_path / "hdf5_userblock_source"
    source.mkdir()
    content = b"U" * 512 + bytes.fromhex("894844460D0A1A0A") + bytes([2]) + b"\x00" * 32
    (source / "with_userblock.h5").write_bytes(content)
    output = tmp_path / "hdf5_userblock_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["signature"] == "HDF5"
    assert row["signature_status"] == "verified"
    assert row["container_type"] == "HDF5 superblock v2"


def test_case_distinct_directories_do_not_form_relationship():
    from labvault_scout.relationships import detect_open_copies

    rows = [
        {"path": "Run/experiment.jnb", "risk": "RESCUE"},
        {"path": "run/experiment_export.csv", "risk": "SAFE"},
    ]
    detect_open_copies(rows)
    assert rows[0]["open_copy"] == ""
    assert rows[0]["relationship_strength"] == ""


def test_scanner_skips_fifo_entries_when_supported(tmp_path: Path):
    import os
    import pytest
    from labvault_scout.scanner import iter_files

    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO creation is not supported on this platform")

    source = tmp_path / "special_entries"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    fifo = source / "named_pipe"
    os.mkfifo(fifo)

    paths = list(iter_files(source))
    assert [path.name for path in paths] == ["data.csv"]


def test_output_ancestor_does_not_exclude_scan_root(tmp_path: Path):
    from labvault_scout.cli import scan

    source = tmp_path / "ancestor_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")

    assert scan(source, tmp_path) == 1


def test_output_equal_to_scan_root_is_rejected(tmp_path: Path):
    import pytest
    from labvault_scout.cli import scan

    source = tmp_path / "same_root"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must not be the scan root"):
        scan(source, source)


def test_xlsx_requires_excel_ooxml_structure_for_verification(tmp_path: Path):
    import csv
    import zipfile
    from labvault_scout.cli import scan

    source = tmp_path / "xlsx_structure_source"
    source.mkdir()
    fake = source / "fake.xlsx"
    with zipfile.ZipFile(fake, "w") as archive:
        archive.writestr("notes.txt", "not an Excel workbook")

    output = tmp_path / "xlsx_structure_report"
    assert scan(source, output) == 1

    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["signature"] == "ZIP"
    assert row["container_type"] == "ZIP archive"
    assert row["signature_status"] == "unverified: expected OOXML Excel structure"
    assert row["confidence"] == "LOW"


def test_xlsx_with_excel_ooxml_structure_is_verified(tmp_path: Path):
    import csv
    import zipfile
    from labvault_scout.cli import scan

    source = tmp_path / "xlsx_valid_source"
    source.mkdir()
    book = source / "book.xlsx"
    with zipfile.ZipFile(book, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")

    output = tmp_path / "xlsx_valid_report"
    assert scan(source, output) == 1

    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["container_type"] == "OOXML Excel"
    assert row["signature_status"] == "verified"
    assert row["confidence"] == "HIGH"
