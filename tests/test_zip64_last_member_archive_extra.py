"""ZIP64 final streaming descriptor followed by an archive extra data record.

All fixtures are synthetic; the scanner must not modify source archives.
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


def make_last_zip64_descriptor_with_archive_extra(
    payload: bytes, length_delta: int = 0,
) -> bytes:
    """Reorder central records; give the final local member a 64-bit descriptor."""
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
    assert second_descriptor < first_central < second_central < eocd
    assert first_descriptor + 16 == second_local
    assert second_descriptor + 24 == first_central
    assert struct.unpack_from("<I", data, second_central + 42)[0] == second_local

    # The second central member carries a ZIP64 local offset. The central
    # directory will be reordered without changing physical member positions.
    name_length, extra_length, comment_length = struct.unpack_from(
        "<HHH", data, second_central + 28
    )
    assert extra_length == 0 and comment_length == 0
    extra = struct.pack("<HHQ", 1, 8, second_local)
    insertion = second_central + 46 + name_length
    data[insertion:insertion] = extra
    struct.pack_into("<H", data, second_central + 30, len(extra))
    struct.pack_into("<I", data, second_central + 42, 0xFFFFFFFF)
    eocd += len(extra)
    struct.pack_into("<I", data, eocd + 12, eocd - first_central)
    data[first_central:eocd] = (
        data[second_central:eocd] + data[first_central:second_central]
    )

    # A complete archive extra data record may follow the final descriptor.
    record = ARCHIVE_EXTRA + struct.pack("<I", len(payload) + length_delta) + payload
    data[first_central:first_central] = record
    eocd = data.rfind(EOCD)
    struct.pack_into("<I", data, eocd + 16, first_central + len(record))
    return bytes(data)


@pytest.mark.parametrize(
    "payload,length_delta,expected",
    [
        (b"notes", 0, "OOXML Excel"),
        (b"notes", -1, "Ambiguous ZIP data descriptor metadata"),
        (b"notes", 1, "Ambiguous ZIP data descriptor metadata"),
    ],
    ids=["valid-final-extra", "underreported-length", "overreported-length"],
)
def test_reordered_last_zip64_descriptor_archive_extra_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
    length_delta: int,
    expected: str,
) -> None:
    from labvault_scout import identifier

    original = make_last_zip64_descriptor_with_archive_extra(payload, length_delta)
    path = tmp_path / "zip64-last-descriptor-archive-extra.xlsx"
    path.write_bytes(original)
    with zipfile.ZipFile(io.BytesIO(original)) as archive:
        assert archive.namelist() == [SECOND_NAME, FIRST_NAME]
        assert archive.read(FIRST_NAME) == FIRST_CONTENT
        assert archive.read(SECOND_NAME) == SECOND_CONTENT
        assert archive.getinfo(SECOND_NAME).header_offset > 0

    if expected == "OOXML Excel":
        assert identifier.inspect_zip_container(path) == expected
    else:
        def fail_if_classified(*args: object, **kwargs: object) -> None:
            raise AssertionError("Malformed ZIP64 final record reached ZipFile")
        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", fail_if_classified)
            assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == original
