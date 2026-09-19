# LabVault Scout v0.3.0 Development Plan / 开发计划

v0.2.0 is frozen at its published tag. v0.3.0 development happens on `develop-v0.3.0`.

v0.2.0 已按正式发布标签冻结。v0.3.0 在 `develop-v0.3.0` 分支开发。

## Priorities / 优先级

1. Report compatibility and provenance / 报告兼容性与来源信息
   - Add explicit report schema and tool version metadata without exposing source absolute paths.
   - 在不暴露源目录绝对路径的前提下，为报告增加明确的 schema 与工具版本信息。

2. Compound and compressed scientific formats / 复合扩展名与压缩科研格式
   - Prefer the longest configured extension so formats such as `.nii.gz` are not reduced to generic `.gz`.
   - 使用最长匹配扩展名，避免 `.nii.gz` 被错误降级为普通 `.gz`。
   - Implemented: bounded NIfTI-1 header evidence for `.nii` and `.nii.gz` using only the standard library.
   - 已实现：仅使用标准库，对 `.nii` 与 `.nii.gz` 的 NIfTI-1 头进行有界结构检查。
   - Expand bounded, read-only evidence for additional compressed formats where standard-library inspection is safe.
   - 在标准库能够安全执行有界只读检查的范围内继续增强其他压缩格式证据。

3. Stronger project summaries / 更强项目级摘要
   - Make preservation reports easier to compare across repeated scans while retaining transparent evidence.
   - 在保留透明证据的同时，让多次扫描之间更容易进行比较。

4. Scale and determinism / 规模与确定性
   - Keep output deterministic where possible and extend scale tests without brittle timing thresholds.
   - 尽可能保持输出确定性，并继续扩展规模测试，不采用脆弱的固定耗时阈值。

## Constraints / 约束

- Zero monetary cost / 零消费
- Local and offline / 本地离线
- Read-only source handling / 源文件只读
- No telemetry / 无遥测
- No paid API or server dependency / 无付费 API 或服务器依赖
- Conservative claims with explicit evidence / 保守判断并明确展示证据
