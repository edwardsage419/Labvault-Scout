from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Callable, Iterator


def _is_within(path: Path, excluded: Path | None) -> bool:
    if excluded is None:
        return False
    # A known report subtree remains excluded even if resolving it fails.
    if path.is_relative_to(excluded):
        return True
    try:
        path.resolve().relative_to(excluded)
        return True
    except ValueError:
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
        safe_dirs = []
        for name in sorted(dirs):
            directory = current_path / name
            try:
                if not directory.is_symlink() and not _is_within(directory, excluded):
                    safe_dirs.append(name)
            except OSError as exc:
                if on_error is not None:
                    on_error(directory, exc)
        dirs[:] = safe_dirs
        for name in sorted(files):
            path = current_path / name
            try:
                mode = path.lstat().st_mode
                if not stat.S_ISLNK(mode) and stat.S_ISREG(mode) and not _is_within(path, excluded):
                    yield path
            except OSError as exc:
                if on_error is not None:
                    on_error(path, exc)
                continue
