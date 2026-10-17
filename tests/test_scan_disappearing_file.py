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
