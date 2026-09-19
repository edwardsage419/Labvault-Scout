from __future__ import annotations

import gzip
import zipfile
from pathlib import Path
from typing import BinaryIO

ZIP_MAGIC = bytes.fromhex("504B0304")
ZIP_EMPTY_MAGIC = bytes.fromhex("504B0506")
ZIP_SPANNED_MAGIC = bytes.fromhex("504B0708")
ZIP_MAGICS = (ZIP_MAGIC, ZIP_EMPTY_MAGIC, ZIP_SPANNED_MAGIC)
OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
HDF5_MAGIC = bytes.fromhex("894844460D0A1A0A")
PDF_MAGIC = b"%PDF-"
GZIP_MAGIC = bytes.fromhex("1F8B")
NETCDF_MAGICS = {
    b"CDF\x01": "NetCDF CDF-1",
    b"CDF\x02": "NetCDF CDF-2",
    b"CDF\x05": "NetCDF CDF-5",
}
TIFF_CLASSIC_MAGICS = (bytes.fromhex("49492A00"), bytes.fromhex("4D4D002A"))
TIFF_BIG_MAGICS = (bytes.fromhex("49492B00"), bytes.fromhex("4D4D002B"))
TIFF_MAGICS = TIFF_CLASSIC_MAGICS + TIFF_BIG_MAGICS
FITS_SIMPLE_PREFIX = b"SIMPLE  ="


def signature_from_head(head: bytes) -> str:
    """Return a coarse signature label from already-read header bytes."""
    if any(head.startswith(magic) for magic in ZIP_MAGICS):
        return "ZIP"
    if head.startswith(OLE_MAGIC):
        return "OLE"
    if head.startswith(HDF5_MAGIC):
        return "HDF5"
    if head.startswith(PDF_MAGIC):
        return "PDF"
    if head.startswith(GZIP_MAGIC):
        return "GZIP"
    if any(head.startswith(magic) for magic in NETCDF_MAGICS):
        return "NETCDF"
    if any(head.startswith(magic) for magic in TIFF_MAGICS):
        return "TIFF"
    if head.startswith(FITS_SIMPLE_PREFIX):
        return "FITS"
    return ""


def netcdf_container_from_header(header: bytes) -> str:
    """Validate bounded NetCDF classic-family header evidence."""
    if signature_from_head(header) != "NETCDF":
        return ""
    if len(header) < 8:
        return "Truncated NetCDF container"
    for magic, label in NETCDF_MAGICS.items():
        if header.startswith(magic):
            return label
    return "Invalid NetCDF container"


def tiff_container_from_header(header: bytes) -> str:
    """Validate classic TIFF and BigTIFF header structure."""
    if signature_from_head(header) != "TIFF":
        return ""
    little = header[:2] == b"II"
    endian = "little" if little else "big"
    byteorder = "little" if little else "big"
    version = int.from_bytes(header[2:4], byteorder)

    if version == 42:
        if len(header) < 8:
            return "Truncated TIFF container"
        return f"TIFF classic ({endian}-endian)"

    if version == 43:
        if len(header) < 16:
            return "Truncated BigTIFF container"
        offset_size = int.from_bytes(header[4:6], byteorder)
        reserved = int.from_bytes(header[6:8], byteorder)
        if offset_size != 8 or reserved != 0:
            return "Invalid BigTIFF header"
        return f"BigTIFF ({endian}-endian)"

    return "Invalid TIFF version"


def fits_container_from_header(header: bytes, size: int) -> str:
    """Validate bounded FITS primary-header structure."""
    if signature_from_head(header) != "FITS":
        return ""
    if size < 2880 or len(header) < 240:
        return "Truncated FITS container"
    if size % 2880 != 0:
        return "Invalid FITS block size"

    first = header[0:80]
    second = header[80:160]
    third = header[160:240]
    if first[:8] != b"SIMPLE  " or first[8:10] != b"= ":
        return "Invalid FITS SIMPLE card"
    if first[29:30] == b"F":
        return "Nonconforming FITS (SIMPLE=F)"
    if first[29:30] != b"T":
        return "Invalid FITS SIMPLE value"
    if second[:8] != b"BITPIX  " or third[:8] != b"NAXIS   ":
        return "Invalid FITS mandatory header order"
    return "FITS primary HDU (SIMPLE=T)"


