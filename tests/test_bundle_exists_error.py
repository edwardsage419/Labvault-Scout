from pathlib import Path

from labvault_scout.cli import scan


def test_verify_bundle_reports_io_error_if_artifact_exists_check_fails(
    tmp_path: Path, monkeypatch
) -> None:
    import labvault_scout.bundle as bundle_module

    source = tmp_path / "source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "report"
    scan(source, output)

    target = output / "report.html"
    original_exists = Path.exists

    def unreadable_exists(path: Path) -> bool:
        if path == target:
            raise PermissionError("denied")
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", unreadable_exists)

    result = bundle_module.verify_bundle(output)

    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert {
        "path": "report.html",
        "issue": "IO_ERROR",
        "error": "PermissionError",
    } in result["problems"]
