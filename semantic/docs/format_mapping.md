<a id="top"></a>
# 跨格式语义映射表 / Cross-Format Semantic Mapping Table

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

本文档描述各格式对象如何转入 `SemanticBoard`，以及如何从 `SemanticBoard` 转出到 Aurora/AAF 与 AuroraDB。这里的“映射”不是字段名到字段名的复制，而是把源格式对象解释为 PCB 语义对象，再按目标格式需要重新生成对象。ODB++ 到 Semantic 的字段级映射、via template 细化和旋转公式见：[odbpp_to_semantic_mapping.md](odbpp_to_semantic_mapping.md)。

## 总体对象映射

| 语义对象 | AEDB 输入来源 | Semantic 表达 | Aurora/AAF 输出 | AuroraDB 编译结果 | ODB++ 输入来源 |
| --- | --- | --- | --- | --- | --- |
| 板级元数据 | AEDB metadata | `SemanticMetadata` | 不直接输出；作为转换包上下文 | 不直接输出 | Step/job metadata |
| 单位 | AEDB layout unit | `SemanticBoard.units` | `layout set -unit <mil>`、`library set -unit <mil>` | `CeLayout.Units` | Step unit |
| 材料 | material definitions | `SemanticMaterial` | `stackup.json.materials`、`stackup.dat` material fields | stackup sidecar 文件 | layer `attrlist` material/thickness hint |
| 金属层 | stackup signal/plane layer | `SemanticLayer(role=signal/plane)` | `layout set -layerstack`、`stackup.dat/json` Metal | `MetalLayer` 与 layer id | matrix conductor layer |
| 介质层 | stackup dielectric layer | `SemanticLayer(role=dielectric)` | `stackup.dat/json` Dielectric | stackup sidecar 文件 | matrix dielectric layer |
| Board outline | layout outline/profile | `SemanticBoard.board_outline` | `layout set -profile` polygon geometry | `CeLayout.Outline` | profile layer / step profile |
| 网络 | net definitions | `SemanticNet` | `layout add -net` | `NetList.Net` | net records |
| Component | component instances | `SemanticComponent` | `layout add -component` | layer `Components` block | component records |
| Footprint / Part | component part/package | `SemanticFootprint` + component `part_name` | `library add -footprint`、`library add -p` | `CeParts.PartList`、`FootPrintSymbolList` | package / component package |
| Pin | component pins | `SemanticPin` | `layout add -component ... -pin ... -net ...` | `NetPins.Pin` | component pin records |
| Pad | component pin padstack instance | `SemanticPad` | `layout add -shape ... -net ...` 与 `library add -fpn`；多层 component pin padstack 额外生成同坐标 `NetVias.Via` | net geometry placement、footprint `PartPad`，以及 through-hole pin 的 `NetVias.Via` | package pad / feature |
| Pad/Via shape | padstack pad、antipad、hole | `SemanticShape` | `layout add -g ... -id ... -shape ...` | `GeomSymbols.ShapeList` | symbol/feature geometry |
| Via template | padstack definition | `SemanticViaTemplate` | `layout add -via` | `GeomSymbols.ViaList` | drill template / via feature；可用时会用匹配到的 signal-layer pad 和 negative pad antipad 细化 |
| Via instance | padstack instance, 非 pin | `SemanticVia` | `layout add -via ... -location ... -net ...` | `NetVias.Via` | via feature |
| Trace / arc | path primitive | `SemanticPrimitive(kind=trace/arc)` | `Line` / `Larc` net geometry，并用 Circle shape 表示线宽 | layer `NetGeometry` | line/track feature 与独立 `A` arc feature |
| Polygon | polygon / zone primitive | `SemanticPrimitive(kind=polygon/zone)` | `Polygon` net geometry | layer `NetGeometry`，包含 `Parc` 曲线边 | polygon/surface feature，包含 contour `OC` arc |
| Polygon void | polygon voids | `SemanticPrimitive.geometry.voids` | container `Polygon` + `PolygonHole` | `PolygonHole` with holes | surface hole feature |
| 连接关系 | component、pin、pad、net、via、primitive 引用 | `ConnectivityEdge` | 不单独输出；用于诊断与导出决策 | 不单独输出 | derived references |

