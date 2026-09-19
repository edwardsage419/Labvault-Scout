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

需要 Python 3.10 或更高版本。以下命令安装冻结的 v0.2.0-rc1 标签，不跟随持续变化的开发分支。

```bash
git clone https://github.com/edwardsage419/Labvault-Scout.git
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

## 当前状态

v0.2.0-rc1 是第二个开发周期的首个发布候选版本。在 v0.1.0 基础上增加衍生文件家族关系、EXACT / DERIVATIVE 关系强度、机器可读优先级原因、保存建议行动、OpenDocument / HDF5 / RO-Crate / BagIt 结构证据，以及减少重复文件读取的扫描优化。

## 发布说明

参见 [v0.2.0-rc1 中英双语发布说明](RELEASE_NOTES_0_2_0_RC1.md) 和 [v0.1.0 发布说明](RELEASE_NOTES_0_1_0.md)。

## 许可证

MIT
