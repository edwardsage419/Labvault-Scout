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
    assert struct.unpack_from("<I", data, 18)[0] == 0
    assert struct.unpack_from("<I", data, 22)[0] == 0
    central = data.find(bytes.fromhex("504b0102"))
    assert central > 0
    assert struct.unpack_from("<I", data, central + 20)[0] > 0
    path = tmp_path / "descriptor.xlsx"
    path.write_bytes(data)
    assert identifier.inspect_zip_container(path) == "OOXML Excel"
    assert path.read_bytes() == data

@pytest.mark.parametrize("forged_size", [0, 0xFFFFFF00])
def test_zip_local_compressed_size_mismatch_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forged_size: int,
) -> None:
    path = tmp_path / "forged-local-compressed-size.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")

    data = bytearray(path.read_bytes())
    central = data.find(bytes.fromhex("504b0102"))
    assert central > 0
    actual_size = struct.unpack_from("<I", data, central + 20)[0]
    assert actual_size > 0 and actual_size != forged_size
    struct.pack_into("<I", data, 18, forged_size)
    path.write_bytes(data)
    original = path.read_bytes()

    # ZipFile uses the central size and can still read the contradictory member.
    with zipfile.ZipFile(path) as archive:
        assert archive.read("[Content_Types].xml") == b"<Types/>"

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse conflicting local sizes")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == (
        "Ambiguous ZIP local compressed size"
    )
    assert path.read_bytes() == original


@pytest.mark.parametrize("forged_size", [0, 0xFFFFFF00])
def test_zip_local_uncompressed_size_mismatch_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forged_size: int,
) -> None:
    path = tmp_path / "forged-local-uncompressed-size.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")

    data = bytearray(path.read_bytes())
    central = data.find(bytes.fromhex("504b0102"))
    assert central > 0
    actual_size = struct.unpack_from("<I", data, central + 24)[0]
    assert actual_size > 0 and actual_size != forged_size
    struct.pack_into("<I", data, 22, forged_size)
    path.write_bytes(data)
    original = path.read_bytes()

    # ZipFile trusts the central size and can still read the contradictory member.
    with zipfile.ZipFile(path) as archive:
        assert archive.read("[Content_Types].xml") == b"<Types/>"

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse conflicting local sizes")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == (
        "Ambiguous ZIP local uncompressed size"
    )
    assert path.read_bytes() == original

@pytest.mark.parametrize("boundary", ["next_member", "central_directory"])
def test_zip_compressed_data_boundary_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str,
) -> None:
    path = tmp_path / "forged-compressed-boundary.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")

    data = bytearray(path.read_bytes())
    first_central = data.find(bytes.fromhex("504b0102"))
    second_central = data.find(bytes.fromhex("504b0102"), first_central + 4)
    assert first_central > 0 and second_central > first_central
    first_local = struct.unpack_from("<I", data, first_central + 42)[0]
    second_local = struct.unpack_from("<I", data, second_central + 42)[0]
    if boundary == "next_member":
        local_offset, central_offset, limit = first_local, first_central, second_local
    else:
        local_offset, central_offset, limit = second_local, second_central, first_central
    name_size, extra_size = struct.unpack_from("<HH", data, local_offset + 26)
    data_start = local_offset + 30 + name_size + extra_size
    forged_size = limit - data_start + 1
    assert forged_size > 0
    # Keep both size declarations consistent while crossing a structural boundary.
    struct.pack_into("<I", data, local_offset + 18, forged_size)
    struct.pack_into("<I", data, central_offset + 20, forged_size)
    path.write_bytes(data)
    original = path.read_bytes()

    with zipfile.ZipFile(path) as archive:
        assert "[Content_Types].xml" in archive.namelist()
        assert "xl/workbook.xml" in archive.namelist()

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse overlapping compressed data")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == (
        "Invalid ZIP compressed data boundary"
    )
    assert path.read_bytes() == original


def test_zip_empty_member_keeps_bounded_classification(tmp_path: Path) -> None:
    path = tmp_path / "empty-member.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
        archive.writestr("empty", b"")
    assert identifier.inspect_zip_container(path) == "OOXML Excel"


