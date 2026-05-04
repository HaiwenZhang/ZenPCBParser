<a id="top"></a>
# ODB++ JSON 输出结构说明 / ODB++ JSON Output Structure

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

本文档说明 Aurora Translator 当前 ODB++ 解析输出的 JSON 结构。机器可读 schema 由 Pydantic 模型生成，路径为 [odbpp_schema.json](odbpp_schema.json)。

## 版本

- 当前项目版本：`1.0.42`
- 当前 ODB++ 解析器版本：`0.6.3`
- 当前 ODB++ JSON schema 版本：`0.6.0`
- 项目发布或集成格式级变更时更新 `PROJECT_VERSION`，并写入 `metadata.project_version`。
- 解析逻辑、容器读取、性能或 diagnostics 行为变化时，更新 `metadata.parser_version`。
- JSON 字段增删、字段含义或结构变化时，更新 `metadata.output_schema_version`。

## 生成方式

```powershell
uv run python .\main.py odbpp schema -o .\odbpp\docs\odbpp_schema.json
```

## 解析方式

```powershell
uv run python .\main.py odbpp parse <odbpp-dir-or-archive> -o .\out\odbpp.json
uv run python .\main.py odbpp parse <odbpp-dir-or-archive> --step pcb --summary-only
uv run python .\main.py odbpp to-auroradb <odbpp-dir-or-archive> -o .\out\odbpp_auroradb --odbpp-output .\out\odbpp.json --semantic-output .\out\odbpp.semantic.json
uv run python .\main.py odbpp parse <odbpp-dir-or-archive> --rust-binary .\crates\odbpp_parser\target\release\odbpp_parser.exe -o .\out\odbpp_cli.json
```

ODB++ 解析由 `crates/odbpp_parser` 的共享 Rust 解析核心执行。Python 集成层默认优先导入 `aurora_odbpp_native` PyO3 模块；如果未安装 native 模块，或者显式传入 `--rust-binary`，则回退到 `odbpp_parser` CLI。无论哪条路径，Python 都会注入项目/解析器/schema 版本，并用 Pydantic 校验结果。

## 顶层结构

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `metadata` | object | 项目版本、ODB++ 解析器版本、schema 版本、源路径、容器类型和 Rust 后端信息。 |
| `summary` | object | step、layer、feature、component、net 和 diagnostics 统计。 |
| `matrix` | object/null | 从 `matrix/matrix` 解析出的 layer/row 信息。 |
| `steps` | array | 发现的 ODB++ step 及每个 step 的 profile 记录。 |
| `symbols` | array/null | 从 `symbols/<name>/features` 解析出的 ODB++ symbol library feature definitions；`--summary-only` 时为 `null`。 |
| `drill_tools` | array/null | 从选定 step 的 `layers/<layer>/tools` 文件解析出的 layer tool definitions；`--summary-only` 时为 `null`。 |
| `packages` | array/null | 从选定 step 的 `eda/data` 解析出的 EDA package definitions，包含 package pins 和 package geometry；`--summary-only` 时为 `null`。 |
| `layers` | array/null | 选定 step 的 layer `features` 明细；`--summary-only` 时为 `null`。 |
| `components` | array/null | 选定 step 的层级化组件记录，包含子 pin 和 PRP 属性；`--summary-only` 时为 `null`。 |
| `nets` | array/null | 选定 step 的 net 记录，包含可解析的 EDA feature/pin 引用；`--summary-only` 时为 `null`。 |
| `diagnostics` | array | 非致命解析诊断，例如暂不支持的 `.Z` 压缩成员。 |

## 明细记录

