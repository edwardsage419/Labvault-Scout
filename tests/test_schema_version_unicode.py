"""Version-aware validation must reject unencodable schema identifiers."""

import json
from pathlib import Path

import pytest

from labvault_scout.cli import scan
from labvault_scout.compare import (
    compare_payloads,
    load_scan_report,
    report_integrity_status,
    verify_report,
)


@pytest.mark.parametrize("codepoint", [0xD800, 0xDCFF])
def test_unencodable_future_schema_version_rejected_without_report_checksum(
    tmp_path: Path, codepoint: int,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "scan"
    assert scan(source, output) == 0
    valid = load_scan_report(output / "scan.json")
    assert report_integrity_status(valid) == "VERIFIED"

    malformed = json.loads(json.dumps(valid))
    malformed["schema_version"] = "2" + chr(codepoint)
    # Unknown schema versions historically permit an absent report checksum.
    # The identifier must still be UTF-8 encodable before accepting the report.
    malformed.pop("report_sha256")
    report_path = tmp_path / "unencodable-future-schema.json"
    report_path.write_text(json.dumps(malformed, ensure_ascii=True), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid Unicode in schema_version"):
        load_scan_report(report_path)
    assert report_integrity_status(malformed) == "MISMATCH"
    checked = verify_report(malformed)
    assert checked["status"] == "UNSUPPORTED"
    assert checked["integrity_status"] == "MISMATCH"
    assert checked["exit_code"] == 2

    comparison = compare_payloads(valid, malformed)
    assert comparison["comparison_status"] == "PARTIAL"
    assert comparison["after"]["integrity_status"] == "MISMATCH"


def test_encodable_future_schema_version_remains_loadable(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "scan"
    assert scan(source, output) == 0
    payload = load_scan_report(output / "scan.json")
    payload["schema_version"] = "2.0+révision"
    payload.pop("report_sha256")

    report_path = tmp_path / "future-schema.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert load_scan_report(report_path)["schema_version"] == "2.0+révision"
    assert report_integrity_status(payload) == "VERIFIED"
    checked = verify_report(payload)
    assert checked["status"] == "UNSUPPORTED"
    assert checked["integrity_status"] == "VERIFIED"
    assert checked["exit_code"] == 2


@pytest.mark.parametrize("codepoint", [0xD800, 0xDCFF])
@pytest.mark.parametrize("location", ["tool_version", "extension_value", "extension_key"])
def test_unencodable_future_schema_metadata_rejected_without_checksum(
    tmp_path: Path, codepoint: int, location: str,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "scan"
    assert scan(source, output) == 0
    valid = load_scan_report(output / "scan.json")
    assert report_integrity_status(valid) == "VERIFIED"

    malformed = json.loads(json.dumps(valid))
    malformed["schema_version"] = "2"
    malformed.pop("report_sha256")
    bad_text = "invalid" + chr(codepoint)
    if location == "tool_version":
        malformed["tool"]["version"] = bad_text
    elif location == "extension_value":
        malformed["future_extension"] = {"note": bad_text}
    else:
        malformed["future_extension"] = {bad_text: "note"}

    path = tmp_path / "future-metadata.json"
    path.write_text(json.dumps(malformed, ensure_ascii=True), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid Unicode"):
        load_scan_report(path)
    assert report_integrity_status(malformed) == "MISMATCH"
    checked = verify_report(malformed)
    assert checked["status"] == "UNSUPPORTED"
    assert checked["integrity_status"] == "MISMATCH"
    assert checked["exit_code"] == 2
    comparison = compare_payloads(valid, malformed)
    assert comparison["comparison_status"] == "PARTIAL"
    assert comparison["after"]["integrity_status"] == "MISMATCH"


def test_encodable_future_schema_metadata_remains_compatible(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "scan"
    assert scan(source, output) == 0
    payload = load_scan_report(output / "scan.json")
    payload["schema_version"] = "2"
    payload.pop("report_sha256")
    payload["tool"]["version"] = "révision"
    payload["future_extension"] = {"測定": "München"}

    path = tmp_path / "future-metadata-valid.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert load_scan_report(path)["future_extension"] == {"測定": "München"}
    assert report_integrity_status(payload) == "VERIFIED"
    checked = verify_report(payload)
    assert checked["status"] == "UNSUPPORTED"
    assert checked["integrity_status"] == "VERIFIED"
