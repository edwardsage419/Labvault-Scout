from pathlib import Path

import pytest

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
