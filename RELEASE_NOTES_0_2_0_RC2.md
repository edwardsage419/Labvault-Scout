# LabVault Scout v0.2.0-rc2 Release Notes / 发布说明

## English

v0.2.0-rc2 is a focused hardening release candidate following RC1.

### Changes since RC1

* Structural container warnings such as invalid, truncated, unreadable, or unknown container structures now add 10 points to preservation priority.
* Priority explanations record this as `container=+10`.
* Files with structural container warnings receive the conservative `REVIEW_CONTAINER` recommendation.
* Regression tests cover invalid ZIP and truncated HDF5 triage.
* Release metadata and installation guidance are prepared for a frozen RC2 tag.

The scanner remains local, offline, read-only, zero-cost, and telemetry-free.

## 中文

v0.2.0-rc2 是 RC1 之后的集中加固候选版本。

### 相比 RC1 的变化

* 对无效、截断、不可读或未知容器结构增加 10 分保存优先级。
* 优先级原因使用 `container=+10` 记录该因素。
* 存在容器结构异常的文件给出更保守的 `REVIEW_CONTAINER` 建议。
* 增加无效 ZIP 与截断 HDF5 的回归测试。
* 为冻结的 RC2 标签整理版本元数据和安装说明。

扫描器继续保持本地、离线、只读、零成本且无遥测。
