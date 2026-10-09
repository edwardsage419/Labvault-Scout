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


def test_load_bundle_manifest_rejects_symlink_swap_after_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from labvault_scout.bundle import BUNDLE_FILES, manifest_payload_sha256

    manifest = tmp_path / "bundle_manifest.json"
    external = tmp_path / "external.json"
    payload = {
        "schema_version": "1",
        "tool": {"name": "LabVault Scout", "version": "0.3.2"},
        "algorithm": "sha256",
        "files": [
            {"path": name, "size": 0, "sha256": "0" * 64}
            for name in BUNDLE_FILES
        ],
    }
    payload["manifest_sha256"] = manifest_payload_sha256(payload)
    data = json.dumps(payload)
    manifest.write_text(data, encoding="utf-8")
    external.write_text(data, encoding="utf-8")

    original_is_symlink = Path.is_symlink
    swapped = False

    def swap_after_check(path: Path) -> bool:
        nonlocal swapped
        result = original_is_symlink(path)
        if path == manifest and not swapped:
            assert result is False
            manifest.unlink()
            try:
                manifest.symlink_to(external)
            except (OSError, NotImplementedError):
                pytest.skip("symlink creation is unavailable")
            swapped = True
        return result

    monkeypatch.setattr(Path, "is_symlink", swap_after_check)

    with pytest.raises(ValueError, match="Bundle manifest"):
        load_bundle_manifest(tmp_path)

    assert swapped
