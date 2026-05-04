<a id="top"></a>
# Semantic 语义层变更记录 / Semantic Layer Changelog

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

## 0.7.5

- ALG -> SemanticBoard 现在会按 `GRAPHIC_DATA_10` 区分 `CONNECT`、`SHAPE` 和 `VOID`：`CONNECT` 仍导出 trace / arc，`SHAPE` 会按 `RECORD_TAG` group 聚合为 polygon，`VOID` 会作为 polygon void 导出到 `geometry.voids`。
- BRD -> SemanticBoard 现在会把 track / shape segment 坐标链导出为 trace、arc 和 polygon，并把 0x34 keepout 链挂到 shape polygon 的 `geometry.voids`。
- Semantic JSON schema 保持 `0.7.1`；字段结构不变，但 Allegro 来源的 `primitives` 会从大量未分组线/弧恢复为可导出的走线、铜皮 polygon 和 `PolygonHole`。

## 0.7.4

- ALG -> SemanticBoard 现在会把 Cadence Allegro extracta 文本中的 conductor layer、net、component/package、pin、component pad、via template、via、trace/arc/rectangle primitive 和 board extents 转成统一语义对象，使 ALG -> AuroraDB 能输出 stackup、component placement、pad `NetGeom`、`NetVias.Via` 和布线图元。
- 对缺少 `CLASS=PIN` 铜皮 pad 记录但存在逻辑 pin 的 ALG pin，会保留 pin 并生成按源单位换算的默认圆形 pad，同时写入 `alg.default_pad_geometry` info 级 diagnostic。
- Semantic JSON schema 更新到 `0.7.1`；结构字段不变，但 `source_format` 枚举新增 `alg`。

## 0.7.3

- BRD -> SemanticBoard 现在会把物理 ETCH 层、net、placed pad bbox、component / pin / footprint、padstack via template 和 via 转成统一语义对象，使 BRD -> AuroraDB 能输出基础 stackup、component placement、pad `NetGeom` 和 `NetVias.Via`。
- Track / shape segment 链仍保留在 BRD source JSON 中，并通过 `brd.semantic_segment_geometry_deferred` diagnostic 标记后续补齐。
- Semantic JSON schema 保持 `0.7.0`；未新增字段，但 BRD 来源的 `shapes`、`via_templates`、`components`、`pins`、`pads` 和 `vias` 数量会从空集合变为可导出的基础几何。

## 0.7.1

- AEDB polygon pad shape 的 arc-height 映射现在遵循 AEDB raw-point 约定：`arc_height < 0` 写为 AuroraDB `CCW=Y`，使 semantic shape arc values 与 target exporter 保持一致。
- Semantic JSON schema 保持 `0.7.0`；字段结构不变，预期差异仅限 AEDB-derived polygon shape `values` 中的 arc direction marker。

## 0.7.0

- Semantic 主要 `geometry` 字段收敛为 typed hint model：`SemanticFootprint.geometry`、`SemanticViaTemplate.geometry`、`SemanticPad.geometry`、`SemanticVia.geometry`、`SemanticPrimitive.geometry` 和 `SemanticBoard.board_outline` 现在有显式 schema，同时保留 extra metadata。
- AEDB adapter 会把 path/polygon/void arc geometry 转成 typed primitive geometry；ODB++ adapter 和 AuroraDB exporter 改为通过 typed geometry 的 `.get()` 兼容读取 shape、rotation、arc、void 和 matched pad metadata。
- Semantic JSON schema 更新为 `0.7.0`；JSON 字段名保持兼容，但 schema 从裸 `dict[str, Any]` 变为 typed geometry definitions。
- 使用私有 ODB++ 样本验证 `layers=32`、`components=682`、`pads=24472`、`vias=5466`、`primitives=111009`、`diagnostics=2`；使用私有 AEDB 样本验证 minimal/full AuroraDB 14 个输出文件 SHA-256 完全一致。

## 0.6.38

- AEDB -> SemanticBoard 不再复制或生成 AuroraDB 私有 `NetGeom` 运行时缓存；trace / polygon primitive 只携带显式、可序列化的 `geometry` 数据。
- AEDB minimal profile 进入 Semantic 时使用 source model 中保留的 `center_line`、`raw_points` 和 void raw geometry，direct AuroraDB exporter 在目标层重新生成 `Line` / `Larc` / `Polygon` / `Parc`。
- Semantic JSON schema 保持 `0.6.0`；字段结构不变，预期 Semantic JSON 除版本 metadata 外不新增私有字段，AEDB minimal profile 路径可获得更完整的 geometry 内容。

## 0.6.37

- ODB++ -> SemanticBoard 现在会将标准 `rect` / `rect...xr` / `oval` symbol 的长轴规范化到 Semantic shape `+X` 方向；源 symbol 为纵向定义时，`90 deg` symbol-axis basis 会折算到 `SemanticPad.geometry.rotation`。
- Via template refinement 在计算 matched pad / antipad 相对旋转时，会根据 shape 几何判断 `180 deg` 半周对称；中心在原点的 circle / rectangle / rounded-rectangle，以及可判定半周对称的 polygon，会使用半周等价归一。
- Semantic JSON schema 保持 `0.6.0`；该版本不新增字段，但 ODB++ 来源的 oriented pad shape 宽高、pad rotation、refined slotted via template 数量和 layer pad rotation 可能变化。

## 0.6.36

- ODB++ -> SemanticBoard 的 via template refinement 撤销 v0.6.35 引入的 shape-axis 扣除，恢复 `theta_layer_pad_relative = normalize(theta_pad - theta_via)`。
- AuroraDB 会将 shape 的 `width` / `height` 作为几何定义保留，再叠加 `ViaList` layer row rotation 和 `NetVias.Via` instance rotation；因此 Semantic 相对角不应预先消除 oval / rounded-rectangle 的默认长轴方向。
- Semantic JSON schema 保持 `0.6.0`；该版本不新增字段，但 ODB++ 来源的 refined slotted via template layer pad rotation 可能变化。

## 0.6.35

- ODB++ -> SemanticBoard 的 via template refinement 现在会在计算 matched pad / antipad 相对旋转时考虑 oriented shape 的默认长轴方向。
- 当 reference barrel 是有方向的 `Rectangle` / `RoundedRectangle`，而 matched pad 的 `width` / `height` 默认轴与 barrel 不一致时，先扣除 shape axis delta，再写入 `via_templates.geometry.layer_pad_rotations`。
- Semantic JSON schema 保持 `0.6.0`；该版本不新增字段，但 ODB++ 来源的 refined slotted via template layer pad rotation 可能变化。

## 0.6.34

- ODB++ -> SemanticBoard 的 slotted via barrel 现在统一使用 `+X` 轴作为旋转基准：`RoundedRectangle` shape 保存为 `total_length x width`，`SemanticVia.geometry.rotation` 使用 `atan2(-dy, dx)` 表示 ODB++ 顺时针正角。
- 该修复使 slotted via instance rotation、barrel shape 和 `via_templates.geometry.layer_pad_rotations` 使用同一坐标基准，避免下游 AuroraDB `NetVias.Via` / `ViaList` 输出比源 pad 方向偏 `90 deg`。
- Semantic JSON schema 保持 `0.6.0`；该版本不新增字段，但 ODB++ 来源的 slotted via `shapes` 值、`vias.geometry.rotation` 和 refined `via_templates.geometry.layer_pad_rotations` 会变化。

## 0.6.33

- AEDB -> SemanticBoard 的 via template layer pads 现在按 stackup 物理顺序保存，不再按 layer name 字符串排序。
- 该修复会让 AEDB 来源的 `via_templates.layer_pads` 顺序与 `layers.order_index` / AuroraDB `LayerStackup.MetalLayers` 一致，避免下游导出或审查时把排序错位误判为 via 层缺失。
- 新增 `odbpp_to_semantic_mapping.md`，整理 ODB++ 对象到 Semantic 对象的字段级映射、via template 细化逻辑和旋转关系。
- 明确 ODB++ -> Semantic 仍保存 clockwise-positive 角度；AuroraDB `ViaList` layer row 的 `CCW=Y` 数值转换属于 target exporter 边界。
- Semantic JSON schema 保持 `0.6.0`；该版本不新增字段，但 AEDB 来源的 `via_templates.layer_pads` 顺序可能变化。

