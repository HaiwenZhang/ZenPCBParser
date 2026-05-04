<a id="top"></a>
# ODB++Design Format Specification 工程总结 / ODB++Design Format Specification Engineering Summary

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

本文总结官方 `ODB++Design Format Specification Release 8.1 Update 4, August 2024`，面向本项目的 ODB++ 解析、Semantic 统一模型映射和 AuroraDB 转换实现。本文不是官方规范的替代品，遇到字段级歧义时应以官方文档为准。

参考资料：

- 官方 PDF：[ODB++Design Format Specification Release 8.1 Update 4, August 2024](https://odbplusplus.com//wp-content/uploads/sites/2/2024/08/odb_spec_user.pdf)
- 官方资源页：[ODB++Design Resources](https://odbplusplus.com/design/our-resources/)

## 格式定位

ODB++ 是面向 PCB 制造、装配、测试和 DFM 流程的数据交换格式。它不是单一文件，而是一个产品模型目录树。目录树内的 matrix、step、layer、features、EDA data、component、package、attribute、stackup 和 metadata 等文件共同描述板级对象。

对解析器来说，ODB++ 的关键特征是：

- 几何、网络、封装、器件、叠层和制造属性分散在多个文件中。
- 图形实体大量依赖 symbol 间接定义形状和尺寸。
- layer matrix 是理解板层顺序、类型、钻孔 span 和制造层关系的基础。
- EDA data 和 component 文件共同构成 component、pin、net、pad feature 的连接关系。
- 属性系统非常丰富，很多制造语义只能从 attrlist 或系统属性中恢复。
- 需要保留未知字段和未知属性，避免后续转换丢失语义。

## 顶层目录树

典型 ODB++ 产品模型目录包含：

| 路径 | 作用 | 解析关注点 |
| --- | --- | --- |
| `matrix/matrix` | 产品模型矩阵 | layer 顺序、类型、context、polarity、drill/rout span、mask/paste/silk 与 copper 的关系 |
| `matrix/stackup.xml` | 结构化叠层 | material、dielectric、copper、supplier data、stackup section |
| `misc/attrlist` | 产品级属性 | 全局制造、DFM、来源信息 |
| `misc/info` | 基本产品信息 | 单位、保存信息、来源标识 |
| `misc/metadata.xml` | 元数据 | 需求、制造、装配、最终产品 metadata |
| `misc/sysattr.*` | 系统属性定义 | 属性类型、单位、取值约束 |
| `misc/userattr` | 用户属性定义 | 用户扩展属性 |
| `steps/<step>/profile` | step 外形 | board outline 或 panel/coupon outline |
| `steps/<step>/eda/data` | EDA 信息 | nets、subnets、FID feature 引用、packages、package pins |
| `steps/<step>/layers/<layer>/features` | layer 图形 | line、pad、arc、text、barcode、surface |
| `steps/<step>/layers/<layer>/components` | component 实例 | CMP、PRP、TOP toeprint/pin |
| `steps/<step>/layers/<layer>/tools` | drill/rout tools | drill diameter、plating、tool metadata |
| `symbols/<symbol>/features` | 用户自定义 symbol | complex pad shape、surface symbol |
| `wheels/<wheel>/dcodes` | Gerber/tool wheel | legacy 或制造辅助信息 |

## Step 与 Layer

一个产品模型可以包含多个 step。常见 step 包括单板、panel、coupon 或制造辅助对象。解析时必须选择当前目标 step，而不是简单把所有 step 混合。

layer 需要从 `matrix/matrix` 和 step 下的 layer 文件共同解释：

- `SIGNAL`、`POWER_GROUND`、`MIXED` 通常映射到电气铜层。
- `DIELECTRIC` 进入 stackup，而不是 AuroraDB metal layer。
- `SOLDER_MASK`、`SOLDER_PASTE`、`SILK_SCREEN`、`MASK`、`CONDUCTIVE_PASTE` 是制造/装配层。
- `DRILL` 和 `ROUT` 通过 `START_NAME` / `END_NAME` 表达 span。
- `DOCUMENT`、`MISC`、`COMPONENT` 等需要按用途分别处理，不能默认当作布线层。

对转换到 AuroraDB 的意义：

- signal/plane layer 应进入 `layout.db`/layer `.lyr`。
- dielectric layer 更适合进入 `stackup.dat` / `stackup.json`。
- component layer 应转成 component placement 层。
- document/drawing 层默认不应伪造成 net geometry。

## 单位、坐标和角度

ODB++ 文件通常通过 `UNITS` 指定单位，常见值是 `MM` 和 `INCH`。解析器需要按文件上下文解释坐标和尺寸。

实现建议：

- 每个 features、tools、symbols、stackup 文件应携带或继承单位。
- 输出统一模型时应保存源单位，并在导出 Aurora/AAF 时集中转换。
- 标准 symbol 的尺寸参数不能一律按裸数解释，必须结合 symbol 规则和单位。
- 角度按度读取，进入本项目 Semantic 模型前统一转为弧度。
- 输出 Aurora/AAF 时再转为目标格式需要的角度表达，并归一化到稳定范围。

## 图形实体

ODB++ layer geometry 主要由 `features` 文件描述。

| Record | 含义 | 主要字段 |
| --- | --- | --- |
| `L` | line | start、end、symbol、polarity、attribute、ID |
| `P` | pad | x/y、symbol、polarity、dcode、orient_def、attribute、ID |
| `A` | arc | start、end、center、symbol、polarity、clockwise、attribute、ID |
| `S` | surface | contour records、polarity、attribute、ID |
| `T` | text | location、font、polarity、orient_def、size、text |
| `B` | barcode | location、barcode、font、polarity、orient_def、text |

几何转换要点：

- line 和 arc 是 symbol sweep，而不只是无宽度中心线。
- pad 是在点位放置 symbol。
- surface 是实体面，可能包含多个 island 和 hole。
- positive feature 会覆盖已有内容，negative feature 会擦除已有内容。
- feature ID 和 attribute 应保留，用于 net 关联、DFM 和追溯。

## Symbol

symbol 是 ODB++ 几何的核心抽象。它可以是标准 symbol，也可以是用户自定义 symbol。

常见标准 symbol：

- `r<diameter>`：圆。
- `rect<width>x<height>`：矩形。
- `oval<width>x<height>`：长圆。
- rounded rectangle、donut、thermal、octagon 等。

实现建议：

- 优先解析标准 symbol 为统一 `SemanticShape`。
- 对无法直接识别的 symbol，尝试读取 `symbols/<symbol>/features`。
- 用户自定义 symbol 中的 surface contour 应转换为 polygon shape。
- 不能解析的 symbol 应保留原始 symbol 名称和来源，避免静默丢失。

## Surface、Contour 和 Polygon

surface 表示合法 contour，可包含 island 和 hole。规范要求：

- island 之间不应重叠。
- hole 应位于所属 island 内。
- polygon 不应自交。
- island 和 hole 有自然包含顺序。
- curve 边需要有合法的 start、end、center。

实现建议：

- 按 contour polarity 或 containment 识别 island/hole。
- 多 island surface 应拆为多个 semantic polygon primitive。
- hole 应作为 void 附加到所属 island。
- contour arc edge 应保留为 polygon arc vertex，导出 AuroraDB 时映射为 `Parc`。
- negative surface 不应直接当作独立实铜，需要结合目标格式能力决定是保留 void 语义还是作为 coverage-only。

## Pad Orientation 与镜像

`orient_def` 是 pad、text、barcode 等对象的方向定义。对 pad 转换尤其关键。

legacy 值：

| orient_def | 含义 |
| --- | --- |
| `0` | 0 度，无镜像 |
| `1` | 90 度，无镜像 |
| `2` | 180 度，无镜像 |
| `3` | 270 度，无镜像 |
| `4` | 0 度，x-axis mirror |
| `5` | 90 度，x-axis mirror |
| `6` | 180 度，x-axis mirror |
| `7` | 270 度，x-axis mirror |

扩展值：

| orient_def | 含义 |
| --- | --- |
| `8 <angle>` | 任意角度，无镜像 |
| `9 <angle>` | 任意角度，x-axis mirror |

实现注意：

- ODB++ Design Format Specification 定义 rotation 为顺时针方向。本转换器中，ODB++ component 与 pin 角度在 Semantic 中保持“正角为顺时针”，导出 Aurora/AAF 时不再套用 AEDB 路径的符号翻转。
- Component-local 到 board 的 ODB++ 顺时针角 `theta` 变换为：`x_board = x0 + x_local*cos(theta) + y_local*sin(theta)`，`y_board = y0 - x_local*sin(theta) + y_local*cos(theta)`。
- 位于 bottom component layer 的 ODB++ component 在导出到 AuroraDB 时还需要沿 local x-axis mirror；AuroraDB/AAF 表示为 component placement 上的 `flipX`。
- 当缺少 package pin geometry、需要从 placed pad 反推 footprint pin 时，使用对应逆变换：`x_local = dx*cos(theta) - dy*sin(theta)`，`y_local = dx*sin(theta) + dy*cos(theta)`。
- 如果同时存在旋转和镜像，按规范语义先旋转，再沿 x 轴镜像。
- ODB++ pad 的方向语义和 Aurora/AAF 的角度方向可能不同，导出时需要统一转换。
- component rotation 与 pad orientation 不是同一个概念，不能互相替代。
- footprint-local pin 应优先来自 package pin geometry，不应由某个 placed component 的全局 pad 反推后复用给所有 component。

## EDA Data、Net 和 Pin 连接

`steps/<step>/eda/data` 是恢复电气连接的关键来源。常见 record：

| Record | 作用 |
| --- | --- |
| `NET` | 定义电气 net |
| `SNT` | 定义 subnet 或 pin 上下文 |
| `FID` | 把 net/subnet 关联到 layer feature |
| `PKG` | 定义 package |
| `PIN` | 定义 package pin |
| `FGR` | feature group |
| `PRP` | 属性 |
| `LYR` | EDA layer 名称表 |

连接关系通常需要跨文件合成：

- EDA `FID` 指向 layer feature。
- `SNT TOP T/B` 上下文提供 component side 和 pin 上下文。
- component 文件里的 `TOP` toeprint record 提供 placed component pin 信息。
- `CMP` 通过 package reference 关联 EDA `PKG`。
- package `PIN` 提供 package-local pin/shape。

实现建议：

- component pin 到 pad feature 的主键应优先使用真实 `component_index + pin_index`。
- component 文件 pin 行里的 net reference 可作为 fallback。
- `$NONE$` 不应合并为一个普通电气 net；面向 AuroraDB 输出时，显式 ODB++ 无网络别名应映射为规范化 `NoNet` keyword。
- 无 net feature 可以保留为 primitive 或 coverage 数据，但不应虚构电气连通关系。
- net、pin、pad、component、feature 都应保留 source reference，便于排查错连。

## Component、Package 和 Footprint

component 实例通常位于 component layer 的 `components` 文件中。核心记录：

- `CMP`：component placement，包含位置、旋转、镜像、refdes、package reference 等。
- `PRP`：component property，例如 part number、value。
- `TOP`：component toeprint/pin，包含 pin index、位置、旋转、net reference、pin name。

package 信息通常来自 `eda/data`：

- package 定义封装名、package index、body outline、bounds。
- package pin 定义 pin 名称、位置、旋转、电气/装配类型。
- package pin 可带 shape，用于 footprint pad template。

转换到 Semantic/AuroraDB 时的建议模型：

- `SemanticFootprint` 来源应是 ODB++ package。
- `SemanticComponent` 来源应是 placed CMP。
- `SemanticPin` 来源应是 component toeprint pin。
- `SemanticPad` 可以来自 pin-associated feature，也可以 fallback 到 package pin geometry。
- AuroraDB `design.part` 中的 footprint pin 应使用 package-local pin geometry。
- AuroraDB `design.layout` 中的 component placement 应使用 component location、rotation、side 和 part mapping。

## Drill、Via 和 Rout

drill/rout 层由 matrix span 和 layer tools 共同解释。

关键点：

- `START_NAME` / `END_NAME` 表示 drill/rout 穿越的 board layer span。
- span 为空时通常按顶层到最底层 board layer 解释。
- blind/buried via 和 backdrill 需要结合 layer subtype 和属性。
- tools 文件提供 drill diameter、plating、tool metadata。
- pad/antipad/thermal 可能来自 signal/plane layer 上与 drill location 匹配的 pad feature。

实现建议：

- via template 不应只按 drill diameter 合并，还应考虑 drill layer span。
- 可按 net、location、layer span 匹配 signal-layer pad。
- negative polarity pad 可用于推断 antipad，但复杂 void 组合需要保留诊断或 coverage。
- backdrill 相关属性应保留，即使暂时不能完整映射。

## Attribute 系统

ODB++ 属性用于保存制造、装配、测试、DFM 和用户扩展语义。常见属性来源：

- product `misc/attrlist`
- step `attrlist`
- layer `attrlist`
- feature attributes
- component attributes
- package/component `PRP`
- system attribute definition files
- user attribute definition file

实现建议：

- 已识别属性映射到强类型字段，例如 layer thickness、material、part number、value。
- 未识别属性保留到 `attributes` 或 `geometry` hint。
- 属性值要保留原始字符串，避免丢失单位、枚举或供应链字段。
- 解析系统属性时应记录属性 class、type、unit 和可用范围。

Update 4 值得关注的属性和语义包括：

- EDA 来源类属性，例如 `.class_source`、`.eda_layers`。
- IPC via 类型相关属性，例如 `.ipc_via_type_top` / `.ipc_via_type_bottom`。
- capped via、backdrill depth、stub drill 等制造属性。
- copper weight/thickness、dielectric material 和 stackup 相关字段。

## Stackup 和 Material

叠层信息可来自：

- `matrix/matrix`
- `matrix/stackup.xml`
- layer `attrlist`
- system/user attributes
- tools 或 metadata 中的制造 hint

实现建议：

- matrix 是 layer 顺序和 layer role 的基础。
- stackup.xml 可提供更完整的材料、厚度和供应商字段。
- layer attrlist 可补充 copper weight、dielectric constant、loss tangent 等。
- 输出 AuroraDB 时，metal layer 和 dielectric stackup 应分开处理。

## Component Variants 和 BOM

ODB++ 支持通过 BOM 和 attributes 表达 variant：

- product-level variant list 表示可用 variant。
- step-level current variant 表示当前 active variant。
- component-level variant membership 表示 component 属于哪些 variant。
- 不参与当前 BOM 的 component 可通过 not-populated 语义标记。

实现建议：

- 初期可以保留 variant 相关属性，不改变默认 component 输出。
- 后续可在 CLI 增加 variant 选择参数。
- 输出 BOM 或 assembly 视图时再启用 not-populated 过滤。

## 解析优先级建议

面向本项目，推荐按以下顺序继续增强 ODB++ 解析：

1. product root、压缩包、legacy `.Z` 处理。
2. matrix layer 类型、顺序、span、subtype、REF。
3. features 中的 `L/P/A/S/T/B` 和 attribute/ID。
4. standard symbol 和 user-defined symbol。
5. EDA `NET/SNT/FID/PKG/PIN/FGR`。
6. component `CMP/PRP/TOP`。
7. package-local footprint body 和 pin geometry。
8. drill/rout tools、via span、pad/antipad 匹配。
9. stackup.xml、metadata.xml、attrlist/sysattr/userattr。
10. component variant、BOM、assembly/test 扩展。

## 转换到 AuroraDB 的重点映射

| ODB++ 对象 | Semantic 对象 | Aurora/AAF 输出 |
| --- | --- | --- |
| matrix signal/power layer | `SemanticLayer(role=signal/plane)` | `layout set -layerstack`、layer `.lyr` |
| matrix dielectric layer | `SemanticLayer(role=dielectric)` | `stackup.dat` / `stackup.json` |
| profile geometry | `board_outline` | `layout set -g ... -profile` |
| standard/user symbol | `SemanticShape` | `layout add -g ... -shape` |
| net feature line | trace primitive | `layout add -g Line/Larc ... -net` |
| net feature pad | `SemanticPad` | `layout add -shape ... -net` |
| drill point | `SemanticVia` | `layout add -via ...` |
| surface | polygon primitive | polygon / polygon hole / Parc |
| EDA package | `SemanticFootprint` | `library add -footprint` |
| package pin shape | footprint pad template | `library add -pad` / `library add -fpn` |
| component CMP | `SemanticComponent` | `layout add -component` |
| component TOP pin | `SemanticPin` | `layout add -component ... -pin ... -net` |
| PRP / attrlist | attributes | part attributes、metadata、coverage |

## 常见风险点

- 把 `$NONE$` 当成普通电气 net，而不是把显式无网络引用映射为 AuroraDB `NoNet`。
- 忽略 `orient_def` 的 mirror 语义，导致 pad/component pin 旋转不对。
- 用 placed component pad 反推通用 footprint pin，导致同 footprint 不同旋转实例互相污染。
- 只解析标准 symbol，丢失 user-defined pad shape。
- surface hole/island 分组错误，导致铜皮 void 丢失或反向。
- 忽略 negative polarity，导致 plane cutout 或 antipad 错误。
- 只按 drill diameter 合并 via template，忽略 layer span。
- 把 document/drawing layer 输出成真实电气 net geometry。
- 忽略 attrlist/sysattr，导致材料、厚度、制造约束丢失。
- 不保留 source reference，后续难以定位转换差异。

## 本项目当前实现关注点

本项目的 ODB++ 到 Semantic/AuroraDB 链路应持续满足这些原则：

- ODB++ 格式 JSON 保留高保真源信息，Semantic 只做统一语义投影。
- 所有关键对象保留 `SourceRef`，方便从 AuroraDB 输出追溯到 ODB++ 文件。
- 几何转换优先保真，再按 AuroraDB 能力降级。
- 未能映射的制造/DFM 信息进入 attributes、geometry hint 或 coverage report。
- 位于可布线层的正极性无 net trace/arc/polygon 对象可导出为 AuroraDB `NoNet` 几何；document/profile 绘图对象和 negative cutout 不应混入电气网络几何。
- component、pin、pad、footprint 的映射要优先使用 EDA/package 的结构关系，而不是仅靠几何近邻。

## 后续增强清单

- 完善更多标准 symbol，特别是 thermal、donut、rounded/chamfered rectangle。
- 增强 user-defined symbol 中嵌套 surface、negative feature 和 arc edge 的处理。
- 支持更完整的 stackup.xml 到 material/stackup 的映射。
- 扩展 soldermask、paste、silkscreen、assembly 层语义输出策略。
- 增强 backdrill、capped via、IPC via type 等制造属性映射。
- 增加 component variant/BOM 选择能力。
- 为 `$NONE$`、negative feature、surface void、drill span、orient_def mirror 建立更多回归样例。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

This document summarizes the official `ODB++Design Format Specification Release 8.1 Update 4, August 2024` for this project's ODB++ parser, Semantic model mapping, and AuroraDB conversion work. It is not a replacement for the official specification. When field-level behavior is ambiguous, use the official documentation as the source of truth.

References:

- Official PDF: [ODB++Design Format Specification Release 8.1 Update 4, August 2024](https://odbplusplus.com//wp-content/uploads/sites/2/2024/08/odb_spec_user.pdf)
- Official resources page: [ODB++Design Resources](https://odbplusplus.com/design/our-resources/)

## Format Role

ODB++ is a data exchange format for PCB fabrication, assembly, test, and DFM workflows. It is not a single file. It is a product-model directory tree whose matrix, step, layer, features, EDA data, component, package, attribute, stackup, and metadata files describe board-level objects together.

Important parser implications:

- Geometry, nets, packages, components, stackup, and manufacturing attributes are distributed across multiple files.
- Many geometric entities rely on symbols for shape and size.
- The layer matrix is the base for layer order, layer type, drill span, and manufacturing-layer relationships.
- EDA data and component files jointly describe component, pin, net, and pad-feature connectivity.
- The attribute system carries a large part of manufacturing semantics.
- Unknown fields and attributes should be preserved so later conversion stages do not lose source intent.

## Top-Level Directory Tree

Typical ODB++ product-model directories include:

| Path | Role | Parser Focus |
| --- | --- | --- |
| `matrix/matrix` | Product model matrix | Layer order, type, context, polarity, drill/rout span, mask/paste/silk relation to copper |
| `matrix/stackup.xml` | Structured stackup | Material, dielectric, copper, supplier data, stackup section |
| `misc/attrlist` | Product-level attributes | Global manufacturing, DFM, and source metadata |
| `misc/info` | Basic product information | Units, save metadata, source identifiers |
| `misc/metadata.xml` | Metadata | Requirements, manufacturing, assembly, final-product metadata |
| `misc/sysattr.*` | System attribute definitions | Attribute type, unit, value constraints |
| `misc/userattr` | User attribute definitions | User-defined extension attributes |
| `steps/<step>/profile` | Step outline | Board, panel, or coupon outline |
| `steps/<step>/eda/data` | EDA data | Nets, subnets, FID feature references, packages, package pins |
| `steps/<step>/layers/<layer>/features` | Layer graphics | Lines, pads, arcs, text, barcodes, surfaces |
| `steps/<step>/layers/<layer>/components` | Component instances | CMP, PRP, TOP toeprint/pin records |
| `steps/<step>/layers/<layer>/tools` | Drill/rout tools | Drill diameter, plating, tool metadata |
| `symbols/<symbol>/features` | User-defined symbols | Complex pad shape and surface symbol geometry |
| `wheels/<wheel>/dcodes` | Gerber/tool wheel | Legacy or manufacturing support data |

## Steps And Layers

A product model can contain multiple steps. Common examples are a single PCB, a panel, a coupon, or manufacturing support objects. A parser should select the target step instead of merging all steps blindly.

Layers must be interpreted from both `matrix/matrix` and the files under the selected step:

- `SIGNAL`, `POWER_GROUND`, and `MIXED` usually map to electrical copper layers.
- `DIELECTRIC` belongs in stackup data rather than AuroraDB metal layers.
- `SOLDER_MASK`, `SOLDER_PASTE`, `SILK_SCREEN`, `MASK`, and `CONDUCTIVE_PASTE` are manufacturing or assembly layers.
- `DRILL` and `ROUT` use `START_NAME` / `END_NAME` for layer span.
- `DOCUMENT`, `MISC`, and `COMPONENT` need purpose-specific handling and should not be treated as routable layers by default.

AuroraDB conversion guidance:

- Signal and plane layers should enter `layout.db` and layer `.lyr` files.
- Dielectric layers should enter `stackup.dat` and `stackup.json`.
- Component layers should become component placement layers.
- Document and drawing layers should not be exported as fabricated electrical net geometry by default.

## Units, Coordinates, And Angles

ODB++ files commonly declare units with `UNITS`, usually `MM` or `INCH`. Coordinates and sizes must be interpreted in the file context.

Implementation guidance:

- Each features, tools, symbols, or stackup file should carry or inherit units.
- The unified Semantic model should preserve source units, with target-unit conversion centralized in exporters.
- Standard symbol parameters cannot be interpreted as plain numbers without symbol and unit rules.
- Source angles are read as degrees and converted to radians before entering this project's Semantic model.
- Aurora/AAF export should convert angles back to target-format conventions and normalize them to a stable range.

## Graphic Entities

Layer geometry is mainly described by `features` files.

| Record | Meaning | Main Fields |
| --- | --- | --- |
| `L` | Line | Start, end, symbol, polarity, attributes, ID |
| `P` | Pad | X/Y, symbol, polarity, dcode, orient_def, attributes, ID |
| `A` | Arc | Start, end, center, symbol, polarity, clockwise flag, attributes, ID |
| `S` | Surface | Contour records, polarity, attributes, ID |
| `T` | Text | Location, font, polarity, orient_def, size, text |
| `B` | Barcode | Location, barcode type, font, polarity, orient_def, text |

Geometry conversion notes:

- Lines and arcs are symbol sweeps, not just zero-width centerlines.
- Pads place a symbol at a point.
- Surfaces are filled areas and can contain multiple islands and holes.
- Positive features add material over previous features; negative features remove material from previous features.
- Feature IDs and attributes should be preserved for net connectivity, DFM, and traceability.

## Symbols

Symbols are a core ODB++ geometry abstraction. A symbol can be standard or user-defined.

Common standard symbols include:

- `r<diameter>`: circle.
- `rect<width>x<height>`: rectangle.
- `oval<width>x<height>`: oval or rounded rectangle.
- Rounded rectangles, donuts, thermals, octagons, and related variants.

Implementation guidance:

- Parse standard symbols into `SemanticShape` where possible.
- If a symbol cannot be parsed directly, try `symbols/<symbol>/features`.
- Surface contours inside user-defined symbols should become polygon shapes.
- Unparsed symbols should preserve the original symbol name and source reference instead of being dropped silently.

## Surfaces, Contours, And Polygons

A surface represents a legal contour and can contain islands and holes. The specification requires non-overlapping islands, holes contained in their islands, non-self-intersecting polygons, and legal curve edges.

Implementation guidance:

- Identify islands and holes by contour polarity or containment.
- Split multi-island surfaces into multiple Semantic polygon primitives.
- Attach holes as voids to their containing islands.
- Preserve contour arc edges as polygon arc vertices; AuroraDB export can map these to `Parc`.
- Negative surfaces should not automatically become standalone copper. Preserve void semantics or keep them as coverage data when the target format cannot represent the composition safely.

## Pad Orientation And Mirroring

`orient_def` defines orientation for pads, text, barcode records, and similar objects. It is especially important for pad conversion.

Legacy values:

| orient_def | Meaning |
| --- | --- |
| `0` | 0 degrees, no mirror |
| `1` | 90 degrees, no mirror |
| `2` | 180 degrees, no mirror |
| `3` | 270 degrees, no mirror |
| `4` | 0 degrees, x-axis mirror |
| `5` | 90 degrees, x-axis mirror |
| `6` | 180 degrees, x-axis mirror |
| `7` | 270 degrees, x-axis mirror |

Extended values:

| orient_def | Meaning |
| --- | --- |
| `8 <angle>` | Arbitrary rotation, no mirror |
| `9 <angle>` | Arbitrary rotation, x-axis mirror |

Implementation notes:

- The ODB++ Design Format Specification defines rotation as clockwise. In the converter, ODB++ component and pin angles remain clockwise-positive through Semantic and are written to Aurora/AAF without the AEDB sign inversion.
- For component-local to board transforms, ODB++ clockwise angle `theta` uses `x_board = x0 + x_local*cos(theta) + y_local*sin(theta)` and `y_board = y0 - x_local*sin(theta) + y_local*cos(theta)`.
- ODB++ components placed on a bottom component layer also need a local x-axis mirror when exported to AuroraDB; AuroraDB/AAF represents this as component placement `flipX`.
- When package pin geometry is missing and placed pads are used to reconstruct footprint pins, the inverse transform is `x_local = dx*cos(theta) - dy*sin(theta)` and `y_local = dx*sin(theta) + dy*cos(theta)`.
- If both rotation and mirror are present, the specification applies rotation first, then x-axis mirroring.
- ODB++ pad orientation and Aurora/AAF angle conventions can differ; exporters must convert consistently.
- Component rotation and pad orientation are different concepts and should not replace each other.
- Footprint-local pins should prefer package pin geometry instead of being inferred from one placed component and reused for all components with the same footprint.

## EDA Data, Nets, And Pin Connectivity

`steps/<step>/eda/data` is the key source for electrical connectivity.

| Record | Role |
| --- | --- |
| `NET` | Electrical net definition |
| `SNT` | Subnet or pin context |
| `FID` | Link from a net/subnet to a layer feature |
| `PKG` | Package definition |
| `PIN` | Package pin definition |
| `FGR` | Feature group |
| `PRP` | Property |
| `LYR` | EDA layer name table |

Connectivity is usually built across multiple files:

- EDA `FID` records point to layer features.
- `SNT TOP T/B` context provides component side and pin context.
- Component-file `TOP` toeprint records provide placed component pins.
- `CMP` records reference EDA `PKG` records.
- Package `PIN` records provide package-local pins and shapes.

Implementation guidance:

- Component pin to pad feature matching should prefer the real `component_index + pin_index` key.
- Net references from component-file pin rows can be a fallback.
- `$NONE$` should not be merged as a normal electrical net; for AuroraDB output, explicit ODB++ no-net aliases should map to the canonical `NoNet` keyword.
- No-net features can be preserved as primitives or coverage data, but should not invent electrical connectivity.
- Nets, pins, pads, components, and features should retain source references for debugging mismatches.

## Components, Packages, And Footprints

Component instances usually appear in component-layer `components` files. Core records:

- `CMP`: component placement, including location, rotation, mirror, refdes, and package reference.
- `PRP`: component property, such as part number or value.
- `TOP`: component toeprint or pin, including pin index, position, rotation, net reference, and pin name.

Package data usually comes from `eda/data`:

- Package records define package name, package index, body outline, and bounds.
- Package pin records define pin name, position, rotation, electrical/assembly type, and optional shape.
- Package pin shapes can define footprint pad templates.

Recommended Semantic/AuroraDB mapping:

- `SemanticFootprint` should come from the ODB++ package.
- `SemanticComponent` should come from placed `CMP` records.
- `SemanticPin` should come from component toeprint pins.
- `SemanticPad` can come from pin-associated features or fall back to package pin geometry.
- AuroraDB `design.part` footprint pins should use package-local pin geometry.
- AuroraDB `design.layout` component placements should use component location, rotation, side, and part mapping.

## Drill, Via, And Rout

Drill and rout layers are interpreted from matrix span plus layer tools.

Key points:

- `START_NAME` / `END_NAME` define the board-layer span of a drill or rout layer.
- Empty spans usually mean top board layer to bottom board layer.
- Blind/buried vias and backdrills need layer subtype and attributes.
- Tools files provide drill diameter, plating, and tool metadata.
- Pads, antipads, and thermals may be inferred by matching signal/plane-layer pad features at drill locations.

Implementation guidance:

- Via templates should consider both drill diameter and drill-layer span.
- Signal-layer pads can be matched by net, location, and layer span.
- Negative-polarity pads can infer antipads, but complex void compositions should retain diagnostics or coverage data.
- Backdrill-related attributes should be preserved even before full target mapping exists.

## Attribute System

ODB++ attributes preserve manufacturing, assembly, test, DFM, and user-extension semantics. Common sources include:

- Product `misc/attrlist`
- Step `attrlist`
- Layer `attrlist`
- Feature attributes
- Component attributes
- Package/component `PRP` records
- System attribute definition files
- User attribute definition files

Implementation guidance:

- Known attributes should map to strong fields, such as layer thickness, material, part number, and value.
- Unknown attributes should be preserved in `attributes` or geometry hints.
- Original string values should be retained to avoid losing units, enums, or supply-chain fields.
- System attribute parsing should record class, type, unit, and value constraints when available.

Update 4 items worth preserving include:

- EDA source attributes such as `.class_source` and `.eda_layers`.
- IPC via type attributes such as `.ipc_via_type_top` and `.ipc_via_type_bottom`.
- Capped-via, backdrill-depth, and stub-drill manufacturing attributes.
- Copper weight/thickness, dielectric material, and stackup-related attributes.

## Stackup And Material

Stackup information can come from:

- `matrix/matrix`
- `matrix/stackup.xml`
- Layer `attrlist`
- System or user attributes
- Tools or metadata manufacturing hints

Implementation guidance:

- Matrix remains the base source for layer order and layer role.
- `stackup.xml` can provide richer material, thickness, and supplier fields.
- Layer attributes can supplement copper weight, dielectric constant, loss tangent, and similar data.
- AuroraDB export should separate metal-layer geometry from dielectric stackup output.

## Component Variants And BOM

ODB++ can represent variants through BOM and attributes:

- Product-level variant lists define available variants.
- Step-level current variant defines the active variant.
- Component-level variant membership defines which variants include a component.
- Components not used by the active BOM can be marked as not populated.

Implementation guidance:

- Early parser stages can preserve variant attributes without filtering default component output.
- A future CLI option can select a variant.
- BOM or assembly-oriented exports can then apply not-populated filtering.

## Recommended Parser Priority

For this project, ODB++ parser improvements should generally follow this order:

1. Product root, archives, and legacy `.Z` handling.
2. Matrix layer type, order, span, subtype, and `REF`.
3. `L/P/A/S/T/B` features with attributes and IDs.
4. Standard and user-defined symbols.
5. EDA `NET/SNT/FID/PKG/PIN/FGR`.
6. Component `CMP/PRP/TOP`.
7. Package-local footprint body and pin geometry.
8. Drill/rout tools, via span, and pad/antipad matching.
9. `stackup.xml`, `metadata.xml`, `attrlist`, `sysattr`, and `userattr`.
10. Component variants, BOM, assembly, and test extensions.

## AuroraDB Conversion Mapping

| ODB++ Object | Semantic Object | Aurora/AAF Output |
| --- | --- | --- |
| Matrix signal/power layer | `SemanticLayer(role=signal/plane)` | `layout set -layerstack`, layer `.lyr` |
| Matrix dielectric layer | `SemanticLayer(role=dielectric)` | `stackup.dat` / `stackup.json` |
| Profile geometry | `board_outline` | `layout set -g ... -profile` |
| Standard/user symbol | `SemanticShape` | `layout add -g ... -shape` |
| Net feature line | Trace primitive | `layout add -g Line/Larc ... -net` |
| Net feature pad | `SemanticPad` | `layout add -shape ... -net` |
| Drill point | `SemanticVia` | `layout add -via ...` |
| Surface | Polygon primitive | Polygon / polygon hole / Parc |
| EDA package | `SemanticFootprint` | `library add -footprint` |
| Package pin shape | Footprint pad template | `library add -pad` / `library add -fpn` |
| Component CMP | `SemanticComponent` | `layout add -component` |
| Component TOP pin | `SemanticPin` | `layout add -component ... -pin ... -net` |
| PRP / attrlist | Attributes | Part attributes, metadata, coverage |

## Common Risk Areas

- Treating `$NONE$` as a normal electrical net instead of mapping explicit no-net references to AuroraDB `NoNet`.
- Ignoring `orient_def` mirror semantics, producing incorrect pad or component-pin rotations.
- Inferring a shared footprint pin layout from one placed component, causing different rotations of the same footprint to contaminate each other.
- Parsing only standard symbols and dropping user-defined pad shapes.
- Grouping surface islands and holes incorrectly, losing voids or reversing copper.
- Ignoring negative polarity, which can break plane cutouts or antipads.
- Merging via templates only by drill diameter while ignoring layer span.
- Exporting document or drawing layers as fabricated electrical net geometry.
- Dropping `attrlist` or `sysattr` content, losing material, thickness, or manufacturing constraints.
- Omitting source references, making conversion differences hard to debug.

## Current Project Principles

The project's ODB++ to Semantic/AuroraDB pipeline should continue to follow these principles:

- ODB++ format JSON preserves high-fidelity source information; Semantic is a unified semantic projection.
- Important objects retain `SourceRef` for tracing AuroraDB output back to ODB++ files.
- Geometry conversion should prefer fidelity first and degrade according to AuroraDB capability.
- Manufacturing and DFM data that cannot be mapped yet should go into attributes, geometry hints, or coverage reports.
- Positive no-net trace/arc/polygon objects on routable layers can be exported as AuroraDB `NoNet` geometry; document/profile drawing objects and negative cutouts should remain separate from electrical net geometry.
- Component, pin, pad, and footprint mapping should prioritize EDA/package structure over geometric proximity alone.

## Future Work

- Cover more standard symbols, especially thermal, donut, rounded, and chamfered rectangle variants.
- Improve user-defined symbols with nested surfaces, negative features, and arc edges.
- Map more of `stackup.xml` into material and stackup models.
- Define export policy for soldermask, paste, silkscreen, and assembly layers.
- Map backdrill, capped-via, IPC via type, and related manufacturing attributes.
- Add component variant and BOM selection support.
- Add more regression cases for `$NONE$`, negative features, surface voids, drill spans, and mirrored `orient_def` values.
