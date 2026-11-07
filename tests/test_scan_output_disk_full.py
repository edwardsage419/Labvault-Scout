"""Report writes remain recoverable after simulated disk exhaustion."""

import errno
from contextlib import contextmanager
from pathlib import Path

import pytest

import labvault_scout.report as report
import labvault_scout.safeio as safeio
from labvault_scout.bundle import BUNDLE_FILES, BUNDLE_MANIFEST_NAME, verify_bundle
from labvault_scout.cli import scan


def _prepare_existing_bundle(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    target = source / "sample.csv"
    target.write_bytes(b"value\n1\n")
    output = tmp_path / "report"
    assert scan(source, output) == 1
    assert verify_bundle(output)["status"] == "VERIFIED"
    return target, output


def test_disk_full_during_first_csv_preserves_complete_previous_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target, output = _prepare_existing_bundle(tmp_path)
    previous = {
        name: (output / name).read_bytes()
        for name in (*BUNDLE_FILES, BUNDLE_MANIFEST_NAME)
    }
    target.write_bytes(b"value\n2\n")
    original_writer = report.atomic_text_writer

    @contextmanager
    def fail_first_csv(path, **kwargs):
        with original_writer(path, **kwargs) as handle:
            if Path(path).name == "files.csv":
                handle.write("partial")
                raise OSError(errno.ENOSPC, "synthetic disk full")
            yield handle

    monkeypatch.setattr(report, "atomic_text_writer", fail_first_csv)
    with pytest.raises(OSError, match="synthetic disk full"):
        scan(tmp_path / "source", output)

    assert all((output / name).read_bytes() == content for name, content in previous.items())
    assert list(output.glob(".files.csv.*.tmp")) == []
    assert verify_bundle(output)["status"] == "VERIFIED"
    assert target.read_bytes() == b"value\n2\n"


def test_disk_full_during_final_html_invalidates_previous_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target, output = _prepare_existing_bundle(tmp_path)
    previous_html = (output / "report.html").read_bytes()
    previous_manifest = (output / BUNDLE_MANIFEST_NAME).read_bytes()
    previous_json = (output / "scan.json").read_bytes()
    target.write_bytes(b"value\n2\n")
    original_write = report.atomic_write_text

    def fail_html(path, text, *, encoding="utf-8"):
        if Path(path).name == "report.html":
            with safeio.atomic_text_writer(path, encoding=encoding) as handle:
                handle.write("partial")
                raise OSError(errno.ENOSPC, "synthetic disk full")
        return original_write(path, text, encoding=encoding)

    monkeypatch.setattr(report, "atomic_write_text", fail_html)
    with pytest.raises(OSError, match="synthetic disk full"):
        scan(tmp_path / "source", output)

    assert (output / "report.html").read_bytes() == previous_html
    assert (output / BUNDLE_MANIFEST_NAME).read_bytes() == previous_manifest
    assert (output / "scan.json").read_bytes() != previous_json
    assert list(output.glob(".report.html.*.tmp")) == []
    verification = verify_bundle(output)
    assert verification["status"] == "FAILED"
    assert any(problem["path"] == "scan.json" for problem in verification["problems"])
    assert target.read_bytes() == b"value\n2\n"
