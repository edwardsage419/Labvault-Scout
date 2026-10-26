from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO


@contextmanager
def atomic_text_writer(
    path: Path,
    *,
    encoding: str = "utf-8",
    newline: str | None = None,
) -> Iterator[TextIO]:
    """Write text through a same-directory temporary file and atomically replace the target."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp_path = Path(temp_name)
    try:
        try:
            handle = os.fdopen(fd, "w", encoding=encoding, newline=newline)
        except BaseException:
            os.close(fd)
            raise
        with handle:
            yield handle
        os.replace(temp_path, path)
    except BaseException as original_error:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        except OSError as cleanup_error:
            raise original_error from cleanup_error
        raise


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Atomically replace a text file without following an existing target symlink."""
    with atomic_text_writer(path, encoding=encoding) as handle:
        handle.write(text)
