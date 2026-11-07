# Release candidate audit: stable v0.3.2 report compatibility

Date: 2026-11-01 UTC
Scope: source-level comparison of `main` (stable v0.3.2, `4877a9a8c794ba7d78d229ef395ad7f9d38961c9`) with `develop-v0.3.0` (`51c0df8c6d5d104fb90e7b850c9b8ab8364c3eb5`).
CI baseline: https://github.com/edwardsage419/Labvault-Scout/actions/runs/41345609529 (six matrix jobs succeeded on that exact development SHA).
Status: **COMPATIBILITY REVIEW OPEN; RELEASE NOT READY.**
This is a source/schema audit. No historical v0.3.2-generated report was executed through the new loader in this audit.

## Findings

| ID | Stable v0.3.2 behavior | Development behavior | Release impact |
| --- | --- | --- | --- |
| C-01 | On POSIX, the stable scanner can emit a schema-1 file path such as `C:sample.csv`, since `Path.relative_to(root).as_posix()` preserves the colon and stable `_validate_report_path` does not reject drive-prefixed strings. | Current `_validate_report_path`, scan path handling, and packaged schema reject `^[A-Za-z]:`. The current test `test_schema1_windows_paths.py` explicitly checks fail-closed behavior. | **Confirmed source-level historical compatibility break for this unusual but legal POSIX filename.** A previously accepted, checksum-consistent schema-1 report may now fail loading or integrity verification. Needs an explicit release compatibility decision and regression evidence. |
| C-02 | Stable schema and runtime accept zero-valued or unknown-key entries in summary `risk_counts` and `priority_counts`. | Current schema and runtime require recognized keys and strictly positive counts. | Schema-1 acceptance is narrower. Stable `build_summary` only increments observed risk/priority categories, so a normal stable scanner-generated report should not contain zero-valued categories. Treat as contract tightening; verify with historical fixtures before claiming full backward compatibility. |
| C-03 | Stable scan schema has no conditional cross-field constraints on empty inventories and error counts. | Development schema adds consistency conditions for empty/nonempty file and error arrays, count maps, and single-file duplicate groups. | Likely excludes internally inconsistent documents. Verify representative stable reports and error-bearing reports; no historical generator regression is established by this audit. |
| C-04 | Stable comparison and verification schemas use less restrictive combinations of status and metrics. | Development schemas add conditional status/integrity and change-count consistency requirements. | Validate stable-generated comparison and verification JSON against the development schemas before claiming interoperability. |
| C-05 | `pyproject.toml` remains `0.3.2` on both branches; README and CHANGELOG identify v0.3.2 as stable. | Development has changed behavior and many additional regression tests under the same package version. | **Version metadata must be resolved before any candidate release.** Do not publish changed code under the existing stable release identity. |

## Evidence and scope

1. Stable source: `src/labvault_scout/cli.py` emits `path.relative_to(root).as_posix()`; `src/labvault_scout/compare.py` validates POSIX path structure without a drive-prefix check. Development adds `^[A-Za-z]:` rejection in the scanner and report validator.
2. Both stable and development `src/labvault_scout/report.py:build_summary` construct risk/priority maps by counting observed rows, starting from empty maps. This bounds the practical impact of C-02 for normal scanner-generated reports.
3. Three packaged schema-1 files changed: `scan-1.schema.json`, `comparison-1.schema.json`, `verification-1.schema.json`. `bundle-manifest-1.schema.json` was unchanged in the branch comparison.
4. `tests/test_public_seattle_weather_sample.py` provides a pinned, offline CSV regression in the development CI. It does not test cross-version report compatibility.
5. The six-job CI success on `51c0df8c` establishes current-suite regression success. It does not prove that every valid historical stable report remains accepted.

## Acceptance plan

1. Preserve the current fail-closed treatment of ambiguous drive-prefixed paths pending an explicit compatibility policy. Do not silently weaken pathname validation to make a historical fixture pass.
2. Produce at least one genuine report using the stable v0.3.2 tag, then run the development `load_scan_report`, `verify`, and `compare` against it. Include empty, normal, error-bearing, and POSIX drive-prefix cases when the platform supports them. Keep generated fixtures synthetic, local, and network independent.
3. For C-01, decide whether the next release documents an intentional incompatibility, offers a safe read-only historical import path with explicit provenance, or changes the report schema version. Any compatibility exception requires its own security review and regression tests.
4. Validate representative stable comparison/verification outputs against the development schemas and record exact results. Separate schema-only validation from runtime CLI verification.
5. Resolve candidate version metadata, release notes, and the remaining phase-B/phase-C gates. Re-run all six CI jobs at the frozen candidate SHA before a release-readiness recommendation.

No main modification, PR merge, release creation, additional service, or change to the project's offline/read-only safety contract is authorized by this audit.