def _zip_with_data_descriptors() -> bytes:
    """Create a small ZIP using real non-seekable streaming descriptors."""
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
    return writer.buffer.getvalue()


@pytest.mark.parametrize("descriptor_field_offset", [4, 8, 12])
def test_zip_data_descriptor_mismatch_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, descriptor_field_offset: int,
) -> None:
    data = bytearray(_zip_with_data_descriptors())
    descriptor = data.find(b"PK\x07\x08")
    assert descriptor > 0
    # Mutate the CRC, compressed size, or uncompressed size of the descriptor.
    data[descriptor + descriptor_field_offset] ^= 1
    path = tmp_path / "forged-descriptor.xlsx"
    path.write_bytes(data)
    original = path.read_bytes()

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse inconsistent data descriptors")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == (
        "Ambiguous ZIP data descriptor metadata"
    )
    assert path.read_bytes() == original


def test_zip_data_descriptor_truncated_by_next_header_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = bytearray(_zip_with_data_descriptors())
    next_local = data.find(b"PK\x03\x04", 4)
    first_central = data.find(b"PK\x01\x02")
    assert next_local > 0 and first_central > next_local
    name_size, extra_size = struct.unpack_from("<HH", data, 26)
    data_start = 30 + name_size + extra_size
    # The forged central size leaves fewer than 12 bytes for the descriptor.
    forged_size = next_local - data_start - 8
    assert forged_size > 0
    struct.pack_into("<I", data, first_central + 20, forged_size)
    path = tmp_path / "short-descriptor.xlsx"
    path.write_bytes(data)
    original = path.read_bytes()

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse a truncated data descriptor")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == (
        "Invalid ZIP data descriptor boundary"
    )
    assert path.read_bytes() == original


def test_zip_unsigned_data_descriptor_remains_accepted(tmp_path: Path) -> None:
    data = bytearray(_zip_with_data_descriptors())
    first_descriptor = data.find(b"PK\x07\x08")
    second_local = data.find(b"PK\x03\x04", 4)
    assert first_descriptor > 0 and second_local > first_descriptor
    # The ZIP specification permits descriptors without the optional signature.
    del data[first_descriptor:first_descriptor + 4]
    first_central = data.find(b"PK\x01\x02")
    second_central = data.find(b"PK\x01\x02", first_central + 4)
    end = data.rfind(b"PK\x05\x06")
    assert first_central > 0 and second_central > first_central and end > second_central
    struct.pack_into("<I", data, second_central + 42, second_local - 4)
    struct.pack_into("<I", data, end + 16, first_central)
    path = tmp_path / "unsigned-descriptor.xlsx"
    path.write_bytes(data)

    with zipfile.ZipFile(path) as archive:
        assert archive.read("[Content_Types].xml") == b"<Types/>"
    assert identifier.inspect_zip_container(path) == "OOXML Excel"
    assert path.read_bytes() == data


def _zip_with_forced_zip64_local_member(streaming: bool) -> bytes:
    """Generate a small valid ZIP64 local member with ordinary central records."""
    class NonSeekableWriter:
        def __init__(self) -> None:
            self.buffer = io.BytesIO()

        def write(self, data: bytes) -> int:
            return self.buffer.write(data)

        def flush(self) -> None:
            pass

    writer = NonSeekableWriter() if streaming else io.BytesIO()
    with zipfile.ZipFile(writer, "w") as archive:
        with archive.open("[Content_Types].xml", "w", force_zip64=True) as member:
            member.write(b"<Types/>")
        archive.writestr("xl/workbook.xml", b"<workbook/>")
    data = bytearray(writer.buffer.getvalue() if streaming else writer.getvalue())
    if not streaming:
        # Python versions differ in whether force_zip64 leaves local sentinels.
        # Both sentinel fields with the generated ZIP64 extra are valid.
        struct.pack_into("<II", data, 18, 0xFFFFFFFF, 0xFFFFFFFF)
    return bytes(data)


