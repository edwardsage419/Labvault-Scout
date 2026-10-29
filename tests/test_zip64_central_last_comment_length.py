"""ZIP64 final central member comment length regression.

Only small synthetic ZIP fixtures are created. The scanner must leave input
bytes unchanged and reject malformed metadata before zipfile classification.
"""
from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

import pytest

CENTRAL = b"PK\x01\x02"
EOCD = b"PK\x05\x06"
ZIP64_OFFSET = struct.pack("<HHQ", 0x0001, 8, 0)
COMMENT = b"NOTE"


def make_zip64_last_comment(*, underreport: bool) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("xl/workbook.xml", b"<workbook/>")
    data = bytearray(output.getvalue())
    first = data.find(CENTRAL)
    last = data.find(CENTRAL, first + 4)
    end = data.rfind(EOCD)
    assert 0 < first < last < end
    assert struct.unpack_from("<I", data, first + 42)[0] == 0
    first_name = struct.unpack_from("<H", data, first + 28)[0]
    assert struct.unpack_from("<H", data, first + 30)[0] == 0
    assert struct.unpack_from("<H", data, last + 32)[0] == 0

    # Require a real ZIP64 central member offset in both fixtures.
    struct.pack_into("<I", data, first + 42, 0xFFFFFFFF)
    data[first + 46 + first_name:first + 46 + first_name] = ZIP64_OFFSET
    struct.pack_into("<H", data, first + 30, len(ZIP64_OFFSET))
    last += len(ZIP64_OFFSET)
    end += len(ZIP64_OFFSET)

    last_name = struct.unpack_from("<H", data, last + 28)[0]
    last_extra = struct.unpack_from("<H", data, last + 30)[0]
    insertion = last + 46 + last_name + last_extra
    data[insertion:insertion] = COMMENT
    struct.pack_into("<H", data, last + 32, len(COMMENT) - int(underreport))
    end += len(COMMENT)
    assert data[end:end + 4] == EOCD
    directory_size = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, directory_size + len(ZIP64_OFFSET) + len(COMMENT))
    return bytes(data)


def test_zip64_valid_last_comment_accepted(tmp_path: Path) -> None:
    from labvault_scout import identifier

    payload = make_zip64_last_comment(underreport=False)
    path = tmp_path / "valid-zip64-last-comment.xlsx"
    path.write_bytes(payload)
    assert identifier.inspect_zip_container(path) == "OOXML Excel"
    assert path.read_bytes() == payload


def test_zip64_underreported_last_comment_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from labvault_scout import identifier

    payload = make_zip64_last_comment(underreport=True)
    path = tmp_path / "short-zip64-last-comment.xlsx"
    path.write_bytes(payload)

    def reject_late_parse(*args: object, **kwargs: object) -> None:
        raise AssertionError("Malformed ZIP64 central record reached ZipFile")

    with monkeypatch.context() as patch:
        patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
        assert identifier.inspect_zip_container(path) == "Invalid ZIP directory record length"
    assert path.read_bytes() == payload
