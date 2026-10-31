"""Three-member ZIP64 central-directory comment boundary regression.

Fixtures are synthetic and small. Scanner access must preserve input bytes.
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


def make_three_member_zip64_middle_comment(delta: int) -> bytes:
    """Vary only the middle central member's declared comment length."""
    if delta not in (-1, 0, 1):
        raise ValueError(delta)
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
    name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, middle + 28)
    assert extra_len == comment_len == 0
    assert middle + 46 + name_len == last
    assert data[middle + 46:middle + 46 + name_len] == NAMES[1].encode()

    local_offset = struct.unpack_from("<I", data, middle + 42)[0]
    assert 0 < local_offset < 0xFFFFFFFF
    assert data[local_offset:local_offset + 4] == b"PK\x03\x04"
    zip64 = struct.pack("<HHQ", 0x0001, 8, local_offset)
    extras = ORDINARY + zip64
    insertion = middle + 46 + name_len
    data[insertion:insertion] = extras + COMMENT
    struct.pack_into("<I", data, middle + 42, 0xFFFFFFFF)
    struct.pack_into("<H", data, middle + 30, len(extras))
    struct.pack_into("<H", data, middle + 32, len(COMMENT) + delta)

    end += len(extras) + len(COMMENT)
    assert data[end:end + 4] == EOCD
    directory_size = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, directory_size + len(extras) + len(COMMENT))
    actual_next = insertion + len(extras) + len(COMMENT)
    declared_next = insertion + len(extras) + len(COMMENT) + delta
    assert data[actual_next:actual_next + 4] == CENTRAL
    assert (data[declared_next:declared_next + 4] == CENTRAL) == (delta == 0)
    return bytes(data)


@pytest.mark.parametrize("delta", [-1, 0, 1], ids=["underreported", "valid", "overreported"])
def test_zip64_three_member_middle_comment_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, delta: int,
) -> None:
    from labvault_scout import identifier

    payload = make_three_member_zip64_middle_comment(delta)
    path = tmp_path / f"three-member-middle-comment-{delta}.xlsx"
    path.write_bytes(payload)
    if delta == 0:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert archive.namelist() == list(NAMES)
            assert archive.infolist()[1].comment == COMMENT
            assert archive.infolist()[1].extra == ORDINARY + struct.pack(
                "<HHQ", 0x0001, 8, archive.infolist()[1].header_offset
            )
            for name, expected in zip(NAMES, CONTENTS):
                assert archive.read(name) == expected
        assert identifier.inspect_zip_container(path) == "OOXML Excel"
    else:
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Misaligned middle ZIP64 record reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == "Invalid ZIP directory record length"
    assert path.read_bytes() == payload



@pytest.mark.parametrize("declared_length", [3, 4, 5], ids=["short", "valid", "long"])
def test_zip64_middle_member_ordinary_extra_inner_length_with_comment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, declared_length: int,
) -> None:
    """Validate ordinary extra field boundaries before the ZIP64 offset and comment."""
    from labvault_scout import identifier

    payload = bytearray(make_three_member_zip64_middle_comment(0))
    first = payload.find(CENTRAL)
    middle = payload.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len = struct.unpack_from("<H", payload, middle + 28)[0]
    extra_start = middle + 46 + name_len
    assert payload[extra_start:extra_start + len(ORDINARY)] == ORDINARY
    # Change only the inner ordinary-field length; retain all outer ZIP lengths.
    struct.pack_into("<H", payload, extra_start + 2, declared_length)
    original = bytes(payload)
    path = tmp_path / f"middle-ordinary-extra-{declared_length}.xlsx"
    path.write_bytes(original)

    if declared_length == 4:
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            assert archive.namelist() == list(NAMES)
            assert archive.infolist()[1].comment == COMMENT
            assert archive.infolist()[1].extra == ORDINARY + struct.pack(
                "<HHQ", 0x0001, 8, archive.infolist()[1].header_offset
            )
            for name, content in zip(NAMES, CONTENTS):
                assert archive.read(name) == content
        assert identifier.inspect_zip_container(path) == "OOXML Excel"
    else:
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Malformed middle ordinary extra reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == "Invalid ZIP directory extra"
    assert path.read_bytes() == original


if __name__ == "__main__":
    for change in (-1, 0, 1):
        blob = make_three_member_zip64_middle_comment(change)
        if change == 0:
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                assert archive.namelist() == list(NAMES)
                assert archive.infolist()[1].comment == COMMENT
                for name, expected in zip(NAMES, CONTENTS):
                    assert archive.read(name) == expected
        print(f"delta={change}, bytes={len(blob)}")

def make_three_member_middle_zip64_then_ordinary(declared_length: int) -> bytes:
    """Keep the ZIP64 offset and member comment, with an ordinary extra after ZIP64."""
    if declared_length not in (3, 4, 5):
        raise ValueError(declared_length)
    data = bytearray(make_three_member_zip64_middle_comment(0))
    first = data.find(CENTRAL)
    middle = data.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, middle + 28)
    extra_start = middle + 46 + name_len
    local_offset = struct.unpack_from("<Q", data, extra_start + len(ORDINARY) + 4)[0]
    zip64 = struct.pack("<HHQ", 0x0001, 8, local_offset)
    assert extra_len == len(ORDINARY) + len(zip64)
    assert comment_len == len(COMMENT)
    assert data[extra_start:extra_start + extra_len] == ORDINARY + zip64
    data[extra_start:extra_start + extra_len] = zip64 + ORDINARY
    ordinary_start = extra_start + len(zip64)
    struct.pack_into("<H", data, ordinary_start + 2, declared_length)
    assert data[extra_start + extra_len:extra_start + extra_len + comment_len] == COMMENT
    assert data[extra_start + extra_len + comment_len:extra_start + extra_len + comment_len + 4] == CENTRAL
    return bytes(data)