## AEDB 到 Semantic 的关键规则

| AEDB 对象 | Semantic 转换规则 |
| --- | --- |
| Stackup material | 转为 `SemanticMaterial`，保留导电率、介电常数、损耗角正切等可用属性。 |
| Signal / plane layer | 转为 `SemanticLayer`，保留名称、顺序、厚度、材料引用和层角色。 |
| Dielectric layer | 转为 `SemanticLayer(role=dielectric)`，只进入 stackup 输出，不作为 AuroraDB metal layer。 |
| Padstack definition | drill hole、regular pad、antipad、thermal pad 转为 `SemanticShape`；每层 pad 引用聚合为 `SemanticViaTemplate`。ODB++ 直接 via 匹配可从同网正极性 pad 推断 regular pad，并从 via 位置上的负极性 pad feature 推断 antipad。 |
| Component pin | 同时生成 `SemanticPin` 和 placed `SemanticPad`，pin 负责网络连接语义，pad 负责铜皮几何和放置信息；如果 pin padstack 在多个 metal layer 上有 layer pad，AuroraDB target 会在导出阶段额外写入同 net、同坐标的 `NetVias.Via`，但不在 Semantic JSON 中新增 `SemanticVia`。 |
| ODB++ component pad layer | 当一个 component 的所有已解析 pin pad 位于同一个金属层时，component placement layer 由该金属层推导，而不是直接使用源 component side layer。原始 ODB++ component layer 保留在 `SemanticComponent.attributes["ODBPP_COMPONENT_LAYER"]`。 |
| ODB++ 保留无网络名 | `$NONE$`、`$NONE`、`NONE$` 和源 `NoNet` 别名会合并为一个伪 `SemanticNet(name="NoNet", role="no_net")`，让 AuroraDB 输出使用其 `NoNet` keyword，而不是普通电气网络名。 |
| Padstack instance | 非 pin 的实例转为 `SemanticVia`，通过 `template_id` 指向 `SemanticViaTemplate`。 |
| Path primitive | 转为 trace primitive，保留 width、center line、bbox。center line 中的 arc marker 后续输出为 `Larc`。 |
| ODB++ 独立 `A` feature | 转为 arc primitive，保留 start、end、center、clockwise 方向，并在可解析时保留圆形 symbol 线宽；有 net 的 arc 后续输出为 `Larc`。 |
| Polygon primitive | 转为 polygon/zone primitive，保留 raw points、推导出的 arc 边、bbox、area、negative/void 标记。ODB++ surface contour 会按 `I` island / `H` hole polarity 分组，contour `OC` 记录会保留源圆心和方向。 |
| Polygon void | 转入父 polygon 的 `geometry.voids`，包含 void 的 arc 边，后续输出为目标格式的 hole 结构。 |

## Semantic 到 Aurora/AAF 的关键规则

