<a id="top"></a>
# AEDB `.def` Binary Format Notes

[中文](#zh)

<a id="zh"></a>
## 中文

本文是 AEDB `.def` 文件的二进制格式逆向说明，重点服务当前
`.def -> AEDBDefBinaryLayout` 读取器维护，并为未来 `AuroraDB -> AEDB .def`
writer 打基础。它只记录当前项目已经能读取、验证或必须保留的文件结构，
不是 Ansys 官方格式规范。

当前实现仍以“读取”为主：`crates/aedb_parser/` 能扫描 `.def` record stream、
抽取 text DSL 和若干 native binary object，并能做 byte-identical roundtrip。
未来从 AuroraDB 生成 `.def` 时，应优先基于本文描述的 record 和 object 关系，
采用保守的 template-based writer，而不是直接从零合成所有未知二进制字段。

范围边界：

- 本文覆盖 AEDB `.def` 二进制 record stream 的读取、domain 抽取和 roundtrip 写回。
- 本文中的 writer 说明只用于未来设计，不表示当前已经支持从 AuroraDB 直接生成新 `.def`。
- 当前可信依据是 `crates/aedb_parser/`、`sources/aedb/def_binary.py`、
  `sources/aedb/def_models.py`、`semantic/adapters/aedb_def_binary.py`
  和仓库内 AEDB case 的解析测试。
- 默认 PyEDB 解析路径仍是 `sources/aedb/parser.py`；本文只描述显式
  `--aedb-backend def-binary` 路径。

## 读写可信度

下表定义本文中字段的可信度：

| 级别 | 含义 | Writer 建议 |
| --- | --- | --- |
| confirmed | 多个样本验证，代码直接读取并用测试锁定。 | 可以生成，但仍需和标准输出对拍。 |
| contextual | 可由上下文稳定推断，例如 polygon owner 从 primitive stream 顺序恢复。 | 可以作为 writer 初版规则，但要保留 fallback 和验证。 |
| guard-only | 字节值用于识别 record，业务含义未知。 | 生成时应复制模板值，不要自定义解释。 |
| unknown | 未命名字段或未验证对象类型。 | 从零 writer 暂不应生成；template writer 应原样保留。 |

## 入口文件

| 路径 | 作用 |
| --- | --- |
| `crates/aedb_parser/src/parser.rs` | `.def` record scanner、text DSL block summary、header 字段和 record hash 统计。 |
| `crates/aedb_parser/src/domain.rs` | 从 text DSL 和 binary records 抽取 domain：net、layer、padstack、component、padstack instance、path、polygon。 |
| `crates/aedb_parser/src/model.rs` | Rust `AedbDefLayout` 输出模型。 |
| `crates/aedb_parser/src/writer.rs` | source-fidelity roundtrip writer，按原 record 边界写回。 |
| `crates/aedb_parser/src/auroradb.rs` | `.def` domain 与标准 AuroraDB 目录的对照辅助。 |
| `sources/aedb/def_binary.py` | Python 集成层，调用 Rust native 或 CLI 并构造 Pydantic model。 |
| `sources/aedb/def_models.py` | Python `AEDBDefBinaryLayout` schema。 |
| `semantic/adapters/aedb_def_binary.py` | `.def` binary source JSON 到 `SemanticBoard` 的 stackup、component、via、trace、polygon 映射。 |

## 解析管线

当前读取链路：

```text
.def bytes
  -> scan_records()
  -> text record / binary gap 切分
  -> analyze_text_record()
  -> extract_domain()
  -> AedbDefLayout JSON
  -> AEDBDefBinaryLayout
  -> SemanticBoard
  -> AuroraDB
```

关键边界：

- `parser.rs` 只负责 record 边界、text DSL 结构摘要和文件级 summary。
- `domain.rs` 才负责从 text 和 binary bytes 中抽取可用业务对象。
- `sources/aedb/def_binary.py` 不重新解析二进制，只把 Rust JSON 组装成 Python model。
- `semantic/adapters/aedb_def_binary.py` 是几何语义层：它把 raw meter 坐标、arc-height、
  raw definition、component pin name 和 polygon void 关系转成统一模型。

## 当前输出模型

`AedbDefLayout` 是本项目自有 source JSON，不是 Ansys 官方 `.def` schema。

顶层字段：

| 字段 | 说明 |
| --- | --- |
| `metadata` | 项目版本、parser 版本、source path、backend 等。 |
| `summary` | 文件大小、record 数、text/binary 字节数、DSL block 数、header 元数据。 |
| `domain` | 当前可用业务对象和 native binary geometry。 |
| `records` | 可选 record summaries；`include_details=false` 时省略。 |
| `blocks` | 可选 text DSL block summaries；`include_details=false` 时省略。 |
| `diagnostics` | scanner / text DSL 结构诊断。 |

`summary` 重要字段：

| 字段 | 来源 |
| --- | --- |
| `file_size_bytes` | 输入文件总字节数。 |
| `record_count` | text record + binary record 数。 |
| `text_record_count` / `binary_record_count` | record 类型计数。 |
| `text_payload_bytes` / `binary_bytes` | payload 字节计数。 |
| `dsl_block_count` / `top_level_block_count` | `$begin` / `$end` block 统计。 |
| `assignment_line_count` | `key=value` 风格行数。 |
| `function_line_count` | `Function(...)` 风格行数。 |
| `def_version` | 从 `Version=` 读取。 |
| `last_update_timestamp` | 从 `LastUpdateTimeStamp=` 读取。 |
| `encrypted` | 从 `Encrypted=` 读取。 |

`domain` 主要字段：

| 字段 | 来源 |
| --- | --- |
| `layout_nets` | binary layout net table。 |
| `materials` | text DSL `EDB/Materials/<name>`。 |
| `stackup_layers` | text DSL `SLayer(...)`。 |
| `board_metal_layers` | `SLayer(T='signal')` 且排除 solderball / port / extent / airbox 辅助层。 |
| `padstacks` | text DSL `EDB/pds/pd`。 |
| `padstack_instance_definitions` | 7-byte binary prefix + `$begin ''` text block。 |
| `components` | text DSL `EDB/Components/<name>`。 |
| `component_placements` | top-level refdes text block。 |
| `binary_strings` | binary length-prefixed ASCII string 统计。 |
| `binary_geometry` | native binary object 聚合计数。 |
| `binary_padstack_instance_records` | native padstack instance records。 |
| `binary_path_records` | native path/trace records。 |
| `binary_polygon_records` | native polygon、void 和 outline polygon records。 |

`RecordSummary` 字段：

| 字段 | 说明 |
| --- | --- |
| `index` | record 顺序号。 |
| `kind` | `text` 或 `binary`。 |
| `offset` / `end_offset` | 原文件 byte 范围。 |
| `total_size` / `payload_size` | record 总长度和 payload 长度。 |
| `tag` | text record tag；binary record 为 `null`。 |
| `payload_hash` | FNV-1a 64-bit hex，用于对拍。 |
| `valid_utf8` | text payload 是否可按 UTF-8 解码。 |
| `first_block_name` / `block_count` | text DSL block summary。 |

`DslBlockSummary` 字段：

| 字段 | 说明 |
| --- | --- |
| `record_index` | 所属 text record。 |
| `name` | `$begin '<name>'` block name。 |
| `path` | 按嵌套拼出的 block path。 |
| `depth` | 嵌套深度。 |
| `start_line` / `end_line` | text payload 内行号。 |
| `assignment_line_count` / `function_line_count` / `other_line_count` | block 内 line 分类统计。 |

## 文件整体结构

AEDB `.def` 是一个 record stream，不是 ANF 文本的二进制压缩版。文件由两类 record
交错组成：

| record 类型 | 识别方式 | 当前读行为 | Writer 含义 |
| --- | --- | --- | --- |
| text record | 5-byte header 后 payload 以 `$begin '` 开头 | 解码 UTF-8 DSL | 可重写 payload，但必须重算 length。 |
| binary record | 两个 text record 之间未识别为 text 的原始字节区间 | 按已知 pattern 扫描对象 | 未知部分应保留；生成新对象需满足 preamble / reference 关系。 |

Text record header：

| 偏移 | 类型 | 可信度 | 说明 |
| --- | --- | --- | --- |
| `+0` | `u8` | confirmed | text tag。部分 object id 会由前置 7-byte binary prefix 和该 tag 组合恢复。 |
| `+1` | `u32le` | confirmed | text payload byte length。 |
| `+5` | bytes | confirmed | text payload，通常以 `$begin '` 开头。 |

当前 `crates/aedb_parser/src/writer.rs` 的 writer 只做 source-fidelity roundtrip：

- text record 写出 `tag + u32le(length) + raw_text`。
- binary record 原样写出 `binary.bytes`。
- 公开样本 roundtrip 已由 Rust tests 验证为 byte-identical。

这说明 record 边界和 text header 已足够可靠；但从 AuroraDB 生成全新 `.def`
还需要合成 text DSL、binary object preamble、object id、net/layer/padstack 引用和几何 payload。

## Record Scanner

`scan_records()` 不依赖文件级目录表，而是从当前 offset 判断是否是 text record：

1. 当前 offset 至少能容纳 5-byte header 和 `$begin '` 前缀。
2. `offset + 1..+5` 解为 `u32le length`。
3. `payload_start + length` 不越过 EOF。
4. payload 起始字节匹配 `$begin '`。

满足以上条件时生成 `DefRecord::Text`；否则向后搜索下一个满足条件的 text record，
中间所有 bytes 作为一个 `DefRecord::Binary`。

重要含义：

- binary record 不是官方命名的 object record，而是两个 text record 之间的原始字节 gap。
- 一个 binary record 内可能包含多个 native object，例如 net table、padstack instance、
  path、polygon、outline。
- byte-identical roundtrip 依赖 record 边界和 raw bytes，不依赖 domain 抽取是否完整。
- 如果某段 bytes 看起来像 `$begin '` 但 length 越界，parser 会返回
  `TextRecordTooLarge`，避免把破损 text 当成 binary gap 跳过。

Text payload 会进一步做 DSL 结构分析：

| 行形态 | 分类 | 说明 |
| --- | --- | --- |
| `$begin '<name>'` | block start | 入栈并记录 `DslBlockSummary`。 |
| `$end '<name>'` | block end | 出栈并填 `end_line`；不匹配时写 diagnostic。 |
| `key=value` | assignment | 计入 assignment line。 |
| `Function(...)` | function | 计入 function line，允许行尾 `\`。 |
| 其他非空行 | other | 保留统计，用于发现新 DSL 语法。 |

## 基础编码约定

| 类型 | 编码 | 备注 |
| --- | --- | --- |
| `u32le` | little-endian unsigned 32-bit | 大部分 tag、length、count、marker 使用。 |
| `i32le` | little-endian signed 32-bit | net/raw owner/raw definition 等可为负的字段。 |
| `f64le` | little-endian IEEE-754 double | 坐标、宽度、旋转、钻孔直径、arc height。 |
| ASCII string | `u32le tag=4` + `u32le length` + payload | payload byte 范围当前要求 `0x20..0x7e`。 |
| 坐标单位 | meter | AuroraDB 对拍时通常换算为 mil。 |
| 旋转单位 | radian | component/padstack instance source rotation。 |

常用换算：

```text
mil = meter * 39370.07874015748
meter = mil * 0.0000254
```

Path/polygon 的 arc 使用 `arc_height` 表示。`arc_height` 本身也是 meter 单位 double。

## Text DSL Record

虽然本文面向二进制写出，但 `.def` 中大量对象定义保存在 text record。未来 writer
不能只写 native binary geometry，还必须生成或复用 text DSL。

Text DSL 基本结构：

```text
$begin '<block name>'
    key=value
    Function(...)
$end '<block name>'
```

当前 reader 读取这些 text DSL 对象：

| 对象 | 主要 block / statement | Writer 作用 |
| --- | --- | --- |
| header | `Hdr` | `Version`、`Encrypted` 等文件元数据。 |
| material | `EDB/Materials/<name>` | stackup material 引用目标。 |
| stackup layer | `SLayer(...)` | 生成 layer id/name/type/thickness/material。 |
| layout layer | `Layer(...)` | 生成 binary path/polygon 中 `layer_id -> name` 的映射。 |
| padstack | `EDB/pds/pd` | 生成 padstack id/name/hole/pad/antipad/thermal。 |
| padstack instance definition | 7-byte prefix + `$begin ''` | 生成 binary padstack instance 的 `raw_definition_index -> padstack/layer range` 映射。 |
| component definition | `EDB/Components/<name>` | 生成 footprint、cell name、pin definition。 |
| component placement | top-level refdes block | 生成 refdes、class、value、package、symbol box。 |

### Text DSL Domain Extraction

`domain.rs` 对 text DSL 的抽取是基于 block path 和 statement prefix 的轻量 parser，
不是完整 AEDB DSL 解释器。已稳定读取的字段如下。

Header summary：

| Statement | 输出字段 |
| --- | --- |
| `Version=` | `summary.def_version` |
| `LastUpdateTimeStamp=` | `summary.last_update_timestamp` |
| `Encrypted=` | `summary.encrypted` |

Material block：

```text
$begin 'EDB'
  $begin 'Materials'
    $begin '<material name>'
      conductivity='...'
      permittivity='...'
      dielectric_loss_tangent='...'
```

| Statement | 输出字段 |
| --- | --- |
| block name | `MaterialDefinition.name` |
| `conductivity=` | `conductivity` |
| `permittivity=` | `permittivity` |
| `dielectric_loss_tangent=` | `dielectric_loss_tangent` |

Stackup / layout layer：

| Statement | 输出字段 | 说明 |
| --- | --- | --- |
| `SLayer(N=..., ID=..., T=..., TB=..., Th=..., LElev=..., Mat=..., FilMat=...)` | `StackupLayer` | `SLayer` 可能跨行，reader 会合并到 `OxideMaterials())` 后再解析。 |
| `Layer(N=..., ID=...)` | `layout_layer_names_by_id` | binary path/polygon 的 `layer_id` 会回填到 layer name。 |

`SLayer` 字段：

| 参数 | 输出字段 |
| --- | --- |
| `N` | `name` |
| `ID` | `id` |
| `T` | `layer_type` |
| `TB` | `top_bottom` |
| `Th` | `thickness` |
| `LElev` | `lower_elevation` |
| `Mat` | `material` |
| `FilMat` | `fill_material` |

Padstack definition：

```text
$begin 'EDB'
  $begin 'pds'
    $begin 'pd'
      id='...'
      nam='...'
      hle(shp=..., Szs('...'), X=..., Y=..., R=...)
      $begin 'lgm'
        lay='...'
        id='...'
        pad(shp=..., Szs('...'), X=..., Y=..., R=...)
        ant(shp=..., Szs('...'), X=..., Y=..., R=...)
        thm(shp=..., Szs('...'), X=..., Y=..., R=...)
