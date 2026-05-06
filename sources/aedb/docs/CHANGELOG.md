<a id="top"></a>
# AEDB 解析器变更记录 / AEDB Parser Changelog

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

在 `0.3.0` 之前，项目整体版本和 AEDB 解析器版本还没有拆分。下面较早的记录从项目级变更记录中迁移而来，因为它们主要描述 AEDB 解析行为、性能、结构或打包调整。

## DEF binary 0.13.0

- Rust AEDB `.def` parser crate 更新到 `0.13.0`，独立 `AEDBDefBinaryLayout` schema 更新到 `0.13.0`；默认 PyEDB AEDB parser 仍保持 `0.4.56`。
- `domain.padstacks[]` 现在保留 text padstack `hle(shp=..., Szs(...), X/Y/R)` 钻孔字段；`domain.padstacks[].layer_pads[]` 现在同时保留 `ant(...)` 和 `thm(...)` 的 shape、尺寸、offset 与 rotation，用于无 ANF 转换恢复 barrel、antipad clearance 和 padstack shape。
- 使用 `examples/edb_cases/DemoCase_LPDDR4.def` 验证：`C200-109T` 可由 `.def` text padstack 字段恢复为 AuroraDB `RectCutCorner 0 0 150 200 75 N Y Y Y Y` barrel；`VIA8D16` / `VIA10D18` / through-hole padstack 的 clearance holes 现在来自 `.def` padstack source 字段，而不依赖 ANF sidecar。

## DEF binary 0.12.0

- Rust AEDB `.def` parser crate 更新到 `0.12.0`，独立 `AEDBDefBinaryLayout` schema 更新到 `0.12.0`；默认 PyEDB AEDB parser 仍保持 `0.4.56`。
- `SLayer(...)` text record 现在会跨行重组后再解析，stackup layer 可恢复厚度、材料和 fill material；`domain.materials[]` 现在读取 text material block 里的 `conductivity`、`permittivity` 和 `dielectric_loss_tangent`。
- native polygon scanner 现在会识别 `Outline` 层的 board-outline polygon record，Demo case 可直接从 `.def` 恢复标准圆角外框。三套纯 `.def` 样本当前恢复 native polygon/void record：`DemoCase_LPDDR4=840`、`SW_ARM_1029=403`、`Zynq_Phoenix_Pro=744`。

## DEF binary 0.11.0

- Rust AEDB `.def` parser crate 更新到 `0.11.0`，独立 `AEDBDefBinaryLayout` schema 更新到 `0.11.0`；默认 PyEDB AEDB parser 仍保持 `0.4.56`。
- `domain.binary_polygon_records[].net_index/net_name` 现在会从同一大二进制 primitive 流中的 path net context 恢复。`.def` path 记录按 layout net 单调分组，native polygon/void 记录插在对应 net group 内；parser 会把当前 path net owner 写入 polygon，并把 owner 传播给同 parent 的 void polygon。
- 三套纯 `.def` 样本验证 native polygon owner：`DemoCase_LPDDR4` 的 `537` 条 polygon/void、`SW_ARM_1029` 的 `345` 条、`Zynq_Phoenix_Pro` 的 `384` 条均恢复到 net 0，分别为 `GND` / `GND_POWER` / `GND`。

## DEF binary 0.10.0

- Rust AEDB `.def` parser crate 更新到 `0.10.0`，独立 `AEDBDefBinaryLayout` schema 更新到 `0.10.0`；默认 PyEDB AEDB parser 仍保持 `0.4.56`。
- 新增 `domain.padstack_instance_definitions[]`，从 text record 前的 7-byte object id 前缀和 `$begin ''` block 里的 `def` / `fl` / `tl` 字段恢复 `raw_definition_index -> padstack_id` 以及真实 top/bottom layer。无 ANF 时 component pad 不再只能靠 raw definition 数字或名称启发式。
- 三套纯 `.def` 样本验证恢复 padstack-instance definition 映射：`DemoCase_LPDDR4=80`、`SW_ARM_1029=112`、`Zynq_Phoenix_Pro=52`。SW 样本中 `1906 -> PAD_SMD-0402`、`120 -> SMD_18` 等映射可直接驱动 AuroraDB `PadTemplate` 的真实 rectangle/circle/oval/square shape。

## DEF binary 0.9.0

- Rust AEDB `.def` parser crate 更新到 `0.9.0`，独立 `AEDBDefBinaryLayout` schema 更新到 `0.9.0`；默认 PyEDB AEDB parser 仍保持 `0.4.56`。
- `binary_padstack_instance_records[]` 新增 `drill_diameter`，从 padstack instance tail 的 double 字段恢复 drill 直径。Demo `via_3781` 解为 `0.0002032 m`（8 mil），`via_4442` 解为 `0.000254 m`（10 mil）；component pin pad 的该字段保持为空。
- `padstacks[].layer_pads[]` 现在保留 text padstack `pad(shp=..., Szs(...), X=..., Y=..., R=...)` 的尺寸和变换字段；无 ANF 转换会优先用这些源字段生成 circle/rectangle/obround pad shape，再退回名称启发式。
- 在删除所有 ANF sidecar 后，三套同版本 `.def` 样本仍可通过 `convert --from aedb --aedb-backend def-binary --to auroradb` 端到端输出 AuroraDB，包含 `layout.db`、`parts.db`、`stackup.dat`、`stackup.json` 和 `layers/*.lyr`。native polygon/void 点列会写出为 layer `Polygon` / `PolygonHole` / `Holes`，board outline 回退为 native 大平面 bbox 加 20 mil clearance。

## DEF binary 0.8.0

- Rust AEDB `.def` parser crate 更新到 `0.8.0`，独立 `AEDBDefBinaryLayout` schema 更新到 `0.8.0`；默认 PyEDB AEDB parser 仍保持 `0.4.56`。
- `AEDBDefBinaryDomain` 新增 `binary_polygon_records`，从原生 `.def` 二进制 polygon preamble 和 raw-point stream 恢复 geometry id、parent geometry id、outer/void 标志、layer id/name、点列和 arc-height marker。`net_index` / `net_name` 先保留为空，后续继续反解 owner 关系。
- 三套同 AEDT/EDB 版本样本验证：`DemoCase_LPDDR4` 恢复 `537` 条 polygon record（outer `23`、void `514`），`SW_ARM_1029` 恢复 `345` 条（outer `128`、void `217`），`Zynq_Phoenix_Pro` 恢复 `384` 条（outer `50`、void `334`）。Zynq 样本覆盖奇数偏移记录和大于 `255` 的 parent polygon id 编码。

## DEF binary 0.7.0

- Rust AEDB `.def` parser crate 更新到 `0.7.0`，独立 `AEDBDefBinaryLayout` schema 更新到 `0.7.0`；默认 PyEDB AEDB parser 仍保持 `0.4.56`。
- `AEDBDefBinaryDomain` 新增 `binary_padstack_instance_records`，从 component/pad 二进制记录恢复 EDB `PadstackInstance` 的全局偏移、geometry id、实例名、名称分类、net index/name、米单位坐标、弧度旋转、raw owner/definition 引用和二级 name/id。
- Demo case 当前恢复 `2843` 条 padstack instance，按 geometry id 和坐标与 ANF `via(...)` 全量一致：`1714` 条 component pin pad、`1117` 条 `via_*`、`12` 条 unnamed/mechanical 记录；其中 `1726` 条包含二级 pin/name 字段。
- 同版本新增样本 `SW_ARM_1029` 和 `Zynq_Phoenix_Pro` 验证通过：path 分别为 `2833` / `2208` 条，padstack instance 分别为 `3531` / `2709` 条，均按 ANF geometry id、layer/坐标、width/rotation 和 arc-height 全量匹配。`SW_ARM_1029` 暴露较大板面坐标，padstack 坐标 guard 改为与 path decoder 一致的 `±10000 mil` 范围。
- `pyedb-core` API 源码确认这些记录对应 EDB `PadstackInstance` 语义：位置/旋转、top/bottom layer range、padstack definition、net、component 和 layout-pin 状态属于同一对象族；本次先落地已验证的 on-disk 字段，padstack definition 和 layer range owner 仍待继续反解。
- Python 端新增 `AEDBDefBinaryLayout -> SemanticBoard` adapter，`convert --from aedb --aedb-backend def-binary --to auroradb` 不再停在 source JSON，可直接写出 AuroraDB `layout.db`、`parts.db`、`stackup.dat/json` 和 layer 文件。
- 当 `.def` 同目录存在 ANF sidecar 时，adapter 会用 ANF `via(...)` 与 `Padstacks` 块补齐 raw padstack definition 的真实名称、层跨度和基础 circle/rectangle/obround/polygon pad shape，并用 `PolygonWithVoids` / `Graphics(... Polygon(...))` 补齐 polygon 与 hole 导出。纯 `.def` 二进制里已定位到 polygon 点列和 `f64::MAX` arc-height marker 结构，但 layer/net/void grouping 的 native 解码仍待完成。

## DEF binary 0.6.0

- Rust AEDB `.def` parser crate 更新到 `0.6.0`，独立 `AEDBDefBinaryLayout` schema 更新到 `0.6.0`；默认 PyEDB AEDB parser 仍保持 `0.4.56`。
- `AEDBDefBinaryDomain` 新增 `layout_nets`，从 `.def` 大二进制 record 开头的 net table 恢复 net index/name；Demo case 当前恢复 `335` 个 layout net。
- `binary_path_records` 新增 `net_index`、`net_name`、`layer_id` 和 `layer_name`。Demo case 的 1965 条 path 均可由二进制 preamble 自身解出 net/layer，并与 ANF `LayoutNet` / `Graphics('<layer>', Path(...))` 上下文一致。
- via 研究更新：当前 tail-pattern 解析出的 1117 条记录按坐标匹配到 ANF 的真实通孔子集，主要为 TOP/BOTTOM `VIA8D16` / `VIA10D18` 类实例；ANF 中大量 TOP-TOP / BOTTOM-BOTTOM `via(...)` 更接近 component pad 或单层 padstack instance，位于另一类 component/pad 二进制记录中。

## DEF binary 0.5.0

- Rust AEDB `.def` parser crate 更新到 `0.5.0`，独立 `AEDBDefBinaryLayout` schema 更新到 `0.5.0`；默认 PyEDB AEDB parser 仍保持 `0.4.56`。
- `AEDBDefBinaryDomain` 新增 `binary_path_records`，保存二进制 path record 的全局偏移、可解码几何 ID、宽度、点列、arc-height marker，以及 Line/Larc segment 计数。
- 使用 `examples/edb_cases/DemoCase_LPDDR4.def` 对照 `examples/edb_cases/DemoCase_LPDDR4.anf` 验证：1965 条 `.def` binary path record 与 ANF `Graphics(... Path(...))` 记录按顺序、宽度和米单位坐标一致；`.def` 文件结构是 text DSL record 与 binary record 交错的 AEDB 存储流，不是 ANF 文本的直接二进制封装。
- 已知限制：via 目前只覆盖可由 `via_<id>` 字符串尾部定位的 1117 条记录，尚未覆盖 Demo case 中 ANF 的全部 2843 条 via；polygon/void payload 和 path 的精确 net/layer owner 表仍未解码。

## 0.4.56

