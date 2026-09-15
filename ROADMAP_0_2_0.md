# LabVault Scout v0.2.0 Development Plan / 开发计划

v0.1.0 remains frozen. v0.2.0 development happens on `develop-v0.2.0` until the next release candidate is ready.

v0.1.0 保持冻结。v0.2.0 在 `develop-v0.2.0` 分支开发，直到下一发布候选版本完成。

## Priorities / 优先级

1. Project-level relationship analysis / 项目级文件关系分析
   - Detect likely source, export, and derivative families beyond exact same-stem pairs.
   - 在严格证据约束下识别源文件、开放导出文件和衍生文件家族。

2. Stronger format evidence / 更强格式证据
   - Implemented: OpenDocument ZIP evidence, bounded HDF5 superblock evidence, RO-Crate and BagIt package evidence.
   - 已实现：OpenDocument ZIP 证据、受限 HDF5 Superblock 证据、RO-Crate 与 BagIt 保存包证据。
   - Expand bounded, read-only structural checks where standard-library parsing is safe.
   - 在标准库能够安全处理的范围内增加只读结构检查。

3. Actionable migration planning / 更可执行的迁移计划
   - Explain why an item is urgent and what evidence lowered or raised its priority.
   - 明确解释文件为什么需要优先处理，以及哪些证据影响了优先级。

4. Performance and scale / 性能与规模
   - Add bounded tests for larger directory trees and avoid unnecessary repeated reads.
   - 增加大目录树测试，减少不必要的重复读取。

## Constraints / 约束

- Zero monetary cost / 零消费
- Local and offline / 本地离线
- Read-only source handling / 源文件只读
- No telemetry / 无遥测
- No paid API or server dependency / 无付费 API 或服务器依赖
- Conservative claims with explicit evidence / 保守判断并明确展示证据
