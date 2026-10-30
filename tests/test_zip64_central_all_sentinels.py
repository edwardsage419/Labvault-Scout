"""Regression tests for ZIP64 central members using all four sentinel fields.

Synthetic archives only. Scanned files remain unchanged and no archive
contents are extracted or executed.
"""
from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

import pytest

CONTENT = b"<Types/>" * 20
CENTRAL = b"PK\x01\x02"
EOCD = b"PK\x05\x06"


def make_zip64_all_sentinels(variant: str) -> bytes:
    """Set four central sentinels and construct ZIP64 extra fields in order."""
    if variant not in {"valid", "short-disk", "extra-trailer", "multidisk"}:
        raise ValueError(variant)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT)
        archive.writestr("xl/workbook.xml", b"<workbook/>")
    data = bytearray(out.getvalue())
    central = data.find(CENTRAL)
    eocd = data.rfind(EOCD)
    assert 0 < central < eocd
    name_length, old_extra = struct.unpack_from("<HH", data, central + 28)
    assert old_extra == 0
    compressed, uncompressed = struct.unpack_from("<II", data, central + 20)
    local_offset = struct.unpack_from("<I", data, central + 42)[0]
    assert local_offset == 0
    struct.pack_into("<II", data, central + 20, 0xFFFFFFFF, 0xFFFFFFFF)
    struct.pack_into("<I", data, central + 42, 0xFFFFFFFF)
    struct.pack_into("<H", data, central + 34, 0xFFFF)
    payload = struct.pack("<QQQ", uncompressed, compressed, local_offset)
    if variant != "short-disk":
        payload += struct.pack("<I", 1 if variant == "multidisk" else 0)
    if variant == "extra-trailer":
        payload += b"ABCD"
    extra = struct.pack("<HH", 0x0001, len(payload)) + payload
    insertion = central + 46 + name_length
    data[insertion:insertion] = extra
    struct.pack_into("<H", data, central + 30, len(extra))
    eocd += len(extra)
    assert data[eocd:eocd + 4] == EOCD
    old_directory_size = struct.unpack_from("<I", data, eocd + 12)[0]
    struct.pack_into("<I", data, eocd + 12, old_directory_size + len(extra))
    return bytes(data)


def inspect_sentinel_layout(data: bytes) -> tuple[int, int]:
    """Check the central ZIP64 payload layout at the byte level."""
    central = data.find(CENTRAL)
    eocd = data.rfind(EOCD)
    assert central > 0 and eocd > central
    assert struct.unpack_from("<II", data, central + 20) == (0xFFFFFFFF, 0xFFFFFFFF)
    assert struct.unpack_from("<H", data, central + 34)[0] == 0xFFFF
    assert struct.unpack_from("<I", data, central + 42)[0] == 0xFFFFFFFF
    name_length, extra_length = struct.unpack_from("<HH", data, central + 28)
    pos = central + 46 + name_length
    tag, length = struct.unpack_from("<HH", data, pos)
    assert tag == 0x0001 and length + 4 == extra_length
    assert eocd == central + struct.unpack_from("<I", data, eocd + 12)[0]
    disk = struct.unpack_from("<I", data, pos + 4 + 24)[0] if length >= 28 else -1
    return length, disk


@pytest.mark.parametrize("variant,expected", [
    ("valid", "OOXML Excel"),
    ("short-disk", "Invalid ZIP directory ZIP64 extra"),
    ("extra-trailer", "Invalid ZIP directory ZIP64 extra"),
    ("multidisk", "Unsupported ZIP multi-disk metadata"),
])
def test_zip64_central_all_sentinels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str, expected: str
) -> None:
    from labvault_scout import identifier

    data = make_zip64_all_sentinels(variant)
    path = tmp_path / f"all-sentinels-{variant}.xlsx"
    path.write_bytes(data)
    assert inspect_sentinel_layout(data)[0] == {
        "valid": 28, "short-disk": 24, "extra-trailer": 32, "multidisk": 28
    }[variant]
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.namelist() == ["[Content_Types].xml", "xl/workbook.xml"]
        assert archive.read("[Content_Types].xml") == CONTENT

    if variant != "valid":
        def fail_if_classified(*args: object, **kwargs: object) -> None:
            raise AssertionError("Malformed ZIP64 central metadata reached ZipFile")
        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", fail_if_classified)
            assert identifier.inspect_zip_container(path) == expected
    else:
        assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == data
