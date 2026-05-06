<a id="top"></a>
# AEDB JSON Schema 变更记录 / AEDB JSON Schema Changelog

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

## 0.13.0

- 独立的 `AEDBDefBinaryLayout` schema 提升到 `0.13.0`：`domain.padstacks[]` 新增 `hole_shape`、`hole_parameters`、`hole_offset_x`、`hole_offset_y`、`hole_rotation`，保存 `.def` text padstack `hle(...)` 字段。
- `domain.padstacks[].layer_pads[]` 新增 `antipad_parameters`、`antipad_offset_x`、`antipad_offset_y`、`antipad_rotation`、`thermal_parameters`、`thermal_offset_x`、`thermal_offset_y` 和 `thermal_rotation`，保留 `ant(...)` / `thm(...)` source 字段。默认 PyEDB `AEDBLayout` schema 不受影响，仍为 `0.5.0`。

## 0.12.0

- 独立的 `AEDBDefBinaryLayout` schema 提升到 `0.12.0`：`domain.materials[]` 新增 `conductivity`、`permittivity` 和 `dielectric_loss_tangent`，保存 `.def` text material block 中反解出的材料物性字段。默认 PyEDB `AEDBLayout` schema 不受影响，仍为 `0.5.0`。

## 0.11.0

- 独立的 `AEDBDefBinaryLayout` schema 提升到 `0.11.0`：`domain.binary_polygon_records[].net_index` / `net_name` 从预留字段变为已恢复字段，保存 native `.def` primitive 流上下文中的真实 polygon/void net owner。

## 0.10.0

- 独立的 `AEDBDefBinaryLayout` schema 提升到 `0.10.0`：`domain.padstack_instance_definitions[]` 新增从 7-byte object 前缀和后续 `$begin ''` text block 恢复的 raw padstack-instance definition 映射，字段包括 `raw_definition_index`、`padstack_id/name`、`first_layer_id/name`、`last_layer_id/name`、`first_layer_positive` 和 solder-ball layer id/name。
- `domain.summary.padstack_instance_definition_count` 新增映射计数。默认 PyEDB `AEDBLayout` schema 不受影响，仍为 `0.5.0`。

## 0.9.0

- 独立的 `AEDBDefBinaryLayout` schema 提升到 `0.9.0`：`domain.binary_padstack_instance_records[]` 新增 `drill_diameter`，保存从原生 `.def` padstack instance tail 中恢复的钻孔直径，单位为米；没有可靠钻孔字段的 component pad 继续输出 `null`。
- `domain.padstacks[].layer_pads[]` 新增 `pad_parameters`、`pad_offset_x`、`pad_offset_y` 和 `pad_rotation`，保存 `.def` text padstack `pad(shp=..., Szs(...), X=..., Y=..., R=...)` 中的原始尺寸和变换字符串，供无 ANF 转换恢复真实 pad shape。
- 默认 PyEDB `AEDBLayout` schema 不受影响，仍为 `0.5.0`。

## 0.8.0

- 独立的 `AEDBDefBinaryLayout` schema 提升到 `0.8.0`：`domain.binary_polygon_records[]` 新增原生 `.def` polygon/void 记录，字段包括全局 `offset`、`count_offset`、`coordinate_offset`、`geometry_id`、`parent_geometry_id`、`is_void`、`layer_id`、`layer_name`、预留 `net_index` / `net_name`、`item_count`、`point_count`、`arc_segment_count` 和 raw-point `items`。
- `domain.binary_geometry` 新增 polygon 汇总计数：`polygon_record_count`、`polygon_outer_record_count`、`polygon_void_record_count`、`polygon_point_count` 和 `polygon_arc_segment_count`。默认 PyEDB `AEDBLayout` schema 不受影响，仍为 `0.5.0`。

## 0.7.0

- 独立的 `AEDBDefBinaryLayout` schema 提升到 `0.7.0`：`domain.binary_padstack_instance_records[]` 新增 EDB `PadstackInstance` 记录，字段包括 `offset`、`geometry_id`、`name`、`name_kind`、`net_index`、`net_name`、`raw_owner_index`、`raw_definition_index`、`x`、`y`、`rotation`、`secondary_name` 和 `secondary_id`。
- `domain.binary_geometry` 新增 padstack instance 汇总计数：`padstack_instance_record_count`、`component_pin_padstack_instance_record_count`、`named_via_padstack_instance_record_count`、`unnamed_padstack_instance_record_count` 和 `padstack_instance_secondary_name_count`。默认 PyEDB `AEDBLayout` schema 不受影响，仍为 `0.5.0`。

## 0.6.0

- 独立的 `AEDBDefBinaryLayout` schema 提升到 `0.6.0`：`domain.layout_nets` 新增 `.def` 二进制 net table，`domain.summary.layout_net_count` 新增 layout net 计数。
- `domain.binary_path_records[]` 新增 `net_index`、`net_name`、`layer_id` 和 `layer_name`，用于保存从二进制 path preamble 解出的 owner 信息。默认 PyEDB `AEDBLayout` schema 不受影响，仍为 `0.5.0`。

## 0.5.0

- `PadPropertyModel` 新增 `raw_points`，用于保存 AEDB polygonal pad 的原始顶点。
- `metadata.output_schema_version` 现在输出 AEDB JSON schema 版本 `0.5.0`。
- 独立的 `AEDBDefBinaryLayout` schema 也提升到 `0.5.0`：`domain.binary_path_records` 新增二进制 path record 的偏移、几何 ID、宽度、点列、arc-height marker 和 Line/Larc segment 计数。默认 PyEDB `AEDBLayout` schema 除 `PadPropertyModel.raw_points` 外不受该字段影响。

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

