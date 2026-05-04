<a id="top"></a>
# Semantic JSON 输出结构说明 / Semantic JSON Output Structure

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

本文档说明 Aurora Translator 当前 semantic 语义层输出的 JSON 结构。机器可读 schema 路径为 [semantic_schema.json](semantic_schema.json)。

## 版本

- 当前项目版本：`1.0.42`
- 当前 Semantic parser 版本：`0.7.1`
- 当前 Semantic JSON schema 版本：`0.7.0`

## 生成方式

```powershell
uv run python .\main.py semantic schema -o .\semantic\docs\semantic_schema.json
```

## 转换方式

```powershell
uv run python .\main.py semantic from-json aedb .\out\board.json
uv run python .\main.py semantic from-json aedb .\out\board.json -o .\out --semantic-output board.semantic.json
uv run python .\main.py semantic from-json auroradb .\out\auroradb.json
uv run python .\main.py semantic from-json auroradb .\out\auroradb.json -o .\out --semantic-output auroradb.semantic.json
uv run python .\main.py semantic from-json odbpp .\out\odbpp.json
uv run python .\main.py semantic from-json odbpp .\out\odbpp.json -o .\out --semantic-output odbpp.semantic.json
uv run python .\main.py semantic from-source aedb <path-to-board.aedb>
uv run python .\main.py semantic from-source aedb <path-to-board.aedb> -o .\out --semantic-output board.semantic.json
uv run python .\main.py semantic from-source odbpp <odbpp-dir-or-archive>
uv run python .\main.py semantic from-source odbpp <odbpp-dir-or-archive> -o .\out --semantic-output odbpp.semantic.json
uv run python .\main.py semantic to-aaf .\out\board.semantic.json -o .\out\aurora_aaf_from_semantic
uv run python .\main.py semantic to-auroradb .\out\board.semantic.json -o .\out\auroradb_from_semantic
```

对于 ODB++ 源路径，semantic CLI 默认优先使用 `aurora_odbpp_native` PyO3 模块；传入 `--rust-binary` 时会强制走 `odbpp_parser` CLI。

## 顶层结构

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `metadata` | object | 项目版本、semantic parser/schema 版本和源格式版本信息。 |
| `units` | string/null | 语义坐标单位。 |
| `summary` | object | layer、material、shape、via template、net、component、footprint、pin、pad、via、primitive、edge 和 diagnostic 计数。 |
| `layers` | array | 语义层列表。 |
| `materials` | array | 语义材料列表，包含导电率、介电常数和介质损耗角正切等属性。 |
| `shapes` | array | AuroraDB-profile 语义 shape，包含 `Circle`、`Rectangle`、`RoundedRectangle` 等几何。 |
| `via_templates` | array | AuroraDB-profile via template，包含 barrel、pad、antipad shape 引用。 |
| `nets` | array | 语义网络列表。 |
| `components` | array | 语义器件列表；可包含源 component 属性。 |
| `footprints` | array | 语义 footprint 列表；可包含源 package/footprint 属性。 |
| `pins` | array | 语义引脚列表。 |
| `pads` | array | 语义 pad 列表。 |
| `vias` | array | 语义过孔列表。 |
| `primitives` | array | 语义几何图元列表。 |
| `connectivity` | array | 连接图边。 |
| `diagnostics` | array | 语义转换诊断。 |
| `board_outline` | object | 可选源 board outline/profile 几何提示；可包含 polygon 顶点和 arc 顶点。 |

Geometry hint 字段是格式中立扩展入口。当前 `footprints.geometry`、`via_templates.geometry`、`pads.geometry`、`vias.geometry`、`primitives.geometry` 和 `board_outline` 使用 typed hint model，并保留 extra metadata 逃生口。ODB++ 转换用它保存 footprint/package body outline、matched via pad evidence、via drill tool metadata、via instance geometry hint 和 board outline/profile geometry。attribute 字典用于保留源 component/package metadata，供统一访问和 part 导出使用。

## source 引用

每个语义对象都有 `source`，用于回溯源格式字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `source_format` | string | `aedb`、`auroradb` 或 `odbpp`。 |
| `path` | string/null | 源 JSON 中的字段路径。 |
| `raw_id` | string/null | 源格式原始 id。 |

## connectivity

| kind | 说明 |
| --- | --- |
| `component-footprint` | component 关联 footprint。 |
| `component-pin` | component 拥有 pin。 |
| `component-pad` | component 拥有已放置 pad。 |
| `footprint-pad` | footprint 关联 pad。 |
| `pin-pad` | pin 绑定 pad。 |
| `pad-net` | pad 连接 net。 |
| `pin-net` | pin 连接 net。 |
| `via-net` | via 连接 net。 |
| `primitive-net` | primitive 连接 net。 |
| `component-primitive` | primitive 归属于 component。 |

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

