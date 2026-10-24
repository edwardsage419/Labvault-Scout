import json
import sys
from pathlib import Path

import pytest

from labvault_scout.cli import main, scan
from labvault_scout.compare import load_scan_report


def test_cli_verify_malformed_json_is_concise_and_json_capable(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    bad = tmp_path / "malformed-report.json"
    bad.write_text("{not-json", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(bad)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "Cannot read scan report" in captured.err
    assert "Traceback" not in captured.err

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(bad), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2
    assert "Cannot read scan report" in result["error"]




@pytest.mark.parametrize("invalid_files", [{}, ""])
def test_direct_integrity_rejects_non_array_legacy_files(
    tmp_path: Path, invalid_files: object,
) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary

    valid = {
        "files": [],
        "errors": [],
        "summary": build_summary([], [], []),
    }
    assert report_integrity_status(valid) == "VERIFIED"
    assert verify_report(valid)["status"] == "VERIFIED"

    malformed = {**valid, "files": invalid_files}
    assert report_integrity_status(malformed) == "MISMATCH"
    checked = verify_report(malformed)
    assert checked["status"] == "FAILED"
    assert checked["exit_code"] == 2

    comparison = compare_payloads(valid, malformed)
    assert comparison["comparison_status"] == "PARTIAL"
    assert comparison["after"]["integrity_status"] == "MISMATCH"

    report = tmp_path / "non_array_legacy_scan.json"
    report.write_text(json.dumps(malformed), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid scan report"):
        load_scan_report(report)



@pytest.mark.parametrize("invalid_errors", [{}, "", None, {"path": "bad.csv"}])
def test_direct_integrity_rejects_non_array_legacy_errors(
    invalid_errors: object,
) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary

    valid = {
        "files": [],
        "errors": [],
        "summary": build_summary([], [], []),
    }
    assert report_integrity_status(valid) == "VERIFIED"
    without_errors = {key: value for key, value in valid.items() if key != "errors"}
    assert report_integrity_status(without_errors) == "VERIFIED"

    malformed = {**valid, "errors": invalid_errors}
    assert report_integrity_status(malformed) == "MISMATCH"

    verified = verify_report(malformed)
    assert verified["status"] == "FAILED"
    assert verified["exit_code"] == 2

    comparison = compare_payloads(valid, malformed)
    assert comparison["comparison_status"] == "PARTIAL"
    assert comparison["after"]["integrity_status"] == "MISMATCH"



@pytest.mark.parametrize("bad_path", ["", None, 0])
def test_direct_integrity_rejects_invalid_legacy_file_paths(
    tmp_path: Path, bad_path: object,
) -> None:
    from labvault_scout.compare import report_integrity_status, verify_report
    from labvault_scout.report import build_summary

    row = {
        "path": "sample.csv",
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
    }
    valid = {
        "files": [row],
        "errors": [],
        "summary": build_summary([row], [], []),
    }
    assert report_integrity_status(valid) == "VERIFIED"
    assert verify_report(valid)["status"] == "VERIFIED"

    bad_row = {**row, "path": bad_path}
    malformed = {
        **valid,
        "files": [bad_row],
        "summary": build_summary([bad_row], [], []),
    }
    assert report_integrity_status(malformed) == "MISMATCH"
    result = verify_report(malformed)
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2

    report = tmp_path / "bad_legacy_path.json"
    report.write_text(json.dumps(malformed), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid file row"):
        load_scan_report(report)



def test_direct_integrity_rejects_duplicate_legacy_file_paths(tmp_path: Path) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary, duplicate_groups

    rows = [
        {
            "path": path,
            "size": 1,
            "sha256": "a" * 64,
            "risk": "SAFE",
            "priority": "LOW",
            "open_copy": "",
        }
        for path in ("first.csv", "second.csv")
    ]
    valid = {
        "files": rows,
        "errors": [],
        "summary": build_summary(rows, [], duplicate_groups(rows)),
    }
    assert report_integrity_status(valid) == "VERIFIED"
    assert verify_report(valid)["status"] == "VERIFIED"

    malformed = json.loads(json.dumps(valid))
    malformed["files"][1]["path"] = malformed["files"][0]["path"]
    malformed["summary"] = build_summary(
        malformed["files"], [], duplicate_groups(malformed["files"])
    )
    assert malformed["summary"]["duplicate_group_count"] == 1
    assert report_integrity_status(malformed) == "MISMATCH"
    result = verify_report(malformed)
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2

    report = tmp_path / "duplicate_legacy_paths.json"
    report.write_text(json.dumps(malformed), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate path"):
        load_scan_report(report)
    with pytest.raises(ValueError, match="Path collision after legacy normalization"):
        compare_payloads(valid, malformed)



def test_direct_integrity_rejects_legacy_path_normalization_collisions() -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary, duplicate_groups

    rows = [
        {
            "path": path,
            "size": 1,
            "sha256": digest,
            "risk": "SAFE",
            "priority": "LOW",
            "open_copy": "",
        }
        for path, digest in (
            ("nested\\data.csv", "a" * 64),
            ("other.csv", "b" * 64),
        )
    ]
    valid = {
        "files": rows,
        "errors": [],
        "summary": build_summary(rows, [], duplicate_groups(rows)),
    }
    assert report_integrity_status(valid) == "VERIFIED"
    assert verify_report(valid)["status"] == "VERIFIED"

    malformed = json.loads(json.dumps(valid))
    malformed["files"][1]["path"] = "nested/data.csv"
    malformed["summary"] = build_summary(
        malformed["files"], [], duplicate_groups(malformed["files"])
    )
    assert malformed["files"][0]["path"] != malformed["files"][1]["path"]
    assert report_integrity_status(malformed) == "MISMATCH"

    checked = verify_report(malformed)
    assert checked["status"] == "FAILED"
    assert checked["exit_code"] == 2
    with pytest.raises(ValueError, match="Path collision after legacy normalization"):
        compare_payloads(valid, malformed)



@pytest.mark.parametrize("invalid_size", [-1, -1.5, "-1"])
def test_legacy_negative_size_cannot_have_verified_inventory(
    tmp_path: Path, invalid_size: object,
) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary

    row = {
        "path": "sample.csv",
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
    }
    valid = {
        "files": [row],
        "errors": [],
        "summary": build_summary([row], [], []),
    }
    assert report_integrity_status(valid) == "VERIFIED"

    malformed = json.loads(json.dumps(valid))
    malformed["files"][0]["size"] = invalid_size
    malformed["summary"] = build_summary(malformed["files"], [], [])
    malformed["summary"]["total_bytes"] = 0
    assert malformed["summary"]["inventory_sha256"] != valid["summary"]["inventory_sha256"]

    # The legacy loader stays lenient for comparison, but must not confer trust.
    report = tmp_path / "negative-size-legacy.json"
    report.write_text(json.dumps(malformed), encoding="utf-8")
    assert load_scan_report(report)["files"][0]["size"] == invalid_size

    assert report_integrity_status(malformed) == "MISMATCH"
    result = verify_report(malformed)
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    comparison = compare_payloads(valid, malformed)
    assert comparison["comparison_status"] == "PARTIAL"
    assert comparison["after"]["integrity_status"] == "MISMATCH"



@pytest.mark.parametrize(
    "invalid_size", ["7.9", "1e3", "1_0", " +7", " 7 ", "٧"],
)
def test_legacy_invalid_size_string_cannot_have_verified_inventory(
    tmp_path: Path, invalid_size: str,
) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary, inventory_sha256

    row = {
        "path": "sample.csv",
        "size": "007",
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
    }
    valid = {
        "files": [row],
        "errors": [],
        "summary": build_summary([row], [], []),
    }
    assert valid["summary"]["total_bytes"] == 7
    assert report_integrity_status(valid) == "VERIFIED"

    malformed = json.loads(json.dumps(valid))
    malformed["files"][0]["size"] = invalid_size
    malformed["summary"]["inventory_sha256"] = inventory_sha256(malformed["files"])
    malformed["summary"]["total_bytes"] = 0

    # The legacy loader and comparison metrics remain lenient; integrity does not.
    path = tmp_path / "malformed-size-string.json"
    path.write_text(json.dumps(malformed), encoding="utf-8")
    assert load_scan_report(path)["files"][0]["size"] == invalid_size
    assert report_integrity_status(malformed) == "MISMATCH"

    verification = verify_report(malformed)
    assert verification["status"] == "FAILED"
    assert verification["exit_code"] == 2
    comparison = compare_payloads(valid, malformed)
    assert comparison["after"]["metrics"]["total_bytes"] == 0
    assert comparison["comparison_status"] == "PARTIAL"
    assert comparison["after"]["integrity_status"] == "MISMATCH"



@pytest.mark.parametrize("invalid_size", [True, False, 0.9, 7.9])
def test_legacy_boolean_or_fractional_size_cannot_have_verified_inventory(
    tmp_path: Path, invalid_size: object,
) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary, inventory_sha256

    row = {
        "path": "sample.csv",
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
    }
    valid = {
        "files": [row],
        "errors": [],
        "summary": build_summary([row], [], []),
    }
    assert report_integrity_status(valid) == "VERIFIED"

    whole_float = json.loads(json.dumps(valid))
    whole_float["files"][0]["size"] = 1.0
    whole_float["summary"] = build_summary(whole_float["files"], [], [])
    assert report_integrity_status(whole_float) == "VERIFIED"

    malformed = json.loads(json.dumps(valid))
    malformed["files"][0]["size"] = invalid_size
    malformed["summary"]["inventory_sha256"] = inventory_sha256(malformed["files"])
    malformed["summary"]["total_bytes"] = 0

    report = tmp_path / "noninteger-numeric-size-legacy.json"
    report.write_text(json.dumps(malformed), encoding="utf-8")
    assert load_scan_report(report)["files"][0]["size"] == invalid_size
    assert report_integrity_status(malformed) == "MISMATCH"

    verified = verify_report(malformed)
    assert verified["status"] == "FAILED"
    assert verified["exit_code"] == 2
    compared = compare_payloads(valid, malformed)
    assert compared["comparison_status"] == "PARTIAL"
    assert compared["after"]["integrity_status"] == "MISMATCH"
    assert compared["after"]["metrics"]["total_bytes"] == 0




@pytest.mark.parametrize("invalid_size", [None, [], {}, {"bytes": 1}])
def test_legacy_null_or_container_size_cannot_verify(
    tmp_path: Path, invalid_size: object,
) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary, inventory_sha256

    row = {
        "path": "sample.csv",
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
    }
    valid = {
        "files": [row],
        "errors": [],
        "summary": build_summary([row], [], []),
    }
    assert report_integrity_status(valid) == "VERIFIED"

    malformed = json.loads(json.dumps(valid))
    malformed["files"][0]["size"] = invalid_size
    malformed["summary"]["inventory_sha256"] = inventory_sha256(malformed["files"])
    malformed["summary"]["total_bytes"] = 0

    report = tmp_path / "invalid-container-size-legacy.json"
    report.write_text(json.dumps(malformed), encoding="utf-8")
    assert load_scan_report(report)["files"][0]["size"] == invalid_size

    assert report_integrity_status(malformed) == "MISMATCH"
    verified = verify_report(malformed)
    assert verified["status"] == "FAILED"
    assert verified["exit_code"] == 2
    compared = compare_payloads(valid, malformed)
    assert compared["comparison_status"] == "PARTIAL"
    assert compared["after"]["integrity_status"] == "MISMATCH"
    assert compared["after"]["metrics"]["total_bytes"] == 0



@pytest.mark.parametrize("invalid_hash", [None, "", 0, True, [], {}, {"hash": "a"}])
def test_legacy_invalid_hash_type_cannot_verify(
    tmp_path: Path, invalid_hash: object,
) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary, inventory_sha256

    row = {
        "path": "sample.csv",
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
    }
    valid = {
        "files": [row],
        "errors": [],
        "summary": build_summary([row], [], []),
    }
    assert report_integrity_status(valid) == "VERIFIED"
    minimal = {"files": [{"path": "sample.csv", "sha256": invalid_hash}]}
    assert report_integrity_status(minimal) == "UNKNOWN"

    malformed = json.loads(json.dumps(valid))
    malformed["files"][0]["sha256"] = invalid_hash
    malformed["summary"]["inventory_sha256"] = inventory_sha256(malformed["files"])
    report = tmp_path / "invalid-hash-type-legacy.json"
    report.write_text(json.dumps(malformed), encoding="utf-8")
    assert load_scan_report(report)["files"][0]["sha256"] == invalid_hash

    assert report_integrity_status(malformed) == "MISMATCH"
    checked = verify_report(malformed)
    assert checked["status"] == "FAILED"
    assert checked["exit_code"] == 2
    compared = compare_payloads(valid, malformed)
    assert compared["comparison_status"] == "PARTIAL"
    assert compared["after"]["integrity_status"] == "MISMATCH"



@pytest.mark.parametrize(
    "invalid_hash", ["a" * 63, "a" * 65, "g" * 64, "A" * 64, "not-a-digest"],
)
def test_legacy_non_sha256_digest_cannot_verify(
    tmp_path: Path, invalid_hash: str,
) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary, inventory_sha256

    row = {
        "path": "sample.csv",
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
    }
    valid = {
        "files": [row],
        "errors": [],
        "summary": build_summary([row], [], []),
    }
    assert report_integrity_status(valid) == "VERIFIED"
    assert report_integrity_status({"files": [{"path": "sample.csv", "sha256": invalid_hash}]}) == "UNKNOWN"

    malformed = json.loads(json.dumps(valid))
    malformed["files"][0]["sha256"] = invalid_hash
    malformed["summary"]["inventory_sha256"] = inventory_sha256(malformed["files"])

    report = tmp_path / "legacy-bad-digest.json"
    report.write_text(json.dumps(malformed), encoding="utf-8")
    assert load_scan_report(report)["files"][0]["sha256"] == invalid_hash
    assert report_integrity_status(malformed) == "MISMATCH"

    verified = verify_report(malformed)
    assert verified["status"] == "FAILED"
    assert verified["exit_code"] == 2
    compared = compare_payloads(valid, malformed)
    assert compared["comparison_status"] == "PARTIAL"
    assert compared["after"]["integrity_status"] == "MISMATCH"



@pytest.mark.parametrize(
    ("field", "count_key", "boolean"),
    [
        ("file_count", None, True),
        ("total_bytes", None, True),
        ("error_count", None, False),
        ("open_copy_count", None, False),
        ("duplicate_group_count", None, False),
        ("risk_counts", "SAFE", True),
        ("priority_counts", "LOW", True),
    ],
)
def test_legacy_boolean_summary_counts_cannot_verify(
    tmp_path: Path, field: str, count_key: str | None, boolean: bool,
) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary

    row = {
        "path": "sample.csv",
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
    }
    valid = {
        "files": [row],
        "errors": [],
        "summary": build_summary([row], [], []),
    }
    assert report_integrity_status(valid) == "VERIFIED"

    malformed = json.loads(json.dumps(valid))
    if count_key is None:
        assert malformed["summary"][field] == boolean
        malformed["summary"][field] = boolean
    else:
        assert malformed["summary"][field][count_key] == boolean
        malformed["summary"][field][count_key] = boolean

    report = tmp_path / "boolean-legacy-summary.json"
    report.write_text(json.dumps(malformed), encoding="utf-8")
    assert load_scan_report(report)["summary"] == malformed["summary"]
    assert report_integrity_status(malformed) == "MISMATCH"

    verified = verify_report(malformed)
    assert verified["status"] == "FAILED"
    assert verified["exit_code"] == 2
    compared = compare_payloads(valid, malformed)
    assert compared["comparison_status"] == "PARTIAL"
    assert compared["after"]["integrity_status"] == "MISMATCH"



@pytest.mark.parametrize(
    ("field", "count_key", "value"),
    [
        ("file_count", None, 1.0),
        ("total_bytes", None, 1.0),
        ("error_count", None, 0.0),
        ("open_copy_count", None, 0.0),
        ("duplicate_group_count", None, 0.0),
        ("risk_counts", "SAFE", 1.0),
        ("priority_counts", "LOW", 1.0),
    ],
)
def test_legacy_fractional_type_summary_counts_cannot_verify(
    tmp_path: Path, field: str, count_key: str | None, value: float,
) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary

    row = {
        "path": "sample.csv",
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
    }
    valid = {"files": [row], "errors": [], "summary": build_summary([row], [], [])}
    assert report_integrity_status(valid) == "VERIFIED"

    malformed = json.loads(json.dumps(valid))
    if count_key is None:
        assert malformed["summary"][field] == value
        malformed["summary"][field] = value
    else:
        assert malformed["summary"][field][count_key] == value
        malformed["summary"][field][count_key] = value

    path = tmp_path / "legacy-float-count.json"
    path.write_text(json.dumps(malformed), encoding="utf-8")
    assert load_scan_report(path)["summary"] == malformed["summary"]
    assert report_integrity_status(malformed) == "MISMATCH"

    verified = verify_report(malformed)
    assert verified["status"] == "FAILED"
    assert verified["exit_code"] == 2
    compared = compare_payloads(valid, malformed)
    assert compared["comparison_status"] == "PARTIAL"
    assert compared["after"]["integrity_status"] == "MISMATCH"



def test_legacy_explicit_null_report_checksum_is_mismatch(tmp_path: Path) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary

    row = {
        "path": "sample.csv",
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
    }
    legacy = {
        "files": [row],
        "errors": [],
        "summary": build_summary([row], [], []),
    }
    assert "report_sha256" not in legacy
    assert report_integrity_status(legacy) == "VERIFIED"
    assert verify_report(legacy)["status"] == "VERIFIED"

    malformed = {**legacy, "report_sha256": None}
    report = tmp_path / "null-report-checksum-legacy.json"
    report.write_text(json.dumps(malformed), encoding="utf-8")
    assert load_scan_report(report)["report_sha256"] is None

    assert report_integrity_status(malformed) == "MISMATCH"
    result = verify_report(malformed)
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    comparison = compare_payloads(legacy, malformed)
    assert comparison["comparison_status"] == "PARTIAL"
    assert comparison["after"]["integrity_status"] == "MISMATCH"



@pytest.mark.parametrize("bad_error", [None, "PermissionError", 7, [], True])
def test_legacy_non_object_error_row_cannot_verify(
    tmp_path: Path, bad_error: object,
) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary

    row = {
        "path": "sample.csv",
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
    }
    good_error = {"path": "blocked.csv", "error": "PermissionError"}
    valid = {
        "files": [row],
        "errors": [good_error],
        "summary": build_summary([row], [good_error], []),
    }
    assert report_integrity_status(valid) == "VERIFIED"

    malformed = json.loads(json.dumps(valid))
    malformed["errors"] = [bad_error]
    assert report_integrity_status({"files": [row], "errors": [bad_error]}) == "UNKNOWN"
    assert malformed["summary"]["error_count"] == len(malformed["errors"])

    report = tmp_path / "legacy-invalid-error-row.json"
    report.write_text(json.dumps(malformed), encoding="utf-8")
    assert load_scan_report(report)["errors"] == [bad_error]
    assert report_integrity_status(malformed) == "MISMATCH"

    verified = verify_report(malformed)
    assert verified["status"] == "FAILED"
    assert verified["exit_code"] == 2
    compared = compare_payloads(valid, malformed)
    assert compared["comparison_status"] == "PARTIAL"
    assert compared["after"]["integrity_status"] == "MISMATCH"



@pytest.mark.parametrize(
    ("include_path", "bad_path"),
    [(False, None), (True, None), (True, ""), (True, 0), (True, []), (True, {})],
)
def test_legacy_invalid_error_path_cannot_verify(
    tmp_path: Path, include_path: bool, bad_path: object,
) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary

    row = {
        "path": "sample.csv",
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
    }
    good_error = {"path": "blocked.csv", "error": "PermissionError"}
    valid = {
        "files": [row],
        "errors": [good_error],
        "summary": build_summary([row], [good_error], []),
    }
    assert report_integrity_status(valid) == "VERIFIED"

    bad_error = {"error": "PermissionError"}
    if include_path:
        bad_error["path"] = bad_path
    malformed = {**valid, "errors": [bad_error]}
    assert report_integrity_status({"files": [row], "errors": [bad_error]}) == "UNKNOWN"
    assert malformed["summary"]["error_count"] == 1

    report = tmp_path / "legacy-invalid-error-path.json"
    report.write_text(json.dumps(malformed), encoding="utf-8")
    assert load_scan_report(report)["errors"] == [bad_error]
    assert report_integrity_status(malformed) == "MISMATCH"

    checked = verify_report(malformed)
    assert checked["status"] == "FAILED"
    assert checked["exit_code"] == 2
    compared = compare_payloads(valid, malformed)
    assert compared["comparison_status"] == "PARTIAL"
    assert compared["after"]["integrity_status"] == "MISMATCH"



@pytest.mark.parametrize(
    ("include_error", "bad_error"),
    [(False, None), (True, None), (True, ""), (True, 0), (True, []), (True, {})],
)
def test_legacy_invalid_error_type_cannot_verify(
    tmp_path: Path, include_error: bool, bad_error: object,
) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary

    row = {
        "path": "sample.csv",
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
    }
    good_error = {"path": "blocked.csv", "error": "PermissionError"}
    valid = {
        "files": [row],
        "errors": [good_error],
        "summary": build_summary([row], [good_error], []),
    }
    assert report_integrity_status(valid) == "VERIFIED"

    malformed_error = {"path": "blocked.csv"}
    if include_error:
        malformed_error["error"] = bad_error
    malformed = {**valid, "errors": [malformed_error]}
    assert report_integrity_status({"files": [row], "errors": [malformed_error]}) == "UNKNOWN"

    report = tmp_path / "legacy-invalid-error-type.json"
    report.write_text(json.dumps(malformed), encoding="utf-8")
    assert load_scan_report(report)["errors"] == [malformed_error]
    assert report_integrity_status(malformed) == "MISMATCH"

    checked = verify_report(malformed)
    assert checked["status"] == "FAILED"
    assert checked["exit_code"] == 2
    compared = compare_payloads(valid, malformed)
    assert compared["comparison_status"] == "PARTIAL"
    assert compared["after"]["integrity_status"] == "MISMATCH"



@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../outside.csv",
        "nested/../outside.csv",
        "/absolute/outside.csv",
        "nested" + chr(92) + ".." + chr(92) + "outside.csv",
        "blocked" + chr(0) + ".csv",
        "C:/sensitive.csv",
        "C:" + chr(92) + "sensitive.csv",
        "C:relative.csv",
        "z:relative.csv",
    ],
)
def test_legacy_unsafe_error_path_cannot_verify(
    tmp_path: Path, unsafe_path: str,
) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary

    row = {
        "path": "sample.csv",
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
    }
    good_error = {"path": "nested" + chr(92) + "blocked.csv", "error": "PermissionError"}
    valid = {
        "files": [row],
        "errors": [good_error],
        "summary": build_summary([row], [good_error], []),
    }
    assert report_integrity_status(valid) == "VERIFIED"

    root_error = {**valid, "errors": [{"path": ".", "error": "PermissionError"}]}
    assert report_integrity_status(root_error) == "VERIFIED"

    malformed = {**valid, "errors": [{"path": unsafe_path, "error": "PermissionError"}]}
    report = tmp_path / "legacy-unsafe-error-path.json"
    report.write_text(json.dumps(malformed), encoding="utf-8")
    assert load_scan_report(report)["errors"] == malformed["errors"]
    assert report_integrity_status(malformed) == "MISMATCH"

    checked = verify_report(malformed)
    assert checked["status"] == "FAILED"
    assert checked["exit_code"] == 2
    compared = compare_payloads(valid, malformed)
    assert compared["comparison_status"] == "PARTIAL"
    assert compared["after"]["integrity_status"] == "MISMATCH"



@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../outside.csv",
        "nested/../outside.csv",
        "/absolute/outside.csv",
        "nested" + chr(92) + ".." + chr(92) + "outside.csv",
        "C:/outside.csv",
        "C:" + chr(92) + "outside.csv",
        "C:relative.csv",
        chr(92) + chr(92) + "server" + chr(92) + "share" + chr(92) + "data.csv",
        "outside" + chr(0) + ".csv",
        ".",
    ],
)
def test_legacy_unsafe_file_path_cannot_verify(
    tmp_path: Path, unsafe_path: str,
) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary, inventory_sha256

    row = {
        "path": "nested" + chr(92) + "sample.csv",
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
    }
    valid = {"files": [row], "errors": [], "summary": build_summary([row], [], [])}
    assert report_integrity_status(valid) == "VERIFIED"
    assert report_integrity_status({"files": [row], "errors": []}) == "UNKNOWN"

    malformed = json.loads(json.dumps(valid))
    malformed["files"][0]["path"] = unsafe_path
    malformed["summary"]["inventory_sha256"] = inventory_sha256(malformed["files"])
    assert report_integrity_status({"files": malformed["files"], "errors": []}) == "MISMATCH"

    path = tmp_path / "legacy-unsafe-file-path.json"
    path.write_text(json.dumps(malformed), encoding="utf-8")
    assert load_scan_report(path)["files"][0]["path"] == unsafe_path
    assert report_integrity_status(malformed) == "MISMATCH"

    checked = verify_report(malformed)
    assert checked["status"] == "FAILED"
    assert checked["exit_code"] == 2
    compared = compare_payloads(valid, malformed)
    assert compared["comparison_status"] == "PARTIAL"
    assert compared["after"]["integrity_status"] == "MISMATCH"

def test_escaped_unpaired_surrogate_does_not_crash_integrity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )

    source = tmp_path / "source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "report"
    scan(source, output)
    original = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert report_integrity_status(original) == "VERIFIED"

    bad = json.loads(json.dumps(original))
    bad["files"][0]["reason"] = chr(0xD800)
    report = tmp_path / "surrogate-report.json"
    report.write_text(json.dumps(bad, ensure_ascii=True), encoding="utf-8")
    loaded = load_scan_report(report)
    assert loaded["files"][0]["reason"] == chr(0xD800)

    assert report_integrity_status(loaded) == "MISMATCH"
    checked = verify_report(loaded)
    assert checked["status"] == "FAILED"
    assert checked["exit_code"] == 2
    comparison = compare_payloads(original, loaded)
    assert comparison["comparison_status"] == "PARTIAL"
    assert comparison["after"]["integrity_status"] == "MISMATCH"

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(report), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "FAILED"

    legacy = {
        "files": [{"path": chr(0xD800), "size": 1, "sha256": "a" * 64}],
        "summary": {"inventory_sha256": "a" * 64},
    }
    assert report_integrity_status(legacy) == "MISMATCH"


