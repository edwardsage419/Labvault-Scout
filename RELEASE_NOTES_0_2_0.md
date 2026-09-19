# LabVault Scout v0.2.0 Release Notes / 发布说明

## English

LabVault Scout v0.2.0 advances the local, read-only scientific data preservation scanner with project-level relationships, stronger structural evidence, actionable preservation triage, and lower repeated I/O.

### Highlights

* Conservative same-directory file-family detection with `EXACT` and `DERIVATIVE` relationship strength.
* Machine-readable preservation priority scores, reasons, and recommended actions.
* Structural evidence for OpenDocument, HDF5 superblocks, RO-Crate, and BagIt packages.
* Structural container warnings raise preservation priority and recommend `REVIEW_CONTAINER`.
* SHA-256 hashing and the bounded identification header are collected in one sequential read.
* Thousand-file traversal regression coverage.
* CSV, JSON, HTML, duplicate, and migration-plan reports retain transparent evidence fields.
* Cross-platform CI covers Python 3.10 and 3.12 on Linux, Windows, and macOS.

### Release hardening

* Runtime/package version metadata is consistent.
* Scan errors use source-relative paths.
* Output-directory edge cases cannot silently suppress an entire scan or write reports at the scan root.
* Non-regular filesystem entries are skipped.
* Directory traversal and file-metadata failures are retained as non-fatal scan errors instead of being silently omitted.
* Same-directory relationships preserve actual directory identity.
* HDF5 user blocks are recognized at specification-defined signature offsets.
* OOXML confidence requires matching internal structure, not only a ZIP outer signature.
* OpenDocument metadata inspection is bounded.
* Empty ZIP archives are recognized correctly.
* Generic OLE evidence for legacy `.xls` files remains medium-confidence rather than claiming Excel-specific verification.
* Packaging metadata, the complete MIT license, and required CFF authors metadata are internally consistent.

LabVault Scout remains local, offline, read-only, open source, zero-cost, and telemetry-free. Risk labels and recommendations are preservation triage signals rather than guarantees of future readability.

## 中文

LabVault Scout v0.2.0 在本地只读科研数据保存风险扫描基础上，进一步加入项目级文件关系、更强的结构证据、更可执行的保存分级，以及减少重复 I/O 的扫描优化。

### 主要变化

* 保守识别同目录文件家族，并区分 `EXACT` 与 `DERIVATIVE` 关系强度。
* 提供机器可读的保存优先级分数、原因和建议行动。
* 增加 OpenDocument、HDF5 superblock、RO-Crate 和 BagIt 结构证据。
* 对容器结构异常提高保存优先级，并建议 `REVIEW_CONTAINER`。
* SHA-256 哈希和有限长度识别头在一次顺序读取中完成。
* 增加 1,000 文件目录遍历回归覆盖。
* CSV、JSON、HTML、重复文件和迁移计划报告保留透明证据字段。
* CI 覆盖 Linux、Windows、macOS 上的 Python 3.10 和 3.12。

### 发布前加固

* 运行时版本与包元数据保持一致。
* 扫描错误路径使用相对源目录路径。
* 输出目录边界情况不会再导致整棵目录被错误排除，也禁止直接把扫描根目录作为输出目录。
* 跳过 FIFO、设备等非普通文件系统条目。
* 目录遍历和文件元数据读取失败会作为非致命扫描错误记录，不再静默漏扫。
* 同目录关系严格保留实际目录身份。
* 支持在规范定义的签名偏移位置识别带 user block 的 HDF5。
* OOXML 只有在内部结构匹配时才获得 verified / 高置信度证据。
* OpenDocument 元数据读取采用有界读取。
* 正确识别空 ZIP 归档。
* 对旧版 `.xls` 的通用 OLE 证据保持中等置信度，不再声称已验证 Excel 专用结构。
* Python 打包元数据、完整 MIT 许可证和 CFF 必填 authors 元数据保持一致。

LabVault Scout 继续保持本地、离线、只读、开源、零成本且无遥测。风险等级和建议行动用于保存工作分级，不代表对未来可读性的保证。
