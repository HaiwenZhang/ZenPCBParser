<a id="top"></a>
# AEDB 到 Semantic 转换说明 / AEDB to Semantic Conversion

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

本文档记录 AEDB JSON 进入 `SemanticBoard` 的语义转换规则。当前 semantic 模型先按 AuroraDB 可表达的语义收敛：默认路径会直接输出 `stackup.dat`、`stackup.json` 和 AuroraDB block 文件；显式 `--export-aaf` 或不编译时才会保留 `aaf/design.layout` 和 `aaf/design.part` 兼容产物。

## 转换目标

AEDB adapter 不做简单字段搬运，而是把 AEDB 对象转换成 AuroraDB 侧需要的语义对象：

| AEDB 内容 | Semantic 语义 | Aurora/AAF 输出 |
| --- | --- | --- |
| `materials` | `SemanticMaterial` | `stackup.json.materials`、`stackup.dat` layer 属性 |
| `layers` | `SemanticLayer` | `stackup.dat/json` 和 `design.layout` layerstack |
| `nets` | `SemanticNet` | `layout add -net` |
| `padstacks.definitions` 的 pad/antipad/thermalpad/hole | `SemanticShape`、`SemanticViaTemplate` | AuroraDB `ShapeList`、`ViaList`；可选 AAF `layout add -g`、`layout add -via` |
| `padstacks.instances` | `SemanticVia` | `layout add -net ... -via ... -location ...` |
| `components.pins` | `SemanticPin`、`SemanticPad` | `library add -p/-pin`、`layout add -component`、`layout add -net ... -component ... -pin`；多层 component pin padstack 额外写入 AuroraDB `NetVias.Via` |
| `primitives.paths/polygons` | `SemanticPrimitive` | `layout add -net ... -g ... -layer` |

## Materials

每个 AEDB material 会转换为 `SemanticMaterial`：

| AEDB 字段 | Semantic 字段 |
| --- | --- |
| `name` | `name`、`id` |
| `conductivity` / `dc_conductivity` | `conductivity` |
| `permittivity` / `dc_permittivity` | `permittivity` |
| `dielectric_loss_tangent` / `loss_tangent` | `dielectric_loss_tangent` |

材料角色按属性推断：

- 有导电率且没有介质属性时，视为 `metal`。
- 有介电常数或介质损耗时，视为 `dielectric`。
- layer 已知为 signal/plane 时，其材料按 `metal` 使用。
- layer 已知为 dielectric 时，其材料按 `dielectric` 使用。

## Layers 和 Stackup

AEDB `layers` 转换为 `SemanticLayer`，保留：

- 源 layer 名称、类型、顺序。
- signal、plane、dielectric、mask、drill 等语义角色。
- 主材料、填充材料和对应 `SemanticMaterial` 引用。
- 厚度原始显示值。

导出到 Aurora/AAF 时：

- `signal` 和 `plane` 进入 `design.layout` 的 layerstack，并编译为 AuroraDB metal layer。
- `dielectric` 进入 `stackup.dat` / `stackup.json`，不写成 AuroraDB `MetalLayer`。
- 厚度统一转换为 mil 后输出。

## Padstack Shapes

AEDB padstack definition 中的 hole、pad、antipad 和 thermal pad 会转换为 AuroraDB-profile shape。
当前映射由 `semantic/adapters/aedb.py::_shape_geometry()` 维护，AuroraDB 输出由 `targets/auroradb/geometry.py::_shape_geometry_payload()` 格式化。

