# Repeated Scan Comparison / 重复扫描比较

LabVault Scout v0.3 development can compare two local `scan.json` reports without uploading research data.

LabVault Scout v0.3 开发线可以在完全本地的情况下比较两份 `scan.json`，不会上传科研数据。

## Usage / 使用方法

```bash
labvault-scout compare old-report/scan.json new-report/scan.json -o labvault-comparison
```

Outputs / 输出：

- `comparison.html`: human-readable summary / 供人工阅读的摘要
- `comparison.json`: machine-readable complete comparison / 机器可读的完整比较
- `changes.csv`: flat table of detected changes / 检测到的变化表格

## Change types / 变化类型

- `ADDED`: a relative path exists only in the later scan. / 相对路径只存在于后一次扫描。
- `REMOVED`: a relative path exists only in the earlier scan. / 相对路径只存在于前一次扫描。
- `MOVED`: one removed path and one added path share a SHA-256 value that occurs exactly once in each report. / 一个删除路径和一个新增路径具有相同 SHA-256，且该哈希在前后两份报告中都只出现一次。
- `CONTENT_CHANGED`: the same relative path has a different SHA-256. / 同一相对路径的 SHA-256 发生变化。
- `ASSESSMENT_CHANGED`: content is unchanged but preservation assessment fields changed, for example after rule improvements. / 文件内容未变，但保存评估字段发生变化，例如规则升级后重新评估。

`MOVED` is a conservative content-identity inference, not filesystem history. LabVault Scout does not claim to know that the operating system actually renamed a file.

`MOVED` 是基于内容身份的保守推断，不是文件系统历史记录。LabVault Scout 不声称知道操作系统是否真的执行了重命名。

## Priority changes / 优先级变化

For paired files, comparison records:

对于前后能够配对的文件，比较结果记录：

- `priority_direction = ESCALATED`: preservation priority increased / 保存优先级上升
- `priority_direction = DEESCALATED`: preservation priority decreased / 保存优先级下降
- `priority_direction = UNCHANGED`: score/level did not move / 分数或等级未变化
- `priority_delta`: later score minus earlier score when numeric scores are available / 存在数字分数时，为后一次减前一次的分数差

The comparison summary also includes aggregate file-count, byte-count, risk-count, and priority-count deltas.

比较摘要还包括文件数量、总字节、风险等级数量和优先级数量的净变化。

## COMPLETE vs PARTIAL / COMPLETE 与 PARTIAL

A comparison is `COMPLETE` when neither source scan reports read/traversal errors and both scan schemas are supported.

当两份源扫描都没有记录读取或目录遍历错误，并且两份扫描 schema 均受支持时，比较状态为 `COMPLETE`。

If either source scan contains errors, or a report uses an unsupported future scan schema, the comparison is marked `PARTIAL`. Existing successfully scanned files are still compared, but additions/removals or field semantics may be incomplete.

如果任一源扫描存在错误，或报告使用未知未来扫描 schema，比较状态标记为 `PARTIAL`。已经成功扫描的文件仍会参与比较，但新增/删除判断或字段语义可能不完整。

## Automation exit codes / 自动化退出码

Default interactive comparison exits normally regardless of whether changes are found.

默认交互式比较不会因为发现变化而返回非零退出码。

For scripts and local automation:

用于脚本和本地自动化：

```bash
labvault-scout compare old/scan.json new/scan.json --exit-code
```

- `0`: complete comparison, no changes / 完整比较且无变化
- `1`: complete comparison, changes detected / 完整比较且检测到变化
- `2`: partial comparison because a source scan contains errors / 因源扫描存在错误而比较不完整

## Cross-platform paths / 跨平台路径

v0.3 scan reports store relative paths with POSIX `/` separators on all supported operating systems.

v0.3 在所有支持的操作系统上都使用 POSIX `/` 保存相对路径。

Pre-schema v0.2 reports created on Windows may contain backslashes. During comparison, LabVault Scout normalizes those legacy paths to `/`. If two legacy paths would collapse to the same normalized path, comparison stops with an error rather than guessing.

Windows 上生成的无 schema v0.2 旧报告可能包含反斜杠。比较时会把这些旧路径规范化为 `/`。如果两个旧路径规范化后发生冲突，程序会停止并报告错误，而不是猜测。

## Inventory fingerprint / 清单指纹

v0.3 `scan.json` includes `summary.inventory_sha256`, calculated deterministically from each relative path, file size, and file SHA-256.

v0.3 的 `scan.json` 包含 `summary.inventory_sha256`，它由每个相对路径、文件大小和文件 SHA-256 确定性计算。

