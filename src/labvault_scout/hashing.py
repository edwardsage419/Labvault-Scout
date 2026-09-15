from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_with_head(path: Path, head_size: int = 512, chunk_size: int = 1024 * 1024) -> tuple[str, bytes]:
    """Hash a file and capture its bounded header in one sequential read."""
    digest = hashlib.sha256()
    head = bytearray()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            if len(head) < head_size:
                need = head_size - len(head)
                head.extend(chunk[:need])
            digest.update(chunk)
    return digest.hexdigest(), bytes(head)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest, _ = sha256_with_head(path, head_size=0, chunk_size=chunk_size)
    return digest