| AEDB 几何 | Semantic shape | AAF geometry |
| --- | --- | --- |
| `NoGeometry` | 不生成 shape | 不输出 geometry |
| `Circle` | `kind="circle"`、`auroradb_type="Circle"` | `Circle,(0,0,diameter)` |
| `Square` | `kind="rectangle"`、`auroradb_type="Rectangle"` | `Rectangle,(0,0,size,size)` |
| `Rectangle` | `kind="rectangle"`、`auroradb_type="Rectangle"` | `Rectangle,(0,0,width,height)` |
| `Oval` / rounded rectangle | `kind="rounded_rectangle"`、`auroradb_type="RoundedRectangle"` | `RoundedRectangle,(0,0,width,height,radius)` |
| AEDB polygonal pad | `kind="polygon"`、`auroradb_type="Polygon"` | `Polygon,(count,(x,y),...,Y,Y)` |
| `Bullet` | `kind="polygon"`、`auroradb_type="Polygon"` | 从 `XSize`、`YSize`、`CornerRadius` 构造带 arc 顶点的 polygon |
| `NSidedPolygon` | `kind="polygon"`、`auroradb_type="Polygon"` | 从 `Size`、`NumSides` 构造 regular polygon |
| `Round45` | `kind="polygon"`、`auroradb_type="Polygon"` | 从 `Inner`、`ChannelWidth`、`IsolationGap` 构造旋转 45° 的 thermal polygon |
| `Round90` | `kind="polygon"`、`auroradb_type="Polygon"` | 从 `Inner`、`ChannelWidth`、`IsolationGap` 构造正交 thermal polygon |

参数化 polygon 构造规则：

- `Polygon` 优先使用 `PadPropertyModel.raw_points`，并支持 AEDB raw point 中的 arc-height marker，输出为 5 值 arc 顶点 `(end_x,end_y,center_x,center_y,CCW)`。
- `Bullet` 按圆角矩形轮廓生成，直线顶点输出 `(x,y)`，圆角输出 5 值 arc 顶点。
- `NSidedPolygon` 使用 `Size / 2` 作为外接圆半径，按 `NumSides` 均匀生成顶点。
- `Round45` / `Round90` 当前按 thermal relief 的十字形导通区域构造 polygon；`Round45` 在 `Round90` 几何基础上旋转 45°。
- 构造完成后会应用 pad property 的 `offset_x`、`offset_y` 和 `rotation`；`SemanticShape.values` 保留在 semantic 单位中，导出时再转换为 mil。
- drill hole 目前只把圆形或 round hole 转成 barrel `Circle`；非圆 hole 和 polygonal hole 暂不生成 barrel shape。
- `thermal_shape_id` 会保留在 `SemanticViaTemplateLayer` 中，但当前 AuroraDB `ViaList` 导出只写 barrel、regular pad 和 antipad，不写 thermal shape。

Circle 的转换语义是：

```text
AEDB pad property: geometry_type=Circle, parameter Diameter
  -> SemanticShape: auroradb_type=Circle, values=[0, 0, diameter]
  -> AuroraDB direct output writes Circle values [0, 0, diameter_mil]
  -> Optional AAF output uses layout add -g with the same Circle values
  -> AuroraDB: GeomSymbols/ShapeList 中的 Circle item
```

`SemanticShape.values` 保留在 semantic 单位中，导出时再转换为 mil。

## Via Templates 和 Via Instances

每个 AEDB padstack definition 会生成一个 `SemanticViaTemplate`：

- `barrel_shape_id` 引用 drill hole shape。
- `layer_pads[].pad_shape_id` 引用各层 regular pad shape。
- `layer_pads[].antipad_shape_id` 引用各层 antipad shape。
- `layer_pads[].thermal_shape_id` 保留 thermal pad shape 引用，供后续导出扩展使用。

每个 AEDB padstack instance 会生成一个 `SemanticVia`：

- `template_id` 指向对应 `SemanticViaTemplate`。
- `net_id` 指向对应 `SemanticNet`。
- `position` 保留实例位置。
- `layer_names` 保留穿越的 signal layer 范围。

默认 direct AuroraDB 导出会把 via template 写入 `ViaList`，via instance 写入 net via 记录。可选 AAF 兼容路径中，via template 写为 `layout add -via`，via instance 写为 `layout add -net ... -via ... -location ...`。