## 0.6.32

- ODB++ -> SemanticBoard 的 via template pad 匹配候选现在先按与 via 中心的距离排序，再在同距离下优先 component pad，避免容差匹配时较远 component pad 覆盖同坐标真实 via pad。
- AuroraDB exporter 输出 `ViaList` layer pad rotation 时会把 ODB++ clockwise 相对角转换为 `CCW=Y` 下的 counter-clockwise 角度，符合 AuroraDB via layer pad 字段语义。
- Semantic JSON schema 保持 `0.6.0`；该版本不新增字段，但 AuroraDB `layout.db` / `aaf/design.layout` 中非零 via template layer pad rotation 的符号可能变化。

## 0.6.31

- ODB++ -> SemanticBoard 的 via template pad 匹配现在支持同 net / 同 layer 下 `0.001` 源单位内的微小坐标偏差，避免 component pin pad 与 drill/via 中心不完全一致时漏掉 pad。
- 匹配到 component pad 时会优先使用 component pad shape，并把 pad 相对 via instance 的旋转写入 `via_templates.geometry.layer_pad_rotations`，供 AuroraDB exporter 写出 layer pad rotation。
- Semantic JSON schema 保持 `0.6.0`；该版本不新增字段，但 ODB++ 来源的 `via_templates.geometry` 可能增加 `layer_pad_rotations`，`via_templates` 数量可能因不同 pad shape/rotation signature 而增加。

## 0.6.30

- AEDB -> SemanticBoard 现在会把 `Round45`、`Round90`、`Bullet` 和 `NSidedPolygon` pad geometry 构造成 `SemanticShape(kind="polygon")`。
- 该修复会让 AEDB -> AuroraDB 的 footprint pad/template geometry 保留这些参数化 pad shape，避免 `Round45` / `Round90` 退化为 circle，也避免 `Bullet` / `NSidedPolygon` 被跳过。
- Semantic JSON schema 保持 `0.6.0`；该版本不新增字段，但 AEDB 来源的 `shapes` 和 `via_templates.layer_pads` 可能增加或改变 shape 类型。

## 0.6.29

- ODB++ -> SemanticBoard 现在会把 drill 层带 net 的 `L` 线型钻孔转换为 slotted `SemanticVia`，使用 `RoundedRectangle` barrel shape，并在 via geometry 中保留 slot 宽度、长度和旋转。
- ODB++ via template 的 pad/antipad 匹配移到 component pad 创建之后执行，并在普通 pad 缺失时回退 component pad，避免 component 绑定的 GND slot via pad 退化为 drill-hole 尺寸。
- Semantic JSON schema 保持 `0.6.0`；该版本不新增字段，但 ODB++ 来源的 `shapes`、`via_templates` 和 `vias` 数量可能增加。

## 0.6.28

- AEDB -> SemanticBoard 现在会把 `PadPropertyModel.raw_points` 中的 polygonal pad 顶点转换为 `SemanticShape(kind="polygon")`。
- 该修复会让 AEDB -> AuroraDB 的 `FootPrintSymbol` pad geometry 补齐此前因 `NoGeometry` 普通 pad 参数而缺失的 polygon `PartPad`。
- Semantic JSON schema 保持 `0.6.0`；该版本不新增 semantic 字段，但 AEDB 来源的 `shapes` 和 `via_templates.layer_pads` 可能增加。

## 0.6.27

- ODB++ -> SemanticBoard 标准 symbol 解析补齐 `s...` square、`di...` diamond、`rect...xr...` 圆角矩形，以及单边为 0 的退化 `oval...`。
- ODB++ component pin 现在能优先绑定真实 feature pad shape；package pin shape 仅作为兜底来源，减少小器件 pad size 被 package marker 覆盖的情况。
- AuroraDB target 导出会按 component footprint pad shape signature 拆分 part/footprint variant，使同一 source footprint 下的 square、diamond、oval/rounded pad 可以分别写出。
- Semantic JSON schema 保持 `0.6.0`；该版本不新增字段，但 ODB++ 来源的 `shapes`、`pads` 和 pad/shape 引用数量可能增加。

## 0.6.26

- ODB++ -> SemanticBoard 的 package fallback 坐标推导现在会在 bottom-side component 上应用 local x-axis mirror，使由 package pin 生成的 placed pad 与 bottom component placement 的 AuroraDB/AFF `flipX` 约定一致。
- ODB++ -> AuroraDB target 导出会把 bottom-side component placement 写成 `flipX`，修正非对称 package 在底层 component layer 上的旋转/镜像方向。
- Semantic JSON schema 保持 `0.6.0`；除版本 metadata 外，仅缺少显式 component pin position、需要 package fallback 的 bottom-side pad 坐标可能变化。

## 0.6.25

- AuroraDB target 导出修正 AEDB footprint library 写出：同一个 footprint 名称被多个 part/variant 引用时只写一次 footprint pad/template geometry，避免重复 `PadTemplate.GeometryList` 让前端 pad geometry 与 `mPadList` 下标错位。
- Direct `parts.db` 生成和 AAF 编译收尾会为没有 pad geometry 的 footprint 补齐空 `MetalLayer top 1`，保证前端解析组件库时 footprint 至少具备 metal layer 容器。
- Semantic JSON schema 保持 `0.6.0`；该版本不新增 semantic JSON 字段。

## 0.6.24

- ODB++ 标准 symbol 数值现在统一按千分之一源单位解释，包括 `r76.2`、`r203.2` 等小数形式。
- ODB++ -> SemanticBoard 的 trace / arc `geometry.width` 不再把小数 round symbol 当成整源单位，避免下游 AuroraDB trace 宽度被放大 1000 倍。
- Semantic JSON schema 保持 `0.6.0`；该版本不新增 semantic JSON 字段。

## 0.6.23

- AuroraDB target 导出现在会在 direct `parts.db` 写出和 AAF 编译收尾阶段执行 footprint pad/pin 完整性修复。
- 每个 part 引用的 footprint 中，所有 `PartPad.PadIDs[0]` 都会保证能在该 part 的 `PinList.Pin.DefData` 第一字段中找到；缺失时会补齐对应 part pin。
- Semantic JSON schema 保持 `0.6.0`；该版本不新增 semantic JSON 字段。

## 0.6.22

- AEDB -> SemanticBoard 现在优先复制 AEDB source model 上的私有 AuroraDB trace / polygon 缓存，减少 semantic 构建阶段的重复几何遍历。
- 缓存缺失时仍回退到 semantic adapter 本地构建逻辑，兼容从显式 AEDB JSON 读取的流程。
- Semantic JSON schema 保持 `0.6.0`；预期 semantic JSON 内容除 `metadata.project_version` / `metadata.parser_version` 外保持等价。

## 0.6.21

- AEDB -> SemanticBoard 为 trace 增加运行时私有 AuroraDB `Line` / `Larc` 行缓存，缓存由 AEDB `center_line` 直接生成。
- 该缓存只服务 AEDB direct AuroraDB 导出，不参与 Pydantic 序列化和 semantic JSON schema。
- Semantic JSON schema 保持 `0.6.0`；预期 semantic JSON 内容除 `metadata.project_version` / `metadata.parser_version` 外保持等价。

## 0.6.20

- 优化 AEDB polygon / void 私有 AuroraDB `NetGeom` 缓存构建热路径，减少 arc 字段读取和转换中的重复函数调用。
- ODB++ -> AuroraDB 导出现在会在 package footprint pad 写出时，把 package pin 编号重映射到对应 component/part pin 名称，避免 `PartPad.PadIDs` 与 `PinList` 不一致。
- Semantic JSON schema 保持 `0.6.0`；该版本不新增 semantic JSON 字段。

## 0.6.19

- AEDB -> SemanticBoard 为 polygon / void 增加运行时私有 AuroraDB `NetGeom` 行缓存，缓存由 AEDB arc model 和 raw points 直接生成。
- 该缓存只服务 AEDB direct AuroraDB 导出，不参与 Pydantic 序列化和 semantic JSON schema。
- Semantic JSON schema 保持 `0.6.0`；预期 semantic JSON 内容除 `metadata.project_version` / `metadata.parser_version` 外保持等价。

## 0.6.18

