"""Candidate regression: ZIP64 central member comments are opaque data.

Synthetic, small ZIP fixtures only. No extraction, source modification, or
execution of archived code. Intended for tests/ after CI state is verified.
"""
from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

import pytest

CENTRAL = b"PK\x01\x02"
EOCD = b"PK\x05\x06"
CONTENT = b"<Types/>"
ZIP64_OFFSET = struct.pack("<HHQ", 0x0001, 8, 0)

COMMENTS = {
    "nested-zip64": struct.pack("<HHQ", 0x0001, 8, 0xFFFFFFFFFFFFFFFF),
    "fake-central": CENTRAL + b"\xff" * 46,
    "fake-eocd": EOCD + b"\x00" * 18,
}


def make_zip64_member_comment(variant: str) -> bytes:
    """Add a central ZIP64 offset and a member comment with deceptive bytes."""
    if variant not in COMMENTS:
        raise ValueError(variant)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT)
        archive.writestr("xl/workbook.xml", b"<workbook/>")

    data = bytearray(stream.getvalue())
    central = data.find(CENTRAL)
    eocd = data.rfind(EOCD)
    assert 0 < central < eocd
    name_size, extra_size, comment_size = struct.unpack_from("<HHH", data, central + 28)
    assert extra_size == comment_size == 0
    assert struct.unpack_from("<I", data, central + 42)[0] == 0

    struct.pack_into("<I", data, central + 42, 0xFFFFFFFF)
    comment = COMMENTS[variant]
    insertion = central + 46 + name_size
    data[insertion:insertion] = ZIP64_OFFSET + comment
    struct.pack_into("<H", data, central + 30, len(ZIP64_OFFSET))
    struct.pack_into("<H", data, central + 32, len(comment))
    eocd += len(ZIP64_OFFSET) + len(comment)
    assert data[eocd:eocd + 4] == EOCD
    directory_size = struct.unpack_from("<I", data, eocd + 12)[0]
    struct.pack_into("<I", data, eocd + 12, directory_size + len(ZIP64_OFFSET) + len(comment))
    return bytes(data)


@pytest.mark.parametrize("variant", sorted(COMMENTS))
def test_zip64_central_member_comment_is_opaque(tmp_path: Path, variant: str) -> None:
    from labvault_scout import identifier

    data = make_zip64_member_comment(variant)
    path = tmp_path / f"zip64-comment-{variant}.xlsx"
    path.write_bytes(data)
    with zipfile.ZipFile(path) as archive:
        assert archive.namelist() == ["[Content_Types].xml", "xl/workbook.xml"]
        assert archive.infolist()[0].header_offset == 0
        assert archive.infolist()[0].comment == COMMENTS[variant]
        assert archive.read("[Content_Types].xml") == CONTENT
    assert identifier.inspect_zip_container(path) == "OOXML Excel"
    assert path.read_bytes() == data


if __name__ == "__main__":
    for variant in sorted(COMMENTS):
        payload = make_zip64_member_comment(variant)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert archive.infolist()[0].comment == COMMENTS[variant]
            assert archive.read("[Content_Types].xml") == CONTENT
        print(variant, len(payload))
