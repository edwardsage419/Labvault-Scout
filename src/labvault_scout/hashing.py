from __future__ import annotations

import hashlib
import os
import stat as stat_module
from os import stat_result
from pathlib import Path


class FileChangedDuringScan(OSError):
    """Raised when a path no longer opens the file identity previously inspected."""


def _file_identity_changed(expected: stat_result, actual: stat_result) -> bool:
    fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns")
    return any(getattr(expected, field, None) != getattr(actual, field, None) for field in fields)


def sha256_with_head(
    path: Path,
    head_size: int = 512,
    chunk_size: int = 1024 * 1024,
    *,
    expected_stat: stat_result | None = None,
) -> tuple[str, bytes]:
    """Hash a stable regular file and capture its bounded header in one read."""
    checked_stat = expected_stat if expected_stat is not None else path.lstat()
    if not stat_module.S_ISREG(checked_stat.st_mode):
        raise FileChangedDuringScan("File identity changed before read")

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags)
    try:
        opened_stat = os.fstat(fd)
        if _file_identity_changed(checked_stat, opened_stat):
            raise FileChangedDuringScan("File identity changed before read")
        handle = os.fdopen(fd, "rb")
        fd = -1
        digest = hashlib.sha256()
        head = bytearray()
        with handle:
            while chunk := handle.read(chunk_size):
                if len(head) < head_size:
                    need = head_size - len(head)
                    head.extend(chunk[:need])
                digest.update(chunk)
    finally:
        if fd != -1:
            os.close(fd)
    return digest.hexdigest(), bytes(head)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest, _ = sha256_with_head(path, head_size=0, chunk_size=chunk_size)
    return digest
