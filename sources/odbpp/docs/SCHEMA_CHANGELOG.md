<a id="top"></a>
# ODB++ JSON Schema 变更记录 / ODB++ JSON Schema Changelog

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

## 0.6.0

- `metadata.backend` 现在从固定值扩展为枚举，允许 `rust-native` 和 `rust-cli`。
- `metadata.rust_parser_version` 的字段语义更新为 Rust 解析器实现版本，而不再限定为可执行文件版本。

## 0.5.0

- `layers[].layer_attributes` 新增选定 step layer `attrlist` 键值字段。
- `drill_tools[]` 新增 `thickness`、`user_params` 和 `raw_fields`，用于保存 layer `tools` 顶层 metadata。

## 0.4.0

- 新增顶层 `drill_tools[]`，用于保存选定 step 的 layer tool definitions。
- 新增顶层 `packages[]`，用于保存选定 step 的 EDA package definitions，包括 package pins、outlines 和 package shape records。
- `summary` 新增 `drill_tool_count` 和 `package_count`。

## 0.3.0

- 新增顶层 `symbols[]`，用于保存 ODB++ symbol library feature definitions。
- `summary` 新增 `symbol_count`。
- `nets[].feature_refs[]` 新增 `subnet_type`、`pin_side`、`net_component_index` 和 `net_pin_index`，使 FID 记录可以保留 SNT pin 上下文。

## 0.2.0

- 为 `layers[].features[]` 新增 `feature_index`、`feature_id`、`attributes` 和 `contours`。
- 新增 `SurfaceContour` 和 `ContourVertex` 结构，用于表示 ODB++ surface 记录。
- 为 component 新增 `component_index`、`package_index`、`location`、`rotation`、`mirror`、`properties` 和嵌套 `pins`。
- 新增 `ComponentPin` 记录，用于保存组件下的 `TOP`/`BOT` pin 行。
- 新增 `nets[].feature_refs[]` 和 `nets[].pin_refs[]`，用于保存 EDA `FID` 和 `SNT TOP T/B` 连接引用。

## 0.1.0

- 新增第一版 `ODBLayout` JSON schema。
- 新增必填顶层字段 `metadata`、`summary`、`steps` 和 `diagnostics`。
- 新增可选明细字段 `matrix`、`layers`、`components` 和 `nets`。
- 新增 ODB++ metadata 字段：`project_version`、`parser_version`、`output_schema_version`、`source`、`source_type`、`selected_step`、`backend` 和 `rust_parser_version`。
- 新增 step、matrix layer、选定 step 的 feature、component、net、profile 和 diagnostics 统计字段。
- 新增 feature、component、net、profile 和 matrix row 模型，并保留 tokenized source records，方便后续逐步增强解析精度。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

## 0.6.0

- `metadata.backend` is now an enum that allows both `rust-native` and `rust-cli` instead of a fixed value.
- `metadata.rust_parser_version` now describes the Rust parser implementation version rather than only an executable version.

## 0.5.0

- Added `layers[].layer_attributes` for selected-step layer `attrlist` key/value pairs.
- Added `drill_tools[].thickness`, `drill_tools[].user_params`, and `drill_tools[].raw_fields` for top-level layer `tools` metadata.

## 0.4.0

- Added top-level `drill_tools[]` for selected-step layer tool definitions.
- Added top-level `packages[]` for selected-step EDA package definitions, including package pins, outlines, and package shape records.
- Added `drill_tool_count` and `package_count` to `summary`.

## 0.3.0

- Added top-level `symbols[]` for ODB++ symbol library feature definitions.
- Added `symbol_count` to `summary`.
- Added `subnet_type`, `pin_side`, `net_component_index`, and `net_pin_index` to `nets[].feature_refs[]` so FID records can retain SNT pin context.

## 0.2.0

- Added `feature_index`, `feature_id`, `attributes`, and `contours` to `layers[].features[]`.
- Added `SurfaceContour` and `ContourVertex` structures for ODB++ surface records.
- Added component placement fields including `component_index`, `package_index`, `location`, `rotation`, `mirror`, `properties`, and nested `pins`.
- Added `ComponentPin` records for child `TOP`/`BOT` component pin lines.
- Added `nets[].feature_refs[]` and `nets[].pin_refs[]` for EDA `FID` and `SNT TOP T/B` connectivity references.

## 0.1.0

- Added the first ODB++ JSON schema for `ODBLayout`.
- Added required top-level fields `metadata`, `summary`, `steps`, and `diagnostics`.
- Added optional detail sections `matrix`, `layers`, `components`, and `nets`.
- Added ODB++ metadata fields: `project_version`, `parser_version`, `output_schema_version`, `source`, `source_type`, `selected_step`, `backend`, and `rust_parser_version`.
- Added summary counts and name lists for steps, matrix layers, selected-step features, components, nets, profiles, and diagnostics.
- Added feature, component, net, profile, and matrix row models that preserve tokenized source records for future parser refinement.
