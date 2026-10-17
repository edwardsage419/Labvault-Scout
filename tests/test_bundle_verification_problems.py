import os
from pathlib import Path

import pytest

from labvault_scout.bundle import load_bundle_manifest, verify_bundle
from labvault_scout.cli import scan
from labvault_scout.hashing import sha256_file


def _scanned_bundle(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "report"
    scan(source, output)
    return output


def test_verify_bundle_detects_non_regular_core_file(tmp_path: Path) -> None:
    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    target.unlink()
    target.mkdir()

    result = verify_bundle(output)

    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert {"path": "report.html", "issue": "NOT_REGULAR_FILE"} in result["problems"]


def test_verify_bundle_reports_file_change_if_directory_swapped_after_file_check(
    tmp_path: Path, monkeypatch
) -> None:
    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    saved = output / "saved-report.tmp"
    original_is_file = Path.is_file
    swapped = False

    def swap_after_file_check(path: Path, *args, **kwargs) -> bool:
        nonlocal swapped
        result = original_is_file(path, *args, **kwargs)
        if path == target and not swapped:
            assert result
            target.replace(saved)
            target.mkdir()
            swapped = True
        return result

    monkeypatch.setattr(Path, "is_file", swap_after_file_check)

    result = verify_bundle(output)

    assert swapped
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert {
        "path": "report.html",
        "issue": "IO_ERROR",
        "error": "FileChangedDuringScan",
    } in result["problems"]


def test_verify_bundle_detects_symlink_swap_after_file_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    moved = output / "original-report.tmp"
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"x")
    assert target.stat().st_size != outside.stat().st_size
    original_is_file = Path.is_file
    swapped = False

    def swap_after_file_check(path: Path, *args, **kwargs) -> bool:
        nonlocal swapped
        is_file = original_is_file(path, *args, **kwargs)
        if path == target and not swapped:
            assert is_file
            target.replace(moved)
            try:
                target.symlink_to(outside)
            except (OSError, NotImplementedError):
                pytest.skip("Symlink creation is unavailable")
            swapped = True
        return is_file

    monkeypatch.setattr(Path, "is_file", swap_after_file_check)

    result = verify_bundle(output)

    assert swapped
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert {
        "path": "report.html",
        "issue": "IO_ERROR",
        "error": "FileChangedDuringScan",
    } in result["problems"]


def test_verify_bundle_detects_size_mismatch(tmp_path: Path) -> None:
    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    expected_size = target.stat().st_size
    target.write_bytes(target.read_bytes() + b"x")

    result = verify_bundle(output)

    problem = next(item for item in result["problems"] if item["path"] == "report.html")
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert problem == {
        "path": "report.html",
        "issue": "SIZE_MISMATCH",
        "expected": expected_size,
        "actual": expected_size + 1,
    }


def test_verify_bundle_detects_sha256_mismatch(tmp_path: Path) -> None:
    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    manifest = load_bundle_manifest(output)
    expected_hash = next(
        entry["sha256"] for entry in manifest["files"] if entry["path"] == "report.html"
    )

    original = target.read_bytes()
    assert original
    replacement = b"0" if original[:1] != b"0" else b"1"
    target.write_bytes(replacement + original[1:])
    assert target.stat().st_size == len(original)
    actual_hash = sha256_file(target)
    assert actual_hash != expected_hash

    result = verify_bundle(output)

    problem = next(item for item in result["problems"] if item["path"] == "report.html")
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert problem == {
        "path": "report.html",
        "issue": "SHA256_MISMATCH",
        "expected": expected_hash,
        "actual": actual_hash,
    }


