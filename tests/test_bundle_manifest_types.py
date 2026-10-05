import json
from pathlib import Path

import pytest

from labvault_scout.bundle import BUNDLE_FILES, load_bundle_manifest, manifest_payload_sha256


def _write_manifest(output_dir: Path, payload: object) -> None:
    (output_dir / "bundle_manifest.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _base_manifest(files: object) -> dict:
    payload = {
        "schema_version": "1",
        "tool": {"name": "LabVault Scout", "version": "0.3.1"},
        "algorithm": "sha256",
        "files": files,
    }
    payload["manifest_sha256"] = manifest_payload_sha256(payload)
    return payload


@pytest.mark.parametrize("payload", [[], "manifest", 1, None])
def test_bundle_manifest_rejects_non_object_root(tmp_path: Path, payload: object) -> None:
    _write_manifest(tmp_path, payload)

    with pytest.raises(ValueError, match="Bundle manifest must be a JSON object"):
        load_bundle_manifest(tmp_path)


@pytest.mark.parametrize("files", [{}, "scan.json", None])
def test_bundle_manifest_rejects_non_list_files(tmp_path: Path, files: object) -> None:
    payload = _base_manifest(files)
    _write_manifest(tmp_path, payload)

    with pytest.raises(ValueError, match="Bundle manifest files must be a list"):
        load_bundle_manifest(tmp_path)


@pytest.mark.parametrize("entry", [None, [], "scan.json"])
def test_bundle_manifest_rejects_non_object_file_entries(tmp_path: Path, entry: object) -> None:
    payload = _base_manifest([entry])
    _write_manifest(tmp_path, payload)

    with pytest.raises(ValueError, match="Bundle manifest contains a non-object file entry"):
        load_bundle_manifest(tmp_path)


def test_bundle_manifest_rejects_duplicate_paths(tmp_path: Path) -> None:
    entries = [
        {"path": member, "size": 0, "sha256": "0" * 64}
        for member in BUNDLE_FILES
    ]
    entries.append(dict(entries[0]))
    payload = _base_manifest(entries)
    _write_manifest(tmp_path, payload)

    with pytest.raises(ValueError, match="Duplicate bundle manifest path"):
        load_bundle_manifest(tmp_path)


def test_bundle_manifest_rejects_absolute_path(tmp_path: Path) -> None:
    entries = [
        {"path": member, "size": 0, "sha256": "0" * 64}
        for member in BUNDLE_FILES
    ]
    entries[0]["path"] = "/scan.json"
    payload = _base_manifest(entries)
    _write_manifest(tmp_path, payload)

    with pytest.raises(ValueError, match="Unsafe bundle manifest path"):
        load_bundle_manifest(tmp_path)


def test_bundle_manifest_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "manifest-target.json"
    target.write_text("{}", encoding="utf-8")
    manifest = tmp_path / "bundle_manifest.json"
    try:
        manifest.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable in this environment")

    with pytest.raises(ValueError, match="Bundle manifest must not be a symlink"):
        load_bundle_manifest(tmp_path)


@pytest.mark.parametrize("bad_path", ["./scan.json", "nested//scan.json"])
def test_bundle_manifest_rejects_noncanonical_paths(tmp_path: Path, bad_path: str) -> None:
    entries = [
        {"path": member, "size": 0, "sha256": "0" * 64}
        for member in BUNDLE_FILES
    ]
    entries[0]["path"] = bad_path
    payload = _base_manifest(entries)
    _write_manifest(tmp_path, payload)

    with pytest.raises(ValueError, match="Unsafe bundle manifest path"):
        load_bundle_manifest(tmp_path)


def test_bundle_manifest_rejects_self_reference(tmp_path: Path) -> None:
    entries = [
        {"path": member, "size": 0, "sha256": "0" * 64}
        for member in BUNDLE_FILES
    ]
    entries[0]["path"] = "bundle_manifest.json"
    payload = _base_manifest(entries)
    _write_manifest(tmp_path, payload)

    with pytest.raises(ValueError, match="Invalid bundle manifest member"):
        load_bundle_manifest(tmp_path)


@pytest.mark.parametrize("bad_path", [None, "", 1, "scan\x00.json"])
def test_bundle_manifest_rejects_invalid_path_values(tmp_path: Path, bad_path: object) -> None:
    entries = [
        {"path": member, "size": 0, "sha256": "0" * 64}
        for member in BUNDLE_FILES
    ]
    entries[0]["path"] = bad_path
    payload = _base_manifest(entries)
    _write_manifest(tmp_path, payload)

    with pytest.raises(ValueError, match="Bundle manifest path must be a non-empty string"):
        load_bundle_manifest(tmp_path)
