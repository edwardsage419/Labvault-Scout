from pathlib import Path

import pytest

from labvault_scout.bundle import BUNDLE_FILES, BUNDLE_MANIFEST_NAME, write_bundle_manifest


def test_bundle_manifest_replace_failure_leaves_no_temporary_file(tmp_path: Path) -> None:
    for name in BUNDLE_FILES:
        (tmp_path / name).write_bytes(b"content")

    manifest_path = tmp_path / BUNDLE_MANIFEST_NAME
    manifest_path.mkdir()

    with pytest.raises(OSError):
        write_bundle_manifest(tmp_path)

    assert manifest_path.is_dir()
    assert list(tmp_path.glob(f".{BUNDLE_MANIFEST_NAME}.*.tmp")) == []