@pytest.mark.parametrize("declared_length", [3, 4, 5], ids=["short", "valid", "long"])
def test_zip64_middle_member_trailing_ordinary_extra_length_with_comment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, declared_length: int,
) -> None:
    """Check trailing ordinary extra boundaries before a middle-member comment."""
    from labvault_scout import identifier

    payload = make_three_member_middle_zip64_then_ordinary(declared_length)
    path = tmp_path / f"middle-trailing-ordinary-{declared_length}.xlsx"
    path.write_bytes(payload)
    if declared_length == 4:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert archive.namelist() == list(NAMES)
            assert archive.infolist()[1].comment == COMMENT
            assert archive.infolist()[1].extra == struct.pack(
                "<HHQ", 0x0001, 8, archive.infolist()[1].header_offset
            ) + ORDINARY
            for name, expected in zip(NAMES, CONTENTS):
                assert archive.read(name) == expected
        assert identifier.inspect_zip_container(path) == "OOXML Excel"
    else:
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Malformed trailing ordinary extra reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == "Invalid ZIP directory extra"
    assert path.read_bytes() == payload

@pytest.mark.parametrize("declared_length", [7, 8, 9], ids=["short", "valid", "long"])
def test_zip64_middle_member_required_offset_inner_length_with_trailing_ordinary_and_comment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, declared_length: int,
) -> None:
    """Require the exact ZIP64 offset field length before an ordinary extra and comment."""
    from labvault_scout import identifier

    payload = bytearray(make_three_member_middle_zip64_then_ordinary(4))
    first = payload.find(CENTRAL)
    middle = payload.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from("<HHH", payload, middle + 28)
    extra_start = middle + 46 + name_len
    assert extra_len == 12 + len(ORDINARY)
    assert comment_len == len(COMMENT)
    assert int.from_bytes(payload[extra_start:extra_start + 2], "little") == 1
    assert struct.unpack_from("<H", payload, extra_start + 2)[0] == 8
    struct.pack_into("<H", payload, extra_start + 2, declared_length)
    original = bytes(payload)
    path = tmp_path / f"middle-zip64-offset-inner-{declared_length}.xlsx"
    path.write_bytes(original)

    if declared_length == 8:
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            assert archive.namelist() == list(NAMES)
            assert archive.infolist()[1].comment == COMMENT
            assert archive.infolist()[1].extra == (
                struct.pack("<HHQ", 0x0001, 8, archive.infolist()[1].header_offset) + ORDINARY
            )
            for name, content in zip(NAMES, CONTENTS):
                assert archive.read(name) == content
        assert identifier.inspect_zip_container(path) == "OOXML Excel"
    else:
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Malformed middle ZIP64 offset length reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == "Invalid ZIP directory ZIP64 extra"
    assert path.read_bytes() == original

def make_three_member_middle_partial_ordinary_header(header_bytes: int) -> bytes:
    """Reclassify the tail of an ordinary extra as comment without moving bytes."""
    if header_bytes not in (1, 2, 3, len(ORDINARY)):
        raise ValueError(header_bytes)
    data = bytearray(make_three_member_middle_zip64_then_ordinary(4))
    first = data.find(CENTRAL)
    middle = data.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, middle + 28)
    extra_start = middle + 46 + name_len
    zip64 = data[extra_start:extra_start + 12]
    assert zip64[:4] == struct.pack("<HH", 0x0001, 8)
    assert extra_len == 12 + len(ORDINARY)
    assert comment_len == len(COMMENT)
    assert data[extra_start + 12:extra_start + extra_len] == ORDINARY
    assert data[extra_start + extra_len:extra_start + extra_len + comment_len] == COMMENT
    moved = len(ORDINARY) - header_bytes
    struct.pack_into("<H", data, middle + 30, extra_len - moved)
    struct.pack_into("<H", data, middle + 32, comment_len + moved)
    assert data[extra_start + 12:extra_start + 12 + header_bytes] == ORDINARY[:header_bytes]
    assert data[extra_start + extra_len + comment_len:extra_start + extra_len + comment_len + 4] == CENTRAL
    return bytes(data)


@pytest.mark.parametrize("header_bytes", [1, 2, 3, 8], ids=["one-byte", "two-byte", "three-byte", "valid"])
def test_zip64_middle_trailing_ordinary_extra_partial_header_with_comment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, header_bytes: int,
) -> None:
    """Reject truncated ordinary-field headers following ZIP64, before ZipFile."""
    from labvault_scout import identifier

    payload = make_three_member_middle_partial_ordinary_header(header_bytes)
    path = tmp_path / f"middle-partial-extra-header-{header_bytes}.xlsx"
    path.write_bytes(payload)
    if header_bytes == 8:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert archive.namelist() == list(NAMES)
            assert archive.infolist()[1].comment == COMMENT
            assert archive.infolist()[1].extra.endswith(ORDINARY)
            for name, content in zip(NAMES, CONTENTS):
                assert archive.read(name) == content
        assert identifier.inspect_zip_container(path) == "OOXML Excel"
    else:
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Truncated middle ordinary extra header reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == "Invalid ZIP directory extra"
    assert path.read_bytes() == payload


def make_three_member_middle_two_ordinary_extras(declared_length: int) -> bytes:
    """Add a second ordinary extra after ZIP64 and an existing ordinary field."""
    if declared_length not in (3, 4, 5):
        raise ValueError(declared_length)
    data = bytearray(make_three_member_middle_zip64_then_ordinary(4))
    first = data.find(CENTRAL)
    middle = data.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, middle + 28)
    extra_start = middle + 46 + name_len
    assert extra_len == 12 + len(ORDINARY)
    assert comment_len == len(COMMENT)
    assert data[extra_start + 12:extra_start + extra_len] == ORDINARY
    second_extra = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    insertion = extra_start + extra_len
    data[insertion:insertion] = second_extra
    struct.pack_into("<H", data, middle + 30, extra_len + len(second_extra))
    end = data.rfind(EOCD)
    assert end > insertion
    directory_size = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, directory_size + len(second_extra))
    struct.pack_into("<H", data, insertion + 2, declared_length)
    assert data[insertion + len(second_extra):insertion + len(second_extra) + comment_len] == COMMENT
    assert data[insertion + len(second_extra) + comment_len:insertion + len(second_extra) + comment_len + 4] == CENTRAL
    return bytes(data)


