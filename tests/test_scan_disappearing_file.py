import json
import os
from pathlib import Path

import pytest

import labvault_scout.cli as cli


def test_scan_records_file_disappearing_before_read(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = source / "vanished.bin"
    target.write_bytes(b"data")
    output = tmp_path / "report"

    def disappearing_iter(root, excluded=None, on_error=None):
        target.unlink()
        yield target

    monkeypatch.setattr(cli, "iter_files", disappearing_iter)

    assert cli.scan(source, output) == 0
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert payload["files"] == []
    assert payload["errors"] == [{"path": "vanished.bin", "error": "FileNotFoundError"}]


def test_scan_rejects_file_replaced_by_symlink_before_read(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = source / "swapped.bin"
    target.write_bytes(b"inside")
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    output = tmp_path / "report"

    def symlink_swap_iter(root, excluded=None, on_error=None):
        target.unlink()
        try:
            target.symlink_to(outside)
        except OSError:
            pytest.skip("symlink creation is unavailable")
        yield target

    monkeypatch.setattr(cli, "iter_files", symlink_swap_iter)

    assert cli.scan(source, output) == 0
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert payload["files"] == []
    assert payload["errors"] == [
        {"path": "swapped.bin", "error": "FileChangedDuringScan"}
    ]


@pytest.mark.skipif(os.name != "nt", reason="Windows metadata semantics")
def test_scan_detects_same_size_change_with_restored_mtime_on_windows(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = source / "changed.bin"
    target.write_bytes(b"abcd")
    output = tmp_path / "report"
    original_stat = target.stat()
    original_sha256_with_head = cli.sha256_with_head

    def changing_after_hash(path: Path):
        digest, header = original_sha256_with_head(path)
        if path == target:
            path.write_bytes(b"wxyz")
            os.utime(
                path,
                ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
            )
        return digest, header

    monkeypatch.setattr(cli, "sha256_with_head", changing_after_hash)

    assert cli.scan(source, output) == 0
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert payload["files"] == []
    assert payload["errors"] == [
        {"path": "changed.bin", "error": "FileChangedDuringScan"}
    ]
