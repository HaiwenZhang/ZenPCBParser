<a id="top"></a>
# AEDB JSON 输出结构说明 / AEDB JSON Output Structure

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

本文档说明 Aurora Translator 当前 AEDB 解析输出的 JSON 结构。机器可读 schema 由代码生成，路径为 [aedb_schema.json](aedb_schema.json)。

## 版本

- 当前项目版本：`1.0.41`
- 当前 AEDB 解析器版本：`0.4.56`
- 当前 AEDB JSON schema 版本：`0.5.0`
- 项目发布或集成格式级变更时更新 `PROJECT_VERSION`，并体现在 `metadata.project_version`。
- AEDB 解析逻辑、归一化逻辑或性能实现变化时更新 `aedb.version.AEDB_PARSER_VERSION`，并体现在 `metadata.parser_version`。
- AEDB JSON 字段增删、字段含义或结构变化时更新 `aedb.version.AEDB_JSON_SCHEMA_VERSION`，并体现在 `metadata.output_schema_version`。

## 生成方式

```powershell
uv run python .\main.py --schema-output .\aedb\docs\aedb_schema.json
```

## 顶层结构

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `metadata` | object | 解析器、源文件、PyEDB/AEDT 后端信息。 |
| `summary` | object | 板级数量统计和 PyEDB 统计信息。 |
| `materials` | array/null | 材料定义，`--summary-only` 时为 `null` 或省略详细内容。 |
| `layers` | array/null | stackup 层列表，直接位于顶层，不再通过 `stackup.layers` 包装。 |
| `nets` | array/null | 网络列表和每个网络的关联数量。 |
| `components` | array/null | 器件实例、引脚、连接网络和位置信息。 |
| `padstacks` | object/null | padstack 定义和实例。 |
| `primitives` | object/null | layout 几何图元，包括 path、polygon 和 zone primitive。 |

## 通用值规则

| 名称 | JSON 表达 | 说明 |
| --- | --- | --- |
| `ValueField` | string/boolean/integer/number/object/null | PyEDB 返回值的安全归一化结果。 |
| `DisplayValue` | object | 保留数值和原始显示字符串，字段为 `value` 与 `display`。 |
| `PointField` | array/null | 二维点，格式为 `[x, y]`。 |
| `PointListField` | array | 二维点列表。 |
| `NumericListField` | array/null | 数字列表，常用于 bounding box。 |
| `EnumField` | string/integer/null | .NET enum 会优先归一化为名称。 |
| `ParameterMapField` | object | 参数名到归一化值的映射。 |

## metadata

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `project_version` | string | 生成该 AEDB JSON 的 Aurora Translator 项目版本。 |
| `parser_version` | string | 生成该 AEDB JSON 的 AEDB 解析器版本。 |
| `output_schema_version` | string | 当前 AEDB JSON schema 版本。 |
| `source` | string | `.aedb` 源目录路径。 |
| `layout_name` | string | 解析出的 layout 名称。 |
| `backend` | string | 当前固定为 `dotnet`。 |
| `pyedb_version` | string | PyEDB 包版本。 |
| `aedt_version` | string | PyEDB 打开 AEDB 时使用的 AEDT 版本。 |
| `read_only` | boolean | 是否以只读方式打开 AEDB。 |

## summary

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `material_count` | integer | 材料数量。 |
| `layer_count` | integer | 层数量。 |
| `net_count` | integer | 网络数量。 |
| `component_count` | integer | 器件数量。 |
| `padstack_definition_count` | integer | padstack 定义数量。 |
| `padstack_instance_count` | integer | padstack 实例数量。 |
| `primitive_count` | integer | layout primitive 总数。 |
| `primitive_type_counts` | object | 按 primitive 类型分组的数量。 |
| `path_count` | integer | path primitive 数量。 |
| `polygon_count` | integer | polygon primitive 数量。 |
| `zone_primitive_count` | integer | zone primitive 数量。 |
| `statistics` | object | PyEDB `get_statistics` 返回的统计信息。 |

`statistics` 包含 `layout_size`、`stackup_thickness`、`num_layers`、`num_nets`、`num_traces`、`num_polygons`、`num_vias`、`num_discrete_components`、`num_inductors`、`num_resistors`、`num_capacitors`。

## materials

每个材料对象包含 `name`、`type`、`conductivity`、`dc_conductivity`、`permittivity`、`dc_permittivity`、`permeability`、`loss_tangent`、`dielectric_loss_tangent`、`magnetic_loss_tangent`、`mass_density`、`poisson_ratio`、`specific_heat`、`thermal_conductivity`、`thermal_expansion_coefficient`、`youngs_modulus`、`dielectric_model_frequency`。

## layers

每个层对象包含 `name`、`id`、`type`、`material`、`fill_material`、`dielectric_fill`、`thickness`、`lower_elevation`、`upper_elevation`、`conductivity`、`permittivity`、`loss_tangent`、`roughness_enabled`、`is_negative`、`is_stackup_layer`、`is_via_layer`、`color`、`transparency`。