- 移除 AEDB path / polygon source model 上面向 AuroraDB 的 Pydantic `PrivateAttr` 运行时 `NetGeom` 缓存，AEDB 解析层不再生成目标格式文本行。
- `auroradb-minimal` profile 改为保留 path `center_line`、polygon `raw_points` 和 void raw geometry；direct AuroraDB exporter 从这些显式几何字段生成输出。
- polygon arc 构建热点只负责生成通用 `ArcModel`，不再混合 `Pnt` / `Parc` 文本生成；primitive timing 日志中的展示字段同步去掉 cache 命名。
- AEDB JSON schema 保持 `0.5.0`；字段结构不变，但 minimal profile 的 source model 内容会包含此前只存在于私有缓存中的可序列化几何。

## 0.4.55

- Padstack definition 解析新增 polygonal pad 支持：当 regular / anti / thermal pad 的普通参数为 `NoGeometry` 但 AEDB 底层 `GetPolygonalPadParameters()` 返回 polygon 时，会保存 polygon 顶点。
- `PadPropertyModel` 新增 `raw_points`，用于保存 polygonal pad 的原始顶点；AEDB JSON schema 更新为 `0.5.0`。
- AEDB -> AuroraDB 路径会通过 Semantic polygon shape 补齐此前为空的 `FootPrintSymbol` pad geometry。
- 使用私有 component-gap AEDB 样本验证：source component count 与 AuroraDB component placement count 均为 `1642`，空 footprint 影响的 component 从 `720` 降为 `0`。

## 0.4.54

- 新增 AEDB `auroradb-minimal` 解析 profile，用于 AEDB -> AuroraDB direct conversion 且不输出中间 JSON 的场景。
- minimal profile 仍读取 path / polygon / void 的底层几何并生成 AuroraDB 运行时私有缓存，但不把 path `center_line` / length / area、polygon `raw_points` / arcs / void model 保存进 AEDB source model。
- `auto` 模式下，只有 `convert --from aedb --to auroradb` 且没有 `--source-output` / `--semantic-output` 时才启用 minimal；显式 source JSON 或 semantic JSON 输出继续使用完整 `full` profile。
- 私有 Zynq AEDB 样本验证同版本 full/minimal AuroraDB 输出 `14` 个文件 hash 完全一致；私有 Rainbow AEDB 样本验证同版本 full/minimal 输出 `40` 个文件 hash 完全一致，`Parse AEDB layout` 从 `74.937s` 降至 `40.576s`。
- AEDB JSON schema 保持 `0.4.0`；显式 AEDB JSON 字段结构不变。AuroraDB 输出预期不变，性能变化集中在 path / polygon primitive 解析阶段。

## 0.4.53

- zone primitive 获取改为合并 `active_layout.Primitives` 的一次性分类结果和快速 `GetFixedZonePrimitive()` 结果，避免常规解析调用 `active_layout.GetZonePrimitives()`。
- `layout_paths`、`layout_polygons`、`zone_primitives` 现在共享同一次 primitive 分类结果，减少重复 `GetPrimitiveType()` 调用，并新增收集/分类计时日志。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除 `metadata.project_version` / `metadata.parser_version` 外，payload 预期与 `0.4.52` 一致。

## 0.4.52

- polygon arc/cache 快速路径继续减少 segment 边的固定开销：segment `ArcModel` 直接在 `_arc_models_and_auroradb_lines_from_raw_points()` 热点循环中构造，避免额外函数调用和参数传递。
- AuroraDB 坐标有效性判断改为边界判断快速路径，保持 NaN/Inf 自动被排除，同时减少每个点上的 `math.isfinite()` 调用。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除 `metadata.project_version` / `metadata.parser_version` 外，payload 预期与 `0.4.51` 一致。

## 0.4.51

- polygon arc/cache 构建热点改为 raw point 快速路径，在 `_arc_models_and_auroradb_lines_from_raw_points()` 中内联坐标缩放、`Pnt` / `Parc` 行生成和 segment `ArcModel` 构造。
- 该改动只减少 Python 函数调用开销，不改变 polygon / void 的 `raw_points`、arcs、bbox、area 或运行时 AuroraDB `NetGeom` 缓存内容。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除 `metadata.project_version` / `metadata.parser_version` 外，payload 预期与 `0.4.50` 一致。

## 0.4.50

- primitive 解析阶段新增低噪声内部计时日志，按 path / polygon 汇总批量 .NET snapshot、模型构建、arc/cache 构建和 fallback 次数。
- 该计时器不启用旧的逐字段 profile，避免为常规解析引入大量额外 `perf_counter()` 调用。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除 `metadata.project_version` / `metadata.parser_version` 外，payload 预期与 `0.4.49` 一致。

## 0.4.49

- path / polygon primitive 解析新增分块批量 .NET snapshot，减少 `GetCenterLine()`、`GetWidth()`、`GetEndCapStyle()`、基础字段、polygon with voids geometry 和 flags 的逐对象 Python/.NET 往返。
- path 端帽仍保留 enum 名称与数值，保证 length / area 的归一化逻辑和 JSON 输出保持等价。
- polygon / void geometry 仍输出完整 `raw_points`、arcs、bbox、area 和 void 结构；批量 helper 只改变读取方式，不减少布局内容。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除 `metadata.project_version` / `metadata.parser_version` 外，payload 预期与 `0.4.48` 一致。

## 0.4.48

- polygon / void 在从 `raw_points` 构造 arcs 时同步生成运行时私有 AuroraDB `NetGeom` item 缓存，避免为输出缓存再次遍历已构造的 arcs。
- 该缓存仍为 Pydantic `PrivateAttr`，只服务 AEDB -> SemanticBoard -> AuroraDB 的运行时导出链路，不进入 AEDB JSON。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除 `metadata.project_version` / `metadata.parser_version` 外，payload 预期与 `0.4.47` 一致。

## 0.4.47

- AEDB path / polygon source model 现在携带运行时私有 AuroraDB trace 与 polygon `NetGeom` 缓存，缓存由 extractor 在已有 `center_line`、arc 和 void 数据上生成。
- 这些缓存是 Pydantic `PrivateAttr`，不会进入 AEDB JSON，也不会改变 AEDB JSON schema。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除 `metadata.project_version` / `metadata.parser_version` 外，payload 预期与 `0.4.46` 一致。

## 0.4.46

- heartbeat 缩进进度块会在阶段完成日志前完全输出，避免 `completed` 行插入到多行 progress 块中间。
- 该改动只修正日志输出顺序，不改变解析内容。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.45` 一致。

## 0.4.45

- 普通解析日志移除详细 profile 明细，只输出已解析对象类型及数量摘要，例如 padstack records、padstack definitions、paths、polygons 和 zone primitives。
- 长耗时阶段的 heartbeat 与 progress 日志改为缩进字段块，保留进度、耗时、速率和 RSS 信息，但减少单行字段堆叠。
- 常规 AEDB 解析路径不再为这些日志收集详细 profile 明细，减少日志观测带来的额外开销。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.44` 一致。

## 0.4.44

- padstack record profile 现在在 `Build padstack instance records` 阶段完成后输出，避免 heartbeat 插入到缩进字段块中。
- 该改动只调整日志顺序，不改变解析内容。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.43` 一致。

## 0.4.43

- 当 padstack batch snapshot 统计与总 snapshot 统计完全一致时，不再重复输出 `Batch snapshot totals` 区块。
- 该改动只进一步减少日志重复，不改变解析内容。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.42` 一致。

## 0.4.42

- 解析日志中的 profile 统计改为分组缩进排版：父级标题只输出一次，计数与耗时字段在下方缩进显示。
- 覆盖 padstack record、padstack definition、path、polygon、path area fallback 和 primitive geometry 统计日志。
- 该改动只调整日志可读性，不改变解析内容。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.41` 一致。

## 0.4.41

- 收紧 Rainbow 长阶段日志：关闭 `parse AEDB layout` 和 `serialize layout primitives` 这类父阶段的重复 heartbeat，让长阶段主要由具体子阶段输出进度。
- primitive 进度日志增加最小输出间隔，避免刚跨百分比阈值时连续输出过密，同时保留处理数量、百分比、速率和 RSS。
- 该改动只调整日志可读性，不改变解析内容。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.40` 一致。

## 0.4.40

- 长时间运行的 AEDB 解析阶段新增 heartbeat 日志，默认每 10 秒输出阶段仍在运行、已运行秒数和当前进程 RSS。
- path、polygon、zone primitive 序列化新增进度日志，包含 `processed/total`、百分比、速率和 RSS。
- 该改动只调整日志可观测性，便于确认大 case 仍在推进，不改变解析内容。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.39` 一致。

## 0.4.39

- 整理 AEDB parser log 和 analysis log 排版，降低配置、解析阶段、输出结果和性能分析混在一起的阅读成本。
- 普通 parser log 新增分区：`Input configuration`、`AEDB parsing`、`Analysis output`、`Run summary`。
- analysis log 新增顶层阶段汇总，并将详细阶段树改为按开始顺序输出，父阶段显示在子阶段之前。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.38` 一致。

## 0.4.38

- 新增 AEDB 解析分析日志：CLI 每次成功解析后会保存独立的 `*_analysis.log`，汇总版本、layout 计数、各阶段耗时和进程 working set 内存采样。
- 新增 `core.metrics.RuntimeMetricsRecorder`，复用现有 `log_timing` 自动采集阶段耗时，并记录阶段开始/结束时的内存占用变化。
- 新增 `--analysis-log-file` 参数；未指定时默认写到 JSON 输出文件同目录。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.37` 一致。

## 0.4.37

- 新增 `.NET PadstackInstanceExtractor.GetSnapshots` 批量 helper，一次读取全部 padstack instance 的 id、name、net、component、placement layer、position/rotation、layer range 和 padstack definition。
- `ExtractionContext.padstack_instance_records` 默认优先使用批量 snapshot 构建 records，helper 不可用、调用失败或数量不匹配时自动回退到上一版逐个 snapshot/PyEDB fallback。
- 新增批量 snapshot 命中、回退和耗时日志，用于确认优化路径是否生效。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.36` 一致。

## 0.4.36

- 新增 `.NET PadstackDefinitionSnapshot` helper，一次读取 padstack definition 的基础字段、hole/via 信息和 regular/anti/thermal pad property。
- `extract_padstack_definition` 默认优先使用 snapshot 路径，helper 不可用或调用失败时自动回退到原 PyEDB wrapper 属性读取。
- 保留上一版 profiling，并新增 snapshot 命中、回退和耗时统计。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.35` 一致。

## 0.4.35

- 为 padstack definition 序列化新增聚合 profiling，拆分 basic/hole/via 字段读取、layer map lookup、pad/antipad/thermalpad map 构建、PadPropertyModel 和 PadstackDefinitionModel 验证耗时。
- profiling 只输出汇总日志，不新增 JSON 字段，也不改变解析内容。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.34` 一致。

## 0.4.34

- 优化 polygon/void arc 构建中的 `ArcModel` 快速构造路径，减少关键字参数绑定和直线 segment arc 的额外函数调用。
- 继续保留 `ArcModel` 类型、字段顺序和原有几何计算公式，避免影响 AEDB JSON 和 semantic 转换代码。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.33` 一致。

## 0.4.33

- 为 path 面积计算增加更细的 profiling：记录解析公式命中、arc center line、多段 center line、unsupported end cap、缺失宽度等决策原因。
- 对需要回退 AEDB `GetPolygonData()` 的 path，新增 reason、corner style、end cap style、center-line 点数 bucket 和按 reason 汇总的 `GetPolygonData()` 耗时日志。
- profiling 只输出汇总日志，不新增 JSON 字段，也不改变解析内容。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.32` 一致。

## 0.4.32

