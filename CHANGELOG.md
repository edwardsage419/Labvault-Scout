# Changelog

## Unreleased 0.3.0

Development continues on `develop-v0.3.0`. See `ROADMAP_0_3_0.md`.

### Added

* Self-describing `scan.json` metadata with report schema, tool version, hash/path semantics, and a deterministic preservation-rule fingerprint
* Project-level JSON summary for file bytes, scan errors, risk/priority counts, open copies, duplicate groups, and a deterministic inventory SHA-256 fingerprint
* Offline `compare` command for added, removed, moved, content-changed, and assessment-changed files
* Deterministic `comparison.json`, `changes.csv`, and `comparison.html` outputs
* Explicit priority escalation/de-escalation direction and score deltas in repeated-scan comparisons
* Aggregate comparison deltas for file count, total bytes, risk counts, and priority counts
* Rule-context comparison (`SAME`, `CHANGED`, or `UNKNOWN`) so assessment drift can be distinguished from content drift
* Embedded report integrity validation (`VERIFIED`, `MISMATCH`, or `UNKNOWN`) covering inventory fingerprint and summary consistency
* Deterministic full-report SHA-256 checksum covering tool/schema metadata, provenance, summaries, file records, and errors
* `bundle_manifest.json` with SHA-256/size records for all core report artifacts
* `verify-bundle` command with human-readable and `--json` output
* Packaged Draft 2020-12 JSON Schema for the bundle manifest
* Optional `compare --exit-code` automation mode: 0=no changes, 1=changes, 2=partial comparison
* Thousand-file repeated-scan comparison regression coverage without timing thresholds
* Comparison output is marked `PARTIAL` when either source scan contains recorded errors
* Unsupported future scan schemas mark comparisons as `PARTIAL` instead of silently assuming compatibility
* Comparisons become `PARTIAL` when a source report's embedded inventory fingerprint validation fails
* CLI `--version`
* Standalone `verify` command for scan-report integrity and schema compatibility checks
* `verify --json` machine-readable output for local scripts and preservation workflows
* Packaged Draft 2020-12 JSON Schemas for scan, comparison, and verification outputs
* `schema` CLI command to print packaged schemas without external dependencies
* Unsupported scan schema takes precedence over checksum status in standalone verification
* Version-aware strict validation for schema 1 report structure, relative paths, SHA-256 fields, sizes, priorities, provenance, and errors
* Schema 1 runtime validation now rejects additional properties and invalid summary field types to match the packaged JSON Schema
* Concise CLI errors with exit code 2 for malformed compare/verify inputs instead of tracebacks
* Compound-extension matching with `.nii.gz` NIfTI coverage
* Bounded NIfTI-1 header evidence for both `.nii` and `.nii.gz` using the standard 348-byte header and magic field
* Bounded NetCDF CDF-1/CDF-2/CDF-5 header evidence for `.nc`
* Bounded classic TIFF and BigTIFF header evidence for `.tif` / `.tiff`
* Bounded FITS primary-header evidence with mandatory keyword order and 2880-byte block checks
* Bounded MATLAB Level 5 MAT-file header evidence with endian-marker validation
* Bounded DICOM Part 10 preamble/`DICM` marker evidence without parsing patient metadata
* Bounded Flow Cytometry Standard 2.0/3.0/3.1/3.2 fixed 58-byte HEADER evidence
* Bounded ASCII-based SPSS SAV (`$FL2`) and ZSAV (`$FL3`) 176-byte fixed-header evidence
* `.zsav` statistical-data rule with conservative RESCUE triage
* Bounded structural evidence for modern Stata DTA releases 117/118/119 using the tagged header and declared byte order

### Changed

* Post-rc2 development package version advances to `0.3.0rc3.dev0`
* Schema 1 report paths now reject NUL characters, absolute paths, parent traversal, dot segments, duplicate `/` separators, and trailing `/`; literal backslashes remain valid filename characters on POSIX systems
* Bundle manifest paths now reject embedded NUL characters explicitly
* Files that change size or modification time during hashing are recorded as `FileChangedDuringScan` instead of producing inconsistent size/hash records
* Report integrity verification now recomputes `open_copy_count` and `duplicate_group_count` in addition to existing summary checks
* Expected `scan` CLI input errors now return a concise message and exit code 2 instead of a Python traceback
* Non-UTF-8 scan reports and bundle manifests now fail with concise `INVALID`/exit-code-2 CLI results instead of decode tracebacks
* Scan and comparison output filesystem errors now return concise exit-code-2 CLI errors instead of tracebacks
* Scientific-format rules are validated for structure, normalized extensions, allowed risks, export lists, and duplicate extensions before use
* Packaged scan JSON Schema path constraints now match runtime `relative-posix` validation, including the special root error path `.`
* Explicit `schema_version` values must be non-empty strings; numeric values are rejected instead of being coerced
* File-change detection now checks device/inode identity, size, mtime, and ctime before and after hashing and again after bounded container inspection
* Directory and file traversal order is deterministic for more stable report diffs
* Reported relative paths use POSIX `/` separators on every supported operating system
* Move detection requires the matching SHA-256 to be globally unique in both source reports
* Pre-schema v0.2 Windows backslash paths are normalized for cross-platform comparison; ambiguous normalization collisions are rejected
* NetCDF-4/HDF5 containers remain conservative `container-only` evidence unless NetCDF-specific structure is proven
* HDF5-based `.mat` files remain conservative `container-only` evidence unless MATLAB-specific structure is proven
* FITS `SIMPLE=F` is treated as nonconforming structural evidence and routed to `REVIEW_CONTAINER`

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
