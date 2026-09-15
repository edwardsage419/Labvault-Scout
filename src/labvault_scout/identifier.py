from __future__ import annotations

import zipfile
from pathlib import Path

ZIP_MAGIC = bytes.fromhex("504B0304")
OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
HDF5_MAGIC = bytes.fromhex("894844460D0A1A0A")
PDF_MAGIC = b"%PDF-"


def inspect_signature(path: Path) -> str:
    """Return a coarse container/signature label without executing file content."""
    with path.open("rb") as handle:
        head = handle.read(8)
    if head.startswith(ZIP_MAGIC):
        return "ZIP"
    if head.startswith(OLE_MAGIC):
        return "OLE"
    if head.startswith(HDF5_MAGIC):
        return "HDF5"
    if head.startswith(PDF_MAGIC):
        return "PDF"
    return ""


def inspect_zip_container(path: Path) -> str:
    """Identify selected ZIP based formats from member names without extraction."""
    if inspect_signature(path) != "ZIP":
        return ""
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" in names:
                if any(name.startswith("xl/") for name in names):
                    return "OOXML Excel"
                if any(name.startswith("word/") for name in names):
                    return "OOXML Word"
                if any(name.startswith("ppt/") for name in names):
                    return "OOXML PowerPoint"
            if "mimetype" in names:
                try:
                    media_type = archive.read("mimetype").decode("ascii", errors="strict").strip()
                except (KeyError, UnicodeDecodeError, RuntimeError, OSError):
                    media_type = ""
                odf_types = {
                    "application/vnd.oasis.opendocument.spreadsheet": "OpenDocument Spreadsheet",
                    "application/vnd.oasis.opendocument.text": "OpenDocument Text",
                    "application/vnd.oasis.opendocument.presentation": "OpenDocument Presentation",
                }
                if media_type in odf_types:
                    return odf_types[media_type]
            if "META-INF/MANIFEST.MF" in names:
                return "JAR compatible ZIP"
            return "ZIP archive"
    except (OSError, zipfile.BadZipFile, RuntimeError):
        return "Invalid ZIP container"


def extension_signature_status(path: Path, signature: str) -> str:
    """Flag strong contradictions for formats whose outer container is predictable."""
    ext = path.suffix.lower()
    expected = {
        ".zip": "ZIP",
        ".xlsx": "ZIP",
        ".docx": "ZIP",
        ".pptx": "ZIP",
        ".h5": "HDF5",
        ".hdf5": "HDF5",
        ".pdf": "PDF",
        ".xls": "OLE",
    }.get(ext)
    if expected and signature and signature != expected:
        return f"mismatch: expected {expected}, detected {signature}"
    if expected and not signature:
        return f"unverified: expected {expected}"
    if expected == signature:
        return "verified"
    return ""


def inspect_ole_container(path: Path) -> str:
    """Perform bounded, read-only OLE evidence inspection without parsing streams."""
    if inspect_signature(path) != "OLE":
        return ""
    try:
        size = path.stat().st_size
        if size < 512:
            return "Truncated OLE container"
        with path.open("rb") as handle:
            header = handle.read(512)
        if len(header) < 512:
            return "Truncated OLE container"
        byte_order = int.from_bytes(header[28:30], "little")
        sector_shift = int.from_bytes(header[30:32], "little")
        if byte_order != 0xFFFE:
            return "Invalid OLE byte order"
        if sector_shift not in (9, 12):
            return "Invalid OLE sector size"
        return f"OLE Compound File ({1 << sector_shift}-byte sectors)"
    except OSError:
        return "Unreadable OLE container"