- 新增 `.NET PrimitiveWithVoidsGeometrySnapshot` 批量路径，一次读取 polygon 主体和全部 void 的 id、raw points、bbox 与 area。
- polygon/void 的 arc 构建仍保留在 Python 侧，避免修改几何公式和序列化结构。
- polygon profiling 日志新增 batch snapshot 命中、fallback、void 数量和耗时统计，用于对比批量 snapshot 与旧逐对象读取路径。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.31` 一致。

## 0.4.31

- 对无 arc、两点直线 path 使用解析公式计算面积，避免为这类 path 调用 AEDB `GetPolygonData()`。
- 复杂 path 仍使用 AEDB 原始 `GetPolygonData().Area()`，保证拐角、arc 和复杂端帽路径继续由底层几何计算。
- path profiling 日志新增 `analytic_area_paths` 和 `polygon_area_paths`，用于统计解析公式路径与 AEDB polygon area fallback 路径。
- JSON 输出结构保持 `0.4.0`；字段结构和数量统计不变。
- JSON 内容变化：直线 path 的 `area` 可能存在浮点尾数级差异，布局点、线宽、长度、bbox 和数量统计不变。

## 0.4.30

- 新增运行时编译和加载的 `.NET PadstackInstanceSnapshot` helper，一次返回 padstack instance 的 id、name、net、component、placement layer、position、layer range、definition 和 pin 标记。
- padstack instance record 构建优先使用 snapshot 路径，减少每个 instance 的 Python/.NET 往返次数；不可用时自动回退到原逐字段读取路径。
- 保留 padstack record profiling 汇总日志，并新增 snapshot 命中与 fallback 统计。
- JSON 输出结构保持 `0.4.0`；字段结构和数量统计不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.29` 一致。

## 0.4.29

- 为 padstack instance record 构建新增字段级 profiling 日志，拆分 name、net、component、placement layer、position、layer range、definition 和 record 构建耗时。
- profiling 只输出汇总日志，不新增 JSON 字段，也不改变解析内容。
- JSON 输出结构保持 `0.4.0`；字段结构和数量统计不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.28` 一致。

## 0.4.28

- polygon 和 void 的 arc 构建改用 AEDB 内部 fast ArcModel 构造器，跳过重复的 Pydantic `model_construct()` 字段处理。
- fast 构造器只用于解析器自己计算出的完整 arc 字段，序列化结果与标准 `ArcModel` 保持一致。
- JSON 输出结构保持 `0.4.0`；字段结构和数量统计不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.27` 一致。

## 0.4.27

- path primitive 的 `bbox` 改为由 `GetCenterLine().GetBBox()` 加上线宽扩展推导，避免为 bbox 再调用 path polygon data 的 `GetBBox()`。
- path primitive 的 `area` 仍使用 AEDB 原始 `GetPolygonData().Area()`，避免圆角、转角和端帽带来的浮点差异。
- path profiling 日志新增 `center_line_bbox`，用于观察 bbox 推导耗时；原 `bbox` 字段继续记录 fallback 或非推导路径耗时。
- JSON 输出结构保持 `0.4.0`；字段结构和数量统计不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.26` 一致。

## 0.4.26

- 为 path primitive 序列化新增聚合 profiling 日志，拆分统计 center-line 读取、length 计算、base metadata、字段归一化和模型构建耗时。
- profiling 只输出汇总日志，不新增 JSON 字段，也不改变解析内容。
- JSON 输出结构保持 `0.4.0`；字段结构和数量统计不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.25` 一致。

## 0.4.25

- polygon 和 void 的几何读取新增 `.NET GeometrySnapshot` 批量路径，一次返回 `raw_points`、`bbox` 和 `area`，减少 Python/.NET 往返调用。
- polygon profiling 日志新增 `geometry_snapshot` 汇总耗时；原 `read_points`、`bbox`、`area` 字段继续用于 fallback 路径和对照分析。
- arc 构建逻辑保持 Python 侧原公式，避免引入浮点末位差异。
- JSON 输出结构保持 `0.4.0`；字段结构和数量统计不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.24` 一致。

## 0.4.24

- 新增运行时编译和加载的 `.NET` polygon point extractor，把 `PolygonData.GetPoint()`、`PointData.X/Y.ToDouble()` 的逐点读取移到 .NET 侧批量执行，并以 `double[]` 返回给 Python。
- polygon、void 和 path center-line 读取优先使用批量 helper；若 C# 编译、加载或调用失败，会自动回退到原 Python `PolygonData.Points` 路径。
- JSON 输出结构保持 `0.4.0`；字段结构和数量统计不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.23` 一致。

## 0.4.23

- polygon/void arc 构建从“先生成 `vertices` 与 `edge_heights` 中间列表再二次遍历”改为基于已读取 raw points 的单遍 ArcModel 构建。
- 保留 `.NET PolygonData.Points` 先物化为 Python list 的稳定读取方式，避免重复 `0.4.20` 中直迭代 `.NET Points` 变慢的问题。
- JSON 输出结构保持 `0.4.0`；字段结构和数量统计不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.22` 一致。

## 0.4.22

- 为 polygon primitive 序列化增加聚合 profiling 日志，拆分统计 polygon/void 的 `.NET` 数据读取、raw points、arc 构建、area、bbox、metadata 和模型构建耗时。
- profiling 只输出汇总日志，不新增 JSON 字段，也不改变解析内容。
- JSON 输出结构保持 `0.4.0`；字段结构和数量统计不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.4.21` 一致。

## 0.4.21

- 撤回 `0.4.20` 中 polygon raw points 直迭代和单遍 arc 构建实验。
- Rainbow training case 实测 `0.4.20` 的 polygon 阶段更慢，因此当前实现恢复到 `.NET Points` 先转列表、再按 `vertices/edge_heights` 构建 arc 的稳定路径。
- JSON 输出结构保持 `0.4.0`；字段结构和数量统计不变。
- JSON 内容变化：除版本 metadata 外，预期与 `0.4.20` 和 `0.4.19` 内容一致。

## 0.4.20

- polygon 和 void 的 raw points 读取不再先创建临时 `.NET list`，而是直接迭代 `PolygonData.Points`。
- polygon/void arc 模型现在从 raw points 单次流式构建，避免额外生成 `vertices` 和 `edge_heights` 中间列表后再二次遍历。
- JSON 输出结构保持 `0.4.0`；字段结构和数量统计不变。
- JSON 内容变化：除版本 metadata 外，polygon、void 和 arc 内容预期不变。

## 0.4.19

- path primitive 的 `length` 默认从已读取的 center-line raw points 和 arc-height marker 直接计算，避免为每条 path 再调用 `.NET PolygonData.GetArcData()`。
- `.NET GetArcData()` 保留为 raw center-line points 不可用时的回退路径。
- JSON 输出结构保持 `0.4.0`；字段结构和数量统计不变。
- JSON 内容变化：除版本 metadata 外，path `length` 可能只出现浮点尾数级差异。

## 0.4.18

- 默认使用 component pin 绝对坐标的 bbox center 计算 `component.center`，避免为 component center 调用 AEDB `.NET LayoutObjInstance` 接口。
- 新增 CLI 参数 `--component-center-source {pin-bbox,layout-instance}`，可在计算版和底层接口版之间切换。
- JSON 输出结构保持 `0.4.0`；`component.center` 字段保留，但默认来源改为 pin bbox center。
- JSON 内容变化：默认计算版不再输出 layout-instance 的 `component.bounding_box`，该字段为 `null`；数量统计不变。

## 0.4.17

- 将 component center、component bounding box、padstack/pin position 的坐标序列化精度从米单位 6 位小数提升到 9 位小数。
- 该调整用于降低通过 pin bbox center 推导 component 坐标时的舍入误差；rotation 精度保持 6 位小数。
- JSON 输出结构保持 `0.4.0`；字段结构和数量统计不变。
- JSON 内容变化：component 和 pin/padstack 相关坐标会输出更多小数位。

## 0.4.16

- 恢复 component layout geometry 提取，重新构建 `ComponentLayoutRecord` 并序列化 `component.center` 和 `component.bounding_box`。
- 修正 `0.4.15` 中跳过 component geometry 后，Semantic/AuroraDB component placement 只能使用不可靠 `location` 的问题；在当前 Zynq case 中，许多 AEDB component 的 `location` 为 `[0.0, 0.0]`。
- JSON 输出结构保持 `0.4.0`；`metadata.parser_version` 现在输出 `0.4.16`。
- JSON 内容变化：相比 `0.4.15`，AEDB 提供 layout instance geometry 的 component 会重新输出非空 `center` 和 `bounding_box`；字段结构和数量统计不变。

## 0.4.15

- 默认跳过 component layout geometry 提取，避开较慢的 `.NET LayoutInstance.GetLayoutObjInstance(...)` 路径。
- `component.center` 和 `component.bounding_box` 现在输出为 `null`；component 身份、placement layer、rotation、pins、nets 和 padstack 数据保持不变。
- 在 Rainbow training 大 case 上，完整 AEDB layout 解析从约 `241.294s` 降到 `144.984s`。
- JSON 输出结构保持 `0.4.0`；`metadata.parser_version` 现在输出 `0.4.15`。

## 0.4.14

- 新增 `PolygonGeometryRecord` 缓存，用于 polygon void，让 parent polygon 面积计算和 `polygon.voids` 序列化复用同一次底层 `PolygonData` 提取。
- 在 Rainbow training 大 case 上，polygon 序列化从 `83.420s` 降到 `78.274s`，完整 AEDB layout 解析从 `246.006s` 降到 `241.294s`。
- 忽略版本 metadata 后，JSON 输出与 `0.4.13` 文本级完全一致。
- JSON 输出结构保持 `0.4.0`；`metadata.parser_version` 现在输出 `0.4.14`。

## 0.4.13

- polygon 和 polygon void 的 arc 现在从 `PolygonData.Points` 中的 arc-height 标记推导，避免序列化阶段反复调用 `.NET PolygonData.GetArcData()` 以及每条 arc 的 `.NET` 方法。
- 在 Rainbow training 大 case 上，polygon 序列化从 `178.486s` 降到 `83.420s`，完整 AEDB layout 解析从 `342.152s` 降到 `246.006s`。
- JSON 结构和数量统计不变；与 `0.4.12` 相比，仅 arc 浮点尾数存在差异，基准 case 测得最大绝对差为 `2.20e-11`。
- JSON 输出结构保持 `0.4.0`；`metadata.parser_version` 现在输出 `0.4.13`。

## 0.4.12

- raw `.NET` padstack 提取现在会保留旧版无 placement layer 对象的空字符串输出，不再输出 `null`。
- 忽略版本 metadata 和 schema `0.4.0` 新增的 `polygon.voids` 后，JSON payload 与 `0.4.8` 基准一致。
- JSON 输出结构保持 `0.4.0`；`metadata.parser_version` 现在输出 `0.4.12`。

## 0.4.11

- raw `.NET` padstack 提取现在会保留旧版未连接 padstack instance 和 pin 的空字符串 `net_name` 输出。
- `metadata.parser_version` 现在输出 `0.4.11`；`metadata.output_schema_version` 仍输出 `0.4.0`。

## 0.4.10

- padstack instances 现在从 `pedb.active_layout.PadstackInstances` 读取，避免为共享的 `PadstackInstanceRecord` 缓存构建 PyEDB wrapper。
- layout primitives 现在从 `pedb.active_layout.Primitives` 读取，并按 raw primitive type 拆分后序列化。
- JSON 输出结构保持 `0.4.0`；`metadata.parser_version` 现在输出 `0.4.10`。

