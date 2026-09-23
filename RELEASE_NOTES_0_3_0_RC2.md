# LabVault Scout v0.3.0-rc2 Release Notes / 发布说明

## English

LabVault Scout v0.3.0-rc2 is a focused hardening candidate following rc1. It keeps the same local, offline, source-read-only design and the same schema 1 report contracts while strengthening scientific-format evidence, installed-package validation, and repository documentation.

### Changes since rc1

* Adds bounded structural evidence for modern Stata DTA releases 117, 118, and 119.
* Validates the tagged `<stata_dta>` header, declared release, and `LSF` / `MSF` byte-order marker without parsing dataset records.
* Older or otherwise unrecognized Stata DTA layouts remain conservatively unverified rather than being claimed invalid.
* Installed-wheel CI now exercises `scan`, `verify`, `verify-bundle`, `compare`, and all four packaged `schema` commands.
* CI verifies packaged format rules and JSON Schema resources after wheel installation.
* CI runs `pip check` after installing the built wheel.
* Bug-report and scientific-format-request issue templates are bilingual.
* Fixes literal line-break artifacts in schema documentation.
* Corrects the stable v0.2.0 quick-start output list so it does not claim the v0.3 bundle manifest.

### Compatibility

No report-schema version change is introduced in rc2. Existing schema 1 scan, comparison, verification, and bundle-manifest contracts remain unchanged.

Stata structural evidence is deliberately limited to modern tagged DTA releases 117, 118, and 119. It is a bounded preservation signal, not a complete semantic validator.

### Safety and scope

LabVault Scout remains local, offline, source-read-only, open source, zero-cost, and telemetry-free. It does not execute scanned files or upload research data.

## 中文

LabVault Scout v0.3.0-rc2 是 rc1 之后的集中加固候选版本。它继续保持完全本地、离线、源文件只读，并保持现有 schema 1 报告契约不变，重点增强科研格式证据、安装包验证和仓库文档。

### 相比 rc1 的变化

* 增加现代 Stata DTA 117、118、119 的有界结构证据。
* 验证带标签的 `<stata_dta>` 文件头、release 和 `LSF` / `MSF` 字节序标记，不解析数据记录。
* 其他旧版或未识别 Stata DTA 结构继续保守标记为未验证，不直接声称文件无效。
* 安装 wheel 后的 CI 现在会实际执行 `scan`、`verify`、`verify-bundle`、`compare` 和四种随包 `schema` 命令。
* CI 会在 wheel 安装后验证格式规则和 JSON Schema 资源是否正确打包。
* 安装构建 wheel 后执行 `pip check`。
* Bug Report 与 Scientific Format Request Issue 模板改为中英双语。
* 修复 schema 文档中的字面量换行符问题。
* 修正稳定版 v0.2.0 Quick start 的输出列表，避免误写 v0.3 才有的 bundle manifest。

### 兼容性

rc2 不引入新的报告 schema 版本。现有 schema 1 的 scan、comparison、verification 和 bundle manifest 契约保持不变。

Stata 结构证据明确限制在现代标签式 DTA 117、118、119。该检查属于有界的数据保存证据，不等同于完整语义验证。

### 安全与范围

LabVault Scout 继续保持本地、离线、源文件只读、开源、零成本且无遥测。工具不会执行被扫描文件，也不会上传科研数据。
