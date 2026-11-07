# LabVault Scout 0.4.0rc1 final freeze gate / 最终冻结验收门槛

Review date / 审查日期: 2026-11-07 (Asia/Taipei)
Branch / 分支: `develop-v0.3.0`
Stable reference / 稳定基线: `main` at `4877a9a8c794ba7d78d229ef395ad7f9d38961c9` (v0.3.2)
Reviewed candidate predecessor / 已审查候选基线: `81f147d293a1ae6e1f35347e25d583a64d972879`
Predecessor CI / 基线 CI: [GitHub Actions 42330795719](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42330795719) (six jobs, success)

## English

### Scope and diff review

At the reviewed predecessor, the development branch is 354 commits ahead and 0 behind stable main. The comparison includes 95 changed files: 12 in `src/labvault_scout/` (9 Python/runtime/version files and 3 JSON schemas), 70 tests, 7 development documents, 3 release metadata/notes files, 1 workflow and 2 ancillary files.

Reviewed source change categories against stable v0.3.2:

| Area | Reviewed change and gate |
| --- | --- |
| `hashing.py`, `cli.py`, `scanner.py` | Read-only regular-file opening, file identity checks before/after hashing and identification, race/error handling, traversal and output exclusion; regression coverage and six-platform CI |
| `identifier.py` | Bounded ZIP/ZIP64 directory preflight and scientific container inspection using verified streams; malformed cases and Phase A bounded exit evidence |
| `bundle.py` | Manifest JSON type and duplicate-key rejection, bounded reads, file identity, SHA-256 and artifact verification; malformed and race regressions |
| `compare.py` | Strict schema-1 report paths and types, bounded JSON parsing, legacy compatibility, comparison/verification semantics; Phase B regressions and real stable v0.3.2 interoperability gate |
| `report.py`, `safeio.py` | CSV output safety and atomic output behavior; corresponding regression coverage |
| Three JSON schemas | Scan, comparison and verification output constraints, with the existing bundle schema retained; runtime's stricter integer-token behavior remains explicitly documented in `docs/SCHEMAS.md` |
| Packaging, CLI and rules | `0.4.0rc1` in both package/runtime, Beta classifier, bundled rules and four schemas, wheel install and CLI smoke tests in all six CI jobs |

No reproducible new high-priority security, source-integrity or report-validity defect was identified in this bounded review. This is not proof against undiscovered defects or a certification of every scientific format.

### Gate disposition

| Gate | Status and evidence |
| --- | --- |
| A ZIP/ZIP64 | BOUNDED PASS, `docs/ZIP64_PHASE_A_EXIT_2026-11-01.md` |
| B global regression | BOUNDED PASS, `docs/PHASE_B_GLOBAL_REGRESSION_GATE_2026-11-01.md` |
| C public samples | BOUNDED PASS: two pinned, offline public tabular samples (CSV, TSV), not comprehensive scientific-format validation |
| D-C01 POSIX drive-prefix historical compatibility | OWNER ACCEPTED, `docs/RELEASE_CANDIDATE_D_C01_OWNER_ACCEPTANCE_2026-11-07.md`; preserve fail-closed behavior |
| D-C02 through D-C04 stable v0.3.2 interoperability | BOUNDED PASS on six operating-system/Python jobs; real stable CLI reports, bundles, comparison and schemas, representative injected PermissionError |
| D-C05 candidate metadata | SATISFIED: package/runtime 0.4.0rc1, Beta classifier, bilingual notes and CHANGELOG |
| D-FREEZE | **PENDING SUCCESS OF THE FREEZE-RECORD COMMIT'S OWN SIX-JOB CI** and exact final HEAD recheck |

After this document's own commit is verified to be the current branch HEAD and its six matrix jobs all succeed, the technical disposition may be **READY_TO_REQUEST_RC1_RELEASE**. No additional code or documentation change is authorized by this record. If that final CI fails, D-FREEZE remains **NOT READY** and only the failure may be addressed.

### Disclosed residual limits

* The confirmed D-C01 report compatibility break remains intentional. Preserve source files and reports, rescan safely renamed copies.
* Two pinned tabular research samples do not validate all scientific formats.
* The CI stable error-bearing report uses deterministic injected `PermissionError`; real OS permission refusal is not exhaustively tested.
* Cross-platform pytest skip counts reflect conditional platform-specific scenarios; the normal `pytest -q` output does not retain individual skip reasons.
* A six-job regression pass is evidence for the tested matrix and version, not a universal correctness or security guarantee.

### Authorization boundary

**No merge to main, PR merge, tag, GitHub Release or stable v0.4.0 publication has been authorized.** A successful D-FREEZE establishes readiness to request a separate release authorization.

## 中文

### 差异与风险审查

以 `81f147d293a1ae6e1f35347e25d583a64d972879` 为审查基线，开发分支比稳定 `main` 领先 354 个提交，落后 0 个，共变更 95 个文件：12 个生产文件与 Schema、70 个测试文件、7 个开发文档、3 个发布元数据与说明文件、1 个工作流文件、2 个辅助文件。

已逐一盘点生产层变更函数与 Schema 文件，并定向复核哈希与文件身份、只读扫描、目录遍历、ZIP/ZIP64 有界结构判断、Bundle 完整性、compare/verify 报告校验、原子写入和安装后资源。对应回归与跨平台 CI 有可追溯证据。本次有界审查未发现新的可复现高优先级完整性或安全缺陷。

### 门槛处理

A 阶段 ZIP/ZIP64、B 阶段全局回归、C 阶段两份离线公开表格样本均保持有界 PASS。D-C01 已获得所有者明确接受，保留严格路径验证。D-C02 至 D-C04 真实稳定版互操作验证有界通过。D-C05 的 `0.4.0rc1` 包版本、运行时版本、Beta 分类和中英文发布说明已满足。

**D-FREEZE 必须等待本冻结记录提交自身的六项 CI 全部成功，并重新确认该提交仍是开发分支最新 HEAD。** 达成后可给出 `READY_TO_REQUEST_RC1_RELEASE` 技术结论。CI 失败时仍判定 `NOT READY`。

保留既有证据边界：部分旧报告可能因严格路径校验被拒绝；两份表格样本不代表所有科研格式均已验证；权限错误通过确定性注入模拟；平台条件跳过的逐项原因未全部由常规 CI 日志记录；测试通过无法证明不存在所有潜在缺陷。

本记录只处理候选版技术冻结准备。**未经单独授权，不合并 `main`、不合并 PR、不创建标签或 GitHub Release，不发布正式 v0.4.0。**