@pytest.mark.parametrize("declared_length", [3, 4, 5], ids=["short", "valid", "long"])
def test_zip64_middle_two_ordinary_extras_last_length_with_comment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, declared_length: int,
) -> None:
    """Reject a malformed last ordinary field after two valid preceding extras."""
    from labvault_scout import identifier

    payload = make_three_member_middle_two_ordinary_extras(declared_length)
    path = tmp_path / f"middle-two-ordinary-extras-{declared_length}.xlsx"
    path.write_bytes(payload)
    if declared_length == 4:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert archive.namelist() == list(NAMES)
            assert archive.infolist()[1].comment == COMMENT
            assert archive.infolist()[1].extra == (
                struct.pack("<HHQ", 0x0001, 8, archive.infolist()[1].header_offset)
                + ORDINARY + struct.pack("<HH", 0xBEEF, 4) + CENTRAL
            )
            for name, content in zip(NAMES, CONTENTS):
                assert archive.read(name) == content
        assert identifier.inspect_zip_container(path) == "OOXML Excel"
    else:
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Malformed second ordinary extra reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == "Invalid ZIP directory extra"
    assert path.read_bytes() == payload


@pytest.mark.parametrize("declared_length", [3, 4, 5], ids=["short", "valid", "long"])
def test_zip64_middle_two_ordinary_extras_first_length_with_comment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, declared_length: int,
) -> None:
    """Reject a malformed first ordinary field before a second ordinary field."""
    from labvault_scout import identifier

    payload = bytearray(make_three_member_middle_two_ordinary_extras(4))
    first = payload.find(CENTRAL)
    middle = payload.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from("<HHH", payload, middle + 28)
    extra_start = middle + 46 + name_len
    ordinary_start = extra_start + 12
    second_extra = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    assert extra_len == 12 + len(ORDINARY) + len(second_extra)
    assert comment_len == len(COMMENT)
    assert payload[ordinary_start:ordinary_start + len(ORDINARY)] == ORDINARY
    assert payload[ordinary_start + len(ORDINARY):ordinary_start + len(ORDINARY) + len(second_extra)] == second_extra
    struct.pack_into("<H", payload, ordinary_start + 2, declared_length)
    original = bytes(payload)
    path = tmp_path / f"middle-first-ordinary-length-{declared_length}.xlsx"
    path.write_bytes(original)

    if declared_length == 4:
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            assert archive.namelist() == list(NAMES)
            assert archive.infolist()[1].comment == COMMENT
            assert archive.infolist()[1].extra == (
                struct.pack("<HHQ", 0x0001, 8, archive.infolist()[1].header_offset)
                + ORDINARY + second_extra
            )
            for name, expected in zip(NAMES, CONTENTS):
                assert archive.read(name) == expected
        assert identifier.inspect_zip_container(path) == "OOXML Excel"
    else:
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Malformed first ordinary extra reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == "Invalid ZIP directory extra"
    assert path.read_bytes() == original


def make_three_member_middle_first_ordinary_partial_header_with_second(
    header_bytes: int,
) -> bytes:
    """Keep a later ordinary field after a truncated first ordinary header."""
    if header_bytes not in (1, 2, 3, len(ORDINARY)):
        raise ValueError(header_bytes)
    data = bytearray(make_three_member_middle_two_ordinary_extras(4))
    first = data.find(CENTRAL)
    middle = data.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, middle + 28)
    extra_start = middle + 46 + name_len
    ordinary_start = extra_start + 12
    second_extra = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    assert extra_len == 12 + len(ORDINARY) + len(second_extra)
    assert comment_len == len(COMMENT)
    assert data[ordinary_start:ordinary_start + len(ORDINARY)] == ORDINARY
    assert data[
        ordinary_start + len(ORDINARY):
        ordinary_start + len(ORDINARY) + len(second_extra)
    ] == second_extra

    # Remove only the first ordinary field's trailing bytes. The next field,
    # member comment, and following central member retain their byte contents.
    removed = len(ORDINARY) - header_bytes
    del data[ordinary_start + header_bytes:ordinary_start + len(ORDINARY)]
    struct.pack_into("<H", data, middle + 30, extra_len - removed)
    end = data.rfind(EOCD)
    assert end > ordinary_start
    directory_size = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, directory_size - removed)

    assert data[ordinary_start:ordinary_start + header_bytes] == ORDINARY[:header_bytes]
    assert data[
        ordinary_start + header_bytes:
        ordinary_start + header_bytes + len(second_extra)
    ] == second_extra
    comment_start = extra_start + extra_len - removed
    assert data[comment_start:comment_start + comment_len] == COMMENT
    assert data[
        comment_start + comment_len:comment_start + comment_len + 4
    ] == CENTRAL
    return bytes(data)


@pytest.mark.parametrize(
    "header_bytes", [1, 2, 3, 8],
    ids=["one-byte", "two-byte", "three-byte", "valid"],
)
def test_zip64_middle_first_ordinary_partial_header_before_second_with_comment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, header_bytes: int,
) -> None:
    """Reject a partial first ordinary header without consuming the next field."""
    from labvault_scout import identifier

    payload = make_three_member_middle_first_ordinary_partial_header_with_second(
        header_bytes
    )
    path = tmp_path / f"middle-first-partial-before-second-{header_bytes}.xlsx"
    path.write_bytes(payload)
    if header_bytes == 8:
        second_extra = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert archive.namelist() == list(NAMES)
            assert archive.infolist()[1].comment == COMMENT
            assert archive.infolist()[1].extra == (
                struct.pack("<HHQ", 0x0001, 8, archive.infolist()[1].header_offset)
                + ORDINARY + second_extra
            )
            for name, expected in zip(NAMES, CONTENTS):
                assert archive.read(name) == expected
        assert identifier.inspect_zip_container(path) == "OOXML Excel"
    else:
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Truncated first ordinary extra reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == "Invalid ZIP directory extra"
    assert path.read_bytes() == payload