def _find_hdf5_signature_offset(handle: BinaryIO, size: int) -> int | None:
    """Find an HDF5 signature at specification-defined user-block offsets."""
    offset = 0
    while offset + len(HDF5_MAGIC) <= size:
        handle.seek(offset)
        if handle.read(len(HDF5_MAGIC)) == HDF5_MAGIC:
            return offset
        offset = 512 if offset == 0 else offset * 2
    return None


def inspect_signature(path: Path) -> str:
    """Return a coarse container/signature label without executing file content."""
    size = path.stat().st_size
    with path.open("rb") as handle:
        head = handle.read(8)
        signature = signature_from_head(head)
        if signature:
            return signature
        return "HDF5" if _find_hdf5_signature_offset(handle, size) is not None else ""


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
    """Validate HDF5 superblock evidence without parsing datasets."""
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            offset = _find_hdf5_signature_offset(handle, size)
            if offset is None:
                return ""
            handle.seek(offset)
            return hdf5_container_from_header(handle.read(16))
    except OSError:
        return "Unreadable HDF5 container"


def nifti1_container_from_header(header: bytes) -> str:
    """Validate bounded NIfTI-1 header evidence."""
    if len(header) < 348:
        return "Truncated NIfTI-1 header"

    little_size = int.from_bytes(header[:4], "little")
    big_size = int.from_bytes(header[:4], "big")
    if 348 not in (little_size, big_size):
        return "Invalid NIfTI-1 header size"

    magic = header[344:348]
    if magic == b"n+1\x00":
        return "NIfTI-1 single-file"
    if magic == b"ni1\x00":
        return "NIfTI-1 paired-file"
    return "Invalid NIfTI-1 magic"


def inspect_gzip_nifti(path: Path) -> str:
    """Inspect only the decompressed NIfTI-1 header inside a gzip stream."""
    if inspect_signature(path) != "GZIP":
        return ""
    try:
        with gzip.open(path, "rb") as handle:
            header = handle.read(348)
        return nifti1_container_from_header(header)
    except (OSError, EOFError):
        return "Invalid GZIP container"


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
    except (OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError):
        return "Invalid ZIP container"


def extension_signature_status(path: Path, signature: str, container_type: str = "") -> str:
    """Flag strong contradictions for formats whose outer container is predictable."""
    lower_name = path.name.lower()
    ext = ".nii.gz" if lower_name.endswith(".nii.gz") else path.suffix.lower()

    if ext == ".nc":
        if signature == "NETCDF":
            return "verified" if container_type.startswith("NetCDF CDF-") else "unverified: expected NetCDF structure"
        if signature == "HDF5":
            return "container-only: HDF5"
        if signature:
            return f"mismatch: expected NetCDF/HDF5, detected {signature}"
        return "unverified: expected NetCDF/HDF5"

    if ext in {".tif", ".tiff"}:
        if signature == "TIFF":
            if container_type.startswith("TIFF classic") or container_type.startswith("BigTIFF"):
                return "verified"
            return "unverified: expected TIFF structure"
        if signature:
            return f"mismatch: expected TIFF, detected {signature}"
        return "unverified: expected TIFF"

    if ext == ".fits":
        if signature == "FITS":
            return "verified" if container_type.startswith("FITS primary HDU") else "unverified: expected FITS structure"
        if signature:
            return f"mismatch: expected FITS, detected {signature}"
        return "unverified: expected FITS"

    expected = {
        ".zip": "ZIP",
        ".xlsx": "ZIP",
        ".docx": "ZIP",
        ".pptx": "ZIP",
        ".h5": "HDF5",
        ".hdf5": "HDF5",
        ".pdf": "PDF",
        ".xls": "OLE",
        ".nii.gz": "GZIP",
        ".nii": "NIFTI1",
    }.get(ext)
    if expected and signature and signature != expected:
        return f"mismatch: expected {expected}, detected {signature}"
    if expected and not signature:
        return f"unverified: expected {expected}"
    if expected == signature:
        if ext == ".nii":
            if not container_type.startswith("NIfTI-1 "):
                return "unverified: expected NIfTI-1 structure"
            return "verified"
        if ext == ".nii.gz":
            if not container_type.startswith("NIfTI-1 "):
                return "unverified: expected NIfTI-1 structure"
            return "verified"
        if ext == ".xls":
            return "container-only: OLE"
        expected_container = {
            ".xlsx": "OOXML Excel",
            ".docx": "OOXML Word",
            ".pptx": "OOXML PowerPoint",
        }.get(ext)
        if expected_container and container_type and container_type != expected_container:
            return f"unverified: expected {expected_container} structure"
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
