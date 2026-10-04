# LabVault Scout v0.3.0 Release Notes / 发布说明

## English

LabVault Scout v0.3.0 is the first stable release of the v0.3 line. It focuses on integrity, reproducibility, conservative scientific-format identification, and long-term preservation-risk review while keeping the project local, offline-first, source-read-only, open source, and zero-cost.

### Release validation

The final 0.3.0 package version is frozen at `0.3.0`.

Before final release preparation, RC4 was validated through:

* Linux, Windows, and macOS CI on Python 3.10 and Python 3.12.
* Building and installing the generated wheel in every CI matrix job.
* CLI smoke coverage for scan, verify, verify-bundle, schema output, and compare.
* Installed-package checks for bundled scientific-format rules and JSON Schemas.
* A separate macOS user-validation run from the published `v0.3.0-rc4` tag using Python 3.12.3, including local wheel build/install, scan, report verification, bundle verification, schema output, and report comparison.

No blocker was found during RC4 user validation.

### Major additions in v0.3.0

* Self-describing scan reports with schema/tool metadata, provenance, summaries, deterministic rule fingerprints, and inventory fingerprints.
* Offline report comparison with added, removed, moved, content-changed, and assessment-changed classifications.
* Embedded report-integrity verification and standalone `verify` command.
* Report-bundle manifests and `verify-bundle` integrity validation.
* Packaged Draft 2020-12 JSON Schemas for scan, comparison, verification, and bundle outputs.
* Strict malformed-input handling with concise CLI failures instead of tracebacks for expected invalid inputs.
* Deterministic traversal, cross-platform POSIX report paths, unique-SHA move detection, and scan-time file-change detection.
* Regression-hardened bounded structural verification for NIfTI-1, NetCDF CDF-1/2/5, TIFF/BigTIFF, FITS, MATLAB Level 5, DICOM Part 10, FCS 2.0/3.0/3.1/3.2, SPSS SAV/ZSAV, and modern Stata DTA 117/118/119.

### Scientific-format policy

Format recognition is intentionally conservative. LabVault Scout uses filename extensions together with bounded structural evidence where reliable evidence is available. It does not execute macros, scripts, or code embedded in scanned files and does not attempt to implement full commercial or scientific application parsers.

Container evidence such as HDF5 remains container-only unless format-specific evidence is proven. Unknown, truncated, invalid, or mismatched inputs are surfaced for review instead of being guessed as verified formats.

### Compatibility

v0.3.0 continues to use schema version 1 for scan, comparison, verification, and bundle-manifest outputs. The final release does not introduce a new report-schema version relative to RC4.

### Privacy and operating model

LabVault Scout remains fully local and offline-first. It does not upload research data, modify source files, require a server, use a paid API, or add telemetry.

## 中文

LabVault Scout v0.3.0 是 v0.3 系列首个稳定版本。该版本重点提升数据完整性、可验证性、确定性、科研格式保守识别和长期保存风险审查，同时继续保持本地运行、默认离线、源文件只读、完全开源和零使用成本。

### 发布验证

最终 package version 已冻结为 `0.3.0`。

正式版发布准备前，RC4 已完成以下验证：

* Linux、Windows、macOS × Python 3.10 / 3.12 完整 CI。
* 每个 CI 组合都实际构建并安装生成的 wheel。
* CLI smoke 覆盖 scan、verify、verify-bundle、schema 和 compare。
* 已安装 package 的科研格式规则和 JSON Schema 资源加载检查。
* 在已发布 `v0.3.0-rc4` tag 上进行了独立 macOS 用户验证，使用 Python 3.12.3 完成本地 wheel 构建/安装、扫描、报告验证、Bundle 验证、Schema 输出和报告比较。

RC4 用户验证没有发现 blocker。

### v0.3.0 主要新增内容

* 自描述 scan report，包括 schema/tool metadata、provenance、summary、确定性规则指纹和 inventory fingerprint。
* 完全离线的报告 compare，区分 added、removed、moved、content-changed 和 assessment-changed。
* 内嵌报告完整性验证和独立 `verify` 命令。
* 报告 Bundle manifest 和 `verify-bundle` 完整性验证。
* scan、comparison、verification 和 bundle 输出的 Draft 2020-12 JSON Schema。
* 对 malformed input 的严格防护，并对预期无效输入返回简洁 CLI 错误而不是 traceback。
* 确定性目录遍历、跨平台 POSIX report path、唯一 SHA move 检测，以及扫描期间文件变化检测。
* 对 NIfTI-1、NetCDF CDF-1/2/5、TIFF/BigTIFF、FITS、MATLAB Level 5、DICOM Part 10、FCS 2.0/3.0/3.1/3.2、SPSS SAV/ZSAV 和现代 Stata DTA 117/118/119 完成回归加固的有界结构验证。

### 科研格式识别原则

格式识别继续保持保守。LabVault Scout 使用扩展名，并在存在可靠证据时结合有界结构证据。它不会执行被扫描文件中的宏、脚本或代码，也不会尝试完整实现商业软件或复杂科研软件格式解析器。

HDF5 等 container evidence 在没有格式专属证据时继续保持 container-only。对 unknown、truncated、invalid 或 signature mismatch 输入，工具会要求 review，而不是猜测为已验证格式。

### 兼容性

v0.3.0 继续使用 schema version 1 的 scan、comparison、verification 和 bundle manifest 输出。相对于 RC4，正式版不引入新的报告 schema version。

### 隐私与运行模式

LabVault Scout 继续完全本地、默认离线运行。它不会上传科研数据，不会修改源文件，不需要服务器，不依赖付费 API，也不加入遥测。