| Semantic 对象 | Aurora/AAF 生成规则 |
| --- | --- |
| `SemanticShape` | 生成 `layout add -g <{id:Circle/Rectangle/RoundedRectangle/Polygon,...}> -id <id> -shape <type>`。 |
| Trace width | 按去重后的宽度生成额外 Circle shape；trace `Line` / `Larc` 通过 `-shape` 引用该宽度 shape。 |
| Trace center line / arc primitive | 普通点对生成 `Line`；AEDB arc marker 和 ODB++ 独立 arc primitive 在 start、end、center、direction、net、width 都可用时生成 `Larc`。 |
| `SemanticPad` | 生成 `layout add -shape <pad_shape> -location <...> -rotation <...> -layer <...> -net <...>`，表示 pin pad 铜皮实体；ODB++ `orient_def` 的 rotation/mirror flag 会保留为 rotation 与 flip transform。AEDB 多层 component pin padstack 会额外生成同 net、同坐标的 AuroraDB `NetVias.Via`，用于表达 through-hole pin 的跨层连接。 |
| `SemanticPin` | 生成 component-layer 上的 net pin binding；必要时用 `-metal` 保留 pin 金属层语义。 |
| `SemanticComponent` | 生成 component placement，part、location、rotation、value 从语义对象重新组织。 |
| Component/footprint attributes | 将共享的 `SemanticComponent.attributes` 和 `SemanticFootprint.attributes` 作为 `library add -p` 的 part attributes 输出。 |
| Footprint pad | 从代表 component 的 placed pads 推导 footprint pad template、pad geometry 和 footprint pin placement；ODB++ component pin 会优先使用 EDA component/pin key，再回退到 pin 引用字段，源 pad `orient_def` 会参与局部 footprint transform。 |
| 共享 part name | 当同一个 semantic part name 映射到多个 footprint 时，导出会生成按 footprint 区分的 part 变体，并让 component placement 引用这些变体名。这样会保留 ODB++ 中 `n/a` 这类占位 part name，又不会把不同层的 short-cline footprint 折叠到一起。 |
| Polygon arc edge | 输出为 5 值 polygon arc 顶点 `(end_x,end_y,center_x,center_y,direction)`，编译后成为 AuroraDB `Parc`。方向按源格式语义转换：AEDB arc height 沿用既有高度约定，ODB++ `OC` clockwise 记录直接映射到 Aurora/AAF 方向标记。 |
| Polygon with voids | 先写 container polygon，再写 `PolygonHole`，让 AuroraDB 中保留 outline、holes 关系和 arc 顶点。 |
| Via template / instance | template 写入 `layout add -via`，非 pin instance 写入带 net 和 location 的 via placement；AEDB 多层 component pin padstack 复用对应 template，在 target 导出阶段作为 synthetic `NetVias.Via` 写入。 |
| Board outline | 将 `board_outline` 输出为 `layout set -profile`；polygon arc 顶点会编译为 `Outline.Parc` item。 |
| Footprint body geometry | 将 `SemanticFootprint.geometry.outlines` 输出为 `library add -g ... -footprint`，让 package body outline 进入 part library。 |
| ODB++ `NoNet` 伪网络 | 对显式被 net record 引用的 no-net pin、pad、via 和 geometry 输出规范化 `NoNet` 网络名；AuroraDB 编译器保留 `NoNet` keyword 的大小写。 |
| No-net drawing geometry | 位于 signal/plane 层的正极性 trace/arc/polygon primitive 会提升为 `NoNet` 并导出为 AuroraDB net geometry；非布线绘图 feature 仍只保留在 coverage 中，negative cutout 不会提升。 |

- 旋转约定：AEDB rotation 继续使用既有 exporter 符号转换；ODB++ rotation 按 ODB++ Design Format Specification 的“正角为顺时针”语义处理，导出 Aurora/AAF 时不套用 AEDB 的符号翻转。从 ODB++ placed pad fallback 推导 footprint pad 时，也使用匹配的顺时针逆变换。
- ODB++ component layer 约定：如果某个 component 的已解析 pin pad 全部位于 `LAYER7`，semantic component layer 会变为 `LAYER7`，Aurora/AAF 导出为 `COMP_LAYER7`；混合层或无法解析 layer 时回退到源 component side。
- part name 与 footprint symbol 分开处理：`library add -p` 记录 component 的 part number，映射到 package/footprint symbol，并携带共享源属性；`library add -footprint` 只输出真实 semantic footprint 或 package fallback。
- 如果一个 part name 被多个 footprint 复用，导出的 part name 会追加标准化后的 footprint 名称，使每个 component 指向正确的 footprint symbol。

