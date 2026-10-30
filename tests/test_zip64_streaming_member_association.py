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
