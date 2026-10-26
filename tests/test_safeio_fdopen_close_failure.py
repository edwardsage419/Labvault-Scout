"""Preserve the stream setup error if closing the temporary descriptor also fails."""

import errno
import os
from pathlib import Path

import pytest

import labvault_scout.safeio as safeio


@pytest.mark.parametrize("existing_target", [False, True])
def test_fdopen_and_close_failure_preserves_setup_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing_target: bool,
) -> None:
    target = tmp_path / "scan.json"
    if existing_target:
        target.write_text("previous", encoding="utf-8")
    opened_fds: list[int] = []
    original_close = os.close

    def fail_fdopen(fd: int, *args, **kwargs):
        opened_fds.append(fd)
        raise ValueError("synthetic fdopen failure")

    def fail_close(fd: int):
        if opened_fds and fd == opened_fds[0]:
            original_close(fd)
            raise OSError(errno.EIO, "synthetic descriptor close failure")
        return original_close(fd)

    with monkeypatch.context() as patch:
        patch.setattr(safeio.os, "fdopen", fail_fdopen)
        patch.setattr(safeio.os, "close", fail_close)
        with pytest.raises(ValueError, match="synthetic fdopen failure") as caught:
            safeio.atomic_write_text(target, "replacement")

    assert isinstance(caught.value.__cause__, OSError)
    assert caught.value.__cause__.errno == errno.EIO
    assert len(opened_fds) == 1
    with pytest.raises(OSError):
        os.fstat(opened_fds[0])
    assert list(tmp_path.glob(".scan.json.*.tmp")) == []
    if existing_target:
        assert target.read_text(encoding="utf-8") == "previous"
    else:
        assert not target.exists()
