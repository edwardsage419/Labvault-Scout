import csv
import json
from pathlib import Path

from labvault_scout.cli import scan
from labvault_scout.hashing import sha256_file
from labvault_scout.report import duplicate_groups
from labvault_scout.risk import classify, load_rules
from labvault_scout.scanner import iter_files


def test_atomic_text_writer_replaces_symlink_without_modifying_target(tmp_path: Path):
    import os
    import pytest
    from labvault_scout.safeio import atomic_write_text

    if not hasattr(os, "symlink"):
        pytest.skip("symlinks are unavailable")

    target = tmp_path / "source.txt"
    target.write_text("source", encoding="utf-8")
    output = tmp_path / "report.txt"
    try:
        os.symlink(target, output)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    atomic_write_text(output, "report", encoding="utf-8")

    assert target.read_text(encoding="utf-8") == "source"
    assert output.is_symlink() is False
    assert output.read_text(encoding="utf-8") == "report"


def test_atomic_text_writer_replaces_hardlink_without_modifying_target(tmp_path: Path):
    import os
    import pytest
    from labvault_scout.safeio import atomic_write_text

    if not hasattr(os, "link"):
        pytest.skip("hard links are unavailable")

    target = tmp_path / "source.txt"
    target.write_text("source", encoding="utf-8")
    output = tmp_path / "report.txt"
    try:
        os.link(target, output)
    except OSError:
        pytest.skip("hard-link creation is unavailable")

    atomic_write_text(output, "report", encoding="utf-8")

    assert target.read_text(encoding="utf-8") == "source"
    assert output.read_text(encoding="utf-8") == "report"
    assert os.stat(target).st_ino != os.stat(output).st_ino or os.name == "nt"


def test_atomic_text_writer_cleans_temporary_file_on_failure(tmp_path: Path):
    import pytest
    from labvault_scout.safeio import atomic_text_writer

    output = tmp_path / "report.txt"
    with pytest.raises(RuntimeError, match="stop"):
        with atomic_text_writer(output) as handle:
            handle.write("partial")
            raise RuntimeError("stop")

    assert not output.exists()
    assert list(tmp_path.glob(".report.txt.*.tmp")) == []


def test_core(tmp_path: Path):
    f = tmp_path / "result.jnb"
    f.write_bytes(b"labvault")
    assert list(iter_files(tmp_path)) == [f]
    assert len(sha256_file(f)) == 64
    assert classify(f, load_rules())["risk"] == "RESCUE"


def test_packaged_scientific_format_rules_have_valid_structure():
    import re
    from importlib.resources import files

    raw = files("labvault_scout").joinpath("rules/scientific_formats.json").read_text(encoding="utf-8")
    items = json.loads(raw)
    required = {"extension", "name", "category", "risk", "reason", "preferred_exports"}

    assert isinstance(items, list)
    assert items
    for item in items:
        assert isinstance(item, dict)
        assert set(item) == required

        extension = item["extension"]
        assert isinstance(extension, str)
        assert extension == extension.lower()
        assert re.fullmatch(r"\.[a-z0-9]+(?:\.[a-z0-9]+)*", extension)

        assert isinstance(item["name"], str) and item["name"].strip()
        assert isinstance(item["category"], str)
        assert re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", item["category"])
        assert item["risk"] in {"SAFE", "WATCH", "RESCUE"}
        assert isinstance(item["reason"], str) and item["reason"].strip()

        exports = item["preferred_exports"]
        assert isinstance(exports, list)
        assert len(exports) == len(set(exports))
        assert all(isinstance(value, str) and re.fullmatch(r"[a-z0-9]+", value) for value in exports)


def test_rule_index_rejects_duplicate_extensions():
    import pytest
    from labvault_scout.risk import _index_rules

    def rule(extension, name):
        return {
            "extension": extension,
            "name": name,
            "category": "open_data",
            "risk": "SAFE",
            "reason": "test rule",
            "preferred_exports": [],
        }

    items = [rule(".csv", "CSV"), rule(".csv", "Duplicate CSV")]
    with pytest.raises(ValueError, match=r"Duplicate scientific format rule extension: \.csv"):
        _index_rules(items)


def test_rule_index_rejects_malformed_rule_structure():
    import pytest
    from labvault_scout.risk import _index_rules

    valid = {
        "extension": ".csv",
        "name": "CSV",
        "category": "open_data",
        "risk": "SAFE",
        "reason": "test rule",
        "preferred_exports": [],
    }

    cases = []

    missing = dict(valid)
    missing.pop("reason")
    cases.append(missing)

    uppercase_extension = dict(valid)
    uppercase_extension["extension"] = ".CSV"
    cases.append(uppercase_extension)

    invalid_risk = dict(valid)
    invalid_risk["risk"] = "DANGER"
    cases.append(invalid_risk)

    duplicate_export = dict(valid)
    duplicate_export["preferred_exports"] = ["csv", "csv"]
    cases.append(duplicate_export)

    non_string_risk = dict(valid)
    non_string_risk["risk"] = ["SAFE"]
    cases.append(non_string_risk)

    non_string_export = dict(valid)
    non_string_export["preferred_exports"] = [{"format": "csv"}]
    cases.append(non_string_export)

    for item in cases:
        with pytest.raises(ValueError, match="Invalid scientific format rule"):
            _index_rules([item])

    with pytest.raises(ValueError, match="must be a JSON array"):
        _index_rules({"extension": ".csv"})


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
    assert payload["errors"] == [{"path": "nested/broken.bin", "error": "OSError"}]
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


def test_empty_zip_archive_is_recognized(tmp_path: Path):
    import csv
    import zipfile
    from labvault_scout.cli import scan

    source = tmp_path / "empty_zip_source"
    source.mkdir()
    archive_path = source / "empty.zip"
    with zipfile.ZipFile(archive_path, "w"):
        pass

    output = tmp_path / "empty_zip_report"
    assert scan(source, output) == 1

    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["signature"] == "ZIP"
    assert row["signature_status"] == "verified"
    assert row["container_type"] == "ZIP archive"


def test_xls_generic_ole_container_does_not_claim_high_confidence(tmp_path: Path):
    import csv
    from labvault_scout.cli import scan

    source = tmp_path / "ole_confidence_source"
    source.mkdir()
    header = bytearray(512)
    header[:8] = bytes.fromhex("D0CF11E0A1B11AE1")
    header[28:30] = (0xFFFE).to_bytes(2, "little")
    header[30:32] = (9).to_bytes(2, "little")
    (source / "generic.xls").write_bytes(header)

    output = tmp_path / "ole_confidence_report"
    assert scan(source, output) == 1

    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["signature"] == "OLE"
    assert row["container_type"] == "OLE Compound File (512-byte sectors)"
    assert row["signature_status"] == "container-only: OLE"
    assert row["confidence"] == "MEDIUM"


def test_iter_files_forwards_walk_errors(tmp_path: Path, monkeypatch):
    import labvault_scout.scanner as scanner

    source = tmp_path / "walk_error_source"
    source.mkdir()
    seen = []

    def fake_walk(root, followlinks=False, onerror=None):
        exc = PermissionError("blocked")
        exc.filename = str(Path(root) / "blocked")
        assert onerror is not None
        onerror(exc)
        return []

    monkeypatch.setattr(scanner.os, "walk", fake_walk)
    paths = list(scanner.iter_files(source, on_error=lambda path, exc: seen.append((path, exc))))

    assert paths == []
    assert len(seen) == 1
    assert seen[0][0].name == "blocked"
    assert isinstance(seen[0][1], PermissionError)


def test_scan_json_records_directory_traversal_errors(tmp_path: Path, monkeypatch):
    import json
    import labvault_scout.cli as cli

    source = tmp_path / "scan_walk_error_source"
    source.mkdir()
    output = tmp_path / "scan_walk_error_report"

    def fake_iter(root, excluded=None, on_error=None):
        assert on_error is not None
        on_error(Path(root) / "blocked", PermissionError("blocked"))
        return iter(())

    monkeypatch.setattr(cli, "iter_files", fake_iter)
    assert cli.scan(source, output) == 0

    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert payload["errors"] == [{"path": "blocked", "error": "PermissionError"}]


def test_iter_files_reports_file_metadata_errors(tmp_path: Path, monkeypatch):
    import labvault_scout.scanner as scanner

    source = tmp_path / "metadata_error_source"
    source.mkdir()
    blocked = source / "blocked.bin"
    blocked.write_bytes(b"x")
    seen = []

    original_lstat = Path.lstat

    def fake_lstat(self):
        if self.name == "blocked.bin":
            raise PermissionError("blocked metadata")
        return original_lstat(self)

    monkeypatch.setattr(Path, "lstat", fake_lstat)
    paths = list(scanner.iter_files(source, on_error=lambda path, exc: seen.append((path, exc))))

    assert paths == []
    assert len(seen) == 1
    assert seen[0][0].name == "blocked.bin"
    assert isinstance(seen[0][1], PermissionError)


def test_compound_extension_prefers_longest_rule():
    rules = load_rules()
    lower = classify(Path("subject01.nii.gz"), rules)
    upper = classify(Path("SUBJECT01.NII.GZ"), rules)

    assert lower["name"] == "NIfTI (Gzip compressed)"
    assert lower["risk"] == "WATCH"
    assert upper["name"] == "NIfTI (Gzip compressed)"


def test_compound_extension_scan_is_not_unknown(tmp_path: Path):
    source = tmp_path / "compound_source"
    source.mkdir()
    (source / "brain.nii.gz").write_bytes(b"not-a-real-nifti")
    output = tmp_path / "compound_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["format"] == "NIfTI (Gzip compressed)"
    assert row["risk"] == "WATCH"


def test_scan_json_is_self_describing(tmp_path: Path):
    import labvault_scout
    from labvault_scout.report import REPORT_SCHEMA_VERSION

    source = tmp_path / "schema_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "schema_report"

    scan(source, output)
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))

    assert payload["schema_version"] == REPORT_SCHEMA_VERSION
    assert payload["tool"] == {"name": "LabVault Scout", "version": labvault_scout.__version__}
    assert "files" in payload
    assert "errors" in payload


def test_cli_version_reports_runtime_version(monkeypatch, capsys):
    import sys
    import pytest
    import labvault_scout
    from labvault_scout.cli import main

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "--version"])
    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"labvault-scout {labvault_scout.__version__}"


def test_html_report_identifies_tool_and_schema(tmp_path: Path):
    import labvault_scout
    from labvault_scout.report import REPORT_SCHEMA_VERSION

    source = tmp_path / "html_metadata_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "html_metadata_report"

    scan(source, output)
    page = (output / "report.html").read_text(encoding="utf-8")

    assert f"Tool version: {labvault_scout.__version__}" in page
    assert f"Report schema: {REPORT_SCHEMA_VERSION}" in page
    assert "Tool version: $" not in page


