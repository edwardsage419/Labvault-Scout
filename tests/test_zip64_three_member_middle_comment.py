"""Three-member ZIP64 central-directory comment boundary regression.

Fixtures are synthetic and small. Scanner access must preserve input bytes.
"""
from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

import pytest

CENTRAL = b"PK\x01\x02"
EOCD = b"PK\x05\x06"
NAMES = ("[Content_Types].xml", "xl/workbook.xml", "xl/styles.xml")
CONTENTS = (b"<Types/>", b"<workbook/>", b"<styles/>")
ORDINARY = struct.pack("<HH", 0xCAFE, 4) + b"\x01\x00\x08\x00"
COMMENT = b"opaque:PK\x01\x02:PK\x05\x06:end"


def make_three_member_zip64_middle_comment(delta: int) -> bytes:
    """Vary only the middle central member's declared comment length."""
    if delta not in (-1, 0, 1):
        raise ValueError(delta)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in zip(NAMES, CONTENTS):
            archive.writestr(name, content)
    data = bytearray(stream.getvalue())
    first = data.find(CENTRAL)
    middle = data.find(CENTRAL, first + 4)
    last = data.find(CENTRAL, middle + 4)
    end = data.rfind(EOCD)
    assert 0 < first < middle < last < end
    name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, middle + 28)
    assert extra_len == comment_len == 0
    assert middle + 46 + name_len == last
    assert data[middle + 46:middle + 46 + name_len] == NAMES[1].encode()

    local_offset = struct.unpack_from("<I", data, middle + 42)[0]
    assert 0 < local_offset < 0xFFFFFFFF
    assert data[local_offset:local_offset + 4] == b"PK\x03\x04"
    zip64 = struct.pack("<HHQ", 0x0001, 8, local_offset)
    extras = ORDINARY + zip64
    insertion = middle + 46 + name_len
    data[insertion:insertion] = extras + COMMENT
    struct.pack_into("<I", data, middle + 42, 0xFFFFFFFF)
    struct.pack_into("<H", data, middle + 30, len(extras))
    struct.pack_into("<H", data, middle + 32, len(COMMENT) + delta)

    end += len(extras) + len(COMMENT)
    assert data[end:end + 4] == EOCD
    directory_size = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, directory_size + len(extras) + len(COMMENT))
    actual_next = insertion + len(extras) + len(COMMENT)
    declared_next = insertion + len(extras) + len(COMMENT) + delta
    assert data[actual_next:actual_next + 4] == CENTRAL
    assert (data[declared_next:declared_next + 4] == CENTRAL) == (delta == 0)
    return bytes(data)


@pytest.mark.parametrize("delta", [-1, 0, 1], ids=["underreported", "valid", "overreported"])
def test_zip64_three_member_middle_comment_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, delta: int,
) -> None:
    from labvault_scout import identifier

    payload = make_three_member_zip64_middle_comment(delta)
    path = tmp_path / f"three-member-middle-comment-{delta}.xlsx"
    path.write_bytes(payload)
    if delta == 0:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert archive.namelist() == list(NAMES)
            assert archive.infolist()[1].comment == COMMENT
            assert archive.infolist()[1].extra == ORDINARY + struct.pack(
                "<HHQ", 0x0001, 8, archive.infolist()[1].header_offset
            )
            for name, expected in zip(NAMES, CONTENTS):
                assert archive.read(name) == expected
        assert identifier.inspect_zip_container(path) == "OOXML Excel"
    else:
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Misaligned middle ZIP64 record reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == "Invalid ZIP directory record length"
    assert path.read_bytes() == payload


if __name__ == "__main__":
    for change in (-1, 0, 1):
        blob = make_three_member_zip64_middle_comment(change)
        if change == 0:
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                assert archive.namelist() == list(NAMES)
                assert archive.infolist()[1].comment == COMMENT
                for name, expected in zip(NAMES, CONTENTS):
                    assert archive.read(name) == expected
        print(f"delta={change}, bytes={len(blob)}")