- ODB++ step profile 现在会收集所有 `OB` contour，并优先选择 `I` 外轮廓中的最大闭合轮廓，避免复杂 profile 被后续 hole contour 覆盖。
- ODB++ -> AuroraDB pad 输出现在只把自身 layer 可映射到 signal/plane 的 pad 写入铜层；mask/paste pad 会保留在 semantic JSON 中，但不会再投影到 component 铜层。
- Semantic JSON schema 保持 `0.6.0`；转换内容会修正 `board_outline` 和下游 AuroraDB 铜层 geometry。

## 0.6.17

- AEDB -> SemanticBoard 内存转换现在保留 polygon / void 的 tuple points 和 AEDB arc model，避免大板在 semantic 构建阶段把所有 geometry 复制为 dict/list。
- 显式写 semantic JSON 时仍由 Pydantic 序列化为原有 JSON 形态；Semantic JSON schema 保持 `0.6.0`。
- 预期 semantic JSON 内容除 `metadata.project_version` / `metadata.parser_version` 外保持等价。

## 0.6.16

- AEDB -> SemanticBoard 新增可选 connectivity 构建开关；命令行可通过 `--skip-semantic-connectivity` 跳过 connectivity edge 和 connectivity diagnostics，用于只需要下游 AuroraDB 输出、不需要 semantic connectivity JSON 的性能场景。
- 默认仍会构建 connectivity，现有 semantic JSON 输出保持兼容。
- Semantic JSON schema 保持 `0.6.0`；默认输出预期除 `metadata.project_version` / `metadata.parser_version` 外不变。

## 0.6.15

- AEDB -> SemanticBoard 收尾阶段继续减少不必要复制；`with_computed_summary()` 直接刷新当前 board summary，不再复制整板对象。
- Semantic JSON schema 保持 `0.6.0`；预期 semantic JSON 内容除 `metadata.project_version` / `metadata.parser_version` 外不变。

## 0.6.14

- 优化 AEDB -> SemanticBoard 构建热路径：semantic id 标准化增加缓存，引用列表去重从逐次线性扫描改为本地 set 索引。
- AEDB -> SemanticBoard 构建完成时避免两次整板 `model_copy()`，直接填充 connectivity 和 diagnostics 后再计算 summary。
- Semantic JSON schema 保持 `0.6.0`；预期 semantic JSON 内容除 `metadata.project_version` / `metadata.parser_version` 外不变。

## 0.6.13

- ODB++ -> SemanticBoard 的去重策略从热路径逐次线性去重改为构建后统一去重，显著降低了大板子 semantic 构建时间。
- 大型 ODB++ 回归样本的 semantic 构建已经从约 44 分钟下降到约 1 分钟量级；当前主要热点转移到 primitive geometry 组装和对象创建。
- `semantic to-auroradb` / `semantic source-to-auroradb` 现在默认直接把 AuroraDB 写到输出目录，`aaf/` 仅在显式传入 `--export-aaf` 或显式选择 AAF 输出时保留。
- Semantic JSON schema 保持 `0.6.0`。

## 0.6.13

- Changed ODB++ -> SemanticBoard deduplication from repeated hot-path linear checks to post-build normalization, which sharply reduces semantic build time on large designs.
- Large ODB++ regression samples dropped from roughly 44 minutes of semantic build time to roughly the one-minute range; the remaining top hotspots are now primitive geometry assembly and object construction.
- `semantic to-auroradb` / `semantic source-to-auroradb` now write AuroraDB directly into the output directory by default; `aaf/` is kept only when `--export-aaf` is passed explicitly or when AAF output is chosen directly.
- Semantic JSON schema remains `0.6.0`.

## 0.6.12

- 新增 `semantic from-source`、`semantic source-to-aaf` 和 `semantic source-to-auroradb` CLI，可直接从 AEDB、AuroraDB 或 ODB++ 源路径构建 `SemanticBoard` 或导出目标格式。
- `semantic from-json` / `semantic from-source` 中的 `-o/--out` 现在只表示输出目录；`semantic.json` 只有显式传入 `--semantic-output` 时才会写出。
- 文档示例现在明确区分 JSON 文件流和源文件直通流程。
- Semantic JSON schema 保持 `0.6.0`。

## 0.6.12

- Added `semantic from-source`, `semantic source-to-aaf`, and `semantic source-to-auroradb` CLI commands so `SemanticBoard` and downstream exports can be built directly from AEDB, AuroraDB, or ODB++ source paths.
- In `semantic from-json` / `semantic from-source`, `-o/--out` now only specifies the output directory; `semantic.json` is written only when `--semantic-output` is passed explicitly.
- Documentation examples now distinguish the JSON file workflow from the direct source workflow.
- Semantic JSON schema remains `0.6.0`.

## 0.6.11

- `write_aaf_from_semantic()` 不再在输出根目录同步写入 `design.layout` / `design.part` 兼容副本，AAF 文件只保留在 `aaf/` 下。
- 复用输出目录时，导出器会清理根目录残留的旧版 `design.layout` / `design.part`，避免与当前 AAF 结果混淆。
- `write_aurora_conversion_package()` 的默认行为保持不变：继续默认编译 `auroradb/`，`aaf/` 作为中间过渡目录保留。
- Semantic JSON schema 保持 `0.6.0`。

## 0.6.10

- Aurora/AAF 导出现在会在共享 part name 映射到多个 footprint 时生成 footprint-specific part 变体，避免 component placement 引用到 footprint 错误的 part。
- ODB++ 内层 short-cline component 即使共享占位 part name，也能在 `design.layout`、`design.part` 和编译后的 AuroraDB `parts.db` 中保留按层区分的 footprint 绑定。
- exporter 现在会在刷新规范 `aaf/` 文件的同时同步刷新根目录 `design.layout` / `design.part` 兼容副本。
- Semantic JSON schema 保持 `0.6.0`。

## 0.6.9

- ODB++ component placement layer 现在会在所有已解析 pin pad 位于同一个金属层时使用该共同金属层，使内层器件可导出为 `COMP_<layer>`。
- ODB++ pin 在其 pad 位于同一层时会携带真实 pad layer；原始 ODB++ component layer 保存在 `SemanticComponent.attributes["ODBPP_COMPONENT_LAYER"]`。
- Semantic JSON schema 保持 `0.6.0`。

## 0.6.8

- ODB++ rotation 导出现在按源格式“正角为顺时针”的约定处理，不再套用 AEDB 路径的符号翻转。
- Component placement、绝对 pin pad shape placement、package footprint pad，以及从 placed pad 反推 footprint pad 的 fallback 路径现在使用同一套 ODB++ 旋转关系。
- Semantic JSON schema 保持 `0.6.0`。

## 0.6.7

- ODB++ 中位于 signal/plane 层的正极性无 net trace/arc/polygon primitive 现在会自动归入 `SemanticNet(name="NoNet", role="no_net")`。
- 这些 primitive 会通过现有 Aurora/AAF trace/arc/polygon 导出路径生成 AuroraDB `NoNet` net geometry；`PROFILE`/非布线层和 negative/cutout primitive 不会提升。
- Semantic JSON schema 保持 `0.6.0`。

## 0.6.6

- ODB++ net record 中的保留无网络名（`$NONE$`、`$NONE`、`NONE$`、`NoNet`）现在会规范化为一个 `SemanticNet(name="NoNet", role="no_net")`。
- Aurora/AAF 导出和 AuroraDB 编译会保留 `NoNet` keyword，避免生成 `$NONE$`、`NONE$` 或 `NONET`。
- Semantic JSON schema 保持 `0.6.0`。

## 0.6.5

- Aurora/AAF polygon void 导出现在支持 ODB++ 用起点等于终点的一条 `OC` 弧表达的整圆 hole。
- 这类整圆 void 会拆成两段 `Parc` 半圆顶点写入 `PolygonHole`，避免因少于 3 个 polygon vertex 被跳过。
- Semantic JSON schema 保持 `0.6.0`。

## 0.6.4

- ODB++ point feature 的 `orient_def` 现在会进入 pad geometry，支持 `0..7` legacy rotation/mirror flag，以及 `8/9 <angle>` 任意角度。
- ODB++ pad mirror flag 现在会在支持的位置导出为 Aurora/AAF `-flipX` / `-flipY` transform option。
- 从 ODB++ placed pad 生成 footprint pad rotation 时，现在会先使用源 pad orientation，再推导 component-local footprint transform。
- Semantic JSON schema 保持 `0.6.0`。