@pytest.mark.parametrize(
    ("key", "marker"),
    [
        ("schema_version", '"schema_version": "1"'),
        ("name", '"name": "LabVault Scout"'),
        ("path", '"path": "data.csv"'),
    ],
)
def test_verify_rejects_duplicate_scan_report_json_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    key: str,
    marker: str,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "report"
    scan(source, output)
    report = output / "scan.json"

    original = report.read_text(encoding="utf-8")
    assert marker in original
    ambiguous = original.replace(marker, f"{marker}, {marker}", 1)
    # Default JSON decoding collapses the duplicate without changing the checksum-bearing payload.
    assert json.loads(ambiguous) == json.loads(original)
    report.write_text(ambiguous, encoding="utf-8")

    with pytest.raises(ValueError, match="Cannot read scan report") as exc_info:
        load_scan_report(report)
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert f"Duplicate scan report JSON key: {key}" in str(exc_info.value.__cause__)

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(report), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2
    assert "Cannot read scan report" in result["error"]


def test_load_scan_report_wraps_json_parser_recursion_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = tmp_path / "deeply-nested-report.json"
    report.write_text("[" * 4000 + "0" + "]" * 4000, encoding="utf-8")
    original_loads = json.loads

    def raise_recursion_error(
        text: str, *, object_pairs_hook: object = None,
        parse_constant: object = None, parse_float: object = None
    ) -> object:
        assert text.startswith("[" * 4000)
        assert callable(object_pairs_hook)
        assert callable(parse_constant)
        assert callable(parse_float)
        raise RecursionError("JSON nesting exceeds parser recursion limit")

    with monkeypatch.context() as patched:
        patched.setattr(json, "loads", raise_recursion_error)

        with pytest.raises(ValueError, match="Cannot read scan report") as exc_info:
            load_scan_report(report)
        assert isinstance(exc_info.value.__cause__, RecursionError)

        patched.setattr(sys, "argv", ["labvault-scout", "verify", str(report)])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err.startswith("Error:")
        assert "Cannot read scan report" in captured.err
        assert "Traceback" not in captured.err

        patched.setattr(sys, "argv", ["labvault-scout", "verify", str(report), "--json"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
        captured = capsys.readouterr()
        assert captured.err == ""

    result = original_loads(captured.out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2
    assert "Cannot read scan report" in result["error"]


@pytest.mark.parametrize(
    ("number", "expected_cause"),
    [
        ("NaN", "Non-standard scan report JSON constant: NaN"),
        ("Infinity", "Non-standard scan report JSON constant: Infinity"),
        ("-Infinity", "Non-standard scan report JSON constant: -Infinity"),
        ("1e999", "Scan report JSON number exceeds floating-point range"),
        ("-1e999", "Scan report JSON number exceeds floating-point range"),
    ],
)
def test_invalid_nonfinite_scan_number_is_rejected_by_verify_and_compare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    number: str,
    expected_cause: str,
) -> None:
    bad = tmp_path / "invalid-numeric-report.json"
    bad.write_text(
        '{"files": [{"path": "data.csv", "size": ' + number + '}], "errors": []}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Cannot read scan report") as exc_info:
        load_scan_report(bad)
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert expected_cause in str(exc_info.value.__cause__)

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(bad), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2
    assert "Cannot read scan report" in result["error"]

    good = tmp_path / "good-legacy-report.json"
    good.write_text('{"files": [{"path": "data.csv", "size": 1}], "errors": []}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["labvault-scout", "compare", str(bad), str(good)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "Cannot read scan report" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("number", ["1e-999", "-1e-999", "1E-999"])
def test_scan_report_rejects_nonzero_float_underflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    number: str,
) -> None:
    bad = tmp_path / "underflow-report.json"
    bad.write_text(
        '{"files": [{"path": "data.csv", "size": ' + number + '}], "errors": []}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Cannot read scan report") as exc_info:
        load_scan_report(bad)
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "Scan report JSON number underflows floating-point range" in str(
        exc_info.value.__cause__
    )

    monkeypatch.setattr(sys, "argv", ["labvault-scout", "verify", str(bad), "--json"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result["status"] == "INVALID"
    assert result["exit_code"] == 2
    assert "Cannot read scan report" in result["error"]

    good = tmp_path / "good-legacy-report.json"
    good.write_text('{"files": [], "errors": []}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["labvault-scout", "compare", str(bad), str(good)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error:")
    assert "Cannot read scan report" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("number", ["0e-999", "-0e-999", "0.000e-999"])
def test_scan_report_exact_float_zero_is_not_underflow(
    tmp_path: Path, number: str
) -> None:
    report = tmp_path / "zero-legacy-report.json"
    report.write_text(
        '{"files": [{"path": "data.csv", "size": ' + number + '}], "errors": []}',
        encoding="utf-8",
    )

    parsed = load_scan_report(report)

    assert parsed["files"][0]["size"] == 0.0


def test_legacy_unencodable_error_path_cannot_verify() -> None:
    """Malformed Unicode in legacy error paths must not receive VERIFIED."""
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary

    valid_error = {"path": "readable.csv", "error": "PermissionError"}
    valid = {
        "files": [],
        "errors": [valid_error],
        "summary": build_summary([], [valid_error], []),
    }
    assert report_integrity_status(valid) == "VERIFIED"

    malformed_error = {"path": "invalid-" + chr(0xDCFF) + ".csv", "error": "PermissionError"}
    malformed = {
        "files": [],
        "errors": [malformed_error],
        "summary": build_summary([], [malformed_error], []),
    }
    assert report_integrity_status(malformed) == "MISMATCH"
    assert verify_report(malformed)["status"] == "FAILED"
    compared = compare_payloads(valid, malformed)
    assert compared["comparison_status"] == "PARTIAL"
    assert compared["after"]["integrity_status"] == "MISMATCH"


@pytest.mark.parametrize("invalid_text", [chr(0xD800), chr(0xDCFF)])
def test_legacy_unencodable_error_text_cannot_verify(invalid_text: str) -> None:
    """Legacy reports with unencodable error messages cannot be verified."""
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary

    good_error = {"path": "readable.csv", "error": "PermissionError"}
    valid = {
        "files": [],
        "errors": [good_error],
        "summary": build_summary([], [good_error], []),
    }
    assert report_integrity_status(valid) == "VERIFIED"

    malformed_error = {"path": "readable.csv", "error": "invalid-" + invalid_text}
    malformed = {
        "files": [],
        "errors": [malformed_error],
        "summary": build_summary([], [malformed_error], []),
    }
    assert report_integrity_status(malformed) == "MISMATCH"
    assert verify_report(malformed)["status"] == "FAILED"
    comparison = compare_payloads(valid, malformed)
    assert comparison["comparison_status"] == "PARTIAL"
    assert comparison["after"]["integrity_status"] == "MISMATCH"



@pytest.mark.parametrize("field", ["format", "reason"])
@pytest.mark.parametrize("invalid_text", [chr(0xD800), chr(0xDCFF)])
def test_legacy_unencodable_file_metadata_cannot_verify(
    field: str, invalid_text: str,
) -> None:
    """Legacy inventory hashes do not authenticate file metadata text."""
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary

    row = {
        "path": "data.csv",
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
        "format": "CSV",
        "reason": "recognized",
    }
    valid = {
        "files": [row],
        "errors": [],
        "summary": build_summary([row], [], []),
    }
    malformed = json.loads(json.dumps(valid))
    malformed["files"][0][field] = invalid_text

    assert report_integrity_status(valid) == "VERIFIED"
    assert report_integrity_status(malformed) == "MISMATCH"
    assert verify_report(malformed)["status"] == "FAILED"
    comparison = compare_payloads(valid, malformed)
    assert comparison["comparison_status"] == "PARTIAL"
    assert comparison["after"]["integrity_status"] == "MISMATCH"

@pytest.mark.parametrize(
    "alias_path",
    ["nested//data.csv", "nested/./data.csv"],
)
def test_legacy_redundant_path_segments_cannot_hide_collisions(
    alias_path: str,
) -> None:
    """Legacy aliases of the same POSIX path cannot verify as distinct files."""
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary, duplicate_groups

    first = {
        "path": alias_path,
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
    }
    second = {**first, "path": "nested/data.csv", "sha256": "b" * 64}
    valid = {
        "files": [first],
        "errors": [],
        "summary": build_summary([first], [], []),
    }
    assert report_integrity_status(valid) == "VERIFIED"

    rows = [first, second]
    malformed = {
        "files": rows,
        "errors": [],
        "summary": build_summary(rows, [], duplicate_groups(rows)),
    }
    assert report_integrity_status(malformed) == "MISMATCH"
    assert verify_report(malformed)["status"] == "FAILED"
    with pytest.raises(ValueError, match="Path collision after legacy normalization"):
        compare_payloads(valid, malformed)


@pytest.mark.parametrize("field", ["name", "version"])
@pytest.mark.parametrize("invalid_text", [chr(0xD800), chr(0xDCFF)])
def test_legacy_unencodable_tool_metadata_cannot_verify(
    field: str, invalid_text: str,
) -> None:
    """Reject malformed legacy tool metadata absent from inventory hashes."""
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary

    valid = {
        "tool": {"name": "LabVault Scout", "version": "0.2.0"},
        "files": [],
        "errors": [],
        "summary": build_summary([], [], []),
    }
    malformed = json.loads(json.dumps(valid))
    malformed["tool"][field] = invalid_text

    assert report_integrity_status(valid) == "VERIFIED"
    assert report_integrity_status(malformed) == "MISMATCH"
    assert verify_report(malformed)["status"] == "FAILED"
    comparison = compare_payloads(valid, malformed)
    assert comparison["comparison_status"] == "PARTIAL"
    assert comparison["after"]["integrity_status"] == "MISMATCH"


@pytest.mark.parametrize("field", ["hash_algorithm", "path_style", "rules_sha256", "source_access"])
@pytest.mark.parametrize("invalid_text", [chr(0xD800), chr(0xDCFF)])
def test_legacy_unencodable_provenance_metadata_cannot_verify(
    field: str, invalid_text: str,
) -> None:
    """Legacy inventory hashes omit provenance metadata text."""
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary

    valid = {
        "provenance": {
            "hash_algorithm": "sha256",
            "path_style": "relative-posix",
            "rules_sha256": "a" * 64,
            "rules_count": 1,
            "source_access": "read-only",
        },
        "files": [],
        "errors": [],
        "summary": build_summary([], [], []),
    }
    malformed = json.loads(json.dumps(valid))
    malformed["provenance"][field] = invalid_text

    assert report_integrity_status(valid) == "VERIFIED"
    assert report_integrity_status(malformed) == "MISMATCH"
    assert verify_report(malformed)["status"] == "FAILED"
    comparison = compare_payloads(valid, malformed)
    assert comparison["comparison_status"] == "PARTIAL"
    assert comparison["after"]["integrity_status"] == "MISMATCH"


@pytest.mark.parametrize(
    "nested_metadata",
    [
        {"notes": [chr(0xD800)]},
        {"notes": {chr(0xDCFF): "invalid key"}},
    ],
)
def test_legacy_nested_unencodable_provenance_cannot_verify(
    nested_metadata: dict,
) -> None:
    """Nested provenance text must be encodable before legacy verification."""
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary

    valid = {
        "provenance": {"notes": {"text": "valid"}},
        "files": [],
        "errors": [],
        "summary": build_summary([], [], []),
    }
    malformed = json.loads(json.dumps(valid))
    malformed["provenance"].update(nested_metadata)

    assert report_integrity_status(valid) == "VERIFIED"
    assert report_integrity_status(malformed) == "MISMATCH"
    assert verify_report(malformed)["status"] == "FAILED"
    comparison = compare_payloads(valid, malformed)
    assert comparison["comparison_status"] == "PARTIAL"
    assert comparison["after"]["integrity_status"] == "MISMATCH"


@pytest.mark.parametrize(
    "nested_metadata",
    [
        {"notes": [chr(0xD800)]},
        {chr(0xDCFF): "invalid key"},
    ],
)
def test_legacy_nested_unencodable_file_metadata_cannot_verify(
    nested_metadata: dict,
) -> None:
    """Nested legacy file metadata must be UTF-8 encodable to verify."""
    from labvault_scout.compare import (
        compare_payloads, report_integrity_status, verify_report,
    )
    from labvault_scout.report import build_summary

    row = {
        "path": "data.csv",
        "size": 1,
        "sha256": "a" * 64,
        "risk": "SAFE",
        "priority": "LOW",
        "open_copy": "",
        "reason": "valid",
    }
    valid = {
        "files": [row],
        "errors": [],
        "summary": build_summary([row], [], []),
    }
    malformed = json.loads(json.dumps(valid))
    malformed["files"][0]["reason"] = nested_metadata

    assert report_integrity_status(valid) == "VERIFIED"
    assert report_integrity_status(malformed) == "MISMATCH"
    assert verify_report(malformed)["status"] == "FAILED"
    compared = compare_payloads(valid, malformed)
    assert compared["comparison_status"] == "PARTIAL"
    assert compared["after"]["integrity_status"] == "MISMATCH"
