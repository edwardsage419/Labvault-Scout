import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import labvault_scout.hashing as hashing
from labvault_scout.hashing import sha256_file, sha256_with_head


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



@pytest.mark.skipif(
    not hasattr(os, "mkfifo") or not hasattr(os, "O_NONBLOCK"),
    reason="POSIX FIFO support is required",
)
def test_hash_rejects_fifo_swap_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"original")
    original_open = hashing.os.open
    swapped = False

    def swap_to_fifo_before_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if path == target and not swapped:
            swapped = True
            target.unlink()
            os.mkfifo(target)
            assert flags & os.O_NONBLOCK, "FIFO open must be nonblocking"
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(hashing.os, "open", swap_to_fifo_before_open)

    with pytest.raises(hashing.FileChangedDuringScan, match="File identity changed before read"):
        sha256_with_head(target)

    assert swapped


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


@pytest.mark.skipif(
    not hasattr(os, "O_NOFOLLOW"),
    reason="O_NOFOLLOW is required to prevent following a swapped symlink",
)
def test_hash_never_opens_symlink_target_after_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import errno

    target = tmp_path / "target.bin"
    target.write_bytes(b"inside")
    moved = tmp_path / "moved.bin"
    original_open = hashing.os.open
    swapped = False

    def swap_to_symlink_before_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if path == target and not swapped:
            target.rename(moved)
            try:
                target.symlink_to(moved)
            except (OSError, NotImplementedError):
                pytest.skip("Symlink creation is unavailable")
            swapped = True
            assert flags & os.O_NOFOLLOW, "Hash opening must not follow symlinks"
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(hashing.os, "open", swap_to_symlink_before_open)

    with pytest.raises(OSError) as exc_info:
        sha256_with_head(target)

    assert swapped
    assert exc_info.value.errno == errno.ELOOP


def test_hash_checks_ctime_difference_according_to_platform(
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

    if os.name != "nt":
        with pytest.raises(hashing.FileChangedDuringScan, match="File identity changed before read"):
            sha256_with_head(target, expected_stat=expected_stat)
    else:
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
        st_ctime_ns=expected_stat.st_ctime_ns,
    )
    changed_stat = SimpleNamespace(
        st_dev=expected_stat.st_dev,
        st_ino=expected_stat.st_ino,
        st_mode=expected_stat.st_mode,
        st_size=expected_stat.st_size + 1,
        st_mtime_ns=expected_stat.st_mtime_ns + 1,
        st_ctime_ns=expected_stat.st_ctime_ns + 1,
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


@pytest.mark.skipif(os.name == "nt", reason="Windows ctime represents file creation time")
def test_hash_detects_same_size_rewrite_with_restored_mtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"original")
    before = target.lstat()
    original_fstat = hashing.os.fstat
    changed = False

    def change_after_open(fd):
        nonlocal changed
        result = original_fstat(fd)
        if not changed:
            changed = True
            target.write_bytes(b"modified")
            os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
            after = target.lstat()
            assert after.st_size == before.st_size
            assert after.st_mtime_ns == before.st_mtime_ns
            if after.st_ctime_ns == before.st_ctime_ns:
                pytest.skip("Filesystem does not distinguish rapid metadata changes")
        return result

    monkeypatch.setattr(hashing.os, "fstat", change_after_open)

    with pytest.raises(hashing.FileChangedDuringScan, match="File changed during read"):
        sha256_with_head(target, expected_stat=before)

    assert changed

@pytest.mark.parametrize("close_fails", [False, True])
def test_hash_stream_setup_error_survives_descriptor_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, close_fails: bool,
) -> None:
    target = tmp_path / "input.bin"
    target.write_bytes(b"original research bytes")
    opened_fds: list[int] = []
    original_close = os.close

    def fail_fdopen(fd: int, *args, **kwargs):
        opened_fds.append(fd)
        raise ValueError("synthetic hash stream setup failure")

    def close_descriptor(fd: int) -> None:
        original_close(fd)
        if opened_fds and fd == opened_fds[0] and close_fails:
            raise OSError(5, "synthetic hash descriptor close failure")

    with monkeypatch.context() as patch:
        patch.setattr(hashing.os, "fdopen", fail_fdopen)
        patch.setattr(hashing.os, "close", close_descriptor)
        with pytest.raises(ValueError, match="synthetic hash stream setup failure") as caught:
            sha256_with_head(target)

    assert len(opened_fds) == 1
    with pytest.raises(OSError):
        os.fstat(opened_fds[0])
    if close_fails:
        assert isinstance(caught.value.__cause__, OSError)
        assert "synthetic hash descriptor close failure" in str(caught.value.__cause__)
    else:
        assert caught.value.__cause__ is None
    assert target.read_bytes() == b"original research bytes"


@pytest.mark.parametrize("chunk_size", [0, -1, False, 1.5])
@pytest.mark.parametrize("with_head", [True, False])
def test_hash_rejects_invalid_chunk_size(
    tmp_path: Path, chunk_size: object, with_head: bool,
) -> None:
    target = tmp_path / "research.bin"
    content = b"original research bytes"
    target.write_bytes(content)

    with pytest.raises(ValueError, match="chunk_size must be a positive integer"):
        if with_head:
            sha256_with_head(target, chunk_size=chunk_size)
        else:
            sha256_file(target, chunk_size=chunk_size)

    assert target.read_bytes() == content


@pytest.mark.parametrize("chunk_size", [1, 3])
def test_hash_accepts_small_positive_chunk_size(
    tmp_path: Path, chunk_size: int,
) -> None:
    target = tmp_path / "research.bin"
    content = b"original research bytes"
    target.write_bytes(content)

    digest, head = sha256_with_head(target, head_size=8, chunk_size=chunk_size)
    assert digest == hashlib.sha256(content).hexdigest()
    assert head == content[:8]
    assert sha256_file(target, chunk_size=chunk_size) == digest
