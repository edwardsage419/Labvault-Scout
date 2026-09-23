# LabVault Scout v0.3.0-rc1 Release Notes / 发布说明

## English

LabVault Scout v0.3.0-rc1 is the first release candidate for the v0.3 line. It focuses on verifiable reports, repeatable local comparisons, stronger deterministic output, and additional bounded scientific-format evidence while preserving the project's local, offline, read-only design.

### Highlights

* Self-describing schema 1 `scan.json` reports with tool version, provenance, rule-set fingerprint, inventory fingerprint, deterministic summary fields, and a full-report SHA-256 checksum.
* Standalone `verify` for scan-report integrity and schema compatibility.
* Report-bundle manifests plus `verify-bundle` for `scan.json`, `files.csv`, `duplicates.csv`, `migration_plan.csv`, and `report.html`.
* Packaged JSON Schema Draft 2020-12 definitions for scan, comparison, verification, and bundle-manifest outputs.
* Local repeated-scan comparison covering additions, removals, unique-hash moves, content changes, assessment changes, priority escalation or de-escalation, and aggregate project deltas.
* Conservative `PARTIAL` comparison status when source scans are incomplete, report integrity fails, or future schemas are unsupported.
* Deterministic traversal, cross-platform POSIX report paths, and thousand-file comparison regression coverage.
* Longest-extension matching so compound formats such as `.nii.gz` retain their intended classification.

### Additional bounded structural evidence

The scanner now provides bounded, read-only structural evidence for:

* NIfTI-1 `.nii` and `.nii.gz`.
* NetCDF CDF-1, CDF-2, and CDF-5.
* Classic TIFF and BigTIFF.
* FITS primary headers.
* MATLAB Level 5 MAT-files.
* DICOM Part 10 preamble and `DICM` marker.
* Flow Cytometry Standard 2.0, 3.0, 3.1, and 3.2 fixed 58-byte headers.
* ASCII-based SPSS SAV `$FL2` and ZSAV `$FL3` fixed 176-byte headers.

HDF5-based MATLAB files and NetCDF-4 files remain conservative container-only evidence unless application-specific structure is proven.

### Safety and scope

LabVault Scout remains local, offline, source-read-only, zero-cost, open source, and telemetry-free. It does not execute file content or upload research data.

Structural evidence is a preservation triage signal. It is not a complete semantic validator. DICOM inspection does not parse patient metadata. FCS inspection validates only the fixed header and does not parse TEXT or DATA segments. SPSS inspection covers the ASCII-based `$FL2` and `$FL3` fixed header path and does not parse data records.

## 中文

LabVault Scout v0.3.0-rc1 是 v0.3 系列的首个发布候选版本。本版本重点增强可验证报告、本地重复扫描比较、确定性输出，以及更多科研格式的有界结构证据，同时继续保持完全本地、离线和源文件只读。

### 主要变化

* schema 1 `scan.json` 报告加入工具版本、来源信息、规则集指纹、inventory 指纹、确定性摘要字段和完整报告 SHA-256 校验值。
* 增加独立 `verify` 命令，用于扫描报告完整性与 schema 兼容性检查。
* 增加报告包 manifest 和 `verify-bundle`，覆盖 `scan.json`、`files.csv`、`duplicates.csv`、`migration_plan.csv` 和 `report.html`。
* 随包提供 scan、comparison、verification 和 bundle manifest 的 JSON Schema Draft 2020-12 定义。
* 本地重复扫描比较可区分新增、删除、唯一哈希移动、内容变化、保存评估变化、优先级上升或下降，以及项目级汇总变化。
* 当源扫描不完整、报告完整性失败或遇到未来未知 schema 时，比较会保守标记为 `PARTIAL`。
* 增加确定性目录遍历、跨平台 POSIX 报告路径，以及 1,000 文件重复扫描比较回归覆盖。
* 使用最长扩展名匹配，使 `.nii.gz` 等复合格式保持正确分类。

### 新增有界结构证据

扫描器现在可以对以下格式执行有界、只读的结构检查：

* NIfTI-1 `.nii` 和 `.nii.gz`。
* NetCDF CDF-1、CDF-2 和 CDF-5。
* 经典 TIFF 与 BigTIFF。
* FITS primary header。
* MATLAB Level 5 MAT-file。
* DICOM Part 10 preamble 与 `DICM` 标记。
* Flow Cytometry Standard 2.0、3.0、3.1、3.2 的固定 58 字节 HEADER。
* ASCII 系 SPSS SAV `$FL2` 与 ZSAV `$FL3` 的固定 176 字节 HEADER。

对于基于 HDF5 的 MATLAB 文件和 NetCDF-4 文件，在尚未证明应用专用结构时继续只报告保守的容器证据。

### 安全与范围

LabVault Scout 继续保持本地、离线、源文件只读、零成本、开源且无遥测。工具不会执行文件内容，也不会上传科研数据。

结构证据用于保存工作分级，不等同于完整语义验证。DICOM 检查不解析患者元数据。FCS 只检查固定 HEADER，不解析 TEXT 或 DATA 段。SPSS 检查覆盖 ASCII 系 `$FL2` 与 `$FL3` 固定 HEADER，不解析数据记录。
