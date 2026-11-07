"""Reject malformed ordinary extra fields adjacent to required ZIP64 metadata.

All archives are synthetic. The scanner must leave each input unchanged.
"""
from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

import pytest


ZIP64_OFFSET = struct.pack("<HHQ", 0x0001, 8, 0)
OVERRUN = struct.pack("<HH", 0xCAFE, 0xFFFF) + b"x"


def make_malformed_mixed_zip(variant: str) -> bytes:
    extras = {
        "short-before": b"\xaa" + ZIP64_OFFSET,
        "short-after": ZIP64_OFFSET + b"\xaa",
        "overrun-before": OVERRUN + ZIP64_OFFSET,
        "overrun-after": ZIP64_OFFSET + OVERRUN,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("xl/workbook.xml", b"<workbook/>")

    data = bytearray(output.getvalue())
    central = data.find(b"PK\x01\x02")
    end = data.rfind(b"PK\x05\x06")
    assert 0 < central < end
    name_size, original_extra = struct.unpack_from("<HH", data, central + 28)
    assert original_extra == 0
    assert struct.unpack_from("<I", data, central + 42)[0] == 0

    struct.pack_into("<I", data, central + 42, 0xFFFFFFFF)
    extra = extras[variant]
    data[central + 46 + name_size:central + 46 + name_size] = extra
    struct.pack_into("<H", data, central + 30, len(extra))
    end += len(extra)
    assert data[end:end + 4] == b"PK\x05\x06"
    directory_size = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, directory_size + len(extra))
    return bytes(data)


@pytest.mark.parametrize(
    "variant", ["short-before", "short-after", "overrun-before", "overrun-after"]
)
def test_zip64_central_malformed_ordinary_extra_rejected_before_zipfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str,
) -> None:
    from labvault_scout import identifier

    data = make_malformed_mixed_zip(variant)
    path = tmp_path / f"mixed-extra-{variant}.xlsx"
    path.write_bytes(data)

    def reject_late_parse(*args: object, **kwargs: object) -> None:
        raise AssertionError("Malformed central extras reached ZipFile")

    with monkeypatch.context() as patch:
        patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
        assert identifier.inspect_zip_container(path) == "Invalid ZIP directory extra"
    assert path.read_bytes() == data


if __name__ == "__main__":
    for case in ("short-before", "short-after", "overrun-before", "overrun-after"):
        data = make_malformed_mixed_zip(case)
        assert len(data) < 512
        print(case, len(data))