## 0.4.9

- polygon primitive 现在会输出 void 几何列表 `voids`，包含 void 的 id、raw points、arc 数组、bbox 和 area。
- JSON 输出结构更新为 `0.4.0`。
- `metadata.parser_version` 现在输出 `0.4.9`；`metadata.output_schema_version` 现在输出 `0.4.0`。

## 0.4.8

- 新增纯 Python 的 `ComponentLayoutRecord` 缓存，只保存 component center 和 bounding box，不再长期保存 `.NET LayoutObjInstance` 对象。
- 组件序列化直接使用 `ComponentLayoutRecord`，减少 `.NET` 对象引用生命周期对解析阶段耗时的影响。
- net 统计改为复用已序列化的 primitives 和 `PadstackInstanceRecord`，避免额外扫描一次 raw primitive/void 树。
- JSON 输出结构保持 `0.3.0` 不变。
- `metadata.parser_version` 现在输出 `0.4.8`；`metadata.output_schema_version` 仍为 `0.3.0`。

## 0.4.7

- 将直接组件 `LayoutObjInstance` 映射移动到材料和层提取之前构建，绕开 `extract_layers()` 之后同一 .NET API 调用明显变慢的问题。
- 后续组件序列化继续复用同一份组件实例映射，保持 component center 和 bounding box 输出不变。
- JSON 输出结构保持 `0.3.0` 不变。
- `metadata.parser_version` 现在输出 `0.4.7`；`metadata.output_schema_version` 仍为 `0.3.0`。

## 0.4.6

- 将直接组件 `LayoutObjInstance` 映射提前到 primitive/net 扫描之前构建，避免 AEDB runtime 在后续阶段后对同一 API 出现明显退化。
- 组件序列化阶段直接复用已构建的组件实例映射，不再重复记录一个空耗时阶段。
- JSON 输出结构保持 `0.3.0` 不变。
- `metadata.parser_version` 现在输出 `0.4.6`；`metadata.output_schema_version` 仍为 `0.3.0`。

## 0.4.5

- 组件 center 和 bounding box 所需的 `LayoutObjInstance` 改为按组件直接调用 `layout_instance.GetLayoutObjInstance(component, None)` 构建映射，避免为组件信息触发全量 `GetAllLayoutObjInstances()` 扫描。
- 完整解析默认不再构建共享 layout object index；net 计数改走 primitive/void 原始对象统计和已缓存的 `PadstackInstanceRecord`。
- JSON 输出结构保持 `0.3.0` 不变。
- `metadata.parser_version` 现在输出 `0.4.5`；`metadata.output_schema_version` 仍为 `0.3.0`。

## 0.4.4

- 将 path、polygon 和 primitives 容器的热路径装配改为 `model_construct`，避免已归一化几何点列和 arc 数据重复经过 Pydantic 字段校验。
- 保留 fallback 路径的 `model_validate`，在底层 PyEDB/.NET 对象不满足快速路径时继续使用原有安全归一化行为。
- JSON 输出结构仍保持 `0.3.0` 不变。
- `metadata.parser_version` 现在输出 `0.4.4`；`metadata.output_schema_version` 仍为 `0.3.0`。

## 0.4.3

- 新增 `PadstackInstanceRecord` 缓存层，组件 pin 序列化和 padstack instance 序列化复用同一批已提取字段。
- 在完整 AEDB 解析流程中显式打点 `Build padstack instance records`，便于观察缓存构建成本和后续阶段收益。
- JSON 输出结构仍保持 `0.3.0` 不变。
- `metadata.parser_version` 现在输出 `0.4.3`；`metadata.output_schema_version` 仍为 `0.3.0`。

## 0.4.2

- 确认 component-only index 加 net fallback 更慢后，恢复完整 layout object index 作为默认路径。
- 为 primitive arc 序列化新增底层 .NET 点对象快速转换路径，常见 arc point 不再额外经过通用 normalize 流程。
- JSON 输出结构仍保持 `0.3.0` 不变。
- `metadata.parser_version` 现在输出 `0.4.2`；`metadata.output_schema_version` 仍为 `0.3.0`。

## 0.4.1

- 新增轻量 component instance index，只收集 component layout object instance。
- net 计数继续使用原始 primitive/void 树 fallback，避免为了 net 统计构建完整 net/padstack layout object 聚合。
- 在不回到完整 layout object index 的情况下，恢复 component center 和 bounding box 的快速提取。
- JSON 输出结构仍保持 `0.3.0` 不变。
- `metadata.parser_version` 现在输出 `0.4.1`；`metadata.output_schema_version` 仍为 `0.3.0`。

## 0.4.0

- 完整 AEDB 解析默认不再构建全量 `GetAllLayoutObjInstances()` layout object index。
- net 计数默认改用原始 primitive/void 树和 padstack 聚合 fallback，只有显式需要时才使用 layout object index。
- component 序列化默认使用 wrapper component instance，不再强制触发共享 layout object index。
- JSON 输出结构仍保持 `0.3.0` 不变。
- `metadata.parser_version` 现在输出 `0.4.0`；`metadata.output_schema_version` 仍为 `0.3.0`。

## 0.3.0

- 新增 AEDB 自有的 `AEDB_PARSER_VERSION`，用于记录 AEDB 解析器实现版本。
- `metadata.parser_version` 现在输出 AEDB 解析器版本，不再输出项目整体版本。
- AEDB 解析实现本身相对上一版行为保持不变。
- 新增 AEDB 自有的 `AEDB_JSON_SCHEMA_VERSION`；schema 专属历史维护在 `SCHEMA_CHANGELOG.md`。

## 0.2.21

- 将 `PARSER_VERSION` 调整为整个 Aurora Translator 项目的版本号。
- 将通用输出结构版本常量替换为 `aedb.version.AEDB_SCHEMA_VERSION`，明确只表示 AEDB JSON 输出结构版本。
- 移除公开的 `OUTPUT_SCHEMA_VERSION` 别名，后续其他格式应各自定义自己的 schema 版本。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.21`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.20

- 将解析器版本常量明确收敛到 AEDB 解析作用域，新增 `AEDB_PARSER_VERSION` 和 `AEDB_OUTPUT_SCHEMA_VERSION`。
- 保留 `PARSER_VERSION` 和 `OUTPUT_SCHEMA_VERSION` 作为兼容旧调用方的别名。
- AEDB metadata 和解析日志现在使用 AEDB 作用域的版本常量。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.20`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.19

- 在 polygon primitive 序列化中新增 segment arc 快速路径。
- 对直线段 arc，复用底层 start/end 点和底层 length，同时直接推导 `mid_point`、`center`、`radius` 和 `is_ccw`，减少额外 `.NET` 几何调用。
- 在保持 arc 字段 JSON 输出语义完全一致的前提下，降低逐个 segment arc 的几何访问开销。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.19`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.18

- 新增共享 layout object index，在一次 `GetAllLayoutObjInstances()` 扫描中同时聚合 component instance、按 net 统计的 primitive 数量、padstack 数量和 component 名称集合。
- net 提取现在复用 layout object index 生成 `primitive_count`、`padstack_instance_count` 和 `component_count`，不再额外重复扫描 wrapper 对象。
- component instance 缓存也复用同一个共享索引，避免 net 和 component 阶段重复扫描 layout object。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.18`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.17

- 新增基于 `layout_instance.GetAllLayoutObjInstances()` 的组件 instance 批量缓存，并按底层 component layout object id 建立索引。
- component 的 `center` 和 `bounding_box` 现在优先复用批量缓存的 layout object instance，只有命中失败时才回退到原来的逐个 PyEDB 查询路径。
- 为组件 instance map 的构建新增独立耗时日志，便于在大板子场景下继续定位热点。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.17`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.16

- 优化 polygon arc 的序列化热路径，在底层 `.NET` arc 对象可用时改为更薄的几何直取逻辑，并直接构造 `ArcModel`。
- 保留原有的安全回退校验路径，确保当底层 arc 对象不满足预期接口时仍可兼容现有行为。
- 在不改变 JSON 结构的前提下，减少 polygon primitive 提取阶段逐个 arc 的 wrapper 和校验开销。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.16`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.15

- 修复 primitive 中 path `length` 的快速路径，让路径长度直接基于底层 center line arc 数据计算，不再回退到更慢的 PyEDB wrapper 属性。
- 为 primitive 的 `aedt_name` 新增基于 `GetProductProperty(...)` 的底层快速路径，并保留与现有 AEDT 命名语义一致的确定性回退逻辑。
- 在保持 JSON 结构不变的前提下，减少 primitive 序列化阶段的高层 wrapper 重复访问。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.15`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.14

- 将完整明细模式下的 summary 生成改为复用已提取的 layers、padstacks、components 和 primitives，而不是再次单独调用高成本的 PyEDB summary 路径。
- 基于已序列化的 primitive bounding box 计算 `layout_size`，基于已序列化的 layer elevation 或 thickness 计算 `stackup_thickness`，并保持 summary 数值与现有输出一致。
- 保留 `summary-only` 模式走原始 PyEDB summary 路径，以降低非完整导出场景下的行为风险。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.14`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.13

- 将逐个 net 的高层 wrapper 遍历替换为基于已缓存 primitives 和 padstack instances 的单次聚合路径。
- 通过一次扫描 layout 对象，按 net name 直接计算 `primitive_count` 和 `padstack_instance_count`。
- 基于 padstack instance 关联到的唯一 component 名称计算 `component_count`，在不重复构造 wrapper 的前提下保持与 PyEDB net 语义一致。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.13`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.12

- 将 summary 中的 `get_statistics()` 调用替换为等价的本地快速路径。
- 通过一次 component 类型统计，同时填充 `num_discrete_components`、`num_resistors`、`num_inductors` 和 `num_capacitors`。
- 直接从已缓存的 extraction context 集合计算 `num_layers`、`num_nets`、`num_traces`、`num_polygons` 和 `num_vias`。
- 保持 `layout_size` 和 `stackup_thickness` 的输出语义与原有 PyEDB summary 字段一致。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.12`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.11

- 为 component 元数据采集新增快速路径。
- 在可用时直接从底层 PyEDB 对象读取 component 的 `refdes`、`part_name`、`placement_layer`、`location`、`center`、`rotation` 和 `bounding_box`。
- 复用一次 component model 探测，同时填充 `model_type` 和 `value`，避免重复走高层 wrapper。
- 复用已缓存的 signal layer 名称推导 `is_top_mounted`，避免为每个 component 重建一次 stackup signal layer 列表。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.11`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.10

- 为 primitive 几何采集新增快速路径。
- 复用一次底层 polygon data 查询，同时填充 primitive 的 `area`、`bbox`、`raw_points` 和 `arcs`。
- 复用一次底层 center line 查询，同时填充 path 的 `center_line` 和 `length`。
- 在可用时直接从底层 PyEDB 对象读取 primitive 的 `id`、`type`、`layer_name`、`net_name`、`component_name` 和 `is_void`，并保留原有 wrapper 路径作为安全回退。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.10`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.9

- 为 component pin 采集新增快速路径，复用已缓存的 padstack instances。
- 通过按 component 分组的 padstack instances 构建组件的 `pins`、`nets` 和 `numpins`，避免重复扫描 PyEDB component layout objects。
- 为 component pin 分组和 component 模型序列化增加更细粒度的耗时日志。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.9`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.8

- 为 padstack instance 采集新增快速路径。
- 复用一次底层 position/rotation 查询，同时填充 `position` 和 `rotation`。
- 复用一次底层 layer range 查询，同时填充 `start_layer`、`stop_layer` 和 `layer_range_names`。
- 在可用时直接从底层 PyEDB 对象读取 `padstack_definition`，并保留原有 wrapper 路径作为安全回退。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.8`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.7

