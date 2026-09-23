from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from os import stat_result

from . import __version__
from .bundle import verify_bundle
from .compare import compare_reports, comparison_exit_code, load_scan_report, verify_report, write_comparison
from .evidence import build_evidence
from .hashing import sha256_with_head
from .identifier import dicom_container_from_header, extension_signature_status, fcs_container_from_header, fits_container_from_header, hdf5_container_from_header, inspect_gzip_nifti, inspect_hdf5_container, inspect_signature, inspect_zip_container, matlab5_container_from_header, netcdf_container_from_header, nifti1_container_from_header, ole_container_from_header, signature_from_head, spss_container_from_header, stata_dta_container_from_header, tiff_container_from_header
from .actions import recommended_action
from .priority import assign_priority, priority_reason
from .relationships import detect_open_copies
from .report import write_reports
from .risk import classify, load_rules, rules_sha256
from .schema_registry import SCHEMA_FILES, load_schema_text
from .scanner import iter_files


def _file_changed_during_scan(before: stat_result, after: stat_result) -> bool:
    """Return True when stable file identity or metadata changed during hashing."""
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    return any(getattr(before, field, None) != getattr(after, field, None) for field in fields)


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

    def record_issue(path: Path, error: str) -> None:
        try:
            error_path = path.relative_to(root).as_posix()
        except ValueError:
            error_path = path.name
        errors.append({"path": error_path, "error": error})

    def record_error(path: Path, exc: OSError) -> None:
        record_issue(path, type(exc).__name__)

    for path in iter_files(root, excluded=excluded_output, on_error=record_error):
        try:
            stat = path.stat()
            rule = classify(path, rules)
            digest, header = sha256_with_head(path)
            post_stat = path.stat()
            if _file_changed_during_scan(stat, post_stat):
                record_issue(path, "FileChangedDuringScan")
                continue
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
            elif signature == "NETCDF":
                container_type = netcdf_container_from_header(header)
            elif signature == "TIFF":
                container_type = tiff_container_from_header(header)
            elif signature == "FITS":
                container_type = fits_container_from_header(header, stat.st_size)
            elif signature == "MAT5":
                container_type = matlab5_container_from_header(header)
            elif signature == "DICOM":
                container_type = dicom_container_from_header(header)
            elif signature == "FCS":
                container_type = fcs_container_from_header(header, stat.st_size)
            elif signature == "SPSS":
                container_type = spss_container_from_header(header, stat.st_size)
            elif signature == "STATA_DTA":
                container_type = stata_dta_container_from_header(header)
            elif path.suffix.lower() == ".dcm":
                container_type = dicom_container_from_header(header)
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
    verify_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print machine-readable verification result",
    )

    bundle_parser = sub.add_parser("verify-bundle", help="Verify all core files in a report directory")
    bundle_parser.add_argument("directory", type=Path)
    bundle_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print machine-readable bundle verification result",
    )

    schema_parser = sub.add_parser("schema", help="Print a packaged JSON Schema")
    schema_parser.add_argument("kind", choices=sorted(SCHEMA_FILES))

    args = parser.parse_args()
    if args.command == "scan":
        try:
            count = scan(args.directory, args.output)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(2) from None
        print(f"Scanned {count} files. Report: {args.output / 'report.html'}")
    elif args.command == "compare":
        try:
            result = compare_reports(args.before, args.after)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(2) from None
        write_comparison(result, args.output)
        print(f"Compared reports. Changes: {result['summary']['change_count']}. Report: {args.output / 'comparison.html'}")
        if args.exit_code:
            raise SystemExit(comparison_exit_code(result))
    elif args.command == "verify":
        try:
            result = verify_report(load_scan_report(args.report))
        except ValueError as exc:
            if args.json_output:
                print(json.dumps({"status": "INVALID", "exit_code": 2, "error": str(exc)}, ensure_ascii=False, sort_keys=True))
            else:
                print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(2) from None
        if args.json_output:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            print(
                f"Report verification: {result['status']} | "
                f"schema={result['schema_version']} | "
                f"integrity={result['integrity_status']} | "
                f"scan_errors={result['error_count']}"
            )
        raise SystemExit(result["exit_code"])
    elif args.command == "verify-bundle":
        try:
            result = verify_bundle(args.directory)
        except ValueError as exc:
            if args.json_output:
                print(json.dumps({"status": "INVALID", "exit_code": 2, "error": str(exc)}, ensure_ascii=False, sort_keys=True))
            else:
                print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(2) from None
        if args.json_output:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            print(
                f"Bundle verification: {result['status']} | "
                f"checked_files={result['checked_files']} | "
                f"problems={len(result['problems'])}"
            )
        raise SystemExit(result["exit_code"])
    elif args.command == "schema":
        print(load_schema_text(args.kind))


if __name__ == "__main__":
    main()
