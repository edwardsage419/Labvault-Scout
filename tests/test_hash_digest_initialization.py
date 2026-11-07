import os
from pathlib import Path

import pytest

import labvault_scout.hashing as hashing


@pytest.mark.parametrize("with_head", [True, False])
def test_hash_digest_initialization_failure_closes_open_stream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, with_head: bool,
) -> None:
    target = tmp_path / "research.bin"
    original = b"research source remains unchanged"
    target.write_bytes(original)
    streams = []

    class TrackingStream:
        def __init__(self, fd: int) -> None:
            self.fd = fd
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb) -> None:
            os.close(self.fd)
            self.closed = True

    def tracking_fdopen(fd: int, *_args, **_kwargs):
        stream = TrackingStream(fd)
        streams.append(stream)
        return stream

    def fail_sha256():
        raise RuntimeError("synthetic digest initialization failure")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(hashing.os, "fdopen", tracking_fdopen)
            patch.setattr(hashing.hashlib, "sha256", fail_sha256)
            with pytest.raises(RuntimeError, match="synthetic digest initialization failure"):
                if with_head:
                    hashing.sha256_with_head(target)
                else:
                    hashing.sha256_file(target)
        assert len(streams) == 1
        assert streams[0].closed, "stream must close when digest setup raises"
        with pytest.raises(OSError):
            os.fstat(streams[0].fd)
        assert target.read_bytes() == original
    finally:
        for stream in streams:
            if not stream.closed:
                os.close(stream.fd)
