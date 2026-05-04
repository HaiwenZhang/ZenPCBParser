<a id="top"></a>
# AuroraDB 与 AAF 命令支持 / AuroraDB And AAF Command Support

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

本项目把 AAF 命令文件作为 AuroraDB 的一个来源入口实现：

```text
design.part + design.layout -> auroradb.aaf -> AuroraDB
```

这里的 AAF 指 ASIV 使用的命令文件，不是原始 AAF 二进制或 JSON。

架构说明见：[architecture.md](architecture.md)。

## 版本

- 当前项目版本：`1.0.26`
- 当前 AuroraDB 解析器版本：`0.2.13`
- 当前 AuroraDB JSON schema 版本：`0.2.0`
- AuroraDB 读取、AAF 命令执行、AuroraDB 派生逻辑变化时，更新 `auroradb.version.AURORADB_PARSER_VERSION`，并体现在 `metadata.parser_version`。
- AuroraDB JSON 字段增删、字段含义或结构变化时，更新 `auroradb.version.AURORADB_JSON_SCHEMA_VERSION`，并体现在 `metadata.output_schema_version`。

## 模块结构

```text
auroradb/
  version.py        # AuroraDB parser/schema 版本
  schema.py         # AuroraDB JSON schema 定义
  block.py          # ASIV CeIODataBlock 风格 block 文本读写
  models.py         # AuroraDB package、metadata、summary 与 Pydantic 结构化模型
  reader.py         # layout.db / parts.db / layers/*.lyr 读取
  writer.py         # AuroraDB 写出
  inspect.py        # summary 与 JSON 导出
  diff.py           # semantic diff
  aaf/
    lexer.py        # ASIV 命令 tokenizer
    parser.py       # design.layout / design.part 命令解析
    geometry.py     # -g geometry 解析
    executor.py     # 命令 AST -> AuroraDB block model
    translator.py   # from-aaf 高层入口
```

## CLI

读取 AuroraDB：

```powershell
aurora-translator auroradb inspect <auroradb_dir>
aurora-translator auroradb export-json <auroradb_dir> -o out.json
aurora-translator auroradb export-json <auroradb_dir> -o out.json --include-raw-blocks
aurora-translator auroradb diff <db_a> <db_b>
```

导出 AuroraDB JSON schema：

```powershell
aurora-translator auroradb schema
aurora-translator auroradb schema -o auroradb\docs\auroradb_schema.json
```

解析 AAF 命令文件：

```powershell
aurora-translator auroradb parse-aaf --layout design.layout --part design.part
```

从 AAF 命令生成 AuroraDB：

```powershell
aurora-translator auroradb from-aaf --layout design.layout --part design.part -o auroradb_out
```

## JSON 输出

机器可读 schema 路径为 [auroradb_schema.json](auroradb_schema.json)。

顶层字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `metadata` | object | 项目版本、AuroraDB 解析器版本、AuroraDB JSON schema 版本。 |
| `root` | string/null | AuroraDB 目录路径；内存对象为 `null`。 |
| `summary` | object | 层、网络、器件、几何等数量统计。 |
| `diagnostics` | array | 非致命读取或转换诊断。 |
| `layout` | object/null | `layout.db` 的结构化内容，包括 units、stackup、shapes、via templates、nets。 |
| `layers` | array | `layers/*.lyr` 的结构化内容，包括 components、logic layers、net geometries。 |
| `parts` | object/null | `parts.db` 的结构化内容，包括 parts、schematic symbols、footprints。 |
| `raw_blocks` | object/null | 可选原始 block tree，仅 `--include-raw-blocks` 时输出。 |

`metadata` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `project_version` | string | 生成该 AuroraDB JSON 的 Aurora Translator 项目版本。 |
| `parser_version` | string | 生成该 AuroraDB JSON 的 AuroraDB 解析器版本。 |
| `output_schema_version` | string | 当前 AuroraDB JSON schema 版本。 |

## 当前覆盖范围

当前版本覆盖 AuroraDB 通用 block 读写、目录读取、写出、summary、结构化 JSON 导出、schema 导出、diff，以及 AAF 命令的基础编译链路。

`design.layout` 已优先支持：

- `layout set -unit`
- `layout set -profile`
- `layout set -layerstack`
- `layout add -shape`
- `layout add -layer`
- `layout add -doc`
- `layout add -complayer`
- `layout add -logic`
- `layout add -component`
- `layout add -via`
- `layout add -net`
- `layout add -component ... -net`
- `layout add -via ... -net`
- `layout add -g/-shape ... -layer ... -net`
- `layout add -g/-shape ... -logic ... -layer`

`design.part` 已优先支持：

- `library add/set -p`
- `library add -pin ... -p`
- `library add -symbol`
- `library add -footprint`
- `library add -pad ... -footprint`
- `library add -g ... -pad ... -footprint`
- `library add -fpn ... -pad ... -layer ... -footprint`
- `library add -g ... -layer ... -footprint`

