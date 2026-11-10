# LabVault Scout v0.4.0 stable release notes / 稳定版发布说明

**Status / 状态: PUBLICATION AUTHORIZED, EXECUTION PENDING / 已授权正式发布，尚未执行公开发布。**
v0.4.0 has **not been published**. The latest published stable release remains v0.3.2. On 2026-11-10, the owner authorized final metadata preparation, tagging and public release. This document records the release plan and verified evidence; it is not evidence that a tag or GitHub Release exists.

**当前状态：正式发布已获授权，公开发布尚未执行。** v0.4.0 尚未公开发布，最新稳定版仍为 v0.3.2。所有者于 2026-11-10 授权最终元数据、正式标签及公开发布。本说明记录实际验证与待办事项，不代表正式标签或 GitHub Release 已存在。

## English

### Proposed scope

LabVault Scout remains a free, open-source, local, offline-first, read-only scientific data preservation risk scanner. It does not upload research data, execute code found in scanned files, modify source files, depend on servers, or require a paid API.

Relative to stable v0.3.2, the v0.4 candidate includes:

* Stronger bounded ZIP/ZIP64 structural inspection and conservative rejection of malformed container metadata.
* File identity checks across hashing and bounded read-only identification, including selected HDF5, FITS, and GZIP/NIfTI paths.
* Stricter malformed scan reports, comparison inputs, report bundle manifests, JSON numeric constraints, and packaged schema validation.
* Additional deterministic filesystem race, error-path, corruption, and cross-platform regressions, plus two version-pinned, offline public tabular datasets for scanner checks.

These improvements do not establish full support for every scientific format. Format claims remain limited to evidence actually inspected.

### Confirmed compatibility change: D-C01

An actual stable v0.3.2 report produced on POSIX with a drive-prefixed relative filename such as `C:sample.csv` can be rejected by the candidate's strict path validator. The project owner accepted this limited compatibility change in `docs/RELEASE_CANDIDATE_D_C01_OWNER_ACCEPTANCE_2026-11-07.md`. Other older reports violating tightened validation can also be rejected even though report schema version 1 is retained.

Do not relax path validation. Preserve source data and historical reports. For a new report, scan a separately staged, safely named **copy**. If the historical report must be inspected, use an isolated offline environment with the pinned v0.3.2 verifier and understand its earlier validation limits.

### Existing verification evidence

