"""Preserve the primary write error when temporary file cleanup also fails."""

import errno
from pathlib import Path

import pytest

import labvault_scout.safeio as safeio


@pytest.mark.parametrize("existing_target", [False, True])
def test_failed_temp_cleanup_preserves_original_replace_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing_target: bool,
) -> None:
    target = tmp_path / "scan.json"
    if existing_target:
        target.write_text("previous", encoding="utf-8")

    def fail_replace(_src, _dst):
        raise OSError(errno.EIO, "synthetic replace failure")

    original_unlink = Path.unlink
    cleanup_attempts = []

    def deny_temp_unlink(self: Path, *args, **kwargs):
        if self.parent == tmp_path and self.name.startswith(".scan.json.") and self.name.endswith(".tmp"):
            cleanup_attempts.append(self)
            raise PermissionError(errno.EACCES, "synthetic cleanup denied")
        return original_unlink(self, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(safeio.os, "replace", fail_replace)
        patch.setattr(safeio.Path, "unlink", deny_temp_unlink)
        with pytest.raises(OSError, match="synthetic replace failure") as caught:
            safeio.atomic_write_text(target, "replacement")

    assert caught.value.errno == errno.EIO
    assert isinstance(caught.value.__cause__, PermissionError)
    assert len(cleanup_attempts) == 1
    assert len(list(tmp_path.glob(".scan.json.*.tmp"))) == 1
    if existing_target:
        assert target.read_text(encoding="utf-8") == "previous"
    else:
        assert not target.exists()
