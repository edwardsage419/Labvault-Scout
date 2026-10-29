"""ZIP64 central-directory 64-bit local-offset compatibility regressions.

The fixtures are small, synthetic archives. No archive extraction is performed.
"""
from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

import pytest

from labvault_scout import identifier


LOCAL_HEADER = b"PK\x03\x04"
CENTRAL_HEADER = b"PK\x01\x02"
EOCD = b"PK\x05\x06"


def make_zip64_central_offset(offset: int) -> bytes:
    """Replace the first central 32-bit local offset with ZIP64 metadata."""
    if offset not in (0, 1, 0x100000000):
        raise ValueError("Unsupported fixture variant")

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("xl/workbook.xml", b"<workbook/>")

    data = bytearray(output.getvalue())
    first_central = data.find(CENTRAL_HEADER)
    end = data.rfind(EOCD)
    assert 0 < first_central < end
    assert data.startswith(LOCAL_HEADER)
    name_size, extra_size = struct.unpack_from("<HH", data, first_central + 28)
    assert extra_size == 0
    assert struct.unpack_from("<I", data, first_central + 42)[0] == 0

    struct.pack_into("<I", data, first_central + 42, 0xFFFFFFFF)
    extra = struct.pack("<HHQ", 0x0001, 8, offset)
    insertion = first_central + 46 + name_size
    data[insertion:insertion] = extra
    struct.pack_into("<H", data, first_central + 30, len(extra))
    end += len(extra)
    old_directory_size = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, old_directory_size + len(extra))
    assert data[end:end + 4] == EOCD
    return bytes(data)


@pytest.mark.parametrize(
    "offset,expected",
    [
        (0, "OOXML Excel"),
        (1, "Invalid ZIP local file header"),
        (0x100000000, "Invalid ZIP local header offset"),
    ],
    ids=["valid-zero-offset", "forged-one-byte-offset", "out-of-range-64bit-offset"],
)
def test_zip64_central_local_offset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offset: int, expected: str,
) -> None:
    """Accept a real local header; reject forged offsets before classification."""
    data = make_zip64_central_offset(offset)
    path = tmp_path / f"zip64-offset-{offset}.xlsx"
    path.write_bytes(data)
    with zipfile.ZipFile(path) as archive:
        assert archive.namelist() == ["[Content_Types].xml", "xl/workbook.xml"]
        assert archive.infolist()[0].header_offset == offset
        if offset == 0:
            assert archive.read("[Content_Types].xml") == b"<Types/>"

    if offset:
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Invalid ZIP64 local offset reached ZipFile")

        monkeypatch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
    assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == data
