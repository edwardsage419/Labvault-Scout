import io
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


@pytest.mark.parametrize(
    "disk_number,directory_disk_number",
    [(1, 1), (0, 1), (1, 0)],
)
def test_zip_eocd_multidisk_metadata_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    disk_number: int, directory_disk_number: int,
) -> None:
    path = tmp_path / "forged-disk.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")

    data = bytearray(path.read_bytes())
    end = data.rfind(bytes.fromhex("504b0506"))
    assert end >= 0
    struct.pack_into("<HH", data, end + 4, disk_number, directory_disk_number)
    path.write_bytes(data)
    original = path.read_bytes()

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse multi-disk metadata")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == (
        "Unsupported ZIP multi-disk metadata"
    )
    assert path.read_bytes() == original


@pytest.mark.parametrize("declared_offset", [0, 1])
def test_zip_eocd_directory_offset_mismatch_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, declared_offset: int,
) -> None:
    path = tmp_path / "forged-offset.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")

    data = bytearray(path.read_bytes())
    end = data.rfind(bytes.fromhex("504b0506"))
    assert end >= 0
    actual_offset = struct.unpack_from("<I", data, end + 16)[0]
    assert actual_offset > declared_offset
    struct.pack_into("<I", data, end + 16, declared_offset)
    path.write_bytes(data)
    original = path.read_bytes()

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse an inconsistent directory offset")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == (
        "Ambiguous ZIP directory offset"
    )
    assert path.read_bytes() == original


@pytest.mark.parametrize("mutation", ["overstated_comment", "trailing_byte"])
def test_zip_eocd_comment_length_mismatch_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str,
) -> None:
    path = tmp_path / "forged-comment.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")

    data = bytearray(path.read_bytes())
    end = data.rfind(bytes.fromhex("504b0506"))
    assert end >= 0
    if mutation == "overstated_comment":
        struct.pack_into("<H", data, end + 20, 1)
    else:
        data.extend(b"X")
    path.write_bytes(data)
    original = path.read_bytes()

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse an inconsistent end record")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == (
        "Ambiguous ZIP end record comment length"
    )
    assert path.read_bytes() == original


def test_zip_eocd_valid_comment_still_identifies_format(tmp_path: Path) -> None:
    path = tmp_path / "commented.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
        archive.comment = b"research archive notes"
    assert identifier.inspect_zip_container(path) == "OOXML Excel"


@pytest.mark.parametrize("variant", ["forged_empty_directory", "short_marker"])
def test_zip_eocd_signature_inside_comment_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str,
) -> None:
    path = tmp_path / "ambiguous-end-record.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")

    if variant == "forged_empty_directory":
        # The forged end record would make ZipFile see an empty archive.
        fake_offset = path.read_bytes().rfind(b"PK\x05\x06") + 22
        comment = struct.pack(
            "<4s4H2LH", b"PK\x05\x06",
            0, 0, 0, 0, 0, fake_offset, 0,
        )
    else:
        comment = b"notes PK\x05\x06 suffix"
    with zipfile.ZipFile(path, "a") as archive:
        archive.comment = comment
    original = path.read_bytes()

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse ambiguous end records")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == (
        "Ambiguous ZIP end record signatures"
    )
    assert path.read_bytes() == original


def test_zip_invalid_utf8_member_name_returns_invalid_container(tmp_path: Path) -> None:
    path = tmp_path / "invalid-utf8.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")

    data = bytearray(path.read_bytes())
    record = data.find(b"PK\x01\x02")
    assert record >= 0
    flags = struct.unpack_from("<H", data, record + 8)[0]
    struct.pack_into("<H", data, record + 8, flags | 0x800)
    data[record + 46] = 0xFF
    path.write_bytes(data)
    original = path.read_bytes()

    assert identifier.inspect_zip_container(path) == "Invalid ZIP container"
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "forged_offset,expected_status",
    [
        (0xFFFFFF00, "Invalid ZIP local header offset"),
        (1, "Invalid ZIP local file header"),
    ],
)
def test_zip_local_header_offset_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    forged_offset: int, expected_status: str,
) -> None:
    path = tmp_path / "forged-local-offset.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")

    data = bytearray(path.read_bytes())
    record = data.find(b"PK\x01\x02")
    assert record >= 0
    struct.pack_into("<I", data, record + 42, forged_offset)
    path.write_bytes(data)
    original = path.read_bytes()

    # zipfile can list the forged member names without reading their local headers.
    with zipfile.ZipFile(path) as archive:
        assert "[Content_Types].xml" in archive.namelist()

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse an invalid local header offset")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == expected_status
    assert path.read_bytes() == original


