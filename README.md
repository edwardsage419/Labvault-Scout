# LabVault Scout

**Find fragile scientific files before they become unreadable.**

LabVault Scout is a local, read-only, open-source scanner for scientific data preservation risk. It inventories research folders, computes SHA-256 hashes, classifies known scientific formats, and produces portable HTML, CSV, and JSON reports.

[中文说明](README.zh-CN.md)

## Why

Research folders often outlive the software that created them. LabVault Scout helps researchers identify files that deserve preservation attention before access becomes difficult.

## Privacy and safety

LabVault Scout runs locally. It does not upload research data, require an account, use telemetry, call paid APIs, or modify source files.

## Quick start

Python 3.10 or newer is required. The command below installs the frozen v0.2.0 tag rather than the moving development branch.

```bash
git clone --branch v0.2.0 --depth 1 https://github.com/edwardsage419/Labvault-Scout.git
cd Labvault-Scout
python -m pip install .
labvault-scout scan /path/to/research
```

By default the scanner creates `labvault-report/` containing:

* `report.html` for human review
* `files.csv` for spreadsheet analysis
* `scan.json` for programmatic use
* `duplicates.csv` for exact SHA-256 duplicate groups
* `migration_plan.csv` for prioritized preservation actions

## Risk levels

| Level | Meaning |
| --- | --- |
| SAFE | Broadly readable open or common formats |
| WATCH | Formats that deserve preservation attention |
| RESCUE | Application-specific or fragile scientific formats that should be prioritized |
| UNKNOWN | No matching rule yet |

Risk labels are triage signals. They are not guarantees of future readability and do not replace institutional preservation policy.

## Current format coverage

The initial rules include common research and scientific formats such as CSV, TSV, TIFF, HDF5, NetCDF, MATLAB, SigmaPlot JNB, Origin OPJ and OPJU, GraphPad Prism PZF, SPSS SAV, Stata DTA, Igor IBW, SPC spectroscopy, FCS, NIfTI and DICOM.

Identification combines extension rules with read-only signature checks for ZIP, OLE, HDF5, and PDF. ZIP structures for OOXML, OpenDocument, RO-Crate, and BagIt are inspected without extracting or executing file content; HDF5 detection also recognizes specification-defined user-block offsets.

## Compare scans

The v0.3 development line can compare two LabVault Scout `scan.json` reports locally:

```bash
labvault-scout compare old-report/scan.json new-report/scan.json -o labvault-comparison
```

The comparison produces `comparison.html`, `comparison.json`, and `changes.csv`, including aggregate file/byte/risk/priority deltas and priority escalation/de-escalation. Move/rename detection is deliberately conservative: it is reported only when the matching SHA-256 occurs exactly once in each complete source report. If either source scan contains recorded errors, the comparison is marked `PARTIAL` because path additions/removals may be incomplete. For scripts, add `--exit-code`: 0 means no changes, 1 means changes were detected, and 2 means the comparison is partial. Pre-schema v0.2 reports created on Windows are normalized from backslash paths to POSIX paths during comparison; ambiguous normalization collisions are rejected rather than guessed. See [the bilingual comparison guide](docs/COMPARISON.md) for semantics and limitations.

## Verify a report

v0.3 can verify the internal consistency of a single scan report:

```bash
labvault-scout verify labvault-report/scan.json
```

Exit code 0 means verified, 1 means integrity is unavailable (typically legacy v0.2), and 2 means integrity failed or the scan schema is unsupported. Add `--json` for machine-readable output.

## Machine-readable schemas

v0.3 packages JSON Schema Draft 2020-12 definitions for scan, comparison, and verification outputs:

```bash
labvault-scout schema scan
labvault-scout schema comparison
labvault-scout schema verification
```

See [docs/SCHEMAS.md](docs/SCHEMAS.md).

## Development

```bash
python -m pip install -e .
python -m pip install pytest
pytest -q
```

CI tests Python 3.10 and 3.12 on Linux, Windows, and macOS.

## Roadmap

v0.2.0 is the current frozen stable release. The v0.3.0 development line adds self-describing reports, deterministic cross-platform paths and inventory fingerprints, repeated-scan comparison, priority-change tracking, compound-extension handling, and bounded NIfTI-1 evidence.

See [ROADMAP_0_3_0.md](ROADMAP_0_3_0.md) for the bilingual development plan.

## Release notes

See [v0.2.0 release notes](RELEASE_NOTES_0_2_0.md) and [v0.1.0 release notes](RELEASE_NOTES_0_1_0.md).

## License

MIT. See [LICENSE](LICENSE).
