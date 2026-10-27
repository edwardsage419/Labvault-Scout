import struct
import zipfile
from pathlib import Path

import pytest

import labvault_scout.identifier as identifier


@pytest.mark.parametrize(
    "entries,directory_size,zip64_locator",
    [
        (10_001, 0, False),
        (1, 2 * 1024 * 1024 + 1, False),
        (0xFFFF, 0, False),
        (1, 0xFFFFFFFF, False),
        (1, 1, True),
    ],
)
def test_zip_directory_limit_checked_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    entries: int, directory_size: int, zip64_locator: bool,
) -> None:
    path = tmp_path / "oversized.zip"
    locator = b"PK\x06\x07" + bytes(16) if zip64_locator else b""
    end_record = struct.pack(
        "<4s4H2LH", b"PK\x05\x06",
        0, 0, entries, entries, directory_size, 0, 0,
    )
    path.write_bytes(b"PK\x03\x04" + locator + end_record)
    original = path.read_bytes()

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse an oversized directory")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == (
        "ZIP directory exceeds bounded inspection limits"
    )
    assert path.read_bytes() == original


def test_small_zip_directory_still_identifies_format(tmp_path: Path) -> None:
    path = tmp_path / "book.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
    assert identifier.inspect_zip_container(path) == "OOXML Excel"
