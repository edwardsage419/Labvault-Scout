# LabVault Scout v0.3.2 Release Notes / 发布说明

## English

LabVault Scout v0.3.2 is a maintenance hardening release for the v0.3 stable line. It tightens bounded structural verification for several already-recognized scientific formats and expands regression coverage for malformed inputs. It does not change report schema version 1, the CLI command surface, the preservation risk taxonomy, or the scientific format rule database.

### Fixed

* TIFF/BigTIFF verification now rejects invalid first-IFD offsets before assigning verified structural evidence.
* FITS verification now requires valid mandatory primary-header value indicators in the bounded header checks.
* DICOM Part 10 verification now requires bounded File Meta Information structural evidence after the `DICM` marker.
* FCS verification now rejects inconsistent DATA/ANALYSIS begin/end offset pairs, including invalid FCS 2.0 DATA zero-fallback combinations.
* SPSS SAV/ZSAV verification now requires the fixed-header `@(#) SPSS DATA FILE` product identifier prefix before assigning verified evidence.
* Modern Stata DTA releases 117/118/119 now require a bounded `<K>...</K>` header marker after the byte-order field before assigning verified structural evidence.

### Regression coverage

* Added malformed bundle-manifest type coverage.
* Added malformed scan-report and comparison-report JSON coverage.
* Added coverage for files that disappear during scanning.
* Added corrupted-header regression cases for the scientific formats tightened in this release.

### Compatibility

v0.3.2 keeps the same schema version 1 report format used by v0.3.1. Existing reports do not require migration. The CLI command surface and scientific-format rule database are unchanged.

The stricter bounded checks can cause malformed files that older logic could over-verify to be reported conservatively as unverified or requiring container review. Valid files that satisfy the existing bounded evidence requirements remain recognized as before.

### Safety and privacy

The project remains local, offline-first, source-read-only, open source, and zero-cost. It does not upload research data, modify source files, require a server, use paid APIs, execute code contained in scanned files, or add telemetry.

## 中文

LabVault Scout v0.3.2 是 v0.3 稳定系列的维护加固版本。本版本主要收紧若干已识别科研格式的 bounded structural verification，并增加 malformed input 回归覆盖。不修改 report schema version 1、CLI 命令面、保存风险分类或科研格式规则数据库。

### 修复

* TIFF/BigTIFF 验证现在会在赋予 verified 结构证据前拒绝无效的首个 IFD offset。
* FITS 验证现在会在 bounded primary-header 检查中要求强制字段具有有效的 value indicator。
* DICOM Part 10 验证现在要求在 `DICM` 标记之后存在可验证的 bounded File Meta Information 结构证据。
* FCS 验证现在会拒绝 DATA/ANALYSIS begin/end offset 不成对的情况，包括 FCS 2.0 中无效的 DATA 双零 fallback 组合。
* SPSS SAV/ZSAV 验证现在要求固定头中的 product identifier 以 `@(#) SPSS DATA FILE` 开头后，才赋予 verified 证据。
* 现代 Stata DTA 117/118/119 现在要求 byte-order 字段后存在 bounded `<K>...</K>` header marker，才赋予 verified 结构证据。

### 回归覆盖

* 增加 malformed bundle manifest 类型覆盖。
* 增加 malformed scan report 与 comparison report JSON 覆盖。
* 增加扫描期间文件消失行为的覆盖。
* 增加本版本所加固科研格式的损坏 header 回归测试。

### 兼容性

v0.3.2 继续使用与 v0.3.1 相同的 schema version 1 报告格式，已有报告不需要迁移。CLI 命令面和科研格式规则数据库保持不变。

更严格的 bounded 检查可能会使过去被过度验证的 malformed 文件改为保守的 unverified 或需要 container review。满足既有 bounded evidence 要求的有效文件仍按原有方式识别。

### 安全与隐私

项目继续保持完全本地、默认离线、源文件只读、完全开源和零使用成本。不会上传科研数据，不会修改源文件，不需要服务器，不依赖付费 API，不执行被扫描文件中的代码，也不会加入遥测。
