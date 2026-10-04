# LabVault Scout v0.3.1 Release Notes / 发布说明

## English

LabVault Scout v0.3.1 is a maintenance release for the v0.3 stable line. It contains documentation and package-metadata corrections only; scanner behavior, report schemas, format rules, integrity checks, comparison semantics, and CLI behavior are unchanged from v0.3.0.

### Fixed

* Updated the English README so the stable quick-start path points to the final v0.3 release instead of the RC4 candidate.
* Updated the Chinese README with the same stable-release guidance.
* Updated Python package metadata from the stale `Development Status :: 3 - Alpha` classifier to `Development Status :: 5 - Production/Stable`.

### Compatibility

v0.3.1 keeps the same schema version 1 outputs as v0.3.0. No report migration is required, and no scientific-format identification rule is changed in this patch.

### Safety and privacy

The project remains local, offline-first, source-read-only, open source, and zero-cost. It does not upload research data, modify source files, require a server, use paid APIs, or add telemetry.

## 中文

LabVault Scout v0.3.1 是 v0.3 稳定系列的维护版本。本版本只修正文档和 package metadata；扫描行为、报告 Schema、格式规则、完整性验证、compare 语义和 CLI 行为均与 v0.3.0 保持不变。

### 修复

* 修正英文 README，使稳定版快速安装路径不再指向 RC4 候选版本，而是指向正式 v0.3 稳定版本。
* 中文 README 同步修正稳定版安装与状态说明。
* 将 Python package metadata 中遗留的 `Development Status :: 3 - Alpha` classifier 更新为 `Development Status :: 5 - Production/Stable`。

### 兼容性

v0.3.1 继续使用与 v0.3.0 相同的 schema version 1 输出。不需要迁移已有报告，本 patch 也不修改任何科研格式识别规则。

### 安全与隐私

项目继续保持完全本地、默认离线、源文件只读、完全开源和零使用成本。不会上传科研数据，不会修改源文件，不需要服务器，不依赖付费 API，也不会加入遥测。
