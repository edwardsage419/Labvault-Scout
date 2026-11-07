"""Candidate regression: unsigned final ZIP64 descriptor and archive extra record.

Synthetic archives only. The scanner must leave its input bytes unchanged.
This candidate must be reviewed against the current repository before merging.
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
ARCHIVE_EXTRA = b"PK\x06\x08"
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


def make_unsigned_final_zip64_descriptor_archive_extra(
    payload: bytes, length_delta: int = 0,
) -> bytes:
    """Build a reordered two-member ZIP with an unsigned 64-bit final descriptor."""
    writer = NonSeekableWriter()
    with zipfile.ZipFile(writer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(FIRST_NAME, FIRST_CONTENT)
        with archive.open(SECOND_NAME, "w", force_zip64=True) as member:
            member.write(SECOND_CONTENT)

    data = bytearray(writer.buffer.getvalue())
    first_local = data.find(LOCAL)
    second_local = data.find(LOCAL, first_local + 4)
    first_descriptor = data.find(DESCRIPTOR)
    second_descriptor = data.find(DESCRIPTOR, first_descriptor + 4)
    first_central = data.find(CENTRAL)
    second_central = data.find(CENTRAL, first_central + 4)
    eocd = data.rfind(EOCD)
    assert first_local == 0 < first_descriptor < second_local < second_descriptor
    assert second_descriptor + 24 == first_central < second_central < eocd

    # Central record for the final physical member uses a ZIP64 local offset.
    name_length, extra_length, comment_length = struct.unpack_from(
        "<HHH", data, second_central + 28
    )
    assert extra_length == 0 and comment_length == 0
    assert struct.unpack_from("<I", data, second_central + 42)[0] == second_local
    zip64_extra = struct.pack("<HHQ", 1, 8, second_local)
    insertion = second_central + 46 + name_length
    data[insertion:insertion] = zip64_extra
    struct.pack_into("<H", data, second_central + 30, len(zip64_extra))
    struct.pack_into("<I", data, second_central + 42, 0xFFFFFFFF)
    eocd += len(zip64_extra)
    struct.pack_into("<I", data, eocd + 12, eocd - first_central)

    # Reverse central records without changing local member order.
    data[first_central:eocd] = (
        data[second_central:eocd]
        + data[first_central:second_central]
    )

    # Remove only the final descriptor's optional four-byte signature.
    assert data[second_descriptor:second_descriptor + 4] == DESCRIPTOR
    del data[second_descriptor:second_descriptor + 4]
    first_central -= 4
    assert first_central == second_descriptor + 20

    # A complete archive extra data record follows the unsigned descriptor.
    record = ARCHIVE_EXTRA + struct.pack("<I", len(payload) + length_delta) + payload
    data[first_central:first_central] = record
    eocd = data.rfind(EOCD)
    struct.pack_into("<I", data, eocd + 16, first_central + len(record))
    assert data[second_descriptor:second_descriptor + 4] != DESCRIPTOR
    return bytes(data)


@pytest.mark.parametrize(
    "payload,length_delta,expected",
    [
        (b"notes", 0, "OOXML Excel"),
        (b"notes", -1, "Ambiguous ZIP data descriptor metadata"),
        (b"notes", 1, "Ambiguous ZIP data descriptor metadata"),
    ],
    ids=["valid-unsigned-final", "unsigned-underreported", "unsigned-overreported"],
)
def test_unsigned_final_zip64_descriptor_archive_extra(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
    length_delta: int,
    expected: str,
) -> None:
    from labvault_scout import identifier

    original = make_unsigned_final_zip64_descriptor_archive_extra(payload, length_delta)
    path = tmp_path / "unsigned-final-zip64-extra.xlsx"
    path.write_bytes(original)
    with zipfile.ZipFile(io.BytesIO(original)) as archive:
        assert archive.namelist() == [SECOND_NAME, FIRST_NAME]
        assert archive.read(FIRST_NAME) == FIRST_CONTENT
        assert archive.read(SECOND_NAME) == SECOND_CONTENT
        info = archive.getinfo(SECOND_NAME)
        local_name_length, local_extra_length = struct.unpack_from(
            "<HH", original, info.header_offset + 26
        )
        descriptor_at = (
            info.header_offset + 30 + local_name_length
            + local_extra_length + info.compress_size
        )
        # Prove this is a 20-byte unsigned ZIP64 descriptor, immediately
        # followed by an archive extra data record with the intended length.
        assert struct.unpack_from("<IQQ", original, descriptor_at) == (
            info.CRC, info.compress_size, info.file_size
        )
        record_at = descriptor_at + 20
        assert original[record_at:record_at + 4] == ARCHIVE_EXTRA
        assert struct.unpack_from("<I", original, record_at + 4)[0] == (
            len(payload) + length_delta
        )

    if expected == "OOXML Excel":
        assert identifier.inspect_zip_container(path) == expected
    else:
        def fail_if_classified(*args: object, **kwargs: object) -> None:
            raise AssertionError("Malformed unsigned descriptor reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", fail_if_classified)
            assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == original
