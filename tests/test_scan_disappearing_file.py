import json
import os
from pathlib import Path

import pytest

import labvault_scout.cli as cli


def test_scan_records_file_disappearing_before_read(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = source / "vanished.bin"
    target.write_bytes(b"data")
    output = tmp_path / "report"

    def disappearing_iter(root, excluded=None, on_error=None):
        target.unlink()
        yield target

    monkeypatch.setattr(cli, "iter_files", disappearing_iter)

    assert cli.scan(source, output) == 0
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert payload["files"] == []
    assert payload["errors"] == [{"path": "vanished.bin", "error": "FileNotFoundError"}]


def test_scan_rejects_file_replaced_by_symlink_before_read(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = source / "swapped.bin"
    target.write_bytes(b"inside")
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    output = tmp_path / "report"

    def symlink_swap_iter(root, excluded=None, on_error=None):
        target.unlink()
        try:
            target.symlink_to(outside)
        except OSError:
            pytest.skip("symlink creation is unavailable")
        yield target

    monkeypatch.setattr(cli, "iter_files", symlink_swap_iter)

    assert cli.scan(source, output) == 0
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert payload["files"] == []
    assert payload["errors"] == [
        {"path": "swapped.bin", "error": "FileChangedDuringScan"}
    ]


def test_scan_binds_first_hash_to_entry_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = source / "changed.bin"
    target.write_bytes(b"original")
    output = tmp_path / "report"
    original_classify = cli.classify

    def replacing_classify(path: Path, rules):
        rule = original_classify(path, rules)
        if path == target:
            path.unlink()
            path.write_bytes(b"replacement-content")
        return rule

    monkeypatch.setattr(cli, "classify", replacing_classify)

    assert cli.scan(source, output) == 0
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert payload["files"] == []
    assert payload["errors"] == [
        {"path": "changed.bin", "error": "FileChangedDuringScan"}
    ]


@pytest.mark.skipif(os.name != "nt", reason="Windows metadata semantics")
def test_scan_detects_same_size_change_with_restored_mtime_on_windows(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = source / "changed.bin"
    target.write_bytes(b"abcd")
    output = tmp_path / "report"
    original_stat = target.stat()
    original_sha256_with_head = cli.hashing_module.sha256_with_head

    def changing_after_hash(path: Path, *args, expected_stat=None, **kwargs):
        digest, header = original_sha256_with_head(
            path, *args, expected_stat=expected_stat, **kwargs
        )
        if path == target:
            path.write_bytes(b"wxyz")
            os.utime(
                path,
                ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
            )
        return digest, header

    monkeypatch.setattr(cli.hashing_module, "sha256_with_head", changing_after_hash)

    assert cli.scan(source, output) == 0
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert payload["files"] == []
    assert payload["errors"] == [
        {"path": "changed.bin", "error": "FileChangedDuringScan"}
    ]


def test_scan_records_directory_symlink_check_error_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    inaccessible = source / "unreadable"
    inaccessible.mkdir()
    (inaccessible / "skipped.bin").write_bytes(b"not scanned")
    (source / "healthy.bin").write_bytes(b"safe")
    output = tmp_path / "report"

    original_is_symlink = Path.is_symlink

    def failing_directory_check(path: Path) -> bool:
        if path == inaccessible:
            raise PermissionError("cannot inspect directory")
        return original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", failing_directory_check)

    assert cli.scan(source, output) == 1
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert [row["path"] for row in payload["files"]] == ["healthy.bin"]
    assert payload["errors"] == [
        {"path": "unreadable", "error": "PermissionError"}
    ]
    assert payload["summary"]["file_count"] == 1
    assert payload["summary"]["error_count"] == 1


def test_scan_excludes_report_directory_when_path_resolution_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "healthy.bin").write_bytes(b"source data")
    output = source / "report"
    output.mkdir()
    (output / "old-report.bin").write_bytes(b"previous report")

    original_resolve = Path.resolve
    output_resolve_calls = 0

    def failing_report_resolve(path: Path, *args, **kwargs) -> Path:
        nonlocal output_resolve_calls
        if path == output:
            output_resolve_calls += 1
            # scan() and iter_files() first canonicalize the output directory.
            if output_resolve_calls > 2:
                raise PermissionError("cannot resolve existing report directory")
        elif output in path.parents:
            raise PermissionError("cannot resolve file in report directory")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", failing_report_resolve)

    assert cli.scan(source, output) == 1

    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert [row["path"] for row in payload["files"]] == ["healthy.bin"]
    assert payload["errors"] == []
    assert payload["summary"]["file_count"] == 1
    assert payload["summary"]["error_count"] == 0


@pytest.mark.parametrize("entry_type", ["file", "directory"])
def test_scan_records_unresolvable_source_path_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry_type: str
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "healthy.bin").write_bytes(b"healthy")
    output = source / "report"
    output.mkdir()
    (output / "prior.bin").write_bytes(b"old report")

    blocked = source / "blocked"
    if entry_type == "directory":
        blocked.mkdir()
        (blocked / "secret.bin").write_bytes(b"not safe to scan")
    else:
        blocked.write_bytes(b"not safe to scan")

    original_resolve = Path.resolve

    def fail_source_resolution(path: Path, *args, **kwargs) -> Path:
        if path == blocked:
            raise PermissionError("cannot resolve source entry")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fail_source_resolution)

    assert cli.scan(source, output) == 1

    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert [row["path"] for row in payload["files"]] == ["healthy.bin"]
    assert payload["errors"] == [
        {"path": "blocked", "error": "PermissionError"}
    ]
    assert payload["summary"]["file_count"] == 1
    assert payload["summary"]["error_count"] == 1