- `layers[].layer_attributes` 保留选定 step layer `attrlist` 键值，例如 copper weight、dielectric thickness、material 和电气属性 hint。
- `layers[].features[]` 保留 ODB++ 零基 `feature_index`、源 `feature_id`、分号属性、`P/L/A` 基础点位，以及 `S ... OB/OS/OC/OE ... SE` surface contour。
- `symbols[]` 保留已解析的 symbol library feature definitions，使 semantic 层可以转换自定义 pad symbol。
- `drill_tools[]` 保留 layer `tools` blocks，例如 via drill size、finish size，以及 thickness、user params、raw fields 等顶层 metadata；semantic 层可结合 matrix start/end layer 使用。
- `packages[]` 保留 EDA package definitions、package pins、outline geometry 和常见 pin geometry records（`RC`、`CR`、`SQ` 与 contour），用于 footprint 重建。
- `components[]` 只表示组件放置记录（`CMP`/`COMP`），`TOP`/`BOT` pin 行会进入 `components[].pins[]`。
- `components[].properties` 保留 `VALUE`、`PART_NUMBER`、`PACKAGE_NAME` 等 `PRP` 属性。
- `nets[].feature_refs[]` 保留 EDA `FID` 记录，在存在 `LYR` 表时解析 layer name，并在 FID 属于 component pin group 时携带关联的 `SNT TOP T/B` pin 上下文。
- `nets[].pin_refs[]` 保留 `SNT TOP T/B` 组件 pin 引用，用于 semantic pin-to-net 绑定。

## 当前限制

- 当前解析器已重建 semantic/AuroraDB 转换所需的常见连接关系和基础几何，但仍不保证完整还原所有 ODB++ 语义。
- 复杂 negative/void 几何、thermal/antipad 约束、soldermask/paste 语义和完整 material library 重建仍是后续增量工作。
- negative polarity、void 细节和材料/叠层物理属性仅在当前已解析记录直接暴露时保留。
- `.Z` 压缩成员暂不直接解压，会进入 diagnostics。
- `features`、`components`、`nets` 仍保留 tokenized source records，方便后续继续补充更精确字段。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

This document describes the current JSON structure emitted by Aurora Translator for ODB++ parsing. The machine-readable schema is generated from Pydantic models and is available at [odbpp_schema.json](odbpp_schema.json).

## Versions

- Current project version: `1.0.42`
- Current ODB++ parser version: `0.6.3`
- Current ODB++ JSON schema version: `0.6.0`
- Update `PROJECT_VERSION` for project releases or integrated format-level changes; it is emitted as `metadata.project_version`.
- Update `metadata.parser_version` when parsing logic, container handling, performance, or diagnostics behavior changes.
- Update `metadata.output_schema_version` when JSON fields, field meanings, or structure change.

## Generation

```powershell
uv run python .\main.py odbpp schema -o .\odbpp\docs\odbpp_schema.json
```

## Parsing

```powershell
uv run python .\main.py odbpp parse <odbpp-dir-or-archive> -o .\out\odbpp.json
uv run python .\main.py odbpp parse <odbpp-dir-or-archive> --step pcb --summary-only
uv run python .\main.py odbpp to-auroradb <odbpp-dir-or-archive> -o .\out\odbpp_auroradb --odbpp-output .\out\odbpp.json --semantic-output .\out\odbpp.semantic.json
uv run python .\main.py odbpp parse <odbpp-dir-or-archive> --rust-binary .\crates\odbpp_parser\target\release\odbpp_parser.exe -o .\out\odbpp_cli.json
```

ODB++ parsing is performed by the shared Rust parser core in `crates/odbpp_parser`. The Python integration layer prefers the `aurora_odbpp_native` PyO3 module; if the native module is not installed, or when `--rust-binary` is passed explicitly, it falls back to the `odbpp_parser` CLI. Both paths inject project/parser/schema versions and validate the result through Pydantic.

## Top-Level Structure

| Field | Type | Description |
| --- | --- | --- |
| `metadata` | object | Project version, ODB++ parser version, schema version, source path, container type, and Rust backend metadata. |
| `summary` | object | Counts for steps, layers, features, components, nets, and diagnostics. |
| `matrix` | object/null | Layer/row information parsed from `matrix/matrix`. |
| `steps` | array | Discovered ODB++ steps and each step's profile records. |
| `symbols` | array/null | ODB++ symbol library feature definitions from `symbols/<name>/features`; `null` in `--summary-only` mode. |
| `drill_tools` | array/null | Layer tool definitions from selected-step `layers/<layer>/tools` files; `null` in `--summary-only` mode. |
| `packages` | array/null | EDA package definitions from selected-step `eda/data`, including package pins and package geometry; `null` in `--summary-only` mode. |
| `layers` | array/null | Layer `features` details for the selected step; `null` in `--summary-only` mode. |
| `components` | array/null | Hierarchical component records for the selected step, including child pins and PRP properties; `null` in `--summary-only` mode. |
| `nets` | array/null | Net records discovered in the selected step, including EDA feature and pin references when available; `null` in `--summary-only` mode. |
| `diagnostics` | array | Non-fatal parsing diagnostics, such as unsupported `.Z` compressed members. |

