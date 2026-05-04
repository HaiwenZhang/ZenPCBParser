<a id="top"></a>
# AuroraDB JSON Schema 变更记录 / AuroraDB JSON Schema Changelog

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

## 0.2.0

- 将主要 AuroraDB JSON schema 从原始 block-tree 导出调整为与 AEDB 风格一致的结构化模型。
- 新增显式结构字段：`layout`、`layers`、`parts`、`nets`、`components`、`footprints`、`pad_templates`、`part_pads`、geometry references。
- 新增可选 `raw_blocks`，供仍需原始 `CeIODataBlock` 树的调用方使用。

## 0.1.0

- 新增第一版 AuroraDB JSON schema，用于描述 `AuroraDBPackage.to_dict(...)` 输出。
- 新增必填顶层字段 `metadata`、`root`、`summary`、`diagnostics`。
- 新增完整 JSON 导出时使用的可选 block-tree 字段 `layout`、`parts`、`layers`。
- 新增 AuroraDB block 与 item 节点的递归 schema 定义。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

## 0.2.0

- Changed the primary AuroraDB JSON schema from raw block-tree export to an AEDB-style structured model.
- Added explicit typed sections for `layout`, `layers`, `parts`, `nets`, `components`, `footprints`, `pad_templates`, `part_pads`, and geometry references.
- Added optional `raw_blocks` for callers that still need the original `CeIODataBlock` trees.

## 0.1.0

- Added the first AuroraDB JSON schema for `AuroraDBPackage.to_dict(...)` payloads.
- Added required top-level `metadata`, `root`, `summary`, and `diagnostics` fields.
- Added optional block-tree fields `layout`, `parts`, and `layers` for full JSON exports.
- Added recursive schema definitions for AuroraDB block and item nodes.
