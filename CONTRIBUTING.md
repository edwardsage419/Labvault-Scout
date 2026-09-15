# Contributing / 贡献指南

## English

Contributions that improve scientific format coverage, tests, documentation, and preservation evidence are welcome.

Please keep the core guarantees intact: local operation, read-only source access, no telemetry, no required cloud service, and no paid API dependency.

For format-rule changes, include the format name, extension, rationale for the proposed risk level, and preferably a public authoritative reference. Do not commit confidential, personal, proprietary, or copyrighted research datasets as test fixtures.

Run `pytest -q` before submitting changes.

## 中文

欢迎贡献科研格式规则、测试、文档和数据保存依据。

请保持核心原则：本地运行、源文件只读、无遥测、不依赖云服务、不依赖付费 API。

修改格式规则时，请说明格式名称、扩展名、风险等级理由，并尽量提供公开且权威的参考资料。不要把机密数据、个人数据、专有科研数据或受版权限制的数据作为测试样本提交。

提交前请运行 `pytest -q`。