## 0.6.3

- ODB++ component pin-to-pad 映射现在把 component 自身的 `component_index` 和 `pin_index` 作为 EDA net feature reference 的主键。
- component 文件 pin 行里的引用字段仍作为回退路径，但在主键可用时不再额外挂入无关 pad。
- Aurora/AAF footprint pad rotation 导出现在会归一化局部 pad 旋转值，避免生成超出常规范围的 part footprint rotation。
- Semantic JSON schema 保持 `0.6.0`。

## 0.6.2

- ODB++ via template 细化现在会按 via location 和 layer，从负极性 pad feature 推断 layer antipad。
- 位于 via 位置的 no-net negative pad primitive 现在可以填充 `SemanticViaTemplateLayer.antipad_shape_id`，同网正极性 pad 仍用于填充普通 layer pad shape。
- ODB++ conversion coverage 新增 via-template antipad 覆盖指标。
- Semantic JSON schema 保持 `0.6.0`。

## 0.6.1

- ODB++ surface 转换现在使用 contour polarity（`I` island / `H` hole），不再假设第一个 contour 是唯一外轮廓、后续所有 contour 都是 hole。
- 多 island 的 ODB++ `S` feature 现在会按 island 生成多个 semantic polygon primitive，并在 geometry hint 中保留源 contour index、contour polarity、group count 和 hole contour。
- ODB++ conversion coverage 新增 multi-island surface 与 polygon-void 覆盖率指标。
- Semantic JSON schema 保持 `0.6.0`。

## 0.6.0

- ODB++ 转换现在使用 layer `attrlist` 数据填充 Semantic material，以及 signal/plane 和 dielectric 层的 stackup thickness。
- 当可按 net、location 和 layer span 匹配 drill feature 与 signal-layer pad 时，ODB++ via template 会使用匹配到的 layer pad shape 细化。
- `SemanticComponent` 和 `SemanticFootprint` 现在保留源 component/package 属性，Aurora/AAF part 导出会把共享 part 属性写入 `design.part`。
- Semantic JSON schema 版本更新为 `0.6.0`。

## 0.5.3

- Aurora/AAF 导出现在会在 ODB++ 转换中区分 part name 和 footprint symbol：`library add -p` 将 part 映射到真实 package/footprint，不再额外生成以 part number 命名的空 footprint。
- ODB++ 转换 coverage 的 `component_placement_count` 现在只统计 component 放置命令，不再混入 component pin/net 绑定命令。
- Semantic JSON schema 保持 `0.5.0`。

## 0.5.2

- ODB++ 无 net 可绘图 primitive 仍保留在 `SemanticPrimitive` 和转换 coverage 中，但 Aurora/AAF 导出默认不再生成 `ODBPP_DRAWING` logic geometry。
- Semantic JSON schema 保持 `0.5.0`。

## 0.5.1

- ODB++ adapter 现在会把所有解析到的 package 发布为 `SemanticFootprint`，包括未被 placed component 引用的 package body geometry。
- ODB++ 无 net 的可绘图 primitive 会在可映射布线层上进入 Semantic coverage 统计。
- Semantic JSON schema 保持 `0.5.0`。

## 0.5.0

- 顶层新增 `board_outline`，源 profile 几何现在可以从统一 Semantic 模型访问，并可导出为 AuroraDB board outline。
- `SemanticFootprint`、`SemanticViaTemplate`、`SemanticVia` 新增 `geometry`，用于保存 package body outline、drill tool metadata 和 via instance 几何提示。
- ODB++ 转换现在会把 profile 几何映射到 `board_outline`，把 package body/outlines 映射到 footprint geometry，并把可匹配的 drill tools 写入 via template/instance geometry。
- Aurora/AAF 导出现在会写 semantic board outline 和 footprint body geometry；CLI 可生成 ODB++ 转换覆盖率报告。
- Semantic JSON schema 版本更新为 `0.5.0`。

## 0.4.7

- ODB++ surface contour 中的 `OC` 记录现在会保留为 `SemanticPrimitive.geometry.arcs` 和 `geometry.voids[].arcs` 中的 polygon arc 边。
- ODB++ polygon 与 polygon shape 导出现在会输出 Aurora/AAF 5 值 polygon arc 顶点，让曲线 contour 边编译到 AuroraDB 后成为 `Parc`。
- ODB++ 独立 `A` arc feature 现在会转换为 semantic arc primitive；当源 arc 有 net 且可解析出正的圆形 symbol 线宽时，会导出为 `Larc` net geometry。
- Semantic JSON schema 版本保持 `0.4.0`。

## 0.4.6

- ODB++ 转换现在按 drill layer + symbol 构建 via template，不再把不同 layer span 的相同 drill symbol 合并成一个 template。
- ODB++ via 现在会携带从 matrix start/end layer 推导出的 `layer_names`，via template 也会为跨越的 signal layers 写入 layer pad entries。
- ODB++ component 转换现在会使用已解析的 EDA package definitions 和 package pin geometry，在缺少 pin-associated `FID` pad feature 时回退生成 component pad。
- ODB++ pad geometry 现在分别记录 dcode 与 orientation，不再把 point dcode 当作 pad rotation。
- Semantic JSON schema 版本保持 `0.4.0`。

## 0.4.5

- ODB++ 转换现在会把关联到 pin 的 `FID` pad feature 映射为 component-owned semantic pad。
- ODB++ footprint 导出现在能拿到 component pad geometry 和 pin-pad 绑定，因此 `design.part` 会包含 footprint pad template 与 pad placement。
- 当存在 symbol library contour 时，ODB++ 自定义 pad symbol 会转换为 semantic polygon shape。
- ODB++ rotation 值进入 exporter 前会从“度”转换为“弧度”。
- Polygon shape 导出现在会把第一个 polygon 值保留为顶点数量，只对坐标值做单位转换。
- Semantic JSON schema 版本保持 `0.4.0`。

## 0.4.4

- 将 ODB++ semantic adapter 中的 Python 3.12 泛型函数语法改为 Python 3.10 兼容的 `TypeVar` 写法。
- Semantic JSON 输出结构保持 `0.4.0`；这是兼容性修复，预期不改变 JSON payload 内容。

## 0.4.3

- ODB++ adapter 现在会把 EDA `FID` feature 引用和 `SNT TOP T/B` pin 引用映射到 semantic net connectivity。
- ODB++ line feature 在可解析圆形 symbol 时会转换为带 center line 和 width shape 的 trace primitive。
- ODB++ surface feature 会根据解析出的 contour 转换为 polygon primitive。
- ODB++ pad/drill point feature 在 symbol 可转换为 AuroraDB shape 时会转换为 semantic pad 或 via。
- ODB++ 组件现在会根据层级 component 记录生成 footprint、component 和 pin。
- Aurora/AAF 导出现在支持直接读取 `SemanticPad.geometry["shape_id"]`，用于已经解析出 pad geometry 的源格式。
- Semantic JSON schema 版本保持 `0.4.0`。

## 0.4.2

- AEDB adapter 现在会把 polygon 和 polygon void 的 arc 明细保留到 `SemanticPrimitive.geometry.arcs` 与 `geometry.voids[].arcs`。
- Aurora/AAF 导出现在会把 polygon 和 void 的曲线边输出为 5 值 polygon arc 顶点，编译到 AuroraDB 后成为 `Parc`。
- 弧线方向沿用 trace `Larc` 已使用的 AEDB->AAF 约定：AEDB arc height 为负时输出 `Y`，为正时输出 `N`；缺少 height 时才用 `is_ccw` 兜底。
- Semantic JSON schema 版本保持 `0.4.0`。

## 0.4.1

- Aurora/AAF 导出新增 component placement、net pin、trace net geometry 和 polygon net geometry 输出；带 void 几何的 polygon 会输出为 PolygonHole。
- Trace 输出现在按 Aurora/AAF 对象语义生成线宽 Circle shape，并把 AEDB center line 中的 arc marker 转换为 `Larc`。
- Pin pad 输出现在拆成 pad 铜皮 shape placement 和 net pin binding 两部分，对齐 AEDB->AAF 参考程序的对象结构。
- `design.part` 现在会生成 footprint pad template、pad geometry 和 footprint pin placement，用于描述 part、footprint、pad 与 pin 的关系。
- AEDB adapter 现在会把 polygon 的 `is_void`、`void_ids` 和 `voids` 写入 `SemanticPrimitive.geometry`，用于输出和追溯 polygon 挖空关系。
- `design.part` 现在会生成 part 与 footprint 条目，并为 part 写入去重后的 pin 列表。
- Semantic JSON schema 版本保持 `0.4.0`。

