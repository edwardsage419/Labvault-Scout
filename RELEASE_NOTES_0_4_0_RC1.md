# LabVault Scout 0.4.0rc1 candidate notes / 候选版说明

Status: **development candidate only**. The published stable release remains **v0.3.2**. This file and candidate metadata do not authorize merging, tagging, publishing, or creating a GitHub Release.

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

The development branch's previous six-job acceptance baseline is commit `5e8ccdc3ba7508e0272a1b43734df11d2b998d23`, GitHub Actions run `41382188397`. The candidate metadata commit `2fc1ee5f57d2855181d504a6fb8829f856803cca` passed all six CI jobs in run `41386826567`. The subsequent D-C05 evidence addendum commit `3ca369ea5f7f17af6caab29992fce869aa359aae` passed all six jobs in run `41884372924`, attempt 2 (the first attempt had one cancelled macOS job before test execution). These are bounded CI records. A final HEAD check and D-FREEZE review remain required before release-candidate acceptance. Current evidence supports bounded regression and interoperability claims only. No complete compatibility guarantee, scientific-format certification, or release approval is implied.

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

候选版本元数据修改前的六平台基线为提交 `5e8ccdc3ba7508e0272a1b43734df11d2b998d23`，CI `41382188397`。候选版本元数据提交 `2fc1ee5f57d2855181d504a6fb8829f856803cca` 已通过 CI `41386826567` 的六项任务。后续 D-C05 证据归档提交 `3ca369ea5f7f17af6caab29992fce869aa359aae` 已通过 CI `41884372924` 第二次尝试的六项任务（第一次尝试有一项 macOS 任务在执行测试前取消）。最终冻结仍需复核最新 HEAD 和 D-FREEZE 差异验收。现有结论属于有界回归和互操作验证，尚无完整兼容性保证，也未获得发布授权。

**No merge to main, tag, PR merge, or Release is authorized. / 未授权修改 main、合并 PR、创建标签或 Release。**