AEDB component pin 仍保留为 `SemanticPin` + `SemanticPad`，不会在 Semantic JSON 中新增 `SemanticVia`。当 component pin/pad 引用的 padstack definition 在多个 metal layer 上有 `layer_pads` 时，AuroraDB target 会把该 pin padstack 额外写成同 net、同坐标的 `NetVias.Via`，用于表达 through-hole component pin 的跨层连接。单层 SMD padstack 不会写成 via。

## Nets、Components 和 Primitives

AEDB nets 会转换为 `SemanticNet`，并根据名称和源标记推断 power、ground 或 signal。

AEDB components 和 pins 会转换为：

- `SemanticComponent`
- `SemanticPin`
- `SemanticPad`
- `SemanticFootprint`

默认 direct AuroraDB 导出会直接生成 `layout.db` 和 `parts.db` 中的 component、pad、pin、part 和 footprint 结构。可选 AAF 兼容路径中，component 会写成 layout component；pin 和 pad 会拆成两个目标对象：pad 铜皮实体写成 `layout add -shape ... -net ...`，pin 连接关系写成 net pin binding。`design.part` 会写入 part、footprint、footprint pad template、footprint pin placement 和去重后的 part pin 列表。

AEDB path、polygon 和 zone primitive 会转换为 `SemanticPrimitive`，保留 layer、net、bbox、center line、polygon 点和 polygon arc 边等信息。默认 direct AuroraDB 导出会直接生成 `Line`、`Larc`、`Polygon`、`PolygonHole`、`Pnt` 和 `Parc` block；可选 AAF 兼容路径会先写成对应 `layout add -net ... -g ... -layer` 命令再编译。polygon 与 void 的 arc 边会输出为 5 值 polygon arc 顶点，编译到 AuroraDB 后成为 `Parc`。弧线方向在默认 AEDB direct cache 路径中沿用既有 AuroraDB item-line 约定；当走通用 exporter fallback 时，`_ccw_flag_from_arc_height()` 按 AuroraDB `CCW` 语义输出：AEDB arc height 为负时输出 `N`，为正时输出 `Y`，缺少 height 时才用 `is_ccw` 兜底。带 `voids` 几何的 polygon 会写成 PolygonHole。polygon 的 `is_void`、`void_ids`、`voids` 和 arc 明细会保留在 `SemanticPrimitive.geometry` 中，用于输出和追溯挖空关系。

## Diagnostics

转换完成后会运行连接诊断：

- layer 的 material 引用是否存在。
- via template 的 shape 引用是否存在。
- via instance 的 template、net、layer 引用是否存在。
- component、pin、pad、footprint、primitive 等连接引用是否存在。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

This document records how AEDB JSON is converted into `SemanticBoard`. The current semantic model is intentionally aligned with AuroraDB-expressible semantics first: the default path writes `stackup.dat`, `stackup.json`, and AuroraDB block files directly; `aaf/design.layout` and `aaf/design.part` are retained only when `--export-aaf` is requested explicitly or compilation is disabled.

## Conversion Goal

The AEDB adapter does not copy fields by name. It converts AEDB objects into semantic objects required by the AuroraDB side:

| AEDB content | Semantic object | Aurora/AAF output |
| --- | --- | --- |
| `materials` | `SemanticMaterial` | `stackup.json.materials`, `stackup.dat` layer properties |
| `layers` | `SemanticLayer` | `stackup.dat/json` and `design.layout` layerstack |
| `nets` | `SemanticNet` | `layout add -net` |
| pad/antipad/thermalpad/hole data in `padstacks.definitions` | `SemanticShape`, `SemanticViaTemplate` | AuroraDB `ShapeList`, `ViaList`; optional AAF `layout add -g`, `layout add -via` |
| `padstacks.instances` | `SemanticVia` | `layout add -net ... -via ... -location ...` |
| `components.pins` | `SemanticPin`, `SemanticPad` | `library add -p/-pin`, `layout add -component`, `layout add -net ... -component ... -pin`; multi-layer component-pin padstacks also emit AuroraDB `NetVias.Via` |
| `primitives.paths/polygons` | `SemanticPrimitive` | `layout add -net ... -g ... -layer` |

## Materials