def test_scanner_orders_files_deterministically(tmp_path: Path):
    source = tmp_path / "ordered_source"
    source.mkdir()
    for name in ("z.csv", "A.csv", "m.csv", "b.csv"):
        (source / name).write_text("x\n1\n", encoding="utf-8")

    names = [path.name for path in iter_files(source)]
    assert names == sorted(names)


def test_scan_json_summary_is_deterministic_and_actionable(tmp_path: Path):
    source = tmp_path / "summary_source"
    source.mkdir()
    (source / "a.csv").write_text("x\n1\n", encoding="utf-8")
    (source / "b.csv").write_text("x\n1\n", encoding="utf-8")
    (source / "project.jnb").write_bytes(b"project")
    output = tmp_path / "summary_report"

    assert scan(source, output) == 3
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    summary = payload["summary"]

    assert summary["file_count"] == 3
    assert summary["total_bytes"] > 0
    assert summary["error_count"] == 0
    assert summary["risk_counts"] == {"RESCUE": 1, "SAFE": 2}
    assert sum(summary["priority_counts"].values()) == 3
    assert summary["open_copy_count"] == 0
    assert summary["duplicate_group_count"] == 1


def test_nifti1_header_evidence():
    from labvault_scout.identifier import nifti1_container_from_header

    header = bytearray(348)
    header[:4] = (348).to_bytes(4, "little")
    header[344:348] = b"n+1\x00"
    assert nifti1_container_from_header(bytes(header)) == "NIfTI-1 single-file"

    header[344:348] = b"ni1\x00"
    assert nifti1_container_from_header(bytes(header)) == "NIfTI-1 paired-file"


def test_gzip_nifti_is_structurally_verified(tmp_path: Path):
    import gzip

    source = tmp_path / "nifti_source"
    source.mkdir()
    header = bytearray(348)
    header[:4] = (348).to_bytes(4, "little")
    header[344:348] = b"n+1\x00"

    path = source / "brain.nii.gz"
    with gzip.open(path, "wb") as handle:
        handle.write(header)
        handle.write(b"\x00" * 64)

    output = tmp_path / "nifti_report"
    assert scan(source, output) == 1

    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["format"] == "NIfTI (Gzip compressed)"
    assert row["signature"] == "GZIP"
    assert row["container_type"] == "NIfTI-1 single-file"
    assert row["signature_status"] == "verified"
    assert row["confidence"] == "HIGH"


def test_gzip_nifti_with_invalid_header_is_not_verified(tmp_path: Path):
    import gzip

    source = tmp_path / "bad_nifti_source"
    source.mkdir()
    path = source / "broken.nii.gz"
    with gzip.open(path, "wb") as handle:
        handle.write(b"not-nifti")

    output = tmp_path / "bad_nifti_report"
    assert scan(source, output) == 1

    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["signature"] == "GZIP"
    assert row["container_type"] == "Truncated NIfTI-1 header"
    assert row["signature_status"] == "unverified: expected NIfTI-1 structure"
    assert row["confidence"] == "LOW"
    assert row["recommended_action"] == "REVIEW_CONTAINER"


def test_uncompressed_nifti_is_structurally_verified(tmp_path: Path):
    source = tmp_path / "nii_source"
    source.mkdir()
    header = bytearray(348)
    header[:4] = (348).to_bytes(4, "little")
    header[344:348] = b"n+1\x00"
    (source / "brain.nii").write_bytes(header + b"\x00" * 64)

    output = tmp_path / "nii_report"
    assert scan(source, output) == 1

    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["format"] == "NIfTI"
    assert row["signature"] == "NIFTI1"
    assert row["container_type"] == "NIfTI-1 single-file"
    assert row["signature_status"] == "verified"
    assert row["confidence"] == "HIGH"


def test_uncompressed_nifti_invalid_header_is_reviewed(tmp_path: Path):
    source = tmp_path / "bad_nii_source"
    source.mkdir()
    (source / "broken.nii").write_bytes(b"not-nifti")

    output = tmp_path / "bad_nii_report"
    assert scan(source, output) == 1

    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["container_type"] == "Truncated NIfTI-1 header"
    assert row["signature_status"] == "unverified: expected NIFTI1"
    assert row["confidence"] == "LOW"
    assert row["recommended_action"] == "REVIEW_CONTAINER"


def test_compare_reports_tracks_content_assessment_add_remove_and_move(tmp_path: Path):
    from labvault_scout.compare import compare_payloads

    def row(path, digest, risk="SAFE", priority="LOW", score=0, action="KEEP"):
        return {
            "path": path,
            "size": 10,
            "sha256": digest,
            "format": "CSV",
            "signature": "",
            "signature_status": "",
            "container_type": "",
            "risk": risk,
            "confidence": "MEDIUM",
            "priority_score": score,
            "priority": priority,
            "priority_reason": f"base={score}",
            "recommended_action": action,
            "open_copy": "",
            "relationship_strength": "",
            "relationship_evidence": "",
            "evidence": "extension rule: CSV",
            "reason": "test",
        }

    before = {"files": [
        row("same.csv", "same"),
        row("content.csv", "old"),
        row("assessment.csv", "assessment", risk="SAFE", priority="LOW", score=0),
        row("removed.csv", "removed"),
        row("old/name.csv", "moved"),
    ]}
    after = {"files": [
        row("same.csv", "same"),
        row("content.csv", "new"),
        row("assessment.csv", "assessment", risk="WATCH", priority="MEDIUM", score=40, action="REVIEW_FORMAT"),
        row("added.csv", "added"),
        row("new/name.csv", "moved"),
    ]}

    result = compare_payloads(before, after)
    assert result["summary"] == {
        "added_count": 1,
        "removed_count": 1,
        "moved_count": 1,
        "content_changed_count": 1,
        "assessment_changed_count": 1,
        "priority_escalated_count": 1,
        "priority_deescalated_count": 0,
        "unchanged_count": 1,
        "change_count": 5,
    }
    types = [item["change_type"] for item in result["changes"]]
    assert types == ["MOVED", "CONTENT_CHANGED", "ASSESSMENT_CHANGED", "ADDED", "REMOVED"]
    assessment = next(item for item in result["changes"] if item["change_type"] == "ASSESSMENT_CHANGED")
    assert "risk" in assessment["changed_fields"]
    assert "priority" in assessment["changed_fields"]
    assert "recommended_action" in assessment["changed_fields"]


def test_compare_move_detection_is_conservative_for_duplicate_hashes():
    from labvault_scout.compare import compare_payloads

    before = {"files": [
        {"path": "old/a.csv", "sha256": "same"},
        {"path": "old/b.csv", "sha256": "same"},
    ]}
    after = {"files": [
        {"path": "new/a.csv", "sha256": "same"},
        {"path": "new/b.csv", "sha256": "same"},
    ]}

    result = compare_payloads(before, after)
    assert result["summary"]["moved_count"] == 0
    assert result["summary"]["added_count"] == 2
    assert result["summary"]["removed_count"] == 2


def test_compare_accepts_legacy_v02_scan_json(tmp_path: Path):
    from labvault_scout.compare import compare_reports

    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    before.write_text(json.dumps({"files": [{"path": "data.csv", "sha256": "a"}], "errors": []}), encoding="utf-8")
    after.write_text(json.dumps({"files": [{"path": "data.csv", "sha256": "a"}], "errors": []}), encoding="utf-8")

    result = compare_reports(before, after)
    assert result["before"]["schema_version"] == "legacy"
    assert result["after"]["schema_version"] == "legacy"
    assert result["summary"]["unchanged_count"] == 1
    assert result["summary"]["change_count"] == 0


def test_compare_rejects_duplicate_paths(tmp_path: Path):
    import pytest
    from labvault_scout.compare import load_scan_report

    report = tmp_path / "bad.json"
    report.write_text(json.dumps({"files": [
        {"path": "data.csv", "sha256": "a"},
        {"path": "data.csv", "sha256": "b"},
    ]}), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate path"):
        load_scan_report(report)


def test_write_comparison_outputs_json_csv_and_html(tmp_path: Path):
    from labvault_scout.compare import compare_payloads, write_comparison

    result = compare_payloads(
        {"files": [{"path": "old.csv", "sha256": "a", "risk": "SAFE"}]},
        {"files": [{"path": "new.csv", "sha256": "a", "risk": "SAFE"}]},
    )
    output = tmp_path / "comparison"
    write_comparison(result, output)

    assert (output / "comparison.json").exists()
    assert (output / "changes.csv").exists()
    assert (output / "comparison.html").exists()
    payload = json.loads((output / "comparison.json").read_text(encoding="utf-8"))
    assert payload["summary"]["moved_count"] == 1
    with (output / "changes.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))
    assert row["change_type"] == "MOVED"
    assert row["before_path"] == "old.csv"
    assert row["after_path"] == "new.csv"


def test_cli_compare_command(tmp_path: Path, monkeypatch, capsys):
    import sys
    from labvault_scout.cli import main

    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    output = tmp_path / "compare-output"
    before.write_text(json.dumps({"files": [{"path": "a.csv", "sha256": "a"}]}), encoding="utf-8")
    after.write_text(json.dumps({"files": [{"path": "a.csv", "sha256": "b"}]}), encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "compare", str(before), str(after), "-o", str(output)])
    main()

    assert (output / "comparison.json").exists()
    assert "Changes: 1" in capsys.readouterr().out


def test_compare_does_not_call_duplicate_content_a_move():
    from labvault_scout.compare import compare_payloads

    before = {"files": [
        {"path": "stable.csv", "sha256": "same"},
        {"path": "old.csv", "sha256": "same"},
    ]}
    after = {"files": [
        {"path": "stable.csv", "sha256": "same"},
        {"path": "new.csv", "sha256": "same"},
    ]}

    result = compare_payloads(before, after)
    assert result["summary"]["moved_count"] == 0
    assert result["summary"]["added_count"] == 1
    assert result["summary"]["removed_count"] == 1


def test_compare_marks_results_partial_when_source_scan_has_errors(tmp_path: Path):
    from labvault_scout.compare import compare_payloads, write_comparison

    before = {
        "files": [{"path": "data.csv", "sha256": "same"}],
        "errors": [{"path": "blocked", "error": "PermissionError"}],
    }
    after = {
        "files": [{"path": "data.csv", "sha256": "same"}],
        "errors": [],
    }

    result = compare_payloads(before, after)
    assert result["comparison_status"] == "PARTIAL"
    assert result["before"]["error_count"] == 1
    assert result["after"]["error_count"] == 0
    assert result["warnings"]

    output = tmp_path / "partial-comparison"
    write_comparison(result, output)
    page = (output / "comparison.html").read_text(encoding="utf-8")
    assert "Status: PARTIAL" in page
    assert "path additions/removals may be incomplete" in page


def test_scan_paths_use_posix_separators_in_reports(tmp_path: Path):
    source = tmp_path / "posix_source"
    nested = source / "nested"
    nested.mkdir(parents=True)
    (nested / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "posix_report"

    scan(source, output)
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))

    assert payload["files"][0]["path"] == "nested/data.csv"
    assert "\\" not in payload["files"][0]["path"]