## 维护规则

- 新增格式 adapter 时，先把源格式对象归一到最接近的 Semantic 对象，再补充目标格式导出逻辑。
- 新增目标格式时，不应直接读取 AEDB/AuroraDB/ODB++ 的源模型；应从 `SemanticBoard` 生成目标对象。
- 如果目标格式需要某种对象级结构，例如 footprint pad template 或 trace width shape，应在导出器中由 semantic 内容重建，而不是把源字段逐项搬运。
- 当映射关系改变但 semantic JSON 字段不变时，更新 semantic parser 版本和 changelog；当 semantic JSON 字段或字段含义改变时，更新 semantic JSON schema 版本。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

This document describes how format objects enter `SemanticBoard` and how `SemanticBoard` is exported to Aurora/AAF and AuroraDB. The mapping is not field-name copying; source objects are interpreted as PCB semantic objects, then regenerated in the target format's object model. See [odbpp_to_semantic_mapping.md](odbpp_to_semantic_mapping.md) for ODB++ field-level mapping, via-template refinement, and rotation formulas.

## Object Mapping

| Semantic object | AEDB input source | Semantic representation | Aurora/AAF output | AuroraDB compiled result | ODB++ input source |
| --- | --- | --- | --- | --- | --- |
| Board metadata | AEDB metadata | `SemanticMetadata` | Not emitted directly; used as package context | Not emitted directly | Step/job metadata |
| Units | AEDB layout unit | `SemanticBoard.units` | `layout set -unit <mil>`, `library set -unit <mil>` | `CeLayout.Units` | Step unit |
| Material | material definitions | `SemanticMaterial` | `stackup.json.materials`, `stackup.dat` material fields | stackup sidecar files | layer `attrlist` material/thickness hints |
| Metal layer | stackup signal/plane layer | `SemanticLayer(role=signal/plane)` | `layout set -layerstack`, `stackup.dat/json` Metal | `MetalLayer` and layer id | matrix conductor layer |
| Dielectric layer | stackup dielectric layer | `SemanticLayer(role=dielectric)` | `stackup.dat/json` Dielectric | stackup sidecar files | matrix dielectric layer |
| Board outline | layout outline/profile | `SemanticBoard.board_outline` | `layout set -profile` polygon geometry | `CeLayout.Outline` | profile layer / step profile |
| Net | net definitions | `SemanticNet` | `layout add -net` | `NetList.Net` | net records |
| Component | component instances | `SemanticComponent` | `layout add -component` | layer `Components` block | component records |
| Footprint / Part | component part/package | `SemanticFootprint` plus component `part_name` | `library add -footprint`, `library add -p` | `CeParts.PartList`, `FootPrintSymbolList` | package / component package |
| Pin | component pins | `SemanticPin` | `layout add -component ... -pin ... -net ...` | `NetPins.Pin` | component pin records |
| Pad | component pin padstack instance | `SemanticPad` | `layout add -shape ... -net ...` and `library add -fpn`; multi-layer component-pin padstacks also emit same-location `NetVias.Via` | net geometry placement, footprint `PartPad`, and through-hole pin `NetVias.Via` | package pad / feature |
| Pad/Via shape | padstack pad, antipad, hole | `SemanticShape` | `layout add -g ... -id ... -shape ...` | `GeomSymbols.ShapeList` | symbol/feature geometry |
| Via template | padstack definition | `SemanticViaTemplate` | `layout add -via` | `GeomSymbols.ViaList` | drill template / via feature, refined from matched signal-layer pads and negative pad antipads when available |
| Via instance | non-pin padstack instance | `SemanticVia` | `layout add -via ... -location ... -net ...` | `NetVias.Via` | via feature |
| Trace / arc | path primitive | `SemanticPrimitive(kind=trace/arc)` | `Line` / `Larc` net geometry, with a Circle shape for width | layer `NetGeometry` | line/track feature and standalone `A` arc feature |
| Polygon | polygon / zone primitive | `SemanticPrimitive(kind=polygon/zone)` | `Polygon` net geometry | layer `NetGeometry`, including `Parc` curved edges | polygon/surface feature, including contour `OC` arcs |
| Polygon void | polygon voids | `SemanticPrimitive.geometry.voids` | container `Polygon` plus `PolygonHole` | `PolygonHole` with holes | surface hole feature |
| Connectivity | component, pin, pad, net, via, primitive references | `ConnectivityEdge` | Not emitted directly; used for diagnostics and export decisions | Not emitted directly | derived references |