def test_scan_records_zip_container_read_error_and_preserves_report_integrity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import labvault_scout.identifier as identifier
    from labvault_scout.compare import load_scan_report, verify_report

    source = tmp_path / "source"
    source.mkdir()
    blocked = source / "blocked.zip"
    blocked.write_bytes(bytes.fromhex("504b0304") + b"synthetic")
    (source / "healthy.csv").write_text("sample data", encoding="utf-8")
    output = tmp_path / "report"

    original_zipfile = identifier.zipfile.ZipFile

    def fail_zip_container_open(path, *args, **kwargs):
        if Path(path) == blocked:
            raise PermissionError("ZIP container read denied")
        return original_zipfile(path, *args, **kwargs)

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_zip_container_open)

    assert cli.scan(source, output) == 1

    payload = load_scan_report(output / "scan.json")
    assert [row["path"] for row in payload["files"]] == ["healthy.csv"]
    assert payload["errors"] == [
        {"path": "blocked.zip", "error": "PermissionError"}
    ]
    assert payload["summary"]["file_count"] == 1
    assert payload["summary"]["error_count"] == 1

    verification = verify_report(payload)
    assert verification["status"] == "VERIFIED"
    assert verification["error_count"] == 1


def test_scan_records_hdf5_container_read_error_without_false_format_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from labvault_scout.compare import load_scan_report, verify_report

    source = tmp_path / "source"
    source.mkdir()
    blocked = source / "blocked.h5"
    blocked.write_bytes(
        b"U" * 512 + bytes.fromhex("894844460d0a1a0a") + bytes([2]) + bytes(32)
    )
    (source / "healthy.csv").write_text("sample data", encoding="utf-8")
    output = tmp_path / "report"

    original_open = Path.open
    blocked_opens = 0

    def deny_second_hdf5_open(path: Path, *args, **kwargs):
        nonlocal blocked_opens
        if path == blocked:
            blocked_opens += 1
            if blocked_opens == 2:
                raise PermissionError("HDF5 superblock read denied")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_second_hdf5_open)

    assert cli.scan(source, output) == 1
    assert blocked_opens == 2

    payload = load_scan_report(output / "scan.json")
    assert [row["path"] for row in payload["files"]] == ["healthy.csv"]
    assert payload["errors"] == [
        {"path": "blocked.h5", "error": "PermissionError"}
    ]
    assert payload["summary"]["file_count"] == 1
    assert payload["summary"]["error_count"] == 1
    verification = verify_report(payload)
    assert verification["status"] == "VERIFIED"
    assert verification["error_count"] == 1