```

| Statement | 输出字段 |
| --- | --- |
| `id=` inside `pd` | `PadstackDefinition.id` |
| `nam=` | `PadstackDefinition.name` |
| `hle(...)` | `hole_shape`、`hole_parameters`、`hole_offset_x/y`、`hole_rotation` |
| `lay=` inside `lgm` | `PadstackLayerPad.layer_name` |
| `id=` inside `lgm` | `PadstackLayerPad.id` |
| `pad(...)` | pad shape / size / offset / rotation |
| `ant(...)` | antipad shape / size / offset / rotation |
| `thm(...)` | thermal shape / size / offset / rotation |

Component definition：

```text
$begin 'EDB'
  $begin 'Components'
    $begin '<component name>'
      UID='...'
      Footprint='...'
      CellName='...'
      $begin 'Pin'
        name='...'
        number='...'
        id='...'
```

| Statement | 输出字段 |
| --- | --- |
| component block name | `ComponentDefinition.name` |
| `UID=` | `uid` |
| `Footprint=` | `footprint` |
| `CellName=` | `cell_name` |
| `Pin/name=` | `ComponentPinDefinition.name` |
| `Pin/number=` | `ComponentPinDefinition.number` |
| `Pin/id=` | `ComponentPinDefinition.id` |

Component placement：

Top-level block names not matching `Hdr`、`EDB`、`PropDisplays`、`RCSComponent`
are treated as placement refdes candidates.

| Statement | 输出字段 |
| --- | --- |
| top-level block name | `ComponentPlacement.refdes` |
| `COMP_CLASS=` | `component_class` |
| `COMP_DEVICE_TYPE=` | `device_type` |
| `COMP_VALUE=` | `value` |
| `COMP_PACKAGE=` | `package` |
| `COMP_PART_NUMBER=` | `part_number` |
| `SYM_BOX(x0,y0,x1,y1)` | `symbol_box` |

`part_name_candidates` 是从 `part_number`、`device_type`、`value`、`package`
派生的候选列表，用于 AuroraDB `parts.db` / footprint variant 对齐。

### Writer 必填 text DSL 关系

从 AuroraDB 写 `.def` 时，至少需要保持这些引用闭合：

- `SLayer(... ID=...)` 和 `Layer(... ID=...)` 必须覆盖所有 metal、outline 和需要引用的辅助层。
- `padstack.id` 必须被 padstack instance definition 的 `def=` 引用。
- padstack instance definition 的 `fl=` / `tl=` 必须引用真实 layer id。
- component definition 的 pins 必须能和 binary component-pin padstack instance name 对齐。
- component placement block name 必须是 refdes，并能匹配 component definition / part candidate。

## Binary Object Recognition

`domain.rs` 会在每个 binary gap 内独立扫描多个 pattern。当前已识别对象：

| 对象 | 识别锚点 | 输出数组 / summary | 可信度 |
| --- | --- | --- | --- |
| length-prefixed ASCII string | `u32le tag=4` + `u32le length` + printable ASCII | `domain.binary_strings` | confirmed |
| layout net table | binary record `+8` 的 `max_net_index` + 前部 ASCII string sequence | `domain.layout_nets` | confirmed/contextual |
| padstack instance | ASCII instance name 前 60-byte preamble + tail marker | `domain.binary_padstack_instance_records` | confirmed |
| via-tail hint | marker tail + x/y/diameter | `domain.binary_geometry.via_*_count` | contextual |
| path / trace | fixed 25-byte marker after width | `domain.binary_path_records` | confirmed |
| native polygon / void | 100-byte preamble + `double_count` + marker `2` | `domain.binary_polygon_records` | confirmed/contextual |
| outline polygon | 64-byte preamble + `Outline` layer id + marker `2` | `domain.binary_polygon_records` | confirmed |

扫描原则：

- 所有 native geometry 坐标以 meter 保存。
- 所有 guard 都以“宁可漏读，不要误读”为优先：坐标、width、count、string length、
  layer id、net index 都有范围限制。
- `binary_geometry` summary 只统计当前 parser 识别出的对象，不表示文件中只有这些
  native object。
- `offset`、`count_offset`、`coordinate_offset` 都是原始文件全局 byte offset，便于回查。

## Length-prefixed ASCII Strings

许多 binary object 通过 ASCII string 定位。编码格式：

| 偏移 | 类型 | 可信度 | 说明 |
| --- | --- | --- | --- |
| `+0` | `u32le` | confirmed | tag，ASCII string 当前为 `4`。 |
| `+4` | `u32le` | confirmed | payload length，reader guard 为 `1..512`。 |
| `+8` | bytes | confirmed | ASCII payload。 |

已观察字符串类型：

| 字符串形态 | 用途 |
| --- | --- |
| `via_<digits>` | routing via padstack instance name。 |
| `line_<digits>` / `line__<digits>` | named path/line instance name。 |
| `poly__<digits>` | polygon instance name。 |
| `poly void_<digits>` | polygon void instance name。 |
| `<REFDES>-<PIN>` | component pin padstack instance name。 |
| `UNNAMED...` | unnamed/mechanical padstack instance。 |

Writer 需要为新几何生成稳定且不冲突的 instance names。推荐保持 AEDB 观察到的命名风格，
例如 routing via 使用 `via_<geometry_id>`，component pin 使用 `<refdes>-<pin>`。

## Layout Net Table

Layout net table 当前从某个 binary record 的前部恢复：

| 位置 | 类型 | 可信度 | 说明 |
| --- | --- | --- | --- |
| binary record `+8` | `u32le` | confirmed/contextual | `max_net_index`。 |
| 同 binary record ASCII strings | string list | confirmed | 前 `max_net_index + 1` 个字符串作为 net names。 |

Reader guard：

- `max_net_index > 0` 且不大于 `100000`。
- 第一条 string header offset 不大于 `128`。
- strings 数量至少为 `max_net_index + 1`。

Writer 建议：

- Net index 从 `0` 连续分配。
- 所有 binary path、polygon、padstack instance 的 `net_index` 必须引用该表。
- 如果使用 template writer，优先复用 net table record 的外壳，只重写 `max_net_index`
  和 length-prefixed string sequence。未知 padding 字段先保留模板布局。

## Padstack Instance Binary Record

Padstack instance 是 `.def` 中最重要的几何对象之一，覆盖 routing via、component pin、
unnamed padstack instance 和其他 named padstack instance。

### Object 形态

当前 reader 以 instance name ASCII string 为锚点：

```text
[60-byte preamble][u32le tag=4][u32le name_length][name bytes][4-byte gap][tail...]
```

### 60-byte preamble

Reader 目前用以下 `u32le` marker 识别 preamble：

| preamble 相对偏移 | 期望值 | 可信度 | 说明 |
| --- | ---: | --- | --- |
| `+0` | `7` | guard-only | object marker。 |
| `+4` | `2` | guard-only | object marker。 |
| `+8` | `1` | guard-only | object marker。 |
| `+12` | `0` | guard-only | object marker。 |
| `+16` | `1` | guard-only | object marker。 |
| `+20` | any <= `10000000` | confirmed | `geometry_id`。 |
| `+24` | `0` | guard-only | object marker。 |
| `+28` | `7` | guard-only | object marker。 |
| `+32` | `1` | guard-only | object marker。 |
| `+36` | `7` | guard-only | object marker。 |
| `+40` | `2` | guard-only | object marker。 |
| `+44` | `1` | guard-only | object marker。 |
| `+48` | `11` | guard-only | object marker。 |
| `+52` | `4` | guard-only | object marker。 |
| `+56` | `name_length` | confirmed | 必须等于 ASCII name length。 |

Writer 建议：

- `geometry_id` 应全局唯一，并和 path/polygon id 空间避免冲突。
- guard-only 字段先复制已验证模板值。
- 如果未来发现这些字段是 object type / class / flags，应再升级文档。

### Tail 字段

Name payload 结束后跳过 4 bytes，tail 当前读取：

| tail 相对偏移 | 类型 | 可信度 | 说明 |
| --- | --- | --- | --- |
| `+0` | `u32le` | confirmed | marker，必须为 `4`。 |
| `+4` | `i32le` | confirmed | `net_index`；负值表示无 net。 |
| `+8` | `i32le` | confirmed | `raw_owner_index`。component pin 通常关联 component/pin owner。 |
| `+12` | `u32le` | confirmed | marker，必须为 `4`。 |
| `+16` | `i32le` | confirmed | `raw_definition_index`，映射到 padstack instance definition。 |
| `+20` | `f64le` | confirmed | `x`，meter。 |
| `+32` | `f64le` | confirmed | `y`，meter。 |
| `+44` | `f64le` | confirmed | `rotation`，radian。 |
| `+56` | `f64le` | confirmed | `drill_diameter`，meter；component pad 常为空或不可靠。 |
| `+68` | `u32le + ASCII + i32le` | confirmed | optional secondary name/id。 |

Reader guard：

- 坐标换算到 mil 后必须在 `-10000..10000`。
- rotation 必须有限且 `abs(rotation) <= 10π`。
- drill diameter 只在 `0.1..500 mil` 之间采用。

### Name 分类

| name 形态 | 当前分类 | Writer 用途 |
| --- | --- | --- |
| `via_<digits>` | `via` | 写 routing via。 |
| `UNNAMED...` | `unnamed` | 写 mechanical/no-net/unnamed padstack。 |
| 包含 `-` | `component_pin` | 写 component pin pad。 |
| 其他 | `named` | 其他命名 padstack instance。 |

从 AuroraDB 写 `.def` 时，component pin 的 rotation 建议来自 component placement
和 footprint pad 局部角度合成；routing via rotation 对圆形 padstack 通常不敏感，
但仍应写出确定值。

### Padstack Instance Definition 引用

`raw_definition_index` 不是 padstack id。它通过 text record 的 7-byte object prefix
和 `$begin ''` block 映射到：

- `def=` padstack id。
- `fl=` first layer id。
- `tl=` last layer id。
- `flp=` first layer positive flag。
- `sbl=` solder ball layer id。

Writer 必须先生成这些 text mapping，再让 binary padstack instance tail 的
`raw_definition_index` 引用它们。

## Via-tail Hint Pattern

除完整 padstack instance 外，reader 还扫描一种 via-tail hint，用于统计 named/unnamed
via location：

| tail 相对偏移 | 类型 | 说明 |
| --- | --- | --- |
| `+0` | `u32le == 4` | marker。 |
| `+8` | `u32le == 0xffffffff` | marker。 |
| `+12` | `u32le == 4` | marker。 |
| `+20` | `f64le` | x，meter。 |
| `+32` | `f64le` | y，meter。 |
| `+56` | `f64le` | diameter，meter，guard `1..20 mil`。 |

当前 writer 不应只生成 via-tail hint。真正可用于 semantic/AuroraDB 的对象是完整
padstack instance record。Via-tail hint 可作为兼容或校验对象，具体写法仍需更多样本确认。

## Path Binary Record

Path record 表达 trace/line 几何。Reader 通过固定 marker 定位：

```text
[80-byte preamble][f64le width][25-byte marker][u32le double_count][f64le coordinate stream]
```

其中 marker 当前为：

```text
00 00 00 00
33 33 33 33 33 33 e3 3f
00 00 00 00
24 00 00 00
00 02 00 00 00
```

字段布局：

| 位置 | 类型 | 可信度 | 说明 |
| --- | --- | --- | --- |
| `width_offset - 80` | bytes | guard/contextual | path preamble。 |
| `width_offset` | `f64le` | confirmed | width，meter。 |
| `width_offset + 8` | bytes | confirmed | fixed marker。 |
| `width_offset + 33` | `u32le` | confirmed | coordinate double count。 |
| `width_offset + 41` | `f64le[]` | confirmed | point / arc-height stream。 |

Reader guard：

- width 换算为 mil 后在 `0..100`。
- double count 非零，不超过 `20000`。
- coordinate stream 不越界。

### Path preamble owner 字段

| preamble 相对偏移 | 读取方式 | 可信度 | 输出 |
| --- | --- | --- | --- |
| `+12` / `+16` | low byte big-endian + high little-endian | confirmed | `geometry_id`。 |
| `+40` / `+44` | low byte big-endian + high byte，且 `+45..+47 == 00 00 ff` | confirmed | `net_index`。 |
| `+52` | `u32be - 65536` | confirmed | `layer_id`。 |

Writer 必须保证：

- `geometry_id` 全局唯一。
- `net_index` 引用 layout net table。
- `layer_id` 引用 text layer/stackup id。
- 如果 path 有 `line_<id>` / `line__<id>` name，name string 位于 width 前某个固定窗口内；
  当前 reader 只用它判断 `named`，不依赖它恢复 owner。

### Point / Arc-height Stream

Coordinate stream 以 double pair 解析：

| pair | 输出 item |
| --- | --- |
| `(x, y)` 且 `abs(y) <= 1e100` | point。 |
| `(arc_height, sentinel)` 且 `abs(sentinel) > 1e100` | arc-height marker。 |

Arc marker 表达从前一个 point 到后一个 point 的圆弧：

```text
point(start), arc_height(h), point(end)
```

圆心恢复公式：

```text
dx = end.x - start.x
dy = end.y - start.y
chord = sqrt(dx*dx + dy*dy)
factor = 0.125 * chord / h - 0.5 * h / chord
center.x = start.x + 0.5 * dx + dy * factor
center.y = start.y + 0.5 * dy - dx * factor
```

当前方向约定：

- `h < 0` 对应 AuroraDB `CCW Y`。
- `h >= 0` 对应 AuroraDB `CCW N`。

Writer 从 AuroraDB `Larc`/`Parc` 写 `.def` 时，需要反向由 start/end/center 计算
arc height。反算公式尚未落地，建议新增单独测试：`height -> center -> height`
往返误差必须小于坐标容差。

## Polygon / Void Binary Record

Polygon 和 void 使用与 path 相同的 point / arc-height stream，但 preamble 不同。

普通 polygon record：

```text
[100-byte polygon preamble][u32le double_count][u32le marker=2][f64le coordinate stream]
```

字段：

| 位置 | 类型 | 可信度 | 说明 |
| --- | --- | --- | --- |
| `count_offset - 100` | bytes | guard/contextual | polygon preamble。 |
| `count_offset` | `u32le` | confirmed | coordinate double count。 |
| `count_offset + 4` | `u32le == 2` | confirmed | marker。 |
| `count_offset + 8` | `f64le[]` | confirmed | point / arc-height stream。 |

Reader guard：

- double count 为偶数。
- double count 至少 6，不超过 `200000`。
- point count 至少 3。
- coordinate stream 不越界。

### Polygon preamble confirmed 字段

| preamble 相对偏移 | 读取方式 | 可信度 | 输出 |
| --- | --- | --- | --- |
| `+0` | `u32le >> 16` | confirmed | `geometry_id`。 |
| `+64` | `u32le >> 16` | confirmed/contextual | `net_index`。 |
| `+76` | `u32le >> 16` | confirmed | `layer_id`。 |
| `+84` / `+88` | low/high byte 组合；`0xffff` 表示无 parent | confirmed | `parent_geometry_id`。 |

Preamble 中还有一组固定 marker，当前只用于识别：

| 相对偏移 | 期望值 |
| --- | ---: |
| `+4` | `196608` |
| `+8` | `393216` |
| `+12` | `65536` |
| `+16` | `458752` |
| `+20` | `131072` |
| `+24` | `65536` |
| `+28` | `0` |
| `+32` | `65536` |
| `+40` | `0` |
| `+44` | `458752` |
| `+48` | `0` |
| `+52` | `458752` |
| `+56` | `0` |
| `+60` | `262144` |
| `+68` | `4294901760` |
| `+92` | `16777216` |
| `+96` | `2` |

Writer 建议复制这些 marker，除非未来确认其语义。

### Outer / Void 关系

| 条件 | 含义 |
| --- | --- |
| `parent_geometry_id == None` | outer polygon。 |
| `parent_geometry_id == Some(id)` | void polygon，挂到 parent geometry id。 |

Void polygon net owner 应继承 parent polygon。未来 writer 应确保 parent polygon 在同一
primitive group 中存在，并且 void 的 layer 与 parent layer 一致。

### Polygon owner

当前 owner 恢复规则：

1. 如果 preamble `+64` 解出 `net_index`，直接使用。
2. 如果缺失，则按同一 binary primitive stream 中 path/polygon offset 顺序，
   使用前后 path 的 net context 推断。
3. Void 从 parent 继承 owner。

该规则是 contextual。Writer 不应依赖推断；应尽量直接写出 polygon preamble 的
`net_index`，并通过 net table 保证可解析。

### Trailing closing arc

Polygon stream 可能以 `arc_height` 结尾，表示最后一个 point 闭合回第一个 point 的圆弧。
Writer 必须支持这种尾部 arc，否则圆形/圆角 void 的覆盖关系会错误。

输出 point stream 时应明确处理两种闭合方式：

- 最后一个 item 是 point，且隐式线段闭合到第一个 point。
- 最后一个 item 是 arc_height，表示 arc 闭合到第一个 point。

## Outline Polygon Record

Board outline 有一类特殊 64-byte preamble：

```text
[64-byte outline preamble][u32le double_count][u32le marker=2][f64le coordinate stream]
```

Confirmed 字段：

| preamble 相对偏移 | 读取方式 | 可信度 | 输出 |
| --- | --- | --- | --- |
| `+0` | `u32le >> 16` | confirmed | `geometry_id`。 |
| `+40` | `u32le >> 16` | confirmed | `layer_id`，必须映射到 `Outline` layer。 |

固定 marker：

| 相对偏移 | 期望值 |
| --- | ---: |
| `+4` | `0` |
| `+8` | `458752` |
| `+12` | `0` |
| `+16` | `458752` |
| `+20` | `0` |
| `+24` | `262144` |
| `+28` | `4294901760` |
| `+32` | `4294967295` |
| `+36` | `327679` |
| `+44` | `0` |
| `+48` | `4278190080` |
| `+52` | `620756991` |
| `+56` | `16777216` |
| `+60` | `2` |

Writer 从 AuroraDB board outline 生成 `.def` 时，推荐优先生成 Outline layer 的
outline polygon record，而不是只依赖铜皮 bbox。

## SemanticBoard 映射

`semantic/adapters/aedb_def_binary.py` 消费 `AEDBDefBinaryLayout` 并生成统一
`SemanticBoard`。这层不是二进制 reader，但它定义了当前读取结果怎样被验证和导出。

| Semantic 对象 | DEF source |
| --- | --- |
| `materials` | `domain.materials`，根据 conductivity / permittivity / loss tangent 推断 role。 |
| `layers` | `domain.stackup_layers`，优先使用 text `SLayer`；metal layer 来自 `board_metal_layers`。 |
| `nets` | `domain.layout_nets` + binary padstack/path 中出现的 net name。`<Power/Ground>` 会归一为 `NONET`。 |
| `via_templates` | `raw_definition_index -> padstack instance definition -> padstack/layer range`。 |
| `components` | `domain.component_placements`；缺失 placement 时可由 component-pin records 合成。 |
| `pins` / `pads` | `component_pin` padstack instance name，如 `<REFDES>-<PIN>`。 |
| `vias` | `name_kind == "via"` 的 binary padstack instance records。 |
| `primitives` | `binary_path_records` 和 `binary_polygon_records`。 |
| `board_outline` | sibling ANF outline（若存在）优先，其次 native outline polygon，再其次 Outline layer path records。 |

可选 ANF sidecar：

- 如果同名 `.anf` 存在，adapter 会读取 ANF 中的 via layer span、padstack geometry、
  polygon-with-voids 和 outline，作为更完整的语义补充。
- 如果 `.anf` 不存在，当前路径仍能只依赖 `.def` native binary records 恢复 stackup、
  net、padstack instance、trace、native polygon/void 和 outline polygon。
- 本文的二进制字段说明以无 ANF sidecar 的 `.def` 读取能力为核心；ANF 只作为可选校验
  或补充来源。

Via taxonomy：

| 字段 | 来源 |
| --- | --- |
| `via_type` | padstack instance definition 的 first/last layer 与 board metal layer 顺序。 |
| `start_layer` / `stop_layer` | `fl=` / `tl=` 映射出的 layer name。 |
| `start_layer_index` / `stop_layer_index` | 在 board metal layer stack 中的位置。 |
| `layer_span_count` | 覆盖 metal layer 数。 |
| `spans_full_stack` | 是否从第一层跨到最后一层。 |

Polygon 映射：

- `binary_path_records` 输出 trace / arc primitive。
- `binary_polygon_records` 中 `is_void=false` 的 record 作为 outer polygon。
- `is_void=true` 的 record 按 `parent_geometry_id` 挂到 outer polygon，输出
  `geometry.voids`，下游 AuroraDB target 写成 `PolygonHole`。
- trailing closing arc 会被纳入 native polygon / void coverage，避免圆形 void 丢失。

## Object ID 和引用关系

未来 writer 最容易出错的是 ID 空间。当前建议：

| ID / index | 来源 | 被谁引用 |
| --- | --- | --- |
| `net_index` | layout net table 顺序 | path preamble、polygon preamble、padstack instance tail。 |
| `layer_id` | `SLayer(...)` / `Layer(...)` | path preamble、polygon preamble、padstack instance definitions。 |
| `padstack.id` | `EDB/pds/pd id=` | padstack instance definition `def=`。 |
| `raw_definition_index` | 7-byte prefix + text tag 组合出的 object id | padstack instance tail `+16`。 |
| `geometry_id` | binary object preamble | parent/void relation、instance identity、writer naming。 |
| `parent_geometry_id` | polygon preamble | void 挂到 outer polygon。 |
| `raw_owner_index` | padstack instance tail `+8` | component/pin owner，语义尚未完全命名。 |

从 AuroraDB 写 `.def` 的推荐顺序：

1. 分配 layer ids，并生成 stackup / layout layer text。
2. 分配 net indices，并生成 layout net table binary record。
3. 分配 padstack ids，生成 `EDB/pds/pd` text。
4. 为每个 padstack layer range 分配 `raw_definition_index`，生成对应 7-byte prefix + `$begin ''` text。
5. 分配 component definitions 和 placement text。
6. 分配 geometry ids。
7. 写 component-pin padstack instance records。
8. 写 routing via padstack instance records。
9. 写 path records。
10. 写 polygon/void records。
11. 写 Outline polygon record。
12. 用 parser 读回，检查所有 id/name/layer/net 引用闭合。

## Writer 策略建议

### 阶段 1：只做 lossless roundtrip

已完成。目标是验证 record scanner 和 writer 不破坏原文件：

```bash
cargo test --manifest-path crates/aedb_parser/Cargo.toml roundtrip
```

该阶段不能从 AuroraDB 生成新板，但能作为所有后续 writer 的安全底座。

### 阶段 2：template-based writer

推荐作为 `AuroraDB -> .def` 的第一版：

- 输入一个同 AEDT/EDB 版本的 seed `.def`。
- 保留未知 binary records 和 guard-only preamble 字段。
- 重写已知 text DSL、net table、padstack instance、path、polygon 和 outline payload。
- 对新增对象复制同类对象 preamble 模板，只替换 confirmed 字段。
- 输出后必须用当前 parser 读回，并和 AuroraDB source 对齐。

这个阶段可以实用地生成可打开 `.def` 的概率最高，因为它不要求一次性理解所有 AEDB 内部对象。

### 阶段 3：pure synthesis writer

从零生成 `.def` 需要补齐：

- 文件级必要 record 顺序。
- 所有 object class/type/flag 字段语义。
- binary record 分组规则。
- component owner、pin owner、layout object owner 的完整关系。
- AEDB 工具打开文件时需要的非几何 metadata。

在这些字段未完全反解前，不建议直接实现 pure synthesis。

## AuroraDB 到 `.def` 的字段映射草案

| AuroraDB / Semantic 信息 | `.def` 写出位置 |
| --- | --- |
| units / board metadata | `Hdr` text，内部坐标仍写 meter。 |
| stackup layers | `SLayer(...)` text + `Layer(...)` text。 |
| materials | `EDB/Materials` text。 |
| nets | layout net table binary record。 |
| pad templates / via templates | `EDB/pds/pd` text + padstack instance definition text。 |
| component parts / footprints | `EDB/Components` text。 |
| component placements | top-level refdes text block。 |
| component pins / pads | `component_pin` padstack instance binary records。 |
| routing vias | `via_<id>` padstack instance binary records。 |
| traces | path binary records。 |
| copper polygons / holes | polygon / void binary records。 |
| board outline | Outline polygon binary record。 |

注意：AuroraDB 的 layer geometry 中有些 shape 是 target 展开后的表达，不一定一一对应 AEDB
原生对象。Writer 应以 SemanticBoard 或更高层几何语义为输入，而不是只从 `.lyr` 文本反推。

## 验证基线

当前已验证样本的读取计数。样本名在长期文档中脱敏，真实 case 以仓库测试和
`docs/CHANGELOG.md` 为准：

| 样本 | metal layers | layout nets | padstack instances | paths | polygon records | polygon voids |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `<EDB_CASES>/sample_a.def` | 8 | 335 | 2843 | 1965 | 840 | 766 |
| `<EDB_CASES>/sample_b.def` | 8 | 456 | 3531 | 2833 | 403 | 225 |
| `<EDB_CASES>/sample_c.def` | 10 | 326 | 2709 | 2208 | 744 | 597 |

Writer 输出必须至少通过：

```bash
cargo test --manifest-path crates/aedb_parser/Cargo.toml
uv run python main.py inspect source --format aedb --aedb-backend def-binary <OUTPUT.def>
uv run python main.py convert --from aedb --aedb-backend def-binary --to auroradb <OUTPUT.def> -o <ROUNDTRIP_AURORADB>
uv run python main.py inspect source --format auroradb <ROUNDTRIP_AURORADB>
```

建议新增 writer 专用不变量：

- record stream 可重新扫描，无 text length 越界。
- 所有 `net_index` 都能映射到 net name。
- 所有 `layer_id` 都能映射到 layer name。
- 所有 padstack instance `raw_definition_index` 都能映射到 padstack id 和 layer range。
- 所有 polygon void 的 parent 存在。
- 所有 geometry id 全局唯一。
- 输出再转 AuroraDB 后 component、net、via、path、polygon count 与输入一致或有明确差异说明。

## 已知缺口

- Binary record 分组边界的业务语义尚未完全确认。当前 roundtrip 可靠，纯合成 record ordering
  还需要更多样本。
- Padstack instance preamble 中大量 marker 字段未知，只能复制模板。
- Path/polygon preamble 除 owner/id/layer/parent 外仍有未知字段。
- `raw_owner_index` 尚未完整命名，component pin owner 关系还需更多样本对齐。
- Via-tail hint 是否是 writer 必需对象尚未确认。
- Component variant / BOM 属性未完整反解，`DNI` 等 variant value 需要单独研究。
- 从 AuroraDB arc 到 AEDB `arc_height` 的反算 writer 尚未实现。
- Pure synthesis writer 需要 AEDB 文件级 metadata 和对象 class/flag 的进一步逆向。

## 代码索引

| 主题 | 文件 |
| --- | --- |
| record scanner | `crates/aedb_parser/src/parser.rs` |
| current roundtrip writer | `crates/aedb_parser/src/writer.rs` |
| binary domain extraction | `crates/aedb_parser/src/domain.rs` |
| Rust output model | `crates/aedb_parser/src/model.rs` |
| Python source model | `sources/aedb/def_models.py` |
| Python parser wrapper | `sources/aedb/def_binary.py` |
| current semantic reader | `semantic/adapters/aedb_def_binary.py` |
| AEDB parser changelog | `sources/aedb/docs/CHANGELOG.md` |
| AEDB schema changelog | `sources/aedb/docs/SCHEMA_CHANGELOG.md` |
