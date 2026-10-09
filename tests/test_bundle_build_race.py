import os
from pathlib import Path

import pytest

from labvault_scout import bundle


def test_build_bundle_manifest_rejects_artifact_changed_during_hash(
    tmp_path: Path, monkeypatch
) -> None:
    for name in bundle.BUNDLE_FILES:
        (tmp_path / name).write_bytes(b"abc")

    target = tmp_path / "scan.json"
    original_sha256_file = bundle.sha256_file

    def changing_sha256_file(path: Path) -> str:
        digest = original_sha256_file(path)
        if path == target:
            target.write_bytes(b"abcd")
        return digest

    monkeypatch.setattr(bundle, "sha256_file", changing_sha256_file)

    with pytest.raises(ValueError, match="Report artifact changed while building bundle manifest: scan.json"):
        bundle.build_bundle_manifest(tmp_path)


@pytest.mark.skipif(os.name != "nt", reason="Windows st_ctime is creation time on supported Python versions")
def test_build_bundle_manifest_rejects_same_size_change_with_restored_mtime_on_windows(
    tmp_path: Path, monkeypatch
) -> None:
    for name in bundle.BUNDLE_FILES:
        (tmp_path / name).write_bytes(b"abc")

    target = tmp_path / "scan.json"
    before = target.stat()
    original_sha256_file = bundle.sha256_file

    def changing_sha256_file(path: Path) -> str:
        digest = original_sha256_file(path)
        if path == target:
            target.write_bytes(b"xyz")
            os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
        return digest

    monkeypatch.setattr(bundle, "sha256_file", changing_sha256_file)

    with pytest.raises(ValueError, match="Report artifact changed while building bundle manifest: scan.json"):
        bundle.build_bundle_manifest(tmp_path)


def test_build_bundle_manifest_rejects_symlink_swap_after_initial_check(
    tmp_path: Path, monkeypatch
) -> None:
    for name in bundle.BUNDLE_FILES:
        (tmp_path / name).write_bytes(b"abc")

    target = tmp_path / "scan.json"
    external = tmp_path / "external.bin"
    external.write_bytes(b"abc")
    original_is_symlink = Path.is_symlink
    swapped = False

    def swap_after_check(path: Path) -> bool:
        nonlocal swapped
        result = original_is_symlink(path)
        if path == target and not swapped:
            assert not result
            target.unlink()
            try:
                target.symlink_to(external)
            except (OSError, NotImplementedError):
                pytest.skip("Symlinks unavailable")
            swapped = True
        return result

    monkeypatch.setattr(Path, "is_symlink", swap_after_check)

    with pytest.raises(ValueError, match="Report artifact is not a regular file: scan.json"):
        bundle.build_bundle_manifest(tmp_path)

    assert swapped


def test_build_bundle_manifest_rejects_transient_replacement_during_hash(
    tmp_path: Path, monkeypatch
) -> None:
    for name in bundle.BUNDLE_FILES:
        (tmp_path / name).write_bytes(b"abc")

    target = tmp_path / "scan.json"
    alternate = tmp_path / "alternate.bin"
    alternate.write_bytes(b"xyz")
    original_sha256_file = bundle.sha256_file
    replaced = False

    def transient_replacement(path: Path) -> str:
        nonlocal replaced
        if path != target or replaced:
            return original_sha256_file(path)
        replaced = True
        saved = tmp_path / "saved.bin"
        target.replace(saved)
        alternate.replace(target)
        try:
            return original_sha256_file(path)
        finally:
            target.unlink()
            saved.replace(target)

    monkeypatch.setattr(bundle, "sha256_file", transient_replacement)

    with pytest.raises(
        ValueError,
        match="Report artifact changed while building bundle manifest: scan.json",
    ):
        bundle.build_bundle_manifest(tmp_path)

    assert replaced