def test_verify_bundle_detects_artifact_changed_after_initial_hash(
    tmp_path: Path, monkeypatch
) -> None:
    import labvault_scout.bundle as bundle_module

    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    manifest = load_bundle_manifest(output)
    expected_hash = next(
        entry["sha256"] for entry in manifest["files"] if entry["path"] == "report.html"
    )
    original_sha256_file = bundle_module.sha256_file
    changed = False

    def changing_after_hash(path: Path, **kwargs) -> str:
        nonlocal changed
        digest = original_sha256_file(path, **kwargs)
        if path == target and not changed:
            original = path.read_bytes()
            replacement = b"0" if original[:1] != b"0" else b"1"
            path.write_bytes(replacement + original[1:])
            changed = True
        return digest

    monkeypatch.setattr(bundle_module, "sha256_file", changing_after_hash)

    result = bundle_module.verify_bundle(output)
    actual_hash = original_sha256_file(target)

    assert actual_hash != expected_hash
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert {
        "path": "report.html",
        "issue": "IO_ERROR",
        "error": "FileChangedDuringScan",
    } in result["problems"]



@pytest.mark.skipif(os.name != "nt", reason="Windows restored-mtime regression")
def test_verify_bundle_detects_windows_same_size_write_with_restored_mtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import labvault_scout.bundle as bundle_module

    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    original_content = target.read_bytes()
    assert original_content
    before = target.lstat()
    changed_content = (b"0" if original_content[:1] != b"0" else b"1") + original_content[1:]
    expected_digest = sha256_file(target)
    assert len(changed_content) == len(original_content)
    original_hash = bundle_module.sha256_file
    changed = False

    def rewrite_after_first_hash(path: Path, **kwargs) -> str:
        nonlocal changed
        digest = original_hash(path, **kwargs)
        if path == target and not changed:
            changed = True
            target.write_bytes(changed_content)
            os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
            after = target.lstat()
            assert after.st_size == before.st_size
            if (
                after.st_mtime_ns != before.st_mtime_ns
                or after.st_ctime_ns != before.st_ctime_ns
            ):
                pytest.skip("Filesystem did not preserve original timestamps")
        return digest

    monkeypatch.setattr(bundle_module, "sha256_file", rewrite_after_first_hash)

    result = bundle_module.verify_bundle(output)

    assert changed
    assert sha256_file(target) != expected_digest
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert {
        "path": "report.html",
        "issue": "SHA256_MISMATCH",
        "expected": expected_digest,
        "actual": sha256_file(target),
    } in result["problems"]


def test_verify_bundle_detects_same_content_file_replacement_between_hashes(
    tmp_path: Path, monkeypatch
) -> None:
    import labvault_scout.bundle as bundle_module

    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    original_hash = bundle_module.sha256_file
    replaced = False

    def replacing_after_first_hash(path: Path, **kwargs) -> str:
        nonlocal replaced
        digest = original_hash(path, **kwargs)
        if path == target and not replaced:
            replacement = output / "replacement.tmp"
            replacement.write_bytes(target.read_bytes())
            replacement.replace(target)
            replaced = True
        return digest

    monkeypatch.setattr(bundle_module, "sha256_file", replacing_after_first_hash)

    result = bundle_module.verify_bundle(output)

    assert replaced
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert {
        "path": "report.html",
        "issue": "IO_ERROR",
        "error": "FileChangedDuringScan",
    } in result["problems"]


def test_verify_bundle_reports_missing_if_artifact_disappears_before_hash(
    tmp_path: Path, monkeypatch
) -> None:
    import labvault_scout.bundle as bundle_module

    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    original_sha256_file = bundle_module.sha256_file

    def disappearing_sha256_file(path: Path, **kwargs) -> str:
        if path == target:
            path.unlink()
        return original_sha256_file(path, **kwargs)

    monkeypatch.setattr(bundle_module, "sha256_file", disappearing_sha256_file)

    result = bundle_module.verify_bundle(output)

    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert {"path": "report.html", "issue": "MISSING"} in result["problems"]


def test_verify_bundle_reports_io_error_if_artifact_hash_cannot_be_read(
    tmp_path: Path, monkeypatch
) -> None:
    import labvault_scout.bundle as bundle_module

    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    original_sha256_file = bundle_module.sha256_file

    def unreadable_sha256_file(path: Path, **kwargs) -> str:
        if path == target:
            raise PermissionError("denied")
        return original_sha256_file(path, **kwargs)

    monkeypatch.setattr(bundle_module, "sha256_file", unreadable_sha256_file)

    result = bundle_module.verify_bundle(output)

    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert {
        "path": "report.html",
        "issue": "IO_ERROR",
        "error": "PermissionError",
    } in result["problems"]


