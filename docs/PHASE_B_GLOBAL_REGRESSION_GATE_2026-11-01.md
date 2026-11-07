# Phase B bounded exit and Phase C public-sample acceptance

Date: 2026-11-01 UTC
Development branch: `develop-v0.3.0`
Reviewed code baseline: `1b4d63dcc305bf0361c4e3b2b1603ecd37245cfd`
Verified six-job CI: https://github.com/edwardsage419/Labvault-Scout/actions/runs/41355703162
Stable baseline: `main`, `4877a9a8c794ba7d78d229ef395ad7f9d38961c9`

## Decision and evidence boundary

**Phase B: BOUNDED PASS.** The release-oriented regression checklist below is covered by the current source, existing tests and a successful six-platform CI run. End proactive expansion of Phase B input combinations. Reopen only for a reproducible high-priority defect, regression, or changed product contract.

**Phase C: BOUNDED PASS for two pinned public tabular research datasets.** Both fixed-byte fixtures are tested with the real scanner offline on Windows, Linux and macOS, Python 3.10 and 3.12. End active tabular-sample expansion. This does not demonstrate real-world accuracy for every supported scientific container or format.

**Phase D: NOT READY.** Historical v0.3.2 report interoperability and candidate version metadata remain release gates. Neither a main merge nor a release is authorized.

This is a bounded acceptance record. The matrix CI exercises the checked-in project tests and installed wheel; it is not a formal proof of absence of future edge cases. The baseline `PHASE_B_GLOBAL_REGRESSION_GATE_2026-11-01.md` previously identified B-R01 as open; the current evidence supersedes that historical state.

## B: release-oriented regression matrix

| Gate | Evidence at reviewed baseline | Result / limit |
| --- | --- | --- |
| B1 hash identity, replacement and nonregular files | `tests/test_hashing_identity.py`, `tests/test_hash_incomplete_read.py`, `tests/test_scan_disappearing_file.py`, `tests/test_bundle_build_race.py`; ZIP, HDF5, FITS, GZIP/NIfTI inspections use verified file streams. Issue #12 closed at 2026-11-01 19:09 UTC. | PASS for specified race and failure scenarios; no claim about every filesystem or adversarial scheduling. |
| B2 filesystem, path, and write failures | `tests/test_safeio_cleanup_failure.py`, `tests/test_scan_output_disk_full.py`, `tests/test_scan_non_utf8_paths.py`, `tests/test_schema1_windows_paths.py`, `tests/test_scan_unicode_traversal_errors.py`; current CI passed. | PASS for tested error propagation and atomicity. Intentional drive-prefix rejection has historical report compatibility impact C-01, tracked under D. |
| B3 malformed input and schema 1 | `tests/test_verify_malformed_report.py`, `tests/test_compare_malformed_report.py`, `tests/test_scan_json_integer_bounds.py`, `tests/test_scan_json_float_bounds.py`, `tests/test_bundle_manifest_types.py`, `tests/test_schema_version_unicode.py`. | PASS for covered runtime parser and schema contracts. External JSON Schema validators can differ from stricter integer-token runtime checks documented in `docs/SCHEMAS.md`. |
| B4 scan / compare / verify / bundle | CI `CLI smoke scan` builds two scans, verifies a report and bundle, performs comparison and checks output artifacts; project tests cover partial/error and race behavior. | PASS on six CI jobs. |
| B5 deterministic reporting and rules | `tests/test_public_seattle_weather_sample.py` and `tests/test_public_unemployment_tsv_sample.py` compare two real scanner outputs byte-semantically through loaded report equality; `tests/test_core.py` and compare tests cover report/inventory checksums. | PASS for fixed fixtures and tested contracts; no universal determinism guarantee. |
| B6 bounded structural identification | `tests/test_core.py` plus existing scientific-format and ZIP64 regressions; `docs/ZIP64_PHASE_A_EXIT_2026-11-01.md` records the prior A exit. | PASS for supported bounded evidence. Format classification remains conservative, with explicit unverified/container-only states. |
| B7 wheel, CLI, packaged resources | Six CI jobs build a wheel, install it, run `pip check`, pytest, CLI help, scan, verify, verify-bundle, compare, and load four packaged JSON Schemas and format rules. | PASS on Windows/Linux/macOS × Python 3.10/3.12 at the exact reviewed SHA. |

CI run `41355703162` completed successfully on all six jobs and matches the reviewed branch HEAD. Job results and steps were independently re-read. Source files were not modified during this gate review.

## C: pinned public research samples

| Sample | Pinned upstream | Bytes / SHA-256 | Formal scanner evidence | Limit |
| --- | --- | --- | --- | --- |
| Seattle weather CSV | `vega/vega-datasets` tag `v3.3.1`, `data/seattle-weather.csv` | 48,219; `0845078a290b48e3149ab8639966824110a251db4e06fc144c06ebb534af23be` | `tests/test_public_seattle_weather_sample.py`: two offline scans, report equality, `SAFE`/`MEDIUM`, verify, verify-bundle, compare, original content and mtime unchanged. | NOAA-derived teaching data, with a derived categorical field; CSV classification uses extension evidence, not semantic validation. |
| County unemployment TSV | `vega/vega-datasets` tag `v3.3.1`, `data/unemployment.tsv` | 34,739; `f82bff0a9745cc9e9997c0b83a02ecc77cea7b1d6acbbc4b404bff293e95bb6e` | `tests/test_public_unemployment_tsv_sample.py`: two offline scans, report equality, `SAFE`/`MEDIUM`, verify, verify-bundle, compare, original content and mtime unchanged. | Historical BLS-derived transformed data; TSV classification uses extension evidence. |

Both fixtures are checked into `tests/fixtures/`; `.gitattributes` preserves their exact bytes on Windows. Neither test downloads data or executes source-file code. The upstream descriptions identify these as U.S. Government public-domain derived data. Both samples are tabular and originate from the same dataset repository; independent non-tabular real-data accuracy remains outside this bounded acceptance.

## D: remaining release gates and decision order

1. **D-C01, historical path compatibility:** stable v0.3.2 on POSIX can emit a schema-1 file path such as `C:sample.csv`; development rejects drive-prefixed paths as unsafe. The current synthetic stable-contract tests explicitly confirm rejection. Keep the fail-closed safety behavior while deciding and documenting the intended compatibility break or a separately reviewed safe migration strategy. Do not silently relax path validation.
2. **D-C02–C04, historical output interoperability:** current synthetic v0.3.2 schema-1 scan reports cover empty, ordinary and error-bearing cases. An actual report emitted by executing the stable v0.3.2 release has not yet been run through development `load_scan_report`, `verify` and `compare`. Stable-generated comparison and verification outputs also need bounded schema/runtime acceptance evidence.
3. **D-C05, version and release documentation:** `pyproject.toml` and runtime still declare `0.3.2` while development behavior has changed. Choose a distinct candidate version, document compatibility changes, update release notes and metadata before requesting a release.
4. **D freeze:** after resolving or explicitly classifying the above, freeze the candidate SHA, verify six completed successful jobs on that exact SHA, review all development changes against stable v0.3.2, and issue an explicit `READY_TO_REQUEST_RELEASE` or `NOT_READY` assessment.

No additional paid service, runtime network requirement, source mutation, server, user-data upload, main change, PR merge, or GitHub Release is introduced by this document.
