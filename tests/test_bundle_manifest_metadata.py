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
