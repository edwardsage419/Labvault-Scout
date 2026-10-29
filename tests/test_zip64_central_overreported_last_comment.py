"""Candidate regression for an overreported final ZIP64 central member comment.

The fixtures are small synthetic OOXML-shaped ZIP files.  The scanner must
reject a record that extends past the declared central-directory boundary,
without invoking zipfile.ZipFile or modifying the source file.
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


def make_zip64_overreported_comment(overreport: int) -> bytes:
    """Build a valid ZIP64 offset extra with a controlled final comment length."""
    assert 0 <= overreport <= 20
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

    # Require a genuine central member ZIP64 local-header-offset sentinel.
    struct.pack_into("<I", data, first + 42, 0xFFFFFFFF)
    data[first + 46 + first_name:first + 46 + first_name] = ZIP64_OFFSET
    struct.pack_into("<H", data, first + 30, len(ZIP64_OFFSET))
    last += len(ZIP64_OFFSET)
    end += len(ZIP64_OFFSET)

    last_name = struct.unpack_from("<H", data, last + 28)[0]
    last_extra = struct.unpack_from("<H", data, last + 30)[0]
    insertion = last + 46 + last_name + last_extra
    data[insertion:insertion] = COMMENT
    struct.pack_into("<H", data, last + 32, len(COMMENT) + overreport)
    end += len(COMMENT)
    assert data[end:end + 4] == EOCD
    directory_size = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, directory_size + len(ZIP64_OFFSET) + len(COMMENT))
    return bytes(data)


def test_zip64_last_comment_exact_length_accepted(tmp_path: Path) -> None:
    from labvault_scout import identifier

    payload = make_zip64_overreported_comment(0)
    path = tmp_path / "exact-comment.xlsx"
    path.write_bytes(payload)
    assert identifier.inspect_zip_container(path) == "OOXML Excel"
    assert path.read_bytes() == payload


@pytest.mark.parametrize("overreport", [1, 20])
def test_zip64_last_comment_overreport_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, overreport: int,
) -> None:
    from labvault_scout import identifier

    payload = make_zip64_overreported_comment(overreport)
    path = tmp_path / f"overreported-{overreport}.xlsx"
    path.write_bytes(payload)

    def reject_late_parse(*args: object, **kwargs: object) -> None:
        raise AssertionError("Overreported central member reached ZipFile")

    with monkeypatch.context() as patch:
        patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
        assert identifier.inspect_zip_container(path) == "Invalid ZIP directory record length"
    assert path.read_bytes() == payload


if __name__ == "__main__":
    for overreport in (0, 1, 20):
        payload = make_zip64_overreported_comment(overreport)
        eocd = payload.rfind(EOCD)
        directory_size = struct.unpack_from("<I", payload, eocd + 12)[0]
        cursor = eocd - directory_size
        for _ in range(2):
            assert payload[cursor:cursor + 4] == CENTRAL
            name, extra, comment = struct.unpack_from("<HHH", payload, cursor + 28)
            cursor += 46 + name + extra + comment
        assert cursor - eocd == overreport
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert archive.namelist() == ["[Content_Types].xml", "xl/workbook.xml"]
            assert archive.read("[Content_Types].xml") == b"<Types/>"
        print(f"overreport={overreport}, central_boundary_overrun={cursor - eocd}, "
              f"stdlib_accepts=True, bytes={len(payload)}")