* The frozen v0.4.0rc1 code is commit `655a3b81834f13b83164951020d3c1e66db4491a`, merged to `main` via PR #13. The six-job CI passed in [run 42334584791](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42334584791).
* The [public v0.4.0rc1 GitHub prerelease](https://github.com/edwardsage419/Labvault-Scout/releases/tag/v0.4.0rc1) contains `labvault_scout-0.4.0rc1-py3-none-any.whl` and its SHA256 checksum file. The verified wheel digest is `750b0535bdf0ec6e49e90f8c25665a2845002cb5f24707b8898fe1957d3fda47`.
* The **publicly downloaded** RC1 wheel passed checksum checking, offline wheel installation, actual CLI scan, report verification, bundle verification, and packaged rules/schema loading on Windows, Ubuntu, and macOS with Python 3.10 and 3.12: [six-job run 42345772714](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42345772714).
* Historical stable v0.3.2 interoperability was tested using real stable CLI outputs. The representative error-bearing report was generated through deterministic `PermissionError` injection; full live operating-system permission-denial behavior remains untested.
* The `0.4.0` package/runtime version and installed-wheel checks passed on Windows, Ubuntu, and macOS with Python 3.10 and 3.12 at development commit `8f51217344a196e995b76ab07fe9e9ebf0a899d3` ([push CI 42358133478](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42358133478)); the draft PR independently passed the same six jobs ([PR CI 42787858787](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42787858787)). The final public stable wheel remains unpublished.

* Stable preparation PR [#14](https://github.com/edwardsage419/Labvault-Scout/pull/14) merged at `b84a857f912e8d621bf30720920a0ff00b512c05`; [post-merge six-job CI 42803107077](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42803107077) succeeded. The candidate wheel passed SHA256 and independent installed-file-to-commit checks. These are prepublication checks.

### Pending stable release gates

1. Finalize the release branch, confirm its exact-head six-job CI, and reconcile `CITATION.cff` `date-released` with the actual release date.
2. Execute the authorized publication: merge finalized release metadata, create the immutable `v0.4.0` tag, and attach an exact-commit wheel and SHA256 file to the public GitHub Release.
3. Independently download the public wheel and checksum, verify SHA256, perform offline installation and CLI tests, and archive the resulting public release evidence.
4. Independent real-world end-user acceptance remains **UNKNOWN**. Do not claim exhaustive scientific-format certification or universal historical compatibility.

## 中文

### 拟发布范围

LabVault Scout 保持完全开源、零使用成本、本地运行、离线优先、只读扫描的科研数据保存风险识别目标。无需服务器或付费 API，不上传科研文件，不修改源文件，不执行被扫描文件中的代码。

与稳定版 v0.3.2 相比，v0.4 候选代码主要包含：

* 加强 ZIP、ZIP64 的有界结构证据检查，对损坏的容器元数据采取保守判断。
* 加强哈希与只读格式检查之间的文件身份验证，覆盖部分 HDF5、FITS 与 GZIP/NIfTI 识别路径。
* 强化异常扫描报告、比较输入、Bundle manifest、JSON 数值约束和随包 Schema 的验证。
* 增加确定性的文件系统竞争、错误路径、损坏输入和跨平台回归测试，并使用两份固定版本的公开表格样本进行离线扫描测试。

这些证据不能证明所有科研格式均已全面验证。格式识别结论仍限于实际检查的有界结构。

### 已接受的历史兼容性变化 D-C01

稳定版 v0.3.2 在 POSIX 系统上生成的部分旧报告，如果包含 `C:sample.csv` 等驱动器前缀相对路径，会被新版严格路径验证拒绝。所有者已经接受这一有限变化，记录见 `docs/RELEASE_CANDIDATE_D_C01_OWNER_ACCEPTANCE_2026-11-07.md`。其他违反新版约束的旧报告也可能被拒绝。报告 Schema 版本仍为 1，并不保证所有旧报告完全兼容。

保留严格路径验证、原始科研数据与历史报告。需要新版报告时，对独立暂存且安全命名的**副本**重新扫描。确需审阅旧报告时，在隔离的离线环境中使用固定的 v0.3.2 验证器，并明确其旧版规则的局限。

### 已完成的验证

* 冻结的 v0.4.0rc1 代码为 `655a3b81834f13b83164951020d3c1e66db4491a`，通过 PR #13 合并至 `main`。对应 [CI 42334584791](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42334584791) 六项全部成功。
* [公开 RC1 预发布版](https://github.com/edwardsage419/Labvault-Scout/releases/tag/v0.4.0rc1) 已提供 wheel 与 SHA256 校验文件。wheel 哈希已验证。
* 直接下载公开 wheel，在 Windows、Ubuntu、macOS 与 Python 3.10、3.12 六种环境下，完成哈希校验、离线安装、真实 CLI 扫描、报告与 Bundle 验证、规则及 Schema 加载测试，对应 [CI 42345772714](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42345772714) 六项成功。
* 已使用真实稳定版 v0.3.2 CLI 输出验证历史互操作。代表性错误报告采用确定性 `PermissionError` 注入，尚无真实操作系统权限拒绝行为的全面验证证据。
* 开发提交 `8f51217344a196e995b76ab07fe9e9ebf0a899d3` 的 `0.4.0` 包版本、运行时版本和 wheel 安装验收，已在 Windows、Ubuntu、macOS 与 Python 3.10、3.12 六种组合中通过（[推送 CI 42358133478](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42358133478)）；草稿 PR 的六项 CI 也全部通过（[PR CI 42787858787](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42787858787)）。公开正式版 wheel 仍未发布。

* 正式版准备 PR [#14](https://github.com/edwardsage419/Labvault-Scout/pull/14) 已合并至 `main`，提交 `b84a857f912e8d621bf30720920a0ff00b512c05` 的 [六平台 CI 42803107077](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42803107077) 全绿。对应候选 wheel 已通过 SHA256 与安装文件源码对应性核验，属于公开发布前证据。

### 尚需完成的正式版门槛

1. 完成发布分支的最终审查与六平台 CI，并按实际发布日期复核 `CITATION.cff` 的 `date-released`。
2. 执行已授权的发布操作：合并最终元数据、创建 `v0.4.0` 标签、将对应提交的 wheel 与 SHA256 文件上传到公开 GitHub Release。
3. 从公开 Release 重新下载 wheel 和校验文件，核对 SHA256，进行离线安装及 CLI 检查，并归档实际发布证据。
4. 独立真实用户验收证据仍为 **UNKNOWN**，不得宣称所有科研格式全面认证或所有历史报告完全兼容。

---
This document will be updated only to reflect verified facts and the actual stable release gate. / 本文件后续仅按经核实的事实及正式版门槛更新。