The fingerprint is useful for quickly checking whether the inventory content changed. It is not a digital signature and does not authenticate who produced the report.

该指纹适合快速判断文件清单内容是否变化。它不是数字签名，也不能证明报告由谁生成。

## Compatibility limits / 兼容性限制

Comparison is designed for LabVault Scout scan reports. v0.2 legacy reports are explicitly supported using their existing `files` records. Malformed structures are rejected. Unknown future scan schema versions are compared conservatively but marked `PARTIAL` rather than silently treated as fully compatible.

比较功能面向 LabVault Scout 扫描报告。v0.2 旧报告通过已有的 `files` 记录明确支持。格式错误的结构会被拒绝；未知未来扫描 schema 会保守地尝试比较，但标记为 `PARTIAL`，不会静默视为完全兼容。


## Rule context / 规则上下文

v0.3 scan reports record a deterministic SHA-256 fingerprint of the active preservation rules, together with the content hash algorithm and relative-path convention. No absolute source directory is stored in this provenance block.

v0.3 扫描报告会记录当前保存规则的确定性 SHA-256 指纹，同时记录内容哈希算法和相对路径约定。该来源信息中不会保存源目录绝对路径。

Comparison reports one of three rule states:

比较结果会显示三种规则状态之一：

- `SAME`: both reports contain the same rule fingerprint / 两份报告具有相同规则指纹
- `CHANGED`: both fingerprints exist but differ / 两份报告都有规则指纹，但内容不同
- `UNKNOWN`: one or both reports do not contain a rule fingerprint, typically legacy v0.2 reports / 一份或两份报告缺少规则指纹，通常是 v0.2 旧报告

`CHANGED` does not make the file inventory comparison partial. Instead, it adds a warning that `ASSESSMENT_CHANGED` results may reflect rule evolution rather than file-content changes.

`CHANGED` 不会让文件清单比较变成 PARTIAL；它会增加警告，提示 `ASSESSMENT_CHANGED` 可能来自规则演进，而不是文件内容变化。


## Report integrity / 报告完整性

v0.3 scan reports embed `summary.inventory_sha256`, deterministic summary counts, and a top-level `report_sha256`. Before comparison, LabVault Scout recomputes the full-report checksum, inventory fingerprint, file count, total bytes, risk/priority counts, and error count from the report contents.

v0.3 扫描报告内嵌 `summary.inventory_sha256`、确定性的摘要计数和顶层 `report_sha256`。比较前，LabVault Scout 会根据报告内容重新计算完整报告校验和、inventory 指纹、文件数量、总字节、风险/优先级计数和错误数量。

Integrity states / 完整性状态：

- `VERIFIED`: the embedded fingerprint matches the file rows / 内嵌指纹与文件记录匹配
- `MISMATCH`: the fingerprint does not match; the report may have been modified or truncated / 指纹不匹配；报告可能被修改或截断
- `UNKNOWN`: no embedded fingerprint is available, typically a legacy v0.2 report / 没有可用内嵌指纹，通常是 v0.2 旧报告

A `MISMATCH` makes the comparison `PARTIAL` and produces automation exit code 2. `UNKNOWN` alone does not make a legacy comparison partial.

`MISMATCH` 会把比较状态降级为 `PARTIAL`，自动化退出码为 2。单独的 `UNKNOWN` 不会让旧版报告比较自动变成 PARTIAL。

The inventory fingerprint and full-report checksum are internal consistency checks, not cryptographic signatures of authorship or provenance.

inventory 指纹和完整报告校验和属于内部一致性检查，不是用于证明作者身份或来源真实性的数字签名。


## Standalone verification / 独立验证

A single report can be checked without comparing it to another report:

可以在不进行两份报告比较的情况下直接检查单份报告：

```bash
labvault-scout verify report/scan.json
labvault-scout verify report/scan.json --json
```

Exit codes / 退出码：

- `0`: supported schema and internally verified / schema 受支持且内部一致性验证通过
- `1`: integrity cannot be verified, typically a legacy report without an embedded fingerprint / 无法验证内部完整性，通常是没有内嵌指纹的旧报告
- `2`: fingerprint/summary mismatch or unsupported scan schema / 指纹或摘要不匹配，或扫描 schema 不受支持

`--json` prints the verification result as one machine-readable JSON object while preserving the same exit codes.

`--json` 会以单个机器可读 JSON 对象输出验证结果，同时保持相同的退出码语义。

Recorded scan errors are reported separately. They indicate incomplete source access, not corruption of the `scan.json` itself.

扫描过程中记录的错误会单独显示。它们代表源数据访问不完整，并不等同于 `scan.json` 自身损坏。