- 新增 `ExtractionContext`，在一次解析过程中缓存共享的 PyEDB 集合。
- summary 和详细 extractors 复用缓存后的集合，减少重复访问 PyEDB/.NET。
- 为 summary、padstack、primitive 采集增加更细粒度的耗时日志。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.7`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.6

- 在 `aedb/docs/aedb_schema.json` 下新增生成的 AEDB JSON Schema 文档。
- 在 `aedb/docs/aedb_json_schema.md` 中维护 AEDB JSON 字段说明，采用中文在前、英文在后的双语格式。
- 在 `README.md` 中链接 schema 相关文档。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.6`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.5

- 将 PyEDB 数据采集逻辑拆分到 `aedb.extractors` 下的领域模块。
- 让 `aedb.models` 专注于 Pydantic 输出 schema。
- 解析流程现在通过 `aedb.extractors.build_aedb_layout` 构建 `AEDBLayout`。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.5`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.4

- 将 PyEDB 返回值归一化辅助函数从 `aedb.models` 提取到 `aedb.normalizers`。
- 让 AEDB Pydantic 模型定义更专注于 schema 和对象装配。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.4`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.3

- 将旧的 `layout_parser` 兼容包移出当前项目，放到上一层目录 `../layout_parser`。
- 从当前项目中移除旧的 `layout-parser` 命令行入口。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.3`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.2

- 将包内容提升到当前工作区根目录，使根目录本身成为 `aurora_translator` 包目录。
- 移除嵌套的 `aurora_translator` 包目录和旧的 `src` 路径引导逻辑。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.2`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.1

- 将实现迁移到 `src/aurora_translator` 包布局。
- 拆分 AEDB 会话处理、CLI、核心工具和 JSON 序列化模块。
- 新增 `board_model`，作为未来共享板级模型的空占位。
- JSON 输出结构仍保持 `0.2.0` 不变。
- `metadata.parser_version` 现在输出 `0.2.1`；`metadata.output_schema_version` 仍为 `0.2.0`。

## 0.2.0

- 在每份导出的 JSON 中新增 `metadata.parser_version`。
- 在每份导出的 JSON 中新增 `metadata.output_schema_version`。
- 当前 JSON 布局使用顶层 `layers`，替代旧的 `stackup.layers` 包装结构。

## 0.1.0

- 初始 AEDB JSON 导出结构。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

Before `0.3.0`, the project version and AEDB parser version were not split. The older entries below were moved from the project changelog because they describe AEDB parsing behavior, performance, structure, or packaging work.

## DEF binary 0.13.0

- The Rust AEDB `.def` parser crate is now `0.13.0`, and the separate `AEDBDefBinaryLayout` schema is now `0.13.0`; the default PyEDB AEDB parser remains `0.4.56`.
- `domain.padstacks[]` now preserves text-padstack `hle(shp=..., Szs(...), X/Y/R)` drill fields. `domain.padstacks[].layer_pads[]` now also preserves `ant(...)` and `thm(...)` shape, size, offset, and rotation fields so no-ANF conversion can recover barrel, antipad clearance, and padstack shapes.
- Verified with `examples/edb_cases/DemoCase_LPDDR4.def`: `C200-109T` is recovered from `.def` text padstack fields as the AuroraDB `RectCutCorner 0 0 150 200 75 N Y Y Y Y` barrel, and `VIA8D16` / `VIA10D18` / through-hole padstack clearance holes now come from `.def` padstack source fields instead of an ANF sidecar.

## DEF binary 0.12.0

- The Rust AEDB `.def` parser crate is now `0.12.0`, and the separate `AEDBDefBinaryLayout` schema is now `0.12.0`; the default PyEDB AEDB parser remains `0.4.56`.
- `SLayer(...)` text records are now reassembled across lines before parsing, so stackup layers recover thickness, material, and fill material; `domain.materials[]` now reads `conductivity`, `permittivity`, and `dielectric_loss_tangent` from text material blocks.
- The native polygon scanner now recognizes board-outline polygon records on the `Outline` layer, allowing the Demo case to recover the standard rounded outline directly from `.def`. The three no-ANF samples currently recover native polygon/void record counts of `DemoCase_LPDDR4=840`, `SW_ARM_1029=403`, and `Zynq_Phoenix_Pro=744`.

## DEF binary 0.11.0

- The Rust AEDB `.def` parser crate is now `0.11.0`, and the separate `AEDBDefBinaryLayout` schema is now `0.11.0`; the default PyEDB AEDB parser remains `0.4.56`.
- `domain.binary_polygon_records[].net_index/net_name` is now recovered from the path net context in the same large binary primitive stream. `.def` path records are monotonic by layout net, and native polygon/void records are inserted inside the matching net group; the parser writes the current path net owner onto each polygon and propagates it to void polygons with the same parent.
- The three pure `.def` samples validate native polygon ownership: `537` Demo polygons/voids, `345` SW polygons/voids, and `384` Zynq polygons/voids all recover to net 0, respectively `GND` / `GND_POWER` / `GND`.

## DEF binary 0.10.0

- The Rust AEDB `.def` parser crate is now `0.10.0`, and the separate `AEDBDefBinaryLayout` schema is now `0.10.0`; the default PyEDB AEDB parser remains `0.4.56`.
- Added `domain.padstack_instance_definitions[]`, recovering the `raw_definition_index -> padstack_id` mapping and real top/bottom layers from the 7-byte object-id prefix before a text record plus the `def` / `fl` / `tl` fields inside the following `$begin ''` block. Without ANF, component pads no longer rely only on raw definition numbers or name heuristics.
- Validation across the three pure `.def` samples recovers padstack-instance definition mappings: `DemoCase_LPDDR4=80`, `SW_ARM_1029=112`, and `Zynq_Phoenix_Pro=52`. In the SW sample, mappings such as `1906 -> PAD_SMD-0402` and `120 -> SMD_18` directly drive real AuroraDB `PadTemplate` rectangle/circle/oval/square shapes.

## DEF binary 0.9.0

- The Rust AEDB `.def` parser crate is now `0.9.0`, and the separate `AEDBDefBinaryLayout` schema is now `0.9.0`; the default PyEDB AEDB parser remains `0.4.56`.
- `binary_padstack_instance_records[]` adds `drill_diameter`, recovering the drill diameter from a double field in the padstack-instance tail. Demo `via_3781` decodes to `0.0002032 m` (8 mil), and `via_4442` decodes to `0.000254 m` (10 mil); component pin pads keep this field empty.
- `padstacks[].layer_pads[]` now preserves dimensions and transform fields from text padstack `pad(shp=..., Szs(...), X=..., Y=..., R=...)` records. No-ANF conversion prefers these source fields for circle/rectangle/obround pad shapes before falling back to name heuristics.
- After removing all ANF sidecars, the three same-version `.def` samples still convert end to end with `convert --from aedb --aedb-backend def-binary --to auroradb`, producing `layout.db`, `parts.db`, `stackup.dat`, `stackup.json`, and `layers/*.lyr`. Native polygon/void point streams are emitted as layer `Polygon` / `PolygonHole` / `Holes`, and the board outline falls back to a native large-plane bbox expanded by 20 mil.

## DEF binary 0.8.0

- The Rust AEDB `.def` parser crate is now `0.8.0`, and the separate `AEDBDefBinaryLayout` schema is now `0.8.0`; the default PyEDB AEDB parser remains `0.4.56`.
- Added `binary_polygon_records` to `AEDBDefBinaryDomain`, recovering geometry id, parent geometry id, outer/void flag, layer id/name, point lists, and arc-height markers from native `.def` binary polygon preambles and raw-point streams. `net_index` / `net_name` are reserved as empty fields while owner decoding continues.
- Validation across three same-version AEDT/EDB samples: `DemoCase_LPDDR4` recovers `537` polygon records (outer `23`, void `514`), `SW_ARM_1029` recovers `345` records (outer `128`, void `217`), and `Zynq_Phoenix_Pro` recovers `384` records (outer `50`, void `334`). The Zynq sample covers odd-offset records and parent polygon ids greater than `255`.

## DEF binary 0.7.0

- The Rust AEDB `.def` parser crate is now `0.7.0`, and the separate `AEDBDefBinaryLayout` schema is now `0.7.0`; the default PyEDB AEDB parser remains `0.4.56`.
- Added `binary_padstack_instance_records` to `AEDBDefBinaryDomain`, recovering EDB `PadstackInstance` offsets, geometry ids, instance names, name classes, net index/name, meter-unit coordinates, radian rotations, raw owner/definition references, and secondary name/id fields from component/pad binary records.
- The Demo case now recovers all `2843` padstack instances by geometry id and coordinate against ANF `via(...)`: `1714` component pin pads, `1117` `via_*` records, and `12` unnamed/mechanical records; `1726` of them carry secondary pin/name fields.
- Added same-version validation with `SW_ARM_1029` and `Zynq_Phoenix_Pro`: path counts are `2833` / `2208`, padstack instance counts are `3531` / `2709`, and all match ANF geometry ids, layers/coordinates, widths/rotations, and arc-height values. `SW_ARM_1029` exposed a larger board coordinate range, so the padstack coordinate guard now uses the same `±10000 mil` range as the path decoder.
- The `pyedb-core` API source confirms these records align with EDB `PadstackInstance` semantics: position/rotation, top/bottom layer range, padstack definition, net, component, and layout-pin state are part of the same object family. This release emits the verified on-disk fields first; padstack definition and layer-range ownership remain under reverse engineering.
- Added the Python `AEDBDefBinaryLayout -> SemanticBoard` adapter, so `convert --from aedb --aedb-backend def-binary --to auroradb` no longer stops at source JSON and can write AuroraDB `layout.db`, `parts.db`, `stackup.dat/json`, and layer files directly.
- When a sibling ANF sidecar exists, the adapter enriches raw padstack definitions with real names, layer spans, and basic circle/rectangle/obround/polygon pad shapes from ANF `via(...)` and `Padstacks`, and emits polygons and holes from `PolygonWithVoids` / `Graphics(... Polygon(...))`. Native `.def` binary research has located polygon point lists and the `f64::MAX` arc-height marker structure, but layer/net/void grouping still needs native decoding.

## DEF binary 0.6.0

- The Rust AEDB `.def` parser crate is now `0.6.0`, and the separate `AEDBDefBinaryLayout` schema is now `0.6.0`; the default PyEDB AEDB parser remains `0.4.56`.
- Added `layout_nets` to `AEDBDefBinaryDomain`, recovering net index/name pairs from the net table at the start of the large `.def` binary record; the Demo case currently recovers `335` layout nets.
- Added `net_index`, `net_name`, `layer_id`, and `layer_name` to `binary_path_records`. All 1965 Demo case paths can now decode net/layer ownership from the binary preamble itself, matching the ANF `LayoutNet` / `Graphics('<layer>', Path(...))` context.
- Via research update: the 1117 records found by the tail-pattern decoder match real ANF through-via subsets by coordinate, mainly TOP/BOTTOM `VIA8D16` / `VIA10D18` instances; many ANF TOP-TOP / BOTTOM-BOTTOM `via(...)` entries are closer to component pads or single-layer padstack instances stored in another component/pad binary record form.

