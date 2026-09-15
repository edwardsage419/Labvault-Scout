# LabVault Scout v0.1.0 / 首个公开版本

## English

LabVault Scout v0.1.0 is the first release candidate of a zero-cost, local, read-only scientific data preservation scanner.

### What it does

- Recursively inventories research folders without modifying source files.
- Computes SHA-256 hashes and identifies exact duplicate groups.
- Triages known scientific formats as SAFE, WATCH, RESCUE, or UNKNOWN.
- Collects bounded signature evidence for ZIP, OLE, HDF5, and PDF.
- Inspects OOXML ZIP structures and basic OLE headers without extraction or execution.
- Detects conservative same-directory, same-stem open copies.
- Records evidence and confidence separately from preservation risk.
- Produces a transparent preservation priority score.
- Generates an actionable `migration_plan.csv`.

### Output

A scan produces:

- `report.html`
- `files.csv`
- `scan.json`
- `duplicates.csv`
- `migration_plan.csv`

### Privacy and cost

The scanner runs locally, requires no account, uploads no research data, uses no telemetry, calls no paid API, and has no server dependency.

### Validation

The release candidate is tested from a built wheel on Ubuntu, macOS, and Windows with Python 3.10 and 3.12. CI validates tests, CLI startup, a real smoke scan, report creation, and packaged scientific-format rules.

### Install from source

```bash
git clone https://github.com/edwardsage419/Labvault-Scout.git
cd Labvault-Scout
python -m pip install .
labvault-scout scan /path/to/research
```

Risk labels and priority scores are triage aids. They are not guarantees of future readability.

---

## 中文

LabVault Scout v0.1.0 是首个发布候选版本。它是一款零成本、完全本地、只读的科研数据保存风险扫描工具。

### 当前能力

- 递归扫描科研目录，不修改源文件。
- 计算 SHA-256，并识别完全相同的重复文件。
- 将已知科研格式分为 SAFE、WATCH、RESCUE、UNKNOWN。
- 对 ZIP、OLE、HDF5、PDF 进行受限文件签名检查。
- 在不解压、不执行文件内容的情况下检查 OOXML ZIP 结构和基础 OLE 文件头。
- 保守检测同目录、同主文件名的开放副本。
- 分别记录保存风险、识别证据和置信度。
- 计算透明、可解释的保存处理优先级。
- 自动生成 `migration_plan.csv` 迁移行动清单。

### 输出文件

每次扫描生成：

- `report.html`
- `files.csv`
- `scan.json`
- `duplicates.csv`
- `migration_plan.csv`

### 隐私与成本

完全本地运行，不需要账户，不上传科研数据，无遥测，无付费 API，无服务器依赖。

### 验证

发布候选 wheel 已在 Ubuntu、macOS、Windows，以及 Python 3.10、3.12 的组合环境中验证。CI 覆盖自动测试、CLI 启动、真实扫描、报告生成和包内科研格式规则加载。

### 从源码安装

```bash
git clone https://github.com/edwardsage419/Labvault-Scout.git
cd Labvault-Scout
python -m pip install .
labvault-scout scan /path/to/research
```

风险等级和优先级用于科研数据保存分诊，不代表对未来可读性的保证。
