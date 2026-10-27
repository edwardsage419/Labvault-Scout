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


@pytest.mark.parametrize(
    "actual_entries,expected_status",
    [
        (3, "Ambiguous ZIP directory entry count"),
        (10_001, "ZIP directory exceeds bounded inspection limits"),
    ],
)
def test_zip_directory_actual_count_checked_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    actual_entries: int, expected_status: str,
) -> None:
    path = tmp_path / "forged-count.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
        for index in range(actual_entries - 2):
            archive.writestr(f"extra/{index:05d}", "")

    data = bytearray(path.read_bytes())
    end = data.rfind(b"PK\x05\x06")
    assert end >= 0
    struct.pack_into("<HH", data, end + 8, 1, 1)
    path.write_bytes(data)
    original = path.read_bytes()

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse an inconsistent directory")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == expected_status
    assert path.read_bytes() == original

@pytest.mark.parametrize("length_field_offset", [28, 30, 32])
def test_zip_directory_overlong_variable_field_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, length_field_offset: int,
) -> None:
    path = tmp_path / "overlong-member.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")

    data = bytearray(path.read_bytes())
    last_record = data.rfind(b"PK\x01\x02")
    assert last_record >= 0
    # Forge a filename, extra-field, or comment length beyond the directory.
    struct.pack_into("<H", data, last_record + length_field_offset, 500)
    path.write_bytes(data)
    original = path.read_bytes()

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse an overlong directory record")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == (
        "Invalid ZIP directory record length"
    )
    assert path.read_bytes() == original
