from pathlib import Path

from labvault_scout.cli import scan


def test_verify_bundle_reports_io_error_if_artifact_file_check_fails(
    tmp_path: Path, monkeypatch
) -> None:
    import labvault_scout.bundle as bundle_module

    source = tmp_path / "source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n", encoding="utf-8")
    output = tmp_path / "report"
    scan(source, output)

    target = output / "report.html"
    original_is_file = Path.is_file

    def unreadable_is_file(path: Path) -> bool:
        if path == target:
            raise PermissionError("denied")
        return original_is_file(path)

    monkeypatch.setattr(Path, "is_file", unreadable_is_file)

    result = bundle_module.verify_bundle(output)

    assert result["status"] == "FAILED"
    assert result["exit_code"] == 2
    assert {
        "path": "report.html",
        "issue": "IO_ERROR",
        "error": "PermissionError",
    } in result["problems"]
