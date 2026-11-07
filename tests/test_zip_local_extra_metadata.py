"""Local ZIP extra metadata must be structurally valid before classification."""

import io
import struct
import zipfile
from pathlib import Path

import pytest

import labvault_scout.identifier as identifier


@pytest.mark.parametrize(
    "local_extra, expected",
    [
        (bytes.fromhex("01000800"), "Invalid ZIP local extra"),
        (bytes.fromhex("00"), "Invalid ZIP local extra"),
        (bytes.fromhex("666601005a"), "OOXML Excel"),
    ],
    ids=["truncated_zip64_field", "trailing_byte", "valid_unknown_field"],
)
def test_zip_local_extra_without_zip64_sentinels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    local_extra: bytes, expected: str,
) -> None:
    path = tmp_path / "local-extra.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("xl/workbook.xml", b"<workbook/>")
    data = bytearray(path.read_bytes())
    name_length, old_extra_length = struct.unpack_from("<HH", data, 26)
    assert old_extra_length == 0
    insert_at = 30 + name_length
    data[insert_at:insert_at] = local_extra
    struct.pack_into("<H", data, 28, len(local_extra))
    first_central = data.find(bytes.fromhex("504b0102"))
    second_central = data.find(bytes.fromhex("504b0102"), first_central + 4)
    end = data.rfind(bytes.fromhex("504b0506"))
    assert first_central > 0 and second_central > first_central
    assert end > second_central
    second_local = struct.unpack_from("<I", data, second_central + 42)[0]
    struct.pack_into(
        "<I", data, second_central + 42, second_local + len(local_extra)
    )
    struct.pack_into("<I", data, end + 16, first_central)
    path.write_bytes(data)
    original = path.read_bytes()

    # Python's ZIP reader tolerates these local extra field structures.
    with zipfile.ZipFile(path) as archive:
        assert archive.read("[Content_Types].xml") == b"<Types/>"

    if expected != "OOXML Excel":
        def fail_if_parsed(*args: object, **kwargs: object) -> None:
            raise AssertionError("ZipFile must not parse invalid local extras")

        monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "local_extra, expected",
    [
        (bytes.fromhex("00"), "Invalid ZIP local extra"),
        (bytes.fromhex("666605005a"), "Invalid ZIP local extra"),
        (bytes.fromhex("666601005a"), "OOXML Excel"),
    ],
    ids=["trailing_byte", "overlong_field", "valid_unknown_field"],
)
def test_streaming_zip_local_extra_framing_checked_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    local_extra: bytes, expected: str,
) -> None:
    class NonSeekableWriter:
        def __init__(self) -> None:
            self.buffer = io.BytesIO()

        def write(self, data: bytes) -> int:
            return self.buffer.write(data)

        def flush(self) -> None:
            pass

    writer = NonSeekableWriter()
    with zipfile.ZipFile(writer, "w") as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("xl/workbook.xml", b"<workbook/>")

    data = bytearray(writer.buffer.getvalue())
    assert struct.unpack_from("<H", data, 6)[0] & 0x0008
    name_length, old_extra_length = struct.unpack_from("<HH", data, 26)
    assert old_extra_length == 0
    data[30 + name_length:30 + name_length] = local_extra
    struct.pack_into("<H", data, 28, len(local_extra))
    first_central = data.find(bytes.fromhex("504b0102"))
    second_central = data.find(bytes.fromhex("504b0102"), first_central + 4)
    end = data.rfind(bytes.fromhex("504b0506"))
    assert first_central > 0 and second_central > first_central
    assert end > second_central
    second_local = struct.unpack_from("<I", data, second_central + 42)[0]
    struct.pack_into(
        "<I", data, second_central + 42, second_local + len(local_extra)
    )
    struct.pack_into("<I", data, end + 16, first_central)
    path = tmp_path / "streaming-extra.xlsx"
    path.write_bytes(data)
    original = path.read_bytes()

    # The standard reader tolerates malformed local extra field framing.
    with zipfile.ZipFile(path) as archive:
        assert archive.read("[Content_Types].xml") == b"<Types/>"

    if expected != "OOXML Excel":
        def fail_if_parsed(*args: object, **kwargs: object) -> None:
            raise AssertionError("ZipFile must not parse invalid streaming local extras")

        monkeypatch.setattr(identifier.zipfile, "ZipFile", fail_if_parsed)
    assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == original
