"""Bounded regressions for a reordered final member with ZIP64 central sizes.

Fixtures are synthetic. Never extract, execute, or modify scanned input bytes.
"""
from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

import pytest

CENTRAL = b"PK\x01\x02"
EOCD = b"PK\x05\x06"
FIRST = b"[Content_Types].xml"
SECOND = b"xl/workbook.xml"
FIRST_DATA = b"<Types/>" * 3
SECOND_DATA = b"<workbook/>" * 7


def make_reordered_last_member_zip64_sizes(variant: str) -> bytes:
    """Move the second central record first, with both 64-bit size fields."""
    if variant not in {"valid", "compressed-conflict", "uncompressed-conflict"}:
        raise ValueError(variant)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(FIRST.decode(), FIRST_DATA)
        archive.writestr(SECOND.decode(), SECOND_DATA)
    data = bytearray(output.getvalue())
    first = data.find(CENTRAL)
    second = data.find(CENTRAL, first + 4)
    end = data.rfind(EOCD)
    assert 0 < first < second < end
    assert struct.unpack_from("<H", data, second + 30)[0] == 0
    first_name_size, first_extra_size, first_comment_size = struct.unpack_from(
        "<HHH", data, first + 28
    )
    assert first + 46 + first_name_size + first_extra_size + first_comment_size == second
    second_name_size, second_extra_size, second_comment_size = struct.unpack_from(
        "<HHH", data, second + 28
    )
    assert second + 46 + second_name_size + second_extra_size + second_comment_size == end
    compressed, uncompressed = struct.unpack_from("<II", data, second + 20)
    assert 0 < compressed < uncompressed < 0xFFFFFFFF
    second_offset = struct.unpack_from("<I", data, second + 42)[0]
    assert second_offset > 0
    assert data[second_offset:second_offset + 4] == b"PK\x03\x04"
    assert struct.unpack_from("<II", data, second_offset + 18) == (
        compressed, uncompressed
    )
    # ZIP64 extra order: uncompressed, then compressed.
    compressed64 = compressed + int(variant == "compressed-conflict")
    uncompressed64 = uncompressed + int(variant == "uncompressed-conflict")
    extra = struct.pack("<HHQQ", 0x0001, 16, uncompressed64, compressed64)
    struct.pack_into("<II", data, second + 20, 0xFFFFFFFF, 0xFFFFFFFF)
    insertion = second + 46 + second_name_size
    data[insertion:insertion] = extra
    struct.pack_into("<H", data, second + 30, len(extra))
    end += len(extra)
    assert data[end:end + 4] == EOCD
    directory_size = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, directory_size + len(extra))
    # Reverse the central directory without moving local file data.
    data[first:end] = data[second:end] + data[first:second]
    assert data[first:first + 4] == CENTRAL
    assert data[first + 46:first + 46 + len(SECOND)] == SECOND
    assert data[end:end + 4] == EOCD
    return bytes(data)


@pytest.mark.parametrize(
    "variant,expected",
    [
        ("valid", "OOXML Excel"),
        ("compressed-conflict", "Ambiguous ZIP local compressed size"),
        ("uncompressed-conflict", "Ambiguous ZIP local uncompressed size"),
    ],
)
def test_reordered_last_member_zip64_central_sizes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str, expected: str
) -> None:
    """Check second-member 64-bit sizes independently of central record order."""
    from labvault_scout import identifier

    data = make_reordered_last_member_zip64_sizes(variant)
    path = tmp_path / f"zip64-reordered-sizes-{variant}.xlsx"
    path.write_bytes(data)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.namelist() == [SECOND.decode(), FIRST.decode()]
        info = archive.infolist()[0]
        assert info.header_offset > 0
        if variant == "valid":
            assert archive.read(SECOND.decode()) == SECOND_DATA
            assert archive.read(FIRST.decode()) == FIRST_DATA
        elif variant == "compressed-conflict":
            assert info.compress_size > 0
        else:
            assert info.file_size > 0

    if variant != "valid":
        def fail_if_classified(*args: object, **kwargs: object) -> None:
            raise AssertionError("Contradictory central ZIP64 sizes reached ZipFile")
        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", fail_if_classified)
            assert identifier.inspect_zip_container(path) == expected
    else:
        assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == data


if __name__ == "__main__":
    for variant in ("valid", "compressed-conflict", "uncompressed-conflict"):
        payload = make_reordered_last_member_zip64_sizes(variant)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert archive.namelist() == [SECOND.decode(), FIRST.decode()]
            if variant == "valid":
                assert archive.read(SECOND.decode()) == SECOND_DATA
        print(variant, len(payload))
