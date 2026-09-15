from __future__ import annotations

import argparse
from pathlib import Path

from .evidence import build_evidence
from .hashing import sha256_file
from .identifier import extension_signature_status, inspect_ole_container, inspect_signature, inspect_zip_container
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
    for path in iter_files(root, excluded=output):
        try:
            stat = path.stat()
            rule = classify(path, rules)
            signature = inspect_signature(path)
            signature_status = extension_signature_status(path, signature)
            if signature == "ZIP":
                container_type = inspect_zip_container(path)
            elif signature == "OLE":
                container_type = inspect_ole_container(path)
            else:
                container_type = ""
            rows.append({
                "path": str(path.relative_to(root)),
                "size": stat.st_size,
                "sha256": sha256_file(path),
                "format": rule["name"],
                "signature": signature,
                "signature_status": signature_status,
                "container_type": container_type,
                "risk": rule["risk"],
                "reason": rule["reason"],
            })
        except (OSError, PermissionError) as exc:
            errors.append({"path": str(path), "error": type(exc).__name__})
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
