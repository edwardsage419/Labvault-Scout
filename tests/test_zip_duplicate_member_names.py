import warnings
from pathlib import Path
from zipfile import ZipFile

import pytest

from labvault_scout.identifier import inspect_zip_container


@pytest.mark.parametrize("kind", ["odf", "ooxml"])
def test_duplicate_zip_member_names_are_ambiguous(
    tmp_path: Path, kind: str,
) -> None:
    path = tmp_path / "ambiguous.zip"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(path, "w") as archive:
            if kind == "odf":
                archive.writestr("mimetype", "text/plain")
                archive.writestr(
                    "mimetype",
                    "application/vnd.oasis.opendocument.spreadsheet",
                )
            else:
                archive.writestr("[Content_Types].xml", "first")
                archive.writestr("[Content_Types].xml", "second")
                archive.writestr("xl/workbook.xml", "")

    original = path.read_bytes()
    assert inspect_zip_container(path) == "Ambiguous ZIP member names"
    assert path.read_bytes() == original


def test_unique_zip_member_names_keep_format_detection(tmp_path: Path) -> None:
    path = tmp_path / "unique.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "mimetype", "application/vnd.oasis.opendocument.spreadsheet"
        )
    assert inspect_zip_container(path) == "OpenDocument Spreadsheet"