def make_three_member_middle_second_ordinary_partial_header(
    header_bytes: int,
) -> bytes:
    """Keep the first ordinary field intact and truncate the second header."""
    if header_bytes not in (1, 2, 3, len(ORDINARY)):
        raise ValueError(header_bytes)
    data = bytearray(make_three_member_middle_two_ordinary_extras(4))
    first = data.find(CENTRAL)
    middle = data.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, middle + 28)
    extra_start = middle + 46 + name_len
    second_start = extra_start + 12 + len(ORDINARY)
    second_extra = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    assert extra_len == 12 + len(ORDINARY) + len(second_extra)
    assert comment_len == len(COMMENT)
    assert data[extra_start + 12:second_start] == ORDINARY
    assert data[second_start:second_start + len(second_extra)] == second_extra

    # Reclassify the second field's tail as comment. The bytes and next
    # central-directory record stay in place, isolating the header boundary.
    moved = len(second_extra) - header_bytes
    struct.pack_into("<H", data, middle + 30, extra_len - moved)
    struct.pack_into("<H", data, middle + 32, comment_len + moved)
    assert data[second_start:second_start + header_bytes] == second_extra[:header_bytes]
    assert data[
        second_start + header_bytes:second_start + len(second_extra)
    ] == second_extra[header_bytes:]
    next_record = extra_start + extra_len + comment_len
    assert data[next_record:next_record + 4] == CENTRAL
    return bytes(data)


@pytest.mark.parametrize(
    "header_bytes", [1, 2, 3, 8],
    ids=["one-byte", "two-byte", "three-byte", "valid"],
)
def test_zip64_middle_second_ordinary_partial_header_before_comment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, header_bytes: int,
) -> None:
    """Reject a partial second ordinary header after a complete first field."""
    from labvault_scout import identifier

    payload = make_three_member_middle_second_ordinary_partial_header(header_bytes)
    path = tmp_path / f"middle-second-partial-extra-{header_bytes}.xlsx"
    path.write_bytes(payload)
    if header_bytes == 8:
        second_extra = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert archive.namelist() == list(NAMES)
            assert archive.infolist()[1].comment == COMMENT
            assert archive.infolist()[1].extra == (
                struct.pack("<HHQ", 0x0001, 8, archive.infolist()[1].header_offset)
                + ORDINARY + second_extra
            )
            for name, expected in zip(NAMES, CONTENTS):
                assert archive.read(name) == expected
        assert identifier.inspect_zip_container(path) == "OOXML Excel"
    else:
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Partial second ordinary header reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == "Invalid ZIP directory extra"
    assert path.read_bytes() == payload


def make_three_member_middle_interleaved_extra(first_length: int) -> bytes:
    """Place required ZIP64 offset between two ordinary fields."""
    if first_length not in (3, 4, 5):
        raise ValueError(first_length)
    data = bytearray(make_three_member_middle_two_ordinary_extras(4))
    first = data.find(CENTRAL)
    middle = data.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, middle + 28)
    extra_start = middle + 46 + name_len
    second = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    assert extra_len == 12 + len(ORDINARY) + len(second)
    assert comment_len == len(COMMENT)
    zip64 = bytes(data[extra_start:extra_start + 12])
    assert zip64[:4] == struct.pack("<HH", 0x0001, 8)
    assert data[extra_start + 12:extra_start + extra_len] == ORDINARY + second
    data[extra_start:extra_start + extra_len] = ORDINARY + zip64 + second
    struct.pack_into("<H", data, extra_start + 2, first_length)
    next_record = extra_start + extra_len + comment_len
    assert data[next_record:next_record + 4] == CENTRAL
    return bytes(data)


@pytest.mark.parametrize("first_length", [3, 4, 5], ids=["short", "valid", "long"])
def test_zip64_middle_interleaved_ordinary_extra_length_with_comment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, first_length: int,
) -> None:
    """Reject malformed ordinary fields before an interleaved ZIP64 offset."""
    from labvault_scout import identifier

    payload = make_three_member_middle_interleaved_extra(first_length)
    path = tmp_path / f"middle-interleaved-{first_length}.xlsx"
    path.write_bytes(payload)
    if first_length == 4:
        second = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert archive.namelist() == list(NAMES)
            info = archive.infolist()[1]
            assert info.comment == COMMENT
            assert info.extra == (
                ORDINARY + struct.pack("<HHQ", 0x0001, 8, info.header_offset) + second
            )
            for name, content in zip(NAMES, CONTENTS):
                assert archive.read(name) == content
        assert identifier.inspect_zip_container(path) == "OOXML Excel"
    else:
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Malformed interleaved extra reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == "Invalid ZIP directory extra"
    assert path.read_bytes() == payload

@pytest.mark.parametrize("declared_length", [3, 4, 5], ids=["short", "valid", "long"])
def test_zip64_middle_interleaved_trailing_ordinary_length_with_comment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, declared_length: int,
) -> None:
    """Reject malformed ordinary extra after an interleaved ZIP64 offset."""
    from labvault_scout import identifier

    payload = bytearray(make_three_member_middle_interleaved_extra(4))
    first = payload.find(CENTRAL)
    middle = payload.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from("<HHH", payload, middle + 28)
    extra_start = middle + 46 + name_len
    zip64_start = extra_start + len(ORDINARY)
    second_start = zip64_start + 12
    second = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    assert extra_len == len(ORDINARY) + 12 + len(second)
    assert comment_len == len(COMMENT)
    assert payload[extra_start:zip64_start] == ORDINARY
    assert payload[zip64_start:second_start][:4] == struct.pack("<HH", 0x0001, 8)
    assert payload[second_start:second_start + len(second)] == second
    struct.pack_into("<H", payload, second_start + 2, declared_length)
    original = bytes(payload)
    path = tmp_path / f"middle-interleaved-trailing-{declared_length}.xlsx"
    path.write_bytes(original)

    if declared_length == 4:
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            assert archive.namelist() == list(NAMES)
            info = archive.infolist()[1]
            assert info.comment == COMMENT
            assert info.extra == (
                ORDINARY + struct.pack("<HHQ", 0x0001, 8, info.header_offset) + second
            )
            for name, expected in zip(NAMES, CONTENTS):
                assert archive.read(name) == expected
        assert identifier.inspect_zip_container(path) == "OOXML Excel"
    else:
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Malformed trailing interleaved extra reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == "Invalid ZIP directory extra"
    assert path.read_bytes() == original

