# ZIP/ZIP64 phase A risk closure and phase B handoff

Date: 2026-11-01 UTC
Branch: develop-v0.3.0
Evidence baseline: 39be6a0d171ea36ff3fbdcaba3cfc62e75e88680
CI baseline: https://github.com/edwardsage419/Labvault-Scout/actions/runs/41272354082

## Decision

**Close active ZIP/ZIP64 field-combination expansion and proceed to global regression (phase B).**

This is a bounded, risk-based closure. It is not an exhaustive proof for all ZIP archives or all ZIP64 field subsets. Reopen this area on a reproducible false acceptance, false rejection, data-integrity defect, or security issue.

## Source and regression evidence

Source: `src/labvault_scout/identifier.py`, particularly `_zip_directory_preflight`. The preflight bounds EOCD search, central directory bytes and entries, validates declared versus actual directory record boundaries, checks member ZIP64 extra-field lengths and order, checks local-header association, and rejects unsupported multi-disk metadata. Classification follows these checks. Inspection reads source files without extraction or execution.

| Risk family | Direct evidence in tests | Status |
| --- | --- | --- |
| ZIP64 member fields: individual size sentinels, offset and disk start | `test_zip64_central_single_sentinel.py`, `test_zip64_central_offset.py`, `test_zip64_central_disk_start.py` | Covered by targeted tests |
| ZIP64 central paired fields and mixed ordinary extras | `test_zip64_central_two_required_fields.py`, `test_zip64_central_two_sizes_middle_comment.py`, `test_zip64_central_uncompressed_offset_fields.py`, three `*_disk_middle.py` files | Covered by targeted tests |
| ZIP64 central triple fields | `test_zip64_central_two_sizes_disk_middle.py`, `test_zip64_central_compressed_offset_disk_middle.py` | Selected combinations covered; remaining subsets not exhaustively enumerated |
| All four central sentinel fields | `test_zip64_central_all_sentinels.py` | Covered by targeted tests |
| Invalid extra length, duplicate ZIP64 tags, opaque ordinary extras | `test_zip64_central_duplicate_sentinel.py`, `test_zip64_central_mixed_malformed_extra.py`, `test_zip64_central_opaque_ordinary_extra.py` | Covered by targeted tests |
| Directory bounds, EOCD comment and entry counts, local member linkage | `test_zip_directory_limits.py`, `test_zip64_streaming_member_association.py`, `test_zip64_three_member_middle_comment.py` | Covered by targeted tests |
| Read-only and deterministic rejection of malformed ZIP | Assertions in the above regression families | Covered for selected fixtures |

A proposed extra three-field case (uncompressed size, local offset, disk start) has only an independent synthetic audit as of this baseline. Its scanner expectations are not CI-validated. The generic sentinel-dependent parser, overlapping pair tests and four-sentinel test reduce the priority of adding another near-identical fixture. Revisit only if an independently reproducible defect or distinct failure mechanism emerges.

## CI evidence

At the baseline commit, GitHub Actions `tests` run `41272354082` completed successfully in all six jobs:

* Ubuntu, Python 3.10: success
* Ubuntu, Python 3.12: success
* Windows, Python 3.10: success
* Windows, Python 3.12: success
* macOS, Python 3.10: success
* macOS, Python 3.12: success

The Ubuntu Python 3.12 log reports `1287 passed, 3 skipped`. This validates the repository test suite and the workflow's wheel build, wheel install, CLI smoke scan, scan/compare/verify/verify-bundle, and packaged resource checks. It does not establish real-world sample compatibility.

## Phase B global regression inventory

| Area | Existing test or workflow evidence | Remaining acceptance work |
| --- | --- | --- |
| Hash identity, incomplete reads, TOCTOU, disappearing files | `test_hashing_identity.py`, `test_hash_incomplete_read.py`, `test_scan_disappearing_file.py` | Inspect source and failure propagation; record bounded PASS or reproducible defect |
| Path, filesystem errors, atomic output | `test_scan_non_utf8_paths.py`, `test_scan_output_disk_full.py`, `test_safeio_*.py` | Inspect path and cleanup semantics |
| Malformed scan/compare/verify/bundle JSON and schema | `test_verify_malformed_report.py`, `test_compare_malformed_report.py`, `test_bundle_manifest_types.py`, `test_scan_json_*.py` | Compare runtime validation against packaged schemas |
| Scientific-format bounded structural evidence | `test_core.py`, `test_dicom_file_meta.py`, `test_fcs_offset_pairs.py`, `test_fits_value_indicator.py`, `test_stata_k_header.py`, `test_tiff_ifd_offset.py` | Select public small real-world samples for independent validation |
| Wheel, CLI and packaged resources | `.github/workflows/tests.yml` | Full release-candidate verification on a frozen candidate |

## Release candidate gates

1. Complete phase B source-to-test risk audit and record any confirmed blockers.
2. Validate a small legal, public, version-pinned, hashed, non-sensitive real scientific sample set offline. Keep CI network independent.
3. Review the full development diff against stable v0.3.2. Baseline comparison reports 333 commits ahead, zero behind, 77 changed files.
4. Verify release documentation, compatibility and version metadata. Baseline `pyproject.toml` remains at `0.3.2`; candidate versioning is unresolved.
5. Re-run all six jobs on the frozen release candidate and report a release-readiness decision.

No modification of `main`, PR merge, or Release is authorized by this document. Preserve MIT licensing, offline operation, read-only scans, and zero-cost deployment.
