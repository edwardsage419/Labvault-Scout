# LabVault Scout v0.4.0 stable release notes / 稳定版发布说明

**Status / 状态: DRAFT FOR STABLE RELEASE REVIEW / 正式版待审草稿.**
v0.4.0 has **not been published**. The latest published stable release is v0.3.2. The v0.4.0rc1 GitHub prerelease is available for evaluation. This document is a release-planning artifact only; it does not authorize a merge, tag, or GitHub Release.

**当前状态：正式版发布前审查草稿。** v0.4.0 尚未发布；最新稳定版是 v0.3.2。v0.4.0rc1 已作为 GitHub 预发布版公开。本文件只记录拟发布范围与审查门槛，不构成合并、标签或正式发布授权。

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

### Pending stable release gates

1. Finalize the `0.4.0` package/runtime version together and validate the installed wheel on all six operating-system/Python combinations.
2. Prepare stable-specific packaging and publication evidence from the precise final commit; verify the released wheel and SHA256 against that commit.
3. Review the final `main` diff, version, CHANGELOG, bilingual READMEs, citation metadata, and this release record. Update `CITATION.cff` only at the formal stable publication stage.
4. Confirm six successful CI jobs for the exact release commit; obtain specific owner authorization before merging, tagging, or publishing the stable release.
5. Independent, real-world end-user RC acceptance evidence is currently **UNKNOWN**. Do not claim external acceptance, exhaustive format certification, or universal historical compatibility.

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

### 尚需完成的正式版门槛

1. 同步更新包与运行时版本至 `0.4.0`，验证六平台安装后版本一致。
2. 为准确的最终提交准备正式版 wheel 与 SHA256，并验证发布的实际文件。
3. 复核正式版最终差异、版本号、CHANGELOG、中英文 README、引用信息及本说明。只有真正进入稳定版发布时才更新 `CITATION.cff`。
4. 核实最终提交自身的六项 CI 全绿；合并、标签及正式 GitHub Release 均需要明确的阶段授权。
5. 独立真实用户的 RC 验收证据目前为 **UNKNOWN**。不能宣称已通过外部用户验收、全面格式认证或全部历史报告兼容。

---
This document will be updated only to reflect verified facts and the actual stable release gate. / 本文件后续仅按经核实的事实及正式版门槛更新。
