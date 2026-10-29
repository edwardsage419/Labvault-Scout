"""ZIP64 central extra compatibility regression for LabVault Scout.

All fixtures are synthetic and small. No archive contents are executed or
extracted. Scanning must leave each source file unchanged.
"""
from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

import pytest

CENTRAL = b"PK\x01\x02"
EOCD = b"PK\x05\x06"
OTHER = struct.pack("<HH", 0xCAFE, 3) + b"abc"
EMPTY_ZIP64 = struct.pack("<HH", 0x0001, 0)
REDUNDANT_ZIP64 = struct.pack("<HHQ", 0x0001, 8, 0)


def make_optional_zip64_extra(variant: str) -> bytes:
    """Add central extras without introducing any 32-bit ZIP64 sentinels."""
    extras = {
        "empty": EMPTY_ZIP64,
        "empty-before-ordinary": EMPTY_ZIP64 + OTHER,
        "empty-after-ordinary": OTHER + EMPTY_ZIP64,
        "nonempty-without-sentinel": REDUNDANT_ZIP64,
    }
    if variant not in extras:
        raise ValueError(variant)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("xl/workbook.xml", b"<workbook/>")
    data = bytearray(buffer.getvalue())
    central = data.find(CENTRAL)
    end = data.rfind(EOCD)
    assert 0 < central < end
    name_length, extra_length = struct.unpack_from("<HH", data, central + 28)
    assert extra_length == 0
    assert struct.unpack_from("<I", data, central + 42)[0] == 0
    assert struct.unpack_from("<II", data, central + 20) != (0xFFFFFFFF, 0xFFFFFFFF)
    extra = extras[variant]
    data[central + 46 + name_length:central + 46 + name_length] = extra
    struct.pack_into("<H", data, central + 30, len(extra))
    end += len(extra)
    assert data[end:end + 4] == EOCD
    directory_length = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, directory_length + len(extra))
    return bytes(data)


@pytest.mark.parametrize(
    "variant,expected",
    [
        ("empty", "OOXML Excel"),
        ("empty-before-ordinary", "OOXML Excel"),
        ("empty-after-ordinary", "OOXML Excel"),
        ("nonempty-without-sentinel", "Invalid ZIP directory ZIP64 extra"),
    ],
)
def test_optional_central_zip64_extra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str, expected: str,
) -> None:
    from labvault_scout import identifier

    data = make_optional_zip64_extra(variant)
    path = tmp_path / (variant + ".xlsx")
    path.write_bytes(data)
    if expected.startswith("Invalid"):
        def unexpected_zipfile(*args: object, **kwargs: object) -> None:
            raise AssertionError("Invalid central ZIP64 extra reached ZipFile")
        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", unexpected_zipfile)
            assert identifier.inspect_zip_container(path) == expected
    else:
        assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == data


if __name__ == "__main__":
    for variant in (
        "empty", "empty-before-ordinary", "empty-after-ordinary",
        "nonempty-without-sentinel",
    ):
        data = make_optional_zip64_extra(variant)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert archive.namelist() == ["[Content_Types].xml", "xl/workbook.xml"]
            assert archive.read("[Content_Types].xml") == b"<Types/>"
        print(f"{variant}: stdlib readable, bytes={len(data)}")