## 0.13.0

- The separate `AEDBDefBinaryLayout` schema is bumped to `0.13.0`: `domain.padstacks[]` adds `hole_shape`, `hole_parameters`, `hole_offset_x`, `hole_offset_y`, and `hole_rotation`, preserving `.def` text-padstack `hle(...)` fields.
- `domain.padstacks[].layer_pads[]` adds `antipad_parameters`, `antipad_offset_x`, `antipad_offset_y`, `antipad_rotation`, `thermal_parameters`, `thermal_offset_x`, `thermal_offset_y`, and `thermal_rotation`, preserving `ant(...)` / `thm(...)` source fields. The default PyEDB `AEDBLayout` schema is unaffected and remains `0.5.0`.

## 0.12.0

- The separate `AEDBDefBinaryLayout` schema is bumped to `0.12.0`: `domain.materials[]` adds `conductivity`, `permittivity`, and `dielectric_loss_tangent`, preserving material-property fields decoded from `.def` text material blocks. The default PyEDB `AEDBLayout` schema is unaffected and remains `0.5.0`.

## 0.11.0

- The separate `AEDBDefBinaryLayout` schema is bumped to `0.11.0`: `domain.binary_polygon_records[].net_index` / `net_name` are no longer reserved-only fields and now carry the recovered native `.def` polygon/void net owner from primitive-stream context.

## 0.10.0

- The separate `AEDBDefBinaryLayout` schema is bumped to `0.10.0`: `domain.padstack_instance_definitions[]` adds raw padstack-instance definition mappings recovered from the 7-byte object prefix plus the following `$begin ''` text block. Fields include `raw_definition_index`, `padstack_id/name`, `first_layer_id/name`, `last_layer_id/name`, `first_layer_positive`, and solder-ball layer id/name.
- `domain.summary.padstack_instance_definition_count` adds the mapping count. The default PyEDB `AEDBLayout` schema is unaffected and remains `0.5.0`.

## 0.9.0

- The separate `AEDBDefBinaryLayout` schema is bumped to `0.9.0`: `domain.binary_padstack_instance_records[]` adds `drill_diameter`, the drill diameter recovered from the native `.def` padstack-instance tail, in meters. Component pads without a reliable drill field continue to emit `null`.
- `domain.padstacks[].layer_pads[]` adds `pad_parameters`, `pad_offset_x`, `pad_offset_y`, and `pad_rotation`, preserving the raw dimensions and transform strings from `.def` text padstack `pad(shp=..., Szs(...), X=..., Y=..., R=...)` records so no-ANF conversion can recover real pad shapes.
- The default PyEDB `AEDBLayout` schema is unaffected and remains `0.5.0`.

## 0.8.0

- The separate `AEDBDefBinaryLayout` schema is bumped to `0.8.0`: `domain.binary_polygon_records[]` adds native `.def` polygon/void records with global `offset`, `count_offset`, `coordinate_offset`, `geometry_id`, `parent_geometry_id`, `is_void`, `layer_id`, `layer_name`, reserved `net_index` / `net_name`, `item_count`, `point_count`, `arc_segment_count`, and raw-point `items`.
- `domain.binary_geometry` adds polygon summary counts: `polygon_record_count`, `polygon_outer_record_count`, `polygon_void_record_count`, `polygon_point_count`, and `polygon_arc_segment_count`. The default PyEDB `AEDBLayout` schema is unaffected and remains `0.5.0`.

## 0.7.0

- The separate `AEDBDefBinaryLayout` schema is bumped to `0.7.0`: `domain.binary_padstack_instance_records[]` adds EDB `PadstackInstance` records with `offset`, `geometry_id`, `name`, `name_kind`, `net_index`, `net_name`, `raw_owner_index`, `raw_definition_index`, `x`, `y`, `rotation`, `secondary_name`, and `secondary_id`.
- `domain.binary_geometry` adds padstack instance summary counts: `padstack_instance_record_count`, `component_pin_padstack_instance_record_count`, `named_via_padstack_instance_record_count`, `unnamed_padstack_instance_record_count`, and `padstack_instance_secondary_name_count`. The default PyEDB `AEDBLayout` schema is unaffected and remains `0.5.0`.

## 0.6.0

- The separate `AEDBDefBinaryLayout` schema is bumped to `0.6.0`: `domain.layout_nets` adds the `.def` binary net table, and `domain.summary.layout_net_count` adds the layout-net count.
- `domain.binary_path_records[]` adds `net_index`, `net_name`, `layer_id`, and `layer_name` for owner information decoded from the binary path preamble. The default PyEDB `AEDBLayout` schema is unaffected and remains `0.5.0`.

## 0.5.0

- Added `raw_points` to `PadPropertyModel` for AEDB polygonal pad vertices.
- `metadata.output_schema_version` now reports AEDB JSON schema version `0.5.0`.
- The separate `AEDBDefBinaryLayout` schema is also bumped to `0.5.0`: `domain.binary_path_records` adds binary path record offsets, geometry ids, widths, point lists, arc-height markers, and Line/Larc segment counts. The default PyEDB `AEDBLayout` schema is unaffected by this field except for `PadPropertyModel.raw_points`.

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
