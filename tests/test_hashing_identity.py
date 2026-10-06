import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import labvault_scout.hashing as hashing
from labvault_scout.hashing import sha256_with_head


def test_hash_rejects_path_identity_change_before_read(tmp_path: Path) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"inside")
    expected_stat = target.lstat()

    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    target.unlink()
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    with pytest.raises(OSError, match="File identity changed before read"):
        sha256_with_head(target, expected_stat=expected_stat)


def test_hash_rejects_symlink_to_same_identity_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"inside")
    expected_stat = target.lstat()
    moved = tmp_path / "moved.bin"
    target.rename(moved)
    try:
        target.symlink_to(moved)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    def fail_if_read(*_args, **_kwargs):
        raise AssertionError("symlink target reached read stage")

    monkeypatch.setattr(hashing.os, "fdopen", fail_if_read)

    with pytest.raises(OSError, match="File identity changed before read"):
        sha256_with_head(target, expected_stat=expected_stat)


def test_hash_ignores_ctime_only_difference_between_path_and_open_handle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target.bin"
    content = b"inside"
    target.write_bytes(content)
    expected_stat = target.lstat()
    opened_stat = SimpleNamespace(
        st_dev=expected_stat.st_dev,
        st_ino=expected_stat.st_ino,
        st_mode=expected_stat.st_mode,
        st_size=expected_stat.st_size,
        st_mtime_ns=expected_stat.st_mtime_ns,
        st_ctime_ns=expected_stat.st_ctime_ns + 1,
    )
    monkeypatch.setattr(hashing.os, "fstat", lambda _fd: opened_stat)

    digest, head = sha256_with_head(target, expected_stat=expected_stat)

    assert digest == hashlib.sha256(content).hexdigest()
    assert head == content


def test_hash_rejects_file_change_during_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"inside")
    expected_stat = target.lstat()
    opened_stat = SimpleNamespace(
        st_dev=expected_stat.st_dev,
        st_ino=expected_stat.st_ino,
        st_mode=expected_stat.st_mode,
        st_size=expected_stat.st_size,
        st_mtime_ns=expected_stat.st_mtime_ns,
    )
    changed_stat = SimpleNamespace(
        st_dev=expected_stat.st_dev,
        st_ino=expected_stat.st_ino,
        st_mode=expected_stat.st_mode,
        st_size=expected_stat.st_size + 1,
        st_mtime_ns=expected_stat.st_mtime_ns + 1,
    )
    stats = iter((opened_stat, changed_stat))
    monkeypatch.setattr(hashing.os, "fstat", lambda _fd: next(stats))

    with pytest.raises(OSError, match="File changed during read"):
        sha256_with_head(target, expected_stat=expected_stat)


def test_hash_rejects_path_identity_change_during_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"inside")
    expected_stat = target.lstat()
    changed_path_stat = SimpleNamespace(
        st_dev=expected_stat.st_dev,
        st_ino=expected_stat.st_ino + 1,
        st_mode=expected_stat.st_mode,
        st_size=expected_stat.st_size,
        st_mtime_ns=expected_stat.st_mtime_ns,
    )
    monkeypatch.setattr(hashing.Path, "lstat", lambda _self: changed_path_stat)

    with pytest.raises(OSError, match="File identity changed before read"):
        sha256_with_head(target, expected_stat=expected_stat)
