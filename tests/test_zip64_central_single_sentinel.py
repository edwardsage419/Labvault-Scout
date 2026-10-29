"""Regressions for ZIP64 central-directory records with one size sentinel."""

from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

import pytest

from labvault_scout import identifier


CONTENT = b"<Types/>" * 40


def make_zip64_single_sentinel(
    field: str, delta: int, compression: int,
) -> tuple[bytes, tuple[int, int]]:
    """Forge one central ZIP64 size sentinel while retaining the local header."""
    if field not in {"compressed", "uncompressed"} or delta not in {0, 1}:
        raise ValueError("Unsupported fixture variant")
    if compression not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
        raise ValueError("Unsupported compression method")

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        archive.writestr("[Content_Types].xml", CONTENT)
        archive.writestr("xl/workbook.xml", b"<workbook/>")

    data = bytearray(output.getvalue())
    central = data.find(b"PK\x01\x02")
    end = data.rfind(b"PK\x05\x06")
    assert 0 < central < end
    compressed, uncompressed = struct.unpack_from("<II", data, central + 20)
    assert 0 < compressed <= uncompressed < 0xFFFFFFFF
    name_size, extra_size = struct.unpack_from("<HH", data, central + 28)
    assert extra_size == 0

    size_field_offset = 20 if field == "compressed" else 24
    original = compressed if field == "compressed" else uncompressed
    struct.pack_into("<I", data, central + size_field_offset, 0xFFFFFFFF)
    extra = struct.pack("<HHQ", 0x0001, 8, original + delta)
    insert_at = central + 46 + name_size
    data[insert_at:insert_at] = extra
    struct.pack_into("<H", data, central + 30, len(extra))
    end += len(extra)
    directory_size = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, directory_size + len(extra))

    expected = (
        (compressed + delta, uncompressed)
        if field == "compressed" else
        (compressed, uncompressed + delta)
    )
    return bytes(data), expected


@pytest.mark.parametrize(
    "compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED],
    ids=["stored", "deflated"],
)
@pytest.mark.parametrize("field", ["compressed", "uncompressed"])
@pytest.mark.parametrize("delta", [0, 1], ids=["valid", "conflict"])
def test_zip64_central_single_sentinel_size_consistency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    compression: int, field: str, delta: int,
) -> None:
    """Accept matching ZIP64 values and reject contradictory central metadata."""
    payload, expected = make_zip64_single_sentinel(field, delta, compression)
    path = tmp_path / f"central-{compression}-{field}-{delta}.xlsx"
    path.write_bytes(payload)
    with zipfile.ZipFile(path) as archive:
        assert archive.namelist() == ["[Content_Types].xml", "xl/workbook.xml"]
        info = archive.infolist()[0]
        assert (info.compress_size, info.file_size) == expected
        if delta == 0:
            assert archive.read("[Content_Types].xml") == CONTENT

    if delta == 0:
        assert identifier.inspect_zip_container(path) == "OOXML Excel"
    else:
        expected_status = (
            "Ambiguous ZIP local compressed size" if field == "compressed"
            else "Ambiguous ZIP local uncompressed size"
        )

        def fail_if_classified(*args: object, **kwargs: object) -> None:
            raise AssertionError("Malformed central ZIP64 metadata reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", fail_if_classified)
            assert identifier.inspect_zip_container(path) == expected_status

    assert path.read_bytes() == payload
