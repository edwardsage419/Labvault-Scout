# Changelog

## 0.4.1 (patch release pending)

**PREPUBLICATION / 补丁版尚未发布.** v0.4.1 is in review. The currently published stable version remains [v0.4.0](https://github.com/edwardsage419/Labvault-Scout/releases/tag/v0.4.0).

**正式补丁版准备中。** 当前最新公开稳定版仍为 v0.4.0，尚无 v0.4.1 标签或公开 wheel。

### Patch scope / 补丁范围

* Address an observed integrity gap in Bundle verification: a manifest modified during file hashing could result in an incorrect VERIFIED status.
* Revalidate manifest contents and observable file identity before verification completes; report FAILED with ManifestChangedDuringVerification when a change is detected.
* Add regression cases for invalid checksums, different internally valid contents, and same-content file replacement.
* Preserve local offline-first, source-read-only behavior. No scientific format rules or schemas were changed by this fix.

### Candidate evidence / 候选证据

* [PR #17](https://github.com/edwardsage419/Labvault-Scout/pull/17) merged at bb50b81075fb2818c42defbfffea431646125142. [Post-merge CI 42953137318](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42953137318) passed all six matrix jobs.
* Version synchronization in commit 4f4d46a032ad875c54f78acaf643b40ffa629b5f passed [CI 42957754106](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42957754106), all six jobs.
* The exact release commit, public wheel SHA256 and publication date remain pending. Detection remains limited to observable evidence, and independent end-user acceptance remains UNKNOWN.

最终发行物哈希和实际发布日期仍待确定。该修复无法保证检测不留下可观察变化的瞬时替换。独立真实用户验收证据仍为 UNKNOWN。参见 [补丁版发布说明草稿](RELEASE_NOTES_0_4_1.md)。

## 0.4.0 — 2026-11-10

**PUBLISHED / 正式版已发布.** [LabVault Scout v0.4.0](https://github.com/edwardsage419/Labvault-Scout/releases/tag/v0.4.0) is the latest stable release. The frozen historical prerelease v0.4.0rc1 remains available.

**2026-11-10 已公开发布 v0.4.0 稳定正式版。** 历史预发布版 v0.4.0rc1 继续保留。

### Stable contents / 正式版内容

* Strengthened bounded ZIP/ZIP64 structural validation and conservative scientific-format evidence.
* Improved file identity/race protection and malformed scan/compare/bundle report validation.
* The documented D-C01 historical compatibility change remains: some older POSIX schema-1 reports with names such as `C:sample.csv` can be rejected. Preserve original files and reports; rescan safely named copies where necessary.
* Package version and runtime version are `0.4.0`; scanner production logic remains frozen since RC1.

### Verification evidence and limits / 验证证据与限制

* RC1's public wheel passed six-platform offline-install and CLI checks in [CI 42345772714](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42345772714).
* The exact stable tag targets `b5b306b75fd5f416f7d6d8510922b2d8aec15b4f`, which passed [six-platform CI 42814281623](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42814281623).
* [Publication workflow 42815063010](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42815063010) passed draft asset checks and public post-publication download/integrity verification. Official wheel SHA256: `4d66260f0b380fb33d48860b837111e03125e97cc751a58d601a3de52ccb5e63`.
* Independent real-world end-user acceptance remains **UNKNOWN**. Complete compatibility with all historical reports and exhaustive certification of scientific formats are not claimed.

已完成最终提交六平台 CI、官方 wheel 校验、离线安装以及公开发行物下载复验。独立真实用户验收仍为 UNKNOWN。详见 [正式版发布说明](RELEASE_NOTES_0_4_0.md)。

## 0.4.0rc1 (GitHub prerelease, published 2026-11-07)

This candidate was published as a GitHub prerelease on 2026-11-07. The latest published stable release remains v0.3.2. Publication of the prerelease does not authorize the final v0.4.0 release.

2026-11-07 已公开发布 GitHub 预发布版。最新稳定正式版仍为 v0.3.2；预发布版的发布不构成最终 v0.4.0 正式发布授权。

### Changed

* Tightened ZIP and ZIP64 bounded structural validation, including malformed central directory and extra-field metadata.
* Strengthened file identity checks across hashing and read-only format identification for selected scientific containers.
* Tightened schema-1 report validation and packaged JSON Schema constraints.

### Testing

* Expanded deterministic malformed-input, filesystem-error, scan, comparison, report-verification, and bundle regressions.
* Added pinned offline CSV and TSV public sample regressions.
* Exercised actual stable v0.3.2 outputs against candidate verification, bundle, comparison, and schemas on Windows, Linux, and macOS with Python 3.10 and 3.12.

### Known compatibility change

* Historical schema-1 reports generated on POSIX with drive-prefixed relative names such as `C:sample.csv` can be rejected by the candidate. This preserves strict path validation. Keep historical reports intact; rescan a separately named copy when a new candidate report is needed. Other reports violating tightened validation may also be rejected.

See the [published v0.4.0rc1 prerelease](https://github.com/edwardsage419/Labvault-Scout/releases/tag/v0.4.0rc1) and [candidate release notes](RELEASE_NOTES_0_4_0_RC1.md) for exact evidence boundaries and migration guidance.

## 0.3.2 — 2026-10-05

### Fixed

* TIFF/BigTIFF verification now rejects invalid first-IFD offsets before assigning verified structural evidence
* FITS verification now requires valid mandatory value indicators in the bounded primary-header checks
* DICOM Part 10 verification now validates bounded File Meta Information evidence after the `DICM` marker
* FCS verification now rejects inconsistent DATA/ANALYSIS begin/end offset pairs, including invalid FCS 2.0 DATA fallback combinations
* SPSS SAV/ZSAV verification now requires the fixed-header product identifier prefix before assigning verified evidence
* Modern Stata DTA verification now requires the mandatory bounded `<K>...</K>` header marker after the byte-order field

### Changed

* Regression coverage now includes malformed bundle-manifest types, malformed scan/compare report JSON, files disappearing during scanning, and additional scientific-format corruption cases

## 0.3.1 — 2026-10-04

### Fixed

* English and Chinese README now identify v0.3.0 as the stable release instead of directing users to the RC4 candidate
* Package metadata now uses the `Development Status :: 5 - Production/Stable` classifier instead of the stale alpha classifier

## 0.3.0 — 2026-10-04

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
* Regression-hardened scientific-format verification across NIfTI-1, NetCDF, TIFF/BigTIFF, FITS, MATLAB Level 5, DICOM Part 10, FCS, SPSS SAV/ZSAV, and modern Stata DTA

### Changed

* Package version finalized at `0.3.0` after RC4 validation
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
* FITS verification now checks bounded header termination, legal BITPIX values, NAXIS/NAXISn structure, and malformed or missing mandatory cards before assigning high confidence
* MATLAB Level 5 verification now validates the version bytes against the declared `IM` / `MI` byte order
* FCS fixed-header verification now validates primary TEXT bounds and non-zero DATA/ANALYSIS segment ranges without parsing file payloads
* SPSS SAV/ZSAV extension-subtype mismatches remain conservatively unverified, while obvious non-SPSS signature mismatches are routed to `REVIEW_FORMAT`
* Modern Stata DTA verification now distinguishes unsupported releases from malformed release/byteorder headers and keeps legacy or unknown DTA files conservatively unverified

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