## DEF binary 0.5.0

- The Rust AEDB `.def` parser crate is now `0.5.0`, and the separate `AEDBDefBinaryLayout` schema is now `0.5.0`; the default PyEDB AEDB parser remains `0.4.56`.
- Added `binary_path_records` to `AEDBDefBinaryDomain`, carrying decoded binary path record offsets, geometry ids where available, widths, point lists, arc-height markers, and Line/Larc segment counts.
- Verified `examples/edb_cases/DemoCase_LPDDR4.def` against `examples/edb_cases/DemoCase_LPDDR4.anf`: all 1965 `.def` binary path records match ANF `Graphics(... Path(...))` records by order, width, and meter-unit coordinates; the `.def` file is an AEDB storage stream interleaving text DSL records and binary records, not a direct binary packing of the ANF text.
- Known limits: via decoding currently covers only the 1117 records locatable from `via_<id>` string tails, not all 2843 ANF vias in the Demo case; polygon/void payloads and exact path net/layer owner tables remain undecoded.

## 0.4.56

- Removed AuroraDB-specific Pydantic `PrivateAttr` runtime `NetGeom` caches from AEDB path / polygon source models; the AEDB extraction layer no longer builds target-format text lines.
- The `auroradb-minimal` profile now preserves path `center_line`, polygon `raw_points`, and void raw geometry; the direct AuroraDB exporter derives output from those explicit geometry fields.
- Polygon arc construction now only builds format-neutral `ArcModel` data instead of mixing in `Pnt` / `Parc` line generation; primitive timing display fields no longer use cache wording.
- AEDB JSON schema remains `0.5.0`; field structure is unchanged, but minimal-profile source model payloads now include serializable geometry that previously only existed in private runtime caches.

## 0.4.55

- Added padstack-definition support for polygonal pads: when regular / anti / thermal pad scalar parameters report `NoGeometry` but the AEDB lower-level `GetPolygonalPadParameters()` returns a polygon, polygon vertices are preserved.
- Added `raw_points` to `PadPropertyModel` for polygonal pad vertices; the AEDB JSON schema is updated to `0.5.0`.
- The AEDB -> AuroraDB path can now fill previously empty `FootPrintSymbol` pad geometry through Semantic polygon shapes.
- Verified with a private component-gap AEDB sample: source component count and AuroraDB component placement count are both `1642`, and components affected by empty footprints dropped from `720` to `0`.

## 0.4.54

- Added the AEDB `auroradb-minimal` parse profile for AEDB -> AuroraDB direct conversion when no intermediate JSON output is requested.
- The minimal profile still reads path / polygon / void bottom-level geometry and builds runtime-private AuroraDB caches, but it does not store path `center_line` / length / area or polygon `raw_points` / arcs / void models in the AEDB source model.
- In `auto` mode, minimal parsing is enabled only for `convert --from aedb --to auroradb` without `--source-output` / `--semantic-output`; explicit source JSON or Semantic JSON output keeps the complete `full` profile.
- A private Zynq AEDB sample verified identical same-version full/minimal AuroraDB hashes across `14` files; a private Rainbow AEDB sample verified identical same-version full/minimal hashes across `40` files, with `Parse AEDB layout` reduced from `74.937s` to `40.576s`.
- AEDB JSON schema remains `0.4.0`; explicit AEDB JSON field structure is unchanged. AuroraDB output is expected to remain unchanged, while performance changes are concentrated in path / polygon primitive parsing.

## 0.4.53

- Zone primitive collection now merges the one-pass `active_layout.Primitives` classification result with the fast `GetFixedZonePrimitive()` result, avoiding the regular use of `active_layout.GetZonePrimitives()`.
- `layout_paths`, `layout_polygons`, and `zone_primitives` now share one primitive classification result, reducing repeated `GetPrimitiveType()` calls and adding collection/classification timing logs.
- AEDB JSON schema remains `0.4.0`; JSON fields are unchanged.
- JSON content changes: except `metadata.project_version` / `metadata.parser_version`, payloads are expected to match `0.4.52`.

## 0.4.52

- The polygon arc/cache fast path further reduces fixed segment-edge overhead: segment `ArcModel` instances are constructed directly inside the `_arc_models_and_auroradb_lines_from_raw_points()` hot loop, avoiding extra function calls and argument passing.
- AuroraDB coordinate validity checks now use a boundary-check fast path, still excluding NaN/Inf while reducing per-point `math.isfinite()` calls.
- AEDB JSON schema remains `0.4.0`; JSON fields are unchanged.
- JSON content changes: except `metadata.project_version` / `metadata.parser_version`, payloads are expected to match `0.4.51`.

## 0.4.51

- Polygon arc/cache construction now uses a raw-point fast path that inlines coordinate scaling, `Pnt` / `Parc` line generation, and segment `ArcModel` construction inside `_arc_models_and_auroradb_lines_from_raw_points()`.
- This only reduces Python function-call overhead; polygon / void `raw_points`, arcs, bbox, area, and runtime AuroraDB `NetGeom` cache content are unchanged.
- AEDB JSON schema remains `0.4.0`; JSON fields are unchanged.
- JSON content changes: except `metadata.project_version` / `metadata.parser_version`, payloads are expected to match `0.4.50`.

## 0.4.50

- Primitive extraction now emits a low-noise internal timing block summarizing path / polygon batch .NET snapshots, model construction, arc/cache construction, and fallback counts.
- This timing path does not enable the older per-field profile, avoiding large numbers of extra `perf_counter()` calls during regular parses.
- AEDB JSON schema remains `0.4.0`; JSON fields are unchanged.
- JSON content changes: except `metadata.project_version` / `metadata.parser_version`, payloads are expected to match `0.4.49`.

## 0.4.49

- Path / polygon primitive extraction now uses chunked .NET batch snapshots, reducing per-object Python/.NET round trips for `GetCenterLine()`, `GetWidth()`, `GetEndCapStyle()`, base fields, polygon-with-void geometry, and flags.
- Path end-cap snapshots keep both enum names and values, preserving equivalent length / area normalization and JSON output.
- Polygon / void geometry still emits complete `raw_points`, arcs, bbox, area, and void structures; the batch helper only changes the read path and does not remove layout content.
- AEDB JSON schema remains `0.4.0`; JSON fields are unchanged.
- JSON content changes: except `metadata.project_version` / `metadata.parser_version`, payloads are expected to match `0.4.48`.

## 0.4.48

- Polygon / void extraction now builds runtime-private AuroraDB `NetGeom` item caches while constructing arcs from `raw_points`, avoiding another pass over already-built arcs just to prepare output caches.
- The cache remains a Pydantic `PrivateAttr` and only serves the AEDB -> SemanticBoard -> AuroraDB runtime export path; it is not emitted into AEDB JSON.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: except `metadata.project_version` / `metadata.parser_version`, payloads are expected to match `0.4.47`.

## 0.4.47

- AEDB path / polygon source models now carry runtime-private AuroraDB trace and polygon `NetGeom` caches generated by the extractor from already available `center_line`, arc, and void data.
- These caches are Pydantic `PrivateAttr` values, so they are not emitted into AEDB JSON and do not change the AEDB JSON schema.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: except `metadata.project_version` / `metadata.parser_version`, payloads are expected to match `0.4.46`.

## 0.4.46

- Heartbeat progress blocks now finish before stage completion logs are emitted, preventing `completed` lines from interrupting multi-line progress blocks.
- This only fixes log output ordering and does not change parsed content.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.45`.

## 0.4.45

- Regular parse logs no longer emit detailed profile breakdowns; they now report only parsed object types and count summaries, such as padstack records, padstack definitions, paths, polygons, and zone primitives.
- Long-running heartbeat and progress logs now use indented field blocks, retaining progress, elapsed time, rate, and RSS while reducing dense one-line field output.
- The normal AEDB parse path no longer collects detailed profile data solely for these logs, reducing observability overhead.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.44`.

## 0.4.44

- Padstack record profile logs now print after `Build padstack instance records` completes, preventing heartbeat messages from interrupting indented field blocks.
- This only changes log ordering and does not change parsed content.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.43`.

## 0.4.43

- When padstack batch snapshot statistics are identical to the total snapshot statistics, the parser no longer repeats a `Batch snapshot totals` block.
- This further reduces repeated log content and does not change parsed content.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.42`.

## 0.4.42

- Profile statistics in parse logs now use grouped indentation: each parent title is printed once and related count/timing fields are shown underneath.
- Applies to padstack record, padstack definition, path, polygon, path area fallback, and primitive geometry statistics.
- This change only improves log readability and does not change parsed content.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.41`.

## 0.4.41

- Tightened Rainbow long-stage logging: disabled duplicate parent heartbeats for `parse AEDB layout` and `serialize layout primitives` so detailed child stages own progress output.
- Primitive progress logs now use a minimum spacing to avoid dense adjacent percent-threshold lines while keeping processed counts, percent, rate, and RSS.
- This change only improves log readability and does not change parsed content.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.40`.

## 0.4.40

- Added heartbeat logs for long-running AEDB parse stages; by default they report that the stage is still running every 10 seconds, including elapsed seconds and current process RSS.
- Path, polygon, and zone primitive serialization now emit progress logs with `processed/total`, percentage, rate, and RSS.
- This only improves log observability for large cases and does not change parsed content.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.39`.

## 0.4.39

- Cleaned up AEDB parser log and analysis log layout to make configuration, parse stages, outputs, and performance analysis easier to read separately.
- The regular parser log now has `Input configuration`, `AEDB parsing`, `Analysis output`, and `Run summary` sections.
- The analysis log now includes a top-level stage summary and prints the detailed stage tree by stage start time so parent stages appear before their child stages.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.38`.

## 0.4.38

- Added an AEDB parse analysis log: after each successful CLI parse, the parser writes a separate `*_analysis.log` summarizing versions, layout counts, stage timings, and process working-set memory samples.
- Added `core.metrics.RuntimeMetricsRecorder`, reusing the existing `log_timing` calls to collect stage durations and sampled start/end memory deltas.
- Added `--analysis-log-file`; when omitted, the log is written next to the JSON output.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.37`.

## 0.4.37

- Added a `.NET PadstackInstanceExtractor.GetSnapshots` batch helper that reads all padstack instance id, name, net, component, placement layer, position/rotation, layer range, and padstack definition fields in one lower-level call.
- `ExtractionContext.padstack_instance_records` now prefers batch snapshot record construction and automatically falls back to the previous per-instance snapshot/PyEDB fallback when the helper is unavailable, fails, or returns an unexpected count.
- Added batch snapshot hit, fallback, and timing counters to confirm whether the optimized path is active.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.36`.

## 0.4.36

- Added a `.NET PadstackDefinitionSnapshot` helper that reads padstack definition base fields, hole/via data, and regular/anti/thermal pad properties in one lower-level pass.
- `extract_padstack_definition` now prefers the snapshot path and automatically falls back to the previous PyEDB wrapper attribute reads when the helper is unavailable or fails.
- Kept the previous profiling and added snapshot hit, fallback, and timing counters.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.35`.

## 0.4.35

- Added aggregate profiling for padstack definition serialization, splitting basic/hole/via field reads, layer-map lookup, pad/antipad/thermalpad map construction, PadPropertyModel validation, and PadstackDefinitionModel validation time.
- Profiling only emits aggregate logs; it adds no JSON fields and does not change parsed content.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.34`.

## 0.4.34

