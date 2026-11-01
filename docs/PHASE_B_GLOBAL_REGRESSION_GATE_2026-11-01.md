# Phase B global regression gate and public-sample pin

Date: 2026-11-01 UTC
Development branch: `develop-v0.3.0`
Read-only source baseline: `1bbeb7ffb6bc15d42c7f80aaaecb88beb1b2c748`
CI baseline: https://github.com/edwardsage419/Labvault-Scout/actions/runs/41280081767

## Gate status

Phase B is **IN PROGRESS**. The six matrix jobs at the baseline commit completed successfully on Windows, Linux and macOS, each on Python 3.10 and 3.12. The workflow builds and installs a wheel, runs pytest, exercises scan/compare/verify/verify-bundle, and loads packaged JSON schemas and format rules.

This record is a source-to-test audit and release-gate inventory. No new project regression or real-sample scan is claimed here.

## B1. Hash identity, filesystem races, and error propagation

Source reviewed: `hashing.py`, `scanner.py`, `cli.py`, `identifier.py`, `safeio.py`, `bundle.py`, `report.py`.

Existing direct tests: `test_hashing_identity.py`, `test_hash_incomplete_read.py`, `test_scan_disappearing_file.py`, `test_scan_output_disk_full.py`, `test_safeio_cleanup_failure.py`, and `test_bundle_build_race.py`.

Observed defenses:
* Hashing checks the initial path identity, opens with `O_NOFOLLOW` where available, compares descriptor and pathname metadata, checks byte counts, and rejects premature EOF and file growth.
* Scan binds the first hash to the enumerated entry and performs a second hash after format inspection. Changed or disappearing files are recorded as errors instead of complete file rows.
* Bundle verification hashes manifest members with identity checks. Report writes use same-directory temporary files and atomic replacement. Existing tests cover disk-full recovery and interrupted bundle consistency.

**Open risk B-R01, prioritize a project-level reproduction before release:** `cli.scan` reopens a pathname for structural inspection after the first protected hash. For example, `identifier.inspect_zip_container` calls `inspect_signature(path)`, `_zip_directory_preflight(path)` and `zipfile.ZipFile(path)`, each opening by pathname. If a writable scan-root entry is replaced by a symlink after the first hash, these inspection opens can follow the replacement before the final hash rejects the changed identity. The existing final hash protects reported integrity; it does not by itself establish that every intermediate inspection read remains inside the original file identity.

A separate synthetic standard-library probe on Linux/Python 3.13.5 showed that replacing a ZIP pathname with a symlink before a pathname-based ZIP inspection allowed an outside ZIP member name to be read, and a later identity check detected the swap. This is a **primitive-level reproduction**, not an execution of LabVault Scout's complete scanner. It does not establish an observed user-data leak or a successful incorrect report.

Next acceptance test: instrument the actual scanner so the entry is swapped immediately before a ZIP/HDF5/FITS/GZIP pathname inspection; assert no external target read occurs, and assert an explicit file-change error with no accepted file row. Test on the six CI platforms. If reproduced, fix the identity binding of inspection reads without relaxing the bounded parsing or source read-only constraints. Record impact and remediation before marking B-R01 closed.

## B2. Malformed JSON, schema and output behavior

Source reviewed: `compare.py`, `bundle.py`, `schema_registry.py`, four packaged schema files, `cli.py`, `report.py`, and `.github/workflows/tests.yml`.

Existing direct tests include `test_compare_malformed_report.py`, `test_verify_malformed_report.py`, `test_bundle_manifest_types.py`, `test_scan_json_integer_bounds.py`, `test_scan_json_float_bounds.py`, `test_scan_json_real_nesting.py`, `test_scan_json_wide_structures.py`, and `test_core.py` schema contract tests.

Bounded source review confirms duplicate-key rejection, non-finite-number rejection, explicit integer/float token limits for scan reports, schema-1 field/type checks, path canonicalization, bundle-manifest size limits, and stable manifest reads. The six-job CI validates the current suite and packaged resource availability. **Status: BOUNDED PASS for the inspected source/test contracts.** A fresh external JSON Schema validation of every generated output has not been performed in this audit. Other malformed-input and filesystem cases remain on the phase B checklist.

## C1. Public scientific sample pinned for later offline validation

Candidate: Vega Datasets `seattle-weather.csv`, based on public NOAA weather observations, with a derived categorical weather column. Vega's dataset page describes it as a public-domain U.S. Government dataset for instructional use.

* Official dataset description: https://vega.github.io/vega-datasets/datasets/seattle_weather/
* Upstream repository: https://github.com/vega/vega-datasets
* Release tag: `v3.3.1`
* Tag commit: `5448e25297c8f705be78e879d5423d55d04dc6f1`
* Exact file: `data/seattle-weather.csv`
* Git blob SHA-1: `0f38b53bdc1c42c5e5d484f33b9d4d7b229e0e59`
* SHA-256 of retrieved ASCII file bytes: `0845078a290b48e3149ab8639966824110a251db4e06fc144c06ebb534af23be`
* File size: 48,219 bytes; 1,461 data rows; six CSV columns.

The SHA-256 calculation used an independently self-tested SHA-256 implementation on the retrieved text, after confirming the file is ASCII. The upstream tag and exact commit returned the same file size. The dataset is **pinned and source-checked**. A formal LabVault Scout scan has **not** been run.

Expected bounded scanner behavior from the current rules: extension rule `CSV`, risk label `SAFE`, and extension-rule confidence `MEDIUM` when no structural signature is present. This is an extension-based preservation-risk assessment, not validation of CSV cell contents.

Next C acceptance: obtain these exact bytes in an isolated workspace, verify SHA-256 before scanning, run scan/verify/verify-bundle twice offline, check deterministic report fields, record any false classification, and preserve the source file unchanged. Keep external network access out of CI and production scans.

## D1. Release candidate readiness inventory

At the baseline comparison, `develop-v0.3.0` is 334 commits ahead of `main` and zero behind, with 78 changed files. `pyproject.toml` still declares `0.3.2`, the stable release version. Release candidate versioning, complete compatibility review, real-sample results, and frozen six-job verification remain pending.

**Release gate: NOT READY.** Resolve or explicitly bound B-R01; complete remaining B module checks; validate pinned public samples offline; review the development diff and version metadata; run all six jobs on a frozen candidate. No main change, PR merge, or Release is authorized by this record.
