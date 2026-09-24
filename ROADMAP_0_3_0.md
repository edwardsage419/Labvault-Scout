# LabVault Scout v0.3.0 Development Plan / 开发计划

v0.2.0 is frozen at its published tag. v0.3.0 development happens on `develop-v0.3.0`.

v0.2.0 已按正式发布标签冻结。v0.3.0 在 `develop-v0.3.0` 分支开发。

## Priorities / 优先级

1. Report compatibility and provenance / 报告兼容性与来源信息
   - Implemented: explicit report schema, tool version, hash/path semantics, and deterministic rule-set fingerprint without exposing source absolute paths.
   - 已实现：在不暴露源目录绝对路径的前提下，记录明确的报告 schema、工具版本、哈希/路径语义和确定性的规则集指纹。
   - Repeated-scan comparison reports whether preservation rules are the same, changed, or unavailable in legacy reports.
   - 重复扫描比较会明确显示保存规则相同、已变化，或旧报告中不可用。
   - Embedded inventory fingerprints, summary counts, and full-report checksums are validated before comparisons; mismatches downgrade the result to PARTIAL.
   - 比较前会验证内嵌 inventory 指纹、摘要计数和完整报告校验和；如果不匹配，结果降级为 PARTIAL。
   - Standalone `verify` checks one `scan.json` without requiring a second report.
   - 独立 `verify` 命令可以直接检查单份 `scan.json`，无需第二份报告。
   - Schema 1 inputs use strict version-aware structural validation while legacy v0.2 stays compatible and unknown future schemas are not forced into current rules.
   - schema 1 输入采用严格的版本感知结构校验；v0.2 旧报告继续兼容，未知未来 schema 不会被强套当前规则。
   - Draft 2020-12 JSON Schemas for scan/comparison/verification outputs and the bundle manifest are packaged with the tool and available through the CLI.
   - scan/comparison/verification 输出与 bundle manifest 的 Draft 2020-12 JSON Schema 随工具一起分发，并可通过 CLI 获取。

2. Compound and compressed scientific formats / 复合扩展名与压缩科研格式
   - Prefer the longest configured extension so formats such as `.nii.gz` are not reduced to generic `.gz`.
   - 使用最长匹配扩展名，避免 `.nii.gz` 被错误降级为普通 `.gz`。
   - Implemented: bounded NIfTI-1 header evidence for `.nii` and `.nii.gz` using only the standard library.
   - 已实现：仅使用标准库，对 `.nii` 与 `.nii.gz` 的 NIfTI-1 头进行有界结构检查。
   - Implemented: bounded NetCDF CDF-1/CDF-2/CDF-5, TIFF/BigTIFF, FITS primary-header, MATLAB Level 5 MAT-file, and DICOM Part 10 marker evidence with no third-party dependency.
   - 已实现：无需第三方依赖的 NetCDF CDF-1/CDF-2/CDF-5、TIFF/BigTIFF、FITS primary header、MATLAB Level 5 MAT-file 与 DICOM Part 10 标记有界证据。
   - Implemented: bounded Flow Cytometry Standard 2.0/3.0/3.1/3.2 fixed 58-byte HEADER evidence.
   - 已实现：对 Flow Cytometry Standard 2.0/3.0/3.1/3.2 的固定 58 字节 HEADER 进行有界结构检查。
   - Implemented: bounded ASCII-based SPSS SAV (`$FL2`) / ZSAV (`$FL3`) 176-byte fixed-header evidence and `.zsav` classification.
   - 已实现：对 ASCII 系 SPSS SAV（`$FL2`）/ ZSAV（`$FL3`）176 字节固定 HEADER 进行有界结构检查，并增加 `.zsav` 分类规则。
   - Implemented: bounded tagged-header evidence for modern Stata DTA releases 117/118/119; older DTA formats remain conservatively unverified.
   - 已实现：对现代 Stata DTA 117/118/119 的标签式文件头进行有界验证；其他旧版 DTA 继续保守标记为未验证。
   - Expand bounded, read-only evidence for additional formats where standard-library inspection is safe.
   - 在标准库能够安全执行有界只读检查的范围内继续增强其他格式证据。

3. Stronger project summaries / 更强项目级摘要
   - Implemented: deterministic project summaries and local comparison of repeated `scan.json` reports.
   - 已实现：确定性的项目摘要，以及本地比较多次 `scan.json` 报告。
   - Comparison distinguishes additions, removals, unique-hash moves, content changes, preservation-assessment changes, priority escalation/de-escalation, and aggregate risk/priority deltas.
   - 比较结果区分新增、删除、唯一哈希移动、内容变化、保存评估变化、优先级上升/下降，以及风险/优先级汇总差异。
   - Optional exit-code mode supports local automation without changing default interactive behavior.
   - 可选退出码模式支持本地自动化，同时保持默认交互行为不变。
   - Legacy v0.2 Windows path separators are normalized conservatively for cross-platform comparisons.
   - 对旧版 v0.2 Windows 路径分隔符进行保守规范化，支持跨平台比较。
   - Unknown future scan schemas are treated conservatively as partial compatibility rather than assumed compatible.
   - 对未知未来扫描 schema 采用保守的部分兼容状态，而不是默认完全兼容。

4. Scale and determinism / 规模与确定性
   - Implemented: deterministic traversal, cross-platform POSIX report paths, and an inventory SHA-256 fingerprint.
   - 已实现：确定性遍历、跨平台统一的 POSIX 报告路径，以及 inventory SHA-256 指纹。
   - Implemented: schema 1 runtime and packaged-schema validation reject NUL, absolute paths, parent traversal, dot segments, duplicate `/` separators, and trailing `/`; literal backslashes are preserved as filename characters on POSIX systems; explicit schema versions must be strings.
   - Implemented: files modified during hashing or bounded container inspection are reported instead of entering an inconsistent inventory.
   - 已实现：schema 1 运行时与随包 schema 路径校验会拒绝 NUL、绝对路径、父目录穿越、点路径段、重复 `/` 分隔符和末尾 `/`；在 POSIX 系统中，字面反斜杠会作为文件名字符保留；显式 schema 版本必须为字符串。
   - 已实现：哈希或有界容器识别期间发生变化的文件会被记录为扫描错误，不进入不一致的清单。
   - Implemented: 1,000-file repeated-scan comparison regression coverage without brittle timing thresholds.
   - 已实现：1,000 文件重复扫描比较回归覆盖，不采用脆弱的固定耗时阈值。

## Constraints / 约束

- Zero monetary cost / 零消费
- Local and offline / 本地离线
- Read-only source handling / 源文件只读
- No telemetry / 无遥测
- No paid API or server dependency / 无付费 API 或服务器依赖
- Conservative claims with explicit evidence / 保守判断并明确展示证据
