"""ZIP64 compressed-size and disk-start central fields in a middle member.

All archives are synthetic. Inspection must be deterministic and read-only.
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


def make_middle_compressed_disk(variant: str) -> bytes:
    """Require a 64-bit compressed size followed by a 32-bit disk number."""
    if variant not in {"valid", "size-conflict", "nonzero-disk", "short", "long", "overrun"}:
        raise ValueError(variant)
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
    name_length, old_extra, old_comment = struct.unpack_from("<HHH", data, middle + 28)
    assert old_extra == old_comment == 0
    assert middle + 46 + name_length == last
    compressed = struct.unpack_from("<I", data, middle + 20)[0]
    uncompressed = struct.unpack_from("<I", data, middle + 24)[0]
    local_offset = struct.unpack_from("<I", data, middle + 42)[0]
    assert 0 < compressed < 0xFFFFFFFF and compressed != uncompressed
    assert 0 < local_offset < 0xFFFFFFFF
    assert struct.unpack_from("<I", data, local_offset + 18)[0] == compressed
    assert struct.unpack_from("<H", data, middle + 34)[0] == 0
    zip64 = struct.pack(
        "<HHQI", 0x0001, 12,
        compressed + (variant == "size-conflict"),
        int(variant == "nonzero-disk"),
    )
    trailing = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    extras = ORDINARY + zip64 + trailing
    insert_at = middle + 46 + name_length
    data[insert_at:insert_at] = extras + COMMENT
    struct.pack_into("<I", data, middle + 20, 0xFFFFFFFF)
    struct.pack_into("<H", data, middle + 34, 0xFFFF)
    struct.pack_into("<H", data, middle + 30, len(extras))
    struct.pack_into("<H", data, middle + 32, len(COMMENT))
    if variant in {"short", "long", "overrun"}:
        declared = {"short": 11, "long": 13, "overrun": 65535}[variant]
        struct.pack_into("<H", data, insert_at + len(ORDINARY) + 2, declared)
    end += len(extras) + len(COMMENT)
    assert data[end:end + 4] == EOCD
    directory_size = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, directory_size + len(extras) + len(COMMENT))
    assert data[insert_at + len(extras) + len(COMMENT):][:4] == CENTRAL
    return bytes(data)


@pytest.mark.parametrize("variant,expected", [
    ("valid", "OOXML Excel"),
    ("size-conflict", "Ambiguous ZIP local compressed size"),
    ("nonzero-disk", "Unsupported ZIP multi-disk metadata"),
    ("short", "Invalid ZIP directory ZIP64 extra"),
    ("long", "Invalid ZIP directory ZIP64 extra"),
    ("overrun", "Invalid ZIP directory extra"),
])
def test_middle_zip64_compressed_size_and_disk_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str, expected: str,
) -> None:
    """Validate size/disk order, length precedence, and local agreement."""
    from labvault_scout import identifier

    payload = make_middle_compressed_disk(variant)
    path = tmp_path / f"middle-compressed-disk-{variant}.xlsx"
    path.write_bytes(payload)
    if variant == "valid":
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert archive.namelist() == list(NAMES)
            assert archive.infolist()[1].comment == COMMENT
            assert archive.infolist()[1].extra.startswith(ORDINARY)
            for name, content in zip(NAMES, CONTENTS):
                assert archive.read(name) == content
        assert identifier.inspect_zip_container(path) == expected
    else:
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Invalid ZIP64 compressed/disk fields reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == expected
            assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == payload