@pytest.mark.parametrize("declared_length", [7, 8, 9], ids=["short", "valid", "long"])
def test_zip64_middle_interleaved_required_offset_length_with_comment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, declared_length: int,
) -> None:
    """Require exact ZIP64 offset length between two ordinary extras."""
    from labvault_scout import identifier

    payload = bytearray(make_three_member_middle_interleaved_extra(4))
    first = payload.find(CENTRAL)
    middle = payload.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from("<HHH", payload, middle + 28)
    extra_start = middle + 46 + name_len
    zip64_start = extra_start + len(ORDINARY)
    trailing = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    assert extra_len == len(ORDINARY) + 12 + len(trailing)
    assert comment_len == len(COMMENT)
    assert payload[extra_start:zip64_start] == ORDINARY
    assert payload[zip64_start:zip64_start + 4] == struct.pack("<HH", 0x0001, 8)
    assert payload[zip64_start + 12:zip64_start + 12 + len(trailing)] == trailing
    struct.pack_into("<H", payload, zip64_start + 2, declared_length)
    original = bytes(payload)
    path = tmp_path / f"middle-interleaved-zip64-length-{declared_length}.xlsx"
    path.write_bytes(original)

    if declared_length == 8:
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            assert archive.namelist() == list(NAMES)
            info = archive.infolist()[1]
            assert info.comment == COMMENT
            assert info.extra == (
                ORDINARY + struct.pack("<HHQ", 0x0001, 8, info.header_offset) + trailing
            )
            for name, expected in zip(NAMES, CONTENTS):
                assert archive.read(name) == expected
        assert identifier.inspect_zip_container(path) == "OOXML Excel"
    else:
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Malformed interleaved ZIP64 offset reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == "Invalid ZIP directory ZIP64 extra"
    assert path.read_bytes() == original

def make_three_member_middle_interleaved_partial_zip64_header(header_bytes: int) -> bytes:
    """Place an incomplete ZIP64 field header before an ordinary field."""
    if header_bytes not in (1, 2, 3, 12):
        raise ValueError(header_bytes)
    data = bytearray(make_three_member_middle_interleaved_extra(4))
    first = data.find(CENTRAL)
    middle = data.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, middle + 28)
    extra_start = middle + 46 + name_len
    zip64_start = extra_start + len(ORDINARY)
    zip64 = bytes(data[zip64_start:zip64_start + 12])
    trailing = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    assert extra_len == len(ORDINARY) + len(zip64) + len(trailing)
    assert data[extra_start:zip64_start] == ORDINARY
    assert zip64[:4] == struct.pack("<HH", 0x0001, 8)
    assert data[zip64_start + 12:extra_start + extra_len] == trailing
    comment = bytes(data[extra_start + extra_len:extra_start + extra_len + comment_len])
    assert comment == COMMENT
    replacement_extra = ORDINARY + zip64[:header_bytes] + trailing
    replacement_comment = zip64[header_bytes:] + comment
    data[extra_start:extra_start + extra_len + comment_len] = (
        replacement_extra + replacement_comment
    )
    struct.pack_into("<H", data, middle + 30, len(replacement_extra))
    struct.pack_into("<H", data, middle + 32, len(replacement_comment))
    next_record = extra_start + len(replacement_extra) + len(replacement_comment)
    assert data[next_record:next_record + 4] == CENTRAL
    return bytes(data)


@pytest.mark.parametrize(
    "header_bytes", [1, 2, 3, 12],
    ids=["one-byte", "two-byte", "three-byte", "valid"],
)
def test_zip64_middle_interleaved_partial_zip64_header_before_ordinary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, header_bytes: int,
) -> None:
    """Reject truncated ZIP64 headers before a trailing ordinary extra."""
    from labvault_scout import identifier

    payload = make_three_member_middle_interleaved_partial_zip64_header(header_bytes)
    path = tmp_path / f"middle-interleaved-partial-zip64-{header_bytes}.xlsx"
    path.write_bytes(payload)

    if header_bytes == 12:
        trailing = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert archive.namelist() == list(NAMES)
            info = archive.infolist()[1]
            assert info.comment == COMMENT
            assert info.extra == (
                ORDINARY + struct.pack("<HHQ", 0x0001, 8, info.header_offset) + trailing
            )
            for name, expected in zip(NAMES, CONTENTS):
                assert archive.read(name) == expected
        assert identifier.inspect_zip_container(path) == "OOXML Excel"
    else:
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Partial interleaved ZIP64 header reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == "Invalid ZIP directory extra"
    assert path.read_bytes() == payload


def make_three_member_middle_interleaved_duplicate_zip64(variant: str) -> bytes:
    """Duplicate the required middle-member ZIP64 offset field in three positions."""
    if variant not in ("valid", "before-ordinary", "adjacent", "after-ordinary"):
        raise ValueError(variant)
    data = bytearray(make_three_member_middle_interleaved_extra(4))
    first = data.find(CENTRAL)
    middle = data.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, middle + 28)
    extra_start = middle + 46 + name_len
    zip64_start = extra_start + len(ORDINARY)
    zip64 = bytes(data[zip64_start:zip64_start + 12])
    trailing = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    assert zip64[:4] == struct.pack("<HH", 0x0001, 8)
    assert extra_len == len(ORDINARY) + len(zip64) + len(trailing)
    assert data[extra_start:extra_start + extra_len] == ORDINARY + zip64 + trailing
    assert data[extra_start + extra_len:extra_start + extra_len + comment_len] == COMMENT
    if variant == "valid":
        return bytes(data)

    insertion = {
        "before-ordinary": extra_start,
        "adjacent": zip64_start + len(zip64),
        "after-ordinary": extra_start + extra_len,
    }[variant]
    data[insertion:insertion] = zip64
    struct.pack_into("<H", data, middle + 30, extra_len + len(zip64))
    end = data.rfind(EOCD)
    assert end > middle
    directory_size = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, directory_size + len(zip64))
    next_record = extra_start + extra_len + len(zip64) + comment_len
    assert data[next_record:next_record + 4] == CENTRAL
    return bytes(data)


