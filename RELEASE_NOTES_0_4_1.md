# LabVault Scout v0.4.1 patch release notes / 补丁版发布说明

**Status: STABLE PATCH RELEASE PUBLISHED 2026-11-11 / 状态：稳定补丁版已于 2026-11-11 正式发布。**

The public [v0.4.1 stable release](https://github.com/edwardsage419/Labvault-Scout/releases/tag/v0.4.1) was published on 2026-11-11. The tag points to `a3e56e672c74cafcdd577f06bde697eab52a11a0`. Previous v0.4.0 assets remain available.

[v0.4.1 稳定补丁版](https://github.com/edwardsage419/Labvault-Scout/releases/tag/v0.4.1) 已于 2026-11-11 发布，正式标签指向 `a3e56e672c74cafcdd577f06bde697eab52a11a0`。历史 v0.4.0 标签与发行物保持不变。

## English

### Patch rationale

A deterministic reproduction found that Bundle verification could return VERIFIED if the manifest was modified during validation of the report artifacts. Further review showed that same-content replacement with a different file identity was also previously missed.

### Changes

1. Load the manifest again at the end of verification and compare its parsed contents to the initial manifest.
2. Compare observable manifest file identity metadata across the verification call. When a change is detected, report FAILED, exit code 2, with issue ManifestChangedDuringVerification.
3. Add deterministic regression cases for an invalid manifest checksum, altered internally valid manifest, and replacement by a file containing identical bytes.

The project remains free, open source, local, offline-first, and source-read-only. No new format certification or schema changes are included.

### Verified evidence

* Fixed code and tests merged through [PR #17](https://github.com/edwardsage419/Labvault-Scout/pull/17) at bb50b81075fb2818c42defbfffea431646125142; its [post-merge CI](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42953137318) passed across Windows, Ubuntu and macOS, Python 3.10 and 3.12.
* The v0.4.1 package/runtime version update at 4f4d46a032ad875c54f78acaf643b40ffa629b5f passed [CI 42957754106](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42957754106), all six jobs.

### Limits and published artifact verification

The checks cover changes detectable through validated contents and observable filesystem metadata. Transient replacements leaving no observable differences cannot be universally excluded. Independent real-world end-user acceptance remains UNKNOWN.

The exact tagged commit `a3e56e672c74cafcdd577f06bde697eab52a11a0` passed [six-job CI 42966527817](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42966527817). [Publication workflow 42966986928](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42966986928) validated wheel RECORD, offline CLI operations, draft release assets and publicly downloaded file bytes. Published wheel SHA256: `8a7fc1b4055672d25c4514b9412ffea3ef1e4ab24d322435c56f5a76b58828b0`. The adjacent wheel.sha256 file checks download consistency but does not independently authenticate publisher identity.

## 中文

### 补丁原因

经确定性复现，Bundle 校验期间如果 manifest 被修改，旧实现在某些情况下可能错误返回 VERIFIED。进一步审查发现，如果 manifest 被内容完全相同但文件身份不同的文件替换，也可能漏检。

### 修复内容

1. 完成报告文件验证后重新加载 manifest，和首次成功验证的内容比较。
2. 比较验证前后的可观察文件身份信息。检测到变化时返回 FAILED、退出码 2，并记录 ManifestChangedDuringVerification。
3. 增加三个回归场景，覆盖错误校验值、内容改变但校验值正确、相同字节内容的文件替换。

本项目继续保持开源、免费、本地运行、离线优先、源文件只读。不增加格式认证声明，也不更改 JSON Schema。

### 已有验证

* 修复及测试通过 [PR #17](https://github.com/edwardsage419/Labvault-Scout/pull/17) 合并，提交 bb50b81075fb2818c42defbfffea431646125142；[合并后 CI](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42953137318) 六项成功。
* v0.4.1 版本号准备提交 4f4d46a032ad875c54f78acaf643b40ffa629b5f 的 [CI](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42957754106) 六项成功。

### 限制和公开发行物验证

本修复针对可观察到的内容或文件身份变化，不能保证发现所有不留下可观察痕迹的瞬时替换。独立真实用户验收证据仍为 UNKNOWN。

正式标签指向 `a3e56e672c74cafcdd577f06bde697eab52a11a0`，对应的 [六平台 CI 42966527817](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42966527817) 已全部通过。[发布工作流 42966986928](https://github.com/edwardsage419/Labvault-Scout/actions/runs/42966986928) 已验证 wheel RECORD、离线 CLI、草稿附件和公开下载文件的完整性。正式 wheel SHA256 为 `8a7fc1b4055672d25c4514b9412ffea3ef1e4ab24d322435c56f5a76b58828b0`。随附 wheel.sha256 用于检查文件一致性，不能独立证明发布者身份。
