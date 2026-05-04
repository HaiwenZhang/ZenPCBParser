<a id="top"></a>
# AuroraDB JSON 输出结构说明 / AuroraDB JSON Output Structure

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

本文档说明 Aurora Translator 当前 AuroraDB 解析输出的 JSON 结构。机器可读 schema 由 `auroradb.schema.auroradb_json_schema()` 定义，路径为 [auroradb_schema.json](auroradb_schema.json)。

## 版本

- 当前项目版本：`1.0.26`
- 当前 AuroraDB 解析器版本：`0.2.13`
- 当前 AuroraDB JSON schema 版本：`0.2.0`
- AuroraDB 读取、AAF 命令执行、AuroraDB 派生逻辑变化时，更新 `auroradb.version.AURORADB_PARSER_VERSION`。
- AuroraDB JSON 字段增删、字段含义或结构变化时，更新 `auroradb.version.AURORADB_JSON_SCHEMA_VERSION`。

## 生成方式

```powershell
uv run python .\main.py auroradb schema -o .\auroradb\docs\auroradb_schema.json
```

## 顶层结构

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `metadata` | object | 版本信息。 |
| `root` | string/null | AuroraDB 目录路径；内存对象为 `null`。 |
| `summary` | object | AuroraDB 摘要统计。 |
| `diagnostics` | array | 非致命读取或转换诊断。 |
| `layout` | object/null | `layout.db` 的结构化内容，包括 units、stackup、shapes、via templates、nets。 |
| `layers` | array | `layers/*.lyr` 的结构化内容，包括 components、logic layers、net geometries。 |
| `parts` | object/null | `parts.db` 的结构化内容，包括 parts、schematic symbols、footprints。 |
| `raw_blocks` | object/null | 可选原始 block tree，仅 `--include-raw-blocks` 时输出。 |

## metadata

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `project_version` | string | 生成该 AuroraDB JSON 的 Aurora Translator 项目版本。 |
| `parser_version` | string | 生成该 AuroraDB JSON 的 AuroraDB 解析器版本。 |
| `output_schema_version` | string | 当前 AuroraDB JSON schema 版本。 |

## summary

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `has_layout` | boolean | 是否读取到 `layout.db`。 |
| `has_parts` | boolean | 是否读取到 `parts.db`。 |
| `units` | string/null | layout 单位。 |
| `metal_layer_count` | integer | 金属层数量。 |
| `layer_count` | integer | AuroraDB layer id 表中记录的层数量。 |
| `logic_layer_count` | integer | 逻辑层数量。 |
| `component_count` | integer | layout 中的组件实例数量。 |
| `net_count` | integer | 网络数量。 |
| `net_pin_count` | integer | 网络 pin 绑定数量。 |
| `net_via_count` | integer | 网络 via 绑定数量。 |
| `net_geometry_count` | integer | 网络几何数量。 |
| `shape_count` | integer | 几何 symbol 数量。 |
| `via_template_count` | integer | via template 数量。 |
| `part_count` | integer | part 数量。 |
| `symbol_count` | integer | schematic symbol 数量。 |
| `footprint_count` | integer | footprint symbol 数量。 |
| `layer_names` | array | 金属层名称。 |
| `net_names` | array | 网络名称。 |
| `part_names` | array | part 名称。 |

## layout

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `units` | string/null | layout 单位。 |
| `outline` | object/null | board outline 的原始节点。 |
| `layer_stackup` | object/null | 金属层顺序、`next_layer_id`、layer name/id 映射。 |
| `shapes` | array | `GeomSymbols/ShapeList` 中的 shape symbol。 |
| `via_templates` | array | `GeomSymbols/ViaList` 中的 via template。 |
| `nets` | array | `Nets` 中的网络、pin 绑定、via 绑定。 |

## layers

每个 layer 对象包含：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `name` | string | 金属层名称。 |
| `id` | integer/null | layer id。 |
| `type` | string/null | layer 类型。 |
| `components` | array | 组件实例，包含 part、component layer、location、value。 |
| `logic_layers` | array | 该金属层下的 logic layer。 |
| `net_geometries` | array | 按网络分组的 `NetGeom` geometry reference。 |
| `raw` | object/null | 原始 `MetalLayer` block 节点。 |

## parts

`parts` 包含：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `parts` | array | `PartList` 中的 part、part info、pin、footprint/symbol 引用。 |
| `schematic_symbols` | array | `SymbolList` 中的 schematic symbol。 |
| `footprints` | array | `FootprintList` 中的 footprint、pad template、metal layer、part pad。 |

## raw block tree

AuroraDB block tree 使用递归节点结构表示：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `kind` | `"block"`/`"item"` | 节点类型。 |
| `name` | string | block 或 item 名称。 |
| `children` | array | block 子节点，仅 `kind="block"` 时存在。 |
| `values` | array | item 值列表，仅 `kind="item"` 时存在。 |

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