@pytest.mark.parametrize(
    "variant", ["valid", "before-ordinary", "adjacent", "after-ordinary"],
)
def test_zip64_middle_interleaved_duplicate_offset_with_comment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str,
) -> None:
    """Reject duplicate ZIP64 offsets before ZipFile, preserving valid ordering."""
    from labvault_scout import identifier

    payload = make_three_member_middle_interleaved_duplicate_zip64(variant)
    path = tmp_path / f"middle-interleaved-duplicate-{variant}.xlsx"
    path.write_bytes(payload)
    trailing = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert archive.namelist() == list(NAMES)
        info = archive.infolist()[1]
        assert info.comment == COMMENT
        zip64 = struct.pack("<HHQ", 0x0001, 8, info.header_offset)
        expected = {
            "valid": ORDINARY + zip64 + trailing,
            "before-ordinary": zip64 + ORDINARY + zip64 + trailing,
            "adjacent": ORDINARY + zip64 + zip64 + trailing,
            "after-ordinary": ORDINARY + zip64 + trailing + zip64,
        }[variant]
        assert info.extra == expected
        if variant == "valid":
            for name, content in zip(NAMES, CONTENTS):
                assert archive.read(name) == content

    if variant == "valid":
        assert identifier.inspect_zip_container(path) == "OOXML Excel"
    else:
        def reject_late_parse(*args: object, **kwargs: object) -> None:
            raise AssertionError("Duplicate middle ZIP64 offset reached ZipFile")

        with monkeypatch.context() as patch:
            patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
            assert identifier.inspect_zip_container(path) == "Invalid ZIP directory ZIP64 extra"
    assert path.read_bytes() == payload


@pytest.mark.parametrize(
    "duplicate_position,malformed_field,expected",
    [
        ("adjacent", "trailing", "Invalid ZIP directory ZIP64 extra"),
        ("after-ordinary", "trailing", "Invalid ZIP directory extra"),
        ("before-ordinary", "first", "Invalid ZIP directory extra"),
        ("adjacent", "first", "Invalid ZIP directory extra"),
    ],
)
def test_zip64_middle_interleaved_duplicate_and_malformed_ordinary_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    duplicate_position: str,
    malformed_field: str,
    expected: str,
) -> None:
    """Reject combined central-extra defects deterministically before ZipFile."""
    from labvault_scout import identifier

    payload = bytearray(make_three_member_middle_interleaved_duplicate_zip64(
        duplicate_position
    ))
    first = payload.find(CENTRAL)
    middle = payload.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from("<HHH", payload, middle + 28)
    extra_start = middle + 46 + name_len
    extra = bytes(payload[extra_start:extra_start + extra_len])
    trailing = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    assert extra_len == len(ORDINARY) + 24 + len(trailing)
    assert comment_len == len(COMMENT)
    zip64_start = 0 if duplicate_position == "before-ordinary" else len(ORDINARY)
    zip64 = extra[zip64_start:zip64_start + 12]
    assert zip64[:4] == struct.pack("<HH", 0x0001, 8)
    assert extra == {
        "before-ordinary": zip64 + ORDINARY + zip64 + trailing,
        "adjacent": ORDINARY + zip64 + zip64 + trailing,
        "after-ordinary": ORDINARY + zip64 + trailing + zip64,
    }[duplicate_position]
    first_start = extra.find(ORDINARY)
    trailing_start = extra.find(trailing)
    assert 0 <= first_start < trailing_start
    malformed_start = first_start if malformed_field == "first" else trailing_start
    struct.pack_into("<H", payload, extra_start + malformed_start + 2, 5)
    original = bytes(payload)
    path = tmp_path / f"mixed-duplicate-{duplicate_position}-{malformed_field}.xlsx"
    path.write_bytes(original)

    def reject_late_parse(*args: object, **kwargs: object) -> None:
        raise AssertionError("Combined malformed central extras reached ZipFile")

    with monkeypatch.context() as patch:
        patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
        assert identifier.inspect_zip_container(path) == expected
        assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "header_bytes", [1, 2, 3, 8],
    ids=["one-byte", "two-byte", "three-byte", "complete"],
)
def test_zip64_middle_interleaved_duplicate_after_partial_trailing_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, header_bytes: int,
) -> None:
    """Reject a partial ordinary header before a repeated ZIP64 offset field."""
    from labvault_scout import identifier

    payload = bytearray(make_three_member_middle_interleaved_duplicate_zip64(
        "after-ordinary"
    ))
    first = payload.find(CENTRAL)
    middle = payload.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from(
        "<HHH", payload, middle + 28
    )
    extra_start = middle + 46 + name_len
    zip64_start = extra_start + len(ORDINARY)
    zip64 = bytes(payload[zip64_start:zip64_start + 12])
    trailing = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    trailing_start = zip64_start + len(zip64)
    assert zip64[:4] == struct.pack("<HH", 0x0001, 8)
    assert comment_len == len(COMMENT)
    assert payload[extra_start:extra_start + extra_len] == (
        ORDINARY + zip64 + trailing + zip64
    )

    # Remove only the ordinary field tail, retaining the duplicate ZIP64.
    # Adjust directory lengths without moving the local member payloads.
    removed = len(trailing) - header_bytes
    del payload[trailing_start + header_bytes:trailing_start + len(trailing)]
    struct.pack_into("<H", payload, middle + 30, extra_len - removed)
    end = payload.rfind(EOCD)
    assert end > middle
    directory_size = struct.unpack_from("<I", payload, end + 12)[0]
    struct.pack_into("<I", payload, end + 12, directory_size - removed)
    next_record = extra_start + extra_len - removed + comment_len
    assert payload[next_record:next_record + 4] == CENTRAL
    assert payload[trailing_start + header_bytes:
                   trailing_start + header_bytes + len(zip64)] == zip64

    original = bytes(payload)
    path = tmp_path / f"middle-duplicate-partial-ordinary-{header_bytes}.xlsx"
    path.write_bytes(original)

    def reject_late_parse(*args: object, **kwargs: object) -> None:
        raise AssertionError("Mixed partial ordinary and duplicate ZIP64 reached ZipFile")

    expected = (
        "Invalid ZIP directory ZIP64 extra" if header_bytes == len(trailing)
        else "Invalid ZIP directory extra"
    )
    with monkeypatch.context() as patch:
        patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
        assert identifier.inspect_zip_container(path) == expected
        assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == original

