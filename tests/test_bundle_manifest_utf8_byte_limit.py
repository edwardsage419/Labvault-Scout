"""UTF-8 byte-size boundary checks for bundle manifest loading."""

import json
from pathlib import Path

import pytest

from labvault_scout.bundle import (
    BUNDLE_FILES,
    MAX_BUNDLE_MANIFEST_BYTES,
    load_bundle_manifest,
    manifest_payload_sha256,
)


def _manifest_with_version(version: str) -> dict:
    payload = {
        "schema_version": "1",
        "tool": {"name": "LabVault Scout", "version": version},
        "algorithm": "sha256",
        "files": [
            {"path": member, "size": 0, "sha256": "0" * 64}
            for member in BUNDLE_FILES
        ],
    }
    payload["manifest_sha256"] = manifest_payload_sha256(payload)
    return payload


def test_manifest_rejects_oversized_utf8_bytes_even_when_character_count_fits(
    tmp_path: Path,
) -> None:
    payload = _manifest_with_version("é" * (MAX_BUNDLE_MANIFEST_BYTES // 2))
    text = json.dumps(payload, ensure_ascii=False)
    encoded = text.encode("utf-8")
    assert len(text) < MAX_BUNDLE_MANIFEST_BYTES
    assert len(encoded) > MAX_BUNDLE_MANIFEST_BYTES
    (tmp_path / "bundle_manifest.json").write_bytes(encoded)

    with pytest.raises(ValueError, match="Bundle manifest exceeds maximum size"):
        load_bundle_manifest(tmp_path)


def test_manifest_accepts_exact_utf8_byte_limit_with_multibyte_text(
    tmp_path: Path,
) -> None:
    version = "é" * ((MAX_BUNDLE_MANIFEST_BYTES - 2048) // 2)
    payload = _manifest_with_version(version)
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    assert len(encoded) < MAX_BUNDLE_MANIFEST_BYTES
    padded = encoded + b" " * (MAX_BUNDLE_MANIFEST_BYTES - len(encoded))
    assert len(padded) == MAX_BUNDLE_MANIFEST_BYTES
    (tmp_path / "bundle_manifest.json").write_bytes(padded)

    loaded = load_bundle_manifest(tmp_path)
    assert loaded["tool"]["version"] == version
    assert loaded["manifest_sha256"] == payload["manifest_sha256"]