## metadata

| Field | Type | Description |
| --- | --- | --- |
| `project_version` | string | Aurora Translator project version that generated this payload. |
| `parser_version` | string | ODB++ parser version. |
| `output_schema_version` | string | ODB++ JSON schema version. |
| `source` | string | ODB++ source directory or archive path. |
| `source_type` | string | Source container type: `directory`, `zip`, `tgz`, or `tar`. |
| `selected_step` | string/null | Step used for detailed parsing; `null` when no step is discovered. |
| `backend` | string | Rust backend used by Aurora Translator: `rust-native` or `rust-cli`. |
| `rust_parser_version` | string | Version reported by the Rust `odbpp_parser` parser implementation. |

## summary

| Field | Description |
| --- | --- |
| `step_count` | Number of steps discovered under `steps/`. |
| `layer_count` | Number of rows parsed from `matrix/matrix`. |
| `board_layer_count` | Number of matrix rows with `context=board`. |
| `signal_layer_count` | Number of matrix rows with `type=signal`. |
| `component_layer_count` | Number of matrix rows with `type=component`. |
| `feature_layer_count` | Number of layers with parsed `features` files. |
| `feature_count` | Number of parsed feature records. |
| `symbol_count` | Number of parsed symbol-library feature files. |
| `drill_tool_count` | Number of parsed layer tool records. |
| `package_count` | Number of parsed EDA package definitions. |
| `component_count` | Number of parsed component placement records. |
| `net_count` | Number of unique discovered net names. |
| `profile_record_count` | Number of profile records. |
| `diagnostic_count` | Number of diagnostics. |
| `step_names` / `layer_names` / `net_names` | Name lists for quick inspection and indexing. |

## Detail Records

- `layers[].layer_attributes` preserves selected-step layer `attrlist` key/value pairs such as copper weight, dielectric thickness, material, and electrical-property hints when present.
- `layers[].features[]` preserves the zero-based ODB++ `feature_index`, source `feature_id`, semicolon attributes, basic points for `P/L/A` records, and surface contours for `S ... OB/OS/OC/OE ... SE` records.
- `symbols[]` preserves parsed symbol-library feature definitions so custom pad symbols can be converted by the semantic layer.
- `drill_tools[]` preserves layer `tools` blocks such as via drill size and finish size, plus top-level metadata such as thickness, user parameters, and raw fields. The semantic layer can combine this data with matrix start/end layers.
- `packages[]` preserves EDA package definitions, package pins, outline geometry, and common pin geometry records (`RC`, `CR`, `SQ`, and contours) for footprint reconstruction.
- `components[]` now represents only component placements (`CMP`/`COMP`). Child `TOP`/`BOT` pin lines are nested under `components[].pins[]`.
- `components[].properties` preserves `PRP` records such as `VALUE`, `PART_NUMBER`, and `PACKAGE_NAME`.
- `nets[].feature_refs[]` preserves EDA `FID` records, resolves layer names from the EDA `LYR` table when present, and carries associated `SNT TOP T/B` pin context when the FID belongs to a component pin group.
- `nets[].pin_refs[]` preserves `SNT TOP T/B` component-pin references for semantic pin-to-net binding.

## Current Limitations

- The parser now reconstructs common connectivity and geometry needed by the semantic AuroraDB path, but it does not yet guarantee complete ODB++ semantic reconstruction.
- Complex negative/void geometry, thermal/antipad constraints, soldermask/paste semantics, and full material-library reconstruction are incremental work.
- Negative polarity, void details, and material/stackup physical properties are preserved only where the current records expose them directly.
- `.Z` compressed members are not decompressed directly and are reported in diagnostics.
- `features`, `components`, and `nets` continue to keep tokenized source records so more precise fields can be added incrementally.
