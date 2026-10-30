"""Regression tests for ZIP64 streaming descriptors and reordered central records.

Synthetic archives only. Scanned inputs remain unchanged.
"""
from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

import pytest

LOCAL = b"PK\x03\x04"
CENTRAL = b"PK\x01\x02"
DESCRIPTOR = b"PK\x07\x08"
EOCD = b"PK\x05\x06"
FIRST_NAME = "[Content_Types].xml"
SECOND_NAME = "xl/workbook.xml"
FIRST_CONTENT = b"<Types/>"
SECOND_CONTENT = b"<workbook/>"


class NonSeekableWriter:
    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, data: bytes) -> int:
        return self.buffer.write(data)

    def flush(self) -> None:
        pass


def make_streaming_zip64_member_association(variant: str) -> bytes:
    """Use a central ZIP64 offset with two distinct streaming descriptors."""
    if variant not in {"valid", "first-descriptor-crc", "second-descriptor-crc"}:
        raise ValueError(variant)
    writer = NonSeekableWriter()
    with zipfile.ZipFile(writer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        with archive.open(FIRST_NAME, "w", force_zip64=True) as member:
            member.write(FIRST_CONTENT)
        archive.writestr(SECOND_NAME, SECOND_CONTENT)
    data = bytearray(writer.buffer.getvalue())
    first_local = data.find(LOCAL)
    second_local = data.find(LOCAL, first_local + 4)
    first_descriptor = data.find(DESCRIPTOR)
    second_descriptor = data.find(DESCRIPTOR, first_descriptor + 4)
    first_central = data.find(CENTRAL)
    second_central = data.find(CENTRAL, first_central + 4)
    eocd = data.rfind(EOCD)
    assert first_local == 0 < first_descriptor < second_local < second_descriptor < first_central < second_central < eocd
    assert struct.unpack_from("<H", data, first_local + 6)[0] & 8
    assert struct.unpack_from("<H", data, second_local + 6)[0] & 8
    assert first_descriptor + 24 == second_local
    assert second_descriptor + 16 == first_central
    name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, first_central + 28)
    assert extra_len == 0
    assert struct.unpack_from("<I", data, first_central + 42)[0] == first_local
    assert second_central == first_central + 46 + name_len + comment_len

    # Store the first member's local offset in a ZIP64 central extra field.
    new_extra = struct.pack("<HHQ", 1, 8, first_local)
    insert_at = first_central + 46 + name_len
    data[insert_at:insert_at] = new_extra
    struct.pack_into("<H", data, first_central + 30, len(new_extra))
    struct.pack_into("<I", data, first_central + 42, 0xFFFFFFFF)
    second_central += len(new_extra)
    eocd += len(new_extra)
    struct.pack_into("<I", data, eocd + 12, eocd - first_central)

    # Reverse central records while preserving physical local-member order.
    data[first_central:eocd] = data[second_central:eocd] + data[first_central:second_central]
    if variant != "valid":
        descriptor = first_descriptor if variant == "first-descriptor-crc" else second_descriptor
        data[descriptor + 4] ^= 1
    return bytes(data)


@pytest.mark.parametrize("variant,expected", [
    ("valid", "OOXML Excel"),
    ("first-descriptor-crc", "Ambiguous ZIP data descriptor metadata"),
    ("second-descriptor-crc", "Ambiguous ZIP data descriptor metadata"),
])
def test_zip64_streaming_reordered_central_descriptor_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str, expected: str,
) -> None:
    """Bind both descriptors by local offsets regardless of central ordering."""
    from labvault_scout import identifier

    data = make_streaming_zip64_member_association(variant)
    path = tmp_path / f"streaming-zip64-reordered-{variant}.xlsx"
    path.write_bytes(data)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.namelist() == [SECOND_NAME, FIRST_NAME]
        assert archive.read(FIRST_NAME) == FIRST_CONTENT
        assert archive.read(SECOND_NAME) == SECOND_CONTENT
        assert archive.getinfo(FIRST_NAME).header_offset == 0

    if variant == "valid":
        assert identifier.inspect_zip_container(path) == expected
    else:
        def fail_if_classified(*args: object, **kwargs: object) -> None:
            raise AssertionError("Corrupt descriptor reached ZIP classification")
        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", fail_if_classified)
            assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == data


