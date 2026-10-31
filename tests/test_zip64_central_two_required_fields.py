"""Two-required-field ZIP64 central metadata with ordinary extras and a comment.

Synthetic three-member archives only. The scanner must leave inputs unchanged.
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


def make_middle_two_required_fields(variant: str) -> bytes:
    """Require compressed size and local offset, preserving middle-member bounds."""
    if variant not in {"valid", "size-conflict", "short", "long"}:
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
    assert 0 < compressed < 0xFFFFFFFF and 0 < uncompressed < 0xFFFFFFFF
    assert compressed != uncompressed
    assert 0 < local_offset < 0xFFFFFFFF
    assert data[local_offset:local_offset + 4] == b"PK\x03\x04"
    assert struct.unpack_from("<I", data, local_offset + 18)[0] == compressed
    size_value = compressed + (variant == "size-conflict")
    zip64 = struct.pack("<HHQQ", 0x0001, 16, size_value, local_offset)
    trailing = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    extras = ORDINARY + zip64 + trailing
    insert_at = middle + 46 + name_length
    data[insert_at:insert_at] = extras + COMMENT
    struct.pack_into("<I", data, middle + 20, 0xFFFFFFFF)
    struct.pack_into("<I", data, middle + 42, 0xFFFFFFFF)
    struct.pack_into("<H", data, middle + 30, len(extras))
    struct.pack_into("<H", data, middle + 32, len(COMMENT))
    if variant in {"short", "long"}:
        struct.pack_into("<H", data, insert_at + len(ORDINARY) + 2,
                         15 if variant == "short" else 17)
    end += len(extras) + len(COMMENT)
    assert data[end:end + 4] == EOCD
    directory_size = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, directory_size + len(extras) + len(COMMENT))
    next_record = insert_at + len(extras) + len(COMMENT)
    assert data[next_record:next_record + 4] == CENTRAL
    return bytes(data)


@pytest.mark.parametrize("variant,expected", [
    ("valid", "OOXML Excel"),
    ("size-conflict", "Ambiguous ZIP local compressed size"),
    ("short", "Invalid ZIP directory ZIP64 extra"),
    ("long", "Invalid ZIP directory ZIP64 extra"),
])
def test_middle_zip64_compressed_and_offset_with_ordinary_extras(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str, expected: str,
) -> None:
    """Validate ZIP64 field order, exact length and local size agreement."""
    from labvault_scout import identifier

    payload = make_middle_two_required_fields(variant)
    path = tmp_path / f"middle-two-required-{variant}.xlsx"
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
            raise AssertionError("Malformed two-field ZIP64 reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == expected
            assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == payload