- Optimized the fast `ArcModel` construction path used by polygon/void arc building, reducing keyword-argument binding and extra function calls for straight segment arcs.
- Kept the `ArcModel` runtime type, field order, and existing geometry formulas to avoid impacting AEDB JSON or semantic conversion code.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.33`.

## 0.4.33

- Added finer path-area profiling that records analytic-area hits, arc center lines, multi-segment center lines, unsupported end caps, missing widths, and other decision reasons.
- For paths that fall back to AEDB `GetPolygonData()`, logs now summarize reason, corner style, end-cap style, center-line point-count buckets, and per-reason `GetPolygonData()` time.
- Profiling only emits aggregate logs; it adds no JSON fields and does not change parsed content.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.32`.

## 0.4.32

- Added a `.NET PrimitiveWithVoidsGeometrySnapshot` batch path that reads the polygon body and all void ids, raw points, bboxes, and areas in one call.
- Polygon/void arc construction remains on the Python side to preserve the existing geometry formulas and serialized structure.
- Polygon profiling logs now include batch snapshot hit, fallback, void-count, and timing counters for comparison with the previous per-object reader path.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.31`.

## 0.4.31

- Straight two-point paths without arcs now use an analytic area calculation, avoiding AEDB `GetPolygonData()` calls for those paths.
- Complex paths still use AEDB's original `GetPolygonData().Area()` so corners, arcs, and complex end-cap geometry remain delegated to the lower-level geometry engine.
- Path profiling logs now include `analytic_area_paths` and `polygon_area_paths` to split analytic area handling from AEDB polygon-area fallback.
- AEDB JSON schema remains `0.4.0`; output fields and counts are unchanged.
- JSON content changes: straight-path `area` values may differ only at floating-point tail precision; layout points, widths, lengths, bboxes, and counts are unchanged.

## 0.4.30

- Added a runtime-compiled and loaded `.NET PadstackInstanceSnapshot` helper that returns padstack instance id, name, net, component, placement layer, position, layer range, definition, and pin flag fields in one call.
- Padstack instance record construction now prefers the snapshot path to reduce per-instance Python/.NET round trips, falling back to the previous per-field reader when unavailable.
- Kept aggregate padstack record profiling logs and added snapshot hit/fallback counters.
- AEDB JSON schema remains `0.4.0`; output fields and counts are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.29`.

## 0.4.29

- Added field-level profiling logs for padstack instance record construction, splitting timing for names, nets, components, placement layers, positions, layer ranges, definitions, and record construction.
- Profiling emits aggregate logs only; it does not add JSON fields or change parsed content.
- AEDB JSON schema remains `0.4.0`; output fields and counts are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.28`.

## 0.4.28

- Polygon and void arc construction now uses an AEDB-internal fast ArcModel constructor, skipping repeated Pydantic `model_construct()` field processing.
- The fast constructor is only used for complete arc fields computed by the parser itself, preserving the same serialized output as standard `ArcModel` instances.
- JSON output schema remains `0.4.0`; field structure and counts are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.27`.

## 0.4.27

- Path primitive `bbox` is now derived from `GetCenterLine().GetBBox()` expanded by trace width, avoiding a second bbox read from path polygon data.
- Path primitive `area` still uses AEDB's original `GetPolygonData().Area()` to avoid floating-point differences from rounded caps, corners, and end caps.
- Added `center_line_bbox` to path profiling logs; the existing `bbox` counter remains for fallback or non-derived paths.
- JSON output schema remains `0.4.0`; field structure and counts are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.26`.

## 0.4.26

- Added aggregated profiling logs for path primitive serialization, splitting center-line reads, length calculation, base metadata, field normalization, and model construction timings.
- Profiling only emits summary logs; it adds no JSON fields and does not change parsed content.
- JSON output schema remains `0.4.0`; field structure and counts are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.25`.

## 0.4.25

- Added a `.NET GeometrySnapshot` batch path for polygon and void geometry reads, returning `raw_points`, `bbox`, and `area` together to reduce Python/.NET round trips.
- Added `geometry_snapshot` to the aggregated polygon profiling log; the existing `read_points`, `bbox`, and `area` counters remain for fallback paths and comparison.
- Kept arc construction on the Python side with the existing formulas to avoid introducing last-digit floating-point differences.
- JSON output schema remains `0.4.0`; field structure and counts are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.24`.

## 0.4.24

- Added a runtime-compiled and loaded `.NET` polygon point extractor that moves per-point `PolygonData.GetPoint()` and `PointData.X/Y.ToDouble()` reads into .NET and returns a batched `double[]` to Python.
- Polygon, void, and path center-line reads prefer the batched helper; if C# compilation, loading, or invocation fails, parsing automatically falls back to the previous Python `PolygonData.Points` path.
- JSON output schema remains `0.4.0`; field structure and counts are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.23`.

## 0.4.23

- Polygon/void arc construction now builds ArcModel objects in one pass over the already-read raw points instead of first creating `vertices` and `edge_heights` intermediate lists and traversing them again.
- Kept the stable `.NET PolygonData.Points` materialization into a Python list to avoid repeating the slower direct `.NET Points` iteration observed in `0.4.20`.
- JSON output schema remains `0.4.0`; field structure and counts are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.22`.

## 0.4.22

- Added aggregate profiling logs for polygon primitive serialization, splitting polygon/void `.NET` data reads, raw points, arc construction, area, bbox, metadata, and model-building time.
- Profiling only emits summary logs; it does not add JSON fields or change parsed content.
- JSON output schema remains `0.4.0`; field structure and counts are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.4.21`.

## 0.4.21

- Reverted the `0.4.20` experiment that directly iterated polygon raw points and built arc models in one pass.
- The Rainbow training case showed slower polygon serialization with `0.4.20`, so the current implementation restores the stable path that materializes `.NET Points` as a list and then builds arcs through `vertices/edge_heights`.
- JSON output schema remains `0.4.0`; field structure and counts are unchanged.
- JSON content changes: aside from version metadata, content is expected to match `0.4.20` and `0.4.19`.

## 0.4.20

- Polygon and void raw points now iterate `PolygonData.Points` directly instead of first creating a temporary `.NET list`.
- Polygon/void arc models are now built from raw points in a single streaming pass, avoiding separate `vertices` and `edge_heights` intermediate lists plus a second traversal.
- JSON output schema remains `0.4.0`; field structure and counts are unchanged.
- JSON content changes: aside from version metadata, polygon, void, and arc content is expected to remain unchanged.

## 0.4.19

- Path primitive `length` is now computed from the already-read center-line raw points and arc-height markers by default, avoiding a per-path `.NET PolygonData.GetArcData()` call.
- `.NET GetArcData()` remains as a fallback when raw center-line points are unavailable.
- JSON output schema remains `0.4.0`; field structure and counts are unchanged.
- JSON content changes: aside from version metadata, path `length` may only differ at floating-point tail precision.

## 0.4.18

- Computes `component.center` from the bbox center of each component's absolute pin positions by default, avoiding AEDB `.NET LayoutObjInstance` calls for component centers.
- Added the CLI option `--component-center-source {pin-bbox,layout-instance}` to switch between the computed mode and the bottom-level interface mode.
- JSON output schema remains `0.4.0`; the `component.center` field is retained, but its default source changes to pin bbox center.
- JSON content change: the default computed mode no longer emits layout-instance `component.bounding_box`, so that field is `null`; counts are unchanged.

## 0.4.17

- Increased coordinate serialization precision for component centers, component bounding boxes, and padstack/pin positions from 6 to 9 decimal places in meter units.
- This reduces rounding error when deriving component placement from pin bbox centers; rotation precision remains 6 decimal places.
- JSON output schema remains `0.4.0`; field structure and counts are unchanged.
- JSON content change: component and pin/padstack coordinate values now emit more decimal places.

## 0.4.16

- Restored component layout geometry extraction by building `ComponentLayoutRecord` and serializing `component.center` and `component.bounding_box`.
- Fixed the `0.4.15` downstream placement regression where Semantic/AuroraDB component placement had to use unreliable `location` values; in the current Zynq case, many AEDB component `location` values are `[0.0, 0.0]`.
- JSON output schema remains `0.4.0`; `metadata.parser_version` now reports `0.4.16`.
- JSON content change: compared with `0.4.15`, components with AEDB layout instance geometry emit non-null `center` and `bounding_box` again; field structure and counts are unchanged.

## 0.4.15

- Component layout geometry extraction is skipped by default, avoiding the slow `.NET LayoutInstance.GetLayoutObjInstance(...)` path.
- `component.center` and `component.bounding_box` are now emitted as `null`; component identity, placement layer, rotation, pins, nets, and padstack data are unchanged.
- On the large Rainbow training case, full AEDB layout parsing dropped from about `241.294s` to `144.984s`.
- JSON output schema remains `0.4.0`; `metadata.parser_version` now reports `0.4.15`.

## 0.4.14

- Added a `PolygonGeometryRecord` cache for polygon voids, so parent polygon area calculation and `polygon.voids` serialization reuse the same bottom-level `PolygonData` extraction.
- On the large Rainbow training case, polygon serialization dropped from `83.420s` to `78.274s`, and total AEDB layout parsing dropped from `246.006s` to `241.294s`.
- JSON output is text-identical to `0.4.13` after ignoring version metadata.
- JSON output schema remains `0.4.0`; `metadata.parser_version` now reports `0.4.14`.

## 0.4.13

- Polygon and polygon-void arcs are now derived from `PolygonData.Points` arc-height markers, avoiding repeated `.NET PolygonData.GetArcData()` calls and per-arc `.NET` method calls during serialization.
- On the large Rainbow training case, polygon serialization dropped from `178.486s` to `83.420s`, and total AEDB layout parsing dropped from `342.152s` to `246.006s`.
- JSON structure and counts are unchanged; compared with `0.4.12`, only arc floating-point tail values changed, with a measured maximum absolute difference of `2.20e-11` on the benchmark case.
- JSON output schema remains `0.4.0`; `metadata.parser_version` now reports `0.4.13`.

## 0.4.12

- Raw `.NET` padstack extraction now preserves legacy empty-string `placement_layer` values for instances that do not belong to a placed component.
- The JSON payload is equivalent to `0.4.8` after ignoring version metadata and the schema-`0.4.0` `polygon.voids` addition.
- JSON output schema remains `0.4.0`; `metadata.parser_version` now reports `0.4.12`.

## 0.4.11

- Raw `.NET` padstack extraction now preserves legacy empty-string `net_name` values for unconnected padstack instances and pins.
- `metadata.parser_version` now reports `0.4.11`; `metadata.output_schema_version` still reports `0.4.0`.

## 0.4.10

- Padstack instances are now read from `pedb.active_layout.PadstackInstances`, avoiding PyEDB wrapper construction for the shared `PadstackInstanceRecord` cache.
- Layout primitives are now read from `pedb.active_layout.Primitives` and split by raw primitive type before serialization.
- JSON output schema remains `0.4.0`; `metadata.parser_version` now reports `0.4.10`.

## 0.4.9

- Polygon primitives now emit a `voids` geometry list with each void id, raw points, arcs, bbox, and area.
- JSON output schema is updated to `0.4.0`.
- `metadata.parser_version` now reports `0.4.9`; `metadata.output_schema_version` now reports `0.4.0`.

## 0.4.8

- Added a plain Python `ComponentLayoutRecord` cache that stores only component center and bounding box instead of retaining `.NET LayoutObjInstance` objects.
- Component serialization now reads the `ComponentLayoutRecord` values directly, reducing parser-phase sensitivity to `.NET` object reference lifetimes.
- Net aggregation now reuses serialized primitives and `PadstackInstanceRecord` data, avoiding an extra raw primitive/void tree scan.
- JSON output schema is unchanged from `0.3.0`.
- `metadata.parser_version` now reports `0.4.8`; `metadata.output_schema_version` remains `0.3.0`.

