<a id="top"></a>
# AEDB JSON Schema 变更记录 / AEDB JSON Schema Changelog

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

## 0.5.0

- `PadPropertyModel` 新增 `raw_points`，用于保存 AEDB polygonal pad 的原始顶点。
- `metadata.output_schema_version` 现在输出 AEDB JSON schema 版本 `0.5.0`。

## 0.4.0

- `PolygonPrimitiveModel` 新增 `voids`，用于保存 polygon 内部 void 的 id、raw points、arcs、bbox 和 area。
- `metadata.output_schema_version` 现在输出 AEDB JSON schema 版本 `0.4.0`。

## 0.3.0

- 新增必填 metadata 字段 `project_version`。
- 将 `metadata.parser_version` 的含义调整为 AEDB 解析器版本。
- `metadata.output_schema_version` 现在输出 AEDB JSON schema 版本 `0.3.0`。

## 0.2.0

- 新增 metadata 版本字段 `parser_version` 和 `output_schema_version`。
- 保持 AEDB stackup 层直接输出到顶层 `layers`。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

## 0.5.0

- Added `raw_points` to `PadPropertyModel` for AEDB polygonal pad vertices.
- `metadata.output_schema_version` now reports AEDB JSON schema version `0.5.0`.

## 0.4.0

- Added `voids` to `PolygonPrimitiveModel` for polygon-internal void id, raw points, arcs, bbox, and area.
- `metadata.output_schema_version` now reports AEDB JSON schema version `0.4.0`.

## 0.3.0

- Added required metadata field `project_version`.
- Changed the meaning of `metadata.parser_version` to AEDB parser version.
- `metadata.output_schema_version` now reports AEDB JSON schema version `0.3.0`.

## 0.2.0

- Added metadata version fields `parser_version` and `output_schema_version`.
- Kept AEDB stackup layers directly under top-level `layers`.
