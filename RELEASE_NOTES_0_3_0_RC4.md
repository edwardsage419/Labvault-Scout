# LabVault Scout v0.3.0-rc4 Release Notes / 发布说明

## English

LabVault Scout v0.3.0-rc4 is a release candidate focused on data-integrity hardening and conservative scientific-format verification. It continues the local, offline, source-read-only design and keeps the existing schema 1 report contracts.

### Changes since rc3

#### Integrity and failure handling

* Report paths, bundle paths, schema versions, and malformed inputs are handled with stricter validation and concise CLI failures.
* Scan-time file-change detection checks identity, size, mtime, and ctime before and after hashing and bounded container inspection.
* Comparison and verification paths remain conservative when reports are malformed, partially valid, from unsupported future schemas, or fail embedded integrity checks.
* Scientific-format rule files are validated for required structure, normalized extensions, allowed risk/category values, export lists, duplicate extensions, and deterministic fingerprinting.

#### Scientific-format verification

The format-recognition regression sweep was completed for the formats already in the v0.3 scope. Recognition remains based on bounded structural evidence and never executes code from scanned files.

* NIfTI-1: little/big endian headers, single/paired-file magic, gzip handling, truncation, invalid magic, and signature mismatch behavior.
* NetCDF: CDF-1, CDF-2, and CDF-5 evidence, including the CDF-5 64-bit record-count boundary; HDF5 containers remain conservative container-only evidence unless NetCDF-specific structure is proven.
* TIFF / BigTIFF: both byte orders, truncation boundaries, BigTIFF offset-size/reserved validation, and signature mismatch review behavior.
* FITS: bounded primary-header validation including SIMPLE, BITPIX, NAXIS/NAXISn structure, END termination, 2880-byte block rules, multi-block headers, and signature mismatch handling.
* MATLAB Level 5: little/big endian headers, version/endian consistency, truncation and invalid marker/version behavior; HDF5-based .mat files remain conservative container-only evidence.
* DICOM Part 10: preamble/DICM marker verification, truncation and missing-marker behavior, and distinct handling for truncated versus non-truncated signature mismatches.
* FCS 2.0/3.0/3.1/3.2: fixed-header validation, 58-byte boundary, spacing and numeric fields, primary TEXT bounds, non-zero DATA/ANALYSIS segment bounds, and signature mismatch handling.
* SPSS SAV/ZSAV: little/big endian fixed headers, truncation, layout and compression validation, SAV/ZSAV subtype-extension mismatches, and obvious non-SPSS signature mismatches.
* Stata DTA: modern releases 117/118/119, LSF/MSF byte order, malformed or truncated release/byteorder headers, unsupported releases, legacy/unknown conservative handling, and signature mismatch behavior.

### Compatibility

rc4 does not introduce a new report schema version. Schema 1 scan, comparison, verification, and bundle-manifest contracts remain in use.

The RC4 package version is frozen at `0.3.0rc4`. The published `v0.3.0-rc4` tag identifies the validated RC4 source.

### Safety and scope

LabVault Scout remains local, offline, source-read-only, open source, zero-cost, and telemetry-free. It does not upload research data, modify source files, execute macros or scripts found in scanned files, or require paid APIs or servers.

The scientific-format checks are intentionally bounded. They provide identification and preservation-risk evidence rather than full parsing or reconstruction of the corresponding application formats.

### Validation status

RC4 validation completed with a fully green CI matrix on Linux, Windows, and macOS with Python 3.10 and Python 3.12 before tagging and publication.

## 中文

LabVault Scout v0.3.0-rc4 是一个重点加强数据完整性和科研格式保守验证的候选版本。它继续保持本地运行、默认离线、源文件只读，并继续使用现有 schema 1 报告契约。

### 相比 rc3 的变化

#### 完整性与异常处理

* 对报告路径、Bundle 路径、schema version 和 malformed input 进行更严格校验，并在 CLI 中返回简洁错误。
* 扫描期间文件变化检测会在哈希和有界容器检查前后核对文件身份、大小、mtime 和 ctime。
* 对格式错误、部分有效、未知未来 schema 或内嵌完整性校验失败的报告，compare 与 verify 继续采用保守处理。
* 科研格式规则文件会检查必需结构、规范化扩展名、允许的风险/分类值、导出列表、重复扩展名以及确定性规则指纹。

#### 科研格式验证

已完成 v0.3 当前范围内现有格式的主要识别回归审计。格式识别继续只使用有界结构证据，不执行被扫描文件中的代码。

* NIfTI-1：覆盖大小端 header、单文件/配对文件 magic、gzip、截断、非法 magic 和 signature mismatch。
* NetCDF：覆盖 CDF-1、CDF-2、CDF-5，包括 CDF-5 的 64 位 record-count 边界；HDF5 容器在没有 NetCDF 专属结构证据时继续保持 container-only。
* TIFF / BigTIFF：覆盖两种字节序、截断边界、BigTIFF offset-size/reserved 校验以及 signature mismatch 的 review 行为。
* FITS：有界验证 SIMPLE、BITPIX、NAXIS/NAXISn、END、2880 字节块规则、多块 header 和 signature mismatch。
* MATLAB Level 5：覆盖大小端 header、version/endian 一致性、截断以及非法 marker/version；HDF5 型 .mat 在没有 MATLAB 专属结构证据时继续保持 container-only。
* DICOM Part 10：覆盖 preamble/DICM marker、截断、缺失 marker，并区分截断 mismatch 与非截断 mismatch 的处理。
* FCS 2.0/3.0/3.1/3.2：覆盖固定 header、58 字节边界、spacing、数字字段、primary TEXT 边界、非零 DATA/ANALYSIS 段范围以及 signature mismatch。
* SPSS SAV/ZSAV：覆盖大小端固定 header、截断、layout/compression、SAV/ZSAV 子类型与扩展名不一致，以及明显非 SPSS signature mismatch。
* Stata DTA：覆盖现代 117/118/119、LSF/MSF、损坏或截断的 release/byteorder header、未知 release、旧版/未知格式的保守判断以及 signature mismatch。

### 兼容性

rc4 不引入新的报告 schema 版本。schema 1 的 scan、comparison、verification 和 bundle manifest 契约继续使用。

RC4 package version 已冻结为 `0.3.0rc4`。已发布的 `v0.3.0-rc4` tag 对应经过验证的 RC4 源代码。

### 安全与范围

LabVault Scout 继续保持本地、离线、源文件只读、开源、零成本且无遥测。它不会上传科研数据，不会修改源文件，不会执行扫描文件中的宏或脚本，也不依赖付费 API 或服务器。

科研格式检查刻意保持有界，只用于提供格式识别和保存风险证据，不尝试完整解析或重建相应商业/科研软件格式。

### 验证状态

RC4 在创建 tag 和发布前，已在 Linux、Windows、macOS，以及 Python 3.10 和 Python 3.12 上完成完整 CI matrix 并全部通过。
