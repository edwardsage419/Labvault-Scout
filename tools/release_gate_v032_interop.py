"""CI-only, offline actual v0.3.2 to development interoperability gate.

Requires a local full Git checkout containing STABLE_SHA. Uses synthetic files
and never modifies either source tree. No network access is performed.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile

from jsonschema import Draft202012Validator

STABLE_SHA = "4877a9a8c794ba7d78d229ef395ad7f9d38961c9"
REPO = Path(__file__).resolve().parents[1]


def command(argv: list[str], *, cwd: Path | None = None, env: dict | None = None, expected: int = 0) -> str:
    proc = subprocess.run(argv, cwd=cwd, env=env, text=True, encoding="utf-8",
                          errors="replace", capture_output=True, timeout=90, check=False)
    assert proc.returncode == expected, (
        f"command {argv[0]} {argv[1:3]} returned {proc.returncode}, expected {expected}; "
        f"stdout={proc.stdout[:500]!r}; stderr={proc.stderr[:500]!r}"
    )
    return proc.stdout


def stable_source(target: Path) -> None:
    assert command(["git", "-C", str(REPO), "rev-parse", "--verify", f"{STABLE_SHA}^{{commit}}" ]).strip() == STABLE_SHA
    archive = subprocess.run(["git", "-C", str(REPO), "archive", "--format=tar", STABLE_SHA, "src"],
                             capture_output=True, timeout=90, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        for entry in tar:
            parts = PurePosixPath(entry.name)
            assert not parts.is_absolute() and ".." not in parts.parts
            assert entry.isdir() or entry.isfile(), f"Unexpected archive entry: {entry.name}"
            dest = target.joinpath(*parts.parts)
            if entry.isdir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(entry) as source, dest.open("wb") as out:
                    while data := source.read(1024 * 1024):
                        out.write(data)


def snapshot(path: Path) -> tuple[str, int, int]:
    s = path.stat()
    return hashlib.sha256(path.read_bytes()).hexdigest(), s.st_size, s.st_mtime_ns


def cli(src: Path, cwd: Path, *args: str, expected: int = 0) -> str:
    env = dict(os.environ, PYTHONPATH=str(src / "src"), PYTHONDONTWRITEBYTECODE="1")
    return command([sys.executable, "-c", "from labvault_scout.cli import main; main()", *map(str, args)],
                   cwd=cwd, env=env, expected=expected)


def validate(output: str | Path, schema: Path) -> None:
    payload = json.loads(output.read_text(encoding="utf-8") if isinstance(output, Path) else output)
    spec = json.loads(schema.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(spec)
    Draft202012Validator(spec).validate(payload)


def run() -> None:
    dev = REPO
    with tempfile.TemporaryDirectory(prefix="labvault-v032-interoperability-") as temp:
        work = Path(temp)
        stable = work / "stable-src"
        stable.mkdir()
        stable_source(stable)
        assert "0.3.2" in cli(stable, work, "--version")
        source = work / "input"
        source.mkdir()
        csv = source / "data.csv"
        csv.write_bytes(b"a,b\n1,2\n")
        original = snapshot(csv)
        before, after = work / "old", work / "new"
        cli(stable, work, "scan", str(source), "-o", str(before))
        stable_report = before / "scan.json"
        assert json.loads(cli(stable, work, "verify", str(stable_report), "--json"))["status"] == "VERIFIED"
        assert json.loads(cli(dev, work, "verify", str(stable_report), "--json"))["status"] == "VERIFIED"
        assert json.loads(cli(dev, work, "verify-bundle", str(before), "--json"))["status"] == "VERIFIED"
        assert snapshot(csv) == original

        empty = work / "empty"
        empty.mkdir()
        empty_report = work / "empty-report"
        cli(stable, work, "scan", str(empty), "-o", str(empty_report))
        assert json.loads(cli(dev, work, "verify", str(empty_report / "scan.json"), "--json"))["status"] == "VERIFIED"

        added = source / "added.txt"
        added.write_bytes(b"new\n")
        added_original = snapshot(added)
        cli(stable, work, "scan", str(source), "-o", str(after))
        comparison = work / "comparison"
        cli(dev, work, "compare", str(stable_report), str(after / "scan.json"), "-o", str(comparison))
        assert (comparison / "comparison.json").exists()
        stable_comparison = work / "stable-comparison"
        cli(stable, work, "compare", str(stable_report), str(after / "scan.json"), "-o", str(stable_comparison))
        stable_verify_json = cli(stable, work, "verify", str(after / "scan.json"), "--json")
        schemas = dev / "src" / "labvault_scout" / "schemas"
        validate(stable_comparison / "comparison.json", schemas / "comparison-1.schema.json")
        validate(stable_verify_json, schemas / "verification-1.schema.json")
        assert snapshot(csv) == original and snapshot(added) == added_original

        if os.name == "posix":
            colon = work / "colon"
            colon.mkdir()
            item = colon / "C:sample.csv"
            item.write_bytes(b"a,b\n1,2\n")
            colon_original = snapshot(item)
            colon_report = work / "colon-report"
            cli(stable, work, "scan", str(colon), "-o", str(colon_report))
            old_payload = json.loads((colon_report / "scan.json").read_text(encoding="utf-8"))
            assert "C:sample.csv" in [row["path"] for row in old_payload["files"]]
            rejected = json.loads(cli(dev, work, "verify", str(colon_report / "scan.json"), "--json", expected=2))
            assert rejected["status"] == "INVALID", rejected
            assert snapshot(item) == colon_original
            print("C-01: confirmed intentional POSIX drive-prefix incompatibility")
        print("Actual v0.3.2 CLI interoperability: normal/empty/compare/bundle/schema PASS")


if __name__ == "__main__":
    run()