## 0.4.0

- 新增 `SemanticShape`，用于表达 AuroraDB `Circle`、`Rectangle`、`RoundedRectangle`、`Polygon` 等 shape 语义。
- 新增 `SemanticViaTemplate` 和 `SemanticViaTemplateLayer`，用于表达 AuroraDB `ViaList` 的 barrel、pad 和 antipad shape 引用。
- `SemanticVia` 新增 `name` 和 `template_id`，用于把 AEDB padstack instance 连接到 semantic via template。
- AEDB adapter 会将 padstack definition 中的 drill hole、pad、antipad 和 thermal pad 几何转换为 semantic shape 和 via template。
- Aurora/AAF 导出会生成 `layout add -g`、`layout add -via` 和 net via placement 命令。
- 新增 AEDB 到 Semantic 转换说明文档。
- Semantic JSON schema 版本更新为 `0.4.0`。

## 0.3.0

- 新增 `SemanticMaterial`，用于保留材料的导电率、介电常数和介质损耗角正切。
- `SemanticLayer` 新增 `material_id`、`fill_material` 和 `fill_material_id`，用于把 layer 与统一材料表关联。
- AEDB adapter 会将 `materials` 和 dielectric stackup layer 转换到统一语义模型。
- 新增 `semantic to-aaf` 和更新 `semantic to-auroradb`，输出 Aurora/AAF 转换包：`design.layout`、`design.part`、`stackup.dat` 和 `stackup.json`。
- `to-auroradb` 默认额外编译 AuroraDB 子目录；dielectric layer 写入 stackup 文件，不写成 AuroraDB `MetalLayer`。
- Semantic JSON schema 版本更新为 `0.3.0`。

## 0.2.0

- 新增 `SemanticFootprint` 和 `SemanticPad`，用于表达封装、焊盘以及其与 component、pin、net 的关系。
- AEDB adapter 会根据 component part 和 pin/padstack 字段生成 footprint、pad 与 pin-pad 绑定。
- AuroraDB adapter 会根据 parts footprint symbol、part pin map 和 layout net pin 生成 footprint、pad 与 pin-pad 绑定。
- ODB++ adapter 会根据 component package 字段生成 footprint 关系。
- 新增 component-footprint、component-pad、footprint-pad、pin-pad 和 pad-net connectivity edge。
- 新增连接一致性诊断，用于报告已存在引用指向缺失语义对象的情况。

## 0.1.0

- 新增 `SemanticBoard` 语义模型，覆盖 layer、net、component、pin、via、primitive、connectivity 和 diagnostics。
- 新增 AEDB、AuroraDB、ODB++ 到 semantic 模型的 adapter。
- 新增基础 connectivity edge 生成逻辑。
- 新增 `aurora-translator semantic from-json` 和 `aurora-translator semantic schema` CLI。
- 新增 semantic JSON schema 文档。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

## 0.7.5

- ALG -> SemanticBoard now distinguishes `CONNECT`, `SHAPE`, and `VOID` by `GRAPHIC_DATA_10`: `CONNECT` still exports traces/arcs, `SHAPE` records are grouped by `RECORD_TAG` into polygons, and `VOID` records are exported through `geometry.voids`.
- BRD -> SemanticBoard now exports track and shape segment coordinate chains as traces, arcs, and polygons, and attaches 0x34 keepout chains to shape polygons through `geometry.voids`.
- Semantic JSON schema remains `0.7.1`; the field structure is unchanged, but Allegro-derived `primitives` now collapse large ungrouped line/arc sets into exportable routing, copper polygons, and `PolygonHole` geometry.

## 0.7.4

- ALG -> SemanticBoard now maps Cadence Allegro extracta conductor layers, nets, components/packages, pins, component pads, via templates, vias, trace/arc/rectangle primitives, and board extents into unified semantic objects, enabling ALG -> AuroraDB output for stackup, component placement, pad `NetGeom`, `NetVias.Via`, and routed primitives.
- For ALG pins that have logical pin records but no matching `CLASS=PIN` copper pad records, the adapter keeps the pin, creates a source-unit-scaled default circular pad, and emits an `alg.default_pad_geometry` info diagnostic.
- Semantic JSON schema is updated to `0.7.1`; field structure is unchanged, but the `source_format` enum now includes `alg`.

## 0.7.3

- BRD -> SemanticBoard now converts physical ETCH layers, nets, placed-pad bounding boxes, components / pins / footprints, padstack via templates, and vias into unified semantic objects, so BRD -> AuroraDB can emit basic stackup, component placements, pad `NetGeom`, and `NetVias.Via` records.
- Track and shape segment chains remain in BRD source JSON and are flagged by the `brd.semantic_segment_geometry_deferred` diagnostic for later mapping.
- Semantic JSON schema remains `0.7.0`; no fields were added, but BRD-derived `shapes`, `via_templates`, `components`, `pins`, `pads`, and `vias` now populate exportable base geometry instead of empty collections.

## 0.7.1

- AEDB polygon pad shape arc-height mapping now follows the AEDB raw-point convention: `arc_height < 0` is emitted as AuroraDB `CCW=Y`, keeping semantic shape arc values aligned with the target exporter.
- Semantic JSON schema remains `0.7.0`; field structure is unchanged, and expected differences are limited to arc direction markers in AEDB-derived polygon shape `values`.

## 0.7.0

- The main Semantic `geometry` fields now use typed hint models: `SemanticFootprint.geometry`, `SemanticViaTemplate.geometry`, `SemanticPad.geometry`, `SemanticVia.geometry`, `SemanticPrimitive.geometry`, and `SemanticBoard.board_outline` have explicit schema while retaining extra metadata.
- The AEDB adapter converts path/polygon/void arc geometry into typed primitive geometry; the ODB++ adapter and AuroraDB exporter read shape, rotation, arc, void, and matched-pad metadata through typed geometry `.get()` compatibility.
- Semantic JSON schema is updated to `0.7.0`; JSON field names remain compatible, but the schema changes from bare `dict[str, Any]` to typed geometry definitions.
- Verified a private ODB++ sample with `layers=32`, `components=682`, `pads=24472`, `vias=5466`, `primitives=111009`, `diagnostics=2`; verified a private AEDB sample where minimal/full AuroraDB outputs have identical SHA-256 hashes across all 14 files.

## 0.6.38

- AEDB -> SemanticBoard no longer copies or builds AuroraDB-private runtime `NetGeom` caches; trace / polygon primitives carry only explicit, serializable `geometry` data.
- When AEDB minimal-profile payloads enter Semantic, they use source-model `center_line`, `raw_points`, and void raw geometry; the direct AuroraDB exporter regenerates `Line` / `Larc` / `Polygon` / `Parc` output at the target layer.
- Semantic JSON schema remains `0.6.0`; field structure is unchanged, no private fields are added to Semantic JSON, and AEDB minimal-profile paths can carry more complete geometry content.

## 0.6.37

- ODB++ -> SemanticBoard now canonicalizes standard `rect` / `rect...xr` / `oval` symbols so their long axis maps to the Semantic shape `+X` direction; when a source symbol is vertically defined, its `90 deg` symbol-axis basis is folded into `SemanticPad.geometry.rotation`.
- Via-template refinement now derives `180 deg` half-turn symmetry from shape geometry before computing matched pad / antipad relative rotations. Centered circles, rectangles, rounded rectangles, and polygons that can be proven half-turn symmetric use half-turn-equivalent normalization.
- Semantic JSON schema remains `0.6.0`; this version adds no fields, but ODB++-derived oriented pad shape width/height, pad rotation, refined slotted via template count, and layer-pad rotation may change.

## 0.6.36

- ODB++ -> SemanticBoard via-template refinement reverts the shape-axis subtraction introduced in v0.6.35 and restores `theta_layer_pad_relative = normalize(theta_pad - theta_via)`.
- AuroraDB preserves a shape's `width` / `height` as geometry, then applies `ViaList` layer-row rotation and `NetVias.Via` instance rotation; Semantic relative angles therefore must not pre-remove default long-axis directions from oval / rounded-rectangle shapes.
- Semantic JSON schema remains `0.6.0`; this version adds no fields, but ODB++-derived refined slotted via template layer-pad rotations may change.