def test_schema1_round_trip_allows_literal_backslash_filename_on_posix(tmp_path: Path):
    import os
    import pytest
    from labvault_scout.compare import load_scan_report

    if os.name == "nt":
        pytest.skip("backslash is a path separator on Windows")

    source = tmp_path / "backslash_source"
    source.mkdir()
    name = "literal\\name.csv"
    (source / name).write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "backslash_report"

    scan(source, output)
    payload = load_scan_report(output / "scan.json")
    assert payload["files"][0]["path"] == name


def test_inventory_fingerprint_is_stable_and_content_sensitive(tmp_path: Path):
    source = tmp_path / "fingerprint_source"
    source.mkdir()
    (source / "b.csv").write_text("b\n", encoding="utf-8")
    (source / "a.csv").write_text("a\n", encoding="utf-8")

    first = tmp_path / "fingerprint_first"
    second = tmp_path / "fingerprint_second"
    scan(source, first)
    scan(source, second)

    first_payload = json.loads((first / "scan.json").read_text(encoding="utf-8"))
    second_payload = json.loads((second / "scan.json").read_text(encoding="utf-8"))
    first_hash = first_payload["summary"]["inventory_sha256"]
    second_hash = second_payload["summary"]["inventory_sha256"]

    assert len(first_hash) == 64
    assert first_hash == second_hash

    (source / "a.csv").write_text("changed\n", encoding="utf-8")
    third = tmp_path / "fingerprint_third"
    scan(source, third)
    third_payload = json.loads((third / "scan.json").read_text(encoding="utf-8"))
    assert third_payload["summary"]["inventory_sha256"] != first_hash


def test_comparison_carries_inventory_fingerprints(tmp_path: Path):
    from labvault_scout.compare import compare_reports

    source = tmp_path / "fingerprint_compare_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    before_dir = tmp_path / "fingerprint_compare_before"
    after_dir = tmp_path / "fingerprint_compare_after"
    scan(source, before_dir)
    scan(source, after_dir)

    result = compare_reports(before_dir / "scan.json", after_dir / "scan.json")
    assert result["before"]["inventory_sha256"]
    assert result["before"]["inventory_sha256"] == result["after"]["inventory_sha256"]


def test_compare_reports_priority_escalation_and_deescalation():
    from labvault_scout.compare import compare_payloads

    before = {"files": [
        {"path": "up.jnb", "sha256": "a", "priority": "MEDIUM", "priority_score": 60},
        {"path": "down.jnb", "sha256": "b", "priority": "HIGH", "priority_score": 90},
    ]}
    after = {"files": [
        {"path": "up.jnb", "sha256": "a", "priority": "HIGH", "priority_score": 80},
        {"path": "down.jnb", "sha256": "b", "priority": "MEDIUM", "priority_score": 50},
    ]}

    result = compare_payloads(before, after)
    assert result["summary"]["priority_escalated_count"] == 1
    assert result["summary"]["priority_deescalated_count"] == 1

    by_path = {item["after_path"]: item for item in result["changes"]}
    assert by_path["up.jnb"]["priority_direction"] == "ESCALATED"
    assert by_path["up.jnb"]["priority_delta"] == 20
    assert by_path["down.jnb"]["priority_direction"] == "DEESCALATED"
    assert by_path["down.jnb"]["priority_delta"] == -40


def test_compare_metrics_delta_for_legacy_and_current_rows():
    from labvault_scout.compare import compare_payloads

    before = {"files": [
        {"path": "a.csv", "sha256": "a", "size": 10, "risk": "SAFE", "priority": "LOW"},
        {"path": "b.jnb", "sha256": "b", "size": 20, "risk": "RESCUE", "priority": "HIGH"},
    ]}
    after = {"files": [
        {"path": "a.csv", "sha256": "a", "size": 15, "risk": "WATCH", "priority": "MEDIUM"},
        {"path": "c.csv", "sha256": "c", "size": 30, "risk": "SAFE", "priority": "LOW"},
        {"path": "d.csv", "sha256": "d", "size": 5, "risk": "SAFE", "priority": "LOW"},
    ]}

    result = compare_payloads(before, after)
    assert result["before"]["metrics"] == {
        "file_count": 2,
        "total_bytes": 30,
        "risk_counts": {"RESCUE": 1, "SAFE": 1},
        "priority_counts": {"HIGH": 1, "LOW": 1},
    }
    assert result["metrics_delta"] == {
        "file_count": 1,
        "total_bytes": 20,
        "risk_counts": {"RESCUE": -1, "SAFE": 1, "WATCH": 1},
        "priority_counts": {"HIGH": -1, "LOW": 1, "MEDIUM": 1},
    }


def test_comparison_exit_codes():
    from labvault_scout.compare import comparison_exit_code

    assert comparison_exit_code({
        "comparison_status": "COMPLETE",
        "summary": {"change_count": 0},
    }) == 0
    assert comparison_exit_code({
        "comparison_status": "COMPLETE",
        "summary": {"change_count": 3},
    }) == 1
    assert comparison_exit_code({
        "comparison_status": "PARTIAL",
        "summary": {"change_count": 0},
    }) == 2


def test_cli_compare_exit_code_is_opt_in(tmp_path: Path, monkeypatch):
    import sys
    import pytest
    from labvault_scout.cli import main

    before = tmp_path / "before-exit.json"
    after = tmp_path / "after-exit.json"
    output = tmp_path / "compare-exit-output"
    before.write_text(json.dumps({"files": [{"path": "a.csv", "sha256": "a"}]}), encoding="utf-8")
    after.write_text(json.dumps({"files": [{"path": "a.csv", "sha256": "b"}]}), encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [
        "labvault-scout", "compare", str(before), str(after), "-o", str(output), "--exit-code"
    ])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1

    monkeypatch.setattr(sys, "argv", [
        "labvault-scout", "compare", str(after), str(after), "-o", str(output), "--exit-code"
    ])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0


def test_cli_compare_partial_exit_code_is_two(tmp_path: Path, monkeypatch):
    import sys
    import pytest
    from labvault_scout.cli import main

    before = tmp_path / "partial-before.json"
    after = tmp_path / "partial-after.json"
    output = tmp_path / "partial-exit-output"
    before.write_text(json.dumps({
        "files": [{"path": "a.csv", "sha256": "a"}],
        "errors": [{"path": "blocked", "error": "PermissionError"}],
    }), encoding="utf-8")
    after.write_text(json.dumps({
        "files": [{"path": "a.csv", "sha256": "a"}],
        "errors": [],
    }), encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [
        "labvault-scout", "compare", str(before), str(after), "-o", str(output), "--exit-code"
    ])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_compare_normalizes_legacy_windows_paths_against_v03_paths():
    from labvault_scout.compare import compare_payloads

    before = {
        "files": [{"path": "nested\\data.csv", "sha256": "same", "size": 1}],
        "errors": [],
    }
    after = {
        "schema_version": "1",
        "tool": {"name": "LabVault Scout", "version": "0.3.0.dev0"},
        "files": [{"path": "nested/data.csv", "sha256": "same", "size": 1}],
        "errors": [],
    }

    result = compare_payloads(before, after)
    assert result["summary"]["change_count"] == 0
    assert result["summary"]["unchanged_count"] == 1
    assert result["before"]["legacy_paths_normalized"] is True
    assert result["after"]["legacy_paths_normalized"] is False
    assert any("backslash paths" in warning for warning in result["warnings"])


def test_compare_rejects_ambiguous_legacy_path_normalization():
    import pytest
    from labvault_scout.compare import compare_payloads

    before = {
        "files": [
            {"path": "nested\\data.csv", "sha256": "a"},
            {"path": "nested/data.csv", "sha256": "b"},
        ]
    }
    after = {"schema_version": "1", "files": []}

    with pytest.raises(ValueError, match="Path collision after legacy normalization"):
        compare_payloads(before, after)


def test_compare_large_inventory_is_deterministic_without_timing_threshold():
    from labvault_scout.compare import compare_payloads

    before_rows = [
        {
            "path": f"data/file_{index:04d}.csv",
            "sha256": f"hash-{index:04d}",
            "size": index + 1,
            "risk": "SAFE",
            "priority": "LOW",
            "priority_score": 0,
        }
        for index in range(1000)
    ]
    after_rows = [dict(row) for row in before_rows]

    after_rows[500]["sha256"] = "changed-hash"
    moved = after_rows.pop(999)
    moved["path"] = "archive/file_0999.csv"
    after_rows.append(moved)

    first = compare_payloads({"files": before_rows}, {"files": after_rows})
    second = compare_payloads(
        {"files": list(reversed(before_rows))},
        {"files": list(reversed(after_rows))},
    )

    assert first == second
    assert first["summary"]["content_changed_count"] == 1
    assert first["summary"]["moved_count"] == 1
    assert first["summary"]["unchanged_count"] == 998
    assert first["summary"]["change_count"] == 2


def test_compare_unknown_scan_schema_is_partial_and_exit_code_two():
    from labvault_scout.compare import compare_payloads, comparison_exit_code

    before = {
        "schema_version": "99",
        "files": [{"path": "data.csv", "sha256": "same"}],
        "errors": [],
    }
    after = {
        "schema_version": "1",
        "files": [{"path": "data.csv", "sha256": "same"}],
        "errors": [],
    }

    result = compare_payloads(before, after)
    assert result["comparison_status"] == "PARTIAL"
    assert result["before"]["schema_supported"] is False
    assert result["after"]["schema_supported"] is True
    assert any("unsupported scan schema" in warning for warning in result["warnings"])
    assert comparison_exit_code(result) == 2


def test_compare_legacy_schema_remains_supported():
    from labvault_scout.compare import compare_payloads

    result = compare_payloads(
        {"files": [{"path": "data.csv", "sha256": "same"}], "errors": []},
        {"files": [{"path": "data.csv", "sha256": "same"}], "errors": []},
    )

    assert result["comparison_status"] == "COMPLETE"
    assert result["before"]["schema_version"] == "legacy"
    assert result["before"]["schema_supported"] is True


def test_rules_fingerprint_is_deterministic_and_sensitive():
    from labvault_scout.risk import rules_sha256

    first = {
        ".csv": {"risk": "SAFE", "name": "CSV"},
        ".jnb": {"risk": "RESCUE", "name": "SigmaPlot"},
    }
    reordered = {
        ".jnb": {"name": "SigmaPlot", "risk": "RESCUE"},
        ".csv": {"name": "CSV", "risk": "SAFE"},
    }
    changed = {
        ".csv": {"risk": "WATCH", "name": "CSV"},
        ".jnb": {"risk": "RESCUE", "name": "SigmaPlot"},
    }

    assert rules_sha256(first) == rules_sha256(reordered)
    assert rules_sha256(first) != rules_sha256(changed)


