import csv
import json
from pathlib import Path

from labvault_scout.cli import scan
from labvault_scout.hashing import sha256_file
from labvault_scout.report import duplicate_groups
from labvault_scout.risk import classify, load_rules
from labvault_scout.scanner import iter_files


def test_core(tmp_path: Path):
    f = tmp_path / "result.jnb"
    f.write_bytes(b"labvault")
    assert list(iter_files(tmp_path)) == [f]
    assert len(sha256_file(f)) == 64
    assert classify(f, load_rules())["risk"] == "RESCUE"


def test_unknown(tmp_path: Path):
    f = tmp_path / "sample.xyzunknown"
    f.write_text("x")
    assert classify(f, load_rules())["risk"] == "UNKNOWN"


def test_duplicate_groups():
    rows = [
        {"path": "a.csv", "size": 1, "sha256": "same"},
        {"path": "b.csv", "size": 1, "sha256": "same"},
        {"path": "c.csv", "size": 1, "sha256": "other"},
    ]
    result = duplicate_groups(rows)
    assert len(result) == 2
    assert {x["path"] for x in result} == {"a.csv", "b.csv"}


def test_end_to_end_reports(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.csv").write_text("x")
    (source / "copy.csv").write_text("x")
    (source / "project.jnb").write_bytes(b"jnb")
    output = tmp_path / "report"
    assert scan(source, output) == 3
    for name in ("report.html", "files.csv", "scan.json", "duplicates.csv"):
        assert (output / name).exists()
    payload = json.loads((output / "scan.json").read_text())
    assert len(payload["files"]) == 3
    with (output / "duplicates.csv").open(encoding="utf-8-sig") as f:
        assert len(list(csv.DictReader(f))) == 2