Each AEDB material becomes a `SemanticMaterial`:

| AEDB field | Semantic field |
| --- | --- |
| `name` | `name`, `id` |
| `conductivity` / `dc_conductivity` | `conductivity` |
| `permittivity` / `dc_permittivity` | `permittivity` |
| `dielectric_loss_tangent` / `loss_tangent` | `dielectric_loss_tangent` |

Material role is inferred from properties:

- Conductivity without dielectric properties is treated as `metal`.
- Permittivity or dielectric loss is treated as `dielectric`.
- A material used by a signal/plane layer is used as `metal`.
- A material used by a dielectric layer is used as `dielectric`.

## Layers and Stackup

AEDB `layers` become `SemanticLayer` entries that preserve:

- Source layer name, type, and order.
- Semantic role such as signal, plane, dielectric, mask, or drill.
- Primary material, fill material, and `SemanticMaterial` references.
- Original thickness display value.

During Aurora/AAF export:

- `signal` and `plane` enter the `design.layout` layerstack and compile into AuroraDB metal layers.
- `dielectric` enters `stackup.dat` / `stackup.json` and is not emitted as an AuroraDB `MetalLayer`.
- Thickness values are converted to mil before output.

## Padstack Shapes

Hole, pad, antipad, and thermal-pad geometry from AEDB padstack definitions become AuroraDB-profile shapes.
The mapping is maintained by `semantic/adapters/aedb.py::_shape_geometry()`, and AuroraDB output is formatted by `targets/auroradb/geometry.py::_shape_geometry_payload()`.

| AEDB geometry | Semantic shape | AAF geometry |
| --- | --- | --- |
| `NoGeometry` | No shape is generated | No geometry output |
| `Circle` | `kind="circle"`, `auroradb_type="Circle"` | `Circle,(0,0,diameter)` |
| `Square` | `kind="rectangle"`, `auroradb_type="Rectangle"` | `Rectangle,(0,0,size,size)` |
| `Rectangle` | `kind="rectangle"`, `auroradb_type="Rectangle"` | `Rectangle,(0,0,width,height)` |
| `Oval` / rounded rectangle | `kind="rounded_rectangle"`, `auroradb_type="RoundedRectangle"` | `RoundedRectangle,(0,0,width,height,radius)` |
| AEDB polygonal pad | `kind="polygon"`, `auroradb_type="Polygon"` | `Polygon,(count,(x,y),...,Y,Y)` |
| `Bullet` | `kind="polygon"`, `auroradb_type="Polygon"` | Polygon with arc vertices built from `XSize`, `YSize`, and `CornerRadius` |
| `NSidedPolygon` | `kind="polygon"`, `auroradb_type="Polygon"` | Regular polygon built from `Size` and `NumSides` |
| `Round45` | `kind="polygon"`, `auroradb_type="Polygon"` | 45-degree thermal polygon built from `Inner`, `ChannelWidth`, and `IsolationGap` |
| `Round90` | `kind="polygon"`, `auroradb_type="Polygon"` | Orthogonal thermal polygon built from `Inner`, `ChannelWidth`, and `IsolationGap` |

Parameterized polygon construction rules:

- `Polygon` prefers `PadPropertyModel.raw_points` and supports AEDB arc-height markers in raw points, emitting 5-value arc vertices `(end_x,end_y,center_x,center_y,CCW)`.
- `Bullet` is generated as a rounded-rectangle outline. Straight vertices use `(x,y)`, and rounded corners use 5-value arc vertices.
- `NSidedPolygon` uses `Size / 2` as the circumradius and generates evenly spaced vertices from `NumSides`.
- `Round45` / `Round90` are currently constructed as thermal-relief cross-shaped conductive regions; `Round45` rotates the `Round90` geometry by 45 degrees.
- After construction, pad property `offset_x`, `offset_y`, and `rotation` are applied. `SemanticShape.values` stay in semantic units and are converted to mil during export.
- Drill holes currently become barrel `Circle` shapes only for circular or round holes; non-circular holes and polygonal holes do not generate barrel shapes yet.
- `thermal_shape_id` is preserved on `SemanticViaTemplateLayer`, but current AuroraDB `ViaList` export writes only barrel, regular pad, and antipad shapes, not thermal shapes.

