"""ZIP64 central member extra-field ordering and duplication regressions.

Synthetic ZIP members only. The scanner must never alter or extract inputs.
"""
from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

import pytest


CENTRAL = b"PK\x01\x02"
EOCD = b"PK\x05\x06"
ZIP64 = struct.pack("<HHQ", 0x0001, 8, 0)
OTHER = struct.pack("<HH", 0xCAFE, 3) + b"abc"


def make_zip64_central_extra(variant: str) -> bytes:
    """Add ZIP64 offset metadata with optional adjacent unrelated fields."""
    extras = {
        "other-before": OTHER + ZIP64,
        "other-after": ZIP64 + OTHER,
        "duplicate-separated": ZIP64 + OTHER + ZIP64,
        "duplicate-adjacent": ZIP64 + ZIP64 + OTHER,
    }
    if variant not in extras:
        raise ValueError(variant)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("xl/workbook.xml", b"<workbook/>")
    data = bytearray(output.getvalue())
    central = data.find(CENTRAL)
    end = data.rfind(EOCD)
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
    assert data[end:end + 4] == EOCD
    size = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, size + len(extra))
    return bytes(data)


@pytest.mark.parametrize(
    "variant,expected",
    [
        ("other-before", "OOXML Excel"),
        ("other-after", "OOXML Excel"),
        ("duplicate-separated", "Invalid ZIP directory ZIP64 extra"),
        ("duplicate-adjacent", "Invalid ZIP directory ZIP64 extra"),
    ],
)
def test_zip64_central_sentinel_duplicate_and_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str, expected: str,
) -> None:
    from labvault_scout import identifier

    data = make_zip64_central_extra(variant)
    path = tmp_path / f"zip64-extra-{variant}.xlsx"
    path.write_bytes(data)
    with zipfile.ZipFile(path) as archive:
        assert archive.namelist() == ["[Content_Types].xml", "xl/workbook.xml"]
        assert archive.infolist()[0].header_offset == 0
        if expected == "OOXML Excel":
            assert archive.read("[Content_Types].xml") == b"<Types/>"

    if expected != "OOXML Excel":
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Duplicate ZIP64 extra reached ZipFile")
        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == expected
    else:
        assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == data


def _self_check() -> None:
    for variant in ("other-before", "other-after", "duplicate-separated", "duplicate-adjacent"):
        data = make_zip64_central_extra(variant)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert archive.namelist() == ["[Content_Types].xml", "xl/workbook.xml"]
            assert archive.infolist()[0].header_offset == 0
            if not variant.startswith("duplicate"):
                assert archive.read("[Content_Types].xml") == b"<Types/>"
        print(f"{variant}: central directory readable, {len(data)} bytes")


if __name__ == "__main__":
    _self_check()