@pytest.mark.parametrize(
    "header_bytes", [1, 2, 3, len(ORDINARY)],
    ids=["one-byte", "two-byte", "three-byte", "complete"],
)
def test_zip64_middle_interleaved_duplicate_after_partial_first_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, header_bytes: int,
) -> None:
    """Reject a partial first ordinary header before two ZIP64 offset fields."""
    from labvault_scout import identifier

    payload = bytearray(make_three_member_middle_interleaved_duplicate_zip64(
        "adjacent"
    ))
    first = payload.find(CENTRAL)
    middle = payload.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from(
        "<HHH", payload, middle + 28
    )
    extra_start = middle + 46 + name_len
    zip64_start = extra_start + len(ORDINARY)
    zip64 = bytes(payload[zip64_start:zip64_start + 12])
    trailing = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    assert zip64[:4] == struct.pack("<HH", 0x0001, 8)
    assert comment_len == len(COMMENT)
    assert payload[extra_start:extra_start + extra_len] == (
        ORDINARY + zip64 + zip64 + trailing
    )

    # Remove the first ordinary field tail without changing either ZIP64 field.
    removed = len(ORDINARY) - header_bytes
    del payload[extra_start + header_bytes:extra_start + len(ORDINARY)]
    struct.pack_into("<H", payload, middle + 30, extra_len - removed)
    end = payload.rfind(EOCD)
    assert end > middle
    directory_size = struct.unpack_from("<I", payload, end + 12)[0]
    struct.pack_into("<I", payload, end + 12, directory_size - removed)
    next_record = extra_start + extra_len - removed + comment_len
    assert payload[next_record:next_record + 4] == CENTRAL
    assert payload[extra_start + header_bytes:
                   extra_start + header_bytes + 2 * len(zip64)] == zip64 + zip64

    original = bytes(payload)
    path = tmp_path / f"middle-duplicate-partial-first-{header_bytes}.xlsx"
    path.write_bytes(original)

    def reject_late_parse(*args: object, **kwargs: object) -> None:
        raise AssertionError("Partial first ordinary and duplicate ZIP64 reached ZipFile")

    expected = (
        "Invalid ZIP directory ZIP64 extra" if header_bytes == len(ORDINARY)
        else "Invalid ZIP directory extra"
    )
    with monkeypatch.context() as patch:
        patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
        assert identifier.inspect_zip_container(path) == expected
        assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == original

@pytest.mark.parametrize(
    "header_bytes", [1, 2, 3, 12],
    ids=["one-byte", "two-byte", "three-byte", "complete-duplicate"],
)
def test_zip64_middle_duplicate_trailing_header_before_comment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, header_bytes: int,
) -> None:
    """Reject a truncated duplicate ZIP64 header before the member comment."""
    from labvault_scout import identifier

    payload = bytearray(make_three_member_middle_interleaved_duplicate_zip64(
        "after-ordinary"
    ))
    first = payload.find(CENTRAL)
    middle = payload.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from(
        "<HHH", payload, middle + 28
    )
    extra_start = middle + 46 + name_len
    trailing = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    duplicate_start = extra_start + len(ORDINARY) + 12 + len(trailing)
    duplicate = bytes(payload[duplicate_start:duplicate_start + 12])
    assert duplicate[:4] == struct.pack("<HH", 0x0001, 8)
    assert comment_len == len(COMMENT)
    assert extra_len == len(ORDINARY) + 24 + len(trailing)
    assert payload[extra_start:extra_start + extra_len] == (
        ORDINARY + duplicate + trailing + duplicate
    )

    # Reclassify the duplicate field's tail as comment bytes. The next
    # central record and archive size remain unchanged.
    moved = len(duplicate) - header_bytes
    struct.pack_into("<H", payload, middle + 30, extra_len - moved)
    struct.pack_into("<H", payload, middle + 32, comment_len + moved)
    new_comment_start = extra_start + extra_len - moved
    assert payload[new_comment_start:new_comment_start + moved + len(COMMENT)] == (
        duplicate[header_bytes:] + COMMENT
    )
    next_record = extra_start + extra_len + comment_len
    assert payload[next_record:next_record + 4] == CENTRAL

    original = bytes(payload)
    path = tmp_path / f"middle-partial-duplicate-zip64-{header_bytes}.xlsx"
    path.write_bytes(original)
    expected = (
        "Invalid ZIP directory ZIP64 extra" if header_bytes == 12
        else "Invalid ZIP directory extra"
    )

    def reject_late_parse(*args: object, **kwargs: object) -> None:
        raise AssertionError("Partial duplicate ZIP64 header reached ZipFile")

    with monkeypatch.context() as patch:
        patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
        assert identifier.inspect_zip_container(path) == expected
        assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == original

