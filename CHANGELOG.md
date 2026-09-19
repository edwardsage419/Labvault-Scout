# Changelog

## Unreleased 0.3.0

Development continues on `develop-v0.3.0`. See `ROADMAP_0_3_0.md`.

### Added

* Self-describing `scan.json` metadata with report schema and tool version
* CLI `--version`
* Compound-extension matching with initial `.nii.gz` NIfTI coverage

### Changed

* Development package version advances to `0.3.0.dev0`

## 0.2.0 — 2026-09-19

### Added

* Conservative derivative file-family relationships with EXACT and DERIVATIVE strength
* Machine-readable priority reasons and recommended preservation actions
* OpenDocument, HDF5 superblock, RO-Crate, and BagIt structural evidence
* Bounded positive priority credit for recognized preservation packages
* Thousand-file directory scale coverage

### Changed

* Structural container warnings add preservation priority and recommend `REVIEW_CONTAINER`
* SHA-256 hashing and the 512-byte identification header are collected in one sequential file read
* HDF5 and OLE structural checks reuse the shared bounded header

### Fixed

* Runtime `__version__` now matches package metadata
* Scan error paths remain relative to the source root
* Output paths outside the source no longer exclude the entire scan; using the scan root itself as output is rejected
* Scanner traversal skips non-regular filesystem entries
* Same-directory relationship matching preserves actual directory identity
* OpenDocument `mimetype` inspection uses a bounded read
* HDF5 signatures after specification-defined user blocks are recognized
* OOXML files require matching internal structure before receiving verified/high-confidence evidence
* Build metadata now requires setuptools 77+ for SPDX license metadata and ships the complete standard MIT license
* Duplicate test names were removed so all intended regressions are collected
* CITATION.cff now includes required CFF 1.2.0 authors metadata
* Empty ZIP archives are recognized as ZIP instead of being marked unverified
* Generic OLE evidence for `.xls` no longer claims high-confidence Excel identification
* Directory traversal and file-metadata failures are reported instead of being silently skipped

## 0.1.0

Initial MVP release candidate.

### Added

* Recursive read-only directory inventory
* SHA-256 hashing
* Exact duplicate grouping and `duplicates.csv` export
* Non-fatal scan error recording
* Conservative same-directory, same-stem open-copy detection
* ZIP, OLE, HDF5, and PDF signature evidence
* Safe ZIP OOXML and bounded OLE container inspection
* Evidence summaries and confidence labels
* Transparent preservation priority scoring
* Prioritized `migration_plan.csv` export
* Extension-based scientific format rules
* SAFE, WATCH, RESCUE, and UNKNOWN triage levels
* HTML, CSV, and JSON report generation
* Cross-platform CI
* English and Chinese documentation