## AEDB To Semantic Rules

| AEDB object | Semantic conversion rule |
| --- | --- |
| Stackup material | Becomes `SemanticMaterial`, preserving available conductivity, permittivity, and loss-tangent properties. |
| Signal / plane layer | Becomes `SemanticLayer`, preserving name, order, thickness, material reference, and layer role. |
| Dielectric layer | Becomes `SemanticLayer(role=dielectric)` and is exported only through stackup outputs, not as an AuroraDB metal layer. |
| Padstack definition | Drill hole, regular pad, antipad, and thermal pad become `SemanticShape`; layer pad references are grouped into `SemanticViaTemplate`. ODB++ direct via matching can infer regular pads from same-net positive pads and antipads from negative pad features at the via location. |
| Component pin | Produces both `SemanticPin` and placed `SemanticPad`; the pin carries net binding semantics, while the pad carries copper geometry and placement. If the pin padstack has layer pads on multiple metal layers, the AuroraDB target also emits a same-net, same-location `NetVias.Via` during export, without adding a `SemanticVia` entry to Semantic JSON. |
| ODB++ component pad layer | When all resolved pin pads for a component share one metal layer, the component placement layer is derived from that metal layer instead of the source component side layer. The original ODB++ component layer remains in `SemanticComponent.attributes["ODBPP_COMPONENT_LAYER"]`. |
| ODB++ reserved no-net name | `$NONE$`, `$NONE`, `NONE$`, and source `NoNet` aliases become one pseudo `SemanticNet(name="NoNet", role="no_net")` so AuroraDB output can use its `NoNet` keyword instead of a normal electrical net name. |
| Padstack instance | A non-pin instance becomes `SemanticVia` and references `SemanticViaTemplate` by `template_id`. |
| Path primitive | Becomes a trace primitive, preserving width, center line, and bbox. Center-line arc markers are later emitted as `Larc`. |
| ODB++ standalone `A` feature | Becomes an arc primitive with start, end, center, clockwise direction, and round-symbol width when resolvable; net-connected arcs later emit as `Larc`. |
| Polygon primitive | Becomes a polygon/zone primitive, preserving raw points, derived arc edges, bbox, area, and negative/void flags. ODB++ surface contours are grouped by `I` island / `H` hole polarity, and contour `OC` records preserve source centers and directions. |
| Polygon void | Is stored under the parent polygon's `geometry.voids`, including void arc edges, and later emitted as the target format's hole structure. |

## Semantic To Aurora/AAF Rules

