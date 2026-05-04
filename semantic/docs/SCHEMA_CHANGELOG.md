<a id="top"></a>
# Semantic JSON Schema 变更记录 / Semantic JSON Schema Changelog

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

## 0.7.1

- `SourceRef.source_format` 和 `SemanticMetadata.source_format` 的枚举新增 `alg`，用于标记 Cadence Allegro extracta ALG source JSON 产生的语义对象。
- 没有新增、删除或重命名顶层字段；既有 `aedb`、`auroradb`、`odbpp` 和 `brd` payload 结构保持兼容。

## 0.7.0

- `SemanticFootprint.geometry`、`SemanticViaTemplate.geometry`、`SemanticPad.geometry`、`SemanticVia.geometry`、`SemanticPrimitive.geometry` 和 `SemanticBoard.board_outline` 从裸 object 收敛为 typed geometry definitions。
- 新增 `SemanticArcGeometry`、`SemanticPolygonVoidGeometry`、`SemanticPrimitiveGeometry` 等 geometry schema 定义；这些 model 仍允许 extra metadata 以保留源格式细节。
- JSON 字段名保持兼容；schema 现在可以描述常用 `shape_id`、`rotation`、`center_line`、`raw_points`、`arcs`、`voids`、`layer_pad_rotations` 和 package outline/pad hints。

## 0.6.0

- `SemanticComponent.attributes` 新增源 component properties，以及归一化后的 package/component metadata。
- `SemanticFootprint.attributes` 新增源 package/footprint properties。

## 0.5.0

- 顶层新增 `board_outline`，用于保存源 board profile 几何。
- `SemanticFootprint`、`SemanticViaTemplate`、`SemanticVia` 新增 `geometry`。
- 新增的 geometry hint 字段用于保留 ODB++ package body outline、drill tool metadata、via instance geometry 和 board outline/profile 细节，供统一模型访问。

## 0.4.0

- 顶层结构新增 `shapes` 和 `via_templates`。
- `summary` 新增 `shape_count` 和 `via_template_count`。
- 新增 `SemanticShape`、`SemanticViaTemplate` 和 `SemanticViaTemplateLayer` schema 定义。
- `SemanticVia` 新增 `name` 和 `template_id`。
- 诊断 pass 会检查 via template 的 shape 引用和 via instance 的 template 引用。

## 0.3.0

- 顶层结构新增 `materials`。
- `summary` 新增 `material_count`。
- `layers` 新增 `material_id`、`fill_material` 和 `fill_material_id`。
- 新增 `SemanticMaterial` schema 定义，包含材料角色、导电率、介电常数和介质损耗角正切。
- 诊断 pass 会检查 layer material 引用是否指向缺失材料。

## 0.2.0

- 顶层结构新增 `footprints` 和 `pads`。
- `summary` 新增 `footprint_count` 和 `pad_count`。
- `nets` 新增 `pad_ids`，`components` 新增 `footprint_id` 和 `pad_ids`，`pins` 新增 `pad_ids`。
- 新增 `SemanticFootprint` 和 `SemanticPad` schema 定义。
- `connectivity.kind` 新增 `component-footprint`、`component-pad`、`footprint-pad`、`pin-pad` 和 `pad-net`。

## 0.1.0

- 初始 semantic JSON schema。
- 顶层结构包含 `metadata`、`units`、`summary`、`layers`、`nets`、`components`、`pins`、`vias`、`primitives`、`connectivity` 和 `diagnostics`。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

## 0.7.1

- Added `alg` to the `SourceRef.source_format` and `SemanticMetadata.source_format` enums for semantic objects generated from Cadence Allegro extracta ALG source JSON.
- No top-level fields were added, removed, or renamed; existing `aedb`, `auroradb`, `odbpp`, and `brd` payload structures remain compatible.

## 0.7.0

- `SemanticFootprint.geometry`, `SemanticViaTemplate.geometry`, `SemanticPad.geometry`, `SemanticVia.geometry`, `SemanticPrimitive.geometry`, and `SemanticBoard.board_outline` change from bare objects to typed geometry definitions.
- Added geometry schema definitions such as `SemanticArcGeometry`, `SemanticPolygonVoidGeometry`, and `SemanticPrimitiveGeometry`; these models still allow extra metadata so source-format details can be retained.
- JSON field names remain compatible; the schema now describes common `shape_id`, `rotation`, `center_line`, `raw_points`, `arcs`, `voids`, `layer_pad_rotations`, and package outline/pad hints.

## 0.6.0

- Added `SemanticComponent.attributes` for source component properties and normalized package/component metadata.
- Added `SemanticFootprint.attributes` for source package/footprint properties.

## 0.5.0

- Added top-level `board_outline` for source board profile geometry.
- Added `geometry` to `SemanticFootprint`, `SemanticViaTemplate`, and `SemanticVia`.
- The new geometry hint fields preserve ODB++ package body outlines, drill tool metadata, via instance geometry, and board outline/profile details for unified model access.

## 0.4.0

- Added top-level `shapes` and `via_templates`.
- Added `shape_count` and `via_template_count` to `summary`.
- Added the `SemanticShape`, `SemanticViaTemplate`, and `SemanticViaTemplateLayer` schema definitions.
- Added `name` and `template_id` to `SemanticVia`.
- The diagnostics pass now checks via-template shape references and via-instance template references.

## 0.3.0

- Added top-level `materials`.
- Added `material_count` to `summary`.
- Added `material_id`, `fill_material`, and `fill_material_id` to `layers`.
- Added the `SemanticMaterial` schema definition with material role, conductivity, permittivity, and dielectric loss tangent.
- The diagnostics pass now checks whether layer material references point to missing materials.

## 0.2.0

- Added top-level `footprints` and `pads`.
- Added `footprint_count` and `pad_count` to `summary`.
- Added `pad_ids` to `nets`, `footprint_id` and `pad_ids` to `components`, and `pad_ids` to `pins`.
- Added `SemanticFootprint` and `SemanticPad` schema definitions.
- Added `component-footprint`, `component-pad`, `footprint-pad`, `pin-pad`, and `pad-net` to `connectivity.kind`.

## 0.1.0

- Initial semantic JSON schema.
- Top-level structure includes `metadata`, `units`, `summary`, `layers`, `nets`, `components`, `pins`, `vias`, `primitives`, `connectivity`, and `diagnostics`.