def test_scan_json_records_non_sensitive_provenance(tmp_path: Path):
    source = tmp_path / "provenance_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "provenance_report"

    scan(source, output)
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    provenance = payload["provenance"]

    assert provenance["hash_algorithm"] == "sha256"
    assert provenance["path_style"] == "relative-posix"
    assert provenance["source_access"] == "read-only"
    assert provenance["rules_count"] > 0
    assert len(provenance["rules_sha256"]) == 64
    assert str(source) not in json.dumps(provenance)


def test_compare_reports_rule_context_status():
    from labvault_scout.compare import compare_payloads

    base = {
        "schema_version": "1",
        "provenance": {"rules_sha256": "a" * 64, "hash_algorithm": "sha256", "path_style": "relative-posix"},
        "files": [{"path": "data.csv", "sha256": "same"}],
        "errors": [],
    }
    same = {
        "schema_version": "1",
        "provenance": {"rules_sha256": "a" * 64, "hash_algorithm": "sha256", "path_style": "relative-posix"},
        "files": [{"path": "data.csv", "sha256": "same"}],
        "errors": [],
    }
    changed = {
        "schema_version": "1",
        "provenance": {"rules_sha256": "b" * 64, "hash_algorithm": "sha256", "path_style": "relative-posix"},
        "files": [{"path": "data.csv", "sha256": "same"}],
        "errors": [],
    }

    same_result = compare_payloads(base, same)
    assert same_result["rules_status"] == "SAME"
    assert not any("Rule-set fingerprint changed" in warning for warning in same_result["warnings"])

    changed_result = compare_payloads(base, changed)
    assert changed_result["comparison_status"] == "COMPLETE"
    assert changed_result["rules_status"] == "CHANGED"
    assert any("Rule-set fingerprint changed" in warning for warning in changed_result["warnings"])


def test_compare_legacy_rule_context_is_unknown():
    from labvault_scout.compare import compare_payloads

    result = compare_payloads(
        {"files": [{"path": "data.csv", "sha256": "same"}], "errors": []},
        {"files": [{"path": "data.csv", "sha256": "same"}], "errors": []},
    )

    assert result["rules_status"] == "UNKNOWN"


def test_report_integrity_status_verifies_v03_inventory(tmp_path: Path):
    from labvault_scout.compare import load_scan_report, report_integrity_status

    source = tmp_path / "integrity_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "integrity_report"
    scan(source, output)

    payload = load_scan_report(output / "scan.json")
    assert report_integrity_status(payload) == "VERIFIED"


def test_compare_marks_tampered_inventory_partial(tmp_path: Path):
    from labvault_scout.compare import compare_payloads, comparison_exit_code

    source = tmp_path / "tamper_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "tamper_report"
    scan(source, output)
    original = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    tampered = json.loads(json.dumps(original))
    tampered["files"][0]["sha256"] = "0" * 64

    result = compare_payloads(original, tampered)
    assert result["before"]["integrity_status"] == "VERIFIED"
    assert result["after"]["integrity_status"] == "MISMATCH"
    assert result["comparison_status"] == "PARTIAL"
    assert any("fingerprint validation" in warning for warning in result["warnings"])
    assert comparison_exit_code(result) == 2


def test_legacy_report_integrity_is_unknown_not_failure():
    from labvault_scout.compare import compare_payloads

    legacy = {
        "files": [{"path": "data.csv", "size": 1, "sha256": "same"}],
        "errors": [],
    }
    result = compare_payloads(legacy, legacy)
    assert result["before"]["integrity_status"] == "UNKNOWN"
    assert result["comparison_status"] == "COMPLETE"


def test_report_integrity_detects_tampered_summary(tmp_path: Path):
    from labvault_scout.compare import compare_payloads

    source = tmp_path / "summary_tamper_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "summary_tamper_report"
    scan(source, output)

    original = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    tampered = json.loads(json.dumps(original))
    tampered["summary"]["file_count"] = 999

    result = compare_payloads(original, tampered)
    assert result["before"]["integrity_status"] == "VERIFIED"
    assert result["after"]["integrity_status"] == "MISMATCH"
    assert result["comparison_status"] == "PARTIAL"


def test_report_integrity_detects_tampered_error_count(tmp_path: Path):
    from labvault_scout.compare import report_integrity_status

    source = tmp_path / "error_count_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "error_count_report"
    scan(source, output)

    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    payload["summary"]["error_count"] = 5
    assert report_integrity_status(payload) == "MISMATCH"


def test_integrity_recomputes_open_copy_and_duplicate_counts(tmp_path: Path):
    from labvault_scout.compare import report_integrity_status
    from labvault_scout.report import report_payload_sha256

    source = tmp_path / "summary_integrity_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "summary_integrity_report"
    scan(source, output)

    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert report_integrity_status(payload) == "VERIFIED"

    for field in ("open_copy_count", "duplicate_group_count"):
        mutated = json.loads(json.dumps(payload))
        mutated["summary"][field] += 1
        mutated["report_sha256"] = report_payload_sha256(mutated)
        assert report_integrity_status(mutated) == "MISMATCH"


def test_verify_report_statuses(tmp_path: Path):
    from labvault_scout.compare import load_scan_report, verify_report

    source = tmp_path / "verify_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "verify_report"
    scan(source, output)

    payload = load_scan_report(output / "scan.json")
    verified = verify_report(payload)
    assert verified["status"] == "VERIFIED"
    assert verified["exit_code"] == 0

    legacy = verify_report({
        "files": [{"path": "data.csv", "size": 1, "sha256": "same"}],
        "errors": [],
    })
    assert legacy["status"] == "UNKNOWN"
    assert legacy["exit_code"] == 1

    tampered = json.loads(json.dumps(payload))
    tampered["summary"]["file_count"] = 999
    failed = verify_report(tampered)
    assert failed["status"] == "FAILED"
    assert failed["exit_code"] == 2

    future = json.loads(json.dumps(payload))
    future["schema_version"] = "99"
    unsupported = verify_report(future)
    assert unsupported["status"] == "UNSUPPORTED"
    assert unsupported["exit_code"] == 2


def test_cli_verify_report_exit_codes(tmp_path: Path, monkeypatch, capsys):
    import sys
    import pytest
    from labvault_scout.cli import main

    source = tmp_path / "verify_cli_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "verify_cli_report"
    scan(source, output)

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(output / "scan.json")])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    assert "Report verification: VERIFIED" in capsys.readouterr().out

    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(json.dumps({
        "files": [{"path": "data.csv", "size": 1, "sha256": "same"}],
        "errors": [],
    }), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(legacy_path)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


def test_scan_json_has_deterministic_full_report_checksum(tmp_path: Path):
    from labvault_scout.report import report_payload_sha256

    source = tmp_path / "checksum_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "checksum_report"
    scan(source, output)

    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert len(payload["report_sha256"]) == 64
    assert payload["report_sha256"] == report_payload_sha256(payload)


def test_report_checksum_detects_assessment_field_tampering(tmp_path: Path):
    from labvault_scout.compare import report_integrity_status

    source = tmp_path / "assessment_tamper_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "assessment_tamper_report"
    scan(source, output)

    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert report_integrity_status(payload) == "VERIFIED"

    payload["files"][0]["risk"] = "RESCUE"
    assert report_integrity_status(payload) == "MISMATCH"


def test_report_checksum_detects_provenance_tampering(tmp_path: Path):
    from labvault_scout.compare import report_integrity_status

    source = tmp_path / "provenance_tamper_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "provenance_tamper_report"
    scan(source, output)

    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    payload["provenance"]["rules_sha256"] = "0" * 64
    assert report_integrity_status(payload) == "MISMATCH"


def test_cli_verify_json_output(tmp_path: Path, monkeypatch, capsys):
    import sys
    import pytest
    from labvault_scout.cli import main

    source = tmp_path / "verify_json_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "verify_json_report"
    scan(source, output)

    monkeypatch.setattr(sys, "argv", [
        "labvault-scout", "verify", str(output / "scan.json"), "--json"
    ])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "VERIFIED"
    assert payload["integrity_status"] == "VERIFIED"
    assert payload["schema_supported"] is True
    assert len(payload["report_sha256"]) == 64


def test_verify_unknown_schema_takes_precedence_over_checksum_mismatch(tmp_path: Path):
    from labvault_scout.compare import verify_report

    source = tmp_path / "schema_precedence_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "schema_precedence_report"
    scan(source, output)

    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    payload["schema_version"] = "99"
    result = verify_report(payload)

    assert result["status"] == "UNSUPPORTED"
    assert result["exit_code"] == 2
    assert result["schema_supported"] is False
    assert result["integrity_status"] == "MISMATCH"


def test_schema1_loader_rejects_noncanonical_and_parent_paths(tmp_path: Path):
    import pytest
    from labvault_scout.compare import load_scan_report

    source = tmp_path / "strict_path_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "strict_path_report"
    scan(source, output)
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))

    for bad_path in ("/absolute/data.csv", "../escape.csv", "nested/../escape.csv", "./data.csv", "nested//data.csv"):
        mutated = json.loads(json.dumps(payload))
        mutated["files"][0]["path"] = bad_path
        report = tmp_path / ("bad-path-" + str(abs(hash(bad_path))) + ".json")
        report.write_text(json.dumps(mutated), encoding="utf-8")
        with pytest.raises(ValueError, match="Report path|canonical POSIX"):
            load_scan_report(report)


    mutated = json.loads(json.dumps(payload))
    mutated["files"][0]["path"] = "bad\x00path.csv"
    report = tmp_path / "bad-path-nul.json"
    report.write_text(json.dumps(mutated), encoding="utf-8")
    with pytest.raises(ValueError, match="Report path"):
        load_scan_report(report)


