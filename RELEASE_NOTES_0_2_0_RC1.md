# LabVault Scout v0.2.0-rc1 Release Notes / 发布说明

## English

v0.2.0-rc1 is the first release candidate for the second LabVault Scout development cycle. It keeps the local, offline, read-only and zero-cost design while improving evidence, migration planning and scan efficiency.

### Highlights

* Conservative derivative file-family detection with EXACT and DERIVATIVE relationship strength.
* Machine-readable priority reasons and preservation actions.
* OpenDocument, bounded HDF5 superblock, RO-Crate and BagIt structural evidence.
* Recognized preservation packages receive limited positive evidence rather than being treated as proof of safety.
* SHA-256 and the bounded identification header are collected in one sequential read.
* HDF5 and OLE checks reuse the shared header.
* Coverage for 1,000-file directories and additional malformed, truncated, disguised, duplicate and report-consistency cases.

### Release candidate status

This is a release candidate. Source handling remains read-only. No telemetry, server, account, paid API or paid dependency is required.

## 中文

v0.2.0-rc1 是 LabVault Scout 第二个开发周期的首个发布候选版本。继续保持本地、离线、只读、零消费设计，同时增强证据、迁移计划和扫描效率。

### 主要变化

* 增加保守的衍生文件家族识别，并区分 EXACT 与 DERIVATIVE 关系强度。
* 增加机器可读的优先级原因和保存建议行动。
* 增加 OpenDocument、受限 HDF5 Superblock、RO-Crate 与 BagIt 结构证据。
* 对已识别科研保存包只给予有限正向证据，不将其视为数据安全证明。
* SHA-256 与受限识别文件头在一次顺序读取中获取。
* HDF5 与 OLE 检查复用共享文件头。
* 增加 1000 文件目录，以及损坏、截断、伪装、重复文件和报告一致性测试。

### 发布候选状态

这是发布候选版本。源文件处理继续保持只读。不需要遥测、服务器、账户、付费 API 或付费依赖。