def test_scan_records_gzip_nifti_inspection_io_error_and_keeps_valid_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import gzip

    import labvault_scout.identifier as identifier
    from labvault_scout.compare import load_scan_report, verify_report

    source = tmp_path / "source"
    source.mkdir()
    blocked = source / "blocked.nii.gz"
    blocked.write_bytes(gzip.compress(bytes(348)))
    (source / "healthy.csv").write_text("sample data", encoding="utf-8")
    output = tmp_path / "report"

    original_open = identifier.gzip.open

    def fail_gzip_open(path, *args, **kwargs):
        if Path(path) == blocked:
            raise PermissionError("GZIP content read denied")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(identifier.gzip, "open", fail_gzip_open)

    assert cli.scan(source, output) == 1
    payload = load_scan_report(output / "scan.json")
    assert [row["path"] for row in payload["files"]] == ["healthy.csv"]
    assert payload["errors"] == [
        {"path": "blocked.nii.gz", "error": "PermissionError"}
    ]
    assert payload["summary"]["file_count"] == 1
    assert payload["summary"]["error_count"] == 1
    verification = verify_report(payload)
    assert verification["status"] == "VERIFIED"
    assert verification["error_count"] == 1


def test_scan_invalid_gzip_stream_remains_format_evidence(tmp_path: Path) -> None:
    from labvault_scout.compare import load_scan_report

    source = tmp_path / "source"
    source.mkdir()
    # GZIP magic followed by an invalid compression method.
    (source / "corrupt.nii.gz").write_bytes(bytes.fromhex("1f8b00") + bytes(32))
    output = tmp_path / "report"

    assert cli.scan(source, output) == 1

    payload = load_scan_report(output / "scan.json")
    assert payload["errors"] == []
    assert [row["path"] for row in payload["files"]] == ["corrupt.nii.gz"]
    assert payload["files"][0]["signature"] == "GZIP"
    assert payload["files"][0]["container_type"] == "Invalid GZIP container"


def test_scan_records_zip_mimetype_member_io_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import zipfile

    import labvault_scout.identifier as identifier
    from labvault_scout.compare import load_scan_report, verify_report

    source = tmp_path / "source"
    source.mkdir()
    blocked = source / "unreadable.ods"
    with zipfile.ZipFile(blocked, "w") as archive:
        archive.writestr(
            "mimetype",
            "application/vnd.oasis.opendocument.spreadsheet",
        )
    (source / "healthy.csv").write_text("sample data", encoding="utf-8")
    output = tmp_path / "report"

    original_open = identifier.zipfile.ZipFile.open

    def fail_mimetype_open(archive, member, *args, **kwargs):
        if Path(archive.filename) == blocked and member == "mimetype":
            raise PermissionError("ZIP mimetype member read denied")
        return original_open(archive, member, *args, **kwargs)

    monkeypatch.setattr(identifier.zipfile.ZipFile, "open", fail_mimetype_open)

    assert cli.scan(source, output) == 1

    payload = load_scan_report(output / "scan.json")
    assert [row["path"] for row in payload["files"]] == ["healthy.csv"]
    assert payload["errors"] == [
        {"path": "unreadable.ods", "error": "PermissionError"}
    ]
    assert payload["summary"]["file_count"] == 1
    assert payload["summary"]["error_count"] == 1
    verified = verify_report(payload)
    assert verified["status"] == "VERIFIED"
    assert verified["error_count"] == 1