## 0.6.35

- ODB++ -> SemanticBoard via-template refinement now accounts for oriented shape default long-axis directions when computing matched pad / antipad relative rotations.
- When the reference barrel is an oriented `Rectangle` / `RoundedRectangle` and the matched pad's `width` / `height` default axis differs from the barrel, the shape-axis delta is removed before writing `via_templates.geometry.layer_pad_rotations`.
- Semantic JSON schema remains `0.6.0`; this version adds no fields, but ODB++-derived refined slotted via template layer-pad rotations may change.

## 0.6.34

- ODB++ -> SemanticBoard slotted via barrels now use the `+X` axis as the rotation basis: the `RoundedRectangle` shape is stored as `total_length x width`, and `SemanticVia.geometry.rotation` uses `atan2(-dy, dx)` as an ODB++ clockwise-positive angle.
- This keeps slotted via instance rotation, barrel shape, and `via_templates.geometry.layer_pad_rotations` on the same coordinate basis, preventing downstream AuroraDB `NetVias.Via` / `ViaList` output from being offset by `90 deg` from the source pad direction.
- Semantic JSON schema remains `0.6.0`; this version adds no fields, but ODB++-derived slotted via `shapes` values, `vias.geometry.rotation`, and refined `via_templates.geometry.layer_pad_rotations` change.

## 0.6.33

- AEDB -> SemanticBoard via-template layer pads now preserve physical stackup order instead of sorting layer names lexically.
- This keeps AEDB-derived `via_templates.layer_pads` aligned with `layers.order_index` / AuroraDB `LayerStackup.MetalLayers`, avoiding downstream export or review confusion where sorted layer order can look like missing via layers.
- Added `odbpp_to_semantic_mapping.md` documenting ODB++ object-to-Semantic field mapping, via-template refinement, and rotation relationships.
- Clarified that ODB++ -> Semantic still stores clockwise-positive angles; AuroraDB `ViaList` layer-row conversion to `CCW=Y` numeric values belongs at the target exporter boundary.
- Semantic JSON schema remains `0.6.0`; this version adds no fields, but AEDB-derived `via_templates.layer_pads` order may change.

## 0.6.32

- ODB++ -> SemanticBoard via-template pad matching now sorts candidates by distance to the via center first, then prefers component pads only at the same distance, preventing a farther component pad from overriding an exactly aligned real via pad during tolerant matching.
- The AuroraDB exporter now converts ODB++ clockwise relative angles to counter-clockwise angles under `CCW=Y` when writing `ViaList` layer pad rotation, matching AuroraDB via layer pad field semantics.
- Semantic JSON schema remains `0.6.0`; this version adds no fields, but nonzero via-template layer pad rotation signs may change in AuroraDB `layout.db` / `aaf/design.layout`.

## 0.6.31

- ODB++ -> SemanticBoard via-template pad matching now tolerates small coordinate offsets up to `0.001` source units on the same net and layer, preventing missed pads when component pin pads and drill/via centers are not exactly equal.
- When a component pad is matched, its pad shape is preferred and its rotation relative to the via instance is written to `via_templates.geometry.layer_pad_rotations` for AuroraDB layer pad rotation output.
- Semantic JSON schema remains `0.6.0`; this version adds no fields, but ODB++-derived `via_templates.geometry` may gain `layer_pad_rotations`, and `via_templates` may increase for distinct pad shape/rotation signatures.

## 0.6.30

- AEDB -> SemanticBoard now constructs `Round45`, `Round90`, `Bullet`, and `NSidedPolygon` pad geometry as `SemanticShape(kind="polygon")`.
- This lets AEDB -> AuroraDB footprint pad/template geometry preserve these parameterized pad shapes, avoiding `Round45` / `Round90` degradation to circles and avoiding skipped `Bullet` / `NSidedPolygon` shapes.
- Semantic JSON schema remains `0.6.0`; this version adds no fields, but AEDB-derived `shapes` and `via_templates.layer_pads` may increase or change shape type.

## 0.6.29

- ODB++ -> SemanticBoard now converts net-connected drill-layer `L` line drill features into slotted `SemanticVia` records, using `RoundedRectangle` barrel shapes and preserving slot width, length, and rotation in via geometry.
- ODB++ via-template pad/antipad matching now runs after component pads are created and falls back to component pads when regular pads are missing, preventing component-bound GND slot via pads from degrading to drill-hole size.
- Semantic JSON schema remains `0.6.0`; this version adds no fields, but ODB++-derived `shapes`, `via_templates`, and `vias` may increase.

## 0.6.28

- AEDB -> SemanticBoard now converts polygonal pad vertices from `PadPropertyModel.raw_points` into `SemanticShape(kind="polygon")`.
- This fills AEDB -> AuroraDB `FootPrintSymbol` pad geometry that was previously missing when scalar pad parameters reported `NoGeometry`.
- Semantic JSON schema remains `0.6.0`; this version adds no semantic fields, but AEDB-derived `shapes` and `via_templates.layer_pads` may increase.

## 0.6.27

- ODB++ -> SemanticBoard standard symbol parsing now supports `s...` squares, `di...` diamonds, `rect...xr...` rounded rectangles, and degenerate one-sided-zero `oval...` symbols.
- ODB++ component pins can now bind real feature pad shapes first; package pin shapes are kept only as a fallback, reducing cases where small component pad sizes are overwritten by package markers.
- AuroraDB target export splits part/footprint variants by component footprint pad shape signature, so square, diamond, and oval/rounded pads under the same source footprint can be written separately.
- Semantic JSON schema remains `0.6.0`; this release adds no fields, but ODB++ `shapes`, `pads`, and pad/shape references may increase.

## 0.6.26

- ODB++ -> SemanticBoard package fallback coordinate derivation now applies a local x-axis mirror for bottom-side components, so placed pads generated from package pins follow the same convention as AuroraDB/AAF component placement `flipX`.
- ODB++ -> AuroraDB target export now writes bottom-side component placements with `flipX`, fixing rotation/mirroring of asymmetric packages on bottom component layers.
- Semantic JSON schema remains `0.6.0`; aside from version metadata, only bottom-side pad coordinates inferred from package fallback may change when explicit component pin positions are missing.

## 0.6.25

- AuroraDB target export now writes AEDB footprint library pad/template geometry only once when multiple parts/variants reference the same footprint name, avoiding duplicated `PadTemplate.GeometryList` entries that desynchronize frontend pad geometries from `mPadList`.
- Direct `parts.db` generation and AAF compilation now add an empty `MetalLayer top 1` to footprints without pad geometry so the frontend always receives a metal-layer container for each footprint.
- Semantic JSON schema remains `0.6.0`; this release does not add semantic JSON fields.

## 0.6.24

- ODB++ standard symbol numbers are now consistently interpreted as one-thousandth of the source unit, including decimal forms such as `r76.2` and `r203.2`.
- ODB++ -> SemanticBoard trace / arc `geometry.width` no longer treats decimal round symbols as whole source units, preventing downstream AuroraDB trace widths from being inflated by 1000x.
- Semantic JSON schema remains `0.6.0`; this release does not add semantic JSON fields.

## 0.6.23

- AuroraDB target export now repairs footprint pad/pin integrity at the end of direct `parts.db` generation and AAF compilation.
- For every footprint referenced by a part, each `PartPad.PadIDs[0]` is guaranteed to be present in that part's `PinList.Pin.DefData` first field; missing part pins are added as needed.
- Semantic JSON schema remains `0.6.0`; this release does not add semantic JSON fields.

## 0.6.22

- AEDB -> SemanticBoard now copies private AuroraDB trace / polygon caches from AEDB source models first, reducing repeated geometry traversal during semantic construction.
- When caches are absent, the semantic adapter still falls back to its local cache-building logic for explicit AEDB JSON workflows.
- Semantic JSON schema remains `0.6.0`; semantic JSON content is expected to remain equivalent except `metadata.project_version` / `metadata.parser_version`.

## 0.6.21

