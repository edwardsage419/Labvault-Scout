from __future__ import annotations

from pathlib import Path
from typing import Iterator


def iter_files(root: Path) -> Iterator[Path]:
    """Yield regular files recursively without modifying the source tree."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    for path in root.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink():
                yield path
        except OSError:
            continue
