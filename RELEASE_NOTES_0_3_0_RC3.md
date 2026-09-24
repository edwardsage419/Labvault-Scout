# LabVault Scout v0.3.0-rc3 Release Notes / 发布说明

## English

LabVault Scout v0.3.0-rc3 is a validation and failure-handling hardening candidate following rc2. It keeps the same local, offline, source-read-only design and the same schema 1 report contracts while tightening report validation, scan consistency, rule-file validation, and CLI error behavior.

### Changes since rc2

* Scientific-format rules are validated before use for required fields, normalized extensions, allowed risks, categories, export lists, and duplicate extensions.
* Schema 1 path validation rejects NUL characters, absolute paths, parent traversal, dot segments, duplicate `/` separators, and trailing `/`.
* Literal backslashes remain valid filename characters on POSIX systems and are preserved rather than mistaken for separators.
* Explicit scan `schema_version` values must be non-empty strings instead of being silently coerced.
* File-change detection now compares device/inode identity, size, mtime, and ctime before and after hashing, and checks again after bounded container inspection.
* Files changed during a scan are recorded as `FileChangedDuringScan` and excluded from that scan inventory.
* Report integrity verification now recomputes open-copy and duplicate-group summary counts in addition to existing inventory and summary checks.
* Bundle verification classifies broken symlink artifacts as `SYMLINK` rather than `MISSING`.
* Malformed or non-UTF-8 scan reports and bundle manifests produce concise exit-code-2 CLI errors rather than Python tracebacks.
* Scan and comparison output filesystem failures also produce concise exit-code-2 errors.
* Additional regression coverage exercises malformed manifests, non-UTF-8 reports, invalid rule structures, path semantics, changing files, and filesystem failures.

### Compatibility

rc3 does not introduce a new report schema version. Existing schema 1 scan, comparison, verification, and bundle-manifest contracts remain in use.

The path contract continues to use `/` as the report path separator. On POSIX systems, a literal backslash may legally occur inside a filename and is preserved as a filename character.

### Safety and scope

LabVault Scout remains local, offline, source-read-only, open source, zero-cost, and telemetry-free. It does not execute scanned files or upload research data.

## 中文

LabVault Scout v0.3.0-rc3 是 rc2 之后的验证与故障处理加固候选版本。它继续保持完全本地、离线、源文件只读，并继续使用现有 schema 1 报告契约，重点加强报告校验、扫描一致性、规则文件校验和 CLI 错误处理。

### 相比 rc2 的变化

* 科研格式规则在使用前会检查必需字段、规范化扩展名、允许的风险等级、分类、导出格式列表和重复扩展名。
* schema 1 路径校验会拒绝 NUL 字符、绝对路径、父目录穿越、点路径段、重复 `/` 分隔符和末尾 `/`。
* 在 POSIX 系统中，字面反斜杠仍可作为合法文件名字符并会原样保留，不会被误当成路径分隔符。
* 显式的扫描 `schema_version` 必须是非空字符串，不再静默转换其他类型。
* 文件变化检测现在会比较哈希前后的设备号、inode、大小、mtime 和 ctime，并在有界容器检查完成后再次确认。
* 扫描期间发生变化的文件会记录为 `FileChangedDuringScan`，不会进入该次扫描清单。
* 报告完整性验证会额外重新计算开放副本数量与重复组数量，并继续执行已有 inventory 和摘要一致性检查。
* Bundle 验证会把损坏的符号链接工件识别为 `SYMLINK`，不会误报为 `MISSING`。
* 格式错误或非 UTF-8 的扫描报告与 bundle manifest 会返回简洁的退出码 2 CLI 错误，不再出现 Python traceback。
* 扫描和比较输出阶段的文件系统失败也会返回简洁的退出码 2 错误。
* 新增回归覆盖包括损坏 manifest、非 UTF-8 报告、错误规则结构、路径语义、扫描期间文件变化和文件系统失败。

### 兼容性

rc3 不引入新的报告 schema 版本。现有 schema 1 的 scan、comparison、verification 和 bundle manifest 契约继续使用。

报告路径继续统一使用 `/` 作为路径分隔符。在 POSIX 系统中，文件名内部合法出现的字面反斜杠会作为文件名字符保留。

### 安全与范围

LabVault Scout 继续保持本地、离线、源文件只读、开源、零成本且无遥测。工具不会执行被扫描文件，也不会上传科研数据。