- AEDB -> SemanticBoard now adds a runtime-private AuroraDB `Line` / `Larc` item-line cache for traces, generated directly from AEDB `center_line`.
- The cache is used only by AEDB direct AuroraDB export and is not included in Pydantic serialization or the semantic JSON schema.
- Semantic JSON schema remains `0.6.0`; semantic JSON content is expected to remain equivalent except `metadata.project_version` / `metadata.parser_version`.

## 0.6.20

- Optimized the AEDB polygon / void private AuroraDB `NetGeom` cache builder hot path, reducing repeated function calls for arc field access and conversion.
- ODB++ -> AuroraDB export now remaps package-footprint pad pin numbers to the corresponding component/part pin names when writing package footprint pads, avoiding `PartPad.PadIDs` versus `PinList` mismatches.
- Semantic JSON schema remains `0.6.0`; this release does not add semantic JSON fields.

## 0.6.19

- AEDB -> SemanticBoard now adds a runtime-private AuroraDB `NetGeom` line cache for polygon / void geometry, generated directly from AEDB arc models and raw points.
- The cache is used only by AEDB direct AuroraDB export and is not included in Pydantic serialization or the semantic JSON schema.
- Semantic JSON schema remains `0.6.0`; semantic JSON content is expected to remain equivalent except `metadata.project_version` / `metadata.parser_version`.

## 0.6.18

- ODB++ step profile conversion now collects every `OB` contour and prefers the largest closed `I` outer contour, preventing complex profiles from being overwritten by later hole contours.
- ODB++ -> AuroraDB pad export now emits only pads whose own layer maps to signal/plane copper; mask/paste pads remain available in semantic JSON but are no longer projected onto the component copper layer.
- Semantic JSON schema remains `0.6.0`; conversion content changes correct `board_outline` and downstream AuroraDB copper geometry.

## 0.6.17

- AEDB -> SemanticBoard in-memory conversion now preserves polygon / void tuple points and AEDB arc models, avoiding large-board geometry copies into dict/list payloads during semantic construction.
- Explicit semantic JSON writing is still serialized by Pydantic into the existing JSON shape; Semantic JSON schema remains `0.6.0`.
- Semantic JSON content is expected to remain equivalent except `metadata.project_version` / `metadata.parser_version`.

## 0.6.16

- AEDB -> SemanticBoard now has optional connectivity construction; the CLI can pass `--skip-semantic-connectivity` to skip connectivity edges and diagnostics when a run only needs downstream AuroraDB output rather than semantic connectivity JSON.
- Connectivity is still built by default, so existing semantic JSON output remains compatible.
- Semantic JSON schema remains `0.6.0`; default output is expected to remain unchanged except for `metadata.project_version` / `metadata.parser_version`.

## 0.6.15

- AEDB -> SemanticBoard finalization continues to reduce unnecessary copying; `with_computed_summary()` refreshes the current board summary directly instead of copying the whole board.
- Semantic JSON schema remains `0.6.0`; expected semantic JSON content is unchanged except for `metadata.project_version` / `metadata.parser_version`.

## 0.6.14

- Optimized the AEDB -> SemanticBoard hot path with cached semantic id normalization and local set indexes for reference-list deduplication instead of repeated linear scans.
- Avoided two full-board `model_copy()` calls at the end of AEDB -> SemanticBoard construction by filling connectivity and diagnostics before recomputing the summary.
- Semantic JSON schema remains `0.6.0`; expected semantic JSON content is unchanged except for `metadata.project_version` / `metadata.parser_version`.

## 0.6.11

- `write_aaf_from_semantic()` no longer writes root-level `design.layout` / `design.part` compatibility copies; AAF files now live only under `aaf/`.
- When reusing an output directory, the exporter removes stale root-level `design.layout` / `design.part` leftovers so they do not look like current output.
- The default `write_aurora_conversion_package()` behavior is unchanged: it still compiles `auroradb/` by default, while `aaf/` remains the transitional package directory.
- Semantic JSON schema remains `0.6.0`.

## 0.6.10

- Aurora/AAF export now creates footprint-specific part variants when shared part names map to multiple footprints, preventing component placements from referencing a part with the wrong footprint.
- ODB++ inner-layer short-cline components that share placeholder part names now keep their layer-specific footprint bindings through `design.layout`, `design.part`, and compiled AuroraDB `parts.db`.
- The exporter now refreshes root-level `design.layout` / `design.part` compatibility copies alongside the canonical `aaf/` files.
- Semantic JSON schema remains `0.6.0`.

## 0.6.9

- ODB++ component placement layers now use the common metal layer of resolved pin pads when all known pin pads share that layer, allowing inner-layer components to export as `COMP_<layer>`.
- ODB++ pins now carry the actual resolved pad layer when their pads share one layer; the original ODB++ component layer is preserved in `SemanticComponent.attributes["ODBPP_COMPONENT_LAYER"]`.
- Semantic JSON schema remains `0.6.0`.

## 0.6.8

- ODB++ rotations now export with the source format's clockwise-positive convention instead of passing through the AEDB-style sign inversion.
- Component placement, absolute pin-pad shape placement, package footprint pads, and fallback placed-pad-to-footprint derivation now share the same ODB++ rotation relationship.
- Semantic JSON schema remains `0.6.0`.

## 0.6.7

- Positive ODB++ no-net trace/arc/polygon primitives on signal/plane layers now join `SemanticNet(name="NoNet", role="no_net")`.
- These primitives use the existing Aurora/AAF trace/arc/polygon export path to generate AuroraDB `NoNet` net geometry; `PROFILE`/non-routable layers and negative/cutout primitives are not promoted.
- Semantic JSON schema remains `0.6.0`.

## 0.6.6

- ODB++ reserved no-net names in net records (`$NONE$`, `$NONE`, `NONE$`, and `NoNet`) now normalize to one `SemanticNet(name="NoNet", role="no_net")`.
- Aurora/AAF export and AuroraDB compilation preserve the `NoNet` keyword, avoiding `$NONE$`, `NONE$`, or `NONET` output names.
- Semantic JSON schema remains `0.6.0`.

## 0.6.5

- Aurora/AAF polygon-void export now supports full-circle ODB++ holes encoded as a single `OC` arc whose start point equals its end point.
- These full-circle voids are emitted as two semicircular `Parc` vertices inside `PolygonHole`, avoiding the previous skip when the contour had fewer than three polygon vertices.
- Semantic JSON schema remains `0.6.0`.

## 0.6.4

- ODB++ point-feature `orient_def` values are now decoded for pad geometry, including `0..7` legacy rotations/mirror flags and `8/9 <angle>` arbitrary rotations.
- ODB++ pad mirror flags now export as Aurora/AAF `-flipX` / `-flipY` transform options where supported.
- Footprint pad rotations generated from ODB++ placed pads now use the source pad orientation before deriving the component-local footprint transform.
- Semantic JSON schema remains `0.6.0`.

## 0.6.3

- ODB++ component pin-to-pad mapping now uses the component's own `component_index` and `pin_index` as the primary key for EDA net feature references.
- Component-file pin reference fields remain available as a fallback, but no longer add unrelated pads when the authoritative component/pin key is present.
- Aurora/AAF footprint pad rotation export now normalizes local pad rotation values, so generated part footprints avoid out-of-range rotation values.
- Semantic JSON schema remains `0.6.0`.

## 0.6.2

- ODB++ via template refinement now infers layer antipads from negative-polarity pad features matched by via location and layer.
- No-net negative pad primitives at the via location can now populate `SemanticViaTemplateLayer.antipad_shape_id`, while same-net positive pads continue to populate regular layer pad shapes.
- ODB++ conversion coverage now reports via-template antipad counts.
- Semantic JSON schema remains `0.6.0`.

## 0.6.1

- ODB++ surface conversion now uses contour polarity (`I` island / `H` hole) instead of assuming the first contour is the only outline and all later contours are holes.
- Multi-island ODB++ `S` features now produce one semantic polygon primitive per island, preserving source contour indices, contour polarities, group counts, and hole contours in geometry hints.
- ODB++ conversion coverage now reports multi-island surface and polygon-void coverage metrics.
- Semantic JSON schema remains `0.6.0`.

## 0.6.0

- ODB++ conversion now uses layer `attrlist` data to populate Semantic materials and stackup layer thickness for signal/plane and dielectric layers.
- ODB++ via templates are refined from matched signal-layer pad shapes when layer pads can be paired with drill features by net, location, and layer span.
- `SemanticComponent` and `SemanticFootprint` now preserve source component/package attributes, and Aurora/AAF part export writes shared part attributes into `design.part`.
- Updated the Semantic JSON schema version to `0.6.0`.

