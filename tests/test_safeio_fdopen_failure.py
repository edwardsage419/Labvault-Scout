"""A failed stream wrapper must not leak the newly created temporary descriptor."""

import os
from pathlib import Path

import pytest

import labvault_scout.safeio as safeio


@pytest.mark.parametrize("existing_target", [False, True])
def test_fdopen_failure_closes_descriptor_and_preserves_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing_target: bool,
) -> None:
    target = tmp_path / "scan.json"
    if existing_target:
        target.write_text("previous", encoding="utf-8")
    opened_fds: list[int] = []

    def fail_fdopen(fd: int, *args, **kwargs):
        opened_fds.append(fd)
        raise PermissionError("synthetic fdopen failure")

    monkeypatch.setattr(safeio.os, "fdopen", fail_fdopen)
    with pytest.raises(PermissionError, match="synthetic fdopen failure"):
        safeio.atomic_write_text(target, "replacement")

    assert len(opened_fds) == 1
    with pytest.raises(OSError):
        os.fstat(opened_fds[0])
    assert list(tmp_path.glob(".scan.json.*.tmp")) == []
    if existing_target:
        assert target.read_text(encoding="utf-8") == "previous"
    else:
        assert not target.exists()
