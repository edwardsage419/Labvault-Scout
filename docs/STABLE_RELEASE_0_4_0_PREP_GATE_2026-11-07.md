# LabVault Scout v0.4.0 stable release preparation gate / 正式版发布准备验收

Review date / 审查日期: 2026-11-07 (Asia/Taipei)

**Disposition: PREPARATION BOUNDED PASS; FINAL STABLE PUBLICATION NOT YET AUTHORIZED / 准备阶段有界通过，尚未授权正式发布。**

## English

### Frozen reference and scope

* Current stable GitHub release: **v0.3.2**.
* Public prerelease: [v0.4.0rc1](https://github.com/edwardsage419/Labvault-Scout/releases/tag/v0.4.0rc1), pinned to `655a3b81834f13b83164951020d3c1e66db4491a` on `main`.
* Stable-preparation development predecessor: `2968d92498157806e820201a5562ffc1eeb076ad` on `develop-v0.3.0`.
* Verified six-job predecessor CI: [run 42357936859](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42357936859), Windows, Ubuntu and macOS × Python 3.10 and 3.12, all success.

Against the frozen RC1 merge on `main`, the reviewed predecessor is six commits ahead and zero behind, with seven changed files: `CHANGELOG.md`, `README.md`, `README.zh-CN.md`, `RELEASE_NOTES_0_4_0.md`, `RELEASE_NOTES_0_4_0_RC1.md`, `pyproject.toml`, and `src/labvault_scout/__init__.py`. There are no changes in the scanner, hash, identifier, bundle, comparison, report writer, safety I/O, rules, or schema implementations after the tested RC1 code freeze.

The package and runtime both declare `0.4.0`; the package development classifier is `Production/Stable`. Existing `tests/test_core.py` checks the runtime version against installed wheel metadata and the CLI's `--version`. The six-platform workflow builds a wheel, installs it, runs pytest, and exercises CLI scan, verify, verify-bundle, compare, and packaged resources. A final public stable wheel download has **not** yet been tested or published.

### Verified RC1 distribution evidence

The [public RC1 wheel](https://github.com/edwardsage419/Labvault-Scout/releases/tag/v0.4.0rc1) was checked against its published SHA256, then downloaded and installed without a package index in all six OS/Python combinations. Real CLI scan, report/bundle verification, and packaged schema/rules checks passed in [run 42345772714](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42345772714).

The owner accepted D-C01's intentional, narrow historical path compatibility break. Keep strict fail-closed path checks; preserve historical reports and source files and scan safely named copies if needed. Schema version 1 is retained; acceptance of every older report is **not** guaranteed.

### Outstanding stable publication gates

1. This preparation-gate document commit must complete six CI jobs successfully, and the exact development HEAD must remain unchanged.
2. Review the final stable PR and its six-job CI before any merge into `main`. A merge requires the owner's separate authorization.
3. Reconcile user-visible stable-version references and `CITATION.cff` with the actual stable release date and tag at the publication stage; do not rewrite historical RC1 evidence.
4. Build and validate the final `0.4.0` wheel from the exact release commit, with SHA256 and cross-platform offline use checks, then verify the published assets.
5. Obtain specific authorization before the stable tag and GitHub Release. Keep RC1 tagged and immutable.
6. Evidence for independent real-world end-user acceptance is **UNKNOWN**; the published sample regressions are limited to two public tabular files, and simulated `PermissionError` does not exhaustively test live OS permission failures.

**No stable v0.4.0 publication, tag, PR merge or main update is authorized by this document.**

## 中文

### 已验证准备基线

* 当前稳定正式版仍为 **v0.3.2**。
* 公开预发布版 [v0.4.0rc1](https://github.com/edwardsage419/Labvault-Scout/releases/tag/v0.4.0rc1) 的代码固定为 `655a3b81834f13b83164951020d3c1e66db4491a`。
* 本次审查的开发分支基线为 `2968d92498157806e820201a5562ffc1eeb076ad`。
* 对应 [CI 42357936859](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42357936859) 六项全部成功。

与 RC1 冻结后的 `main` 相比，开发分支领先 6 个提交，落后 0 个，共变更 7 个文件：CHANGELOG、中英文 README、正式版说明草稿、RC1 说明、`pyproject.toml` 和 `__init__.py`。RC1 冻结后的扫描、哈希、格式识别、Bundle、compare、报告、路径安全、规则和 Schema 生产逻辑均未修改。

包版本与运行时版本均为 `0.4.0`，包分类已为 `Production/Stable`。已有测试核对安装包版本、运行时版本及 CLI 输出。六平台 CI 包括 wheel 构建与安装、pytest、扫描、报告与 Bundle 验证、compare 和随包资源。正式版 `0.4.0` 的公开 wheel 尚未发布，也尚未进行公开下载后的验收。

### RC1 发行物证据及兼容性

公开 RC1 wheel 已在 Windows、Ubuntu、macOS 与 Python 3.10、3.12 六种组合中完成 SHA256 核验、离线安装、CLI 扫描、报告与 Bundle 验证、规则及 Schema 检查，[CI 42345772714](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42345772714) 全绿。

已接受 D-C01 的有限历史路径兼容性变化。继续严格拒绝不安全路径，保留科研源文件和旧报告，对安全命名的独立副本重新扫描。报告 Schema 保留版本 1，不保证所有旧报告均能通过新版校验。

### 尚未关闭的正式发布门槛

1. 本验收文档提交自身的六平台 CI 需全部成功，并复查最新开发 HEAD。
2. 审查正式版 PR 与六平台 CI；合并 `main` 仍需所有者明确授权。
3. 在真正正式发布时核对中英文稳定版本入口、`CITATION.cff`、实际发布日期及标签；保留历史 RC1 记录。
4. 从精确正式版提交构建 `0.4.0` wheel，验证 SHA256、跨平台离线安装和公开上传的发行物。
5. 正式标签与 GitHub Release 需单独授权，RC1 历史标签保持不变。
6. 独立真实用户验收证据仍为 **UNKNOWN**。已有公开表格样本只覆盖两项，权限拒绝案例主要采用确定性注入，均不能外推为全面认证。

**本记录不授权合并 `main`、创建正式版标签或发布 v0.4.0。**
