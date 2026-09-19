from __future__ import annotations

import argparse
from pathlib import Path

from .evidence import build_evidence
from .hashing import sha256_with_head
from .identifier import extension_signature_status, hdf5_container_from_header, inspect_hdf5_container, inspect_signature, inspect_zip_container, ole_container_from_header, signature_from_head
from .actions import recommended_action
from .priority import assign_priority, priority_reason
from .relationships import detect_open_copies
from .report import write_reports
from .risk import classify, load_rules
from .scanner import iter_files


def scan(root: Path, output: Path) -> int:
    root = root.expanduser().resolve()
    rules = load_rules()
    rows: list[dict] = []
    errors: list[dict] = []
    output = output.expanduser().resolve()
    if output == root:
        raise ValueError("Output directory must not be the scan root.")
    try:
        output.relative_to(root)
    except ValueError:
        excluded_output = None
    else:
        excluded_output = output

    def record_error(path: Path, exc: OSError) -> None:
        try:
            error_path = str(path.relative_to(root))
        except ValueError:
            error_path = path.name
        errors.append({"path": error_path, "error": type(exc).__name__})

    for path in iter_files(root, excluded=excluded_output, on_error=record_error):
        try:
            stat = path.stat()
            rule = classify(path, rules)
            digest, header = sha256_with_head(path)
            signature = signature_from_head(header)
            if not signature and path.suffix.lower() in {".h5", ".hdf5", ".mat"}:
                signature = inspect_signature(path)
            if signature == "ZIP":
                container_type = inspect_zip_container(path)
            elif signature == "OLE":
                container_type = ole_container_from_header(header, stat.st_size)
            elif signature == "HDF5":
                container_type = hdf5_container_from_header(header) or inspect_hdf5_container(path)
            else:
                container_type = ""
            signature_status = extension_signature_status(path, signature, container_type)
            rows.append({
                "path": str(path.relative_to(root)),
                "size": stat.st_size,
                "sha256": digest,
                "format": rule["name"],
                "signature": signature,
                "signature_status": signature_status,
                "container_type": container_type,
                "risk": rule["risk"],
                "reason": rule["reason"],
            })
        except OSError as exc:
            record_error(path, exc)
    detect_open_copies(rows)
    for row in rows:
        row["evidence"], row["confidence"] = build_evidence(row)
        row["priority_score"], row["priority"] = assign_priority(row)
        row["priority_reason"] = priority_reason(row)
        row["recommended_action"] = recommended_action(row)
    write_reports(rows, output, errors)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(prog="labvault-scout")
    sub = parser.add_subparsers(dest="command", required=True)
    scan_parser = sub.add_parser("scan", help="Scan a directory read-only")
    scan_parser.add_argument("directory", type=Path)
    scan_parser.add_argument("-o", "--output", type=Path, default=Path("labvault-report"))
    args = parser.parse_args()
    if args.command == "scan":
        count = scan(args.directory, args.output)
        print(f"Scanned {count} files. Report: {args.output / 'report.html'}")


if __name__ == "__main__":
    main()
