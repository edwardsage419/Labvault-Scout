"""Schema 1 reports must reject Windows-specific path spellings."""

import json
import re
from pathlib import Path

import pytest

from labvault_scout.cli import scan
from labvault_scout.compare import load_scan_report, report_integrity_status, verify_report
from labvault_scout.report import inventory_sha256, report_payload_sha256
from labvault_scout.schema_registry import load_schema_text


@pytest.mark.parametrize("row_kind", ["file", "error"])
@pytest.mark.parametrize(
    "unsafe_path",
    [
        "C:relative.csv",
        "C:/absolute.csv",
        "z:relative.csv",
        "nested\\data.csv",
        "\\\\server\\share.csv",
    ],
)
def test_schema1_rejects_windows_paths_even_with_recomputed_checksums(
    tmp_path: Path, row_kind: str, unsafe_path: str,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.csv").write_text("value\n1\n", encoding="utf-8")
    output = tmp_path / "output"
    scan(source, output)
    valid = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert report_integrity_status(valid) == "VERIFIED"

    malformed = json.loads(json.dumps(valid))
    if row_kind == "file":
        malformed["files"][0]["path"] = unsafe_path
        malformed["summary"]["inventory_sha256"] = inventory_sha256(malformed["files"])
    else:
        malformed["errors"] = [{"path": unsafe_path, "error": "PermissionError"}]
        malformed["summary"]["error_count"] = 1
    malformed["report_sha256"] = report_payload_sha256(malformed)

    # A recomputed checksum must not make an unsafe path trustworthy.
    assert report_integrity_status(malformed) == "MISMATCH"
    assert verify_report(malformed)["status"] == "FAILED"
    report_path = tmp_path / "unsafe-scan.json"
    report_path.write_text(json.dumps(malformed), encoding="utf-8")
    with pytest.raises(ValueError, match="Report path"):
        load_scan_report(report_path)

    schema = json.loads(load_schema_text("scan"))
    if row_kind == "file":
        path_schema = schema["properties"]["files"]["items"]["properties"]["path"]
    else:
        path_schema = schema["properties"]["errors"]["items"]["properties"]["path"]["anyOf"][1]
    assert any(
        re.search(clause["not"]["pattern"], unsafe_path)
        for clause in path_schema["allOf"]
        if "pattern" in clause.get("not", {})
    )
