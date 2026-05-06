<a id="top"></a>
# Cadence Allegro BRD Binary Format Notes

[中文](#zh)

<a id="zh"></a>
## 中文

本文是 Cadence Allegro `.brd` 二进制文件的逆向说明，重点服务本项目继续完善
BRD 读取器。本文只描述当前项目已经能读取、验证或需要进一步定位的文件结构，
不是 Cadence 官方格式规范。

范围边界：

- 本文面向 `.brd -> BRDLayout` 读取和调试。
- 本文不定义 `AuroraDB -> BRD` 写出方案。
- 本文不要求生成 BRD，也不讨论如何合成 Cadence 可打开的新 `.brd`。
- 当前可信依据是 `crates/brd_parser/`、`sources/brd/`、`semantic/adapters/brd.py`
  和已纳入仓库的 BRD case 验证结果。

## 读取可信度

| 级别 | 含义 | 当前读取行为 |
| --- | --- | --- |
| confirmed | 多版本样本验证，Rust parser 直接建模。 | 输出到 `BRDLayout`，供 Semantic / AuroraDB 继续使用。 |
| contextual | 字段值可通过对象链路稳定推断。 | 输出基础字段，语义层再根据 `key` / `next` / layer / net 关系重建对象。 |
| guard-only | 用于跳过、对齐或防止误读，业务含义未命名。 | parser 只消费字节，不暴露为业务字段。 |
| unknown | 未覆盖或未稳定解释的结构。 | 遇到不能安全跳过的未知 block 会停止并写入 diagnostic。 |

## 入口文件

| 路径 | 作用 |
| --- | --- |
| `crates/brd_parser/src/parser.rs` | BRD 二进制扫描主循环、版本识别、`BRDLayout` source JSON 组装。 |
| `crates/brd_parser/src/parser/header.rs` | 文件 header、string table、linked-list metadata 解析。 |
| `crates/brd_parser/src/parser/blocks.rs` | object block 类型分派和字段读取。 |
| `crates/brd_parser/src/parser/reader.rs` | little-endian reader、字符串、对齐和 Allegro `f64` 读取。 |
| `crates/brd_parser/src/model.rs` | Rust 输出模型。 |
| `sources/brd/models.py` | Python `BRDLayout` Pydantic 模型。 |
| `sources/brd/parser.py` | Python 集成层，优先调用 PyO3 native，失败时回退 Rust CLI。 |
| `semantic/adapters/brd.py` | BRD source JSON 到 `SemanticBoard` 的几何、网络、组件和 stackup 映射。 |

## 文件整体结构

当前读取器把 `.brd` 看作固定 header、string table、连续 object block 三段：

```text
+----------------------+ 0x0000
| file header          |
| linked list metadata |
| layer map            |
+----------------------+ 0x1200
| string table         |
+----------------------+ after string table
| object block stream  |
| zero padding / gaps  |
+----------------------+ EOF
```

关键规则：

- 文件开头 `u32le magic` 决定 Allegro binary format version。
- string table 固定从 `0x1200` 开始。
- string table 之后是顺序排列的 object block stream。
- 每个 object block 的第 1 个字节是 block type，当前支持范围为 `0x01..0x3C`。
- 多数 object block 内部有 `key` 和 `next`。`key` 是对象 ID，`next` 是同类表或
  子链中的下一对象。
- header 里也保存若干 linked-list head / tail，但当前 parser 以顺序扫描为主，
  以 block 自带 `key` / `next` 做语义重建。
- object stream 中的连续 `0x00` 会被视为 gap / padding；parser 会局部扫描到下一个
  可能的 block 起点。

## 基础编码约定

| 类型 | 编码 | 说明 |
| --- | --- | --- |
| `u8` | unsigned 8-bit | block type、layer class、subclass、shape type 等。 |
| `u16` | little-endian unsigned 16-bit | count、string size、padstack layer count 等。 |
| `u32` | little-endian unsigned 32-bit | key、next、string id、count、raw coordinate。 |
| `i32` | little-endian signed 32-bit | raw coordinate、offset、bbox。 |
| Allegro `f64` | 先读 `u32 high`，再读 `u32 low`，拼成 `(high << 32) | low` | arc center、radius 等。不能按普通连续 `f64le` 直接扫。 |
| C string | `NUL` 结尾，可选 4-byte 对齐 | string table 使用。 |
| fixed string | 固定长度字节区，遇 `NUL` 截断 | header version、旧版本 layer name、若干 table 字段使用。 |

坐标和长度在 source JSON 中保留 raw 值。语义层按 header 单位换算：

| Header 单位 | 换算 |
| --- | --- |
| `millimeters` | `semantic_mm = raw / units_divisor` |
| `mils` | `semantic_mil = raw / units_divisor` |
| 其他单位 | 使用 `coordinate_scale_nm = 25400.0 / units_divisor`，再换算到 mm。 |

旋转字段通常命名为 `rotation_mdeg`，含义是 millidegree：

```text
degrees = rotation_mdeg / 1000.0
radians = degrees * pi / 180
```

## Magic 和格式版本

`crates/brd_parser/src/parser.rs` 用 `magic & 0xFFFF_FF00` 识别版本：

| Magic pattern | `format_version` | 说明 |
| --- | --- | --- |
| `0x0013_0000` | `V_160` | Allegro 16.0 系列。 |
| `0x0013_0400` | `V_162` | Allegro 16.2 系列。 |
| `0x0013_0C00` | `V_164` | Allegro 16.4 系列。 |
| `0x0013_1000` | `V_165` | Allegro 16.5 系列。 |
| `0x0013_1500` | `V_166` | Allegro 16.6 系列。 |
| `0x0014_0400` / `0x0014_0500` / `0x0014_0600` / `0x0014_0700` | `V_172` | 17.2 系列。 |
| `0x0014_0900` / `0x0014_0E00` | `V_174` | 17.4 系列。 |
| `0x0014_1500` | `V_175` | 17.5 系列。 |
| `0x0015_0000` / `0x0015_0200` | `V_180` | 18.0 系列。 |
| `0x0016_0100` | `V_181` | 新版 BRD 样本当前落在该分支。 |

`magic` 高 16 位小于等于 `0x0012` 时，当前实现认为是 pre-v16，不支持读取。

## Header

Header 从文件开头开始。当前已建模字段如下：

| 字段 | 类型 | 可信度 | 说明 |
| --- | --- | --- | --- |
| `magic` | `u32` | confirmed | 格式版本识别。 |
| `file_role` | `u32` | confirmed | 文件角色，含义未进一步拆分。 |
| `writer_program` | `u32` | confirmed | 写入程序标识，含义未进一步拆分。 |
| `object_count` | `u32` | confirmed | 文件声明对象数；不一定等于当前 parser 已建模 block 数。 |
| `max_key` | `u32` | confirmed | 文件中对象 key 的上界提示。 |
| `allegro_version` | fixed string 60 | confirmed | Header 中的人类可读 Allegro 版本字符串。 |
| `board_units_code` | `u8` | confirmed | 单位代码。 |
| `board_units` | derived | confirmed | `mils`、`inches`、`millimeters`、`centimeters`、`micrometers` 或 `unknown`。 |
| `units_divisor` | `u32` | confirmed | raw 坐标除数。 |
| `coordinate_scale_nm` | derived | contextual | `25400.0 / units_divisor`，用于非 mil / mm 的 fallback 换算。 |
| `string_count` | `u32` | confirmed | string table 入口数量。 |
| `x27_end` | `u32` | guard-only | block `0x27` 的跳过边界。 |
| `linked_lists` | map | contextual | header 中记录的 object list head / tail。 |
| `layer_map` | 25 entries | contextual | class code 到 layer-list key 的映射提示。 |

单位代码：

| Code | 单位 |
| --- | --- |
| `0x01` | `mils` |
| `0x02` | `inches` |
| `0x03` | `millimeters` |
| `0x04` | `centimeters` |
| `0x05` | `micrometers` |

版本差异：

- `V_180` 之前和之后 linked-list pair 的 head / tail 顺序不同。
- `V_180+` 在标准 linked list 前还有 `v18_1..v18_5`，并在后部可能出现
  `v18_extra_1..v18_extra_4`。
- Header 中 `allegro_version` 字符串起点用于校验 header stride：
  - pre-`V_180`：期望 offset `0xF8`。
  - `V_180+`：期望 offset `0x124` 或 `0x144`。

当前 linked-list 名称是 parser 内部的稳定标签，不等价于官方字段名：

```text
0x04_net_assignments
0x06_components
0x0c_pin_defs
shapes
0x14_graphics
0x1b_nets
0x1c_padstacks
0x24_0x28
unknown1
0x2b_footprints
0x03_0x30
0x0a_drc
0x1d_0x1e_0x1f
unknown2
0x38_films
0x2c_tables
0x0c_secondary
unknown3
0x36
unknown6
0x0a_2
```

## String Table

String table 固定从 `0x1200` 开始，读取 `header.string_count` 个 entry。

每个 entry：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `u32le` | 字符串 ID。 |
| `value` | C string | `NUL` 结尾，读取后按 4-byte 对齐。 |

string id 被多个对象引用：

- net name。
- padstack name。
- component device type。
- component symbol name。
- component instance refdes。
- footprint name。
- footprint library path。
- pad definition name。
- V165+ layer-list entry name。

读取器会先构建 `id -> value` map，再回填 `Net.name`、`Padstack.name`、
`Component.device_type`、`Component.symbol_name`、`ComponentInstance.refdes`、
`Footprint.name`、`Footprint.sym_lib_path` 和 `PadDefinition.name`。

## Object Block Stream

string table 结束后，parser 顺序读取 object block：

1. 读取当前 offset 的 `block_type`。
2. 如果是 `0x00`，跳过 zero gap 并尝试对齐到下一个 block。
3. 如果 `block_type > 0x3C`，停止扫描并记录 diagnostic。
4. 根据 block type 调用对应 parse 函数。
5. 记录 `BlockSummary`：`block_type`、`type_name`、`offset`、`length`、`key`、`next`。
6. 将已建模对象放入 `BRDLayout` 对应数组。

`BlockSummary` 很重要：即使某些 block 当前只做 key / next 或跳过，其 offset 和 length
仍可用于后续逆向和语义层回读原始 bytes。

## Block Type 表

当前 `blocks.rs` 识别以下 block type：

| Type | 名称 | 当前建模状态 |
| --- | --- | --- |
| `0x01` | `ARC` | 建模为 `Segment(kind="arc")`。 |
| `0x03` | `FIELD` | 跳过多种 subtype，保留 key / next。 |
| `0x04` | `NET_ASSIGNMENT` | 建模 `NetAssignment`。 |
| `0x05` | `TRACK` | 建模 `Track`。 |
| `0x06` | `COMPONENT` | 建模 `Component`。 |
| `0x07` | `COMPONENT_INST` | 建模 `ComponentInstance`。 |
| `0x08` | `PIN_NUMBER` | 保留 key / next。 |
| `0x09` | `FILL_LINK` | 保留 key。 |
| `0x0A` | `DRC` | 保留 key / next。 |
| `0x0C` | `PIN_DEF` | 保留 key / next。 |
| `0x0D` | `PAD` | 建模 `PadDefinition`。 |
| `0x0E` | `RECT_0E` | 保留 key / next。 |
| `0x0F` | `FUNCTION_SLOT` | 保留 key / next。 |
| `0x10` | `FUNCTION_INST` | 保留 key。 |
| `0x11` | `PIN_NAME` | 保留 key / next。 |
| `0x12` | `XREF` | 保留 key。 |
| `0x14` | `GRAPHIC` | 保留 key / next。 |
| `0x15` / `0x16` / `0x17` | `SEGMENT` | 建模为 `Segment(kind="line")`。 |
| `0x1B` | `NET` | 建模 `Net`。 |
| `0x1C` | `PADSTACK` | 建模 `Padstack` 和 `PadstackComponent`。 |
| `0x1D` | `CONSTRAINT_SET` | 跳过 variable-size payload，保留 key / next。 |
| `0x1E` | `SI_MODEL` | 跳过 string payload，保留 key / next。V18.1 有局部重同步保护。 |
| `0x1F` | `PADSTACK_DIM` | 跳过 version-dependent stride，保留 key / next。 |
| `0x20` | `UNKNOWN_20` | 保留 key / next。 |
| `0x21` | `BLOB` | 按 size 跳过，保留 key。 |
| `0x22` | `UNKNOWN_22` | 保留 key。 |
| `0x23` | `RATLINE` | 保留 key / next。 |
| `0x24` | `RECT` | 保留 key / next。 |
| `0x26` | `MATCH_GROUP` | 保留 key。 |
| `0x27` | `CSTRMGR_XREF` | 根据 `header.x27_end` 跳过。 |
| `0x28` | `SHAPE` | 建模 `Shape`。 |
| `0x29` | `PIN` | 保留 key。 |
| `0x2A` | `LAYER_LIST` | 建模 `Layer`。 |
| `0x2B` | `FOOTPRINT_DEF` | 建模 `Footprint`。 |
| `0x2C` | `TABLE` | 保留 key / next。 |
| `0x2D` | `FOOTPRINT_INST` | 建模 `FootprintInstance`。 |
| `0x2E` | `CONNECTION` | 保留 key / next。 |
| `0x2F` | `UNKNOWN_2F` | 保留 key。 |
| `0x30` | `TEXT_WRAPPER` | 建模 text 位置、层、旋转、string graphic key。 |
| `0x31` | `STRING_GRAPHIC` | 建模 text 字符串 payload。 |
| `0x32` | `PLACED_PAD` | 建模 `PlacedPad`。 |
| `0x33` | `VIA` | 建模 `Via`。 |
| `0x34` | `KEEPOUT` | 建模 `Keepout`，用于 polygon void。 |
| `0x35` | `FILE_REF` | 跳过固定 payload。 |
| `0x36` | `DEF_TABLE` | 按 substruct code 跳过 table payload，保留 key / next。 |
| `0x37` | `PTR_ARRAY` | 跳过固定数组，保留 key / next。 |
| `0x38` | `FILM` | 保留 key / next。 |
| `0x39` | `FILM_LAYER_LIST` | 保留 key。 |
| `0x3A` | `FILM_LIST_NODE` | 保留 key / next。 |
| `0x3B` | `PROPERTY` | 跳过 property payload；语义层可从原始 bytes 读取 embedded stackup。 |
| `0x3C` | `KEY_LIST` | 跳过 key list payload，保留 key。 |

## Layer 和 Class / Subclass

很多几何对象在 block type 后紧跟两个字节：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `class_code` | `u8` | Allegro class。 |
| `subclass_code` | `u8` | Allegro subclass 或物理层序号。 |

当前 class code 名称：

| Code | 名称 |
| --- | --- |
| `0x01` | `BOARD_GEOMETRY` |
| `0x02` | `COMPONENT_VALUE` |
| `0x03` | `DEVICE_TYPE` |
| `0x04` | `DRAWING_FORMAT` |
| `0x05` | `DRC_ERROR` |
| `0x06` | `ETCH` |
| `0x07` | `MANUFACTURING` |
| `0x08` | `ANALYSIS` |
| `0x09` | `PACKAGE_GEOMETRY` |
| `0x0A` | `PACKAGE_KEEPIN` |
| `0x0B` | `PACKAGE_KEEPOUT` |
| `0x0C` | `PIN` |
| `0x0D` | `REF_DES` |
| `0x0E` | `ROUTE_KEEPIN` |
| `0x0F` | `ROUTE_KEEPOUT` |
| `0x10` | `TOLERANCE` |
| `0x11` | `USER_PART_NUMBER` |
| `0x12` | `VIA_CLASS` |
| `0x13` | `VIA_KEEPOUT` |
| `0x14` | `ANTI_ETCH` |
| `0x15` | `BOUNDARY` |
| `0x16` | `CONSTRAINTS_REGION` |

固定 subclass 名称：

| 条件 | 名称 |
| --- | --- |
| `(class=0x01, subclass=0xEA)` | `BGEOM_OUTLINE` |
| `(class=0x04, subclass=0xFD)` | `DFMT_OUTLINE` |
| `subclass=0xF8` | `DISPLAY_BOTTOM` |
| `subclass=0xF9` | `DISPLAY_TOP` |
| `subclass=0xFA` | `SILKSCREEN_BOTTOM` |
| `subclass=0xFB` | `SILKSCREEN_TOP` |
| `subclass=0xFC` | `ASSEMBLY_BOTTOM` |
| `subclass=0xFD` | `ASSEMBLY_TOP_OR_ALL` |

物理铜层来自 `0x2A LAYER_LIST`。V165+ 的 layer list entry 是 string id，
parser 当前先输出为 `string:<id>`，语义层再通过 string table 得到实际层名。

语义层只把 class `0x06 ETCH` 映射为可布线金属层。`subclass_code` 优先按层名或
物理层序号解析。

## Net 和 Net Assignment

BRD 中 net 与对象连接不是每个几何对象都直接保存 net name，而是通过 key 链连接。

### `0x1B NET`

已建模字段：

| 字段 | 说明 |
| --- | --- |
| `key` | net object key。 |
| `next` | 下一个 net。 |
| `name_string_id` / `name` | net 名称。 |
| `assignment` | 关联的 net assignment key。 |
| `fields` | property / field 链入口。 |
| `match_group` | match group key。 |

### `0x04 NET_ASSIGNMENT`

已建模字段：

| 字段 | 说明 |
| --- | --- |
| `key` | assignment object key。 |
| `next` | 下一个 assignment。 |
| `net` | 关联的 net key。 |
| `conn_item` | 连接对象链的起点。 |

`semantic/adapters/brd.py` 会从 `conn_item` 开始，按 `BlockSummary.key -> next`
构建 `connected_item_key -> net_id` map。这样 `Shape`、`Track`、`Via`、`PlacedPad`
等对象即使没有直接 net name，也能通过连接链恢复 net。

Allegro 保留无网络名通常归一为 `NONET`。

## Padstack

### `0x1C PADSTACK`

已建模字段：

| 字段 | 说明 |
| --- | --- |
| `key` / `next` | padstack 对象 ID 和链表下一项。 |
| `name_string_id` / `name` | padstack 名称。 |
| `layer_count` | padstack 覆盖层数。 |
| `drill_size_raw` | 钻孔 raw 直径。 |
| `fixed_component_count` | 固定 component row 数。 |
| `components_per_layer` | 每层 component row 数。 |
| `components[]` | pad / antipad / thermal / keepout 几何表。 |

版本相关 row 数：

| 版本 | fixed rows | per-layer rows |
| --- | --- | --- |
| pre-`V_165` | 10 | 3 |
| `V_165` 到 pre-`V_172` | 11 | 3 |
| `V_172+` | 21 | 4 |

V172+ 每层四类 role：

| per-layer slot | role |
| --- | --- |
| 0 | `antipad` |
| 1 | `thermal_relief` |
| 2 | `pad` |
| 3 | `keepout` |

每个 `PadstackComponent` 当前字段：

| 字段 | 说明 |
| --- | --- |
| `slot_index` | component row 全局序号。 |
| `layer_index` | 物理层序号；fixed rows 为 `null`。 |
| `role` | `fixed`、`antipad`、`thermal_relief`、`pad`、`keepout`。 |
| `component_type` / `type_name` | 几何类型。 |
| `width_raw` / `height_raw` | raw 尺寸。 |
| `z1_raw` | V172+ 额外尺寸；rounded / oblong 类常用作 radius。 |
| `x_offset_raw` / `y_offset_raw` | pad 中心偏移。 |
| `shape_key` | shape-symbol 等复杂 pad 几何引用。 |
| `z2_raw` | 额外引用或尺寸字段；复杂 pad 时可作为 shape key fallback。 |

当前几何类型表：

| Code | `type_name` |
| --- | --- |
| `0x00` | `NULL` |
| `0x02` | `CIRCLE` |
| `0x03` | `OCTAGON` |
| `0x04` | `CROSS` |
| `0x05` | `SQUARE` |
| `0x06` | `RECTANGLE` |
| `0x07` | `DIAMOND` |
| `0x0A` | `PENTAGON` |
| `0x0B` | `OBLONG_X` |
| `0x0C` | `OBLONG_Y` |
| `0x0F` | `HEXAGON_X` |
| `0x10` | `HEXAGON_Y` |
| `0x12` | `TRIANGLE` |
| `0x16` | `SHAPE_SYMBOL` |
| `0x17` | `FLASH` |
| `0x19` | `DONUT` |
| `0x1B` | `ROUNDED_RECTANGLE` |
| `0x1C` | `CHAMFERED_RECTANGLE` |
| `0x1E` | `NSIDED_POLYGON` |
| `0xEE` | `APERTURE_EXT` |

语义层会用这些 component rows 构造 pad / via template shape。对于 `SHAPE_SYMBOL`，
会用 `shape_key` 或 `z2_raw` 回查 `0x28 SHAPE` 的 segment chain。

## Component / Footprint / Pad

组件相关对象由多个 block 共同表达：

| Block | 模型 | 主要字段 |
| --- | --- | --- |
| `0x06 COMPONENT` | `Component` | device type、symbol name、first instance、function slot、pin number、fields。 |
| `0x07 COMPONENT_INST` | `ComponentInstance` | footprint instance、refdes、function instance、first pad。 |
| `0x2B FOOTPRINT_DEF` | `Footprint` | footprint name、first instance、library path、bbox/raw coords。 |
| `0x2D FOOTPRINT_INST` | `FootprintInstance` | placement layer、rotation、x/y、component instance、first pad、text。 |
| `0x0D PAD` | `PadDefinition` | local x/y、padstack key、flags、local rotation。 |
| `0x32 PLACED_PAD` | `PlacedPad` | layer、net assignment、parent footprint、pad key、pin number、name text、bbox。 |

典型关系：

```text
Footprint.first_instance -> FootprintInstance(key)
Component.first_instance -> ComponentInstance(key)
ComponentInstance.footprint_instance -> FootprintInstance(key)
ComponentInstance.first_pad -> PlacedPad(key)
FootprintInstance.first_pad -> PlacedPad(key)
PlacedPad.pad -> PadDefinition(key)
PadDefinition.padstack -> Padstack(key)
PlacedPad.net_assignment -> NetAssignment(key)
```

位置和旋转：

- `FootprintInstance.x_raw` / `y_raw` 是 component placement raw 坐标。
- `FootprintInstance.rotation_mdeg` 是 component placement 旋转。
- `PadDefinition.x_raw` / `y_raw` 是 footprint-local pad 坐标。
- `PadDefinition.rotation_mdeg` 是 footprint-local pad 旋转。
- `PlacedPad.coords_raw` 是 placed pad bbox，不是 pad center 的唯一来源。

底层读取器只保留这些 source 字段；组件 side、pin、pad、footprint shape 和 pad rotation
的最终解释在 `semantic/adapters/brd.py` 中完成。

## Via

### `0x33 VIA`

已建模字段：

| 字段 | 说明 |
| --- | --- |
| `key` / `next` | via 对象 ID 和链表下一项。 |
| `layer` | class / subclass 信息。 |
| `net_assignment` | net assignment key。 |
| `padstack` | padstack key。 |
| `x_raw` / `y_raw` | via placement raw 坐标。 |

当前 via span 主要由 padstack 推断：

- padstack name 若符合 `V<start><end>S-<drill>-<pad>`，语义层从名称恢复 blind / buried
  层范围。
- 否则如果 `layer_count > 1`，默认认为覆盖当前物理铜层 stack。
- pad / barrel shape 来自 `PadstackComponent`，不足时回退到 `drill_size_raw` 或名称尺寸。

## Track / Segment / Arc

走线由 `Track` 指向 segment chain：

| Block | 模型 | 说明 |
| --- | --- | --- |
| `0x05 TRACK` | `Track` | layer、net assignment、first segment。 |
| `0x15` / `0x16` / `0x17 SEGMENT` | `Segment(kind="line")` | line segment。 |
| `0x01 ARC` | `Segment(kind="arc")` | arc segment。 |

`Track.first_segment` 指向第一段。每个 `Segment.next` 指向下一段；语义层按如下规则停止：

- `next == 0`。
- `next == track.key`。
- 遇到重复 key，防止环。
- 找不到 `next` 对应的 segment。

Line segment 字段：

| 字段 | 说明 |
| --- | --- |
| `key` / `next` | segment 对象 ID 和下一段。 |
| `parent` | track / shape / keepout key。 |
| `width_raw` | 线宽 raw。 |
| `start_raw` / `end_raw` | 起止 raw 坐标。 |

Arc segment 额外字段：

| 字段 | 说明 |
| --- | --- |
| `center_raw` | arc center，Allegro `f64` pair。 |
| `radius_raw` | arc radius，Allegro `f64`。 |
| `bbox_raw` | raw bbox。 |
| `clockwise` | 从 subtype bit `0x40` 推断。 |

## Shape / Keepout / Polygon Hole

### `0x28 SHAPE`

`Shape` 表示 copper shape、board outline、shape-symbol 等面几何。

已建模字段：

| 字段 | 说明 |
| --- | --- |
| `key` / `next` | shape 对象 ID 和链表下一项。 |
| `layer` | class / subclass 信息。 |
| `first_segment` | 外轮廓 segment chain 起点。 |
| `first_keepout` | void / keepout chain 起点。 |
| `table` | table key，版本位置不同。 |
| `coords_raw` | bbox raw 坐标。 |

外轮廓通过 `first_segment` 连接 `0x15..0x17` line 和 `0x01` arc。

### `0x34 KEEPOUT`

`Keepout` 用于表达 shape void / polygon hole：

| 字段 | 说明 |
| --- | --- |
| `key` / `next` | keepout 对象 ID 和下一 void。 |
| `layer` | class / subclass 信息。 |
| `flags` | void flags，尚未拆分。 |
| `first_segment` | void contour segment chain 起点。 |

`semantic/adapters/brd.py` 对 shape 的处理：

1. 通过 net assignment 连接链找到 shape net。
2. 读取 shape 外轮廓 segment chain。
3. 从 `first_keepout` 开始遍历 keepout chain。
4. 每个 keepout 的 segment chain 转成一个 polygon void。
5. 输出到 Semantic polygon primitive 的 `geometry.voids`，下游 AuroraDB 输出为
   `PolygonHole`。

Board outline 也来自 `0x28 SHAPE`。语义层会在 `BOARD_GEOMETRY` class 中选择候选，
优先选择 subclass `BGEOM_OUTLINE` / code `0xEA`，再按 bbox 面积和 segment 数挑选。

## Text

Text 由 wrapper 和 string graphic 两类 block 共同表达：

| Block | 模型字段 | 说明 |
| --- | --- | --- |
| `0x30 TEXT_WRAPPER` | layer、x/y、rotation、string graphic key | 保存 text 的放置上下文。 |
| `0x31 STRING_GRAPHIC` | wrapper key、x/y、payload string | 保存实际字符串。 |

当前 source model 输出 `BRDText`，字段包括：

- `key`
- `next`
- `layer`
- `text`
- `x_raw`
- `y_raw`
- `rotation_mdeg`
- `string_graphic_key`

REF_DES、DISPLAY、ASSEMBLY 相关 text 会被语义层用于恢复 component layer 和 refdes
placement context。

## Embedded Stackup Property

BRD 的物理 stackup 信息不总是以常规 layer list 暴露。当前语义层额外支持从
`0x3B PROPERTY` block 中读取 embedded stackup：

1. 通过 `BlockSummary.offset` / `length` 从原始 `.brd` 切出 property bytes。
2. 判断 property name 是否为 `DBPartitionAttachment`。
3. 在 property payload 中查找 zip magic `PK\x03\x04`。
4. 从 zip 中读取 `objects/Design.xml` 和 `Header.xml`。
5. 解析 cross-section layer、material、thickness、conductivity、permittivity、
   loss tangent。
6. 只有当 embedded copper layer names 与当前 BRD 物理铜层名完全一致时，才采用该
   stackup；否则回退为铜层之间插入 `D0..Dn` dielectric placeholder。

这部分不是 Rust source JSON 的显式结构，而是 Semantic adapter 基于 block summary
和原始 `.brd` bytes 做的二次读取。

## 当前 `BRDLayout` 输出结构

`BRDLayout` 是本项目自有 source JSON，不是官方 BRD schema。主要数组：

| 字段 | 来源 |
| --- | --- |
| `header` | file header。 |
| `strings` | string table。 |
| `layers` | `0x2A LAYER_LIST`。 |
| `nets` | `0x1B NET`。 |
| `padstacks` | `0x1C PADSTACK`。 |
| `components` | `0x06 COMPONENT`。 |
| `component_instances` | `0x07 COMPONENT_INST`。 |
| `footprints` | `0x2B FOOTPRINT_DEF`。 |
| `footprint_instances` | `0x2D FOOTPRINT_INST`。 |
| `pad_definitions` | `0x0D PAD`。 |
| `placed_pads` | `0x32 PLACED_PAD`。 |
| `vias` | `0x33 VIA`。 |
| `tracks` | `0x05 TRACK`。 |
| `segments` | `0x01 ARC`、`0x15..0x17 SEGMENT`。 |
| `shapes` | `0x28 SHAPE`。 |
| `keepouts` | `0x34 KEEPOUT`。 |
| `net_assignments` | `0x04 NET_ASSIGNMENT`。 |
| `texts` | `0x30 TEXT_WRAPPER`、`0x31 STRING_GRAPHIC`。 |
| `blocks` | 所有已识别 block 的 summary。 |
| `block_counts` | 按 block type 聚合的计数。 |
| `diagnostics` | 读取过程中的非致命问题。 |

## 已验证读取路径

常用验证命令：

```bash
cargo test --manifest-path crates/brd_parser/Cargo.toml
uv run python main.py inspect source --format brd <BRD_CASE> --log-level ERROR
uv run python main.py dump source --format brd <BRD_CASE> --output <OUTPUT_JSON>
```

当前验证过的读取能力包括：

- 多个同设计、不同 Allegro 保存版本的 `.brd` 可以解析到 `diagnostics=0`。
- `V_172` 到 `V_181` 样本覆盖 header stride、linked-list 顺序和 version gate。
- `0x34 KEEPOUT` 可恢复 shape void，并在下游输出 polygon hole。
- `0x3B PROPERTY` 中的 embedded stackup 只有在 copper name 完全匹配时才被采用。

示例轻量读取结果：

```text
Sample: <BRD_CASES>/demo_v17_2.brd
Result: format=V_172, strings=2679, objects=110019/112674,
        nets=489, padstacks=43, footprints=41, vias=1117, diagnostics=0

Sample: <BRD_CASES>/demo_v25_1.brd
Result: format=V_181, strings=2682, objects=110036/112684,
        nets=489, padstacks=43, footprints=41, vias=1117, diagnostics=0
```

## 已知限制

当前读取器仍有以下限制：

- 许多 block 的业务字段只做 skip / key / next 保留，未完全命名。
- header linked-list metadata 的官方字段含义未全部确定。
- constraint、DRC、film、manufacturing、property table 等非几何业务结构未完整建模。
- text wrapper 与 string graphic 的完整关系仍主要由下游语义规则消费，不是一个完整
  官方 text object 模型。
- padstack 中 `shape_key` / `z2_raw` 对复杂 flash、aperture、NSIDED polygon 的含义
  仍需更多样本确认。
- blind / buried via span 当前部分依赖 padstack 名称规则和 layer_count fallback。
- embedded stackup 只在 property zip 和当前物理铜层名一致时采用；不一致时会回退
  placeholder dielectric。
- board outline 通过 `BOARD_GEOMETRY` shape 候选挑选，若源文件存在多个 outline-like
  shape，仍需要 case 对拍确认优先级。

后续若继续完善 BRD 读取，应优先补充：

- `0x03 FIELD` subtype 到 property / text / component metadata 的映射。
- `0x36 DEF_TABLE` substruct 的字段级模型。
- padstack complex shape / flash / aperture 的真实几何解释。
- text wrapper 和 string graphic 的双向索引。
- 更多 `V_181` 样本对 `v18_extra_*` header 槽位的定位。
