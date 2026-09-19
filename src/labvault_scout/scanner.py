from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Iterator


def _is_within(path: Path, excluded: Path | None) -> bool:
    if excluded is None:
        return False
    try:
        path.resolve().relative_to(excluded)
        return True
    except (ValueError, OSError):
        return False


def iter_files(
    root: Path,
    excluded: Path | None = None,
    on_error: Callable[[Path, OSError], None] | None = None,
) -> Iterator[Path]:
    """Yield regular files recursively and report non-fatal traversal errors."""
    root = root.expanduser().resolve()
    excluded = excluded.expanduser().resolve() if excluded else None
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    def report_walk_error(exc: OSError) -> None:
        if on_error is not None:
            error_path = Path(exc.filename) if exc.filename else root
            on_error(error_path, exc)

    for current, dirs, files in os.walk(root, followlinks=False, onerror=report_walk_error):
        current_path = Path(current)
        dirs[:] = [
            name for name in dirs
            if not (current_path / name).is_symlink()
            and not _is_within(current_path / name, excluded)
        ]
        for name in files:
            path = current_path / name
            try:
                if not path.is_symlink() and path.is_file() and not _is_within(path, excluded):
                    yield path
            except OSError as exc:
                if on_error is not None:
                    on_error(path, exc)
                continue