## nets

每个网络对象包含 `name`、`is_power_ground`、`component_count`、`primitive_count`、`padstack_instance_count`。

## components

每个器件对象包含 `refdes`、`component_name`、`part_name`、`type`、`value`、`placement_layer`、`location`、`center`、`rotation`、`bounding_box`、`is_top_mounted`、`enabled`、`model_type`、`numpins`、`nets`、`pins`。

每个 `pins` 项包含 `name`、`id`、`net_name`、`position`、`rotation`、`placement_layer`、`start_layer`、`stop_layer`、`padstack_definition`、`is_pin`。

## padstacks

`padstacks` 包含两个数组：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `definitions` | array | padstack 定义。 |
| `instances` | array | padstack 实例。 |

每个 definition 包含 `name`、`material`、`hole_type`、`hole_range`、`hole_diameter`、`hole_diameter_string`、`hole_finished_size`、`hole_offset_x`、`hole_offset_y`、`hole_rotation`、`hole_plating_ratio`、`hole_plating_thickness`、`hole_properties`、`via_layers`、`via_start_layer`、`via_stop_layer`、`pad_by_layer`、`antipad_by_layer`、`thermalpad_by_layer`。

每个 pad property 包含 `pad_type`、`geometry_type`、`shape`、`offset_x`、`offset_y`、`rotation`、`parameters`、`raw_points`。

每个 instance 包含 `id`、`name`、`type`、`net_name`、`component_name`、`placement_layer`、`position`、`rotation`、`start_layer`、`stop_layer`、`layer_range_names`、`padstack_definition`、`is_pin`。

## primitives

`primitives` 包含三个数组：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `paths` | array | 走线/path primitives。 |
| `polygons` | array | polygon primitives。 |
| `zone_primitives` | array | zone primitives，字段结构沿用 polygon。 |

path 和 polygon 都继承 primitive 基础字段：`id`、`name`、`type`、`aedt_name`、`layer_name`、`net_name`、`component_name`、`area`、`bbox`、`is_void`。

path 额外包含 `width`、`length`、`center_line`、`corner_style`、`end_cap_style`。

polygon 额外包含 `raw_points`、`arcs`、`is_negative`、`is_zone_primitive`、`has_voids`、`void_ids`、`voids`。

arc 包含 `start`、`end`、`center`、`mid_point`、`height`、`radius`、`length`、`is_segment`、`is_point`、`is_ccw`。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

This document describes the current JSON structure emitted by Aurora Translator for AEDB parsing. The machine-readable schema is generated from code and is available at [aedb_schema.json](aedb_schema.json).

## Versions

- Current project version: `1.0.41`
- Current AEDB parser version: `0.4.56`
- Current AEDB JSON schema version: `0.5.0`
- Update `PROJECT_VERSION` for project releases or integrated format-level changes; it is emitted as `metadata.project_version`.
- Update `aedb.version.AEDB_PARSER_VERSION` when AEDB parsing logic, normalization logic, or performance behavior changes; it is emitted as `metadata.parser_version`.
- Update `aedb.version.AEDB_JSON_SCHEMA_VERSION` when AEDB JSON fields, field meanings, or structure change; it is emitted as `metadata.output_schema_version`.

## Generation

```powershell
uv run python .\main.py --schema-output .\aedb\docs\aedb_schema.json
```

## Top-Level Structure

| Field | Type | Description |
| --- | --- | --- |
| `metadata` | object | Parser, source file, and PyEDB/AEDT backend metadata. |
| `summary` | object | Board-level counts and PyEDB statistics. |
| `materials` | array/null | Material definitions; `null` or omitted details in `--summary-only` mode. |
| `layers` | array/null | Stackup layers, stored directly at the top level without the old `stackup.layers` wrapper. |
| `nets` | array/null | Net list and per-net related counts. |
| `components` | array/null | Component instances, pins, connected nets, and placement information. |
| `padstacks` | object/null | Padstack definitions and instances. |
| `primitives` | object/null | Layout geometry primitives, including paths, polygons, and zone primitives. |

## Common Value Rules

| Name | JSON Representation | Description |
| --- | --- | --- |
| `ValueField` | string/boolean/integer/number/object/null | JSON-safe normalized value returned from PyEDB. |
| `DisplayValue` | object | Keeps both numeric value and original display string in `value` and `display`. |
| `PointField` | array/null | 2D point represented as `[x, y]`. |
| `PointListField` | array | List of 2D points. |
| `NumericListField` | array/null | Numeric list, often used for bounding boxes. |
| `EnumField` | string/integer/null | .NET enums are normalized to names when possible. |
| `ParameterMapField` | object | Mapping from parameter names to normalized values. |

## metadata

