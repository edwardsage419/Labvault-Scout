# JSON Schemas / JSON Schema 说明

LabVault Scout v0.3 packages Draft 2020-12 JSON Schemas for its machine-readable outputs.

LabVault Scout v0.3 随包提供机器可读输出的 Draft 2020-12 JSON Schema。

## Print a schema / 输出 schema

```bash
labvault-scout schema scan
labvault-scout schema comparison
labvault-scout schema verification\nlabvault-scout schema bundle
```

The files are also packaged inside `labvault_scout/schemas/`:

对应文件也包含在 `labvault_scout/schemas/` 包目录中：

- `scan-1.schema.json`
- `comparison-1.schema.json`
- `verification-1.schema.json`\n- `bundle-manifest-1.schema.json`

The schemas describe the current versioned output contracts. LabVault Scout itself does not depend on an external JSON Schema validator; runtime validation remains implemented locally with the Python standard library.

这些 schema 描述当前版本化输出契约。LabVault Scout 本身不依赖外部 JSON Schema 验证器；运行时校验仍使用 Python 标准库在本地实现。

The schema files are interoperability aids, not cryptographic trust statements. Report integrity is handled separately by LabVault Scout's embedded checksums, `verify`, and `verify-bundle` commands.

schema 文件用于互操作，不代表密码学信任声明。报告内部完整性由 LabVault Scout 的内嵌校验和、`verify` 与 `verify-bundle` 命令单独处理。
