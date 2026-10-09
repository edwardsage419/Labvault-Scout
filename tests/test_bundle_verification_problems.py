from pathlib import Path

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

    def changing_after_hash(path: Path) -> str:
        nonlocal changed
        digest = original_sha256_file(path)
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
        "issue": "SHA256_MISMATCH",
        "expected": expected_hash,
        "actual": actual_hash,
    } in result["problems"]



def test_verify_bundle_detects_same_content_file_replacement_between_hashes(
    tmp_path: Path, monkeypatch
) -> None:
    import labvault_scout.bundle as bundle_module

    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    original_hash = bundle_module.sha256_file
    replaced = False

    def replacing_after_first_hash(path: Path) -> str:
        nonlocal replaced
        digest = original_hash(path)
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

    def disappearing_sha256_file(path: Path) -> str:
        if path == target:
            path.unlink()
        return original_sha256_file(path)

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

    def unreadable_sha256_file(path: Path) -> str:
        if path == target:
            raise PermissionError("denied")
        return original_sha256_file(path)

    monkeypatch.setattr(bundle_module, "sha256_file", unreadable_sha256_file)

    result = bundle_module.verify_bundle(output)

    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert {
        "path": "report.html",
        "issue": "IO_ERROR",
        "error": "PermissionError",
    } in result["problems"]


def test_verify_bundle_reports_io_error_if_artifact_stat_cannot_be_read(
    tmp_path: Path, monkeypatch
) -> None:
    import labvault_scout.bundle as bundle_module

    output = _scanned_bundle(tmp_path)
    target = output / "report.html"
    original_is_symlink = Path.is_symlink
    original_exists = Path.exists
    original_is_file = Path.is_file
    original_stat = Path.stat

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

    def unreadable_stat(path: Path, *args, **kwargs):
        if path == target:
            raise PermissionError("denied")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "is_symlink", controlled_is_symlink)
    monkeypatch.setattr(Path, "exists", controlled_exists)
    monkeypatch.setattr(Path, "is_file", controlled_is_file)
    monkeypatch.setattr(Path, "stat", unreadable_stat)

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
