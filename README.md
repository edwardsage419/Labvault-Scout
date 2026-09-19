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

Identification combines extension rules with bounded, read-only signature checks for ZIP, OLE, HDF5, and PDF. ZIP OOXML structures and basic OLE headers are inspected without extracting or executing file content.

## Development

```bash
python -m pip install -e .
python -m pip install pytest
pytest -q
```

CI tests Python 3.10 and 3.12 on Linux, Windows, and macOS.

## Roadmap

v0.2.0 adds conservative derivative file families, relationship strength, machine-readable priority reasons, preservation actions, stronger structural evidence, and reduced repeated file reads.

## Release notes

See [v0.2.0 release notes](RELEASE_NOTES_0_2_0.md) and [v0.1.0 release notes](RELEASE_NOTES_0_1_0.md).

## License

MIT. See [LICENSE](LICENSE).