def test_verify_bundle_reports_io_error_if_artifact_lstat_cannot_be_read(
    tmp_path: Path, monkeypatch
) -> None:
    import labvault_scout.bundle as bundle_module

    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    original_is_symlink = Path.is_symlink
    original_exists = Path.exists
    original_is_file = Path.is_file
    original_lstat = Path.lstat

    def controlled_is_symlink(path: Path) -> bool:
        if path == target:
            return False
        return original_is_symlink(path)

    def controlled_exists(path: Path) -> bool:
        if path == target:
            return True
        return original_exists(path)

    def controlled_is_file(path: Path) -> bool:
        if path == target:
            return True
        return original_is_file(path)

    def unreadable_lstat(path: Path, *args, **kwargs):
        if path == target:
            raise PermissionError("denied")
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "is_symlink", controlled_is_symlink)
    monkeypatch.setattr(Path, "exists", controlled_exists)
    monkeypatch.setattr(Path, "is_file", controlled_is_file)
    monkeypatch.setattr(Path, "lstat", unreadable_lstat)

    result = bundle_module.verify_bundle(output)

    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert {
        "path": "report.html",
        "issue": "IO_ERROR",
        "error": "PermissionError",
    } in result["problems"]


def test_verify_bundle_reports_io_error_if_artifact_symlink_check_fails(
    tmp_path: Path, monkeypatch
) -> None:
    import labvault_scout.bundle as bundle_module

    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    original_is_symlink = Path.is_symlink

    def unreadable_is_symlink(path: Path) -> bool:
        if path == target:
            raise PermissionError("denied")
        return original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", unreadable_is_symlink)

    result = bundle_module.verify_bundle(output)

    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert {
        "path": "report.html",
        "issue": "IO_ERROR",
        "error": "PermissionError",
    } in result["problems"]


def test_verify_bundle_detects_symlink_swap_after_second_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import labvault_scout.bundle as bundle_module

    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    external = output / "original-report.tmp"
    original_hash = bundle_module.sha256_file
    hash_calls = 0
    swapped = False

    def swapping_after_second_hash(path: Path, **kwargs) -> str:
        nonlocal hash_calls, swapped
        digest = original_hash(path, **kwargs)
        if path == target:
            hash_calls += 1
            if hash_calls == 2:
                target.replace(external)
                try:
                    target.symlink_to(external)
                except (OSError, NotImplementedError):
                    pytest.skip("Symlink creation is unavailable")
                swapped = True
        return digest

    monkeypatch.setattr(bundle_module, "sha256_file", swapping_after_second_hash)

    result = bundle_module.verify_bundle(output)

    assert swapped
    assert hash_calls == 2
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert {
        "path": "report.html",
        "issue": "IO_ERROR",
        "error": "FileChangedDuringScan",
    } in result["problems"]



def test_verify_bundle_rejects_transient_same_content_swap_during_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import labvault_scout.bundle as bundle_module

    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    saved = output / "saved-original.tmp"
    replacement = output / "matching-content.tmp"
    replacement.write_bytes(target.read_bytes())
    original_sha256_file = bundle_module.sha256_file
    swapped = False

    def transient_swap(path: Path, **kwargs) -> str:
        nonlocal swapped
        if path != target or swapped:
            return original_sha256_file(path, **kwargs)

        swapped = True
        target.replace(saved)
        replacement.replace(target)
        try:
            return original_sha256_file(path, **kwargs)
        finally:
            target.unlink()
            saved.replace(target)

    monkeypatch.setattr(bundle_module, "sha256_file", transient_swap)

    result = bundle_module.verify_bundle(output)

    assert swapped
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert {
        "path": "report.html",
        "issue": "IO_ERROR",
        "error": "FileChangedDuringScan",
    } in result["problems"]
