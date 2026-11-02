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


def cli(src: Path, cwd: Path, *args: str, expected: int = 0,
        inject_read_error: bool = False) -> str:
    env = dict(os.environ, PYTHONPATH=str(src / "src"), PYTHONDONTWRITEBYTECODE="1")
    script = "from labvault_scout.cli import main; main()"
    if inject_read_error:
        # Fault injection runs inside the actual stable CLI subprocess.
        # Source files remain untouched; the simulated OS error is explicit.
        script = (
            "from labvault_scout import cli as app\n"
            "original = app.sha256_with_head\n"
            "def injected(path):\n"
            "    if path.name == 'blocked.csv':\n"
            "        raise PermissionError('injected read failure')\n"
            "    return original(path)\n"
            "app.sha256_with_head = injected\n"
            "app.main()\n"
        )
    return command([sys.executable, "-c", script, *map(str, args)],
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

        # Actual stable CLI creates an error-bearing report under deterministic
        # injected read failure. This is a simulated OS error, not a real permission
        # denial; the scanner, report writer, and verifier are the real v0.3.2 code.
        error_source = work / "error-input"
        error_source.mkdir()
        healthy = error_source / "healthy.csv"
        blocked = error_source / "blocked.csv"
        healthy.write_bytes(b"a,b\n1,2\n")
        blocked.write_bytes(b"a,b\n3,4\n")
        healthy_original, blocked_original = snapshot(healthy), snapshot(blocked)
        error_report_dir = work / "error-report"
        cli(stable, work, "scan", str(error_source), "-o", str(error_report_dir),
            inject_read_error=True)
        error_report = error_report_dir / "scan.json"
        error_payload = json.loads(error_report.read_text(encoding="utf-8"))
        assert [row["path"] for row in error_payload["files"]] == ["healthy.csv"]
        assert error_payload["errors"] == [{"path": "blocked.csv", "error": "PermissionError"}]
        assert error_payload["summary"]["error_count"] == 1
        stable_error_verification = json.loads(cli(stable, work, "verify", str(error_report), "--json"))
        dev_error_verification = json.loads(cli(dev, work, "verify", str(error_report), "--json"))
        assert stable_error_verification["status"] == "VERIFIED"
        assert dev_error_verification["status"] == "VERIFIED"
        assert dev_error_verification["error_count"] == 1
        validate(json.dumps(stable_error_verification), schemas / "verification-1.schema.json")
        assert json.loads(cli(dev, work, "verify-bundle", str(error_report_dir), "--json"))["status"] == "VERIFIED"
        assert snapshot(healthy) == healthy_original and snapshot(blocked) == blocked_original
        print("D-C02: actual stable CLI error-bearing report accepted by development (injected PermissionError)")
        print(json.dumps({
            "gate": "v0.3.2-interop",
            "stable_sha": STABLE_SHA,
            "development_sha": command(["git", "-C", str(REPO), "rev-parse", "HEAD"]).strip(),
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "report_sha256": {
                "normal": hashlib.sha256(stable_report.read_bytes()).hexdigest(),
                "empty": hashlib.sha256((empty_report / "scan.json").read_bytes()).hexdigest(),
                "error_injected": hashlib.sha256(error_report.read_bytes()).hexdigest(),
            },
            "error_count": error_payload["summary"]["error_count"],
            "source_snapshots_unchanged": True,
            "error_mode": "injected PermissionError during stable SHA256 read",
        }, sort_keys=True))

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
