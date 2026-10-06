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


def test_scan_binds_first_hash_to_entry_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = source / "changed.bin"
    target.write_bytes(b"original")
    output = tmp_path / "report"
    original_classify = cli.classify

    def replacing_classify(path: Path, rules):
        rule = original_classify(path, rules)
        if path == target:
            path.unlink()
            path.write_bytes(b"replacement-content")
        return rule

    monkeypatch.setattr(cli, "classify", replacing_classify)

    assert cli.scan(source, output) == 0
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert payload["files"] == []
    assert payload["errors"] == [
        {"path": "changed.bin", "error": "FileChangedDuringScan"}
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
    original_sha256_with_head = cli.hashing_module.sha256_with_head

    def changing_after_hash(path: Path, *, expected_stat=None):
        digest, header = original_sha256_with_head(
            path, expected_stat=expected_stat
        )
        if path == target:
            path.write_bytes(b"wxyz")
            os.utime(
                path,
                ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
            )
        return digest, header

    monkeypatch.setattr(cli.hashing_module, "sha256_with_head", changing_after_hash)

    assert cli.scan(source, output) == 0
    payload = json.loads((output / "scan.json").read_text(encoding="utf-8"))
    assert payload["files"] == []
    assert payload["errors"] == [
        {"path": "changed.bin", "error": "FileChangedDuringScan"}
    ]
