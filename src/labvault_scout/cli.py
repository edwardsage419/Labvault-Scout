from __future__ import annotations

import argparse
from pathlib import Path

from .hashing import sha256_file
from .report import write_reports
from .risk import classify, load_rules
from .scanner import iter_files


def scan(root: Path, output: Path) -> int:
    root = root.expanduser().resolve()
    rules = load_rules()
    rows: list[dict] = []
    errors: list[dict] = []
    for path in iter_files(root):
        try:
            stat = path.stat()
            rule = classify(path, rules)
            rows.append({
                "path": str(path.relative_to(root)),
                "size": stat.st_size,
                "sha256": sha256_file(path),
                "format": rule["name"],
                "risk": rule["risk"],
                "reason": rule["reason"],
            })
        except (OSError, PermissionError) as exc:
            errors.append({"path": str(path), "error": type(exc).__name__})
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