## 0.5.3

- Aurora/AAF export now keeps part names and footprint symbols separate for ODB++ conversions: `library add -p` maps each part to its real package/footprint, and duplicate empty footprints named after part numbers are no longer emitted.
- ODB++ conversion coverage now counts only component placement commands for `component_placement_count`, excluding component pin/net binding commands.
- Semantic JSON schema remains `0.5.0`.

## 0.5.2

- ODB++ no-net drawable primitives remain available in `SemanticPrimitive` objects and conversion coverage, but Aurora/AAF export no longer emits them as `ODBPP_DRAWING` logic geometry by default.
- Semantic JSON schema remains `0.5.0`.

## 0.5.1

- ODB++ adapters now publish every parsed package as a `SemanticFootprint`, including package body geometry for packages not referenced by placed components.
- ODB++ no-net drawable primitives are counted in Semantic coverage for mapped routable layers.
- Semantic JSON schema remains `0.5.0`.

## 0.5.0

- Added top-level `board_outline` so source profile geometry can be accessed from the unified Semantic model and exported as the AuroraDB board outline.
- Added `geometry` to `SemanticFootprint`, `SemanticViaTemplate`, and `SemanticVia` for package body outlines, drill tool metadata, and via instance geometry hints.
- ODB++ conversion now maps profile geometry into `board_outline`, package body/outlines into footprint geometry, and matched drill tools into via template/instance geometry.
- Aurora/AAF export now writes semantic board outline geometry and footprint body geometry; ODB++ conversion coverage reports can be generated from the CLI.
- Updated the Semantic JSON schema version to `0.5.0`.

## 0.4.7

- ODB++ surface contour `OC` records are now preserved as polygon arc edges in `SemanticPrimitive.geometry.arcs` and `geometry.voids[].arcs`.
- ODB++ polygon and polygon-shape export now emits 5-value Aurora/AAF polygon arc vertices so curved contour edges compile into AuroraDB `Parc` items.
- ODB++ standalone `A` arc features now become semantic arc primitives and can export as `Larc` net geometry when the source arc has net connectivity and a resolvable positive round-symbol width.
- The Semantic JSON schema version remains `0.4.0`.

## 0.4.6

- ODB++ conversion now builds via templates per drill layer and symbol instead of collapsing matching drill symbols across different layer spans.
- ODB++ vias now carry `layer_names` derived from matrix start/end layers, and their via templates include layer pad entries for the traversed signal layers.
- ODB++ component conversion now uses parsed EDA package definitions and package pin geometry as a fallback for component pad generation when no pin-associated `FID` pad feature is available.
- ODB++ pad geometry now records dcode/orientation separately and no longer treats point dcode as pad rotation.
- The Semantic JSON schema version remains `0.4.0`.

## 0.4.5

- ODB++ conversion now maps pin-associated `FID` pad features into component-owned semantic pads.
- ODB++ footprint export now receives component pad geometry and pin-pad bindings, so `design.part` includes footprint pad templates and placements.
- ODB++ symbol-library contours are converted to semantic polygon shapes for custom pad symbols when available.
- ODB++ rotation values are now converted from degrees to radians before entering the exporter.
- Polygon shape export now keeps the first polygon value as a vertex count while unit-converting only coordinate values.
- The Semantic JSON schema version remains `0.4.0`.

## 0.4.4

- Replaced Python 3.12 generic-function syntax in the ODB++ semantic adapter with Python 3.10-compatible `TypeVar` typing.
- Semantic JSON output schema remains `0.4.0`; this is a compatibility fix with no expected JSON payload changes.

## 0.4.3

- The ODB++ adapter now maps EDA `FID` feature references and `SNT TOP T/B` pin references into semantic net connectivity.
- ODB++ line features now become trace primitives with center lines and width shapes when round symbols can be resolved.
- ODB++ surface features now become polygon primitives from parsed contours.
- ODB++ pad/drill point features now become semantic pads or vias when their symbols can be converted to AuroraDB shapes.
- ODB++ components now produce footprints, components, and pins from hierarchical component records.
- Aurora/AAF export now accepts direct `SemanticPad.geometry["shape_id"]` references for source formats that already resolved pad geometry.
- The Semantic JSON schema version remains `0.4.0`.

## 0.4.2

- The AEDB adapter now preserves polygon and polygon-void arc details in `SemanticPrimitive.geometry.arcs` and `geometry.voids[].arcs`.
- Aurora/AAF export now emits curved polygon and void edges as 5-value polygon arc vertices, which compile into AuroraDB `Parc` items.
- Arc direction follows the AEDB-to-AAF convention used by trace `Larc`: negative AEDB arc height emits `Y`, positive height emits `N`, and `is_ccw` is used as a fallback when height is unavailable.
- The Semantic JSON schema version remains `0.4.0`.

## 0.4.1

- Aurora/AAF export now writes component placements, net pins, trace net geometry, and polygon net geometry; polygons with void geometry are emitted as PolygonHole.
- Trace export now generates width Circle shapes as Aurora/AAF objects and converts AEDB center-line arc markers into `Larc` geometry.
- Pin-pad export now emits pad copper shape placement separately from net-pin binding, matching the object structure used by the AEDB-to-AAF reference flow.
- `design.part` now emits footprint pad templates, pad geometry, and footprint pin placement to describe the part, footprint, pad, and pin relationship.
- The AEDB adapter now stores polygon `is_void`, `void_ids`, and `voids` in `SemanticPrimitive.geometry` so polygon cutout relationships can be emitted and traced.
- `design.part` now emits part and footprint entries plus deduplicated part pin lists.
- The Semantic JSON schema version remains `0.4.0`.

## 0.4.0

- Added `SemanticShape` for AuroraDB shape semantics such as `Circle`, `Rectangle`, `RoundedRectangle`, and `Polygon`.
- Added `SemanticViaTemplate` and `SemanticViaTemplateLayer` for AuroraDB `ViaList` barrel, pad, and antipad shape references.
- Added `name` and `template_id` to `SemanticVia` so AEDB padstack instances can connect to semantic via templates.
- The AEDB adapter now converts drill-hole, pad, antipad, and thermal-pad geometry from padstack definitions into semantic shapes and via templates.
- Aurora/AAF export now emits `layout add -g`, `layout add -via`, and net via placement commands.
- Added AEDB-to-Semantic conversion documentation.
- Updated the Semantic JSON schema version to `0.4.0`.

## 0.3.0

- Added `SemanticMaterial` for preserving material conductivity, permittivity, and dielectric loss tangent.
- Added `material_id`, `fill_material`, and `fill_material_id` to `SemanticLayer` so layers can reference the unified material table.
- The AEDB adapter now converts `materials` and dielectric stackup layers into the unified semantic model.
- Added `semantic to-aaf` and updated `semantic to-auroradb` to emit an Aurora/AAF conversion package: `design.layout`, `design.part`, `stackup.dat`, and `stackup.json`.
- `to-auroradb` also compiles an AuroraDB subdirectory by default; dielectric layers are written to stackup files, not emitted as AuroraDB `MetalLayer` blocks.
- Updated the Semantic JSON schema version to `0.3.0`.

## 0.2.0

- Added `SemanticFootprint` and `SemanticPad` for footprint, pad, component, pin, and net relationships.
- The AEDB adapter now derives footprints, pads, and pin-pad bindings from component part and pin/padstack fields.
- The AuroraDB adapter now derives footprints, pads, and pin-pad bindings from parts footprint symbols, part pin maps, and layout net pins.
- The ODB++ adapter now derives footprint relationships from component package fields.
- Added component-footprint, component-pad, footprint-pad, pin-pad, and pad-net connectivity edges.
- Added connectivity consistency diagnostics for references that point to missing semantic objects.

## 0.1.0

- Added the `SemanticBoard` semantic model covering layers, nets, components, pins, vias, primitives, connectivity, and diagnostics.
- Added adapters from AEDB, AuroraDB, and ODB++ into the semantic model.
- Added basic connectivity edge generation.
- Added the `aurora-translator semantic from-json` and `aurora-translator semantic schema` CLI commands.
- Added semantic JSON schema documentation.