def test_zip_local_member_name_mismatch_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "forged-local-name.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")

    data = bytearray(path.read_bytes())
    assert data[:4] == b"PK\x03\x04"
    data[30] = ord("X")  # Alter the local name while keeping the directory name.
    path.write_bytes(data)
    original = path.read_bytes()

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse inconsistent local member names")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == "Ambiguous ZIP local member name"
    assert path.read_bytes() == original

def test_zip_local_compression_method_mismatch_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "forged-local-method.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")

    data = bytearray(path.read_bytes())
    assert data[:4] == b"PK\x03\x04"
    central = data.find(b"PK\x01\x02")
    assert central > 0
    assert struct.unpack_from("<H", data, central + 10)[0] == 0
    # The local method disagrees with the central directory's stored method.
    struct.pack_into("<H", data, 8, 8)
    path.write_bytes(data)
    original = path.read_bytes()

    # ZipFile trusts the central directory and still lists the member names.
    with zipfile.ZipFile(path) as archive:
        assert "[Content_Types].xml" in archive.namelist()

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse conflicting compression methods")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == (
        "Ambiguous ZIP local compression method"
    )
    assert path.read_bytes() == original

@pytest.mark.parametrize("forged_flags", [0x0008, 0x0800])
def test_zip_local_general_purpose_flags_mismatch_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forged_flags: int,
) -> None:
    path = tmp_path / "forged-local-flags.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")

    data = bytearray(path.read_bytes())
    assert data[:4] == bytes.fromhex("504b0304")
    central = data.find(bytes.fromhex("504b0102"))
    assert central > 0
    assert struct.unpack_from("<H", data, central + 8)[0] == 0
    struct.pack_into("<H", data, 6, forged_flags)
    path.write_bytes(data)
    original = path.read_bytes()

    # ZipFile reads member names despite contradictory local flags.
    with zipfile.ZipFile(path) as archive:
        assert "[Content_Types].xml" in archive.namelist()

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse conflicting local flags")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == (
        "Ambiguous ZIP local general-purpose flags"
    )
    assert path.read_bytes() == original


def test_zip_local_crc_mismatch_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "forged-local-crc.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")

    data = bytearray(path.read_bytes())
    central = data.find(bytes.fromhex("504b0102"))
    assert central > 0
    original_crc = struct.unpack_from("<I", data, central + 16)[0]
    # The local header disagrees with the central directory CRC.
    struct.pack_into("<I", data, 14, original_crc ^ 0xFFFFFFFF)
    path.write_bytes(data)
    original = path.read_bytes()

    # ZipFile uses the central CRC and still reads the forged member.
    with zipfile.ZipFile(path) as archive:
        assert archive.read("[Content_Types].xml") == b"<Types/>"

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse inconsistent local CRC")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == "Ambiguous ZIP local CRC"
    assert path.read_bytes() == original


def test_zip_data_descriptor_allows_zero_local_crc(tmp_path: Path) -> None:
    class NonSeekableWriter:
        def __init__(self) -> None:
            self.buffer = io.BytesIO()

        def write(self, data: bytes) -> int:
            return self.buffer.write(data)

        def flush(self) -> None:
            pass

    writer = NonSeekableWriter()
    with zipfile.ZipFile(writer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")

    data = writer.buffer.getvalue()
    assert struct.unpack_from("<H", data, 6)[0] & 0x0008
    assert struct.unpack_from("<I", data, 14)[0] == 0
    path = tmp_path / "descriptor.xlsx"
    path.write_bytes(data)
    assert identifier.inspect_zip_container(path) == "OOXML Excel"
    assert path.read_bytes() == data
