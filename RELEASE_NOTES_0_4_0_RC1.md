# LabVault Scout 0.4.0rc1 candidate notes / 候选版说明

Status: **v0.4.0rc1 GitHub prerelease published on 2026-11-07**. The latest stable release remains **v0.3.2**. Publication of this candidate does not authorize a final v0.4.0 stable release.

## English

### Scope

This candidate consolidates bounded safety and integrity hardening on the existing local, read-only scientific preservation scanner. It does not add a server, account, telemetry, paid API, scanned-file execution, or new product surface.

* Tightened ZIP and ZIP64 structural evidence handling and conservative rejection of malformed container metadata.
* Hardened file identity checks and read-only structural inspection against changes between hashing and identification, including HDF5, FITS, and GZIP/NIfTI paths.
* Expanded error-path, malformed-report, JSON Schema, report bundle, and cross-platform deterministic regression coverage.
* Added pinned offline scanner regression fixtures from Vega Datasets v3.3.1: Seattle Weather CSV and Unemployment TSV. These two tabular samples do not establish accuracy for all scientific container formats.
* Validated actual stable v0.3.2 executable outputs against development verification, bundle verification, comparison, and Draft 2020-12 schemas across Windows, Linux, and macOS with Python 3.10 and 3.12. The representative error report uses deterministic injected PermissionError; it is not a live OS permission-denial test.

### Known compatibility change: POSIX drive-prefix filenames (D-C01)

The stable v0.3.2 scanner can produce a schema-1 report on POSIX containing a relative filename such as `C:sample.csv`. This candidate rejects that historical path as unsafe drive-prefix syntax. An actual v0.3.2-generated report with that filename was rejected by the development verifier on Linux and macOS. This is an **intentional, narrow backward-compatibility break**. Other legacy reports may also be rejected when they violate tightened validation rules. Schema version 1 is retained; schema-version equality does not guarantee acceptance of every historical report.

Do not disable or bypass the candidate's path validation. Preserve historical reports as evidence. For a new candidate report, place a **copy** of affected source files in a separate, safely named staging directory and rescan the copy; leave original research files and historical reports unchanged. Compare only reports whose path semantics are understood. When inspection of a historical report is necessary, use the pinned stable v0.3.2 verifier in an isolated, offline environment, with the limitations of its older validation rules. Never treat a historical successful verification as proof that the candidate would accept the same report.

### Evidence and limits

Historical prepublication gates included six-job runs `41382188397`, `41386826567`, and `41884372924` (attempt 2). The final D-FREEZE review and owner acceptance of D-C01 were subsequently completed. The candidate was merged to `main` at `655a3b81834f13b83164951020d3c1e66db4491a`, and [run 42334584791](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42334584791) passed all six matrix jobs. The public [v0.4.0rc1 prerelease](https://github.com/edwardsage419/Labvault-Scout/releases/tag/v0.4.0rc1) has a wheel and SHA256 file. Actual downloads of that wheel passed SHA256 checking, offline installation, and CLI scans on Windows, Ubuntu and macOS with Python 3.10 and 3.12 in [run 42345772714](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42345772714). These are bounded regression and distribution checks, not universal backward-compatibility evidence, scientific-format certification, or independent real-user acceptance.

## 中文

### 变更范围

本候选版集中加固现有本地、只读科研文件保存风险扫描器的安全性与完整性。继续保持 MIT 开源、零使用成本、离线优先，不引入服务器、账户、遥测、付费 API 或扫描文件代码执行。

* 收紧 ZIP 与 ZIP64 的结构证据判断，对损坏容器元数据保守拒绝。
* 加固哈希与格式识别之间的文件身份校验，包括 HDF5、FITS、GZIP/NIfTI 的只读结构检查。
* 扩充文件系统错误、异常报告、JSON Schema、Bundle 与跨平台确定性回归。
* 纳入固定版本的 Seattle Weather CSV 与 Unemployment TSV 离线真实样本。两种表格格式的结果不能外推至全部科研容器格式。
* 在 Windows、Linux、macOS 与 Python 3.10、3.12 上，实际执行稳定版 v0.3.2，验证历史报告、Bundle、比较结果及 Draft 2020-12 Schema。错误报告通过确定性 PermissionError 注入产生，尚未验证真实操作系统权限拒绝的全部行为。

### 已确认的历史兼容性变化（D-C01）

在 POSIX 系统上，稳定版 v0.3.2 可以生成包含 `C:sample.csv` 这类相对文件名的 schema 1 报告。候选版将其判为不安全的驱动器前缀路径并拒绝。Linux 与 macOS 已通过真实稳定版输出复现这一差异。这是**有意保留的有限向后兼容性变化**。其他不满足新校验约束的历史报告也可能被拒绝。schema 版本仍为 1，版本相同不代表所有历史报告均能通过新校验。

不得绕过当前路径校验。保留原始历史报告。需要生成新报告时，将受影响科研文件**复制**到独立且安全命名的临时目录，对副本重新扫描，保持原始科研文件和历史报告不变。仅在路径语义明确时比较报告。必须检查旧报告时，可在隔离、离线环境使用固定的 v0.3.2 验证器，同时明确旧版验证规则的局限。

### 证据边界与发布门槛

此前候选版本的六平台 CI 证据包括 `41382188397`、`41386826567` 和 `41884372924`（第二次尝试）。之后已完成 D-C01 所有者接受与 D-FREEZE 冻结审查。候选代码合并到 `main` 的 SHA 为 `655a3b81834f13b83164951020d3c1e66db4491a`，对应 [CI 42334584791](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42334584791) 六项全绿。公开的 [v0.4.0rc1 预发布版](https://github.com/edwardsage419/Labvault-Scout/releases/tag/v0.4.0rc1) 已附带 wheel 和 SHA256 文件；从公开 Release 下载 wheel 后，在 Windows、Ubuntu、macOS 的 Python 3.10 与 3.12 上完成哈希核验、离线安装及 CLI 扫描，[CI 42345772714](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42345772714) 六项全绿。上述证据属于有界回归与发行物测试，不能证明全部历史兼容性、所有科研格式准确性或独立真实用户验收。

**RC1 is published; a final stable v0.4.0 release remains subject to separate technical review and owner authorization. / RC1 已作为预发布版公开，最终 v0.4.0 稳定版仍需单独技术审查与所有者授权。**
