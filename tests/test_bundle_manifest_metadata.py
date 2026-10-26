import json
from pathlib import Path

import pytest

from labvault_scout.bundle import (
    BUNDLE_FILES,
    MAX_BUNDLE_MANIFEST_BYTES,
    MAX_BUNDLE_JSON_INTEGER_DIGITS,
    load_bundle_manifest,
    manifest_payload_sha256,
)


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


@pytest.mark.parametrize("codepoint", [0xD800, 0xDCFF])
@pytest.mark.parametrize("location", ["tool_version", "member_path"])
def test_bundle_manifest_rejects_unencodable_json_text(
    tmp_path: Path, codepoint: int, location: str,
) -> None:
    payload = _base_manifest()
    malformed = "invalid" + chr(codepoint)
    if location == "tool_version":
        payload["tool"]["version"] = malformed
    else:
        payload["files"][0]["path"] = malformed
    # JSON escapes permit lone surrogates; manifest hashing must reject them
    # with a consistent validation error rather than UnicodeEncodeError.
    _write_manifest(tmp_path, payload)
    with pytest.raises(ValueError, match="Bundle manifest contains invalid Unicode") as caught:
        load_bundle_manifest(tmp_path)
    assert isinstance(caught.value.__cause__, UnicodeEncodeError)


@pytest.mark.parametrize("excess", [1, 4096])
def test_bundle_manifest_rejects_oversized_json(tmp_path: Path, excess: int) -> None:
    payload = _base_manifest()
    encoded = json.dumps(payload).encode("utf-8")
    assert len(encoded) < MAX_BUNDLE_MANIFEST_BYTES
    manifest = tmp_path / "bundle_manifest.json"
    manifest.write_bytes(
        encoded + b" " * (MAX_BUNDLE_MANIFEST_BYTES + excess - len(encoded))
    )
    with pytest.raises(ValueError, match="Bundle manifest exceeds maximum size"):
        load_bundle_manifest(tmp_path)


def test_bundle_manifest_accepts_exact_size_limit(tmp_path: Path) -> None:
    payload = _base_manifest()
    encoded = json.dumps(payload).encode("utf-8")
    assert len(encoded) < MAX_BUNDLE_MANIFEST_BYTES
    manifest = tmp_path / "bundle_manifest.json"
    manifest.write_bytes(encoded + b" " * (MAX_BUNDLE_MANIFEST_BYTES - len(encoded)))
    loaded = load_bundle_manifest(tmp_path)
    assert loaded["manifest_sha256"] == payload["manifest_sha256"]


@pytest.mark.parametrize("sign", ["", "-"])
def test_bundle_manifest_rejects_overlong_json_integer(
    tmp_path: Path, sign: str,
) -> None:
    payload = json.dumps(_base_manifest())
    assert '"size": 0' in payload
    overlong = sign + "9" * (MAX_BUNDLE_JSON_INTEGER_DIGITS + 1)
    malformed = payload.replace('"size": 0', f'"size": {overlong}', 1)
    (tmp_path / "bundle_manifest.json").write_text(malformed, encoding="utf-8")

    with pytest.raises(ValueError, match="Cannot read bundle manifest") as caught:
        load_bundle_manifest(tmp_path)
    assert isinstance(caught.value.__cause__, ValueError)
    assert "integer exceeds digit limit" in str(caught.value.__cause__)


def test_bundle_manifest_accepts_json_integer_at_digit_limit(tmp_path: Path) -> None:
    payload = _base_manifest()
    size = int("9" * MAX_BUNDLE_JSON_INTEGER_DIGITS)
    payload["files"][0]["size"] = size
    payload["manifest_sha256"] = manifest_payload_sha256(payload)
    _write_manifest(tmp_path, payload)

    assert load_bundle_manifest(tmp_path)["files"][0]["size"] == size