@pytest.mark.parametrize(
    "header_bytes", [1, 2, 3, 12],
    ids=["one-byte", "two-byte", "three-byte", "complete-duplicate"],
)
def test_zip64_middle_duplicate_first_header_before_ordinary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, header_bytes: int,
) -> None:
    """Reject a truncated leading duplicate ZIP64 header before ordinary extras."""
    from labvault_scout import identifier

    payload = bytearray(make_three_member_middle_interleaved_duplicate_zip64(
        "before-ordinary"
    ))
    first = payload.find(CENTRAL)
    middle = payload.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from(
        "<HHH", payload, middle + 28
    )
    extra_start = middle + 46 + name_len
    zip64 = bytes(payload[extra_start:extra_start + 12])
    trailing = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    assert zip64[:4] == struct.pack("<HH", 0x0001, 8)
    assert extra_len == 24 + len(ORDINARY) + len(trailing)
    assert comment_len == len(COMMENT)
    assert payload[extra_start:extra_start + extra_len] == (
        zip64 + ORDINARY + zip64 + trailing
    )

    # Shorten the first ZIP64 header while retaining the later valid ZIP64.
    removed = len(zip64) - header_bytes
    del payload[extra_start + header_bytes:extra_start + len(zip64)]
    struct.pack_into("<H", payload, middle + 30, extra_len - removed)
    end = payload.rfind(EOCD)
    assert end > middle
    directory_size = struct.unpack_from("<I", payload, end + 12)[0]
    struct.pack_into("<I", payload, end + 12, directory_size - removed)
    assert payload[extra_start:extra_start + extra_len - removed] == (
        zip64[:header_bytes] + ORDINARY + zip64 + trailing
    )
    assert payload[
        extra_start + extra_len - removed:
        extra_start + extra_len - removed + comment_len
    ] == COMMENT
    next_record = extra_start + extra_len - removed + comment_len
    assert payload[next_record:next_record + 4] == CENTRAL

    original = bytes(payload)
    path = tmp_path / f"middle-leading-duplicate-partial-{header_bytes}.xlsx"
    path.write_bytes(original)
    expected = (
        "Invalid ZIP directory ZIP64 extra" if header_bytes == len(zip64)
        else "Invalid ZIP directory extra"
    )

    def reject_late_parse(*args: object, **kwargs: object) -> None:
        raise AssertionError("Partial leading duplicate ZIP64 reached ZipFile")

    with monkeypatch.context() as patch:
        patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
        assert identifier.inspect_zip_container(path) == expected
        assert identifier.inspect_zip_container(path) == expected
    assert path.read_bytes() == original

@pytest.mark.parametrize(
    "declared_length", [7, 8, 9, 65535],
    ids=["short", "duplicate", "long", "overrun"],
)
def test_zip64_middle_duplicate_leading_offset_length_before_ordinary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, declared_length: int,
) -> None:
    """Reject invalid leading ZIP64 lengths before ordinary and duplicate extras."""
    from labvault_scout import identifier

    payload = bytearray(make_three_member_middle_interleaved_duplicate_zip64(
        "before-ordinary"
    ))
    first = payload.find(CENTRAL)
    middle = payload.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from(
        "<HHH", payload, middle + 28
    )
    extra_start = middle + 46 + name_len
    leading = bytes(payload[extra_start:extra_start + 12])
    trailing = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    assert leading[:4] == struct.pack("<HH", 0x0001, 8)
    assert extra_len == 24 + len(ORDINARY) + len(trailing)
    assert comment_len == len(COMMENT)
    assert payload[extra_start:extra_start + extra_len] == (
        leading + ORDINARY + leading + trailing
    )
    assert payload[
        extra_start + extra_len:extra_start + extra_len + comment_len
    ] == COMMENT
    next_record = extra_start + extra_len + comment_len
    assert payload[next_record:next_record + 4] == CENTRAL

    # Change only the first ZIP64 field's declared inner length.
    struct.pack_into("<H", payload, extra_start + 2, declared_length)
    original = bytes(payload)
    path = tmp_path / f"middle-leading-zip64-length-{declared_length}.xlsx"
    path.write_bytes(original)

    def reject_late_parse(*args: object, **kwargs: object) -> None:
        raise AssertionError("Malformed leading ZIP64 extra reached ZipFile")

    expected_error = (
        "Invalid ZIP directory extra" if declared_length == 65535
        else "Invalid ZIP directory ZIP64 extra"
    )
    with monkeypatch.context() as patch:
        patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
        assert identifier.inspect_zip_container(path) == expected_error
        assert identifier.inspect_zip_container(path) == expected_error
    assert path.read_bytes() == original

@pytest.mark.parametrize(
    "declared_length,expected_error",
    [
        (7, "Invalid ZIP directory ZIP64 extra"),
        (8, "Invalid ZIP directory ZIP64 extra"),
        (9, "Invalid ZIP directory extra"),
        (65535, "Invalid ZIP directory extra"),
    ],
    ids=["short", "duplicate", "overrun-one", "overrun-max"],
)
def test_zip64_middle_duplicate_trailing_offset_length_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    declared_length: int,
    expected_error: str,
) -> None:
    """Check trailing duplicate ZIP64 length precedence after ordinary extras."""
    from labvault_scout import identifier

    payload = bytearray(make_three_member_middle_interleaved_duplicate_zip64(
        "after-ordinary"
    ))
    first = payload.find(CENTRAL)
    middle = payload.find(CENTRAL, first + 4)
    assert 0 < first < middle
    name_len, extra_len, comment_len = struct.unpack_from(
        "<HHH", payload, middle + 28
    )
    extra_start = middle + 46 + name_len
    zip64_start = extra_start + len(ORDINARY)
    zip64 = bytes(payload[zip64_start:zip64_start + 12])
    trailing = struct.pack("<HH", 0xBEEF, 4) + CENTRAL
    duplicate_start = zip64_start + len(zip64) + len(trailing)
    assert zip64[:4] == struct.pack("<HH", 0x0001, 8)
    assert extra_len == len(ORDINARY) + 2 * len(zip64) + len(trailing)
    assert comment_len == len(COMMENT)
    assert payload[extra_start:extra_start + extra_len] == (
        ORDINARY + zip64 + trailing + zip64
    )
    assert payload[
        extra_start + extra_len:extra_start + extra_len + comment_len
    ] == COMMENT
    next_record = extra_start + extra_len + comment_len
    assert payload[next_record:next_record + 4] == CENTRAL

    # Keep the outer directory bounds fixed and mutate only the duplicate length.
    struct.pack_into("<H", payload, duplicate_start + 2, declared_length)
    original = bytes(payload)
    path = tmp_path / f"middle-trailing-duplicate-length-{declared_length}.xlsx"
    path.write_bytes(original)

    def reject_late_parse(*args: object, **kwargs: object) -> None:
        raise AssertionError("Malformed trailing ZIP64 extra reached ZipFile")

    with monkeypatch.context() as patch:
        patch.setattr(identifier.zipfile, "ZipFile", reject_late_parse)
        assert identifier.inspect_zip_container(path) == expected_error
        assert identifier.inspect_zip_container(path) == expected_error
    assert path.read_bytes() == original
