# D-C01 owner acceptance / D-C01 所有者接受记录

Date / 日期：2026-11-07 (Asia/Taipei)
Candidate / 候选版：`0.4.0rc1`
Decision / 决策：**ACCEPTED BY OWNER / 所有者已接受**
Scope / 范围：documented, limited historical schema-1 report compatibility break / 已披露的有限历史报告兼容性变化

## English

### Decision

On 2026-11-07, the project owner explicitly accepted D-C01, the candidate's intentional rejection of historical schema-1 reports containing drive-prefixed relative paths such as `C:sample.csv`.

* Preserve the current fail-closed path validation. Do not weaken the drive-prefix check to accept affected historical reports.
* Disclose this historical compatibility break, including that other historical reports violating tightened validation may also be rejected. Keeping schema version `1` does not guarantee universal backward compatibility.
* Preserve original scientific source files and historical reports. To create a new candidate report, scan separately staged **copies** under safe filenames.
* If an old report requires inspection, the pinned v0.3.2 verifier may be used in an isolated, offline environment, with its older validation limits explicitly understood. Its success does not establish candidate compatibility.

### Evidence and limits

The actual stable v0.3.2 scanner can produce a schema-1 report on POSIX with filename `C:sample.csv`; the candidate's stricter verifier rejects that report. The discrepancy was reproduced on Linux and macOS using stable-version output. See `docs/RELEASE_CANDIDATE_D_EXECUTION_GATE_2026-11-02.md` and `RELEASE_NOTES_0_4_0_RC1.md`.

Before recording this decision, development HEAD `b08bf1a39d1d40f3730bd1314d376090d0e8074d` passed all six Windows/Ubuntu/macOS × Python 3.10/3.12 jobs in GitHub Actions [run 42318813221](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42318813221). This is the predecessor's CI evidence. The decision-record commit requires its own complete six-job CI and D-FREEZE review.

**D-C01 owner decision is closed. D-FREEZE and release authorization remain open.** This record does not authorize a merge into `main`, a tag, a GitHub Release, or claims of full historical compatibility or comprehensive format certification.

## 中文

### 接受决定

2026 年 11 月 7 日，项目所有者明确接受 D-C01，即候选版有意拒绝部分包含驱动器前缀相对路径（例如 `C:sample.csv`）的历史 schema 1 报告。

* 保留现有 fail-closed 路径校验，不为了接受历史报告而放宽驱动器前缀检查。
* 公开披露这项历史兼容性变化。其他违反新版严格校验规则的旧报告也可能被拒绝。Schema 版本保留 `1`，并不代表全部旧报告均可兼容。
* 保留科研源文件和历史报告。需要产生新版报告时，在独立、安全命名的目录中对**副本**重新扫描。
* 确需核验旧报告时，可在隔离的离线环境使用固定的 v0.3.2 验证器，并明确旧验证规则的局限。旧版验证成功不等于候选版可接受。

### 证据边界与剩余门槛

稳定版 v0.3.2 可在 POSIX 系统生成包含 `C:sample.csv` 的 schema 1 报告；候选版会拒绝这类路径。已使用真实稳定版输出在 Linux 和 macOS 上复现。证据见 `docs/RELEASE_CANDIDATE_D_EXECUTION_GATE_2026-11-02.md` 和 `RELEASE_NOTES_0_4_0_RC1.md`。

归档前的开发 HEAD `b08bf1a39d1d40f3730bd1314d376090d0e8074d` 已在 GitHub Actions [run 42318813221](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42318813221) 完成 Windows、Ubuntu、macOS 与 Python 3.10、3.12 六项成功测试。这是归档前提交的证据。归档提交仍须独立通过六项 CI，并完成 D-FREEZE。

**D-C01 的所有者决策已关闭。D-FREEZE 和发布授权仍未完成。** 本记录不授权修改或合并 `main`、创建标签、创建 GitHub Release，也不构成全量历史兼容或全面科研格式验证的声明。
