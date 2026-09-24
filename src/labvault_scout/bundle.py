from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

from . import __version__
from .hashing import sha256_file

BUNDLE_SCHEMA_VERSION = "1"
BUNDLE_MANIFEST_NAME = "bundle_manifest.json"
BUNDLE_FILES = (
    "scan.json",
    "files.csv",
    "duplicates.csv",
    "migration_plan.csv",
    "report.html",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def manifest_payload_sha256(payload: dict) -> str:
    """Return a deterministic checksum excluding the manifest checksum field."""
    clean = dict(payload)
    clean.pop("manifest_sha256", None)
    encoded = json.dumps(
        clean,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_bundle_manifest(output_dir: Path) -> dict:
    """Build a deterministic manifest for the core report artifacts."""
    entries = []
    for name in sorted(BUNDLE_FILES):
        path = output_dir / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Report artifact is not a regular file: {name}")
        stat = path.stat()
        entries.append({
            "path": name,
            "size": stat.st_size,
            "sha256": sha256_file(path),
        })

    payload = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "tool": {"name": "LabVault Scout", "version": __version__},
        "algorithm": "sha256",
        "files": entries,
    }
    payload["manifest_sha256"] = manifest_payload_sha256(payload)
    return payload


def write_bundle_manifest(output_dir: Path) -> dict:
    payload = build_bundle_manifest(output_dir)
    (output_dir / BUNDLE_MANIFEST_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def _canonical_manifest_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("Bundle manifest path must be a non-empty string")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value != path.as_posix():
        raise ValueError(f"Unsafe bundle manifest path: {value}")
    if value == "." or value == BUNDLE_MANIFEST_NAME:
        raise ValueError(f"Invalid bundle manifest member: {value}")
    return value


def load_bundle_manifest(output_dir: Path) -> dict:
    manifest_path = output_dir / BUNDLE_MANIFEST_NAME
    if manifest_path.is_symlink():
        raise ValueError("Bundle manifest must not be a symlink")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read bundle manifest: {manifest_path}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Bundle manifest must be a JSON object")
    required = {"schema_version", "tool", "algorithm", "files", "manifest_sha256"}
    actual_fields = set(payload)
    missing = sorted(required - actual_fields)
    extra = sorted(actual_fields - required)
    if missing:
        raise ValueError(f"Bundle manifest is missing fields: {', '.join(missing)}")
    if extra:
        raise ValueError(f"Bundle manifest has invalid top-level fields: {', '.join(extra)}")
    if payload["schema_version"] != BUNDLE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported bundle manifest schema: {payload['schema_version']}")
    if payload["algorithm"] != "sha256":
        raise ValueError("Unsupported bundle manifest algorithm")
    tool = payload["tool"]
    if (
        not isinstance(tool, dict)
        or set(tool) != {"name", "version"}
        or tool.get("name") != "LabVault Scout"
        or not isinstance(tool.get("version"), str)
        or not tool["version"]
    ):
        raise ValueError("Invalid bundle manifest tool metadata")
    if not isinstance(payload["files"], list):
        raise ValueError("Bundle manifest files must be a list")
    checksum = payload["manifest_sha256"]
    if not isinstance(checksum, str) or not SHA256_RE.fullmatch(checksum):
        raise ValueError("Invalid bundle manifest checksum")
    if manifest_payload_sha256(payload) != checksum:
        raise ValueError("Bundle manifest checksum mismatch")

    seen = set()
    for entry in payload["files"]:
        if not isinstance(entry, dict):
            raise ValueError("Bundle manifest contains a non-object file entry")
        if set(entry) != {"path", "size", "sha256"}:
            raise ValueError("Bundle manifest file entry has invalid fields")
        member = _canonical_manifest_path(entry["path"])
        if member in seen:
            raise ValueError(f"Duplicate bundle manifest path: {member}")
        seen.add(member)
        if not isinstance(entry["size"], int) or isinstance(entry["size"], bool) or entry["size"] < 0:
            raise ValueError(f"Invalid bundle manifest size: {member}")
        if not isinstance(entry["sha256"], str) or not SHA256_RE.fullmatch(entry["sha256"]):
            raise ValueError(f"Invalid bundle manifest SHA-256: {member}")

    if seen != set(BUNDLE_FILES):
        missing_members = sorted(set(BUNDLE_FILES) - seen)
        extra_members = sorted(seen - set(BUNDLE_FILES))
        detail = []
        if missing_members:
            detail.append(f"missing {', '.join(missing_members)}")
        if extra_members:
            detail.append(f"unexpected {', '.join(extra_members)}")
        raise ValueError("Bundle manifest members differ from expected set: " + "; ".join(detail))
    return payload


def verify_bundle(output_dir: Path) -> dict:
    """Verify all core report artifacts against the packaged manifest."""
    payload = load_bundle_manifest(output_dir)
    problems = []
    for entry in payload["files"]:
        member = entry["path"]
        path = output_dir.joinpath(*PurePosixPath(member).parts)
        if path.is_symlink():
            problems.append({"path": member, "issue": "SYMLINK"})
            continue
        if not path.exists():
            problems.append({"path": member, "issue": "MISSING"})
            continue
        if not path.is_file():
            problems.append({"path": member, "issue": "NOT_REGULAR_FILE"})
            continue
        actual_size = path.stat().st_size
        if actual_size != entry["size"]:
            problems.append({
                "path": member,
                "issue": "SIZE_MISMATCH",
                "expected": entry["size"],
                "actual": actual_size,
            })
            continue
        actual_hash = sha256_file(path)
        if actual_hash != entry["sha256"]:
            problems.append({
                "path": member,
                "issue": "SHA256_MISMATCH",
                "expected": entry["sha256"],
                "actual": actual_hash,
            })

    return {
        "status": "VERIFIED" if not problems else "FAILED",
        "exit_code": 0 if not problems else 2,
        "schema_version": payload["schema_version"],
        "checked_files": len(payload["files"]),
        "manifest_sha256": payload["manifest_sha256"],
        "tool": payload["tool"],
        "problems": problems,
    }
