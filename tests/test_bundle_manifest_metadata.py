import json
from pathlib import Path

import pytest

from labvault_scout.bundle import BUNDLE_FILES, load_bundle_manifest, manifest_payload_sha256


def _write_manifest(output_dir: Path, payload: dict) -> None:
    (output_dir / "bundle_manifest.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _base_manifest() -> dict:
    payload = {
        "schema_version": "1",
        "tool": {"name": "LabVault Scout", "version": "0.3.1"},
        "algorithm": "sha256",
        "files": [
            {"path": member, "size": 0, "sha256": "0" * 64}
            for member in BUNDLE_FILES
        ],
    }
    payload["manifest_sha256"] = manifest_payload_sha256(payload)
    return payload


@pytest.mark.parametrize("bad_schema", [None, 1, True, "", "2"])
def test_bundle_manifest_rejects_invalid_schema_versions(
    tmp_path: Path,
    bad_schema: object,
) -> None:
    payload = _base_manifest()
    payload["schema_version"] = bad_schema
    payload["manifest_sha256"] = manifest_payload_sha256(payload)
    _write_manifest(tmp_path, payload)

    with pytest.raises(ValueError, match="Unsupported bundle manifest schema"):
        load_bundle_manifest(tmp_path)


@pytest.mark.parametrize("bad_algorithm", [None, 1, True, "", "SHA256", "md5"])
def test_bundle_manifest_rejects_invalid_algorithms(
    tmp_path: Path,
    bad_algorithm: object,
) -> None:
    payload = _base_manifest()
    payload["algorithm"] = bad_algorithm
    payload["manifest_sha256"] = manifest_payload_sha256(payload)
    _write_manifest(tmp_path, payload)

    with pytest.raises(ValueError, match="Unsupported bundle manifest algorithm"):
        load_bundle_manifest(tmp_path)


@pytest.mark.parametrize(
    "bad_checksum",
    [None, 1, True, "", "0" * 63, "A" * 64, "g" * 64],
)
def test_bundle_manifest_rejects_invalid_checksum_formats(
    tmp_path: Path,
    bad_checksum: object,
) -> None:
    payload = _base_manifest()
    payload["manifest_sha256"] = bad_checksum
    _write_manifest(tmp_path, payload)

    with pytest.raises(ValueError, match="Invalid bundle manifest checksum"):
        load_bundle_manifest(tmp_path)


def test_bundle_manifest_rejects_checksum_mismatch(tmp_path: Path) -> None:
    payload = _base_manifest()
    checksum = payload["manifest_sha256"]
    replacement = "0" if checksum[0] != "0" else "1"
    payload["manifest_sha256"] = replacement + checksum[1:]
    _write_manifest(tmp_path, payload)

    with pytest.raises(ValueError, match="Bundle manifest checksum mismatch"):
        load_bundle_manifest(tmp_path)
