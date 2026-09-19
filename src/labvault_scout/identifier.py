from __future__ import annotations

import zipfile
from pathlib import Path

ZIP_MAGIC = bytes.fromhex("504B0304")
OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
HDF5_MAGIC = bytes.fromhex("894844460D0A1A0A")
PDF_MAGIC = b"%PDF-"


def signature_from_head(head: bytes) -> str:
    """Return a coarse signature label from already-read header bytes."""
    if head.startswith(ZIP_MAGIC):
        return "ZIP"
    if head.startswith(OLE_MAGIC):
        return "OLE"
    if head.startswith(HDF5_MAGIC):
        return "HDF5"
    if head.startswith(PDF_MAGIC):
        return "PDF"
    return ""


def inspect_signature(path: Path) -> str:
    """Return a coarse container/signature label without executing file content."""
    with path.open("rb") as handle:
        return signature_from_head(handle.read(8))


def hdf5_container_from_header(header: bytes) -> str:
    """Validate HDF5 superblock evidence from already-read header bytes."""
    if signature_from_head(header) != "HDF5":
        return ""
    try:
        if len(header) < 9:
            return "Truncated HDF5 container"
        version = header[8]
        if version not in (0, 1, 2, 3):
            return f"Unknown HDF5 superblock version {version}"
        return f"HDF5 superblock v{version}"
    except (IndexError, ValueError):
        return "Invalid HDF5 container"


def inspect_hdf5_container(path: Path) -> str:
    """Validate bounded HDF5 superblock evidence without parsing datasets."""
    try:
        with path.open("rb") as handle:
            return hdf5_container_from_header(handle.read(16))
    except OSError:
        return "Unreadable HDF5 container"


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
                    with archive.open("mimetype") as member:
                        media_type = member.read(256).decode("ascii", errors="strict").strip()
                except (KeyError, UnicodeDecodeError, RuntimeError, OSError):
                    media_type = ""
                odf_types = {
                    "application/vnd.oasis.opendocument.spreadsheet": "OpenDocument Spreadsheet",
                    "application/vnd.oasis.opendocument.text": "OpenDocument Text",
                    "application/vnd.oasis.opendocument.presentation": "OpenDocument Presentation",
                }
                if media_type in odf_types:
                    return odf_types[media_type]
            if "ro-crate-metadata.json" in names:
                return "RO-Crate Research Object"
            if "bagit.txt" in names and "bag-info.txt" in names:
                return "BagIt Research Package"
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


def ole_container_from_header(header: bytes, size: int) -> str:
    """Validate bounded OLE header evidence from already-read bytes."""
    if signature_from_head(header) != "OLE":
        return ""
    try:
        if size < 512:
            return "Truncated OLE container"
        if len(header) < 512:
            return "Truncated OLE container"
        byte_order = int.from_bytes(header[28:30], "little")
        sector_shift = int.from_bytes(header[30:32], "little")
        if byte_order != 0xFFFE:
            return "Invalid OLE byte order"
        if sector_shift not in (9, 12):
            return "Invalid OLE sector size"
        return f"OLE Compound File ({1 << sector_shift}-byte sectors)"
    except (IndexError, ValueError):
        return "Invalid OLE container"


def inspect_ole_container(path: Path) -> str:
    """Perform bounded, read-only OLE evidence inspection without parsing streams."""
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            return ole_container_from_header(handle.read(512), size)
    except OSError:
        return "Unreadable OLE container"
