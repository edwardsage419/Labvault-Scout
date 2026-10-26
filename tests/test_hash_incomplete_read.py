"""Regression tests for a premature EOF with unchanged file metadata."""

from pathlib import Path

import pytest

import labvault_scout.hashing as hashing


@pytest.mark.parametrize("with_head", [True, False])
def test_hash_rejects_premature_eof_without_metadata_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, with_head: bool,
) -> None:
    target = tmp_path / "research.bin"
    content = b"original research bytes"
    target.write_bytes(content)
    original_fdopen = hashing.os.fdopen
    streams = []

    class PrematureEOFStream:
        def __init__(self, stream):
            self.stream = stream
            self.reads = 0

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def fileno(self):
            return self.stream.fileno()

        def read(self, size=-1):
            self.reads += 1
            if self.reads == 1:
                return self.stream.read(min(size, 3))
            return b""

    def premature_fdopen(fd, mode):
        wrapper = PrematureEOFStream(original_fdopen(fd, mode))
        streams.append(wrapper)
        return wrapper

    with monkeypatch.context() as patch:
        patch.setattr(hashing.os, "fdopen", premature_fdopen)
        with pytest.raises(
            hashing.FileChangedDuringScan, match="Incomplete file read: byte count mismatch"
        ):
            if with_head:
                hashing.sha256_with_head(target, head_size=8, chunk_size=4)
            else:
                hashing.sha256_file(target, chunk_size=4)

    assert len(streams) == 1
    assert streams[0].reads == 2
    assert streams[0].stream.closed
    assert target.read_bytes() == content
