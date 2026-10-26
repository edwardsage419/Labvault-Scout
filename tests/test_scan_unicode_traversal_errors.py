"""Keep Unicode traversal failures visible without corrupting scan artifacts."""

import errno
from pathlib import Path

import pytest

import labvault_scout.cli as cli
import labvault_scout.scanner as scanner
from labvault_scout.bundle import verify_bundle
from labvault_scout.compare import load_scan_report, verify_report


@pytest.mark.parametrize("failure_mode", ["walk_error", "entry_lstat"])
def test_unicode_traversal_error_preserves_partial_report_integrity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_mode: str,
) -> None:
    source = tmp_path / "source"
    nested = source / "研究_β"
    nested.mkdir(parents=True)
    healthy = nested / "正常.csv"
    healthy.write_bytes(b"sample\n")
    blocked = nested / ("无法访问_é" if failure_mode == "walk_error" else "无法访问_é.bin")

    if failure_mode == "walk_error":
        original_walk = scanner.os.walk

        def walk_with_error(top, *args, **kwargs):
            onerror = kwargs.get("onerror")
            assert onerror is not None
            onerror(PermissionError(errno.EACCES, "synthetic denial", str(blocked)))
            yield from original_walk(top, *args, **kwargs)

        monkeypatch.setattr(scanner.os, "walk", walk_with_error)
    else:
        blocked.write_bytes(b"untouched")
        original_lstat = Path.lstat

        def denied_lstat(path, *args, **kwargs):
            if path == blocked:
                raise PermissionError(errno.EACCES, "synthetic denial", str(path))
            return original_lstat(path, *args, **kwargs)

        monkeypatch.setattr(Path, "lstat", denied_lstat)

    output = tmp_path / "report"
    assert cli.scan(source, output) == 1
    payload = load_scan_report(output / "scan.json")
    assert [row["path"] for row in payload["files"]] == ["研究_β/正常.csv"]
    assert payload["errors"] == [
        {"path": blocked.relative_to(source).as_posix(), "error": "PermissionError"}
    ]
    assert payload["summary"]["file_count"] == 1
    assert payload["summary"]["error_count"] == 1
    assert verify_report(payload)["status"] == "VERIFIED"
    assert verify_bundle(output)["status"] == "VERIFIED"
    assert healthy.read_bytes() == b"sample\n"
    if failure_mode == "entry_lstat":
        assert blocked.read_bytes() == b"untouched"