@pytest.mark.parametrize(
    "padding", [b"\x00", b"JUNK"],
    ids=["single-byte", "four-bytes"],
)
def test_zip64_reordered_streaming_descriptor_rejects_inter_member_padding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, padding: bytes,
) -> None:
    """Reject unaccounted bytes after a ZIP64 descriptor with reordered entries."""
    from labvault_scout import identifier

    data = bytearray(make_streaming_zip64_member_association("valid"))
    first_descriptor = data.find(DESCRIPTOR)
    second_local = data.find(LOCAL, 4)
    first_central = data.find(CENTRAL)
    assert first_descriptor + 24 == second_local < first_central
    # After reversal, the first central record describes the second member.
    assert struct.unpack_from("<I", data, first_central + 42)[0] == second_local

    data[second_local:second_local] = padding
    struct.pack_into(
        "<I", data, first_central + len(padding) + 42,
        second_local + len(padding),
    )
    eocd = data.rfind(EOCD)
    struct.pack_into("<I", data, eocd + 16, first_central + len(padding))
    original = bytes(data)
    path = tmp_path / "zip64-reordered-descriptor-gap.xlsx"
    path.write_bytes(original)

    # The standard ZIP reader tolerates this unaccounted inter-member gap.
    with zipfile.ZipFile(io.BytesIO(original)) as archive:
        assert archive.namelist() == [SECOND_NAME, FIRST_NAME]
        assert archive.read(FIRST_NAME) == FIRST_CONTENT
        assert archive.read(SECOND_NAME) == SECOND_CONTENT

    def fail_if_classified(*args: object, **kwargs: object) -> None:
        raise AssertionError("Unaccounted ZIP64 descriptor gap reached ZipFile")

    with monkeypatch.context() as patch:
        patch.setattr(identifier.zipfile, "ZipFile", fail_if_classified)
        assert identifier.inspect_zip_container(path) == (
            "Ambiguous ZIP data descriptor metadata"
        )
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "location,payload,length_delta,expected",
    [
        ("after-last", b"", 0, "OOXML Excel"),
        ("after-last", b"notes", 0, "OOXML Excel"),
        ("after-last", b"notes", -1, "Ambiguous ZIP data descriptor metadata"),
        ("after-last", b"notes", 1, "Ambiguous ZIP data descriptor metadata"),
        ("between-members", b"notes", 0, "Ambiguous ZIP data descriptor metadata"),
    ],
    ids=[
        "final-empty-record",
        "final-payload-record",
        "final-underreported-length",
        "final-overreported-length",
        "complete-record-between-members",
    ],
)
def test_zip64_reordered_streaming_archive_extra_record_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    location: str,
    payload: bytes,
    length_delta: int,
    expected: str,
) -> None:
    """Accept a complete final archive extra record, reject misplaced or malformed ones."""
    from labvault_scout import identifier

    data = bytearray(make_streaming_zip64_member_association("valid"))
    first_central = data.find(CENTRAL)
    first_descriptor = data.find(DESCRIPTOR)
    second_descriptor = data.rfind(DESCRIPTOR, 0, first_central)
    second_local = data.find(LOCAL, 4)
    assert first_descriptor + 24 == second_local
    assert second_descriptor + 16 == first_central

    record = b"PK\\x06\\x08" + struct.pack("<I", len(payload) + length_delta) + payload
    insert_at = first_central if location == "after-last" else second_local
    data[insert_at:insert_at] = record

    if location == "between-members":
        # Central records are reversed: the first record describes the second local member.
        struct.pack_into(
            "<I", data, first_central + len(record) + 42,
            second_local + len(record),
        )
    end = data.rfind(EOCD)
    struct.pack_into("<I", data, end + 16, first_central + len(record))

    original = bytes(data)
    path = tmp_path / "zip64-reordered-archive-extra.xlsx"
    path.write_bytes(original)

    # Standard zipfile accepts these synthetic archives, including malformed variants.
    with zipfile.ZipFile(io.BytesIO(original)) as archive:
        assert archive.namelist() == [SECOND_NAME, FIRST_NAME]
        assert archive.read(FIRST_NAME) == FIRST_CONTENT
        assert archive.read(SECOND_NAME) == SECOND_CONTENT

    if expected == "OOXML Excel":
        assert identifier.inspect_zip_container(path) == expected
    else:
        def fail_if_classified(*args: object, **kwargs: object) -> None:
            raise AssertionError("Ambiguous archive extra record reached ZIP classification")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", fail_if_classified)
            assert identifier.inspect_zip_container(path) == expected

    assert path.read_bytes() == original
