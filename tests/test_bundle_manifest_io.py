import json
import os
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


@pytest.mark.skipif(os.name == "nt", reason="Windows st_ctime tracks creation time")
def test_load_bundle_manifest_rejects_same_size_change_with_restored_mtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from labvault_scout.bundle import BUNDLE_FILES, manifest_payload_sha256

    manifest = tmp_path / "bundle_manifest.json"
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
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    original_lstat = Path.lstat
    manifest_checks = 0
    changed = False

    def changing_lstat(path: Path, *args, **kwargs):
        nonlocal manifest_checks, changed
        if path == manifest:
            manifest_checks += 1
            # is_symlink(), pre-read lstat(), then post-read lstat().
            if manifest_checks == 3:
                before = original_lstat(path, *args, **kwargs)
                content = manifest.read_bytes()
                replaced = content.replace(
                    b'"algorithm": "sha256"',
                    b'"algorithm": "sha25x"',
                )
                assert len(replaced) == len(content)
                assert replaced != content
                manifest.write_bytes(replaced)
                os.utime(manifest, ns=(before.st_atime_ns, before.st_mtime_ns))
                if original_lstat(path, *args, **kwargs).st_ctime_ns == before.st_ctime_ns:
                    pytest.skip("File system cannot distinguish metadata changes")
                changed = True
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", changing_lstat)

    with pytest.raises(ValueError, match="Bundle manifest changed during read"):
        from labvault_scout.bundle import load_bundle_manifest

        load_bundle_manifest(tmp_path)

    assert changed


def test_load_bundle_manifest_wraps_json_parser_recursion_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "bundle_manifest.json"
    manifest.write_text("[" * 4000 + "0" + "]" * 4000, encoding="utf-8")

    def raise_recursion_error(
        text: str, *, object_pairs_hook: object = None,
        parse_constant: object = None, parse_float: object = None
    ) -> object:
        assert text.startswith("[" * 4000)
        assert callable(object_pairs_hook)
        assert callable(parse_constant)
        assert callable(parse_float)
        raise RecursionError("JSON nesting exceeds parser recursion limit")

    monkeypatch.setattr(json, "loads", raise_recursion_error)
    with pytest.raises(ValueError, match="Cannot read bundle manifest"):
        load_bundle_manifest(tmp_path)


def test_load_bundle_manifest_wraps_excessive_integer_digits(tmp_path: Path) -> None:
    number = "9" * 5000
    try:
        json.loads(number)
    except ValueError:
        pass
    else:
        pytest.skip("JSON parser does not enforce an integer digit limit")

    manifest = tmp_path / "bundle_manifest.json"
    manifest.write_text(number, encoding="utf-8")

    with pytest.raises(ValueError, match="Cannot read bundle manifest"):
        load_bundle_manifest(tmp_path)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_load_bundle_manifest_rejects_nonstandard_json_constant(
    tmp_path: Path, constant: str
) -> None:
    from labvault_scout.bundle import BUNDLE_FILES, manifest_payload_sha256

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
    encoded = json.dumps(payload)
    assert '"size": 0' in encoded
    malformed = encoded.replace('"size": 0', f'"size": {constant}', 1)
    (tmp_path / "bundle_manifest.json").write_text(malformed, encoding="utf-8")

    with pytest.raises(ValueError, match="Cannot read bundle manifest") as exc_info:
        load_bundle_manifest(tmp_path)
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert f"Non-standard bundle manifest JSON constant: {constant}" in str(
        exc_info.value.__cause__
    )


@pytest.mark.parametrize("number", ["1e999", "-1e999"])
def test_load_bundle_manifest_rejects_float_overflow(
    tmp_path: Path, number: str
) -> None:
    from labvault_scout.bundle import BUNDLE_FILES, manifest_payload_sha256

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
    encoded = json.dumps(payload)
    assert '"size": 0' in encoded
    malformed = encoded.replace('"size": 0', f'"size": {number}', 1)
    (tmp_path / "bundle_manifest.json").write_text(malformed, encoding="utf-8")

    with pytest.raises(ValueError, match="Cannot read bundle manifest") as exc_info:
        load_bundle_manifest(tmp_path)
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "Bundle manifest JSON number exceeds floating-point range" in str(
        exc_info.value.__cause__
    )