This document describes the current JSON structure emitted by Aurora Translator for AuroraDB parsing. The machine-readable schema is defined by `auroradb.schema.auroradb_json_schema()` and is available at [auroradb_schema.json](auroradb_schema.json).

## Versions

- Current project version: `1.0.26`
- Current AuroraDB parser version: `0.2.13`
- Current AuroraDB JSON schema version: `0.2.0`
- Update `auroradb.version.AURORADB_PARSER_VERSION` when AuroraDB reading, AAF command execution, or AuroraDB generation logic changes.
- Update `auroradb.version.AURORADB_JSON_SCHEMA_VERSION` when AuroraDB JSON fields, field meanings, or structure change.

## Generation

```powershell
uv run python .\main.py auroradb schema -o .\auroradb\docs\auroradb_schema.json
```

## Top-Level Structure

| Field | Type | Description |
| --- | --- | --- |
| `metadata` | object | Version information. |
| `root` | string/null | AuroraDB directory path; `null` for in-memory objects. |
| `summary` | object | AuroraDB summary statistics. |
| `diagnostics` | array | Non-fatal read or conversion diagnostics. |
| `layout` | object/null | Structured content from `layout.db`, including units, stackup, shapes, via templates, and nets. |
| `layers` | array | Structured content from `layers/*.lyr`, including components, logic layers, and net geometries. |
| `parts` | object/null | Structured content from `parts.db`, including parts, schematic symbols, and footprints. |
| `raw_blocks` | object/null | Optional raw block tree, emitted only with `--include-raw-blocks`. |

## metadata

| Field | Type | Description |
| --- | --- | --- |
| `project_version` | string | Aurora Translator project version that generated this AuroraDB JSON. |
| `parser_version` | string | AuroraDB parser version that generated this AuroraDB JSON. |
| `output_schema_version` | string | Current AuroraDB JSON schema version. |

## summary

| Field | Type | Description |
| --- | --- | --- |
| `has_layout` | boolean | Whether `layout.db` was read. |
| `has_parts` | boolean | Whether `parts.db` was read. |
| `units` | string/null | Layout units. |
| `metal_layer_count` | integer | Number of metal layers. |
| `layer_count` | integer | Number of layers recorded in the AuroraDB layer id table. |
| `logic_layer_count` | integer | Number of logic layers. |
| `component_count` | integer | Number of component instances in the layout. |
| `net_count` | integer | Number of nets. |
| `net_pin_count` | integer | Number of net pin bindings. |
| `net_via_count` | integer | Number of net via bindings. |
| `net_geometry_count` | integer | Number of net geometries. |
| `shape_count` | integer | Number of geometry symbols. |
| `via_template_count` | integer | Number of via templates. |
| `part_count` | integer | Number of parts. |
| `symbol_count` | integer | Number of schematic symbols. |
| `footprint_count` | integer | Number of footprint symbols. |
| `layer_names` | array | Metal layer names. |
| `net_names` | array | Net names. |
| `part_names` | array | Part names. |

## layout

| Field | Type | Description |
| --- | --- | --- |
| `units` | string/null | Layout units. |
| `outline` | object/null | Raw node for the board outline. |
| `layer_stackup` | object/null | Metal layer order, `next_layer_id`, and layer name/id mappings. |
| `shapes` | array | Shape symbols from `GeomSymbols/ShapeList`. |
| `via_templates` | array | Via templates from `GeomSymbols/ViaList`. |
| `nets` | array | Nets, pin bindings, and via bindings from `Nets`. |

## layers

Each layer object contains:

| Field | Type | Description |
| --- | --- | --- |
| `name` | string | Metal layer name. |
| `id` | integer/null | Layer id. |
| `type` | string/null | Layer type. |
| `components` | array | Component instances, including part, component layer, location, and value. |
| `logic_layers` | array | Logic layers under this metal layer. |
| `net_geometries` | array | `NetGeom` geometry references grouped by net. |
| `raw` | object/null | Raw `MetalLayer` block node. |

## parts

`parts` contains:

| Field | Type | Description |
| --- | --- | --- |
| `parts` | array | Parts from `PartList`, including part info, pins, and footprint/symbol references. |
| `schematic_symbols` | array | Schematic symbols from `SymbolList`. |
| `footprints` | array | Footprints from `FootprintList`, including pad templates, metal layers, and part pads. |

## Raw Block Tree

AuroraDB block trees are represented as recursive nodes:

| Field | Type | Description |
| --- | --- | --- |
| `kind` | `"block"`/`"item"` | Node type. |
| `name` | string | Block or item name. |
| `children` | array | Child block nodes, present only when `kind="block"`. |
| `values` | array | Item values, present only when `kind="item"`. |
