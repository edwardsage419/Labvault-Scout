"""Reject scan paths that cannot be encoded in UTF-8 report artifacts."""

from pathlib import Path

import pytest

import labvault_scout.cli as cli


@pytest.mark.parametrize("failure_mode", ["file", "walk_error"])
def test_scan_fails_closed_for_unencodable_report_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_mode: str,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    healthy = source / "healthy.csv"
    healthy.write_bytes(b"value\n1\n")
    output = tmp_path / "report"
    unencodable = source / "invalid-\udcff.csv"

    def fake_iter(root: Path, excluded=None, on_error=None):
        if failure_mode == "walk_error":
            assert on_error is not None
            on_error(unencodable, PermissionError("blocked"))
        else:
            yield unencodable

    monkeypatch.setattr(cli, "iter_files", fake_iter)

    with pytest.raises(ValueError, match="cannot be represented safely"):
        cli.scan(source, output)

    assert healthy.read_bytes() == b"value\n1\n"
    assert not (output / "scan.json").exists()
