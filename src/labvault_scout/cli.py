from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .compare import compare_reports, comparison_exit_code, load_scan_report, verify_report, write_comparison
from .evidence import build_evidence
from .hashing import sha256_with_head
from .identifier import extension_signature_status, hdf5_container_from_header, inspect_gzip_nifti, inspect_hdf5_container, inspect_signature, inspect_zip_container, nifti1_container_from_header, ole_container_from_header, signature_from_head
from .actions import recommended_action
from .priority import assign_priority, priority_reason
from .relationships import detect_open_copies
from .report import write_reports
from .risk import classify, load_rules, rules_sha256
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
            error_path = path.relative_to(root).as_posix()
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
            elif signature == "GZIP" and path.name.lower().endswith(".nii.gz"):
                container_type = inspect_gzip_nifti(path)
            elif path.suffix.lower() == ".nii":
                container_type = nifti1_container_from_header(header)
                if container_type.startswith("NIfTI-1 "):
                    signature = "NIFTI1"
            else:
                container_type = ""
            signature_status = extension_signature_status(path, signature, container_type)
            rows.append({
                "path": path.relative_to(root).as_posix(),
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
    provenance = {
        "hash_algorithm": "sha256",
        "path_style": "relative-posix",
        "rules_sha256": rules_sha256(rules),
        "rules_count": len(rules),
        "source_access": "read-only",
    }
    write_reports(rows, output, errors, provenance=provenance)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(prog="labvault-scout")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    scan_parser = sub.add_parser("scan", help="Scan a directory read-only")
    scan_parser.add_argument("directory", type=Path)
    scan_parser.add_argument("-o", "--output", type=Path, default=Path("labvault-report"))

    compare_parser = sub.add_parser("compare", help="Compare two scan.json reports")
    compare_parser.add_argument("before", type=Path)
    compare_parser.add_argument("after", type=Path)
    compare_parser.add_argument("-o", "--output", type=Path, default=Path("labvault-comparison"))
    compare_parser.add_argument(
        "--exit-code",
        action="store_true",
        help="Exit 0 for no changes, 1 for changes, or 2 for a partial comparison",
    )

    verify_parser = sub.add_parser("verify", help="Verify one scan.json report")
    verify_parser.add_argument("report", type=Path)

    args = parser.parse_args()
    if args.command == "scan":
        count = scan(args.directory, args.output)
        print(f"Scanned {count} files. Report: {args.output / 'report.html'}")
    elif args.command == "compare":
        result = compare_reports(args.before, args.after)
        write_comparison(result, args.output)
        print(f"Compared reports. Changes: {result['summary']['change_count']}. Report: {args.output / 'comparison.html'}")
        if args.exit_code:
            raise SystemExit(comparison_exit_code(result))
    elif args.command == "verify":
        result = verify_report(load_scan_report(args.report))
        print(
            f"Report verification: {result['status']} | "
            f"schema={result['schema_version']} | "
            f"integrity={result['integrity_status']} | "
            f"scan_errors={result['error_count']}"
        )
        raise SystemExit(result["exit_code"])


if __name__ == "__main__":
    main()
