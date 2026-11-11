# LabVault Scout v0.4.1 patch release notes / 补丁版发布说明

**Status: PREPUBLICATION DRAFT / 状态：正式发布前草稿。**

v0.4.1 is not yet published. The latest public stable release is [v0.4.0](https://github.com/edwardsage419/Labvault-Scout/releases/tag/v0.4.0). The existing stable tag and released wheel remain unchanged.

v0.4.1 尚未公开发布。当前最新正式稳定版仍为 v0.4.0，既有标签与发行物均保持不变。

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

### Limits and publication requirements

The checks cover changes detectable through validated contents and observable filesystem metadata. Transient replacements leaving no observable differences cannot be universally excluded. Independent real-world end-user acceptance remains UNKNOWN.

Before public publication, review the exact final commit and CI, independently verify the final wheel and SHA256, update citation information to the actual publication date, obtain separate tag and public Release authorization, and verify the publicly downloaded assets.

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

### 限制和正式发布条件

本修复针对可观察到的内容或文件身份变化，不能保证发现所有不留下可观察痕迹的瞬时替换。独立真实用户验收证据仍为 UNKNOWN。

正式发布前需要确认最终提交及完整 CI、校验正式 wheel 和 SHA256、按实际发布日期更新引用信息、取得单独的正式标签及公开 Release 授权，并重新下载公开发行物完成验证。
