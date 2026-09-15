from __future__ import annotations

from pathlib import Path

ZIP_MAGIC = b"PK\x03\x04"
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


def extension_signature_status(path: Path, signature: str) -> str:
    """Flag only strong contradictions for formats whose container is predictable."""
    ext = path.suffix.lower()
    expected = {
        ".zip": "ZIP",
        ".xlsx": "ZIP",
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
