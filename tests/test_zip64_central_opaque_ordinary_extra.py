"""Keep ordinary central extras opaque beside required ZIP64 offset metadata.

Synthetic ZIP inputs only. Classification must be read-only.
"""
from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

import pytest


ZIP64_OFFSET = struct.pack("<HHQ", 0x0001, 8, 0)
# The inner bytes resemble a complete ZIP64 field with a conflicting offset.
NESTED_ZIP64 = struct.pack("<HHQ", 0x0001, 8, 0xFFFFFFFFFFFFFFFF)
OPAQUE_EXTRA = struct.pack("<HH", 0xCAFE, len(NESTED_ZIP64)) + NESTED_ZIP64
EMPTY_EXTRA = struct.pack("<HH", 0xCAFE, 0)


def make_zip64_with_ordinary_extra(variant: str) -> bytes:
    extras = {
        "nested-before": OPAQUE_EXTRA + ZIP64_OFFSET,
        "nested-after": ZIP64_OFFSET + OPAQUE_EXTRA,
        "empty-before": EMPTY_EXTRA + ZIP64_OFFSET,
        "empty-after": ZIP64_OFFSET + EMPTY_EXTRA,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("xl/workbook.xml", b"<workbook/>")
    data = bytearray(output.getvalue())
    central = data.find(b"PK\x01\x02")
    end = data.rfind(b"PK\x05\x06")
    assert 0 < central < end
    name_size, old_extra = struct.unpack_from("<HH", data, central + 28)
    assert old_extra == 0
    assert struct.unpack_from("<I", data, central + 42)[0] == 0
    struct.pack_into("<I", data, central + 42, 0xFFFFFFFF)
    extra = extras[variant]
    insertion = central + 46 + name_size
    data[insertion:insertion] = extra
    struct.pack_into("<H", data, central + 30, len(extra))
    end += len(extra)
    assert data[end:end + 4] == b"PK\x05\x06"
    directory_size = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, directory_size + len(extra))
    return bytes(data)


@pytest.mark.parametrize("variant", ["nested-before", "nested-after", "empty-before", "empty-after"])
def test_zip64_central_ordinary_extra_payload_is_opaque(tmp_path: Path, variant: str) -> None:
    from labvault_scout import identifier

    data = make_zip64_with_ordinary_extra(variant)
    path = tmp_path / f"opaque-extra-{variant}.xlsx"
    path.write_bytes(data)
    with zipfile.ZipFile(path) as archive:
        assert archive.namelist() == ["[Content_Types].xml", "xl/workbook.xml"]
        assert archive.infolist()[0].header_offset == 0
        assert archive.read("[Content_Types].xml") == b"<Types/>"
    assert identifier.inspect_zip_container(path) == "OOXML Excel"
    assert path.read_bytes() == data


if __name__ == "__main__":
    for case in ("nested-before", "nested-after", "empty-before", "empty-after"):
        blob = make_zip64_with_ordinary_extra(case)
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            assert archive.infolist()[0].header_offset == 0
            assert archive.read("[Content_Types].xml") == b"<Types/>"
        print(case, len(blob))