## 0.4.7

- Moved direct component `LayoutObjInstance` map construction before material and layer extraction, avoiding the same .NET API becoming much slower after `extract_layers()`.
- Later component serialization still reuses the same component instance map, preserving component center and bounding-box output.
- JSON output schema is unchanged from `0.3.0`.
- `metadata.parser_version` now reports `0.4.7`; `metadata.output_schema_version` remains `0.3.0`.

## 0.4.6

- Moved direct component `LayoutObjInstance` map construction before primitive/net scans to avoid a large AEDB runtime slowdown on the same API after later layout traversal.
- Component serialization now reuses the prebuilt component instance map instead of logging a second no-op map build step.
- JSON output schema is unchanged from `0.3.0`.
- `metadata.parser_version` now reports `0.4.6`; `metadata.output_schema_version` remains `0.3.0`.

## 0.4.5

- Changed the component center and bounding-box `LayoutObjInstance` path to build the map with direct `layout_instance.GetLayoutObjInstance(component, None)` calls instead of triggering a full `GetAllLayoutObjInstances()` scan.
- Full parsing no longer builds the shared layout object index by default; net counts now use raw primitive/void aggregation plus the cached `PadstackInstanceRecord` data.
- JSON output schema is unchanged from `0.3.0`.
- `metadata.parser_version` now reports `0.4.5`; `metadata.output_schema_version` remains `0.3.0`.

## 0.4.4

- Switched the hot path for path, polygon, and primitives container assembly to `model_construct`, avoiding repeated Pydantic field validation for already-normalized geometry point lists and arc data.
- Kept fallback paths on `model_validate` so unexpected PyEDB/.NET wrapper shapes continue to use the previous safe normalization behavior.
- JSON output schema is unchanged from `0.3.0`.
- `metadata.parser_version` now reports `0.4.4`; `metadata.output_schema_version` remains `0.3.0`.

## 0.4.3

- Added a `PadstackInstanceRecord` cache so component-pin serialization and padstack-instance serialization reuse the same extracted fields.
- Added an explicit `Build padstack instance records` timing step in full AEDB parsing to show cache construction cost and downstream savings.
- JSON output schema is unchanged from `0.3.0`.
- `metadata.parser_version` now reports `0.4.3`; `metadata.output_schema_version` remains `0.3.0`.

## 0.4.2

- Restored the full layout object index as the default path after measuring that the component-only index plus net fallback was slower.
- Added a fast path for raw .NET point conversion in primitive arc serialization, avoiding an extra generic normalization pass for common arc point objects.
- JSON output schema is unchanged from `0.3.0`.
- `metadata.parser_version` now reports `0.4.2`; `metadata.output_schema_version` remains `0.3.0`.

## 0.4.1

- Added a lightweight component instance index that collects only component layout object instances.
- Kept net counting on the raw primitive/void tree fallback so net counts do not require the full net/padstack layout object aggregation.
- Restored fast component center and bounding-box extraction without returning to the full layout object index path.
- JSON output schema is unchanged from `0.3.0`.
- `metadata.parser_version` now reports `0.4.1`; `metadata.output_schema_version` remains `0.3.0`.

## 0.4.0

- Avoided the default full `GetAllLayoutObjInstances()` layout object index during full-detail AEDB parsing.
- Net counts now use the raw primitive/void tree and padstack aggregation fallback unless the layout object index is explicitly requested.
- Component serialization now uses wrapper component instances by default instead of forcing the shared layout object index.
- JSON output schema is unchanged from `0.3.0`.
- `metadata.parser_version` now reports `0.4.0`; `metadata.output_schema_version` remains `0.3.0`.

## 0.3.0

- Added AEDB-owned `AEDB_PARSER_VERSION` for AEDB parser implementation changes.
- `metadata.parser_version` now reports the AEDB parser version instead of the project version.
- Parser implementation is otherwise unchanged from the previous AEDB parser behavior.
- Added AEDB-owned `AEDB_JSON_SCHEMA_VERSION`; schema-specific history is maintained in `SCHEMA_CHANGELOG.md`.

## 0.2.21

- Changed `PARSER_VERSION` to represent the overall Aurora Translator project version.
- Replaced the generic output schema version constant with `aedb.version.AEDB_SCHEMA_VERSION`, which is scoped specifically to AEDB JSON output.
- Removed the public `OUTPUT_SCHEMA_VERSION` alias because non-AEDB formats should define their own schema versions when they are added.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.21`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.20

- Scoped parser version constants to AEDB parsing by adding `AEDB_PARSER_VERSION` and `AEDB_OUTPUT_SCHEMA_VERSION`.
- Kept `PARSER_VERSION` and `OUTPUT_SCHEMA_VERSION` as backward-compatible aliases for existing callers.
- Updated AEDB metadata and parser logs to use the AEDB-scoped version constants.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.20`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.19

- Added a segment-arc fast path during polygon primitive serialization.
- For straight segment arcs, reused raw start/end points and the raw length while deriving `mid_point`, `center`, `radius`, and `is_ccw` without extra `.NET` geometry calls.
- Preserved exact JSON output semantics for arc fields while reducing repeated per-segment geometry access.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.19`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.18

- Added a shared layout object index that aggregates component instances, primitive counts by net, padstack counts by net, and component names by net in one `GetAllLayoutObjInstances()` scan.
- Reused the layout object index in net extraction so `primitive_count`, `padstack_instance_count`, and `component_count` no longer require separate wrapper scans.
- Kept the component instance cache on the same shared index, avoiding duplicate layout object scans between net and component extraction.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.18`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.17

- Added a bulk component-instance cache built from `layout_instance.GetAllLayoutObjInstances()` and keyed by the raw component layout-object id.
- Switched component `center` and `bounding_box` extraction to reuse the cached bulk layout-object instances before falling back to the legacy per-component PyEDB lookup.
- Added a dedicated timing step for building the component instance map so large-board hotspot analysis is visible in the logs.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.17`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.16

- Optimized polygon arc serialization by switching the hot path to a thinner raw `.NET` arc reader and constructing `ArcModel` objects directly when the raw geometry calls succeed.
- Preserved the existing fallback validation path for compatibility when a raw arc object does not expose the expected geometry members.
- Reduced repeated per-arc wrapper and validation overhead in polygon primitive extraction while keeping the JSON schema unchanged.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.16`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.15

- Fixed the primitive path-length fast path so path `length` is computed directly from raw center-line arc data instead of falling back to the slower PyEDB wrapper property.
- Added a raw primitive `aedt_name` fast path based on `GetProductProperty(...)`, with a deterministic fallback that preserves the existing AEDT naming semantics.
- Reduced repeated high-level wrapper traversal during primitive serialization while keeping the JSON schema unchanged.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.15`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.14

- Reworked full-detail summary generation to reuse already extracted layers, padstacks, components, and primitives instead of issuing separate expensive PyEDB summary calls.
- Computed `layout_size` from serialized primitive bounding boxes and `stackup_thickness` from serialized layer elevations or thickness values, preserving the existing summary values.
- Kept `summary-only` mode on the original raw PyEDB summary path to minimize behavior risk outside full-detail exports.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.14`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.13

- Replaced per-net wrapper traversal with one-pass aggregation across cached primitives and padstack instances.
- Computed `primitive_count` and `padstack_instance_count` by net name during a single scan of cached layout objects.
- Computed `component_count` from unique component names attached to each net through padstack instances, matching PyEDB net semantics without repeated wrapper construction.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.13`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.12

- Replaced the summary `get_statistics()` call with an equivalent local fast path.
- Counted component categories in one pass to populate `num_discrete_components`, `num_resistors`, `num_inductors`, and `num_capacitors`.
- Computed `num_layers`, `num_nets`, `num_traces`, `num_polygons`, and `num_vias` directly from cached extraction context collections.
- Kept `layout_size` and `stackup_thickness` semantics aligned with the existing PyEDB summary fields.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.12`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.11

- Added a fast path for component metadata extraction.
- Read component `refdes`, `part_name`, `placement_layer`, `location`, `center`, `rotation`, and `bounding_box` directly from low-level PyEDB objects when available.
- Reused one component model probe to populate both `model_type` and `value`, avoiding repeated wrapper traversal.
- Reused cached signal layer names to derive `is_top_mounted` without rebuilding the stackup signal-layer list for each component.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.11`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.10

- Added a fast path for primitive geometry extraction.
- Reused one low-level polygon data query to populate primitive `area`, `bbox`, `raw_points`, and `arcs`.
- Reused one low-level center line query to populate path `center_line` and `length`.
- Read primitive `id`, `type`, `layer_name`, `net_name`, `component_name`, and `is_void` directly from low-level PyEDB objects when available, with safe fallback to the existing wrapper path.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.10`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.9

- Added a fast path for component pin extraction using cached padstack instances.
- Built component `pins`, `nets`, and `numpins` from grouped padstack instances instead of re-scanning PyEDB component layout objects.
- Added finer-grained timing logs for component pin grouping and component model serialization.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.9`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.8

- Added a fast path for padstack instance extraction.
- Reused one low-level position/rotation query to populate both `position` and `rotation`.
- Reused one low-level layer range query to populate `start_layer`, `stop_layer`, and `layer_range_names`.
- Read `padstack_definition` directly from the low-level PyEDB object when available, with safe fallback to the existing wrapper path.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.8`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.7

- Added `ExtractionContext` to cache shared PyEDB collections during one parse run.
- Reused cached collections across summary and detailed extractors.
- Added finer-grained timing logs for summary, padstack, and primitive extraction.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.7`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.6

- Added generated AEDB JSON Schema documentation under `aedb/docs/aedb_schema.json`.
- Maintained AEDB JSON field documentation in the bilingual file `aedb/docs/aedb_json_schema.md`, with Chinese first and English second.
- Linked the schema documentation from `README.md`.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.6`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.5

- Split PyEDB data extraction into domain modules under `aedb.extractors`.
- Kept `aedb.models` focused on Pydantic output schemas.
- Parser orchestration now builds `AEDBLayout` through `aedb.extractors.build_aedb_layout`.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.5`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.4

- Extracted PyEDB value normalization helpers from `aedb.models` into `aedb.normalizers`.
- Kept AEDB Pydantic model definitions focused on schema and object assembly.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.4`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.3

- Moved the legacy `layout_parser` compatibility package out of the project to `../layout_parser`.
- Removed the legacy `layout-parser` console script from the current project.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.3`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.2

- Promoted the package contents so the workspace root itself is the `aurora_translator` package directory.
- Removed the nested `aurora_translator` package directory and the old `src` path bootstrapping.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.2`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.1

- Moved implementation into the `src/aurora_translator` package layout.
- Split AEDB session handling, CLI, core utilities, and JSON serialization into separate modules.
- Added `board_model` as an intentionally empty placeholder for the future shared board model.
- JSON output schema is unchanged from `0.2.0`.
- `metadata.parser_version` now reports `0.2.1`; `metadata.output_schema_version` remains `0.2.0`.

## 0.2.0

- Added `metadata.parser_version` to each exported JSON payload.
- Added `metadata.output_schema_version` to each exported JSON payload.
- Current JSON layout uses top-level `layers` instead of the older `stackup.layers` wrapper.

## 0.1.0

- Initial AEDB JSON export structure.
