# LabVault Scout

**在科研文件失去可读性之前找到它们。**

LabVault Scout 是一个完全本地、只读、开源的科研数据保存风险扫描器。它扫描科研目录，计算文件哈希，识别已知科研格式，并生成 HTML、CSV 和 JSON 报告。

## 原则

* 完全本地运行
* 只读扫描
* 不上传文件
* 不需要账户
* 无遥测
* 无付费 API
* 无服务器
* 永远不修改源文件

## 快速开始

需要 Python 3.10 或更高版本。以下命令安装冻结的 v0.2.0 标签，不跟随持续变化的开发分支。

```bash
git clone --branch v0.2.0 --depth 1 https://github.com/edwardsage419/Labvault-Scout.git
cd Labvault-Scout
python -m pip install .
labvault-scout scan /path/to/research
```

报告默认写入 `labvault-report/`，包括 `report.html`、`files.csv`、`scan.json`、精确重复文件清单 `duplicates.csv`，以及按保存优先级排序的 `migration_plan.csv`。

## 风险等级

* **SAFE**：开放或具有广泛可读性的常见格式
* **WATCH**：值得关注长期保存问题的格式
* **RESCUE**：应优先处理的应用专用或脆弱科研格式
* **UNKNOWN**：当前规则库尚不能判断

风险等级用于保存工作优先级判断，不代表对未来可读性的保证。

## 比较两次扫描

v0.3 开发线可以完全在本地比较两份 LabVault Scout `scan.json`：

```bash
labvault-scout compare old-report/scan.json new-report/scan.json -o labvault-comparison
```

比较会生成 `comparison.html`、`comparison.json` 和 `changes.csv`，并提供文件数、总字节、风险/优先级汇总差异以及优先级上升/下降。移动/重命名识别采用保守规则：只有匹配的 SHA-256 在两份完整源报告中都只出现一次时，才报告为移动。如果任一源扫描存在已记录错误，比较状态会标记为 `PARTIAL`，因为新增/删除路径可能并不完整。脚本自动化可增加 `--exit-code`：0 表示无变化，1 表示检测到变化，2 表示比较不完整。对于 Windows 上生成的无 schema 的 v0.2 旧报告，比较时会把反斜杠路径规范化为 POSIX 路径；如果规范化后发生路径冲突，则直接拒绝比较而不是猜测。详细语义和限制参见[中英双语比较指南](docs/COMPARISON.md)。

## 验证单份报告

v0.3 可以直接检查单份扫描报告的内部一致性：

```bash
labvault-scout verify labvault-report/scan.json
```

退出码 0 表示验证通过，1 表示无法验证内部完整性（通常是 v0.2 旧报告），2 表示完整性验证失败或扫描 schema 不受支持。增加 `--json` 可获得机器可读输出。

## 验证整个报告包

v0.3 还可以把生成的 HTML/CSV/JSON 报告文件作为一个整体进行校验：

```bash
labvault-scout verify-bundle labvault-report
labvault-scout verify-bundle labvault-report --json
```

manifest 固定覆盖 `scan.json`、`files.csv`、`duplicates.csv`、`migration_plan.csv` 和 `report.html`。额外文件不会影响验证；核心文件缺失或被修改都会使验证失败。

## 机器可读 Schema

v0.3 随包提供 scan、comparison、verification 和 bundle manifest 输出的 JSON Schema Draft 2020-12 定义：

```bash
labvault-scout schema scan
labvault-scout schema comparison
labvault-scout schema verification
labvault-scout schema bundle
```

参见 [docs/SCHEMAS.md](docs/SCHEMAS.md)。

## 格式结构证据

v0.3 开发线在现有 ZIP、OLE、HDF5、PDF、NIfTI 证据基础上，增加 NetCDF CDF-1/CDF-2/CDF-5、TIFF/BigTIFF、FITS primary header、MATLAB Level 5 MAT-file 与 DICOM Part 10 preamble/`DICM` 标记的有界只读检查。对于基于 HDF5 的 NetCDF-4 和 `.mat`，当前只报告保守的容器证据，不声称已经验证格式专用结构；FITS `SIMPLE=F` 会明确标记为 nonconforming 并进入容器复核。DICOM 检查只读取 Part 10 preamble/marker，不解析患者元数据或数据集内容。 FCS 检查只验证 FCS 2.0、3.0、3.1、3.2 的固定 58 字节 HEADER 结构，不读取 TEXT 或 DATA 段。 SPSS 检查对 ASCII 系 `$FL2` SAV 与 `$FL3` ZSAV 的 176 字节固定 HEADER、字节序和压缩代码做有界验证，不读取数据记录。

## 当前状态

v0.2.0 是当前冻结的稳定正式版。v0.3.0 开发线正在增加自描述且可验证的报告、跨平台确定性路径与 inventory 指纹、多次扫描比较、优先级变化跟踪、复合扩展名处理、随包分发的 JSON Schema，以及 NIfTI、NetCDF、TIFF/BigTIFF、FITS、MATLAB Level 5、DICOM Part 10、FCS 2.0/3.0/3.1/3.2 和 SPSS SAV/ZSAV 的有界结构证据。

参见 [ROADMAP_0_3_0.md](ROADMAP_0_3_0.md) 中英双语开发计划。

## 发布说明

参见 [v0.2.0 中英双语发布说明](RELEASE_NOTES_0_2_0.md) 和 [v0.1.0 发布说明](RELEASE_NOTES_0_1_0.md)。

## 许可证

MIT
