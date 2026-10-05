from pathlib import Path

import pytest

from labvault_scout.bundle import load_bundle_manifest


def test_load_bundle_manifest_wraps_symlink_check_io_error(
    tmp_path: Path, monkeypatch
) -> None:
    manifest = tmp_path / "bundle_manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    original_is_symlink = Path.is_symlink

    def unreadable_is_symlink(path: Path) -> bool:
        if path == manifest:
            raise PermissionError("denied")
        return original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", unreadable_is_symlink)

    with pytest.raises(ValueError, match="Cannot read bundle manifest"):
        load_bundle_manifest(tmp_path)