def test_schema1_loader_rejects_invalid_hash_size_and_required_fields(tmp_path: Path):
    import pytest
    from labvault_scout.compare import load_scan_report

    source = tmp_path / "strict_fields_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "strict_fields_report"
    scan(source, output)
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))

    cases = []
    bad_hash = json.loads(json.dumps(payload))
    bad_hash["files"][0]["sha256"] = "not-a-sha256"
    cases.append((bad_hash, "invalid sha256"))

    bad_size = json.loads(json.dumps(payload))
    bad_size["files"][0]["size"] = -1
    cases.append((bad_size, "invalid size"))

    missing = json.loads(json.dumps(payload))
    del missing["files"][0]["risk"]
    cases.append((missing, "missing fields"))

    bad_priority = json.loads(json.dumps(payload))
    bad_priority["files"][0]["priority_score"] = 101
    cases.append((bad_priority, "invalid priority_score"))

    for index, (case, message) in enumerate(cases):
        report = tmp_path / f"bad-fields-{index}.json"
        report.write_text(json.dumps(case), encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            load_scan_report(report)


def test_schema1_loader_rejects_invalid_error_paths(tmp_path: Path):
    import pytest
    from labvault_scout.compare import load_scan_report

    source = tmp_path / "strict_error_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "strict_error_report"
    scan(source, output)
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    mutated = json.loads(json.dumps(payload))
    mutated["errors"] = [{"path": "../outside", "error": "PermissionError"}]

    report = tmp_path / "bad-error-path.json"
    report.write_text(json.dumps(mutated), encoding="utf-8")
    with pytest.raises(ValueError, match="Report path|traverse parents"):
        load_scan_report(report)


def test_legacy_loader_remains_lenient_for_minimal_rows(tmp_path: Path):
    from labvault_scout.compare import load_scan_report

    report = tmp_path / "legacy-minimal.json"
    report.write_text(json.dumps({
        "files": [{"path": "data.csv", "sha256": "legacy"}],
        "errors": [],
    }), encoding="utf-8")

    payload = load_scan_report(report)
    assert payload["files"][0]["sha256"] == "legacy"


def test_loader_rejects_non_string_or_empty_explicit_schema_version(tmp_path: Path):
    import pytest
    from labvault_scout.compare import load_scan_report, verify_report

    source = tmp_path / "schema_type_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "schema_type_report"
    scan(source, output)
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))

    for value in (1, True, ""):
        mutated = json.loads(json.dumps(payload))
        mutated["schema_version"] = value
        report = tmp_path / ("bad-schema-version-" + str(type(value).__name__) + "-" + str(value) + ".json")
        report.write_text(json.dumps(mutated), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid scan schema_version"):
            load_scan_report(report)

    direct = json.loads(json.dumps(payload))
    direct["schema_version"] = 1
    result = verify_report(direct)
    assert result["status"] == "UNSUPPORTED"
    assert result["schema_version"] == "invalid"
    assert result["schema_supported"] is False


def test_unknown_future_schema_uses_minimum_validation_only(tmp_path: Path):
    from labvault_scout.compare import load_scan_report, verify_report

    report = tmp_path / "future.json"
    report.write_text(json.dumps({
        "schema_version": "99",
        "files": [{"path": "data.csv", "future_field": {"anything": True}}],
        "errors": [],
    }), encoding="utf-8")

    payload = load_scan_report(report)
    result = verify_report(payload)
    assert result["status"] == "UNSUPPORTED"
    assert result["exit_code"] == 2


def test_cli_scan_invalid_inputs_exit_two_without_traceback(tmp_path: Path, monkeypatch, capsys):
    import sys
    import pytest
    from labvault_scout.cli import main

    missing = tmp_path / "missing-source"
    monkeypatch.setattr(sys, "argv", ["labvault-scout", "scan", str(missing)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "Traceback" not in captured.err

    source = tmp_path / "same-output-source"
    source.mkdir()
    monkeypatch.setattr(sys, "argv", ["labvault-scout", "scan", str(source), "-o", str(source)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Output directory must not be the scan root" in captured.err
    assert "Traceback" not in captured.err


def test_cli_scan_oserror_exits_two_without_traceback(tmp_path: Path, monkeypatch, capsys):
    import sys
    import pytest
    import labvault_scout.cli as cli_module

    source = tmp_path / "scan-oserror-source"
    source.mkdir()

    def fail_scan(directory, output):
        raise PermissionError("permission denied")

    monkeypatch.setattr(cli_module, "scan", fail_scan)
    monkeypatch.setattr(sys, "argv", ["labvault-scout", "scan", str(source)])

    with pytest.raises(SystemExit) as exc:
        cli_module.main()
    assert exc.value.code == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "permission denied" in captured.err
    assert "Traceback" not in captured.err


def test_cli_verify_invalid_report_is_concise_and_json_capable(tmp_path: Path, monkeypatch, capsys):
    import sys
    import pytest
    from labvault_scout.cli import main

    bad = tmp_path / "invalid-report.json"
    bad.write_text('{"schema_version":"1","files":[]}', encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(bad)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "Traceback" not in captured.err

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(bad), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2


def test_cli_verify_non_utf8_report_exits_two_without_traceback(tmp_path: Path, monkeypatch, capsys):
    import sys
    import pytest
    from labvault_scout.cli import main

    bad = tmp_path / "non-utf8-report.json"
    bad.write_bytes(b"\xff\xfe\xfa")

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(bad)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "Traceback" not in captured.err

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(bad), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2
    assert "Cannot read scan report" in result["error"]


def test_cli_compare_non_utf8_report_exits_two_without_traceback(tmp_path: Path, monkeypatch, capsys):
    import sys
    import pytest
    from labvault_scout.cli import main

    bad = tmp_path / "non-utf8-compare.json"
    good = tmp_path / "good-legacy.json"
    bad.write_bytes(b"\xff\xfe\xfa")
    good.write_text(
        json.dumps({"files": [{"path": "data.csv", "sha256": "x"}], "errors": []}),
        encoding="utf-8",
    )

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "compare", str(bad), str(good)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "Cannot read scan report" in captured.err
    assert "Traceback" not in captured.err


def test_cli_compare_invalid_report_exits_two_without_traceback(tmp_path: Path, monkeypatch, capsys):
    import sys
    import pytest
    from labvault_scout.cli import main

    bad = tmp_path / "bad-compare.json"
    good = tmp_path / "good-legacy.json"
    bad.write_text('{"schema_version":"1","files":[]}', encoding="utf-8")
    good.write_text(json.dumps({"files": [{"path": "data.csv", "sha256": "x"}], "errors": []}), encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "compare", str(bad), str(good)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "Traceback" not in captured.err


def test_cli_compare_output_oserror_exits_two_without_traceback(tmp_path: Path, monkeypatch, capsys):
    import sys
    import pytest
    import labvault_scout.cli as cli_module

    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    payload = {"files": [{"path": "data.csv", "sha256": "same"}], "errors": []}
    before.write_text(json.dumps(payload), encoding="utf-8")
    after.write_text(json.dumps(payload), encoding="utf-8")

    def fail_write(result, output):
        raise PermissionError("permission denied")

    monkeypatch.setattr(cli_module, "write_comparison", fail_write)
    monkeypatch.setattr(
        sys,
        "argv",
        ["labvault-scout", "compare", str(before), str(after), "-o", str(tmp_path / "comparison")],
    )

    with pytest.raises(SystemExit) as exc:
        cli_module.main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "permission denied" in captured.err
    assert "Traceback" not in captured.err


def test_packaged_json_schemas_are_available_and_parseable():
    from labvault_scout.schema_registry import load_schema_text
    from labvault_scout.report import FIELDS

    scan_schema = json.loads(load_schema_text("scan"))
    comparison_schema = json.loads(load_schema_text("comparison"))
    verification_schema = json.loads(load_schema_text("verification"))

    assert scan_schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert scan_schema["properties"]["schema_version"]["const"] == "1"
    assert set(scan_schema["properties"]["files"]["items"]["required"]) == set(FIELDS)
    assert comparison_schema["properties"]["schema_version"]["const"] == "1"
    assert verification_schema["oneOf"]


def test_cli_schema_outputs_packaged_schema(monkeypatch, capsys):
    import sys
    from labvault_scout.cli import main

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "schema", "scan"])
    main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["title"] == "LabVault Scout scan report schema 1"


def test_scan_schema_enforces_relative_posix_paths():
    import re
    from labvault_scout.schema_registry import load_schema_text

    schema = json.loads(load_schema_text("scan"))
    file_path_schema = schema["properties"]["files"]["items"]["properties"]["path"]
    error_path_schema = schema["properties"]["errors"]["items"]["properties"]["path"]

    def accepts(path_schema, value):
        if "anyOf" in path_schema:
            return any(accepts(option, value) for option in path_schema["anyOf"])
        if "const" in path_schema:
            return value == path_schema["const"]
        if len(value) < path_schema.get("minLength", 0):
            return False
        for clause in path_schema.get("allOf", []):
            negated = clause.get("not", {})
            if "const" in negated and value == negated["const"]:
                return False
            if "pattern" in negated and re.search(negated["pattern"], value):
                return False
        return True

    for value in ("data.csv", "nested/data.csv", "nested/deeper/file.jnb", "literal\\name.csv"):
        assert accepts(file_path_schema, value)

    for value in (
        ".",
        "/absolute/data.csv",
        "../escape.csv",
        "nested/../escape.csv",
        "./data.csv",
        "nested/./data.csv",
        "nested//data.csv",
        "data.csv/",
        "bad\x00path.csv",
    ):
        assert not accepts(file_path_schema, value)

    assert accepts(error_path_schema, ".")
    assert accepts(error_path_schema, "nested/problem")
    assert accepts(error_path_schema, "literal\\problem")


def test_all_schema_registry_entries_load():
    from labvault_scout.schema_registry import SCHEMA_FILES, load_schema_text

    assert set(SCHEMA_FILES) == {"scan", "comparison", "verification", "bundle"}
    for kind in SCHEMA_FILES:
        assert json.loads(load_schema_text(kind))["$schema"].endswith("/2020-12/schema")


def test_netcdf_classic_family_header_evidence():
    from labvault_scout.identifier import netcdf_container_from_header, signature_from_head

    cases = {
        b"CDF\x01" + b"\x00" * 4: "NetCDF CDF-1",
        b"CDF\x02" + b"\x00" * 4: "NetCDF CDF-2",
        b"CDF\x05" + b"\x00" * 4: "NetCDF CDF-5",
    }
    for header, label in cases.items():
        assert signature_from_head(header) == "NETCDF"
        assert netcdf_container_from_header(header) == label


def test_netcdf_classic_scan_is_verified(tmp_path: Path):
    source = tmp_path / "netcdf_source"
    source.mkdir()
    (source / "climate.nc").write_bytes(b"CDF\x01" + b"\x00" * 32)
    output = tmp_path / "netcdf_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["format"] == "NetCDF"
    assert row["signature"] == "NETCDF"
    assert row["container_type"] == "NetCDF CDF-1"
    assert row["signature_status"] == "verified"
    assert row["confidence"] == "HIGH"


def test_netcdf_hdf5_container_is_conservative(tmp_path: Path):
    source = tmp_path / "netcdf4_source"
    source.mkdir()
    header = bytes.fromhex("894844460D0A1A0A") + bytes([2]) + b"\x00" * 64
    (source / "modern.nc").write_bytes(header)
    output = tmp_path / "netcdf4_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["signature"] == "HDF5"
    assert row["container_type"] == "HDF5 superblock v2"
    assert row["signature_status"] == "container-only: HDF5"
    assert row["confidence"] == "MEDIUM"


def test_netcdf_disguised_file_is_mismatch(tmp_path: Path):
    source = tmp_path / "bad_netcdf_source"
    source.mkdir()
    (source / "fake.nc").write_bytes(b"%PDF-1.7\n")
    output = tmp_path / "bad_netcdf_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["signature"] == "PDF"
    assert row["signature_status"] == "mismatch: expected NetCDF/HDF5, detected PDF"
    assert row["confidence"] == "LOW"


def test_tiff_classic_and_bigtiff_header_evidence():
    from labvault_scout.identifier import signature_from_head, tiff_container_from_header

    classic_le = bytes.fromhex("49492A00") + (8).to_bytes(4, "little")
    classic_be = bytes.fromhex("4D4D002A") + (8).to_bytes(4, "big")
    big_le = bytes.fromhex("49492B00") + (8).to_bytes(2, "little") + b"\x00\x00" + (16).to_bytes(8, "little")

    assert signature_from_head(classic_le) == "TIFF"
    assert tiff_container_from_header(classic_le) == "TIFF classic (little-endian)"
    assert tiff_container_from_header(classic_be) == "TIFF classic (big-endian)"
    assert tiff_container_from_header(big_le) == "BigTIFF (little-endian)"


def test_tiff_scan_is_structurally_verified(tmp_path: Path):
    source = tmp_path / "tiff_source"
    source.mkdir()
    (source / "image.tif").write_bytes(bytes.fromhex("49492A00") + (8).to_bytes(4, "little") + b"\x00" * 32)
    output = tmp_path / "tiff_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["signature"] == "TIFF"
    assert row["container_type"] == "TIFF classic (little-endian)"
    assert row["signature_status"] == "verified"
    assert row["confidence"] == "HIGH"


def test_truncated_bigtiff_is_reviewed(tmp_path: Path):
    source = tmp_path / "bad_tiff_source"
    source.mkdir()
    (source / "broken.tiff").write_bytes(bytes.fromhex("49492B00"))
    output = tmp_path / "bad_tiff_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["signature"] == "TIFF"
    assert row["container_type"] == "Truncated BigTIFF container"
    assert row["signature_status"] == "unverified: expected TIFF structure"
    assert row["confidence"] == "LOW"
    assert row["recommended_action"] == "REVIEW_CONTAINER"


def _valid_fits_bytes(simple_value: bytes = b"T") -> bytes:
    block = bytearray(b" " * 2880)
    block[0:30] = b"SIMPLE  =                    " + simple_value
    block[80:110] = b"BITPIX  =                    8"
    block[160:190] = b"NAXIS   =                    0"
    block[240:243] = b"END"
    return bytes(block)


def test_fits_primary_header_is_verified(tmp_path: Path):
    source = tmp_path / "fits_source"
    source.mkdir()
    (source / "spectrum.fits").write_bytes(_valid_fits_bytes())
    output = tmp_path / "fits_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["format"] == "FITS"
    assert row["signature"] == "FITS"
    assert row["container_type"] == "FITS primary HDU (SIMPLE=T)"
    assert row["signature_status"] == "verified"
    assert row["confidence"] == "HIGH"
    assert row["recommended_action"] == "KEEP"


def test_fits_simple_false_is_nonconforming_and_reviewed(tmp_path: Path):
    source = tmp_path / "fits_false_source"
    source.mkdir()
    (source / "nonconforming.fits").write_bytes(_valid_fits_bytes(b"F"))
    output = tmp_path / "fits_false_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["signature"] == "FITS"
    assert row["container_type"] == "Nonconforming FITS (SIMPLE=F)"
    assert row["signature_status"] == "unverified: expected FITS structure"
    assert row["confidence"] == "LOW"
    assert row["recommended_action"] == "REVIEW_CONTAINER"


def test_fits_invalid_block_size_is_reviewed(tmp_path: Path):
    source = tmp_path / "fits_bad_block_source"
    source.mkdir()
    data = bytearray(_valid_fits_bytes())
    data.extend(b"x")
    (source / "badblock.fits").write_bytes(data)
    output = tmp_path / "fits_bad_block_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["container_type"] == "Invalid FITS block size"
    assert row["signature_status"] == "unverified: expected FITS structure"
    assert row["recommended_action"] == "REVIEW_CONTAINER"


def test_fits_disguised_file_is_mismatch(tmp_path: Path):
    source = tmp_path / "fake_fits_source"
    source.mkdir()
    (source / "fake.fits").write_bytes(b"%PDF-1.7\n")
    output = tmp_path / "fake_fits_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["signature"] == "PDF"
    assert row["signature_status"] == "mismatch: expected FITS, detected PDF"
    assert row["confidence"] == "LOW"


def _matlab5_header(endian: bytes = b"IM") -> bytes:
    header = bytearray(b" " * 128)
    text = b"MATLAB 5.0 MAT-file, Platform: GLNXA64, Created by LabVault Scout test"
    header[:len(text)] = text
    header[124:126] = b"\x00\x01"
    header[126:128] = endian
    return bytes(header)


def test_matlab5_header_evidence():
    from labvault_scout.identifier import matlab5_container_from_header, signature_from_head

    little = _matlab5_header(b"IM")
    big = _matlab5_header(b"MI")

    assert signature_from_head(little) == "MAT5"
    assert matlab5_container_from_header(little) == "MATLAB Level 5 MAT-file (little-endian)"
    assert matlab5_container_from_header(big) == "MATLAB Level 5 MAT-file (big-endian)"


def test_matlab5_scan_is_structurally_verified(tmp_path: Path):
    source = tmp_path / "mat5_source"
    source.mkdir()
    (source / "experiment.mat").write_bytes(_matlab5_header() + b"\x00" * 64)
    output = tmp_path / "mat5_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["format"] == "MATLAB Data"
    assert row["signature"] == "MAT5"
    assert row["container_type"] == "MATLAB Level 5 MAT-file (little-endian)"
    assert row["signature_status"] == "verified"
    assert row["confidence"] == "HIGH"


def test_matlab_hdf5_container_remains_conservative(tmp_path: Path):
    source = tmp_path / "mat_hdf5_source"
    source.mkdir()
    header = bytes.fromhex("894844460D0A1A0A") + bytes([2]) + b"\x00" * 64
    (source / "modern.mat").write_bytes(header)
    output = tmp_path / "mat_hdf5_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["signature"] == "HDF5"
    assert row["container_type"] == "HDF5 superblock v2"
    assert row["signature_status"] == "container-only: HDF5"
    assert row["confidence"] == "MEDIUM"


def test_matlab_disguised_file_is_mismatch(tmp_path: Path):
    source = tmp_path / "bad_mat_source"
    source.mkdir()
    (source / "fake.mat").write_bytes(b"%PDF-1.7\n")
    output = tmp_path / "bad_mat_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["signature"] == "PDF"
    assert row["signature_status"] == "mismatch: expected MATLAB Level 5/HDF5, detected PDF"
    assert row["confidence"] == "LOW"


def test_truncated_matlab5_header_is_reviewed(tmp_path: Path):
    source = tmp_path / "truncated_mat_source"
    source.mkdir()
    (source / "broken.mat").write_bytes(b"MATLAB 5.0 MAT-file")
    output = tmp_path / "truncated_mat_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["signature"] == "MAT5"
    assert row["container_type"] == "Truncated MATLAB Level 5 header"
    assert row["signature_status"] == "unverified: expected MATLAB Level 5 structure"
    assert row["confidence"] == "LOW"
    assert row["recommended_action"] == "REVIEW_CONTAINER"


def _dicom_part10_bytes() -> bytes:
    return b"\x00" * 128 + b"DICM" + b"\x00" * 64


def test_dicom_part10_header_evidence():
    from labvault_scout.identifier import dicom_container_from_header, signature_from_head

    data = _dicom_part10_bytes()
    assert signature_from_head(data) == "DICOM"
    assert dicom_container_from_header(data) == "DICOM Part 10 file"


def test_dicom_part10_scan_is_verified(tmp_path: Path):
    source = tmp_path / "dicom_source"
    source.mkdir()
    (source / "image.dcm").write_bytes(_dicom_part10_bytes())
    output = tmp_path / "dicom_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["format"] == "DICOM"
    assert row["signature"] == "DICOM"
    assert row["container_type"] == "DICOM Part 10 file"
    assert row["signature_status"] == "verified"
    assert row["confidence"] == "HIGH"


def test_dicom_without_part10_marker_is_unverified_not_claimed_valid(tmp_path: Path):
    source = tmp_path / "dicom_no_marker_source"
    source.mkdir()
    (source / "legacy.dcm").write_bytes(b"\x00" * 256)
    output = tmp_path / "dicom_no_marker_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["signature"] == ""
    assert row["container_type"] == "DICOM Part 10 marker not found"
    assert row["signature_status"] == "unverified: expected DICOM Part 10"
    assert row["confidence"] == "LOW"


def test_dicom_disguised_file_is_mismatch(tmp_path: Path):
    source = tmp_path / "bad_dicom_source"
    source.mkdir()
    (source / "fake.dcm").write_bytes(b"%PDF-1.7\n")
    output = tmp_path / "bad_dicom_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["signature"] == "PDF"
    assert row["signature_status"] == "mismatch: expected DICOM Part 10, detected PDF"
    assert row["confidence"] == "LOW"


def test_truncated_dicom_header_is_reviewed(tmp_path: Path):
    source = tmp_path / "truncated_dicom_source"
    source.mkdir()
    (source / "short.dcm").write_bytes(b"\x00" * 64)
    output = tmp_path / "truncated_dicom_report"

    assert scan(source, output) == 1
    with (output / "files.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))

    assert row["container_type"] == "Truncated DICOM Part 10 header"
    assert row["signature_status"] == "unverified: expected DICOM Part 10"
    assert row["recommended_action"] == "REVIEW_CONTAINER"


def test_scan_writes_bundle_manifest_covering_core_outputs(tmp_path: Path):
    from labvault_scout.bundle import BUNDLE_FILES, load_bundle_manifest

    source = tmp_path / "bundle_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "bundle_report"

    scan(source, output)
    manifest = load_bundle_manifest(output)

    assert (output / "bundle_manifest.json").exists()
    assert {entry["path"] for entry in manifest["files"]} == set(BUNDLE_FILES)
    assert len(manifest["manifest_sha256"]) == 64


def test_verify_bundle_succeeds_and_detects_tampering(tmp_path: Path):
    from labvault_scout.bundle import verify_bundle

    source = tmp_path / "bundle_verify_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "bundle_verify_report"
    scan(source, output)

    result = verify_bundle(output)
    assert result["status"] == "VERIFIED"
    assert result["exit_code"] == 0
    assert result["checked_files"] == 5
    assert result["problems"] == []

    (output / "report.html").write_text("tampered", encoding="utf-8")
    result = verify_bundle(output)
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert result["problems"][0]["path"] == "report.html"


def test_verify_bundle_detects_missing_core_file(tmp_path: Path):
    from labvault_scout.bundle import verify_bundle

    source = tmp_path / "bundle_missing_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "bundle_missing_report"
    scan(source, output)

    (output / "duplicates.csv").unlink()
    result = verify_bundle(output)
    assert result["status"] == "FAILED"
    assert {"path": "duplicates.csv", "issue": "MISSING"} in result["problems"]


def test_bundle_manifest_checksum_detects_manifest_tampering(tmp_path: Path):
    import pytest
    from labvault_scout.bundle import load_bundle_manifest

    source = tmp_path / "bundle_manifest_tamper_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "bundle_manifest_tamper_report"
    scan(source, output)

    path = output / "bundle_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["files"][0]["size"] += 1
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="checksum mismatch"):
        load_bundle_manifest(output)


def test_bundle_manifest_rejects_path_traversal(tmp_path: Path):
    import pytest
    from labvault_scout.bundle import load_bundle_manifest, manifest_payload_sha256

    source = tmp_path / "bundle_path_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "bundle_path_report"
    scan(source, output)

    path = output / "bundle_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["files"][0]["path"] = "../scan.json"
    payload["manifest_sha256"] = manifest_payload_sha256(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Unsafe bundle manifest path"):
        load_bundle_manifest(output)


def test_bundle_manifest_rejects_nul_path(tmp_path: Path):
    import pytest
    from labvault_scout.bundle import load_bundle_manifest, manifest_payload_sha256

    source = tmp_path / "bundle_nul_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "bundle_nul_report"
    scan(source, output)

    path = output / "bundle_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["files"][0]["path"] = "scan\x00.json"
    payload["manifest_sha256"] = manifest_payload_sha256(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Bundle manifest path"):
        load_bundle_manifest(output)


def test_cli_verify_bundle_and_json_output(tmp_path: Path, monkeypatch, capsys):
    import sys
    import pytest
    from labvault_scout.cli import main

    source = tmp_path / "bundle_cli_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "bundle_cli_report"
    scan(source, output)

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify-bundle", str(output), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "VERIFIED"
    assert payload["checked_files"] == 5


def test_cli_verify_bundle_invalid_manifest_is_concise_and_json_capable(tmp_path: Path, monkeypatch, capsys):
    import sys
    import pytest
    from labvault_scout.cli import main

    output = tmp_path / "invalid_bundle"
    output.mkdir()

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify-bundle", str(output)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "Traceback" not in captured.err

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify-bundle", str(output), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2
    assert "error" in result


def test_cli_verify_bundle_malformed_json_is_concise_and_json_capable(tmp_path: Path, monkeypatch, capsys):
    import sys
    import pytest
    from labvault_scout.cli import main

    output = tmp_path / "malformed_bundle"
    output.mkdir()
    (output / "bundle_manifest.json").write_text("{not-json", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify-bundle", str(output)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "Traceback" not in captured.err

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify-bundle", str(output), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2
    assert "Cannot read bundle manifest" in result["error"]


def test_cli_verify_bundle_invalid_utf8_is_concise_and_json_capable(tmp_path: Path, monkeypatch, capsys):
    import sys
    import pytest
    from labvault_scout.cli import main

    output = tmp_path / "invalid_utf8_bundle"
    output.mkdir()
    (output / "bundle_manifest.json").write_bytes(b"\xff\xfe\xfa")

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify-bundle", str(output)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "Traceback" not in captured.err

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify-bundle", str(output), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2
    assert "Cannot read bundle manifest" in result["error"]


def test_bundle_schema_is_packaged():
    from labvault_scout.schema_registry import load_schema_text

    schema = json.loads(load_schema_text("bundle"))
    assert schema["title"] == "LabVault Scout bundle manifest schema 1"
    assert schema["properties"]["schema_version"]["const"] == "1"


def test_bundle_manifest_rejects_extra_top_level_fields(tmp_path: Path):
    import pytest
    from labvault_scout.bundle import load_bundle_manifest, manifest_payload_sha256

    source = tmp_path / "bundle_extra_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "bundle_extra_report"
    scan(source, output)

    path = output / "bundle_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    payload["manifest_sha256"] = manifest_payload_sha256(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid top-level fields"):
        load_bundle_manifest(output)


def test_bundle_manifest_rejects_empty_tool_version(tmp_path: Path):
    import pytest
    from labvault_scout.bundle import load_bundle_manifest, manifest_payload_sha256

    source = tmp_path / "bundle_tool_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "bundle_tool_report"
    scan(source, output)

    path = output / "bundle_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["tool"]["version"] = ""
    payload["manifest_sha256"] = manifest_payload_sha256(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid bundle manifest tool metadata"):
        load_bundle_manifest(output)


def test_verify_bundle_rejects_symlinked_core_artifact_when_supported(tmp_path: Path):
    import os
    import pytest
    from labvault_scout.bundle import verify_bundle

    if not hasattr(os, "symlink"):
        pytest.skip("symlinks are not supported")

    source = tmp_path / "bundle_symlink_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "bundle_symlink_report"
    scan(source, output)

    report = output / "report.html"
    outside = tmp_path / "outside.html"
    outside.write_text(report.read_text(encoding="utf-8"), encoding="utf-8")
    report.unlink()
    try:
        os.symlink(outside, report)
    except OSError:
        pytest.skip("symlink creation is unavailable in this environment")

    result = verify_bundle(output)
    assert {"path": "report.html", "issue": "SYMLINK"} in result["problems"]
    assert result["status"] == "FAILED"


def test_verify_bundle_classifies_broken_symlink_as_symlink(tmp_path: Path):
    import os
    import pytest
    from labvault_scout.bundle import verify_bundle

    if not hasattr(os, "symlink"):
        pytest.skip("symlinks are not supported")

    source = tmp_path / "bundle_broken_symlink_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "bundle_broken_symlink_report"
    scan(source, output)

    report = output / "report.html"
    missing_target = tmp_path / "missing-target.html"
    report.unlink()
    try:
        os.symlink(missing_target, report)
    except OSError:
        pytest.skip("symlink creation is unavailable in this environment")

    result = verify_bundle(output)
    assert {"path": "report.html", "issue": "SYMLINK"} in result["problems"]
    assert result["status"] == "FAILED"


def test_generated_machine_outputs_match_packaged_schema_field_contracts(tmp_path: Path):
    from labvault_scout.bundle import load_bundle_manifest
    from labvault_scout.compare import compare_reports, load_scan_report, verify_report
    from labvault_scout.schema_registry import load_schema_text

    def assert_exact_fields(payload, schema):
        assert set(payload) == set(schema["required"])
        assert set(payload) == set(schema["properties"])

    source = tmp_path / "contract_source"
    source.mkdir()
    data = source / "data.csv"
    data.write_text("x\n1\n", encoding="utf-8")

    before_dir = tmp_path / "contract_before"
    scan(source, before_dir)

    data.write_text("x\n2\n", encoding="utf-8")
    after_dir = tmp_path / "contract_after"
    scan(source, after_dir)

    scan_payload = json.loads((after_dir / "scan.json").read_text(encoding="utf-8"))
    scan_schema = json.loads(load_schema_text("scan"))
    assert_exact_fields(scan_payload, scan_schema)
    assert_exact_fields(scan_payload["tool"], scan_schema["properties"]["tool"])
    assert_exact_fields(scan_payload["provenance"], scan_schema["properties"]["provenance"])
    assert_exact_fields(scan_payload["summary"], scan_schema["properties"]["summary"])
    assert_exact_fields(scan_payload["files"][0], scan_schema["properties"]["files"]["items"])

    comparison = compare_reports(before_dir / "scan.json", after_dir / "scan.json")
    comparison_schema = json.loads(load_schema_text("comparison"))
    assert_exact_fields(comparison, comparison_schema)
    assert_exact_fields(comparison["before"], comparison_schema["properties"]["before"])
    assert_exact_fields(comparison["after"], comparison_schema["properties"]["after"])
    assert_exact_fields(comparison["metrics_delta"], comparison_schema["properties"]["metrics_delta"])
    assert_exact_fields(comparison["summary"], comparison_schema["properties"]["summary"])
    assert comparison["changes"]
    assert_exact_fields(comparison["changes"][0], comparison_schema["properties"]["changes"]["items"])

    verification = verify_report(load_scan_report(after_dir / "scan.json"))
    verification_schema = json.loads(load_schema_text("verification"))["oneOf"][0]
    assert_exact_fields(verification, verification_schema)

    bundle = load_bundle_manifest(after_dir)
    bundle_schema = json.loads(load_schema_text("bundle"))
    assert_exact_fields(bundle, bundle_schema)
    for entry in bundle["files"]:
        assert_exact_fields(entry, bundle_schema["properties"]["files"]["items"])


def test_schema1_runtime_validation_rejects_additional_properties(tmp_path: Path):
    import pytest
    from labvault_scout.compare import load_scan_report
    from labvault_scout.report import report_payload_sha256

    source = tmp_path / "strict_schema_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "strict_schema_report"
    scan(source, output)

    original = json.loads((output / "scan.json").read_text(encoding="utf-8"))

    cases = []

    top = json.loads(json.dumps(original))
    top["unexpected"] = True
    cases.append((top, "unexpected top-level fields"))

    tool = json.loads(json.dumps(original))
    tool["tool"]["unexpected"] = True
    cases.append((tool, "invalid tool metadata"))

    provenance = json.loads(json.dumps(original))
    provenance["provenance"]["unexpected"] = True
    cases.append((provenance, "invalid provenance metadata"))

    summary = json.loads(json.dumps(original))
    summary["summary"]["unexpected"] = 1
    cases.append((summary, "invalid summary fields"))

    file_row = json.loads(json.dumps(original))
    file_row["files"][0]["unexpected"] = "x"
    cases.append((file_row, "unexpected fields"))

    for index, (payload, message) in enumerate(cases):
        payload["report_sha256"] = report_payload_sha256(payload)
        path = tmp_path / f"strict_case_{index}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            load_scan_report(path)


def test_schema1_runtime_validation_rejects_invalid_summary_types(tmp_path: Path):
    import pytest
    from labvault_scout.compare import load_scan_report
    from labvault_scout.report import report_payload_sha256

    source = tmp_path / "strict_summary_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "strict_summary_report"
    scan(source, output)

    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    payload["summary"]["file_count"] = True
    payload["report_sha256"] = report_payload_sha256(payload)
    path = tmp_path / "bad_summary.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid summary file_count"):
        load_scan_report(path)


def test_schema1_runtime_validation_handles_non_string_enum_without_typeerror(tmp_path: Path):
    import pytest
    from labvault_scout.compare import load_scan_report
    from labvault_scout.report import report_payload_sha256

    source = tmp_path / "strict_enum_source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "strict_enum_report"
    scan(source, output)

    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    payload["files"][0]["risk"] = ["SAFE"]
    payload["report_sha256"] = report_payload_sha256(payload)
    path = tmp_path / "bad_enum.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="non-string risk"):
        load_scan_report(path)

def _fcs_header(version: bytes = b"FCS3.2") -> bytes:
    offsets = (58, 127, 128, 255, 0, 0)
    return version + b"    " + b"".join(f"{value:>8}".encode("ascii") for value in offsets)


def test_fcs_fixed_header_evidence():
    from labvault_scout.identifier import fcs_container_from_header, signature_from_head

    for version in (b"FCS2.0", b"FCS3.0", b"FCS3.1", b"FCS3.2"):
        header = _fcs_header(version)
        assert len(header) == 58
        assert signature_from_head(header) == "FCS"
        assert fcs_container_from_header(header, 256) == f"FCS {version[3:].decode('ascii')} fixed header"


def test_fcs_scan_is_structurally_verified(tmp_path: Path):
    source = tmp_path / "fcs_source"
    source.mkdir()
    (source / "cells.fcs").write_bytes(_fcs_header() + b"/$TOT/1/" + b" " * 190)
    output = tmp_path / "fcs_report"

    scan(source, output)
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    row = payload["files"][0]
    assert row["format"] == "Flow Cytometry Standard"
    assert row["signature"] == "FCS"
    assert row["container_type"] == "FCS 3.2 fixed header"
    assert row["signature_status"] == "verified"


def test_truncated_fcs_header_is_reviewed(tmp_path: Path):
    source = tmp_path / "truncated_fcs_source"
    source.mkdir()
    (source / "broken.fcs").write_bytes(b"FCS3.2    ")
    output = tmp_path / "truncated_fcs_report"

    scan(source, output)
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    row = payload["files"][0]
    assert row["signature"] == "FCS"
    assert row["container_type"] == "Truncated FCS header"
    assert row["signature_status"] == "unverified: expected FCS fixed header"


def test_fcs_disguised_file_is_mismatch(tmp_path: Path):
    source = tmp_path / "bad_fcs_source"
    source.mkdir()
    (source / "fake.fcs").write_bytes(b"%PDF-1.7\n")
    output = tmp_path / "bad_fcs_report"

    scan(source, output)
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    row = payload["files"][0]
    assert row["signature_status"] == "mismatch: expected FCS, detected PDF"

def _spss_header(magic: bytes = b"$FL2", byteorder: str = "little") -> bytes:
    header = bytearray(176)
    header[:4] = magic
    product = b"@(#) SPSS DATA FILE LabVault Scout synthetic test"
    header[4:4 + len(product)] = product
    header[64:68] = (2).to_bytes(4, byteorder, signed=True)
    header[68:72] = (1).to_bytes(4, byteorder, signed=True)
    compression = 2 if magic == b"$FL3" else 0
    header[72:76] = compression.to_bytes(4, byteorder, signed=True)
    header[76:80] = (0).to_bytes(4, byteorder, signed=True)
    header[80:84] = (1).to_bytes(4, byteorder, signed=True)
    return bytes(header)


def test_spss_fixed_header_evidence():
    from labvault_scout.identifier import signature_from_head, spss_container_from_header

    sav = _spss_header(b"$FL2", "little")
    zsav = _spss_header(b"$FL3", "big")
    assert signature_from_head(sav) == "SPSS"
    assert signature_from_head(zsav) == "SPSS"
    assert spss_container_from_header(sav, 176) == "SPSS SAV $FL2 fixed header (little-endian)"
    assert spss_container_from_header(zsav, 176) == "SPSS ZSAV $FL3 fixed header (big-endian)"


def test_spss_sav_scan_is_structurally_verified(tmp_path: Path):
    source = tmp_path / "spss_sav_source"
    source.mkdir()
    (source / "survey.sav").write_bytes(_spss_header(b"$FL2"))
    output = tmp_path / "spss_sav_report"

    scan(source, output)
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    row = payload["files"][0]
    assert row["format"] == "SPSS Data"
    assert row["signature"] == "SPSS"
    assert row["container_type"] == "SPSS SAV $FL2 fixed header (little-endian)"
    assert row["signature_status"] == "verified"


def test_spss_zsav_scan_is_structurally_verified(tmp_path: Path):
    source = tmp_path / "spss_zsav_source"
    source.mkdir()
    (source / "survey.zsav").write_bytes(_spss_header(b"$FL3"))
    output = tmp_path / "spss_zsav_report"

    scan(source, output)
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    row = payload["files"][0]
    assert row["format"] == "SPSS ZSAV Data"
    assert row["signature"] == "SPSS"
    assert row["container_type"] == "SPSS ZSAV $FL3 fixed header (little-endian)"
    assert row["signature_status"] == "verified"


def test_spss_wrong_magic_for_extension_is_not_verified(tmp_path: Path):
    source = tmp_path / "spss_wrong_magic_source"
    source.mkdir()
    (source / "wrong.sav").write_bytes(_spss_header(b"$FL3"))
    output = tmp_path / "spss_wrong_magic_report"

    scan(source, output)
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    row = payload["files"][0]
    assert row["signature_status"] == "unverified: expected SPSS $FL2 fixed header"


def test_truncated_spss_header_is_reviewed(tmp_path: Path):
    source = tmp_path / "spss_truncated_source"
    source.mkdir()
    (source / "broken.sav").write_bytes(b"$FL2")
    output = tmp_path / "spss_truncated_report"

    scan(source, output)
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    row = payload["files"][0]
    assert row["container_type"] == "Truncated SPSS system-file header"
    assert row["signature_status"] == "unverified: expected SPSS $FL2 fixed header"

def test_modern_stata_dta_header_evidence():
    from labvault_scout.identifier import stata_dta_container_from_header

    for release in (b"117", b"118", b"119"):
        header = (
            b"<stata_dta><header><release>"
            + release
            + b"</release><byteorder>LSF</byteorder>"
        )
        assert stata_dta_container_from_header(header) == f"Stata DTA release {release.decode('ascii')} (LSF)"

    big_endian = b"<stata_dta><header><release>118</release><byteorder>MSF</byteorder>"
    assert stata_dta_container_from_header(big_endian) == "Stata DTA release 118 (MSF)"


def test_modern_stata_dta_header_rejects_malformed_values():
    from labvault_scout.identifier import stata_dta_container_from_header

    assert stata_dta_container_from_header(b"not-stata") == ""
    assert stata_dta_container_from_header(b"<stata_dta><header><release>118") == "Truncated Stata DTA release header"
    unsupported = b"<stata_dta><header><release>999</release><byteorder>LSF</byteorder>"
    assert stata_dta_container_from_header(unsupported) == "Unsupported modern Stata DTA release"
    bad_order = b"<stata_dta><header><release>118</release><byteorder>XYZ</byteorder>"
    assert stata_dta_container_from_header(bad_order) == "Invalid Stata DTA byteorder value"

def _modern_stata_dta_header(release: bytes = b"118", byteorder: bytes = b"LSF") -> bytes:
    return (
        b"<stata_dta><header><release>"
        + release
        + b"</release><byteorder>"
        + byteorder
        + b"</byteorder>"
    )


def test_modern_stata_dta_scan_is_structurally_verified(tmp_path: Path):
    source = tmp_path / "stata_source"
    source.mkdir()
    (source / "study.dta").write_bytes(_modern_stata_dta_header() + b"<K>\x01\x00</K>")
    output = tmp_path / "stata_report"

    scan(source, output)
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    row = payload["files"][0]
    assert row["format"] == "Stata Data"
    assert row["signature"] == "STATA_DTA"
    assert row["container_type"] == "Stata DTA release 118 (LSF)"
    assert row["signature_status"] == "verified"


def test_stata_dta_disguised_file_is_mismatch(tmp_path: Path):
    source = tmp_path / "bad_stata_source"
    source.mkdir()
    (source / "fake.dta").write_bytes(b"%PDF-1.7\n")
    output = tmp_path / "bad_stata_report"

    scan(source, output)
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    row = payload["files"][0]
    assert row["signature_status"] == "mismatch: expected Stata DTA, detected PDF"


def test_legacy_or_unknown_stata_dta_remains_unverified(tmp_path: Path):
    source = tmp_path / "legacy_stata_source"
    source.mkdir()
    (source / "legacy.dta").write_bytes(b"\x72\x02" + b"\x00" * 200)
    output = tmp_path / "legacy_stata_report"

    scan(source, output)
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    row = payload["files"][0]
    assert row["signature"] == ""
    assert row["signature_status"] == "unverified: modern Stata DTA structure not detected"

def test_file_change_detection_covers_identity_and_ctime():
    from types import SimpleNamespace
    from labvault_scout.cli import _file_changed_during_scan

    baseline = SimpleNamespace(
        st_dev=1,
        st_ino=10,
        st_size=100,
        st_mtime_ns=1000,
        st_ctime_ns=2000,
    )
    same = SimpleNamespace(
        st_dev=1,
        st_ino=10,
        st_size=100,
        st_mtime_ns=1000,
        st_ctime_ns=2000,
    )
    assert _file_changed_during_scan(baseline, same) is False

    for field, value in (
        ("st_dev", 2),
        ("st_ino", 11),
        ("st_size", 101),
        ("st_mtime_ns", 1001),
        ("st_ctime_ns", 2001),
    ):
        changed = SimpleNamespace(**baseline.__dict__)
        setattr(changed, field, value)
        assert _file_changed_during_scan(baseline, changed) is True


def test_scan_reports_file_changed_during_container_inspection(tmp_path: Path, monkeypatch):
    import labvault_scout.cli as cli_module

    source = tmp_path / "changing_container_source"
    source.mkdir()
    target = source / "archive.zip"
    target.write_bytes(b"PK\x03\x04synthetic")
    output = tmp_path / "changing_container_report"

    def changing_inspect(path: Path):
        path.write_bytes(path.read_bytes() + b"changed")
        return "ZIP archive"

    monkeypatch.setattr(cli_module, "inspect_zip_container", changing_inspect)
    count = cli_module.scan(source, output)

    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert count == 0
    assert payload["files"] == []
    assert payload["errors"] == [{"path": "archive.zip", "error": "FileChangedDuringScan"}]


def test_scan_reports_file_changed_during_hash(tmp_path: Path, monkeypatch):
    import labvault_scout.cli as cli_module

    source = tmp_path / "changing_source"
    source.mkdir()
    target = source / "data.csv"
    target.write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "changing_report"

    original_hash = cli_module.sha256_with_head

    def changing_hash(path: Path):
        digest, header = original_hash(path)
        path.write_text("x\n1\n2\n", encoding="utf-8")
        return digest, header

    monkeypatch.setattr(cli_module, "sha256_with_head", changing_hash)
    count = cli_module.scan(source, output)

    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert count == 0
    assert payload["files"] == []
    assert payload["errors"] == [{"path": "data.csv", "error": "FileChangedDuringScan"}]

