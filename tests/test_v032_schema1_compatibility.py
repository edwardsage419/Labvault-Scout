"""Synthetic v0.3.2 schema-1 compatibility checks.

The summary and checksum algorithms reproduce report.py at stable commit
4877a9a8. These fixtures are reconstructed from that source; they are not
archived reports produced by executing the stable binary.
"""

import hashlib
import json
from pathlib import Path

import pytest

from labvault_scout.compare import (
    compare_reports, load_scan_report, report_integrity_status, verify_report,
)


def _stable_contract_report(path: str | None, with_error: bool = False) -> dict:
    rows = []
    if path is not None:
        rows.append({
            "path": path, "size": 4,
            "sha256": hashlib.sha256(b"a,b\n").hexdigest(),
            "format": "CSV", "signature": "", "signature_status": "",
            "container_type": "", "risk": "SAFE", "confidence": "MEDIUM",
            "priority_score": 0, "priority": "LOW",
            "priority_reason": "", "recommended_action": "", "open_copy": "",
            "relationship_strength": "", "relationship_evidence": "",
            "evidence": "", "reason": "",
        })
    errors = [{"path": "unreadable.csv", "error": "PermissionError"}] if with_error else []
    inventory = hashlib.sha256()
    for row in sorted(rows, key=lambda item: item["path"]):
        inventory.update(
            f"{row['path']}\0{row['size']}\0{row['sha256']}\n".encode("utf-8")
        )
    summary = {
        "file_count": len(rows),
        "total_bytes": sum(row["size"] for row in rows),
        "inventory_sha256": inventory.hexdigest(),
        "error_count": len(errors),
        "risk_counts": {"SAFE": 1} if rows else {},
        "priority_counts": {"LOW": 1} if rows else {},
        "open_copy_count": 0,
        "duplicate_group_count": 0,
    }
    payload = {
        "schema_version": "1",
        "tool": {"name": "LabVault Scout", "version": "0.3.2"},
        "provenance": {
            "hash_algorithm": "sha256", "path_style": "relative-posix",
            "rules_sha256": "0" * 64, "rules_count": 32,
            "source_access": "read-only",
        },
        "summary": summary, "files": rows, "errors": errors,
    }
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    payload["report_sha256"] = hashlib.sha256(serialized).hexdigest()
    return payload


@pytest.mark.parametrize(
    ("path", "with_error"),
    [(None, False), ("data.csv", False), ("data.csv", True), (None, True)],
)
def test_synthetic_v032_schema1_load_verify_and_compare(
    tmp_path: Path, path: str | None, with_error: bool,
) -> None:
    payload = _stable_contract_report(path, with_error)
    report_path = tmp_path / "synthetic-v032.json"
    report_path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_scan_report(report_path)
    assert loaded == payload
    assert report_integrity_status(loaded) == "VERIFIED"
    assert verify_report(loaded)["status"] == "VERIFIED"
    if path is not None and not with_error:
        assert compare_reports(report_path, report_path)["summary"]["change_count"] == 0


def test_synthetic_v032_posix_drive_prefix_requires_compatibility_decision(
    tmp_path: Path,
) -> None:
    # Stable v0.3.2 accepted this legal POSIX path. Current readers reject it.
    payload = _stable_contract_report("C:sample.csv")
    report_path = tmp_path / "synthetic-v032-drive-prefix.json"
    report_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Report path"):
        load_scan_report(report_path)
    assert report_integrity_status(payload) == "MISMATCH"
