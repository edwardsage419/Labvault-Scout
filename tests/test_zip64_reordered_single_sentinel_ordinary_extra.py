"""Reordered final-member ZIP64 single-size sentinels with ordinary extras.

All fixtures are synthetic; inspection must leave source bytes unchanged.
"""
from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

import pytest

FIRST = "[Content_Types].xml"
SECOND = "xl/workbook.xml"
FIRST_DATA = b"<Types/>" * 4
SECOND_DATA = b"<workbook/>" * 8
CENTRAL = b"PK\x01\x02"
EOCD = b"PK\x05\x06"
# The ordinary field's payload resembles a ZIP64 tag, but is opaque.
ORDINARY = struct.pack("<HH", 0xCAFE, 4) + b"\x01\x00\x08\x00"


def make_reordered_single_sentinel_extra(field: str, position: str, delta: int) -> bytes:
    """Forge one ZIP64 size sentinel on the final local member, then reorder central entries."""
    if field not in ("compressed", "uncompressed") or position not in ("before", "after"):
        raise ValueError("Unsupported field or position")
    if delta not in (0, 1):
        raise ValueError("Unsupported size delta")

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(FIRST, FIRST_DATA)
        archive.writestr(SECOND, SECOND_DATA)
    data = bytearray(output.getvalue())
    first = data.find(CENTRAL)
    second = data.find(CENTRAL, first + 4)
    end = data.rfind(EOCD)
    assert 0 < first < second < end
    first_name, first_extra, first_comment = struct.unpack_from("<HHH", data, first + 28)
    second_name, second_extra, second_comment = struct.unpack_from("<HHH", data, second + 28)
    assert first_extra == second_extra == 0
    assert first + 46 + first_name + first_comment == second
    assert second + 46 + second_name + second_comment == end
    assert data[second + 46:second + 46 + second_name] == SECOND.encode()

    compressed, uncompressed = struct.unpack_from("<II", data, second + 20)
    assert 0 < compressed < uncompressed < 0xFFFFFFFF
    local_offset = struct.unpack_from("<I", data, second + 42)[0]
    assert local_offset > 0 and data[local_offset:local_offset + 4] == b"PK\x03\x04"
    assert struct.unpack_from("<II", data, local_offset + 18) == (compressed, uncompressed)

    selected = compressed if field == "compressed" else uncompressed
    struct.pack_into("<I", data, second + (20 if field == "compressed" else 24), 0xFFFFFFFF)
    zip64 = struct.pack("<HHQ", 0x0001, 8, selected + delta)
    extras = ORDINARY + zip64 if position == "before" else zip64 + ORDINARY
    insertion = second + 46 + second_name
    data[insertion:insertion] = extras
    struct.pack_into("<H", data, second + 30, len(extras))
    end += len(extras)
    assert data[end:end + 4] == EOCD
    directory_bytes = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, directory_bytes + len(extras))

    # Reorder only central entries. The final local member remains second on disk.
    data[first:end] = data[second:end] + data[first:second]
    assert data[first:first + 4] == CENTRAL
    assert data[first + 46:first + 46 + len(SECOND)] == SECOND.encode()
    assert data[end:end + 4] == EOCD
    return bytes(data)


@pytest.mark.parametrize("field", ["compressed", "uncompressed"])
@pytest.mark.parametrize("position", ["before", "after"])
@pytest.mark.parametrize("delta", [0, 1], ids=["valid", "conflict"])
def test_reordered_final_member_zip64_single_sentinel_with_ordinary_extra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    field: str, position: str, delta: int,
) -> None:
    from labvault_scout import identifier

    payload = make_reordered_single_sentinel_extra(field, position, delta)
    path = tmp_path / f"reordered-single-{field}-{position}-{delta}.xlsx"
    path.write_bytes(payload)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert archive.namelist() == [SECOND, FIRST]
        info = archive.infolist()[0]
        assert info.header_offset > 0
        local_compressed, local_uncompressed = struct.unpack_from(
            "<II", payload, info.header_offset + 18
        )
        assert (info.compress_size, info.file_size) == (
            local_compressed + (delta if field == "compressed" else 0),
            local_uncompressed + (delta if field == "uncompressed" else 0),
        )
        assert ORDINARY in info.extra
        if delta == 0:
            assert archive.read(SECOND) == SECOND_DATA
            assert archive.read(FIRST) == FIRST_DATA

    if delta == 0:
        assert identifier.inspect_zip_container(path) == "OOXML Excel"
    else:
        expected = (
            "Ambiguous ZIP local compressed size" if field == "compressed"
            else "Ambiguous ZIP local uncompressed size"
        )

        def fail_if_classified(*args: object, **kwargs: object) -> None:
            raise AssertionError("Conflicting ZIP64 central size reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", fail_if_classified)
            assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == payload


if __name__ == "__main__":
    for size_field in ("compressed", "uncompressed"):
        for ordinary_position in ("before", "after"):
            for size_delta in (0, 1):
                blob = make_reordered_single_sentinel_extra(size_field, ordinary_position, size_delta)
                with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                    assert archive.namelist() == [SECOND, FIRST]
                    if size_delta == 0:
                        assert archive.read(SECOND) == SECOND_DATA
                        assert archive.read(FIRST) == FIRST_DATA
                print(size_field, ordinary_position, size_delta, len(blob))