更细的 symbol 几何执行和外部 parts DB merge 已保留诊断入口；遇到未覆盖命令会写入 diagnostics，方便后续按格式能力继续补齐。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

This project implements AAF command files as an input source for AuroraDB:

```text
design.part + design.layout -> auroradb.aaf -> AuroraDB
```

Here AAF means the command files used by ASIV, not raw AAF binary or JSON.

Architecture notes: [architecture.md](architecture.md).

## Versions

- Current project version: `1.0.26`
- Current AuroraDB parser version: `0.2.13`
- Current AuroraDB JSON schema version: `0.2.0`
- Update `auroradb.version.AURORADB_PARSER_VERSION` when AuroraDB reading, AAF command execution, or AuroraDB generation logic changes; it is emitted as `metadata.parser_version`.
- Update `auroradb.version.AURORADB_JSON_SCHEMA_VERSION` when AuroraDB JSON fields, field meanings, or structure change; it is emitted as `metadata.output_schema_version`.

## Module Structure

```text
auroradb/
  version.py        # AuroraDB parser/schema versions
  schema.py         # AuroraDB JSON schema definition
  block.py          # ASIV CeIODataBlock-style block text read/write
  models.py         # AuroraDB package, metadata, summary, and Pydantic structured model
  reader.py         # Reads layout.db / parts.db / layers/*.lyr
  writer.py         # Writes AuroraDB
  inspect.py        # Summary and JSON export
  diff.py           # Semantic diff
  aaf/
    lexer.py        # ASIV command tokenizer
    parser.py       # design.layout / design.part command parsing
    geometry.py     # -g geometry parsing
    executor.py     # Command AST -> AuroraDB block model
    translator.py   # High-level from-aaf entry point
```

## CLI

Read AuroraDB:

```powershell
aurora-translator auroradb inspect <auroradb_dir>
aurora-translator auroradb export-json <auroradb_dir> -o out.json
aurora-translator auroradb export-json <auroradb_dir> -o out.json --include-raw-blocks
aurora-translator auroradb diff <db_a> <db_b>
```

Export AuroraDB JSON schema:

```powershell
aurora-translator auroradb schema
aurora-translator auroradb schema -o auroradb\docs\auroradb_schema.json
```

Parse AAF command files:

```powershell
aurora-translator auroradb parse-aaf --layout design.layout --part design.part
```

Generate AuroraDB from AAF commands:

```powershell
aurora-translator auroradb from-aaf --layout design.layout --part design.part -o auroradb_out
```

## JSON Output

The machine-readable schema is [auroradb_schema.json](auroradb_schema.json).

Top-level fields:

| Field | Type | Description |
| --- | --- | --- |
| `metadata` | object | Project version, AuroraDB parser version, and AuroraDB JSON schema version. |
| `root` | string/null | AuroraDB directory path; `null` for in-memory objects. |
| `summary` | object | Counts for layers, nets, components, geometry, and related objects. |
| `diagnostics` | array | Non-fatal read or conversion diagnostics. |
| `layout` | object/null | Structured content from `layout.db`, including units, stackup, shapes, via templates, and nets. |
| `layers` | array | Structured content from `layers/*.lyr`, including components, logic layers, and net geometries. |
| `parts` | object/null | Structured content from `parts.db`, including parts, schematic symbols, and footprints. |
| `raw_blocks` | object/null | Optional raw block tree, emitted only with `--include-raw-blocks`. |

`metadata` fields:

| Field | Type | Description |
| --- | --- | --- |
| `project_version` | string | Aurora Translator project version that generated this AuroraDB JSON. |
| `parser_version` | string | AuroraDB parser version that generated this AuroraDB JSON. |
| `output_schema_version` | string | Current AuroraDB JSON schema version. |

## Current Coverage

The current version covers generic AuroraDB block read/write, directory reading, writing, summaries, structured JSON export, schema export, diff, and the basic AAF command compilation path.

`design.layout` is prioritized for:

- `layout set -unit`
- `layout set -profile`
- `layout set -layerstack`
- `layout add -shape`
- `layout add -layer`
- `layout add -doc`
- `layout add -complayer`
- `layout add -logic`
- `layout add -component`
- `layout add -via`
- `layout add -net`
- `layout add -component ... -net`
- `layout add -via ... -net`
- `layout add -g/-shape ... -layer ... -net`
- `layout add -g/-shape ... -logic ... -layer`

`design.part` is prioritized for:

- `library add/set -p`
- `library add -pin ... -p`
- `library add -symbol`
- `library add -footprint`
- `library add -pad ... -footprint`
- `library add -g ... -pad ... -footprint`
- `library add -fpn ... -pad ... -layer ... -footprint`
- `library add -g ... -layer ... -footprint`

More detailed symbol geometry execution and external parts DB merging keep diagnostics entry points. Unsupported commands are written to diagnostics so future format coverage can be expanded incrementally.