| Field | Type | Description |
| --- | --- | --- |
| `project_version` | string | Aurora Translator project version that generated this AEDB JSON. |
| `parser_version` | string | AEDB parser version that generated this AEDB JSON. |
| `output_schema_version` | string | Current AEDB JSON schema version. |
| `source` | string | Source `.aedb` directory path. |
| `layout_name` | string | Parsed layout name. |
| `backend` | string | Currently fixed to `dotnet`. |
| `pyedb_version` | string | PyEDB package version. |
| `aedt_version` | string | AEDT version used by PyEDB when opening the AEDB. |
| `read_only` | boolean | Whether the AEDB was opened read-only. |

## summary

| Field | Type | Description |
| --- | --- | --- |
| `material_count` | integer | Number of materials. |
| `layer_count` | integer | Number of layers. |
| `net_count` | integer | Number of nets. |
| `component_count` | integer | Number of components. |
| `padstack_definition_count` | integer | Number of padstack definitions. |
| `padstack_instance_count` | integer | Number of padstack instances. |
| `primitive_count` | integer | Total number of layout primitives. |
| `primitive_type_counts` | object | Primitive counts grouped by primitive type. |
| `path_count` | integer | Number of path primitives. |
| `polygon_count` | integer | Number of polygon primitives. |
| `zone_primitive_count` | integer | Number of zone primitives. |
| `statistics` | object | Statistics returned by PyEDB `get_statistics`. |

`statistics` includes `layout_size`, `stackup_thickness`, `num_layers`, `num_nets`, `num_traces`, `num_polygons`, `num_vias`, `num_discrete_components`, `num_inductors`, `num_resistors`, and `num_capacitors`.

## materials

Each material object contains `name`, `type`, `conductivity`, `dc_conductivity`, `permittivity`, `dc_permittivity`, `permeability`, `loss_tangent`, `dielectric_loss_tangent`, `magnetic_loss_tangent`, `mass_density`, `poisson_ratio`, `specific_heat`, `thermal_conductivity`, `thermal_expansion_coefficient`, `youngs_modulus`, and `dielectric_model_frequency`.

## layers

Each layer object contains `name`, `id`, `type`, `material`, `fill_material`, `dielectric_fill`, `thickness`, `lower_elevation`, `upper_elevation`, `conductivity`, `permittivity`, `loss_tangent`, `roughness_enabled`, `is_negative`, `is_stackup_layer`, `is_via_layer`, `color`, and `transparency`.

## nets

Each net object contains `name`, `is_power_ground`, `component_count`, `primitive_count`, and `padstack_instance_count`.

## components

Each component object contains `refdes`, `component_name`, `part_name`, `type`, `value`, `placement_layer`, `location`, `center`, `rotation`, `bounding_box`, `is_top_mounted`, `enabled`, `model_type`, `numpins`, `nets`, and `pins`.

Each `pins` item contains `name`, `id`, `net_name`, `position`, `rotation`, `placement_layer`, `start_layer`, `stop_layer`, `padstack_definition`, and `is_pin`.

## padstacks

`padstacks` contains two arrays:

| Field | Type | Description |
| --- | --- | --- |
| `definitions` | array | Padstack definitions. |
| `instances` | array | Padstack instances. |

Each definition contains `name`, `material`, `hole_type`, `hole_range`, `hole_diameter`, `hole_diameter_string`, `hole_finished_size`, `hole_offset_x`, `hole_offset_y`, `hole_rotation`, `hole_plating_ratio`, `hole_plating_thickness`, `hole_properties`, `via_layers`, `via_start_layer`, `via_stop_layer`, `pad_by_layer`, `antipad_by_layer`, and `thermalpad_by_layer`.

Each pad property contains `pad_type`, `geometry_type`, `shape`, `offset_x`, `offset_y`, `rotation`, `parameters`, and `raw_points`.

Each instance contains `id`, `name`, `type`, `net_name`, `component_name`, `placement_layer`, `position`, `rotation`, `start_layer`, `stop_layer`, `layer_range_names`, `padstack_definition`, and `is_pin`.

## primitives

`primitives` contains three arrays:

| Field | Type | Description |
| --- | --- | --- |
| `paths` | array | Trace/path primitives. |
| `polygons` | array | Polygon primitives. |
| `zone_primitives` | array | Zone primitives with the same field structure as polygons. |

Paths and polygons inherit the primitive base fields: `id`, `name`, `type`, `aedt_name`, `layer_name`, `net_name`, `component_name`, `area`, `bbox`, and `is_void`.

Paths additionally contain `width`, `length`, `center_line`, `corner_style`, and `end_cap_style`.

Polygons additionally contain `raw_points`, `arcs`, `is_negative`, `is_zone_primitive`, `has_voids`, `void_ids`, and `voids`.

Each arc contains `start`, `end`, `center`, `mid_point`, `height`, `radius`, `length`, `is_segment`, `is_point`, and `is_ccw`.