Circle conversion semantics:

```text
AEDB pad property: geometry_type=Circle, parameter Diameter
  -> SemanticShape: auroradb_type=Circle, values=[0, 0, diameter]
  -> AuroraDB direct output writes Circle values [0, 0, diameter_mil]
  -> Optional AAF output uses layout add -g with the same Circle values
  -> AuroraDB: Circle item under GeomSymbols/ShapeList
```

`SemanticShape.values` stay in semantic units and are converted to mil during export.

## Via Templates and Via Instances

Each AEDB padstack definition becomes one `SemanticViaTemplate`:

- `barrel_shape_id` references the drill-hole shape.
- `layer_pads[].pad_shape_id` references the regular pad shape for each layer.
- `layer_pads[].antipad_shape_id` references the antipad shape for each layer.
- `layer_pads[].thermal_shape_id` preserves thermal-pad shape references for later export expansion.

Each AEDB padstack instance becomes one `SemanticVia`:

- `template_id` points to the corresponding `SemanticViaTemplate`.
- `net_id` points to the corresponding `SemanticNet`.
- `position` preserves the instance location.
- `layer_names` preserves the traversed signal-layer range.

Default direct AuroraDB export writes via templates into `ViaList` and via instances into net-via records. In the optional AAF compatibility path, via templates are written as `layout add -via` and via instances as `layout add -net ... -via ... -location ...`.

AEDB component pins remain `SemanticPin` + `SemanticPad` and do not add `SemanticVia` entries to Semantic JSON. When a component pin/pad references a padstack definition with layer pads on multiple metal layers, the AuroraDB target also emits a same-net, same-location `NetVias.Via` to represent the through-hole component-pin cross-layer connection. Single-layer SMD padstacks are not emitted as vias.

## Nets, Components, and Primitives

AEDB nets become `SemanticNet` entries, with power, ground, or signal roles inferred from source flags and names.

AEDB components and pins become:

- `SemanticComponent`
- `SemanticPin`
- `SemanticPad`
- `SemanticFootprint`

Default direct AuroraDB export writes component, pad, pin, part, and footprint structures directly into `layout.db` and `parts.db`. In the optional AAF compatibility path, components are written as layout components. Pins and pads are split into two target objects: placed pad copper is emitted as `layout add -shape ... -net ...`, and pin connectivity is emitted as net-pin bindings. `design.part` writes part and footprint entries, footprint pad templates, footprint pin placements, and deduplicated part pin lists.

AEDB path, polygon, and zone primitives become `SemanticPrimitive` entries that preserve layer, net, bbox, center line, polygon point information, and polygon arc edges. Default direct AuroraDB export writes `Line`, `Larc`, `Polygon`, `PolygonHole`, `Pnt`, and `Parc` blocks directly; the optional AAF compatibility path first writes the corresponding `layout add -net ... -g ... -layer` commands and then compiles them. Polygon and void arc edges are emitted as 5-value polygon arc vertices and compile into AuroraDB `Parc` items. Arc direction in the default AEDB direct cache path follows the existing AuroraDB item-line convention. When the generic exporter fallback is used, `_ccw_flag_from_arc_height()` writes AuroraDB `CCW` semantics: negative AEDB arc height emits `N`, positive height emits `Y`, and `is_ccw` is used only as a fallback when height is unavailable. Polygons with `voids` geometry are written as PolygonHole. Polygon `is_void`, `void_ids`, `voids`, and arc details are preserved in `SemanticPrimitive.geometry` so cutout relationships can be emitted and traced.

## Diagnostics

After conversion, the diagnostics pass checks:

- Whether layer material references exist.
- Whether via-template shape references exist.
- Whether via-instance template, net, and layer references exist.
- Whether component, pin, pad, footprint, and primitive references exist.