@pytest.mark.parametrize("streaming", [False, True])
def test_zip_forced_zip64_local_sizes_remain_accepted(
    tmp_path: Path, streaming: bool,
) -> None:
    data = _zip_with_forced_zip64_local_member(streaming)
    local_sizes = struct.unpack_from("<II", data, 18)
    if streaming:
        assert local_sizes in {(0, 0), (0xFFFFFFFF, 0xFFFFFFFF)}
    else:
        assert local_sizes == (0xFFFFFFFF, 0xFFFFFFFF)
    assert bytes.fromhex("504b0607") not in data  # No ZIP64 EOCD locator.
    assert bool(struct.unpack_from("<H", data, 6)[0] & 0x0008) == streaming
    path = tmp_path / "forced-zip64.xlsx"
    path.write_bytes(data)

    with zipfile.ZipFile(path) as archive:
        assert archive.read("[Content_Types].xml") == b"<Types/>"
    assert identifier.inspect_zip_container(path) == "OOXML Excel"
    assert path.read_bytes() == data


@pytest.mark.parametrize(
    "extra_offset,expected_status",
    [
        (0, "Invalid ZIP local ZIP64 extra"),
        (4, "Ambiguous ZIP local uncompressed size"),
        (12, "Ambiguous ZIP local compressed size"),
    ],
)
def test_zip_local_zip64_extra_conflicts_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    extra_offset: int, expected_status: str,
) -> None:
    data = bytearray(_zip_with_forced_zip64_local_member(False))
    name_length = struct.unpack_from("<H", data, 26)[0]
    extra_start = 30 + name_length
    assert data[extra_start:extra_start + 4] == bytes.fromhex("01001000")
    data[extra_start + extra_offset] ^= 1
    path = tmp_path / "forged-local-zip64.xlsx"
    path.write_bytes(data)
    original = path.read_bytes()

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse conflicting ZIP64 local sizes")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == expected_status
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "appended_extra", [bytes.fromhex("01000000"), bytes.fromhex("00")],
    ids=["duplicate_zip64", "trailing_byte"],
)
def test_zip_local_zip64_extra_rejects_duplicate_or_trailing_bytes_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, appended_extra: bytes,
) -> None:
    data = bytearray(_zip_with_forced_zip64_local_member(False))
    name_length, extra_length = struct.unpack_from("<HH", data, 26)
    insert_at = 30 + name_length + extra_length
    data[insert_at:insert_at] = appended_extra
    struct.pack_into("<H", data, 28, extra_length + len(appended_extra))
    first_central = data.find(bytes.fromhex("504b0102"))
    second_central = data.find(bytes.fromhex("504b0102"), first_central + 4)
    assert first_central > 0 and second_central > first_central
    second_local = struct.unpack_from("<I", data, second_central + 42)[0]
    struct.pack_into("<I", data, second_central + 42, second_local + len(appended_extra))
    end = data.rfind(bytes.fromhex("504b0506"))
    assert end > second_central
    struct.pack_into("<I", data, end + 16, first_central)
    path = tmp_path / "malformed-local-zip64.xlsx"
    path.write_bytes(data)
    original = path.read_bytes()

    # The standard ZIP reader accepts the conflicting local extra structure.
    with zipfile.ZipFile(path) as archive:
        assert archive.read("[Content_Types].xml") == b"<Types/>"

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse malformed local ZIP64 extras")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == "Invalid ZIP local ZIP64 extra"
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "padding", [b"\x00", b"junk"], ids=["single_byte", "four_bytes"]
)
def test_zip_data_descriptor_inter_member_padding_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, padding: bytes,
) -> None:
    data = bytearray(_zip_with_data_descriptors())
    descriptor = data.find(b"PK\x07\x08")
    second_local = data.find(b"PK\x03\x04", 4)
    assert descriptor > 0 and second_local == descriptor + 16
    # A valid descriptor prefix with extra bytes must not cross a member boundary.
    data[second_local:second_local] = padding
    first_central = data.find(b"PK\x01\x02")
    second_central = data.find(b"PK\x01\x02", first_central + 4)
    end = data.rfind(b"PK\x05\x06")
    assert 0 < first_central < second_central < end
    struct.pack_into("<I", data, second_central + 42, second_local + len(padding))
    struct.pack_into("<I", data, end + 16, first_central)
    path = tmp_path / "descriptor-gap.xlsx"
    path.write_bytes(data)
    original = path.read_bytes()

    # The standard reader ignores the extra bytes between local members.
    with zipfile.ZipFile(path) as archive:
        assert archive.read("[Content_Types].xml") == b"<Types/>"

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse ambiguous descriptor gaps")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == (
        "Ambiguous ZIP data descriptor metadata"
    )
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "padding",
    [b"\x00", b"junk", b"PK\x06\x08" + struct.pack("<I", 5) + b"ABCD"],
    ids=["single_byte", "four_bytes", "malformed_archive_extra"],
)
def test_zip_last_data_descriptor_unaccounted_bytes_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, padding: bytes,
) -> None:
    data = bytearray(_zip_with_data_descriptors())
    first_central = data.find(b"PK\x01\x02")
    last_descriptor = data.rfind(b"PK\x07\x08", 0, first_central)
    assert first_central > 0 and last_descriptor + 16 == first_central
    data[first_central:first_central] = padding
    end = data.rfind(b"PK\x05\x06")
    assert end > first_central
    struct.pack_into("<I", data, end + 16, first_central + len(padding))
    path = tmp_path / "last-descriptor-gap.xlsx"
    path.write_bytes(data)
    original = path.read_bytes()

    # ZipFile ignores unaccounted bytes before the central directory.
    with zipfile.ZipFile(path) as archive:
        assert archive.read("xl/workbook.xml") == b"<workbook/>"

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse ambiguous trailing bytes")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == (
        "Ambiguous ZIP data descriptor metadata"
    )
    assert path.read_bytes() == original


