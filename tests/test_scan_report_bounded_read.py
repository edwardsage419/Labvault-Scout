"""Keep untrusted scan-report reads bounded by inspected file size."""

from pathlib import Path

import labvault_scout.compare as compare


def test_scan_report_reader_requests_only_initial_size_plus_one(
    tmp_path: Path, monkeypatch,
) -> None:
    report = tmp_path / "scan.json"
    report.write_bytes(b'{"files": []}')
    expected_size = report.stat().st_size

    original_fdopen = compare.os.fdopen
    requested_sizes: list[int] = []

    class ObservedStream:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def fileno(self):
            return self.stream.fileno()

        def read(self, size=-1):
            requested_sizes.append(size)
            assert 0 < size <= expected_size + 1, "Unbounded scan report read"
            return self.stream.read(size)

    def observe_fdopen(fd, *args, **kwargs):
        return ObservedStream(original_fdopen(fd, *args, **kwargs))

    with monkeypatch.context() as patch:
        patch.setattr(compare.os, "fdopen", observe_fdopen)
        assert compare.load_scan_report(report) == {"files": []}

    assert requested_sizes == [expected_size + 1]
    assert report.read_bytes() == b'{"files": []}'
