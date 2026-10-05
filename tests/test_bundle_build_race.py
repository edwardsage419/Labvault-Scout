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