@pytest.mark.parametrize("payload", [b"", b"ABCD"], ids=["empty", "four_bytes"])
def test_zip_last_data_descriptor_archive_extra_record_remains_accepted(
    tmp_path: Path, payload: bytes,
) -> None:
    data = bytearray(_zip_with_data_descriptors())
    first_central = data.find(b"PK\x01\x02")
    last_descriptor = data.rfind(b"PK\x07\x08", 0, first_central)
    assert first_central > 0 and last_descriptor + 16 == first_central
    record = b"PK\x06\x08" + struct.pack("<I", len(payload)) + payload
    data[first_central:first_central] = record
    end = data.rfind(b"PK\x05\x06")
    struct.pack_into("<I", data, end + 16, first_central + len(record))
    path = tmp_path / "archive-extra.xlsx"
    path.write_bytes(data)

    with zipfile.ZipFile(path) as archive:
        assert archive.read("xl/workbook.xml") == b"<workbook/>"
    assert identifier.inspect_zip_container(path) == "OOXML Excel"
    assert path.read_bytes() == data


def _zip_with_central_extra_variant(kind: str) -> bytes:
    """Forge a small central-only ZIP64 extra without touching local members."""
    writer = io.BytesIO()
    with zipfile.ZipFile(writer, "w") as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("xl/workbook.xml", b"<workbook/>")
    data = bytearray(writer.getvalue())
    central = data.find(b"PK\x01\x02")
    end = data.rfind(b"PK\x05\x06")
    assert 0 < central < end
    name_size, extra_size = struct.unpack_from("<HH", data, central + 28)
    assert extra_size == 0
    original_directory_size = struct.unpack_from("<I", data, end + 12)[0]
    compressed = struct.unpack_from("<I", data, central + 20)[0]
    uncompressed = struct.unpack_from("<I", data, central + 24)[0]
    local_offset = struct.unpack_from("<I", data, central + 42)[0]

    if kind in {"sizes_offset", "missing"}:
        struct.pack_into("<II", data, central + 20, 0xFFFFFFFF, 0xFFFFFFFF)
    if kind in {"sizes_offset", "offset"}:
        struct.pack_into("<I", data, central + 42, 0xFFFFFFFF)
    if kind == "sizes_offset":
        payload = struct.pack("<QQQ", uncompressed, compressed, local_offset)
        extra = struct.pack("<HH", 1, len(payload)) + payload
    elif kind == "offset":
        payload = struct.pack("<Q", local_offset)
        extra = struct.pack("<HH", 1, len(payload)) + payload
    elif kind == "trailing":
        extra = b"\x00"
    elif kind == "duplicate":
        extra = b"\x01\x00\x00\x00" * 2
    elif kind == "overflow":
        extra = struct.pack("<HH", 0xCAFE, 5) + b"ABCD"
    elif kind == "missing":
        extra = b""
    else:
        raise AssertionError(kind)

    insert_at = central + 46 + name_size
    data[insert_at:insert_at] = extra
    struct.pack_into("<H", data, central + 30, len(extra))
    struct.pack_into(
        "<I", data, end + len(extra) + 12,
        original_directory_size + len(extra),
    )
    return bytes(data)