| Semantic object | Aurora/AAF generation rule |
| --- | --- |
| `SemanticShape` | Emits `layout add -g <{id:Circle/Rectangle/RoundedRectangle/Polygon,...}> -id <id> -shape <type>`. |
| Trace width | Emits deduplicated Circle shapes; trace `Line` / `Larc` commands reference the width shape through `-shape`. |
| Trace center line / arc primitive | Normal point pairs emit `Line`; AEDB arc markers and ODB++ standalone arc primitives emit `Larc` when start, end, center, direction, net, and width are available. |
| `SemanticPad` | Emits `layout add -shape <pad_shape> -location <...> -rotation <...> -layer <...> -net <...>` for the pin-pad copper body; ODB++ `orient_def` rotation/mirror flags are preserved as rotation and flip transforms. AEDB multi-layer component-pin padstacks also emit same-net, same-location AuroraDB `NetVias.Via` records to represent through-hole pin cross-layer connectivity. |
| `SemanticPin` | Emits a net-pin binding on the component layer and preserves pin metal-layer semantics with `-metal` when needed. |
| `SemanticComponent` | Emits component placement, rebuilding part, location, rotation, and value from semantic content. |
| Component/footprint attributes | Emits shared `SemanticComponent.attributes` and `SemanticFootprint.attributes` as part attributes on `library add -p`. |
| Footprint pad | Derives footprint pad templates, pad geometry, and footprint pin placement from representative placed pads; ODB++ component pins use EDA component/pin keys before fallback pin references, and source pad `orient_def` contributes to the local footprint transform. |
| Shared part names | When the same semantic part name maps to multiple footprints, export creates footprint-specific part variants and component placements reference those variant names. This preserves placeholder ODB++ part names such as `n/a` without collapsing layer-specific short-cline footprints. |
| Polygon arc edge | Emits a 5-value polygon arc vertex `(end_x,end_y,center_x,center_y,direction)`, which compiles into AuroraDB `Parc`. Direction follows source semantics: AEDB arc height uses the existing height convention, while ODB++ `OC` clockwise records map directly to the Aurora/AAF direction flag. |
| Polygon with voids | Emits container polygons first and then `PolygonHole`, preserving the outline, hole relationship, and arc vertices in AuroraDB. |
| Via template / instance | Emits templates through `layout add -via` and non-pin instances through net-connected via placement. AEDB multi-layer component-pin padstacks reuse the corresponding template and are emitted as synthetic `NetVias.Via` records at target-export time. |
| Board outline | Emits `board_outline` as `layout set -profile`; polygon arc vertices compile into `Outline.Parc` items. |
| Footprint body geometry | Emits `SemanticFootprint.geometry.outlines` as `library add -g ... -footprint` commands so package body outlines are visible in the part library. |
| ODB++ `NoNet` pseudo-net | Emits the canonical `NoNet` net name for explicitly net-referenced no-net pins, pads, vias, and geometry; the AuroraDB compiler preserves the `NoNet` keyword case. |
| No-net drawing geometry | Positive trace/arc/polygon primitives on signal or plane layers are promoted to `NoNet` and emitted as AuroraDB net geometry; non-routable drawing features remain coverage-only, and negative cutouts are not promoted. |

- Rotation convention: AEDB rotations keep the existing exporter sign conversion, while ODB++ rotations are clockwise-positive per the ODB++ Design Format Specification and are emitted to Aurora/AAF without that AEDB sign inversion. ODB++ placed-pad fallback footprint derivation uses the matching clockwise inverse transform.
- ODB++ component-layer convention: if a component's resolved pin pads all live on `LAYER7`, the semantic component layer becomes `LAYER7`, which Aurora/AAF exports as `COMP_LAYER7`; mixed or unresolved pad layers fall back to the source component side.
- Part names and footprint symbols are kept separate: `library add -p` records the component part number, maps it to a package/footprint symbol, and carries shared source attributes; `library add -footprint` emits actual semantic footprints or package fallbacks only.
- If one part name is reused with several footprints, the exported part name is suffixed with the standardized footprint name so each component points at the correct footprint symbol.

## Maintenance Rules

- When adding a source adapter, normalize source objects into the nearest Semantic object before adding target export behavior.
- When adding a target format, generate target objects from `SemanticBoard` rather than reading AEDB, AuroraDB, or ODB++ source models directly.
- If a target format needs object-level structures, such as footprint pad templates or trace width shapes, rebuild them in the exporter from semantic content instead of copying source fields one by one.
- If mapping behavior changes without a semantic JSON field change, update the semantic parser version and changelog. If semantic JSON fields or meanings change, update the semantic JSON schema version.
