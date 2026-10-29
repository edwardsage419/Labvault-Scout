"""ZIP64 central-directory disk-start regression candidates for LabVault Scout.

Synthetic ZIPs only. No extraction or execution of archived content.
The production test imports labvault_scout only inside its test body so this
file can be collected and its fixtures independently checked before integration.
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


def make_zip64_central_disk_start(variant: str) -> bytes:
    """Forge the first central record's 16-bit disk sentinel and ZIP64 extra.

    A ZIP64 disk-start value is encoded in four bytes. The single-disk
    value zero is valid; a nonzero value declares unsupported spanning.
    """
    if variant not in {"zero", "nonzero", "missing", "short", "offset-zero", "offset-nonzero",
                        "ordinary-before-zero", "ordinary-after-zero", "ordinary-before-nonzero"}:
        raise ValueError("Unknown fixture variant")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT)
        archive.writestr("xl/workbook.xml", b"<workbook/>")

    data = bytearray(output.getvalue())
    central = data.find(CENTRAL)
    eocd = data.rfind(EOCD)
    assert 0 < central < eocd
    name_size, extra_size = struct.unpack_from("<HH", data, central + 28)
    assert extra_size == 0
    assert struct.unpack_from("<H", data, central + 34)[0] == 0

    struct.pack_into("<H", data, central + 34, 0xFFFF)
    if variant.startswith("offset-"):
        assert struct.unpack_from("<I", data, central + 42)[0] == 0
        struct.pack_into("<I", data, central + 42, 0xFFFFFFFF)
    if variant == "missing":
        return bytes(data)
    payload = (
        b"\x00\x00" if variant == "short"
        else (struct.pack("<Q", 0) if variant.startswith("offset-") else b"")
        + struct.pack("<I", 1 if variant in {"nonzero", "offset-nonzero", "ordinary-before-nonzero"} else 0)
    )
    extra = struct.pack("<HH", 0x0001, len(payload)) + payload
    ordinary = struct.pack("<HH", 0xCAFE, 3) + b"abc"
    if variant.startswith("ordinary-before"):
        extra = ordinary + extra
    elif variant == "ordinary-after-zero":
        extra += ordinary
    insertion = central + 46 + name_size
    data[insertion:insertion] = extra
    struct.pack_into("<H", data, central + 30, len(extra))
    eocd += len(extra)
    assert data[eocd:eocd + 4] == EOCD
    directory_size = struct.unpack_from("<I", data, eocd + 12)[0]
    struct.pack_into("<I", data, eocd + 12, directory_size + len(extra))
    return bytes(data)


@pytest.mark.parametrize(
    "variant,expected",
    [
        ("zero", "OOXML Excel"),
        ("nonzero", "Unsupported ZIP multi-disk metadata"),
        ("missing", "Invalid ZIP directory ZIP64 extra"),
        ("short", "Invalid ZIP directory ZIP64 extra"),
        ("offset-zero", "OOXML Excel"),
        ("offset-nonzero", "Unsupported ZIP multi-disk metadata"),
        ("ordinary-before-zero", "OOXML Excel"),
        ("ordinary-after-zero", "OOXML Excel"),
        ("ordinary-before-nonzero", "Unsupported ZIP multi-disk metadata"),
    ],
    ids=[
        "valid-single-disk", "unsupported-multidisk", "missing-zip64-extra",
        "short-zip64-extra", "offset-plus-disk-zero", "offset-plus-disk-nonzero",
        "ordinary-before-valid-disk", "ordinary-after-valid-disk",
        "ordinary-before-multidisk",
    ],
)
def test_zip64_central_disk_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str, expected: str,
) -> None:
    """Validate ZIP64 disk origin before name-based format classification."""
    from labvault_scout import identifier

    data = make_zip64_central_disk_start(variant)
    path = tmp_path / f"zip64-disk-{variant}.xlsx"
    path.write_bytes(data)
    with zipfile.ZipFile(path) as archive:
        assert archive.namelist() == ["[Content_Types].xml", "xl/workbook.xml"]
        if variant in {"zero", "offset-zero", "ordinary-before-zero", "ordinary-after-zero"}:
            assert archive.read("[Content_Types].xml") == CONTENT

    if variant not in {"zero", "offset-zero", "ordinary-before-zero", "ordinary-after-zero"}:
        def fail_if_classified(*args: object, **kwargs: object) -> None:
            raise AssertionError("Malformed ZIP64 disk metadata reached ZipFile")
        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", fail_if_classified)
            assert identifier.inspect_zip_container(path) == expected
    else:
        assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == data


def _self_check() -> None:
    for variant in (
        "zero", "nonzero", "missing", "short", "offset-zero", "offset-nonzero",
        "ordinary-before-zero", "ordinary-after-zero", "ordinary-before-nonzero",
    ):
        data = make_zip64_central_disk_start(variant)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert archive.namelist() == ["[Content_Types].xml", "xl/workbook.xml"]
            if variant in {"zero", "offset-zero", "ordinary-before-zero", "ordinary-after-zero"}:
                assert archive.read("[Content_Types].xml") == CONTENT
        print(f"{variant}: synthetic ZIP built and directory readable ({len(data)} bytes)")


if __name__ == "__main__":
    _self_check()