@pytest.mark.parametrize("kind", ["sizes_offset", "offset"])
def test_zip_central_zip64_member_fields_remain_accepted(
    tmp_path: Path, kind: str,
) -> None:
    data = _zip_with_central_extra_variant(kind)
    path = tmp_path / "central-zip64.xlsx"
    path.write_bytes(data)
    with zipfile.ZipFile(path) as archive:
        assert archive.read("[Content_Types].xml") == b"<Types/>"
    assert identifier.inspect_zip_container(path) == "OOXML Excel"
    assert path.read_bytes() == data


@pytest.mark.parametrize(
    "kind,expected_status",
    [
        ("trailing", "Invalid ZIP directory extra"),
        ("overflow", "Invalid ZIP directory extra"),
        ("duplicate", "Invalid ZIP directory ZIP64 extra"),
        ("missing", "Invalid ZIP directory ZIP64 extra"),
    ],
)
def test_zip_central_extra_malformed_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    kind: str, expected_status: str,
) -> None:
    data = _zip_with_central_extra_variant(kind)
    path = tmp_path / "forged-central-extra.xlsx"
    path.write_bytes(data)
    if kind in {"trailing", "duplicate"}:
        # The standard reader accepts these contradictory central extras.
        with zipfile.ZipFile(path) as archive:
            assert archive.read("[Content_Types].xml") == b"<Types/>"

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not parse malformed central extras")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == expected_status
    assert path.read_bytes() == data


@pytest.mark.parametrize("forged_size", [0x100000000, 0x100000001])
def test_zip64_descriptor_large_uncompressed_size_rejected_without_overflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forged_size: int,
) -> None:
    data = bytearray(_zip_with_data_descriptors())
    first_central = data.find(b"PK\x01\x02")
    end = data.rfind(b"PK\x05\x06")
    assert 0 < first_central < end
    assert struct.unpack_from("<H", data, first_central + 8)[0] & 0x0008
    name_size, extra_size = struct.unpack_from("<HH", data, first_central + 28)
    assert extra_size == 0

    # A tiny archive can declare a ZIP64 uncompressed size in its central
    # record. The existing 32-bit descriptor must be rejected without overflow.
    struct.pack_into("<I", data, first_central + 24, 0xFFFFFFFF)
    extra = struct.pack("<HHQ", 1, 8, forged_size)
    insert_at = first_central + 46 + name_size
    data[insert_at:insert_at] = extra
    struct.pack_into("<H", data, first_central + 30, len(extra))
    end += len(extra)
    directory_size = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, directory_size + len(extra))

    path = tmp_path / "zip64-oversized-descriptor.xlsx"
    path.write_bytes(data)
    original = path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        assert "[Content_Types].xml" in archive.namelist()

    def fail_if_parsed(*args: object, **kwargs: object) -> None:
        raise AssertionError("ZipFile must not classify inconsistent ZIP64 metadata")

    monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == (
        "Ambiguous ZIP data descriptor metadata"
    )
    assert path.read_bytes() == original