This document describes the current JSON structure emitted by Aurora Translator's semantic layer. The machine-readable schema is [semantic_schema.json](semantic_schema.json).

## Versions

- Current project version: `1.0.42`
- Current Semantic parser version: `0.7.1`
- Current Semantic JSON schema version: `0.7.0`

## Generation

```powershell
uv run python .\main.py semantic schema -o .\semantic\docs\semantic_schema.json
```

## Conversion

```powershell
uv run python .\main.py semantic from-json aedb .\out\board.json
uv run python .\main.py semantic from-json aedb .\out\board.json -o .\out --semantic-output board.semantic.json
uv run python .\main.py semantic from-json auroradb .\out\auroradb.json
uv run python .\main.py semantic from-json auroradb .\out\auroradb.json -o .\out --semantic-output auroradb.semantic.json
uv run python .\main.py semantic from-json odbpp .\out\odbpp.json
uv run python .\main.py semantic from-json odbpp .\out\odbpp.json -o .\out --semantic-output odbpp.semantic.json
uv run python .\main.py semantic from-source aedb <path-to-board.aedb>
uv run python .\main.py semantic from-source aedb <path-to-board.aedb> -o .\out --semantic-output board.semantic.json
uv run python .\main.py semantic from-source odbpp <odbpp-dir-or-archive>
uv run python .\main.py semantic from-source odbpp <odbpp-dir-or-archive> -o .\out --semantic-output odbpp.semantic.json
uv run python .\main.py semantic to-aaf .\out\board.semantic.json -o .\out\aurora_aaf_from_semantic
uv run python .\main.py semantic to-auroradb .\out\board.semantic.json -o .\out\auroradb_from_semantic
```

For ODB++ source paths, the semantic CLI prefers the `aurora_odbpp_native` PyO3 module by default; passing `--rust-binary` forces the `odbpp_parser` CLI.

## Top-Level Structure

| Field | Type | Description |
| --- | --- | --- |
| `metadata` | object | Project version, semantic parser/schema versions, and source-format version metadata. |
| `units` | string/null | Semantic coordinate units. |
| `summary` | object | Counts for layers, materials, shapes, via templates, nets, components, footprints, pins, pads, vias, primitives, edges, and diagnostics. |
| `layers` | array | Semantic layers. |
| `materials` | array | Semantic materials with properties such as conductivity, permittivity, and dielectric loss tangent. |
| `shapes` | array | AuroraDB-profile semantic shapes such as `Circle`, `Rectangle`, and `RoundedRectangle`. |
| `via_templates` | array | AuroraDB-profile via templates with barrel, pad, and antipad shape references. |
| `nets` | array | Semantic nets. |
| `components` | array | Semantic components, including source/component attributes when available. |
| `footprints` | array | Semantic footprints, including source package/footprint attributes when available. |
| `pins` | array | Semantic pins. |
| `pads` | array | Semantic pads. |
| `vias` | array | Semantic vias. |
| `primitives` | array | Semantic geometry primitives. |
| `connectivity` | array | Connectivity graph edges. |
| `diagnostics` | array | Semantic conversion diagnostics. |
| `board_outline` | object | Optional source board outline/profile geometry hints, including polygon vertices and arc vertices when available. |

Geometry hint fields are format-neutral extension points. `footprints.geometry`, `via_templates.geometry`, `pads.geometry`, `vias.geometry`, `primitives.geometry`, and `board_outline` now use typed hint models while keeping an extra-metadata escape hatch. ODB++ conversion uses them for footprint/package body outlines, matched via pad evidence, drill tool metadata, via instance geometry hints, and board outline/profile geometry. Attribute dictionaries preserve source component/package metadata for unified access and part export.

## source References

Every semantic object has `source` for tracing back to the source-format field:

| Field | Type | Description |
| --- | --- | --- |
| `source_format` | string | `aedb`, `auroradb`, or `odbpp`. |
| `path` | string/null | Field path inside the source JSON. |
| `raw_id` | string/null | Original source-format id. |

## connectivity

| kind | Description |
| --- | --- |
| `component-footprint` | A component references a footprint. |
| `component-pin` | A component owns a pin. |
| `component-pad` | A component owns a placed pad. |
| `footprint-pad` | A footprint references a pad. |
| `pin-pad` | A pin is bound to a pad. |
| `pad-net` | A pad connects to a net. |
| `pin-net` | A pin connects to a net. |
| `via-net` | A via connects to a net. |
| `primitive-net` | A primitive connects to a net. |
| `component-primitive` | A primitive belongs to a component. |
