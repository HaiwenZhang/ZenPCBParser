<a id="top"></a>
# 变更记录 / Changelog

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

## 1.0.44

- 修正 Allegro MCM/package 派生 BRD header 解析：BRD parser `0.1.9` 现在识别 V18 header 在版本字符串前新增的 4 个链表槽位，`24.1/25.1` MCM 样本不再把 `board_units_code` 错读为 `12`、`units_divisor` 错读为 `0`。BRD JSON schema 保持 `0.5.0`，预期输出差异为这些新版本 MCM 的 source metadata 和下游坐标缩放恢复到 header 声明单位。
- 验证 `<BRD_CASES>/pkg-mcm-{24.1,25.1}.mcm`：source summary 为 `diagnostics=0`，header 为 `board_units_code=5`、`units_divisor=100`、`coordinate_scale_nm=254.0`；5 个 MCM 版本均可转换并回读 AuroraDB，读回计数为 `layers=17`、`nets=328`、`components=20`、`parts=3`、`net_geometries=22043`、`diagnostics=0`。
- 修正大型 BRD 派生 AuroraDB 输出的读回问题：AuroraDB parser `0.2.14` 现在会在括号表达式内部正确处理 quoted 字符串，`PART_NAME` 等属性值包含 `(` 时不再触发未闭合 reserved expression。AuroraDB JSON schema 保持 `0.2.0`。
- 优化大型 `BRD -> SemanticBoard -> AuroraDB` 转换性能：BRD parser `0.1.8` 的 Python 集成改用 Rust CLI `--output` 临时文件并以受信任构造方式建立 BRD source model，BRD semantic adapter 为 source shape/segment 建一次性索引并对高频 semantic primitive/pad/via 对象使用内部 fast construction。BRD JSON schema、Semantic JSON schema 和 AuroraDB 文件输出不变。
- 验证 `<BRD_CASES>/large-ddr5-17.4.brd`：优化前后 AuroraDB 目录 `diff -qr` 无差异，读回为 `layers=14`、`nets=6207`、`components=6894`、`net_geometries=365949`、`diagnostics=0`；source load 从约 `96.0s` 降至约 `73.6s`，Semantic build 从约 `238.8s` 降至约 `104.3s`。
- 新增 Rust ODB++ target exporter `crates/odbpp_exporter/` 和 Python wrapper `targets/odbpp/`；`convert --to odbpp` 现在走 `source -> SemanticBoard -> ODB++`，不从 AEDB/BRD/ALG/ODB++ source 格式直接旁路导出。
- ODB++ exporter 写出 deterministic 目录结构，覆盖 `matrix/matrix`、`misc/info`、`steps/<step>/profile`、`stephdr`、layer `features` / `attrlist` / drill `tools`、component layer `components`、`eda/data` 和 `netlists/cadnet/netlist`。
- Rust writer 按 `examples/odbpp` 的 C++ 语义拆分：`writer.rs` 只做模块入口，`entity.rs` 负责 entity/step 编排，`features.rs` 负责 feature records，`attributes.rs` 负责 attribute tables 和 layer attrlist，`components.rs` 负责 component records，`package.rs` 负责 EDA package/pin outlines，`eda_data.rs` 负责 EDA net/package data，`netlist.rs` 负责 cadnet netlist，`formatting.rs` 和 `model.rs` 负责 ODB++ 格式化和 Semantic 输入模型。
- 对照 C++ 修正 component `TOP` 记录的 net/subnet 引用，并补齐 cadnet pad/via net point 记录；layer attrlist 会从 Semantic layer/material 的 thickness、material、dielectric constant 和 loss tangent 写出可用属性。JSON schema 不变。
- 验证：`cargo test --manifest-path crates/odbpp_exporter/Cargo.toml` 通过，生成的 ODB++ 目录可由现有 Rust ODB++ parser 读回。
- 修正 `examples/AX7996A_MB_V3/AuroraDB` 的 AuroraDB -> ODB++ -> AuroraDB 回环保真问题：AuroraDB adapter 现在保留 layout shapes，展开 `Line` / `Larc` / `Polygon` / `PolygonHole` / `SymbolID+Location` net geometry，并把 `COMP_*` pin/pad layer 映射回真实金属层；ODB++ exporter 保留源 net 名称、修正 `eda/data` `LYR` / `FID` 顺序，并写出 flashed net geometry。
- 验证 `examples/AX7996A_MB_V3/AuroraDB` 回环：`units=mm`、`metal_layers=10`、`nets=1278`、`components=2176`、`parts=244`、`netpins=8589`、`netvias=27914`、`net_geometries=68091` 一致，按 `layer|net` 聚合的 net geometry mismatch 为 `0`。`shape_count` 和 `via_template_count` 因 ODB++ symbol / via template 规范化而不同。
- 修正 `<CASE_ROOT>/AX-small` 驱动的 Allegro ALG / BRD 到 AuroraDB 对齐问题：ALG adapter 现在保留 extracta stackup material / dielectric、源单位坐标、最大 board outline、`NoNet`、part 名称和多层 padstack via；BRD adapter 现在使用 source component / instance / footprint / pad definition 字段恢复 refdes、part/package、side、component 位置旋转、pin 名称和 NPTH-like hole via。
- BRD parser `0.1.5` / BRD JSON schema `0.4.0` 新增 0x06 component、0x07 component instance、0x2D footprint instance 和 0x0D pad definition source model。Semantic parser 更新到 `0.7.6`，Semantic JSON schema 保持 `0.7.1`；ALG parser / ALG JSON schema 不变。
- 验证 `<CASE_ROOT>/AX-small`：ALG 生成的 AuroraDB `stackup.dat` 与标准输出一致，`part_names=244/244`、`via_templates=31`、`netvias=27914`、`netpins=8589`；BRD 生成的 AuroraDB 为 `part_names=244/244`、`via_templates=31`、`netvias=27914`、`netpins=8589`、`components=2176`、`pins=8589`。BRD source 仍不暴露完整介质/material stackup，因此 BRD stackup 输出只覆盖可解析的 copper layer。
- 修正 `<CASE_ROOT>/AX-small` 驱动的 BRD board outline 与 via/template 对齐：BRD adapter 现在从 `BOARD_GEOMETRY/BGEOM_OUTLINE` segment chain 写出 `board_outline`，从 Allegro via padstack 名称恢复 blind/buried 层跨度和 drill/pad 尺寸，为 POB/slot padstack 写出 `RectCutCorner` template，并用 padstack offset 写出 component-pad `NetVias` 的 drill center。Semantic parser 更新到 `0.7.7`，Semantic JSON schema 保持 `0.7.1`；BRD parser / BRD JSON schema 不变。
- 验证 `<CASE_ROOT>/AX-small`：BRD 生成的 AuroraDB `layout.db` outline 与 ALG 和标准输出一致，`via_templates=31`、`netvias=27914`、`nets_with_vias=865`、`diagnostics=0`；忽略 `NoNet` / `NONET` keyword 命名差异时，BRD `NetVias` 坐标和层跨度与标准输出为 `27914/27914` 一致。
- 修正 `<CASE_ROOT>/AX-small` 驱动的 BRD padstack / component layer 对齐：BRD parser `0.1.6` / BRD JSON schema `0.5.0` 新增 0x1C padstack component 几何表；Semantic parser 更新到 `0.7.8`，会用 padstack component 类型恢复圆形 U1201 BGA pad，用 REF_DES 内层 subclass 恢复 `COMP_L2`、`COMP_L3`、`COMP_L5`、`COMP_L7`、`COMP_L8`、`COMP_L9`，并把 POB/GND 偏心 slot via 的旋转预烘到 ViaList polygon / `RectCutCorner` shape，避免依赖 `NetVias` instance rotation。Semantic JSON schema 保持 `0.7.1`。
- 验证 `<CASE_ROOT>/AX-small`：BRD 生成的 AuroraDB 为 `layers=10`、`components=2176`、`pins=8589`、`pads=8589`、`vias=27904`、`via_templates=153`、`diagnostics=0`；`LayerNameIDs` 包含 `COMP_TOP`、`COMP_BOTTOM`、`COMP_L2`、`COMP_L3`、`COMP_L5`、`COMP_L7`、`COMP_L8`、`COMP_L9`，U1201 footprint pad template 为 `Circle 0 0 0.33`，5 个 POB/GND slot via template 的 barrel/pad shape 和 10 个对应 `NetVias` 的 `rotation=0` 与标准 AuroraDB 对齐。
- 新增 Altium Designer `.PcbDoc` source parser 初版：`crates/altium_parser/` 提供 Rust CFB / PCB stream 解析核心、CLI 和 PyO3 native module，`sources/altium/` 提供 Python 集成层、Pydantic model 和 schema helper；`inspect`、`dump`、`schema`、`convert`、`semantic` 和 pipeline 现在接受 `--format altium` / `--from altium`。
- Altium parser `0.1.0` / Altium JSON schema `0.1.0` 会解析 `.PcbDoc` 二进制容器中的 `FileHeader`、`Board6`、`Nets6`、`Classes6`、`Rules6`、`Components6`、`Pads6`、`Vias6`、`Tracks6`、`Arcs6`、`Fills6`、`Regions6`、`ShapeBasedRegions6`、`Polygons6`、`Texts6` 和 `WideStrings6`。新增 `Altium -> SemanticBoard` adapter，会映射铜层、net、component/footprint、pad/pin、via template、via、trace/arc/fill/region/polygon primitive 和 board outline；Semantic parser 更新到 `0.7.9`，Semantic JSON schema 更新到 `0.7.2`，枚举新增 `source_format=altium`。
- 使用 `examples/altium_cases/VR.PcbDoc` 验证：source summary 为 `layers=98`、`nets=404`、`components=494`、`pads=7124`、`vias=1123`、`tracks=26872`、`arcs=1213`、`regions=60`、`polygons=136`、`diagnostics=0`；Semantic summary 为 `layers=32`、`nets=405`、`components=494`、`footprints=48`、`pins=2176`、`pads=7124`、`vias=1123`、`primitives=28284`、`diagnostics=0`。
- 使用 `examples/altium_cases/XC7Z020CLG400-AD9).PcbDoc` 验证：source summary 为 `layers=98`、`nets=302`、`components=276`、`pads=1684`、`vias=1576`、`tracks=13915`、`arcs=110`、`regions=22`、`polygons=37`、`diagnostics=1`；Semantic summary 为 `layers=32`、`nets=303`、`components=276`、`footprints=26`、`pins=1676`、`pads=1684`、`vias=1576`、`primitives=14115`、`diagnostics=1`。唯一 diagnostic 是 `ShapeBasedRegions6` 尾部读取失败，主对象流仍可解析并转换。
- 修正 `<CASE_ROOT>/AX-small` 驱动的 BRD component pad footprint 旋转：BRD adapter 现在区分 footprint-local `PartPad` 旋转、layout 绝对 pad 旋转和 component-pad `NetVias` instance 旋转，J2801 / J4802 的长方形 pad 与 Q4008 的多边形 pad 不再额外叠加 component rotation；POB 偏心 oblong polygon 会预旋到 footprint-local shape，并把 `PartPad Location` 锚定到 drill center。Semantic parser 更新到 `0.7.10`，BRD parser / BRD JSON schema 不变，Semantic JSON schema 保持 `0.7.2`。
- 验证 `<CASE_ROOT>/AX-small`：BRD 生成的 AuroraDB 仍为 `layers=10`、`components=2176`、`pins=8589`、`pads=8589`、`vias=27904`、`via_templates=153`、`diagnostics=0`；J2801、J4802 和 Q4008 对应 `PartPad` rotation 为 `0`，J4802 POB footprint pad template / location 与标准输出对齐，component-pad `NetVias` rotation 仍为 `0`。
- 修正 `<CASE_ROOT>/AX-small` 驱动的 ALG component layer 和 component pad 选择：ALG semantic adapter 现在按 pin regular pad 层、padstack 跨层范围和金属层顺序推断 component placement layer，允许输出 `COMP_L2` 等内层 component layer；AuroraDB parts exporter 选择 component footprint pad 时优先匹配 component 的实际金属层，并把 ALG oblong pad 映射为 `RoundedRectangle`。Semantic parser 更新到 `0.7.11`，ALG parser / ALG JSON schema 不变，Semantic JSON schema 保持 `0.7.2`。
- 验证 `<CASE_ROOT>/AX-small` ALG 转换：Semantic summary 为 `layers=21`、`components=2176`、`pins=8589`、`pads=9014`、`vias=27904`、`diagnostics=0`；AuroraDB `parts=244`、`footprints=130`，`COMP_*` pin 分布与标准输出一致：`COMP_TOP=4807`、`COMP_BOTTOM=3644`、`COMP_L2=12`、`COMP_L3=2`、`COMP_L5=14`、`COMP_L7=74`、`COMP_L8=24`、`COMP_L9=12`。
- 优化 `<CASE_ROOT>/AX-small` ALG 语义转换性能：避免 component 到 pin 的重复全表扫描，ALG polygon / void segment 使用轻量 geometry payload，connectivity edge 使用跳过验证的内部构造路径。该性能优化本身生成的 AuroraDB `layout.db` / `parts.db` 与优化前一致，ALG parser / ALG JSON schema / Semantic JSON schema 不变。
- 验证 `<CASE_ROOT>/AX-small` ALG 转换：`from_alg(..., build_connectivity=True)` cProfile 耗时从约 `8.42s` 降到约 `7.17s`；端到端转换中 semantic build 阶段为 `5.739s`。
- 修正 `<CASE_ROOT>/AX-small` 驱动的 ALG component pad contour 解析：ALG full-geometry 中 `LINE` / `ARC` pad 轮廓会先按 record group 合并，并优先回退到同一 padstack/layer 的简单 pad 定义，不再把 `GRAPHIC_DATA_3/4` 的绝对端点坐标当作 pad 宽高。Semantic parser 更新到 `0.7.12`，ALG parser / ALG JSON schema 不变，Semantic JSON schema 保持 `0.7.2`。
- 验证 `<CASE_ROOT>/AX-small`：Semantic summary 为 `layers=21`、`components=2176`、`pins=8589`、`pads=8679`、`vias=27904`、`primitives=59512`、`diagnostics=0`；L9 `PAD_DIFFERENT_L1` footprint pad template 从错误的 `72.7502 x 11.2266` / `72.8378 x 11.139` 恢复为标准 AuroraDB 的 `Rectangle 0 0 0.15 0.15`，对应 `PartPad` local rotation 为 `0`；`COMP_L9` component placement 坐标和 pin 分布保持与标准输出一致。
- 新增 Rust AEDB `.def` 逆向解析和写回核心 `crates/aedb_parser/`，提供 CLI 和 PyO3 native module 骨架；当前覆盖 length-prefixed text record / binary gap 扫描、AEDB `$begin` / `$end` DSL block summary，以及 source-fidelity `.def` roundtrip writer。默认 `sources/aedb/` PyEDB 解析路径和 AEDB JSON schema 不变。
- 验证 `examples/edb_cases/{fpc,kb,mb}.def`：`cargo test --manifest-path crates/aedb_parser/Cargo.toml`、`cargo check --manifest-path crates/aedb_parser/Cargo.toml` 和 `cargo build --manifest-path crates/aedb_parser/Cargo.toml` 通过；三个公开样例均为 `def_version=12.1`、`encrypted=false`、`diagnostics=0`，roundtrip 写回与输入 byte-identical。
- Python CLI 新增 opt-in `--aedb-backend def-binary`，用于 `inspect source --format aedb` 和 `dump source-json --format aedb` 调用 Rust `.def` parser；默认 `--aedb-backend pyedb` 和 `sources/aedb/parser.py` 行为不变，`def-binary` 用于 Semantic JSON 或转换时会明确报错。新增独立 `AEDBDefBinaryLayout` payload，既有 `AEDBLayout` JSON schema 不变。
- 验证：`uv run python -m compileall sources/aedb cli pipeline` 通过；`main.py inspect source --format aedb examples/edb_cases/fpc.def --aedb-backend def-binary --json` 和 `main.py dump source-json --format aedb examples/edb_cases/fpc.def --aedb-backend def-binary` 通过。
- AEDB DEF binary parser 更新到 `0.4.0`，`AEDBDefBinaryLayout` schema 更新到 `0.4.0`；Rust payload 新增 `domain.binary_geometry`，从 `.def` 二进制 via tail 和 raw-point path 记录中抽取 via 坐标计数、匿名/命名 path 计数、Line/Larc segment 计数和 path width 统计。既有 PyEDB `AEDBLayout` schema 不变。
- Rust CLI `compare-auroradb <board.def> --auroradb <dir>` 继续用于将 `.def` 抽取结果与标准 AuroraDB 目录做对照；`examples/edb_cases/{fpc,kb,mb}` 当前达到金属层顺序、ViaList 名称、电气 net 名称、component placement 名称和 part-name candidates 对照通过，并新增二进制 via/path 与 AuroraDB `NetVias`、`Line`、`Larc` 的 warning 级计数对照。剩余差异集中在 component pad-derived via、Location pad geometry、polygon/void payload 和 layer/net 精确归属。
- 修正 `<CASE_ROOT>/SS-small` 驱动的 Allegro ALG / BRD 到 AuroraDB 对齐问题：ALG adapter 将空网统一为 `NONET`；BRD adapter 将未命名 BRD nets 合并到 `NONET`，物理铜层选择改为优先识别精确 `TOP ... BOTTOM` stackup layer list，并且只会采用 BRD 自身内嵌且与当前铜层名完全一致的 `DBPartitionAttachment` stackup，旧的/mismatch cross-section 会被忽略。缺失可用物性 stackup 时，BRD adapter 会按当前铜层顺序生成 `D0..Dn` 介质占位层，而不依赖同目录 extracta `.alg`。REF_DES `FIELD -> TEXT_WRAPPER` 链和 `ASSEMBLY_` / `DISPLAY_` 自定义层对用于恢复内层 component placement。BRD parser `0.1.7` 修正 pre-V172 `0x0C PIN_DEF` 记录步长，BRD JSON schema 保持 `0.5.0`；Semantic parser 更新到 `0.7.13`，Semantic JSON schema 保持 `0.7.2`。
- 验证 `<CASE_ROOT>/SS-small`：`<OUTPUT_ROOT>/ss-small-{alg,brd}` 与标准 AuroraDB 对比均为 `units=mm`、`metal_layers=10`、`layers=17`、`nets=585`、`components=1283`、`netpins=4561`、`netvias=17310`、`net_geometries=23203`、`parts=164`、`footprints=88`、`via_templates=8`；net set、component layer distribution、按 `layer|net` 聚合的 NetGeom、按 net 聚合的 NetVia 和 NetPin diff 均为 `0`。BRD-only 转换在无同目录 `.alg` 时生成的 `stackup.dat` 层结构与标准一致：`SOLDERMASK_TOP/TOP/D0/.../D8/BOTTOM/SOLDERMASK_BOTTOM`；该 BRD 内嵌 `DBPartitionAttachment` cross-section 是旧 8 层数据，因此物性厚度/材料仍使用默认值而非旧数据。`shape_count` 因 symbol 规范化仍不同：标准 `167`、ALG `137`、BRD `121`。

## 1.0.43

- 新增 Cadence Allegro BRD source parser 初版：`crates/brd_parser/` 提供 Rust 解析核心、CLI 和 PyO3 native module，`sources/brd/` 提供 Python 集成层、Pydantic model 和可生成 JSON schema；`inspect`、`dump`、`schema`、`convert`、`semantic` 和 pipeline 现在接受 `--format brd` / `--from brd`。
- BRD parser `0.1.2` / BRD JSON schema `0.1.0` 会解析 BRD header、字符串表、layer list、net、padstack、footprint、placed pad、via、track、shape、text 和 block summary。新 JSON 输出字段为 BRD 专属 source JSON；既有 AEDB、AuroraDB、ODB++ 和 Semantic JSON schema 不变。
- 新增 `BRD -> SemanticBoard` 初版 adapter，当前会把 BRD 物理 ETCH layer、net、placed pad bbox、component / pin / footprint、padstack via template 和 via 映射进 Semantic；track / shape segment 链仍保留在 BRD source JSON 中并通过 diagnostic 标记后续补齐。Semantic parser 更新到 `0.7.3`，Semantic JSON schema 保持 `0.7.0`。
- 使用公开样本 `examples/LPDDR4_Demo.brd` 验证：识别为 `V_174`、单位 `mils`，Rust parser summary 为 `objects=95671/109165`、`strings=4108`、`layers=6`、`nets=605`、`padstacks=143`、`footprints=43`、`placed_pads=3140`、`vias=1501`、`tracks=4692`、`shapes=1481`、`texts=11640`、`diagnostics=0`；CLI `inspect source --format brd --json` 和 `schema --format brd` 均通过。
- 修正 BRD 多版本二进制解析的版本条件和 V18.1 font table 步长，使 `<BRD_CASES>/DemoCase_LPDDR4_{17.2,22.1,23.1,24.1,25.1}.brd` 这一组从原始 17.2 到不同 Allegro 保存版本均可零诊断解析；共同关键计数为 `layers=7`、`nets=489`、`padstacks=43`、`footprints=41`、`placed_pads=2963`、`vias=1117`、`tracks=1734`、`shapes=2675`、`texts=14652`。BRD JSON schema 不变，预期输出差异为 V17.2/V18.1 版本不再提前停止，source JSON 中可获得完整已建模对象集合。
- 追加验证 `<BRD_CASES>/PA-series_{17.2,22.1,23.1,24.1,25.1}.brd` 这一组同一设计的不同 Allegro 保存版本：五个版本均为 `diagnostics=0`，共同关键计数为 `layers=12`、`nets=1438`、`padstacks=158`、`footprints=139`、`placed_pads=8951`、`vias=16017`、`tracks=7539`、`shapes=4123`、`texts=20996`。BRD JSON schema 不变。
- 追加验证 `<BRD_CASES>/AX-series_{17.4,22.1,23.1,24.1,25.1}.brd` 这一组同一设计的不同 Allegro 保存版本：五个版本均为 `diagnostics=0`，共同关键计数为 `layers=12`、`nets=1771`、`padstacks=153`、`footprints=156`、`placed_pads=12322`、`vias=27902`、`tracks=15190`、`shapes=12689`、`texts=29716`。BRD JSON schema 不变。
- 使用 `<BRD_CASES>/AX-series_25.1.brd` 验证 BRD 到 AuroraDB 输出：Semantic summary 为 `layers=10`、`nets=1771`、`components=2176`、`footprints=156`、`pins=8591`、`pads=8591`、`vias=27902`、`via_templates=153`，AuroraDB 输出包含 `10` 个 layer 文件、`2176` 个 component placement、`8591` 个 pad `NetGeom` 和 `27902` 个 `NetVias.Via`。预期输出差异为 BRD→AuroraDB 不再只导出 layer/net 空壳；Semantic JSON schema 不变。
- 修正 V18.1 `SI_MODEL` 字符串长度少报时的本地重同步，使 `<BRD_CASES>/S5000-series_{17.4,22.1,23.1,24.1,25.1}.brd` 这一组同一设计的不同 Allegro 保存版本均可零诊断解析；共同关键计数为 `layers=6`、`nets=7233`、`padstacks=163`、`footprints=146`、`placed_pads=43944`、`vias=31318`、`tracks=40514`、`shapes=24145`、`texts=162630`。BRD JSON schema 不变，预期输出差异为 V18.1/S5000 25.1 不再在 SI model 数据中提前停止。
- 删除历史 C++ BRD reference 目录 `examples/brd_parser`；后续 BRD 解析维护入口为 `crates/brd_parser/` 和 `sources/brd/`。该仓库结构清理不改变 BRD JSON schema 或 parser 输出。
- 新增 Cadence Allegro extracta ALG source parser 初版：`crates/alg_parser/` 提供 Rust 流式解析核心、CLI 和 PyO3 native module，`sources/alg/` 提供 Python 集成层、Pydantic model 和可生成 JSON schema；`inspect`、`dump`、`schema`、`convert`、`semantic` 和 pipeline 现在接受 `--format alg` / `--from alg`。
- ALG parser `0.1.0` / ALG JSON schema `0.1.0` 会解析 extracta 文本中的 board、layer、component、component pin、logical pin、composite pad、full geometry pad/via/track/outline、net 和 symbol 数据。新增 JSON 输出为 ALG 专属 source JSON；Semantic schema 仅新增 `source_format=alg` 枚举值并更新到 `0.7.1`。
- 新增 `ALG -> SemanticBoard -> AuroraDB` adapter，将 ALG conductor layer、net、component/package、pin、component pad、via template、via、trace/arc/rectangle primitive 和 board extents 映射到统一语义对象；AuroraDB target 对 `alg` 启用与 ODB++ 相同的 component footprint pad 优先策略和 bottom-side flip 规则，缺失铜皮 pad 的默认兜底尺寸会按源单位从 mil 换算。Semantic parser 更新到 `0.7.4`。
- 使用 `<ALG_CASES>/DemoCase_LPDDR4.alg` 验证 ALG 到 AuroraDB 输出：source summary 为 `layers=17`、`metal_layers=8`、`components=293`、`pins=1710`、`pads=1803`、`vias=1117`、`tracks=18364`、`nets=334`、`diagnostics=0`；Semantic summary 为 `layers=8`、`nets=334`、`components=293`、`footprints=27`、`pins=1710`、`pads=1745`、`vias=1117`、`primitives=18364`、`diagnostics=0`。
- 使用 `<ALG_CASES>/AX-series.alg`、`<ALG_CASES>/PA-series.alg` 和 `<ALG_CASES>/S5000-series.alg` 验证大型 ALG 到 AuroraDB 输出：AX 为 `layers=10`、`nets=1277`、`components=2176`、`pins=8589`、`pads=9014`、`vias=27902`、`primitives=411081`、`diagnostics=0`；PA 为 `layers=8`、`nets=935`、`components=1652`、`pins=6146`、`pads=6394`、`vias=16017`、`primitives=159378`，并有 `272` 条 info 级默认 pad geometry 诊断用于标记 extracta 中缺失铜皮 pad 的逻辑 pin；S5000 为 `layers=14`、`nets=6206`、`components=6888`、`pins=35289`、`pads=45195`、`vias=31318`、`primitives=661365`、`diagnostics=0`。
- 修正 `<ALG_CASES>/AX-series.alg` 和 `<BRD_CASES>/AX-series_25.1.brd` 的 Allegro 铜皮导出：ALG parser `0.1.1` / ALG JSON schema `0.2.0` 在 track 记录中保留 `GRAPHIC_DATA_10` 几何角色，BRD parser `0.1.4` / BRD JSON schema `0.3.0` 新增 0x34 keepout source model；Semantic parser `0.7.5` 会把 `SHAPE` segment chain 聚合为 polygon，把 ALG `VOID` 与 BRD keepout 聚合为 `PolygonHole`，并允许 Allegro `SHAPE` 的 2 点退化 polygon。Semantic JSON schema 保持 `0.7.1`。使用 AX 对照验证：ALG 输出 `SHAPE polygon=8415`、`PolygonHole=352`、`Line=51024`、`Larc=72`；BRD 25.1 输出 `SymbolID -1=8415`、`PolygonHole=352`、`Line=51016`、`Larc=72`。

## 1.0.42

- 集成 ODB++ parser `0.6.3`、Semantic parser `0.7.1` 和 Semantic JSON schema `0.7.0`；AEDB parser 保持 `0.4.56`，AEDB JSON schema 保持 `0.5.0`，ODB++ JSON schema 保持 `0.6.0`。
- Semantic 主要 `geometry` 字段收敛为 typed hint model：`footprints.geometry`、`via_templates.geometry`、`pads.geometry`、`vias.geometry`、`primitives.geometry` 和 `board_outline` 现在有显式 schema，同时保留 extra metadata 逃生口；预期 Semantic JSON schema 结构变化，但 JSON 输出字段名保持兼容。
- 修正 Python ODB++ parser 集成层的 Rust CLI binary 自动定位路径，使其能从项目根目录找到 `crates/odbpp_parser/target/release/odbpp_parser(.exe)`；不改变 ODB++ JSON schema。
- Rust archive reader 在 `--summary-only`、显式 `--step` 和默认 auto-step details 路径中会跳过非必要明细文件；默认 details 现在先通过 summary pass 选 step，再只读取选中 step 的明细文件。
- Rust ODB++ archive reader 现在默认跳过超过 512 MiB 的单个 entry，并写入 non-fatal diagnostic；新增 tokenizer、matrix、feature、net 和 archive size-limit 单元测试，不改变 ODB++ JSON schema。
- 测试体系补齐 pytest/golden fixture 基座，并新增 GitHub Actions 工作流，固化 `ruff format --check`、`ruff check`、Python compile、`unittest`、`pytest` 和 `cargo test`。
- 批量移除项目 Markdown 文档文件头 UTF-8 BOM，避免普通 UTF-8 工具链读取失败；不改变文档正文内容。
- AuroraDB exporter 继续拆分 pass 边界：新增 `targets/auroradb/direct.py` 承载 direct AuroraDB builder 状态，`layout.py` 承载 `layout.db` / `design.layout` 写出，`parts.py` 承载 `parts.db` / `design.part` 写出和 part/footprint plan，`geometry.py` 承载 shape / via / trace / polygon geometry command/payload，`formatting.py` 承载单位换算、数值解析、坐标解析和旋转格式化，`names.py` 承载命名规范化和 AAF quoting，`stackup.py` 承载 stackup planning 与 `stackup.dat` / `stackup.json` serialization；该内部重构不改变生成文件格式。
- 修正 AEDB -> AuroraDB 弧高方向回归：direct exporter 现在按 AEDB raw-point / arc-height 约定将 `arc_height < 0` 写为 AuroraDB `CCW=Y`，并优先尊重显式 `is_ccw` / `clockwise`；Semantic / AEDB / ODB++ JSON schema 不变。预期输出差异为 AEDB trace `Larc`、polygon/void `Parc` 和 polygon pad shape arc 的方向标记恢复正确。
- 统一 CLI 和流程日志风格：命令启动、主要阶段、长耗时 heartbeat 和进度日志现在使用 `Run started` / `Start` / `Progress` / `Done` / `Run completed` 状态词；启动横幅包含 `Aurora Translator` 项目名，主要阶段恢复星号横幅，日志等级恢复为完整 `[INFO]` / `[ERROR]` 形式，并移除重复的日志文件提示；不改变 JSON schema 或转换输出。
- Python 代码格式化标准化为 Ruff formatter：`pyproject.toml` 现在显式保存 Ruff formatter 配置，提交前运行 `uv run ruff format .`，只读检查运行 `uv run ruff format --check .`。
- 使用私有 ODB++ 样本 `<CASE_ROOT>/sample.tgz` 验证：Semantic summary 为 `layers=32`、`components=682`、`pads=24472`、`vias=5466`、`primitives=111009`、`diagnostics=2`，并成功写出 AuroraDB 和 coverage report。
- 使用私有 AEDB 样本 `<CASE_ROOT>/sample.aedb` 验证：minimal/full 两条 AEDB -> AuroraDB 路径均为 `layers=21`、`components=282`、`pads=1432`、`vias=1160`、`primitives=2355`、`diagnostics=2`，14 个 AuroraDB 输出文件 SHA-256 完全一致。

## 1.0.41

- 集成 AEDB parser `0.4.56` 和 Semantic parser `0.6.38`；AuroraDB parser、ODB++ parser 和所有 JSON schema 版本保持不变。
- AEDB source model 和 Semantic model 移除面向 AuroraDB 的 Pydantic `PrivateAttr` 运行时 `NetGeom` 缓存；direct AuroraDB exporter 现在只从显式 `geometry.center_line`、`geometry.raw_points`、`geometry.arcs` 和 `geometry.voids` 生成 trace / polygon 几何。
- `auroradb-minimal` profile 现在保留 path `center_line`、polygon `raw_points` 和 void raw geometry，使 AEDB -> SemanticBoard -> AuroraDB 不再依赖不可序列化隐藏状态；JSON schema 不变，但 minimal profile 的源模型内容会比 `1.0.40` 更完整。
- CLI 入口和 source loader 改为按命令/格式懒加载，`schema`、`inspect aaf`、`convert --help` 等非 AEDB 路径不再提前加载 PyEDB；新增 `tests/` 架构护栏，覆盖私有缓存移除、Semantic JSON 明文几何、CLI lazy import 和 direct trace exporter。
- 新增 `targets/auroradb/plan.py`，集中构建 AuroraDB 导出所需的板级索引，为后续拆分 direct layout / parts / geometry exporter 降低耦合；`ruff` 从运行依赖移到 dev dependency group。

## 1.0.40

- 集成 Semantic parser `0.6.37`；AEDB parser、AuroraDB parser、ODB++ parser 和所有 JSON schema 版本保持不变。
- ODB++ -> Semantic 现在会把标准 `rect` / `rect...xr` / `oval` 这类有方向 symbol 的长轴规范化到 Semantic shape 的 `+X` 方向；当源 symbol 自身是纵向定义时，会把该 `90 deg` symbol 轴向折算进 pad feature rotation。
- Via template refinement 计算 matched pad / antipad 相对旋转时，会根据 shape 几何判断是否存在 `180 deg` 半周对称；对中心在原点的 circle / rectangle / rounded-rectangle 以及可判定半周对称的 polygon，按 `180 deg` 等价归一相对角，避免 slot start/end 方向或 symbol 宽高基准导致视觉等价 pad 写出 `180 deg` 差值。
- 该修复只依据 source symbol 尺寸和 shape 几何，不按 layer、refdes 或坐标做特殊处理；JSON schema 不变。预期输出差异集中在 ODB++ slotted via 的 `SemanticPad.geometry.rotation`、`via_templates.geometry.layer_pad_rotations` 和 AuroraDB `layout.db` 的 `ViaList` layer row rotation。
- 使用私有 ODB++ slot-via 回归样本验证：Semantic summary 为 `components=682`、`via_templates=66`、`vias=5466`；相关 `r650` / `r500` / `r450` slot via 的 `TOP`、`L2`、`BOTTOM` layer pad rotation 均为 `0 Y`；`PartPad -> PinList` 一致性问题为 `0`。

## 1.0.39

- 集成 Semantic parser `0.6.36`；AEDB parser、AuroraDB parser、ODB++ parser 和所有 JSON schema 版本保持不变。
- 撤销 ODB++ slotted via matched pad 相对旋转中的 shape-axis 扣除逻辑：AuroraDB 会按 `Rectangle` / `RoundedRectangle` 的 `width` / `height` 定义绘制 shape，再叠加 `ViaList` layer row rotation 和 `NetVias.Via` instance rotation，因此 Semantic 只应保存 `pad_rotation - via_rotation`。
- 该修复使 connector pin 位置的 TOP oval via pad 写回必要的 `-90 Y` layer rotation，避免 v1.0.38 输出相差 `90 deg`；JSON schema 不变。
- 使用私有 ODB++ slot-via 回归样本验证：Semantic summary 为 `components=682`、`via_templates=69`、`vias=5466`；目标 connector 位置的 `r650` slot via `TOP` layer pad rotation 为 `-90 Y`，`L2` / `BOTTOM` 为 `0 Y`；`PartPad -> PinList` 一致性问题为 `0`。

## 1.0.38

- 集成 Semantic parser `0.6.35`；AEDB parser、AuroraDB parser、ODB++ parser 和所有 JSON schema 版本保持不变。
- 修正 ODB++ slotted via 的 matched layer pad 相对旋转：当 slot barrel 和 matched oval / rounded-rectangle pad 的默认长轴方向不一致时，`via_templates.geometry.layer_pad_rotations` 会先消除 shape 自身宽高轴差，再计算相对角。
- 该修复会让 connector pin 位置上 TOP oval via pad 不再额外偏转 `90 deg`；圆形 via 和无方向 barrel 不受影响，JSON schema 不变。
- 使用私有 ODB++ slot-via 回归样本验证：Semantic summary 为 `components=682`、`via_templates=69`、`vias=5466`；目标 connector 位置的 `r650` slot via `TOP` layer pad rotation 从 `-90 Y` 修正为 `0 Y`；`PartPad -> PinList` 一致性问题为 `0`。

## 1.0.37

- 集成 Semantic parser `0.6.34`；AEDB parser、AuroraDB parser、ODB++ parser 和所有 JSON schema 版本保持不变。
- 修正 ODB++ slotted via 的旋转基准：`SemanticVia.geometry.rotation` 现在按 ODB++ 顺时针正角、相对 shape `+X` 轴保存，slot barrel `RoundedRectangle` 也改为 `total_length x width`，避免 AuroraDB `NetVias.Via` 和 `ViaList` layer pad 在导出时整体偏转 `90 deg`。
- `via_templates.geometry.layer_pad_rotations` 会基于新的 slot via instance 角度重新计算；该修复影响 ODB++ slot via barrel shape、via instance rotation 和匹配 pad/antipad 的相对 rotation，不改变 JSON schema。
- 使用私有 ODB++ slot-via 回归样本验证：Semantic summary 为 `components=682`、`via_templates=69`、`vias=5466`；`PartPad -> PinList` 一致性问题为 `0`。

## 1.0.36

- Semantic parser 保持 `0.6.33`；AEDB parser、AuroraDB parser、ODB++ parser 和所有 JSON schema 版本保持不变。
- 修正 ODB++ -> Semantic -> AuroraDB `ViaList` layer pad rotation 输出：Semantic 中继续按 ODB++ 规格保存 clockwise-positive 相对角，但写入 AuroraDB `CCW=Y` 字段时转换为 counter-clockwise 数值。
- 该修复只影响 AuroraDB via template layer pad / antipad 的非零 rotation 符号，不改变 component placement、net via instance location、Semantic JSON 字段或 ODB++ source JSON。
- 使用私有 ODB++ slot-via 回归样本验证：Semantic summary 仍为 `components=682`、`via_templates=69`、`vias=5466`；`PartPad -> PinList` 一致性问题为 `0`。

## 1.0.35

- Semantic parser 保持 `0.6.33`；AEDB parser 保持 `0.4.55`，AEDB JSON schema 保持 `0.5.0`，AuroraDB parser 保持 `0.2.13`，ODB++ parser 和 JSON schema 版本保持不变。
- AEDB -> AuroraDB 导出现在会把多层 component pin padstack 额外写成同 net、同坐标的 `NetVias.Via`，使 through-hole connector pin 能在内层信号层显示为跨层连接。
- 单层 SMD component padstack 不会写成 via；该修复只作用于引用多层 via template 的 component pin/pad。
- 修正 ODB++ -> AuroraDB `ViaList` layer pad rotation 输出：component-connected slot via 的 layer pad 相对角现在与 ODB++ component / pad 导出一样保持顺时针正角约定，不再额外反号，避免 connector pin 连接的 slot via pad 和 GND slot via pad 旋转反向。
- 新增 ODB++ -> Semantic 详细映射文档，整理对象映射、via template 细化、component/pad/via 旋转公式和 AuroraDB target 边界。
- 使用私有 AEDB through-hole connector 回归样本验证：内层 trace 的 connector-pin 端点会新增同坐标 `NetVias.Via`；相关通孔 component pin 端点会获得对应 net via。
- 使用私有 ODB++ slot-via 回归样本验证：多个同坐标 pin-connected slot via 均保留匹配到的真实 pad shape；相关 slot via template layer pad rotation 输出为 `-90 Y`，`PartPad -> PinList` 一致性问题为 `0`。
- JSON schema 版本未变化；AuroraDB `layout.db` 的 `ViaList` 会包含被通孔 component pin 使用的 padstack template，`NetVias` 数量会增加。

## 1.0.34

- 集成 Semantic parser `0.6.33`；AEDB parser 保持 `0.4.55`，AEDB JSON schema 保持 `0.5.0`，AuroraDB parser 保持 `0.2.13`，ODB++ parser 和 JSON schema 版本保持不变。
- AEDB -> SemanticBoard 的 via template layer pads 现在按 stackup 物理顺序保存，不再按 layer name 字符串排序，避免 via layer 顺序与 `LayerStackup.MetalLayers` 不一致。
- AuroraDB 导出 `ViaList` 时只写出实际被 exported net via 使用的 via template，不再把 component/SMD padstack definition 写成未使用的 via template，避免单层 component padstack 被误判为 via 缺层。
- 使用私有 AEDB via-layer 样本验证：source via instance 为 `5806`，全部为 TOP 到 BOTTOM 全层跨度；AuroraDB `NetVias` 为 `5806`，`ViaList` 从 `99` 个 template 精简为 `7` 个被使用的 via template，且每个被使用 template 都包含 `12` 个 metal layer。
- JSON schema 版本未变化；Semantic JSON 中 AEDB `via_templates.layer_pads` 的顺序会变化，AuroraDB `layout.db` 中 `ViaList` template 数量和 layer pad 顺序会变化。

## 1.0.33

- 集成 Semantic parser `0.6.32`；AEDB parser 保持 `0.4.55`，AEDB JSON schema 保持 `0.5.0`，AuroraDB parser 保持 `0.2.13`，ODB++ parser 和 JSON schema 版本保持不变。
- ODB++ via template pad 匹配候选现在先按与 via 中心的距离排序，再在同距离下优先 component pad，避免容差匹配时用较远的 component pad 覆盖同坐标真实 via pad。
- AuroraDB `ViaList` layer pad rotation 现在按字段自带的 `CCW` 语义输出：ODB++ clockwise 相对角会转换成 `CCW=Y` 下的 counter-clockwise 角度，而不是复用普通 location rotation。
- 使用私有 ODB++ via-pad rotation 样本验证：Semantic summary 为 `shapes=253`、`via_templates=69`、`vias=5466`；`r650` slot via template 的 `TOP` pad 保持真实 rounded-rectangle pad，`L2` / `BOTTOM` pad rotation 输出为 `90 Y`，slot via instance rotation 保持 `-180` / `0`；`PartPad -> PinList` 一致性问题为 `0`。
- JSON schema 版本未变化；AuroraDB `layout.db` / `aaf/design.layout` 中非零 via template layer pad rotation 的符号会按 `CCW=Y` 语义变化。

## 1.0.32

- 集成 Semantic parser `0.6.31`；AEDB parser 保持 `0.4.55`，AEDB JSON schema 保持 `0.5.0`，AuroraDB parser 保持 `0.2.13`，ODB++ parser 和 JSON schema 版本保持不变。
- ODB++ via template 的 pad 匹配现在允许同 net / 同 layer 下 `0.001` 源单位内的微小坐标偏差，修复 component pin 连接的 drill/via 因 pin pad 与 drill 中心存在微小偏移而丢失 TOP layer pad 的问题。
- 当 via 与 component pad 匹配时，现在优先使用 component pad shape，并在 refined via template 中记录 layer pad 相对 via instance 的 rotation；AuroraDB direct 和 AAF 输出都会写出每层 via pad rotation。
- 使用私有 ODB++ component-connected via-pad 样本验证：Semantic summary 为 `shapes=253`、`via_templates=69`、`vias=5466`；slot via template 的 `TOP` pad 使用真实 rounded-rectangle pad，`L2` / `BOTTOM` pad rotation 为 `-90`，slot via instance rotation 保持 `-180` / `0`；`PartPad -> PinList` 一致性问题为 `0`。
- JSON schema 版本未变化；Semantic JSON 的 `via_templates.geometry.layer_pad_rotations` 可能新增旋转提示，AuroraDB `layout.db` / `aaf/design.layout` 的 via template layer pad shape 和 rotation 会变化。

## 1.0.31

- 集成 Semantic parser `0.6.30`；AEDB parser 保持 `0.4.55`，AEDB JSON schema 保持 `0.5.0`，AuroraDB parser 保持 `0.2.13`，ODB++ parser 和 JSON schema 版本保持不变。
- AEDB -> SemanticBoard 现在会把 `Round45`、`Round90`、`Bullet` 和 `NSidedPolygon` pad geometry 构造成 `SemanticShape(kind="polygon")`，避免这些参数化 AEDB pad shape 在 AuroraDB footprint pad/template 输出中被跳过或退化为 circle。
- `NSidedPolygon` 会按 `Size` 和 `NumSides` 生成 regular polygon；`Bullet` 会按 `XSize`、`YSize`、`CornerRadius` 生成带 arc 顶点的 polygon；`Round45` / `Round90` 会按 `Inner`、`ChannelWidth`、`IsolationGap` 生成对应方向的 thermal polygon。
- JSON schema 版本未变化；AEDB source JSON 字段不变。预期输出差异集中在 Semantic JSON 的 `shapes` / `via_templates.layer_pads` 和 AuroraDB `parts.db` / `layout.db` 中相关 pad shape 由缺失或旧类型变为 `Polygon`。

## 1.0.30

- 集成 Semantic parser `0.6.29`；AEDB parser 保持 `0.4.55`，AuroraDB parser 保持 `0.2.13`，ODB++ parser 和 JSON schema 版本保持不变。
- ODB++ -> SemanticBoard 现在会把 drill 层带 net 的 `L` 线型钻孔转换为 slotted `SemanticVia`，barrel shape 使用 `RoundedRectangle`，并记录 via instance 旋转，补齐此前缺失的椭圆 via、via pad 和 via hole。
- ODB++ via template 的 pad/antipad 匹配改为在 component pad 生成后执行；匹配时优先使用普通 metal-layer pad，缺失时回退 component pad，使 component 绑定的 GND slot via pad 能使用真实 oval/rounded pad 尺寸。
- AuroraDB exporter 现在会把 Semantic via instance 的 rotation 写入 direct `layout.db` 和 AAF `layout add -net ... -via` 命令。
- `ODBPP_DRAWING` / drawing-only drill marker 仍按当前策略不翻译到 AuroraDB；本次只翻译真实 drill 层 net via/hole。
- 使用私有 ODB++ slot-via 样本验证：Semantic summary 为 `shapes=253`、`via_templates=14`、`vias=5466`；AuroraDB 输出包含 `4` 个 slot via template 和 `15` 个 slot via instance，其中 GND slot via 为 `10` 个；`PartPad -> PinList` 一致性问题为 `0`。
- JSON schema 版本未变化；Semantic JSON 会新增 slotted via 和 rounded-rectangle shape，AuroraDB `layout.db` / `aaf/design.layout` 会新增 slot via template、slot via instance 和必要的 via rotation。

## 1.0.29

- 集成 AEDB parser `0.4.55`、AEDB JSON schema `0.5.0` 和 Semantic parser `0.6.28`；AuroraDB parser 保持 `0.2.13`，ODB++ parser 和 JSON schema 版本保持不变。
- AEDB padstack definition 解析新增 polygonal pad 支持：当 `GetPadParametersValue()` 返回 `NoGeometry` 但 `GetPolygonalPadParameters()` 返回 polygon 时，会把顶点保存到 `PadPropertyModel.raw_points`。
- AEDB -> SemanticBoard 会将 polygonal pad 转换为 `SemanticShape(kind="polygon")`，AuroraDB `parts.db` 的 `FootPrintSymbol -> PadTemplate -> PartPad` 因此能输出 polygon 焊盘，避免 component placement 存在但 footprint 为空。
- 使用私有 AEDB component-gap 样本验证：source component count 和 AuroraDB component placement count 均为 `1642`；空 footprint 影响的 component 从 `720` 降为 `0`。
- 预期输出差异：AEDB JSON 的 pad property 新增 `raw_points`；Semantic JSON 的 `shapes` / `via_templates.layer_pads` 可能新增 polygon pad shape；AuroraDB `parts.db` 会补齐此前空缺的 polygon `PadTemplate` 和 `PartPad`。

## 1.0.28

- 集成 Semantic parser `0.6.27`；AEDB parser 保持 `0.4.54`，AuroraDB parser 保持 `0.2.13`，ODB++ parser 和 JSON schema 版本保持不变。
- ODB++ 标准 symbol 解析补齐 `s...` square、`di...` diamond、`rect...xr...` 圆角矩形，以及单边为 0 的退化 `oval...`，使 component pad、via matched pad 和 layout primitive 能获得稳定 `shape_id`。
- ODB++ -> AuroraDB footprint library 现在优先使用 component 绑定到真实 metal-layer feature pad 的几何作为 `PartPad` 模板；只有缺少可用 feature pad 时才回退 package pin marker，避免小器件 pin size 被 package marker 缩小。
- 当同一 source footprint 下存在不同 pad shape signature 时，会拆分 AuroraDB part/footprint variant，并通过 `EXPORT_FOOTPRINT` 保留导出 footprint 名称，避免 square/diamond 等不同焊盘形状互相覆盖。
- 使用私有 ODB++ 样本验证：Semantic summary 为 `components=682`、`pads=24472`、`vias=5451`、`via_templates=10`，AuroraDB `parts.db` 为 `94` 个 Part、`78` 个 FootPrintSymbol，`PartPad -> PinList` 一致性问题为 `0`。
- JSON schema 未变化；Semantic JSON 会新增此前未识别的 pad/shape 关系，AuroraDB `parts.db` / `aaf/design.part` 中 component pad 尺寸、diamond pad 和 oval/rounded pad 输出会变化。

## 1.0.27

- 集成 AEDB parser `0.4.54`；Semantic parser 保持 `0.6.26`，AuroraDB parser 保持 `0.2.13`，ODB++ parser 和 JSON schema 版本保持不变。
- AEDB -> AuroraDB direct conversion 在未请求 `--source-output` / `--semantic-output` 时会自动启用 `auroradb-minimal` 解析 profile，跳过 source/Semantic JSON 才需要的 path `center_line` / length / area 和 polygon `raw_points` / arcs / void model 存储，只保留 AuroraDB 输出需要的 bbox、width、基础归属字段和运行时私有 `NetGeom` 缓存。
- 新增 `--aedb-parse-profile auto|full|auroradb-minimal`；显式输出 AEDB JSON 或 Semantic JSON 时仍使用完整解析，显式 minimal 与中间 JSON 输出组合会报错。
- 使用私有 AEDB 回归样本验证：同版本 full profile 与 auto minimal profile 的 AuroraDB 输出 `14` 个文件 hash 完全一致。使用大型 AEDB 回归样本验证：同版本 full/minimal 输出 `40` 个文件 hash 完全一致，`Parse AEDB layout` 从 `74.937s` 降至 `40.576s`，`Serialize layout primitives` 从 `55.498s` 降至 `21.221s`。
- JSON schema 未变化；显式 source JSON / semantic JSON 仍保持完整 profile。AuroraDB 输出预期不变，性能变化集中在 AEDB path / polygon primitive 解析阶段。

## 1.0.26

- 集成 Semantic parser `0.6.26`；AEDB parser 保持 `0.4.53`，AuroraDB parser 保持 `0.2.13`，ODB++ parser 和 JSON schema 版本保持不变。
- 修正 ODB++ -> AuroraDB bottom-side component placement：来自 bottom component layer 的 component 现在会在 direct AuroraDB 和 AAF 输出中写入 `flipX`，使 package footprint pin 经过顺时针 rotation 与 local x-axis mirror 后对齐 ODB++ component pin 的绝对坐标。
- 修正缺少显式 component pin position 时的 ODB++ package fallback 坐标推导：bottom-side component 从 package pin 生成 placed pad 时会应用同一 local x-axis mirror，避免 fallback footprint/pad 坐标与 component placement 约定不一致。
- 使用私有 ODB++ bottom-side component 样本验证：AuroraDB component placement count 为 `1572`，bottom-side `flipX` placement count 为 `869`，抽检非对称 bottom package 的 source pin 与 AuroraDB 变换后 pin 最大误差为 `0 mil`。
- JSON schema 未变化；Semantic JSON 除版本 metadata 外，仅使用 package fallback 推导的 bottom-side pad 坐标可能变化；AuroraDB `layers/*.lyr` 和 `aaf/design.layout` 中的 bottom-side component placement 会新增 `FlipX=Y` / `-flipX`。

## 1.0.25

- 集成 AEDB parser `0.4.53`；Semantic parser 保持 `0.6.25`，AuroraDB parser 保持 `0.2.13`，ODB++ parser 和 JSON schema 版本保持不变。
- AEDB zone primitive 获取改为合并 `layout.Primitives` 一次性分类结果和快速 `GetFixedZonePrimitive()` 结果，默认不再调用耗时很长的 `GetZonePrimitives()`；仅在 raw active layout primitives 不可用的兜底场景下使用旧接口。
- primitive 收集新增 `collect layout primitives` / `classify layout primitives` 计时日志，避免 zone/primitive 分类阶段再次出现长时间黑盒。
- 修正 ODB++ -> AuroraDB component layer 映射：`COMP_+_TOP` / `COMP_+_BOT` 等 ODB++ component layer 现在会分别映射到顶层/底层 metal layer，避免没有统一 pin pad layer 的 component placement 被跳过。
- JSON schema 未变化；预期 source JSON 仅 `metadata.project_version` / `metadata.parser_version` 变化，semantic JSON 仅 `metadata.project_version` / `metadata.source_parser_version` 变化；ODB++ -> AuroraDB 的 component placement 输出会补齐此前缺失的 top/bottom component。

## 1.0.24

- 修正 Semantic -> AuroraDB 弧线方向输出：`Larc` / `Parc` 的最后字段统一按 AuroraDB 的 `CCW` 语义写出，不再把 ODB++ 的 `cw` 标志原样当作 AuroraDB 标志，避免 ODB++ 转出的弧线方向反向。
- 同步修正基于 arc-height 反推中心点的弧线方向；arc-height 为负仍表示 clockwise，写入 AuroraDB 时会转换为 `CCW=N`。
- JSON schema 未变化；Semantic JSON 不变，AuroraDB `layout.db` / layer `.lyr` 中的弧线方向标志会变化。

## 1.0.23

- 集成 Semantic parser `0.6.25` 和 AuroraDB parser `0.2.13`；AEDB、ODB++ parser 和 JSON schema 版本保持不变。
- 修正 AEDB -> AuroraDB `parts.db` 导出：当多个 part/variant 共用同一个 footprint 名称时，footprint pad/template geometry 只写入一次，避免重复 `PadTemplate.GeometryList` 导致前端 `mPadID` 下标越界。
- AuroraDB direct 导出和 AAF 编译收尾会为没有可导出 pad geometry 的 `FootPrintSymbol` 补齐空 `MetalLayer top 1`，避免前端解析/组件 outline 构建时报 `foot print symbol don't have metal layer`。
- AuroraDB block writer/reader 修正普通字段中括号/引号的处理：包含括号的名称会被正确加引号，reader 不再把引号内括号当作未闭合保留表达式。
- 批量前端检查脚本新增 `--only-failed-summary`，可基于历史 `summary.json` 只重跑失败案例。
- JSON schema 未变化；Semantic JSON 不变，AuroraDB `parts.db` 会消除重复 footprint pad/template geometry，并可能为空 footprint 补齐空 metal layer。

## 1.0.22

- 集成 AEDB parser `0.4.52`；Semantic parser 保持 `0.6.24`，AuroraDB、ODB++ parser 和 JSON schema 版本保持不变。
- AEDB polygon arc/cache 快速路径继续减少每条 segment 边的固定开销：segment `ArcModel` 构造直接在热点循环中完成，并简化 AuroraDB 坐标有效性判断。
- JSON schema 未变化；预期 source JSON 仅 `metadata.project_version` / `metadata.parser_version` 变化，semantic JSON 仅 `metadata.project_version` / `metadata.source_parser_version` 变化，AuroraDB 文件输出不变。

## 1.0.21

- Semantic parser 保持 `0.6.24`；AEDB、AuroraDB、ODB++ parser 和 JSON schema 版本保持不变。
- AuroraDB exporter 现在会把 `RoundedRectangle x y w h r` 补齐为前端兼容的完整 `RoundedRectangle x y w h r N Y Y Y Y` 格式，表示非倒角且四个角均为圆角，避免前端 `CeRectCutCorner.ReadFromIODataNode()` 因字段数不足无法读取。
- JSON schema 未变化；Semantic JSON 不变，AuroraDB `layout.db` / `parts.db` 中的 `RoundedRectangle` 几何字段会补齐。

## 1.0.20

- 集成 AEDB parser `0.4.51`；Semantic parser 保持 `0.6.24`，AuroraDB、ODB++ parser 和 JSON schema 版本保持不变。
- AEDB polygon arc/cache 构建热点改为更直接的 raw point 快速路径：在同一循环中内联坐标缩放、`Pnt` / `Parc` 行生成和 segment `ArcModel` 构造，减少每个点/边上的通用函数调用开销。
- JSON schema 未变化；预期 source JSON 仅 `metadata.project_version` / `metadata.parser_version` 变化，semantic JSON 仅 `metadata.project_version` / `metadata.source_parser_version` 变化，AuroraDB 文件输出不变。

## 1.0.19

- 集成 AEDB parser `0.4.50`；Semantic parser 保持 `0.6.24`，AuroraDB、ODB++ parser 和 JSON schema 版本保持不变。
- AEDB primitive 解析日志新增低噪声内部计时块，只汇总 path / polygon 的批量 .NET snapshot、模型构建、arc/cache 构建和 fallback 次数，便于定位后续优化瓶颈。
- JSON schema 未变化；预期 source JSON 仅 `metadata.project_version` / `metadata.parser_version` 变化，semantic JSON 仅 `metadata.project_version` / `metadata.source_parser_version` 变化，AuroraDB 文件输出不变。

## 1.0.18

- 集成 AEDB parser `0.4.49`；Semantic parser 保持 `0.6.24`，AuroraDB、ODB++ parser 和 JSON schema 版本保持不变。
- AEDB path / polygon primitive 解析新增分块批量 .NET snapshot：path 的 center line、宽度、端帽、基础字段，以及 polygon/void geometry、flags、基础字段会在批量 helper 中读取，减少 Python 与 .NET 的逐对象往返。
- JSON schema 未变化；预期 source JSON 仅 `metadata.project_version` / `metadata.parser_version` 变化，semantic JSON 仅 `metadata.project_version` / `metadata.source_parser_version` 变化，AuroraDB 文件输出不变。

## 1.0.17

- 集成 Semantic parser `0.6.24`；AEDB、AuroraDB、ODB++ parser 和 JSON schema 版本保持不变。
- 修正 ODB++ 标准 symbol 尺寸解析：`r76.2`、`r203.2` 等带小数的 round symbol 现在也按千分之一源单位解释，避免 trace-width 回归样本的 trace 宽度从 `3 mil`、`8 mil` 被错误放大成 `3000 mil`、`8000 mil`。
- JSON schema 未变化；预期 source JSON 仅 `metadata.project_version` 变化，semantic JSON 的 trace/arc `geometry.width` 会修正为真实源单位宽度，AuroraDB `Line` / `Larc` 引用的圆形 trace symbol 直径会同步修正。

## 1.0.16

- 集成 AEDB parser `0.4.48`；Semantic parser 保持 `0.6.23`，AuroraDB parser 保持 `0.2.12`，JSON schema 版本保持不变。
- AEDB polygon / void 现在在从 `raw_points` 构造 arcs 的同一轮遍历中生成运行时私有 AuroraDB `NetGeom` item 缓存，避免 `0.4.47` 中为缓存再次扫描 polygon arcs。
- JSON schema 未变化；预期 source JSON 仅 `metadata.project_version` / `metadata.parser_version` 变化，semantic JSON 仅 `metadata.project_version` / `metadata.source_parser_version` 变化，AuroraDB 文件输出不变。

## 1.0.15

- 集成 Semantic parser `0.6.23`；AEDB、AuroraDB、ODB++ parser 和 JSON schema 版本保持不变。
- AuroraDB `parts.db` 生成现在在 direct 导出和 AAF 编译收尾阶段强制执行 footprint pad/pin 完整性修复：每个 part 引用的 `FootPrintSymbol -> MetalLayer -> PartPad -> PadIDs[0]` 都会在该 part 的 `PinList -> Pin -> DefData` 第一字段中存在。
- JSON schema 未变化；预期 source/semantic JSON 仅 `metadata.project_version` / `metadata.parser_version` 变化，ODB++ 转 AuroraDB 的 `parts.db` 会在必要时补齐缺失的 part pin 定义。

## 1.0.14

- 集成 AEDB parser `0.4.47` 和 Semantic parser `0.6.22`；AuroraDB parser 保持 `0.2.12`，JSON schema 版本保持不变。
- AEDB extractor 现在在构造 path / polygon source model 时预生成运行时私有 AuroraDB trace 与 polygon `NetGeom` 缓存。
- AEDB -> SemanticBoard 现在优先复制 source model 上的私有缓存，避免 semantic 构建阶段再次扫描 `center_line`、polygon arcs 和 void arcs。
- JSON schema 未变化；预期 source JSON 仅 `metadata.project_version` / `metadata.parser_version` 变化，semantic JSON 仅 `metadata.project_version` / `metadata.parser_version` 变化，AuroraDB 文件输出不变。

## 1.0.13

- 集成 Semantic parser `0.6.21` 和 AuroraDB parser `0.2.12`；AEDB、ODB++ parser 和 JSON schema 版本保持不变。
- AEDB trace 现在会在 SemanticBoard 中预生成运行时私有 AuroraDB `Line` / `Larc` 行缓存，避免导出阶段重复扫描 `center_line`。
- AEDB direct AuroraDB exporter 会用 trace 私有缓存直接写 `NetGeom` raw block，减少 `AuroraBlock` / `AuroraItem` 对象构建。
- JSON schema 未变化；预期 source JSON 仅 `metadata.project_version` 变化，semantic JSON 仅 `metadata.project_version` / `metadata.parser_version` 变化，AuroraDB 文件输出不变。

## 1.0.12

- 集成 Semantic parser `0.6.20`；AuroraDB parser 保持 `0.2.11`，AEDB、ODB++ parser 和 JSON schema 版本保持不变。
- 优化 AEDB polygon / void 运行时 `NetGeom` 缓存构建热路径，减少每个 arc 上重复字段读取、单位换算和方向判断调用。
- 修正 ODB++ package footprint pad 导出：当 package pin 为数字而 component/part pin 为真实球位名时，`PartPad.PadIDs` 会按 component pin 顺序和局部坐标重映射，保证同一 part 的 footprint pad 能在 `PinList` 中找到对应 pin。
- JSON schema 未变化；预期 JSON 内容除 `metadata.project_version` / `metadata.parser_version` 外不变，ODB++ 转 AuroraDB 的 `parts.db` 会修正 footprint pad/pin 映射。

## 1.0.11

- 集成 Semantic parser `0.6.19` 和 AuroraDB parser `0.2.11`；AEDB、ODB++ parser 和 JSON schema 版本保持不变。
- AEDB -> SemanticBoard 现在为 polygon / void 预生成运行时私有 AuroraDB `NetGeom` 行缓存，避免导出阶段重复拆解 arc 和 raw point。
- AEDB direct AuroraDB exporter 会优先消费该私有缓存；缓存不进入 semantic JSON，因此显式 JSON 输出结构不变。
- 预期 source JSON 仅 `metadata.project_version` 变化，semantic JSON 仅 `metadata.project_version` / `metadata.parser_version` 变化，AuroraDB 文件输出不变。

## 1.0.10

- 集成 Semantic parser `0.6.18`；AEDB、AuroraDB、ODB++ parser 和 JSON schema 版本保持不变。
- 修正 ODB++ step profile 解析：多个 `OB` contour 现在会按 `I` 外轮廓优先、面积最大优先选择，避免 board-outline 回归样本被后续 hole contour 覆盖后退化为 fallback 矩形板框。
- 修正 ODB++ -> AuroraDB pad 导出：mask/paste 等非金属层 pad 不再 fallback 到 component 所在铜层，避免在 TOP/BOTTOM 铜层生成重复 pad 几何。
- Semantic JSON schema 未变化；ODB++ 转 AuroraDB 输出会修正 board outline 和铜层 `Location` 数量。

## 1.0.9

- 集成 Semantic parser `0.6.17` 和 AuroraDB parser `0.2.10`；AEDB parser 和 JSON schema 版本保持不变。
- 优化 AEDB -> SemanticBoard 内存链路：polygon / void geometry 保留 AEDB 已有的 tuple point 和 arc model，不再先复制为 dict/list。
- 优化 AEDB direct AuroraDB 输出：exporter 现在支持对象型和 dict 型 geometry，并对 numeric coordinate 走更短的单位转换 fast path。
- JSON schema 未变化；预期显式 semantic JSON 除 `metadata.project_version` / `metadata.parser_version` 外保持等价，AuroraDB 文件输出不变。

## 1.0.8

- 集成 AuroraDB parser `0.2.9`；AEDB parser、Semantic parser 和 JSON schema 版本保持不变。
- 优化 AuroraDB 导出写出路径：polygon / void `NetGeom` 现在使用轻量 raw block 直接写出，减少大量 `AuroraBlock` / `AuroraItem` 对象构建。
- 优化 AuroraDB layer 文件写盘：`layers/*.lyr` 使用受控并行写出，降低大板多层输出阶段的等待时间。
- JSON schema 未变化；预期 JSON 内容除 `metadata.project_version` 外不变，AuroraDB 文件输出不变。

## 1.0.7

- 集成 AuroraDB parser `0.2.8`；Semantic parser 保持 `0.6.16`。
- 优化 AEDB direct AuroraDB 输出：polygon/void 现在直接生成 `Pnt` / `Parc` 参数，避免先格式化为字符串再拆分回 block values。
- 优化 parts 构建：footprint pad 导出复用预构建的 pad、pin、shape、footprint 索引，避免大型 AEDB 回归样本在每个 footprint 上重复扫描整板列表。
- 优化长度单位转换和数值格式化：对 numeric + source unit 走 fast path，并缓存常用单位比例与格式化结果。
- 优化 AuroraDB block 写盘：改用分块 `writelines()`，减少大量小 `write()` 调用。
- JSON schema 未变化；预期 JSON 内容除 `metadata.project_version` 外不变，AuroraDB 文件输出不变。

## 1.0.6

- 集成 AuroraDB parser `0.2.7` 和 Semantic parser `0.6.16`。
- 优化 AEDB 默认 AuroraDB 输出路径：直接从 `SemanticBoard` 构建 `AuroraDBPackage`，不再生成内存 AAF command lines 后再经过 parser/executor 编译。
- AuroraDB polygon void、layout block、parts block 现在在默认 AEDB 路径中直接构建，保留 `--export-aaf` 兼容路径用于人工回归。
- 非 AEDB 的内存 AAF fallback 改为边解析边执行，避免额外保存完整 AAF command 对象列表。
- AEDB -> SemanticBoard 新增可选 `--skip-semantic-connectivity`，在不需要 semantic connectivity JSON 时可跳过 connectivity edge 和诊断构建；默认行为保持不变。
- JSON schema 未变化；默认输出预期除 `metadata.project_version` / `metadata.parser_version` 外不变，AuroraDB 文件输出不变。

## 1.0.5

- 集成 AuroraDB parser `0.2.6` 和 Semantic parser `0.6.15`。
- 优化默认 AuroraDB 输出路径：本项目导出的 AAF fast parser 现在按 option 类型拆分值，跳过 `-g`、`-location`、`-via` 等不需要拆分的 payload 扫描。
- 优化 AAF 执行：对导出器生成的 polygon void 临时容器采用移动式组合，避免构建 `PolygonHole` 时重复深拷贝 outline/void 几何。
- 优化 AEDB -> Semantic 构建收尾：`with_computed_summary()` 直接刷新当前 board summary，避免 summary 阶段整板复制。
- 优化 AuroraDB 写盘：block 文件改为流式写入，减少大文件格式化时的中间字符串占用。
- JSON schema 未变化；预期 JSON 内容除 `metadata.project_version` / `metadata.parser_version` 外不变，AuroraDB 文件输出不变。

## 1.0.4

- 集成 AuroraDB parser `0.2.5` 和 Semantic parser `0.6.14`。
- 优化默认 AuroraDB 输出路径：对本项目生成的 AAF command lines 使用轻量 parser，减少通用 AAF tokenizer 成本。
- 优化 AAF geometry 执行：常见 `Line`、`Larc`、`Polygon`、`PolygonHole` 几何现在优先直接构建 AuroraDB block，减少重复 `split_reserved()` 解析。
- 优化 AuroraDB block 写盘格式化和 AEDB -> Semantic 构建热路径，增加格式化缓存、semantic id 缓存和引用列表去重索引。
- JSON schema 未变化；预期 JSON 内容除 `metadata.project_version` / `metadata.parser_version` 外不变，AuroraDB 文件输出不变。

## 1.0.3

- 集成 AuroraDB parser `0.2.4`。
- 优化默认 AuroraDB 输出路径：`export_aaf: false` 时直接传递内存中的 AAF command lines，避免先拼接完整 AAF 文本再拆分解析。
- JSON schema 未变化；预期 JSON 内容除 `metadata.project_version` 外不变，AuroraDB 文件输出不变。

## 1.0.2

- 集成 AuroraDB parser `0.2.3`。
- 优化默认 AuroraDB 输出路径：`export_aaf: false` 时不再创建临时 AAF 文件，而是在内存中生成 AAF command text 并直接交给 AuroraDB 转换器。
- JSON schema 未变化。

## 1.0.1

- 集成 AuroraDB parser `0.2.2`。
- 优化 AuroraDB target 的 AAF 命令执行路径，为命令 option 查询和执行期 layer/net/block 查找增加缓存与索引，降低大样本导出为 AuroraDB 时的编译耗时。
- `AuroraDB` 目标现在默认直接把 `layout.db`、`parts.db` 和 `layers/` 写到 `-o` 输出目录，只保留 `stackup.dat`、`stackup.json`；`aaf/` 仅在显式传入 `--export-aaf` 或显式选择 AAF 输出时保留。
- JSON schema 未变化。

## 1.0.0

- 项目版本基线提升到 `1.0.0`，后续项目级变更从这个版本开始累计。
- 最终确认以 `sources -> SemanticBoard -> targets` 为唯一主架构，保留 AEDB、ODB++、AuroraDB source 以及 AAF / AuroraDB target 全部能力。
- 移除根目录下不再需要的兼容导入壳代码，项目只保留当前实际使用的目录结构和实现文件。
- README、项目架构文档、环境脚本和机器可读 schema 已同步到 `1.0.0` 基线。
- 集成 ODB++ parser `0.6.1` 和 Semantic parser `0.6.13`，重点优化大 ODB++ 样本的解析与语义构建性能。
- 大型 ODB++ 回归样本的 ODB++ -> Semantic -> AuroraDB 全链路现在可在约 3 分钟内完成；其中 semantic 构建已从约 44 分钟下降到约 1 分钟。

## 0.7.64

- 项目目录正式收敛到 `sources / semantic / targets / pipeline / shared` 结构，`SemanticBoard` 成为唯一统一中间模型。
- 新增 `convert`、`inspect`、`dump`、`schema` 顶层命令，主流程现在围绕 `source -> SemanticBoard -> target` 组织；旧的 `auroradb`、`odbpp`、`semantic` 命令继续保留为兼容入口。
- `semantic/aaf_export.py` 已迁移为 `targets/auroradb/exporter.py`，AuroraDB source 读取保留在 `sources/auroradb/`，明确区分 source 与 target 职责。
- `pipeline/` 新增统一加载与转换编排；`shared/` 收敛日志、性能和 JSON 输出工具。
- AEDB、ODB++、AuroraDB source 读取，以及 AAF / AuroraDB 导出链路现在都统一接入运行日志；默认日志路径仍为 `logs/aurora_translator.log`。
- `scripts/setup_env.ps1`、README 和架构文档已同步到新结构与新命令。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

## 1.0.44

- Fixed Allegro MCM/package-derived BRD header parsing: BRD parser `0.1.9` now recognizes the four extra linked-list slots before the version string in V18 headers, so `24.1/25.1` MCM samples no longer misread `board_units_code` as `12` or `units_divisor` as `0`. BRD JSON schema remains `0.5.0`; expected output differences are corrected source metadata and downstream coordinate scaling for these newer MCM files.
- Verification with `<BRD_CASES>/pkg-mcm-{24.1,25.1}.mcm`: source summary reports `diagnostics=0`, with header `board_units_code=5`, `units_divisor=100`, and `coordinate_scale_nm=254.0`; all five MCM versions convert and read back as AuroraDB with `layers=17`, `nets=328`, `components=20`, `parts=3`, `net_geometries=22043`, and `diagnostics=0`.
- Fixed large BRD-derived AuroraDB readback: AuroraDB parser `0.2.14` now treats quoted strings correctly inside parenthesized expressions, so attributes such as `PART_NAME` can contain `(` without raising an unclosed reserved expression. AuroraDB JSON schema remains `0.2.0`.
- Optimized large `BRD -> SemanticBoard -> AuroraDB` conversion performance: BRD parser `0.1.8` Python integration now uses the Rust CLI `--output` temp-file path plus trusted source-model construction, and the BRD semantic adapter builds source shape/segment indexes once and uses internal fast construction for high-volume semantic primitive/pad/via objects. BRD JSON schema, Semantic JSON schema, and AuroraDB file output are unchanged.
- Verification with `<BRD_CASES>/large-ddr5-17.4.brd`: optimized and baseline AuroraDB directories have no `diff -qr` differences, readback reports `layers=14`, `nets=6207`, `components=6894`, `net_geometries=365949`, and `diagnostics=0`; source load improved from about `96.0s` to about `73.6s`, and Semantic build improved from about `238.8s` to about `104.3s`.
- Added the Rust ODB++ target exporter `crates/odbpp_exporter/` and Python wrapper `targets/odbpp/`; `convert --to odbpp` now follows `source -> SemanticBoard -> ODB++` without bypassing Semantic from AEDB/BRD/ALG/ODB++ source formats.
- The ODB++ exporter writes a deterministic directory tree covering `matrix/matrix`, `misc/info`, `steps/<step>/profile`, `stephdr`, layer `features` / `attrlist` / drill `tools`, component-layer `components`, `eda/data`, and `netlists/cadnet/netlist`.
- The Rust writer is split along the C++ `examples/odbpp` semantics: `writer.rs` is only the module entry point, while `entity.rs` owns entity/step orchestration, `features.rs` owns feature records, `attributes.rs` owns attribute tables and layer attrlists, `components.rs` owns component records, `package.rs` owns EDA package/pin outlines, `eda_data.rs` owns EDA net/package data, `netlist.rs` owns cadnet netlists, and `formatting.rs` / `model.rs` own ODB++ formatting and the Semantic input model.
- Fixed component `TOP` record net/subnet references after comparing against the C++ exporter, and added cadnet pad/via net point records. Layer attrlists now emit available Semantic layer/material thickness, material, dielectric constant, and loss tangent attributes. JSON schemas are unchanged.
- Verification: `cargo test --manifest-path crates/odbpp_exporter/Cargo.toml` passes, and the generated ODB++ directory round-trips through the existing Rust ODB++ parser.
- Fixed AuroraDB -> ODB++ -> AuroraDB fidelity for `examples/AX7996A_MB_V3/AuroraDB`: the AuroraDB adapter now preserves layout shapes, expands `Line` / `Larc` / `Polygon` / `PolygonHole` / `SymbolID+Location` net geometry, and maps `COMP_*` pin/pad layers back to real metal layers; the ODB++ exporter preserves source net names, fixes `eda/data` `LYR` / `FID` ordering, and emits flashed net geometry.
- Verification with `examples/AX7996A_MB_V3/AuroraDB`: the round trip preserves `units=mm`, `metal_layers=10`, `nets=1278`, `components=2176`, `parts=244`, `netpins=8589`, `netvias=27914`, and `net_geometries=68091`, with `0` net geometry mismatches when grouped by `layer|net`. `shape_count` and `via_template_count` differ because ODB++ normalizes symbols and via templates.
- Fixed Allegro ALG / BRD to AuroraDB alignment issues driven by `<CASE_ROOT>/AX-small`: the ALG adapter now preserves extracta stackup material / dielectrics, source-unit coordinates, the largest board outline, `NoNet`, part names, and multi-layer padstack vias; the BRD adapter now uses source component / instance / footprint / pad-definition fields to recover refdes, part/package, side, component location/rotation, pin names, and NPTH-like hole vias.
- BRD parser `0.1.5` / BRD JSON schema `0.4.0` add 0x06 component, 0x07 component instance, 0x2D footprint instance, and 0x0D pad definition source models. Semantic parser is now `0.7.6`, while Semantic JSON schema remains `0.7.1`; ALG parser / ALG JSON schema are unchanged.
- Verification with `<CASE_ROOT>/AX-small`: ALG-generated AuroraDB `stackup.dat` matches the standard output, with `part_names=244/244`, `via_templates=31`, `netvias=27914`, and `netpins=8589`; BRD-generated AuroraDB has `part_names=244/244`, `via_templates=31`, `netvias=27914`, `netpins=8589`, `components=2176`, and `pins=8589`. BRD source still does not expose the full dielectric/material stackup, so BRD stackup output covers only the parsed copper layers.
- Fixed BRD board-outline and via/template alignment for `<CASE_ROOT>/AX-small`: the BRD adapter now writes `board_outline` from the `BOARD_GEOMETRY/BGEOM_OUTLINE` segment chain, derives blind/buried layer spans and drill/pad diameters from Allegro via padstack names, emits `RectCutCorner` templates for POB/slot padstacks, and writes padstack-offset drill centers for component-pad `NetVias`. Semantic parser is now `0.7.7`, while Semantic JSON schema remains `0.7.1`; BRD parser / BRD JSON schema are unchanged.
- Verification with `<CASE_ROOT>/AX-small`: the BRD-generated AuroraDB `layout.db` outline now matches ALG and the standard output, with `via_templates=31`, `netvias=27914`, `nets_with_vias=865`, and `diagnostics=0`; ignoring the `NoNet` / `NONET` keyword spelling difference, BRD `NetVias` coordinates and layer spans match the standard output at `27914/27914`.
- Fixed BRD padstack and component-layer alignment for `<CASE_ROOT>/AX-small`: BRD parser `0.1.6` / BRD JSON schema `0.5.0` now exposes the 0x1C padstack component geometry table. Semantic parser is now `0.7.8`; it uses padstack component types to recover the circular U1201 BGA pad, maps REF_DES inner-layer subclasses to `COMP_L2`, `COMP_L3`, `COMP_L5`, `COMP_L7`, `COMP_L8`, and `COMP_L9`, and pre-bakes POB/GND eccentric slot-via rotations into ViaList polygon / `RectCutCorner` shapes instead of relying on `NetVias` instance rotation. Semantic JSON schema remains `0.7.1`.
- Verification with `<CASE_ROOT>/AX-small`: BRD-generated AuroraDB has `layers=10`, `components=2176`, `pins=8589`, `pads=8589`, `vias=27904`, `via_templates=153`, and `diagnostics=0`; `LayerNameIDs` includes `COMP_TOP`, `COMP_BOTTOM`, `COMP_L2`, `COMP_L3`, `COMP_L5`, `COMP_L7`, `COMP_L8`, and `COMP_L9`, the U1201 footprint pad template is `Circle 0 0 0.33`, and the 5 POB/GND slot-via templates plus their 10 `NetVias` entries align with the standard AuroraDB barrel/pad shapes and `rotation=0`.
- Added the first Altium Designer `.PcbDoc` source parser: `crates/altium_parser/` provides the Rust CFB / PCB stream parsing core, CLI, and PyO3 native module, while `sources/altium/` provides the Python integration layer, Pydantic models, and schema helper. `inspect`, `dump`, `schema`, `convert`, `semantic`, and the pipeline now accept `--format altium` / `--from altium`.
- Altium parser `0.1.0` / Altium JSON schema `0.1.0` parses `FileHeader`, `Board6`, `Nets6`, `Classes6`, `Rules6`, `Components6`, `Pads6`, `Vias6`, `Tracks6`, `Arcs6`, `Fills6`, `Regions6`, `ShapeBasedRegions6`, `Polygons6`, `Texts6`, and `WideStrings6` from binary `.PcbDoc` containers. The new `Altium -> SemanticBoard` adapter maps copper layers, nets, components/footprints, pads/pins, via templates, vias, trace/arc/fill/region/polygon primitives, and board outline. Semantic parser is now `0.7.9`; Semantic JSON schema is now `0.7.2`, adding `source_format=altium`.
- Verified `examples/altium_cases/VR.PcbDoc`: source summary has `layers=98`, `nets=404`, `components=494`, `pads=7124`, `vias=1123`, `tracks=26872`, `arcs=1213`, `regions=60`, `polygons=136`, and `diagnostics=0`; Semantic summary has `layers=32`, `nets=405`, `components=494`, `footprints=48`, `pins=2176`, `pads=7124`, `vias=1123`, `primitives=28284`, and `diagnostics=0`.
- Verified `examples/altium_cases/XC7Z020CLG400-AD9).PcbDoc`: source summary has `layers=98`, `nets=302`, `components=276`, `pads=1684`, `vias=1576`, `tracks=13915`, `arcs=110`, `regions=22`, `polygons=37`, and `diagnostics=1`; Semantic summary has `layers=32`, `nets=303`, `components=276`, `footprints=26`, `pins=1676`, `pads=1684`, `vias=1576`, `primitives=14115`, and `diagnostics=1`. The only diagnostic is a `ShapeBasedRegions6` tail-read failure; main object streams still parse and convert.
- Fixed BRD component-pad footprint rotation for `<CASE_ROOT>/AX-small`: the BRD adapter now separates footprint-local `PartPad` rotation, layout absolute pad rotation, and component-pad `NetVias` instance rotation, so the rectangular pads on J2801 / J4802 and the polygon pad on Q4008 no longer receive component rotation twice; eccentric POB oblong polygons are pre-rotated into footprint-local shapes, with `PartPad Location` anchored at the drill center. Semantic parser is now `0.7.10`; BRD parser / BRD JSON schema are unchanged, and Semantic JSON schema remains `0.7.2`.
- Verification with `<CASE_ROOT>/AX-small`: BRD-generated AuroraDB still has `layers=10`, `components=2176`, `pins=8589`, `pads=8589`, `vias=27904`, `via_templates=153`, and `diagnostics=0`; J2801, J4802, and Q4008 `PartPad` rotations are `0`, J4802 POB footprint pad templates / locations align with the standard output, and component-pad `NetVias` rotation remains `0`.
- Fixed ALG component-layer and component-pad selection for `<CASE_ROOT>/AX-small`: the ALG semantic adapter now infers component placement layers from pin regular-pad layers, padstack spans, and metal-layer order, allowing inner component layers such as `COMP_L2`; the AuroraDB parts exporter now prefers component-footprint pads on the component's exact metal layer, and ALG oblong pads map to `RoundedRectangle`. Semantic parser is now `0.7.11`; ALG parser / ALG JSON schema are unchanged, and Semantic JSON schema remains `0.7.2`.
- Verification with `<CASE_ROOT>/AX-small` ALG conversion: Semantic summary is `layers=21`, `components=2176`, `pins=8589`, `pads=9014`, `vias=27904`, and `diagnostics=0`; AuroraDB has `parts=244` and `footprints=130`, and `COMP_*` pin distribution matches the standard output: `COMP_TOP=4807`, `COMP_BOTTOM=3644`, `COMP_L2=12`, `COMP_L3=2`, `COMP_L5=14`, `COMP_L7=74`, `COMP_L8=24`, and `COMP_L9=12`.
- Optimized `<CASE_ROOT>/AX-small` ALG semantic conversion performance by avoiding repeated component-to-pin full scans, using lightweight geometry payloads for ALG polygon / void segments, and constructing connectivity edges through the internal no-validation path. This performance optimization itself leaves generated AuroraDB `layout.db` / `parts.db` unchanged, and ALG parser / ALG JSON schema / Semantic JSON schema are unchanged.
- Verification with `<CASE_ROOT>/AX-small` ALG conversion: `from_alg(..., build_connectivity=True)` cProfile time dropped from about `8.42s` to about `7.17s`; the end-to-end convert semantic-build phase took `5.739s`.
- Fixed ALG component-pad contour handling for `<CASE_ROOT>/AX-small`: `LINE` / `ARC` pad outlines from ALG full-geometry are now grouped by record group and prefer the simple pad definition from the same padstack/layer, so `GRAPHIC_DATA_3/4` absolute endpoint coordinates are no longer treated as pad width/height. Semantic parser is now `0.7.12`; ALG parser / ALG JSON schema are unchanged, and Semantic JSON schema remains `0.7.2`.
- Verification with `<CASE_ROOT>/AX-small`: Semantic summary is `layers=21`, `components=2176`, `pins=8589`, `pads=8679`, `vias=27904`, `primitives=59512`, and `diagnostics=0`; the L9 `PAD_DIFFERENT_L1` footprint pad template changed from the incorrect `72.7502 x 11.2266` / `72.8378 x 11.139` rectangles back to the standard AuroraDB `Rectangle 0 0 0.15 0.15`, with `PartPad` local rotation at `0`; `COMP_L9` component placement coordinates and pin distribution remain aligned with the standard output.
- Added the Rust AEDB `.def` reverse-engineering parser and writer core `crates/aedb_parser/`, with CLI and PyO3 native module scaffolding. It currently covers length-prefixed text record / binary gap scanning, AEDB `$begin` / `$end` DSL block summaries, and a source-fidelity `.def` roundtrip writer. The default `sources/aedb/` PyEDB path and AEDB JSON schema are unchanged.
- Verified `examples/edb_cases/{fpc,kb,mb}.def`: `cargo test --manifest-path crates/aedb_parser/Cargo.toml`, `cargo check --manifest-path crates/aedb_parser/Cargo.toml`, and `cargo build --manifest-path crates/aedb_parser/Cargo.toml` pass; all three public samples report `def_version=12.1`, `encrypted=false`, and `diagnostics=0`, and roundtrip output is byte-identical to input.
- Added opt-in Python CLI support through `--aedb-backend def-binary`, letting `inspect source --format aedb` and `dump source-json --format aedb` call the Rust `.def` parser. The default `--aedb-backend pyedb` and `sources/aedb/parser.py` behavior are unchanged, and `def-binary` raises a clear error for Semantic JSON or conversion. This adds a separate `AEDBDefBinaryLayout` payload while leaving the existing `AEDBLayout` JSON schema unchanged.
- Verification: `uv run python -m compileall sources/aedb cli pipeline` passes; `main.py inspect source --format aedb examples/edb_cases/fpc.def --aedb-backend def-binary --json` and `main.py dump source-json --format aedb examples/edb_cases/fpc.def --aedb-backend def-binary` pass.
- The AEDB DEF binary parser is now `0.4.0`, and the `AEDBDefBinaryLayout` schema is now `0.4.0`. The Rust payload adds `domain.binary_geometry`, extracted from `.def` binary via-tail and raw-point path records, covering via-coordinate counts, named/anonymous path counts, Line/Larc segment counts, and path-width statistics. The existing PyEDB `AEDBLayout` schema is unchanged.
- `compare-auroradb <board.def> --auroradb <dir>` remains the Rust CLI path for comparing DEF extraction against a standard AuroraDB directory. `examples/edb_cases/{fpc,kb,mb}` now pass metal-layer order, ViaList-name, electrical-net-name, component-placement-name, and part-name-candidate checks, and add warning-level binary via/path count checks against AuroraDB `NetVias`, `Line`, and `Larc`. The remaining gaps are concentrated in component pad-derived vias, Location pad geometry, polygon/void payloads, and exact layer/net ownership.
- Fixed Allegro ALG / BRD to AuroraDB alignment issues driven by `<CASE_ROOT>/SS-small`: the ALG adapter now canonicalizes empty nets as `NONET`; the BRD adapter collapses unnamed BRD nets into `NONET`, prefers an exact `TOP ... BOTTOM` physical stackup layer list, and only consumes a BRD-embedded `DBPartitionAttachment` stackup when its copper names exactly match the current BRD copper layers, ignoring stale/mismatched cross-sections. When no usable physical stackup is available, the BRD adapter now generates `D0..Dn` dielectric placeholders from the current copper order without reading a sibling extracta `.alg`. REF_DES `FIELD -> TEXT_WRAPPER` chains plus `ASSEMBLY_` / `DISPLAY_` custom-layer pairs recover inner-layer component placements. BRD parser `0.1.7` fixes the pre-V172 `0x0C PIN_DEF` record stride, while BRD JSON schema remains `0.5.0`; Semantic parser is now `0.7.13`, while Semantic JSON schema remains `0.7.2`.
- Verification with `<CASE_ROOT>/SS-small`: `<OUTPUT_ROOT>/ss-small-{alg,brd}` both match the standard AuroraDB on `units=mm`, `metal_layers=10`, `layers=17`, `nets=585`, `components=1283`, `netpins=4561`, `netvias=17310`, `net_geometries=23203`, `parts=164`, `footprints=88`, and `via_templates=8`; net sets, component layer distribution, NetGeom grouped by `layer|net`, NetVia grouped by net, and NetPin grouped by net all have diff `0`. BRD-only conversion without a sibling `.alg` now produces a `stackup.dat` layer structure matching the standard: `SOLDERMASK_TOP/TOP/D0/.../D8/BOTTOM/SOLDERMASK_BOTTOM`; this BRD's embedded `DBPartitionAttachment` cross-section is stale 8-layer data, so physical thickness/material values still use defaults instead of the stale data. `shape_count` still differs because of symbol normalization: standard `167`, ALG `137`, BRD `121`.

## 1.0.43

- Added the first Cadence Allegro BRD source parser: `crates/brd_parser/` provides the Rust parsing core, CLI, and PyO3 native module, while `sources/brd/` provides the Python integration layer, Pydantic models, and generated JSON schema support. `inspect`, `dump`, `schema`, `convert`, `semantic`, and the pipeline now accept `--format brd` / `--from brd`.
- BRD parser `0.1.2` / BRD JSON schema `0.1.0` parse BRD headers, string tables, layer lists, nets, padstacks, footprints, placed pads, vias, tracks, shapes, texts, and block summaries. The added JSON fields are BRD-specific source JSON; existing AEDB, AuroraDB, ODB++, and Semantic JSON schemas are unchanged.
- Added the first `BRD -> SemanticBoard` adapter. It now maps BRD physical ETCH layers, nets, placed-pad bounding boxes, components / pins / footprints, padstack via templates, and vias into Semantic; track and shape segment chains remain in BRD source JSON and are flagged by a diagnostic for later mapping. Semantic parser is now `0.7.3`; Semantic JSON schema remains `0.7.0`.
- Verified with public sample `examples/LPDDR4_Demo.brd`: detected `V_174`, units `mils`, Rust parser summary `objects=95671/109165`, `strings=4108`, `layers=6`, `nets=605`, `padstacks=143`, `footprints=43`, `placed_pads=3140`, `vias=1501`, `tracks=4692`, `shapes=1481`, `texts=11640`, `diagnostics=0`; CLI `inspect source --format brd --json` and `schema --format brd` both pass.
- Fixed BRD multi-version binary parsing version gates and the V18.1 font-table stride so `<BRD_CASES>/DemoCase_LPDDR4_{17.2,22.1,23.1,24.1,25.1}.brd` parses with zero diagnostics from the original 17.2 file through later Allegro-saved variants; shared key counts are `layers=7`, `nets=489`, `padstacks=43`, `footprints=41`, `placed_pads=2963`, `vias=1117`, `tracks=1734`, `shapes=2675`, and `texts=14652`. BRD JSON schema is unchanged; expected output differences are that V17.2/V18.1 variants no longer stop early and source JSON now contains the full modeled object set.
- Added verification for `<BRD_CASES>/PA-series_{17.2,22.1,23.1,24.1,25.1}.brd`, covering the same design saved by different Allegro versions: all five variants parse with `diagnostics=0`, with shared key counts `layers=12`, `nets=1438`, `padstacks=158`, `footprints=139`, `placed_pads=8951`, `vias=16017`, `tracks=7539`, `shapes=4123`, and `texts=20996`. BRD JSON schema is unchanged.
- Added verification for `<BRD_CASES>/AX-series_{17.4,22.1,23.1,24.1,25.1}.brd`, covering the same design saved by different Allegro versions: all five variants parse with `diagnostics=0`, with shared key counts `layers=12`, `nets=1771`, `padstacks=153`, `footprints=156`, `placed_pads=12322`, `vias=27902`, `tracks=15190`, `shapes=12689`, and `texts=29716`. BRD JSON schema is unchanged.
- Verified BRD to AuroraDB output with `<BRD_CASES>/AX-series_25.1.brd`: Semantic summary is `layers=10`, `nets=1771`, `components=2176`, `footprints=156`, `pins=8591`, `pads=8591`, `vias=27902`, and `via_templates=153`; AuroraDB output contains `10` layer files, `2176` component placements, `8591` pad `NetGeom` records, and `27902` `NetVias.Via` records. The expected output difference is that BRD to AuroraDB no longer exports only a layer/net shell; Semantic JSON schema is unchanged.
- Fixed local resynchronization for V18.1 `SI_MODEL` records whose string length under-reports trailing bytes, so `<BRD_CASES>/S5000-series_{17.4,22.1,23.1,24.1,25.1}.brd` now parses with zero diagnostics across the same design saved by different Allegro versions; shared key counts are `layers=6`, `nets=7233`, `padstacks=163`, `footprints=146`, `placed_pads=43944`, `vias=31318`, `tracks=40514`, `shapes=24145`, and `texts=162630`. BRD JSON schema is unchanged; the expected output difference is that the V18.1/S5000 25.1 variant no longer stops early inside SI model data.
- Removed the historical C++ BRD reference directory `examples/brd_parser`; future BRD parser maintenance should use `crates/brd_parser/` and `sources/brd/` as the entrypoints. This repository-structure cleanup does not change the BRD JSON schema or parser output.
- Added the first Cadence Allegro extracta ALG source parser: `crates/alg_parser/` provides the Rust streaming parser core, CLI, and PyO3 native module, while `sources/alg/` provides the Python integration layer, Pydantic models, and generated JSON schema support. `inspect`, `dump`, `schema`, `convert`, `semantic`, and the pipeline now accept `--format alg` / `--from alg`.
- ALG parser `0.1.0` / ALG JSON schema `0.1.0` parse extracta board, layer, component, component-pin, logical-pin, composite-pad, full-geometry pad/via/track/outline, net, and symbol data. The added JSON fields are ALG-specific source JSON; Semantic schema only adds the `source_format=alg` enum value and is updated to `0.7.1`.
- Added the `ALG -> SemanticBoard -> AuroraDB` adapter, mapping ALG conductor layers, nets, components/packages, pins, component pads, via templates, vias, trace/arc/rectangle primitives, and board extents into unified semantic objects. The AuroraDB target now applies the same component-footprint pad preference and bottom-side flip handling to `alg` as it does for ODB++, and default fallback pads for missing copper geometry are scaled from mils into the source unit. Semantic parser is now `0.7.4`.
- Verified ALG to AuroraDB output with `<ALG_CASES>/DemoCase_LPDDR4.alg`: source summary `layers=17`, `metal_layers=8`, `components=293`, `pins=1710`, `pads=1803`, `vias=1117`, `tracks=18364`, `nets=334`, `diagnostics=0`; Semantic summary `layers=8`, `nets=334`, `components=293`, `footprints=27`, `pins=1710`, `pads=1745`, `vias=1117`, `primitives=18364`, `diagnostics=0`.
- Verified large ALG to AuroraDB output with `<ALG_CASES>/AX-series.alg`, `<ALG_CASES>/PA-series.alg`, and `<ALG_CASES>/S5000-series.alg`: AX has `layers=10`, `nets=1277`, `components=2176`, `pins=8589`, `pads=9014`, `vias=27902`, `primitives=411081`, `diagnostics=0`; PA has `layers=8`, `nets=935`, `components=1652`, `pins=6146`, `pads=6394`, `vias=16017`, `primitives=159378`, plus `272` info-level default pad geometry diagnostics for logical pins whose extracta records do not include copper pad geometry; S5000 has `layers=14`, `nets=6206`, `components=6888`, `pins=35289`, `pads=45195`, `vias=31318`, `primitives=661365`, `diagnostics=0`.
- Fixed Allegro copper-shape export for `<ALG_CASES>/AX-series.alg` and `<BRD_CASES>/AX-series_25.1.brd`: ALG parser `0.1.1` / ALG JSON schema `0.2.0` now preserves the `GRAPHIC_DATA_10` geometry role on track records, while BRD parser `0.1.4` / BRD JSON schema `0.3.0` adds the 0x34 keepout source model. Semantic parser `0.7.5` groups `SHAPE` segment chains into polygons, groups ALG `VOID` and BRD keepout chains into `PolygonHole`, and allows Allegro `SHAPE` polygons with two degenerate points. Semantic JSON schema remains `0.7.1`. AX verification: ALG output has `SHAPE polygon=8415`, `PolygonHole=352`, `Line=51024`, and `Larc=72`; BRD 25.1 output has `SymbolID -1=8415`, `PolygonHole=352`, `Line=51016`, and `Larc=72`.

## 1.0.42

- Integrated ODB++ parser `0.6.3`, Semantic parser `0.7.1`, and Semantic JSON schema `0.7.0`; AEDB parser remains `0.4.56`, AEDB JSON schema remains `0.5.0`, and ODB++ JSON schema remains `0.6.0`.
- The main Semantic `geometry` fields now use typed hint models: `footprints.geometry`, `via_templates.geometry`, `pads.geometry`, `vias.geometry`, `primitives.geometry`, and `board_outline` have explicit schema while retaining an extra-metadata escape hatch; Semantic JSON schema structure changes, but emitted JSON field names remain compatible.
- Fixed Python ODB++ parser integration so automatic Rust CLI binary resolution finds `crates/odbpp_parser/target/release/odbpp_parser(.exe)` from the project root; ODB++ JSON schema is unchanged.
- The Rust archive reader now skips unnecessary detail files for `--summary-only`, explicit `--step`, and default auto-step detail reads; default detail parsing first selects a step through a summary pass, then reads only the selected step's detail files.
- The Rust ODB++ archive reader now skips individual entries larger than 512 MiB by default and records a non-fatal diagnostic; added tokenizer, matrix, feature, net, and archive size-limit unit tests without changing the ODB++ JSON schema.
- Added a pytest/golden fixture foundation plus a GitHub Actions workflow covering `ruff format --check`, `ruff check`, Python compile, `unittest`, `pytest`, and `cargo test`.
- Removed UTF-8 BOM headers from project Markdown documentation so plain UTF-8 tooling can read them; document body content is unchanged.
- AuroraDB exporter pass boundaries were split further: `targets/auroradb/direct.py` owns direct AuroraDB builder state, `layout.py` owns `layout.db` / `design.layout` emission, `parts.py` owns `parts.db` / `design.part` emission plus part/footprint planning, `geometry.py` owns shape / via / trace / polygon geometry commands and payloads, `formatting.py` owns unit conversion, number parsing, point parsing, and rotation formatting, `names.py` owns naming normalization and AAF quoting, and `stackup.py` owns stackup planning plus `stackup.dat` / `stackup.json` serialization; this internal refactor does not change generated file formats.
- Fixed an AEDB -> AuroraDB arc-height direction regression: the direct exporter now maps AEDB raw-point / arc-height markers with `arc_height < 0` to AuroraDB `CCW=Y` and prefers explicit `is_ccw` / `clockwise` flags when present; Semantic / AEDB / ODB++ JSON schemas are unchanged. Expected output differences are corrected direction flags for AEDB trace `Larc`, polygon/void `Parc`, and polygon pad-shape arcs.
- Unified CLI and pipeline log style: command start, major stages, long-running heartbeat, and progress logs now use `Run started` / `Start` / `Progress` / `Done` / `Run completed` status words; the start banner includes the `Aurora Translator` project name, major stages restore star banners, log levels return to full `[INFO]` / `[ERROR]` names, and duplicated log-file notices are removed; JSON schemas and conversion outputs are unchanged.
- Python formatting is now standardized on the Ruff formatter: `pyproject.toml` explicitly stores the Ruff formatter configuration, commits should run `uv run ruff format .`, and read-only checks should run `uv run ruff format --check .`.
- Verified a private ODB++ sample `<CASE_ROOT>/sample.tgz`: Semantic summary is `layers=32`, `components=682`, `pads=24472`, `vias=5466`, `primitives=111009`, `diagnostics=2`, and AuroraDB plus coverage output are written successfully.
- Verified a private AEDB sample `<CASE_ROOT>/sample.aedb`: minimal/full AEDB -> AuroraDB paths both produce `layers=21`, `components=282`, `pads=1432`, `vias=1160`, `primitives=2355`, `diagnostics=2`, and all 14 AuroraDB output files have identical SHA-256 hashes.

## 1.0.41

- Integrated AEDB parser `0.4.56` and Semantic parser `0.6.38`; AuroraDB parser, ODB++ parser, and all JSON schema versions remain unchanged.
- Removed AuroraDB-specific Pydantic `PrivateAttr` runtime `NetGeom` caches from AEDB source models and Semantic models. The direct AuroraDB exporter now derives trace / polygon geometry only from explicit `geometry.center_line`, `geometry.raw_points`, `geometry.arcs`, and `geometry.voids`.
- The `auroradb-minimal` profile now preserves path `center_line`, polygon `raw_points`, and void raw geometry, so AEDB -> SemanticBoard -> AuroraDB no longer depends on non-serializable hidden state. JSON schemas are unchanged, but minimal-profile source model payloads are more complete than `1.0.40`.
- CLI entry points and source loading now import by command/format, so non-AEDB paths such as `schema`, `inspect aaf`, and `convert --help` no longer load PyEDB early. Added `tests/` architecture guards covering private-cache removal, explicit Semantic JSON geometry, CLI lazy import, and direct trace export.
- Added `targets/auroradb/plan.py` for reusable AuroraDB board-level export indexes, lowering coupling for later direct layout / parts / geometry exporter extraction. Moved `ruff` from runtime dependencies into the dev dependency group.

## 1.0.40

- Integrated Semantic parser `0.6.37`; AEDB parser, AuroraDB parser, ODB++ parser, and all JSON schema versions remain unchanged.
- ODB++ -> Semantic now canonicalizes oriented standard `rect` / `rect...xr` / `oval` symbols so the long axis maps to the Semantic shape `+X` direction; when the source symbol is vertically defined, the `90 deg` symbol-axis basis is folded into the pad feature rotation.
- Via-template refinement now derives `180 deg` half-turn symmetry from shape geometry before computing matched pad / antipad relative rotations. Centered circles, rectangles, rounded rectangles, and polygons that can be proven half-turn symmetric are normalized under `180 deg` equivalence, avoiding visual-equivalent slot pads being emitted with a `180 deg` relative offset because of slot start/end direction or symbol width/height basis.
- The fix is data-driven from source symbol dimensions and shape geometry only; it does not branch on layer, refdes, or coordinates. JSON schemas are unchanged. Expected output differences are limited to ODB++ slotted-via `SemanticPad.geometry.rotation`, `via_templates.geometry.layer_pad_rotations`, and AuroraDB `layout.db` `ViaList` layer-row rotations.
- Verified with a private ODB++ slot-via regression sample: Semantic summary is `components=682`, `via_templates=66`, `vias=5466`; relevant `r650` / `r500` / `r450` slot via `TOP`, `L2`, and `BOTTOM` layer pad rotations are all `0 Y`; `PartPad -> PinList` integrity issues are `0`.

## 1.0.39

- Integrated Semantic parser `0.6.36`; AEDB parser, AuroraDB parser, ODB++ parser, and all JSON schema versions remain unchanged.
- Reverted shape-axis subtraction from ODB++ slotted-via matched pad relative rotation: AuroraDB draws `Rectangle` / `RoundedRectangle` from their own `width` / `height`, then applies `ViaList` layer-row rotation and `NetVias.Via` instance rotation, so Semantic should store only `pad_rotation - via_rotation`.
- This restores the required `-90 Y` layer rotation for TOP oval via pads at connector pin locations and avoids the v1.0.38 `90 deg` offset. JSON schemas are unchanged.
- Verified with a private ODB++ slot-via regression sample: Semantic summary is `components=682`, `via_templates=69`, `vias=5466`; the target connector-location `r650` slot via `TOP` layer pad rotation is `-90 Y`, with `L2` / `BOTTOM` at `0 Y`; `PartPad -> PinList` integrity issues are `0`.

## 1.0.38

- Integrated Semantic parser `0.6.35`; AEDB parser, AuroraDB parser, ODB++ parser, and all JSON schema versions remain unchanged.
- Fixed ODB++ slotted-via matched layer-pad relative rotation: when a slot barrel and a matched oval / rounded-rectangle pad use different default long-axis directions, `via_templates.geometry.layer_pad_rotations` now removes the shape width/height axis delta before computing the relative angle.
- This prevents TOP oval via pads at connector pin locations from receiving an extra `90 deg` rotation. Circular vias and unoriented barrels are unaffected, and JSON schemas are unchanged.
- Verified with a private ODB++ slot-via regression sample: Semantic summary is `components=682`, `via_templates=69`, `vias=5466`; the target connector-location `r650` slot via `TOP` layer pad rotation changes from `-90 Y` to `0 Y`; `PartPad -> PinList` integrity issues are `0`.

## 1.0.37

- Integrated Semantic parser `0.6.34`; AEDB parser, AuroraDB parser, ODB++ parser, and all JSON schema versions remain unchanged.
- Fixed the ODB++ slotted-via rotation basis: `SemanticVia.geometry.rotation` now stores ODB++ clockwise-positive angles relative to the shape `+X` axis, and the slot barrel `RoundedRectangle` is emitted as `total_length x width`, preventing AuroraDB `NetVias.Via` and `ViaList` layer pads from being globally offset by `90 deg`.
- `via_templates.geometry.layer_pad_rotations` is recomputed from the new slot via instance angle. This changes ODB++ slot via barrel shapes, via instance rotation, and matched pad / antipad relative rotation, without changing JSON schemas.
- Verified with a private ODB++ slot-via regression sample: Semantic summary is `components=682`, `via_templates=69`, `vias=5466`; `PartPad -> PinList` integrity issues are `0`.

## 1.0.36

- Semantic parser remains `0.6.33`; AEDB parser, AuroraDB parser, ODB++ parser, and all JSON schema versions remain unchanged.
- Fixed ODB++ -> Semantic -> AuroraDB `ViaList` layer pad rotation output: Semantic still stores ODB++ clockwise-positive relative angles, but AuroraDB `CCW=Y` layer-row fields now receive counter-clockwise numeric values.
- This fix only changes nonzero rotation signs for AuroraDB via-template layer pads / antipads; it does not change component placement, net via instance locations, Semantic JSON fields, or ODB++ source JSON.
- Verified with a private ODB++ slot-via regression sample: Semantic summary remains `components=682`, `via_templates=69`, `vias=5466`; `PartPad -> PinList` integrity issues are `0`.

## 1.0.35

- Semantic parser remains `0.6.33`; AEDB parser remains `0.4.55`, AEDB JSON schema remains `0.5.0`, AuroraDB parser remains `0.2.13`, and ODB++ parser and JSON schema versions remain unchanged.
- AEDB -> AuroraDB export now emits multi-layer component pin padstacks as same-net, same-location `NetVias.Via` records, so through-hole connector pins render as cross-layer connections on inner signal layers.
- Single-layer SMD component padstacks are not emitted as vias; the fix only applies to component pins/pads referencing multi-layer via templates.
- Fixed ODB++ -> AuroraDB `ViaList` layer pad rotation output: component-connected slot via layer-pad relative angles now keep the same clockwise-positive convention used by ODB++ component / pad export instead of applying an extra sign inversion, preventing reversed connector-pin slot via pads and GND slot via pads.
- Added detailed ODB++ -> Semantic mapping documentation covering object mapping, via-template refinement, component/pad/via rotation formulas, and the AuroraDB target boundary.
- Verified with a private AEDB through-hole connector regression sample: inner-layer trace connector-pin endpoints now get same-location `NetVias.Via` records, and related through-hole component-pin endpoints receive corresponding net vias.
- Verified with a private ODB++ slot-via regression sample: multiple same-location pin-connected slot vias keep the matched real pad shapes; the related slot via template layer pad rotation is written as `-90 Y`; `PartPad -> PinList` integrity issues are `0`.
- JSON schema versions are unchanged; AuroraDB `layout.db` `ViaList` includes padstack templates used by through-hole component pins, and `NetVias` count increases.

## 1.0.34

- Integrated Semantic parser `0.6.33`; AEDB parser remains `0.4.55`, AEDB JSON schema remains `0.5.0`, AuroraDB parser remains `0.2.13`, and ODB++ parser and JSON schema versions remain unchanged.
- AEDB -> SemanticBoard via-template layer pads now preserve physical stackup order instead of sorting layer names lexically, preventing via layer order from diverging from `LayerStackup.MetalLayers`.
- AuroraDB `ViaList` export now writes only via templates referenced by exported net vias, so component/SMD padstack definitions are no longer emitted as unused via templates and single-layer component padstacks are not mistaken for missing-layer vias.
- Verified with a private AEDB via-layer sample: source via instances are `5806`, all spanning TOP to BOTTOM; AuroraDB `NetVias` is `5806`, `ViaList` is reduced from `99` templates to `7` used via templates, and every used template contains `12` metal layers.
- JSON schema versions are unchanged; AEDB-derived Semantic JSON `via_templates.layer_pads` order changes, and AuroraDB `layout.db` `ViaList` template count and layer-pad order change.

## 1.0.33

- Integrated Semantic parser `0.6.32`; AEDB parser remains `0.4.55`, AEDB JSON schema remains `0.5.0`, AuroraDB parser remains `0.2.13`, and ODB++ parser and JSON schema versions remain unchanged.
- ODB++ via-template pad matching now sorts candidates by distance to the via center first, then prefers component pads only at the same distance, preventing a farther component pad from overriding an exactly aligned real via pad during tolerant matching.
- AuroraDB `ViaList` layer pad rotation now follows the field's own `CCW` semantics: ODB++ clockwise relative angles are converted to counter-clockwise angles under `CCW=Y` instead of reusing normal location rotation formatting.
- Verified with a private ODB++ via-pad rotation sample: Semantic summary is `shapes=253`, `via_templates=69`, `vias=5466`; the `r650` slot via template keeps the real rounded-rectangle `TOP` pad, `L2` / `BOTTOM` pad rotation is written as `90 Y`, slot via instance rotation remains `-180` / `0`; `PartPad -> PinList` integrity issues are `0`.
- JSON schema versions are unchanged; nonzero via-template layer pad rotation signs in AuroraDB `layout.db` / `aaf/design.layout` change to follow `CCW=Y` semantics.

## 1.0.32

- Integrated Semantic parser `0.6.31`; AEDB parser remains `0.4.55`, AEDB JSON schema remains `0.5.0`, AuroraDB parser remains `0.2.13`, and ODB++ parser and JSON schema versions remain unchanged.
- ODB++ via-template pad matching now tolerates small coordinate offsets up to `0.001` source units on the same net and layer, fixing component-pin-connected drills/vias whose TOP-layer pad center differs slightly from the drill center.
- When a via matches a component pad, the component pad shape is preferred and the refined via template records each layer pad rotation relative to the via instance; both direct AuroraDB and AAF output now write via-template layer pad rotation.
- Verified with a private ODB++ component-connected via-pad sample: Semantic summary is `shapes=253`, `via_templates=69`, `vias=5466`; the slot via template uses the real rounded-rectangle `TOP` pad, `L2` / `BOTTOM` pad rotation is `-90`, slot via instance rotation remains `-180` / `0`; `PartPad -> PinList` integrity issues are `0`.
- JSON schema versions are unchanged; Semantic JSON may gain `via_templates.geometry.layer_pad_rotations` hints, and AuroraDB `layout.db` / `aaf/design.layout` via-template layer pad shape and rotation may change.

## 1.0.31

- Integrated Semantic parser `0.6.30`; AEDB parser remains `0.4.55`, AEDB JSON schema remains `0.5.0`, AuroraDB parser remains `0.2.13`, and ODB++ parser and JSON schema versions remain unchanged.
- AEDB -> SemanticBoard now constructs `Round45`, `Round90`, `Bullet`, and `NSidedPolygon` pad geometry as `SemanticShape(kind="polygon")`, avoiding skipped or circle-degraded parameterized AEDB pad shapes in AuroraDB footprint pad/template output.
- `NSidedPolygon` is generated from `Size` and `NumSides`; `Bullet` is generated from `XSize`, `YSize`, and `CornerRadius` with arc vertices; `Round45` / `Round90` are generated from `Inner`, `ChannelWidth`, and `IsolationGap` with the corresponding thermal-polygon orientation.
- JSON schema versions are unchanged and AEDB source JSON fields are unchanged. Expected output differences are limited to related Semantic JSON `shapes` / `via_templates.layer_pads` and AuroraDB `parts.db` / `layout.db` pad shapes changing from missing or older geometry to `Polygon`.

## 1.0.30

- Integrated Semantic parser `0.6.29`; AEDB parser remains `0.4.55`, AuroraDB parser remains `0.2.13`, and ODB++ parser and JSON schema versions remain unchanged.
- ODB++ -> SemanticBoard now converts net-connected drill-layer `L` line drill features into slotted `SemanticVia` records, using `RoundedRectangle` barrel shapes and preserving via-instance rotation so oval vias, via pads, and via holes are no longer dropped.
- ODB++ via-template pad/antipad matching now runs after component pads are created; matching prefers regular metal-layer pads and falls back to component pads when needed, so component-bound GND slot via pads use the real oval/rounded pad size.
- The AuroraDB exporter now writes Semantic via-instance rotation into direct `layout.db` output and AAF `layout add -net ... -via` commands.
- `ODBPP_DRAWING` / drawing-only drill markers remain untranslated to AuroraDB under the current policy; this change only translates real drill-layer net vias/holes.
- Verified with a private ODB++ slot-via sample: Semantic summary is `shapes=253`, `via_templates=14`, `vias=5466`; AuroraDB output contains `4` slot via templates and `15` slot via instances, including `10` GND slot vias; `PartPad -> PinList` integrity issues are `0`.
- JSON schema versions are unchanged; Semantic JSON may add slotted vias and rounded-rectangle shapes, while AuroraDB `layout.db` / `aaf/design.layout` gains slot via templates, slot via instances, and required via rotation.

## 1.0.29

- Integrated AEDB parser `0.4.55`, AEDB JSON schema `0.5.0`, and Semantic parser `0.6.28`; AuroraDB parser remains `0.2.13`, and ODB++ parser and JSON schema versions remain unchanged.
- Added AEDB padstack-definition support for polygonal pads: when `GetPadParametersValue()` reports `NoGeometry` but `GetPolygonalPadParameters()` returns a polygon, vertices are preserved in `PadPropertyModel.raw_points`.
- AEDB -> SemanticBoard now converts polygonal pads into `SemanticShape(kind="polygon")`, allowing AuroraDB `parts.db` `FootPrintSymbol -> PadTemplate -> PartPad` output to include polygon pads instead of empty footprints.
- Verified with a private AEDB component-gap sample: source component count and AuroraDB component placement count are both `1642`; components affected by empty footprints dropped from `720` to `0`.
- Expected output differences: AEDB JSON pad properties add `raw_points`; Semantic JSON `shapes` / `via_templates.layer_pads` may gain polygon pad shapes; AuroraDB `parts.db` fills previously empty polygon `PadTemplate` and `PartPad` records.

## 1.0.28

- Integrated Semantic parser `0.6.27`; AEDB parser remains `0.4.54`, AuroraDB parser remains `0.2.13`, and ODB++ parser and JSON schema versions remain unchanged.
- ODB++ standard symbol parsing now supports `s...` squares, `di...` diamonds, `rect...xr...` rounded rectangles, and degenerate one-sided-zero `oval...` symbols, so component pads, via matched pads, and layout primitives receive stable `shape_id` values.
- ODB++ -> AuroraDB footprint libraries now prefer real component-bound metal-layer feature pad geometry for `PartPad` templates; package pin markers are used only as a fallback, preventing small component pin sizes from shrinking to marker geometry.
- When one source footprint contains multiple pad shape signatures, AuroraDB part/footprint variants are split and the exported footprint name is recorded as `EXPORT_FOOTPRINT`, preventing square/diamond and other pad shapes from overwriting each other.
- Verified with a private ODB++ sample: Semantic summary is `components=682`, `pads=24472`, `vias=5451`, `via_templates=10`; AuroraDB `parts.db` contains `94` Parts and `78` FootPrintSymbols; `PartPad -> PinList` integrity issues are `0`.
- JSON schemas are unchanged; Semantic JSON may add previously unrecognized pad/shape relationships, and AuroraDB `parts.db` / `aaf/design.part` component pad sizes, diamond pads, and oval/rounded pad output may change.

## 1.0.27

- Integrated AEDB parser `0.4.54`; Semantic parser remains `0.6.26`, AuroraDB parser remains `0.2.13`, and ODB++ parser and JSON schema versions remain unchanged.
- AEDB -> AuroraDB direct conversion now automatically enables the `auroradb-minimal` parse profile when neither `--source-output` nor `--semantic-output` is requested. The profile skips path `center_line` / length / area storage and polygon `raw_points` / arcs / void model storage that are only needed by source/Semantic JSON, while keeping bbox, width, ownership fields, and runtime-private `NetGeom` caches required by AuroraDB output.
- Added `--aedb-parse-profile auto|full|auroradb-minimal`; explicit AEDB JSON or Semantic JSON output still uses the complete profile, and explicit minimal parsing with intermediate JSON output is rejected.
- Verified with a private AEDB regression sample: same-version full profile and auto minimal profile produced identical hashes across `14` AuroraDB files. Verified with a large AEDB regression sample: same-version full/minimal output hashes matched across `40` files, `Parse AEDB layout` dropped from `74.937s` to `40.576s`, and `Serialize layout primitives` dropped from `55.498s` to `21.221s`.
- JSON schemas are unchanged; explicit source JSON / semantic JSON still use the complete profile. AuroraDB output is expected to remain unchanged, while performance changes are concentrated in AEDB path / polygon primitive parsing.

## 1.0.26

- Integrated Semantic parser `0.6.26`; AEDB parser remains `0.4.53`, AuroraDB parser remains `0.2.13`, and ODB++ parser and JSON schema versions remain unchanged.
- Fixed ODB++ -> AuroraDB bottom-side component placement: components from bottom component layers now write `flipX` in both direct AuroraDB and AAF output, so package footprint pins align with ODB++ component-pin absolute coordinates after clockwise rotation plus local x-axis mirroring.
- Fixed ODB++ package fallback coordinate derivation when explicit component pin positions are missing: bottom-side components now apply the same local x-axis mirror when package pins are converted into placed pads, keeping fallback footprint/pad coordinates consistent with component placement.
- Verified with a private ODB++ bottom-side component sample: AuroraDB component placement count is `1572`, bottom-side `flipX` placement count is `869`, and the inspected asymmetric bottom package has `0 mil` maximum error between source pins and AuroraDB-transformed pins.
- JSON schemas are unchanged; aside from version metadata, Semantic JSON may change only for bottom-side pad coordinates inferred from package fallback; AuroraDB `layers/*.lyr` and `aaf/design.layout` bottom-side component placements may add `FlipX=Y` / `-flipX`.

## 1.0.25

- Integrated AEDB parser `0.4.53`; Semantic parser remains `0.6.25`, AuroraDB parser remains `0.2.13`, and ODB++ parser and JSON schema versions remain unchanged.
- AEDB zone primitive collection now merges the one-pass `layout.Primitives` classification result with the fast `GetFixedZonePrimitive()` result and no longer calls the very slow `GetZonePrimitives()` path by default; the old interface is kept only as a fallback when raw active layout primitives are unavailable.
- Primitive collection now emits `collect layout primitives` / `classify layout primitives` timing logs so zone/primitive classification cannot become a long uninstrumented section again.
- Fixed ODB++ -> AuroraDB component layer mapping: ODB++ component layers such as `COMP_+_TOP` / `COMP_+_BOT` now map to the top / bottom metal layers, so component placements without a single resolved pin pad layer are no longer skipped.
- JSON schemas are unchanged; expected source JSON changes only `metadata.project_version` / `metadata.parser_version`, expected semantic JSON changes only `metadata.project_version` / `metadata.source_parser_version`; ODB++ -> AuroraDB component placement output may add previously missing top / bottom components.

## 1.0.24

- Fixed Semantic -> AuroraDB arc direction export: the final `Larc` / `Parc` field is now written with AuroraDB `CCW` semantics instead of passing through the ODB++ `cw` flag, avoiding reversed arcs in ODB++ conversions.
- Also fixed arc-height based center reconstruction so negative arc height still means clockwise and is exported to AuroraDB as `CCW=N`.
- JSON schemas are unchanged; Semantic JSON is unchanged, while AuroraDB `layout.db` / layer `.lyr` arc direction flags may change.

## 1.0.23

- Integrated Semantic parser `0.6.25` and AuroraDB parser `0.2.13`; AEDB, ODB++ parser, and JSON schema versions remain unchanged.
- Fixed AEDB -> AuroraDB `parts.db` export so shared footprint names across parts/variants emit footprint pad/template geometry only once, avoiding duplicated `PadTemplate.GeometryList` entries that made the frontend index past `mPadList` and throw on `mPadID`.
- Direct AuroraDB export and AAF compilation now add an empty `MetalLayer top 1` to `FootPrintSymbol` blocks that have no exportable pad geometry, preventing frontend component preparation from reporting `foot print symbol don't have metal layer`.
- AuroraDB block writer/reader now handle parentheses and quotes in ordinary field values correctly: names with parentheses are quoted on write, and quoted parentheses are not treated as unclosed reserved expressions on read.
- The batch frontend check script now supports `--only-failed-summary` to rerun only cases that failed in a previous `summary.json`.
- JSON schemas are unchanged; Semantic JSON is unchanged, while AuroraDB `parts.db` removes duplicated footprint pad/template geometry and may add empty metal layers for padless footprints.

## 1.0.22

- Integrated AEDB parser `0.4.52`; Semantic parser remains `0.6.24`, AuroraDB and ODB++ parser versions remain unchanged, and JSON schema versions remain unchanged.
- AEDB polygon arc/cache fast path further reduces fixed per-segment overhead: segment `ArcModel` construction now happens directly inside the hot loop, and AuroraDB coordinate validity checks are simplified.
- JSON schemas are unchanged; expected source JSON changes only `metadata.project_version` / `metadata.parser_version`, expected semantic JSON changes only `metadata.project_version` / `metadata.source_parser_version`, and AuroraDB file output remains unchanged.

## 1.0.21

- Semantic parser remains `0.6.24`; AEDB, AuroraDB, ODB++, and JSON schema versions remain unchanged.
- The AuroraDB exporter now expands `RoundedRectangle x y w h r` into the frontend-compatible full `RoundedRectangle x y w h r N Y Y Y Y` form, representing a non-chamfered rounded rectangle with all four corners enabled, so frontend `CeRectCutCorner.ReadFromIODataNode()` can read it.
- JSON schemas are unchanged; Semantic JSON is unchanged, while `RoundedRectangle` geometry items in AuroraDB `layout.db` / `parts.db` are expanded.

## 1.0.20

- Integrated AEDB parser `0.4.51`; Semantic parser remains `0.6.24`, AuroraDB and ODB++ parser versions remain unchanged, and JSON schema versions remain unchanged.
- AEDB polygon arc/cache construction now uses a more direct raw-point fast path: coordinate scaling, `Pnt` / `Parc` line generation, and segment `ArcModel` construction are inlined in the same loop to reduce per-point/per-edge generic function-call overhead.
- JSON schemas are unchanged; expected source JSON changes only `metadata.project_version` / `metadata.parser_version`, expected semantic JSON changes only `metadata.project_version` / `metadata.source_parser_version`, and AuroraDB file output remains unchanged.

## 1.0.19

- Integrated AEDB parser `0.4.50`; Semantic parser remains `0.6.24`, AuroraDB and ODB++ parser versions remain unchanged, and JSON schema versions remain unchanged.
- AEDB primitive extraction logs now include a low-noise internal timing block summarizing path / polygon batch .NET snapshots, model construction, arc/cache construction, and fallback counts to guide the next optimization pass.
- JSON schemas are unchanged; expected source JSON changes only `metadata.project_version` / `metadata.parser_version`, expected semantic JSON changes only `metadata.project_version` / `metadata.source_parser_version`, and AuroraDB file output remains unchanged.

## 1.0.18

- Integrated AEDB parser `0.4.49`; Semantic parser remains `0.6.24`, AuroraDB and ODB++ parser versions remain unchanged, and JSON schema versions remain unchanged.
- AEDB path / polygon primitive extraction now uses chunked .NET batch snapshots: path center lines, widths, end caps, base fields, plus polygon/void geometry, flags, and base fields are read through batch helpers to reduce per-object Python/.NET round trips.
- JSON schemas are unchanged; expected source JSON changes only `metadata.project_version` / `metadata.parser_version`, expected semantic JSON changes only `metadata.project_version` / `metadata.source_parser_version`, and AuroraDB file output remains unchanged.

## 1.0.17

- Integrated Semantic parser `0.6.24`; AEDB, AuroraDB, ODB++, and JSON schema versions remain unchanged.
- Fixed ODB++ standard symbol size parsing: decimal round symbols such as `r76.2` and `r203.2` are now interpreted as one-thousandth of the source unit, preventing trace-width regression sample traces from being inflated from `3 mil` / `8 mil` to `3000 mil` / `8000 mil`.
- JSON schemas are unchanged; expected source JSON changes only `metadata.project_version`, semantic trace/arc `geometry.width` values are corrected to the real source-unit widths, and AuroraDB `Line` / `Larc` circular trace-symbol diameters are corrected accordingly.

## 1.0.16

- Integrated AEDB parser `0.4.48`; Semantic parser remains `0.6.23`, AuroraDB parser remains `0.2.12`, and JSON schema versions remain unchanged.
- AEDB polygon / void extraction now builds runtime-private AuroraDB `NetGeom` item caches during the same raw-point pass that constructs polygon arcs, avoiding the extra polygon-arc scan introduced in `0.4.47`.
- JSON schemas are unchanged; expected source JSON changes only `metadata.project_version` / `metadata.parser_version`, expected semantic JSON changes only `metadata.project_version` / `metadata.source_parser_version`, and AuroraDB file output remains unchanged.

## 1.0.15

- Integrated Semantic parser `0.6.23`; AEDB, AuroraDB, ODB++, and JSON schema versions remain unchanged.
- AuroraDB `parts.db` generation now enforces footprint pad/pin integrity at the end of both direct export and AAF compilation: every `FootPrintSymbol -> MetalLayer -> PartPad -> PadIDs[0]` referenced by a part is guaranteed to exist in that part's `PinList -> Pin -> DefData` first field.
- JSON schemas are unchanged; expected source/semantic JSON changes only `metadata.project_version` / `metadata.parser_version`, and ODB++ -> AuroraDB `parts.db` may add missing part pin definitions when needed.

## 1.0.14

- Integrated AEDB parser `0.4.47` and Semantic parser `0.6.22`; AuroraDB parser remains `0.2.12`, and JSON schema versions remain unchanged.
- The AEDB extractor now precomputes runtime-private AuroraDB trace and polygon `NetGeom` caches when building path / polygon source models.
- AEDB -> SemanticBoard now copies private caches from source models first, avoiding another semantic-stage scan of `center_line`, polygon arcs, and void arcs.
- JSON schemas are unchanged; expected source JSON changes only `metadata.project_version` / `metadata.parser_version`, expected semantic JSON changes only `metadata.project_version` / `metadata.parser_version`, and AuroraDB file output remains unchanged.

## 1.0.13

- Integrated Semantic parser `0.6.21` and AuroraDB parser `0.2.12`; AEDB, ODB++, and JSON schema versions remain unchanged.
- AEDB traces now precompute runtime-private AuroraDB `Line` / `Larc` item-line caches on SemanticBoard, avoiding repeated `center_line` scans during export.
- The AEDB direct AuroraDB exporter writes trace `NetGeom` raw blocks from that private cache, reducing `AuroraBlock` / `AuroraItem` object construction.
- JSON schemas are unchanged; expected source JSON changes only `metadata.project_version`, expected semantic JSON changes only `metadata.project_version` / `metadata.parser_version`, and AuroraDB file output remains unchanged.

## 1.0.12

- Integrated Semantic parser `0.6.20`; AuroraDB parser remains `0.2.11`, and AEDB, ODB++, and JSON schema versions remain unchanged.
- Optimized the AEDB polygon / void runtime `NetGeom` cache builder hot path, reducing repeated field reads, unit conversion, and direction checks per arc.
- Fixed ODB++ package-footprint pad export: when package pins are numeric but component/part pins use real ball names, `PartPad.PadIDs` are remapped by component pin order and local coordinates so every footprint pad resolves to a pin in the same part's `PinList`.
- JSON schemas are unchanged; expected JSON content is unchanged except `metadata.project_version` / `metadata.parser_version`; ODB++ -> AuroraDB `parts.db` now corrects footprint pad/pin mapping.

## 1.0.11

- Integrated Semantic parser `0.6.19` and AuroraDB parser `0.2.11`; AEDB, ODB++, and JSON schema versions remain unchanged.
- AEDB -> SemanticBoard now precomputes a runtime-private AuroraDB `NetGeom` line cache for polygon / void geometry, avoiding repeated arc and raw-point conversion during export.
- The AEDB direct AuroraDB exporter consumes this private cache first; it is not serialized into semantic JSON, so the explicit JSON shape remains unchanged.
- Expected source JSON changes only `metadata.project_version`; expected semantic JSON changes only `metadata.project_version` / `metadata.parser_version`; AuroraDB file output remains unchanged.

## 1.0.10

- Integrated Semantic parser `0.6.18`; AEDB, AuroraDB, ODB++, and JSON schema versions remain unchanged.
- Fixed ODB++ step-profile parsing so multiple `OB` contours are selected by `I` outer-contour priority and largest area, avoiding a board-outline regression sample falling back to a rectangular board outline after a later hole contour overwrote the outer profile.
- Fixed ODB++ -> AuroraDB pad export so mask/paste pads no longer fall back to the component copper layer, preventing duplicate pad geometry on TOP/BOTTOM copper layers.
- Semantic JSON schema is unchanged; ODB++ -> AuroraDB output now corrects the board outline and copper-layer `Location` counts.

## 1.0.9

- Integrated Semantic parser `0.6.17` and AuroraDB parser `0.2.10`; AEDB parser and JSON schema versions remain unchanged.
- Optimized the AEDB -> SemanticBoard in-memory path: polygon / void geometry now preserves AEDB tuple points and arc models instead of first copying them into dict/list payloads.
- Optimized AEDB direct AuroraDB export: the exporter now accepts both object-shaped and dict-shaped geometry and uses a shorter numeric-coordinate unit-conversion fast path.
- JSON schema is unchanged; explicit semantic JSON is expected to remain equivalent except `metadata.project_version` / `metadata.parser_version`, and AuroraDB file output is unchanged.

## 1.0.8

- Integrated AuroraDB parser `0.2.9`; AEDB parser, Semantic parser, and JSON schema versions remain unchanged.
- Optimized the AuroraDB export write path: polygon / void `NetGeom` blocks now use lightweight raw blocks, reducing `AuroraBlock` / `AuroraItem` object construction.
- Optimized AuroraDB layer file writing: `layers/*.lyr` are written with bounded parallelism to reduce large-board layer-output wait time.
- JSON schema is unchanged; expected JSON content is unchanged except `metadata.project_version`, and AuroraDB file output is unchanged.

## 1.0.7

- Integrated AuroraDB parser `0.2.8`; Semantic parser remains `0.6.16`.
- Optimized AEDB direct AuroraDB output so polygon/void geometry now builds `Pnt` / `Parc` values directly instead of formatting point strings and splitting them back into block values.
- Optimized parts construction by reusing prebuilt pad, pin, shape, and footprint indexes during footprint-pad export, avoiding repeated whole-board scans on large AEDB regression samples.
- Optimized length conversion and numeric formatting with a numeric + source-unit fast path plus cached unit scales and formatted values.
- Optimized AuroraDB block writing by using chunked `writelines()` to reduce many small `write()` calls.
- JSON schemas are unchanged; expected JSON content is unchanged except for `metadata.project_version`, and AuroraDB file output should remain identical.

## 1.0.6

- Integrated AuroraDB parser `0.2.7` and Semantic parser `0.6.16`.
- Optimized the default AEDB to AuroraDB path by building `AuroraDBPackage` directly from `SemanticBoard` instead of generating in-memory AAF command lines and compiling them through the parser/executor.
- AuroraDB polygon voids, layout blocks, and parts blocks now use direct construction on the default AEDB path, while `--export-aaf` remains available for compatibility and manual regression.
- The non-AEDB in-memory AAF fallback now parses and executes exported commands incrementally instead of storing a full AAF command-object list.
- AEDB -> SemanticBoard adds optional `--skip-semantic-connectivity` for runs that do not need semantic connectivity JSON; default behavior remains unchanged.
- JSON schemas are unchanged; default output is expected to remain unchanged except for `metadata.project_version` / `metadata.parser_version`, and AuroraDB file output should remain identical.

## 1.0.5

- Integrated AuroraDB parser `0.2.6` and Semantic parser `0.6.15`.
- Optimized the default AuroraDB output path: the fast parser for exported AAF now splits option payloads by option type and skips unnecessary scans for `-g`, `-location`, `-via`, and similar single-value payloads.
- Optimized AAF execution by moving exported polygon-void container nodes into the final `PolygonHole` instead of deep-copying outline/void geometry.
- Optimized AEDB -> Semantic finalization so `with_computed_summary()` refreshes the current board summary directly instead of copying the whole board.
- Optimized AuroraDB writing so block files stream directly to disk, reducing intermediate string allocation for large files.
- JSON schemas are unchanged; expected JSON content is unchanged except for `metadata.project_version` / `metadata.parser_version`, and AuroraDB file output should remain identical.

## 1.0.4

- Integrated AuroraDB parser `0.2.5` and Semantic parser `0.6.14`.
- Optimized the default AuroraDB output path with a lighter parser for AAF command lines generated by this project, reducing generic AAF tokenizer overhead.
- Optimized AAF geometry execution so common `Line`, `Larc`, `Polygon`, and `PolygonHole` geometries directly build AuroraDB blocks before falling back to the generic parser.
- Optimized AuroraDB block write formatting and the AEDB -> Semantic hot path with formatting caches, semantic id caching, and indexed reference-list deduplication.
- JSON schemas are unchanged; expected JSON content is unchanged except for `metadata.project_version` / `metadata.parser_version`, and AuroraDB file output should remain identical.

## 1.0.3

- Integrated AuroraDB parser `0.2.4`.
- Optimized the default AuroraDB output path: when `export_aaf: false`, it now passes in-memory AAF command lines directly instead of joining full AAF text and splitting it again for parsing.
- JSON schemas are unchanged; expected JSON content is unchanged except for `metadata.project_version`, and AuroraDB file output should remain identical.

## 1.0.2

- Integrated AuroraDB parser `0.2.3`.
- Optimized the default AuroraDB output path: when `export_aaf: false`, it no longer creates temporary AAF files and instead feeds in-memory AAF command text directly into the AuroraDB translator.
- JSON schemas are unchanged.

## 1.0.1

- Integrated AuroraDB parser `0.2.2`.
- Optimized the AuroraDB target AAF command execution path with cached command option lookups and execution-time layer/net/block indexes, reducing compile overhead when exporting large boards to AuroraDB.
- The `AuroraDB` target now writes `layout.db`, `parts.db`, and `layers/` directly into the `-o` output directory by default while keeping `stackup.dat` and `stackup.json`; `aaf/` is retained only when `--export-aaf` is passed explicitly or when AAF output is chosen directly.
- JSON schemas are unchanged.

## 1.0.0

- Raised the project baseline version to `1.0.0`; future project-level changes now accumulate from this version.
- Finalized `sources -> SemanticBoard -> targets` as the only primary architecture while keeping all AEDB, ODB++, AuroraDB source, and AAF / AuroraDB target capabilities.
- Removed the no-longer-needed root compatibility import shim code so the repository keeps only the active structure and implementation files.
- Updated the README, project architecture docs, environment scripts, and machine-readable schemas to the `1.0.0` baseline.
- Integrated ODB++ parser `0.6.1` and Semantic parser `0.6.13`, focusing on performance for large ODB++ parse and semantic-build workloads.
- The full ODB++ -> Semantic -> AuroraDB flow for a large regression sample now completes in roughly 3 minutes, and the semantic-build phase dropped from roughly 44 minutes to roughly 1 minute.

## 0.7.64

- The project directory layout now formally converges on `sources / semantic / targets / pipeline / shared`, with `SemanticBoard` as the single unified intermediate model.
- Added the top-level `convert`, `inspect`, `dump`, and `schema` commands. The primary workflow is now organized around `source -> SemanticBoard -> target`, while the legacy `auroradb`, `odbpp`, and `semantic` commands remain as compatibility entrypoints.
- `semantic/aaf_export.py` has moved to `targets/auroradb/exporter.py`, while AuroraDB source reading stays under `sources/auroradb/`, making the source/target responsibility split explicit.
- `pipeline/` now owns unified loading and conversion orchestration, and `shared/` consolidates logging, runtime metrics, and JSON output helpers.
- AEDB, ODB++, AuroraDB source loading, and the AAF / AuroraDB export chain now all emit consistent runtime logs; the default log path remains `logs/aurora_translator.log`.
- `scripts/setup_env.ps1`, the README, and the architecture docs now reflect the new structure and command set.

## 0.7.63

- 集成 ODB++ parser/schema `0.6.0`。
- `crates/odbpp_parser` 现在共享同一套 Rust 解析核心，同时提供 `odbpp_parser` CLI 和 `aurora_odbpp_native` PyO3 模块。
- `parse_odbpp()`、`odbpp` CLI 以及 `semantic from-source/source-to-aaf/source-to-auroradb odbpp ...` 现在默认优先使用 native 模块；显式传入 `--rust-binary` 时会强制走 CLI。
- `scripts/setup_env.ps1` 现在会在构建 CLI 后自动通过 `maturin develop --features python` 安装 native 模块。
- ODB++ / Semantic / 项目级文档已更新为 native-first 流程；`ODBLayout.metadata.backend` 现在支持 `rust-native` 和 `rust-cli`。

## 0.7.63

- Integrated ODB++ parser/schema `0.6.0`.
- `crates/odbpp_parser` now shares one Rust parsing core and exposes both the `odbpp_parser` CLI and the `aurora_odbpp_native` PyO3 module.
- `parse_odbpp()`, the `odbpp` CLI, and `semantic from-source/source-to-aaf/source-to-auroradb odbpp ...` now prefer the native module by default; passing `--rust-binary` explicitly forces the CLI.
- `scripts/setup_env.ps1` now installs the native module through `maturin develop --features python` after building the CLI.
- The ODB++ / Semantic / project-level documentation now reflects the native-first workflow, and `ODBLayout.metadata.backend` now supports both `rust-native` and `rust-cli`.

## 0.7.62

- 集成 Semantic parser `0.6.12`。
- 新增 `semantic from-source`、`semantic source-to-aaf` 和 `semantic source-to-auroradb`，可以直接引用 AEDB、AuroraDB 或 ODB++ 源路径，不再要求先准备格式 JSON。
- `semantic from-json` / `semantic from-source` 中的 `-o/--out` 现在只表示输出目录；`semantic.json` 只有显式传入 `--semantic-output` 时才会写出。
- README 和语义层文档现在明确区分 JSON 文件流与源文件直通流程，并补充 AEDB / ODB++ 的 `semantic` 命令示例。
- Semantic JSON schema 保持 `0.6.0`。

## 0.7.62

- Integrated Semantic parser `0.6.12`.
- Added `semantic from-source`, `semantic source-to-aaf`, and `semantic source-to-auroradb` so the semantic CLI can consume AEDB, AuroraDB, or ODB++ source paths directly without requiring pre-exported format JSON.
- In `semantic from-json` / `semantic from-source`, `-o/--out` now only specifies the output directory; `semantic.json` is written only when `--semantic-output` is passed explicitly.
- The README and semantic-layer documentation now distinguish the JSON file workflow from the direct source workflow and include AEDB / ODB++ `semantic` command examples.
- Semantic JSON schema remains `0.6.0`.

## 0.7.61

- 集成 Semantic parser `0.6.11`；`write_aaf_from_semantic()` 不再在输出根目录写入重复的 `design.layout` / `design.part`，只保留 `aaf/` 下的 AAF 文件。
- 如果复用旧输出目录，导出器现在会主动删除根目录残留的旧版 `design.layout` / `design.part` 副本，避免误判为当前导出结果。
- `semantic to-auroradb` 的默认输出语义保持不变：`auroradb/` 继续默认生成，`aaf/` 仅作为过渡目录保留。
- Semantic JSON schema 保持 `0.6.0`；本次只调整导出行为和默认输出结构，不新增 semantic 字段。

## 0.7.60

- 集成 AEDB parser `0.4.46`；heartbeat 缩进进度块会在完成日志前完全输出，避免后台进度线程把 `completed` 行插入到缩进块中间。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.59` / AEDB parser `0.4.45` 一致。

## 0.7.61

- Integrated Semantic parser `0.6.11`; `write_aaf_from_semantic()` no longer writes duplicate root-level `design.layout` / `design.part`, and keeps the AAF files only under `aaf/`.
- When reusing an existing output directory, the exporter now deletes stale root-level `design.layout` / `design.part` leftovers so they are not mistaken for current output.
- The default `semantic to-auroradb` behavior is unchanged: `auroradb/` is still generated by default, while `aaf/` remains the transitional package directory.
- Semantic JSON schema remains `0.6.0`; this change only adjusts export behavior and default output layout.

## 0.7.59

- 集成 Semantic parser `0.6.10`；Aurora/AAF 导出现在会在多个 component 共享同一个 part name 但使用不同 footprint 时生成 footprint-specific part 变体。
- ODB++ 内层 short-cline component，例如 `n/a` + `SHORT_CLINE-LAYER2`，现在会引用自己的导出 part，不再折叠到 `SHORT_CLINE-TOP` part。
- 根目录兼容副本 `design.layout` / `design.part` 现在会与 `aaf/design.layout` / `aaf/design.part` 同步刷新，避免复用输出目录时留下过期 AAF 文件。
- Semantic JSON schema 保持 `0.6.0`；本次只调整转换行为和 metadata 默认版本，不新增 semantic 字段。

## 0.7.58

- 集成 AEDB parser `0.4.45`；解析日志不再输出详细 profile 明细，只保留“解析对象 + 数量”的缩进摘要。
- 长耗时阶段的 heartbeat 和 progress 日志改为缩进字段块，继续显示已处理数量、百分比、耗时、速率和 RSS。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.56` / AEDB parser `0.4.44` 一致。

## 0.7.56

- 集成 Semantic parser `0.6.9`；ODB++ component placement layer 现在优先由已解析 pin pad 的共同金属层推导，因此所有 pin/pad 都在 `LAYER7` 的器件会导出到 `COMP_LAYER7`。
- ODB++ semantic pin 在其所有 pad 位于同一金属层时继承真实 pad layer，避免内层 pin 集合被回退到 top/bottom component layer。
- Semantic JSON schema 保持 `0.6.0`；本次只调整转换行为和 metadata 默认版本，不新增 semantic 字段。

## 0.7.55

- 集成 AEDB parser `0.4.44`；padstack record profile 现在在 `Build padstack instance records` 阶段完成后输出，避免 heartbeat 插入到缩进字段块中。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.54` / AEDB parser `0.4.43` 一致。

## 0.7.54

- 集成 AEDB parser `0.4.43`；当 padstack batch snapshot 统计与总 snapshot 统计完全一致时，不再重复输出 `Batch snapshot totals` 区块。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.53` / AEDB parser `0.4.42` 一致。

## 0.7.53

- 集成 AEDB parser `0.4.42`；解析日志中的 profile 统计改为“标题 + 缩进字段”的分组排版，减少重复输出 `Path profile`、`Polygon profile`、`Padstack record profile` 等前缀。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.52` / AEDB parser `0.4.41` 一致。

## 0.7.52

- 集成 Semantic parser `0.6.8`；ODB++ component、pad 和 package pin rotation 在导出 Aurora/AAF 时按 ODB++ Design Format Specification 的“正角为顺时针”语义处理。
- ODB++ fallback footprint pad 推导现在使用顺时针角度的逆变换，修复旋转器件在缺少 package pin geometry 或输出绝对 pin pad 时的方向问题。
- Semantic JSON schema 保持 `0.6.0`；本次只调整导出行为，不新增 Semantic payload 字段。

## 0.7.51

- 集成 AEDB parser `0.4.41`；细化大型 AEDB 回归样本的长阶段进度日志，避免父阶段 heartbeat 与 primitive 进度日志重复刷屏。
- primitive 进度日志增加最小输出间隔，保留 `processed/total`、百分比、速率和 RSS，但减少连续相邻进度行。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.50` / AEDB parser `0.4.40` 一致。

## 0.7.50

- 集成 AEDB parser `0.4.40`；长时间运行的解析阶段现在会自动输出 heartbeat，避免大型 AEDB 回归样本在阻塞阶段长时间没有日志。
- `log_timing` 默认每 10 秒输出一次 `is still running`，包含已运行秒数和当前进程 RSS。
- path、polygon、zone primitive 序列化新增 `processed/total`、百分比、速率和 RSS 进度日志。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.49` / AEDB parser `0.4.39` 一致。

## 0.7.49

- 集成 AEDB parser `0.4.39`；整理 AEDB parser log 和 analysis log 的排版。
- 普通 parser log 新增 `Input configuration`、`AEDB parsing`、`Analysis output`、`Run summary` 分区，减少配置、解析、输出信息混在一起的问题。
- analysis log 现在先输出顶层阶段汇总，再按阶段开始顺序输出详细阶段树，父阶段会显示在子阶段之前。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.47` / AEDB parser `0.4.38` 一致。

## 0.7.48

- 集成 Semantic parser `0.6.7`；ODB++ 中位于 signal/plane 层的正极性无 net trace/arc/polygon primitive 现在会自动提升为 AuroraDB `NoNet` 几何。
- `PROFILE`/非布线层绘图和 negative/cutout primitive 仍保留为 coverage-only，不混入 `NoNet`。
- Semantic JSON schema 保持 `0.6.0`；本次只修正 ODB++ 到 AuroraDB 的 no-net 图形映射。

## 0.7.47

- 集成 AEDB parser `0.4.38`；AEDB CLI 解析完成后会自动保存一份独立的分析日志，汇总各阶段耗时和进程 working set 内存采样。
- 新增 `--analysis-log-file` 参数用于指定分析日志路径；默认输出到 JSON 文件同目录的 `<json_stem>_analysis.log`。
- AEDB JSON schema 保持 `0.4.0`；输出 JSON 字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.46` / AEDB parser `0.4.37` 一致。

## 0.7.46

- 集成 Semantic parser `0.6.6`；ODB++ 保留无网络名（`$NONE$`、`$NONE`、`NONE$`、`NoNet`）现在会规范化为 AuroraDB 可识别的 `NoNet` keyword。
- 集成 AuroraDB parser `0.2.1`；Aurora/AAF 到 AuroraDB 编译时保留 `NoNet` 的大小写，不再把它写成普通大写网络名 `NONET`。
- Semantic JSON schema 保持 `0.6.0`；本次只修正 ODB++ no-net 映射和 AuroraDB 输出命名。

## 0.7.45

- 集成 AEDB parser `0.4.37`，为 padstack instance record 构建增加 `.NET` batch snapshot 路径，一次读取全部 instance 的基础字段、位置、层范围和 padstack definition。
- 保留逐个 snapshot/PyEDB fallback；新增批量 snapshot 命中、回退和耗时日志，用于确认优化路径是否生效。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.44` / AEDB parser `0.4.36` 一致。

## 0.7.44

- 集成 Semantic parser `0.6.5`；Aurora/AAF polygon void 导出现在支持 ODB++ 用起点等于终点的一条 `OC` 弧表达的整圆 hole。
- 这类整圆 void 会拆成两段 `Parc` 半圆顶点写入 `PolygonHole`，避免因少于 3 个 polygon vertex 被跳过。
- Semantic JSON schema 保持 `0.6.0`；本次只修正 AuroraDB 输出中的 void 几何表达。

## 0.7.43

- 集成 AEDB parser `0.4.36`，为 padstack definition 增加 `.NET` batch snapshot 路径，一次读取 definition 基础字段、hole/via 信息和三类 layer pad property。
- 保留 PyEDB wrapper fallback；新增 snapshot 命中/回退和耗时日志，用于确认优化路径是否生效。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.42` / AEDB parser `0.4.35` 一致。

## 0.7.42

- 集成 AEDB parser `0.4.35`，为 padstack definition 序列化新增聚合 profiling，拆分字段读取、layer map、PadPropertyModel 和 PadstackDefinitionModel 构建耗时。
- AEDB JSON schema 保持 `0.4.0`；本次只输出诊断日志，不新增 JSON 字段。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.41` / AEDB parser `0.4.34` 一致。

## 0.7.41

- 集成 AEDB parser `0.4.34`，优化 polygon/void arc 构建中的 `ArcModel` 快速构造路径，减少纯 Python 对象构建开销。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.39` / AEDB parser `0.4.33` 一致。

## 0.7.40

- 集成 Semantic parser `0.6.4`；ODB++ point feature 的 `orient_def` 现在按 ODB++ pad orientation 规则解释，包括 legacy `4..7` mirror rotation 和 `8/9 <angle>` 任意角度。
- ODB++ pad mirror flag 现在会保留到 Aurora/AAF pad 与 footprint-pad 输出中，footprint pin rotation 也会使用源 pad orientation，而不是只按 component placement rotation 推导。
- Semantic JSON schema 保持 `0.6.0`；本次只填充已有 pad geometry hint 和 AAF transform option，不新增 semantic 字段。

## 0.7.39

- 集成 AEDB parser `0.4.33`，为 path 面积 fallback 增加按原因、corner style、end cap style 和 center-line 点数 bucket 汇总的 profiling。
- 本次用于定位后续减少 path `GetPolygonData()` 时间的优化入口；AEDB JSON schema 保持 `0.4.0`。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.37` / AEDB parser `0.4.32` 一致。

## 0.7.38

- 集成 Semantic parser `0.6.3`；ODB++ component pin 映射现在优先使用 EDA net 中真实 component index + pin index 关联，再回退到 component 文件 pin 行里的引用字段。
- ODB++ 写入 `design.part` 的 footprint pad rotation 现在会按 component placement 相同规则归一化，避免出现 `450` / `540` / `630` 这类异常角度。
- Semantic JSON schema 保持 `0.6.0`；本次修正 ODB++ 转换行为，不新增 semantic 字段。

## 0.7.37

- 集成 AEDB parser `0.4.32`，新增 `.NET PrimitiveWithVoidsGeometrySnapshot` 批量路径，一次读取 polygon 主体和全部 void 的几何数据。
- polygon/void 的 arc 构建仍保留在 Python 侧；AEDB JSON schema 保持 `0.4.0`。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.35` / AEDB parser `0.4.31` 一致。

## 0.7.36

- 集成 Semantic parser `0.6.2`；ODB++ via template 现在会在可匹配时从负极性 pad feature 推断 layer antipad，包括 via 位置上的 no-net negative pad primitive。
- ODB++ conversion coverage 新增 semantic via template antipad 数和 layer antipad entry 总数。
- Semantic JSON schema 保持 `0.6.0`；本次只填充既有 `SemanticViaTemplateLayer.antipad_shape_id`，不新增字段。

## 0.7.35

- 集成 AEDB parser `0.4.31`，对无 arc、两点直线 path 使用解析面积公式，减少 AEDB `GetPolygonData()` 调用次数。
- 复杂 path 仍使用 AEDB 原生 polygon area；AEDB JSON schema 保持 `0.4.0`。
- JSON 内容变化：直线 path 的 `area` 可能存在浮点尾数级差异，布局点、线宽、长度、bbox 和数量统计不变。

## 0.7.34

- 集成 Semantic parser `0.6.1`；ODB++ surface polygon 现在会使用 contour polarity（`I` island / `H` hole），把多 island 的 `S` feature 拆成多个 semantic polygon primitive，并把 hole contour 归到对应 island。
- ODB++ conversion coverage 新增 source multi-island surface 数、source hole contour 数、semantic split-surface polygon 数和 semantic polygon void 数。
- Semantic JSON schema 保持 `0.6.0`；本次只细化转换行为和 coverage 报告，不新增 semantic 模型字段。

## 0.7.33

- 集成 ODB++ parser/schema `0.5.0`，新增 selected-step layer `attrlist` 字段，以及 drill tools 顶层 metadata，例如 `THICKNESS` 和 `USER_PARAMS`。
- 集成 Semantic parser/schema `0.6.0`；ODB++ layer attributes 现在会进入 Semantic stackup material/thickness，via template 会用匹配到的 signal-layer pad 细化，component/package 属性也会保留给统一模型和 AuroraDB part 导出。
- ODB++ 转 AuroraDB 现在会把 part attributes 写入 `parts.db`，并在可用时用 ODB++ copper/dielectric thickness 生成 `stackup.dat` / `stackup.json`。
- 集成 AEDB parser `0.4.30`，新增 `.NET PadstackInstanceSnapshot` helper，将 padstack instance 多字段读取合并为一次底层调用以减少解析耗时。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.32` / AEDB parser `0.4.29` 一致。

## 0.7.32

- 集成 AEDB parser `0.4.29`，为 padstack instance record 构建新增字段级 profiling 日志，方便定位 padstack 解析耗时瓶颈。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.31` / AEDB parser `0.4.28` 一致。

## 0.7.31

- 集成 AEDB parser `0.4.28`，polygon 和 void 的 arc 构建改用 AEDB 内部 fast ArcModel 构造器，减少 120 万级 arc 模型构建开销。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.30` / AEDB parser `0.4.27` 一致。

## 0.7.30

- 集成 AEDB parser `0.4.27`，path primitive 的 `bbox` 改为由 center-line bbox 加上线宽扩展推导，避免为 bbox 再调用 path polygon data 的 `GetBBox()`。
- path primitive 的 `area` 仍使用 AEDB 原始 `GetPolygonData().Area()`，保证圆角、转角和端帽结果不变；AEDB JSON schema 保持 `0.4.0`。
- 集成 Semantic parser `0.5.3`；ODB++ 转 AuroraDB 时，component part 现在只映射到真实 package/footprint symbol，不再额外生成以 part number 命名的空 footprint。
- ODB++ coverage 现在会把 component placement 命令和 component pin/net 绑定分开统计。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.29` / AEDB parser `0.4.26` 一致。

## 0.7.29

- 集成 AEDB parser `0.4.26`，为 path primitive 序列化新增聚合 profiling 日志，拆分 center-line 读取、length 计算、base metadata、字段归一化和模型构建耗时。
- profiling 只输出汇总日志，不新增 JSON 字段，也不改变解析内容。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.28` / AEDB parser `0.4.25` 一致。

## 0.7.28

- 集成 AEDB parser `0.4.25`，polygon 和 void 的几何读取新增 `.NET GeometrySnapshot` 批量路径，一次返回 `raw_points`、`bbox` 和 `area`，减少 Python/.NET 往返调用。
- polygon profiling 日志新增 `geometry_snapshot` 汇总耗时；arc 构建逻辑保持 Python 侧原公式，避免引入浮点末位差异。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.27` / AEDB parser `0.4.24` 一致。

## 0.7.27

- 集成 AEDB parser `0.4.24`，新增运行时编译和加载的 `.NET` polygon point extractor，把 `PolygonData.GetPoint()`、`PointData.X/Y.ToDouble()` 的逐点读取移到 .NET 侧批量执行，并以 `double[]` 返回给 Python。
- polygon、void 和 path center-line 读取优先使用批量 helper；若 C# 编译、加载或调用失败，会自动回退到原 Python `PolygonData.Points` 路径。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.25` / AEDB parser `0.4.23` 一致。
- 集成 Semantic parser `0.5.2`；ODB++ 无 net 绘图 primitive 保留在 Semantic coverage 中，但默认不再导出为 Aurora/AAF `ODBPP_DRAWING` logic geometry。

## 0.7.26

- 集成 Semantic parser `0.5.1`；ODB++ package definitions 现在都会进入 `SemanticFootprint`，包括选定 step 中没有被 component 实例引用的 package body。
- ODB++ 中无 net、但位于可布线层的绘图 primitive 会进入 Semantic coverage 统计，同时避免为机械/绘图线、弧、面和 pad 虚构 net。
- ODB++ coverage 报告新增 semantic drawing primitive、AAF logic geometry、带 outline 的源 package、package body 导出覆盖率等独立计数。
- Semantic JSON schema 保持 `0.5.0`；未新增 schema 字段。

## 0.7.25

- 集成 AEDB parser `0.4.23`，polygon/void arc 构建从“先生成 `vertices` 与 `edge_heights` 中间列表再二次遍历”改为基于已读取 raw points 的单遍 ArcModel 构建。
- 保留 `.NET PolygonData.Points` 先物化为 Python list 的稳定读取方式，避免重复 `0.4.20` 中直迭代 `.NET Points` 变慢的问题。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.24` / AEDB parser `0.4.22` 一致。

## 0.7.24

- 集成 AEDB parser `0.4.22`，为 polygon primitive 序列化增加聚合 profiling 日志，拆分统计 polygon/void 的 `.NET` 数据读取、raw points、arc 构建、area、bbox、metadata 和模型构建耗时。
- profiling 只输出汇总日志，不新增 JSON 字段，也不改变解析内容。
- AEDB JSON schema 保持 `0.4.0`。
- JSON 内容变化：除版本 metadata 外，payload 预期与 `0.7.23` / AEDB parser `0.4.21` 一致。

## 0.7.23

- 集成 AEDB parser `0.4.21`，撤回 `0.4.20` 中 polygon raw points 直迭代和单遍 arc 构建实验。
- 大型 AEDB 回归样本实测 `0.4.20` 的 polygon 阶段更慢，因此当前实现恢复到 `.NET Points` 先转列表、再按 `vertices/edge_heights` 构建 arc 的稳定路径。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，预期与 `0.4.20` 和 `0.4.19` 内容一致；该版本主要记录性能实验撤回。

## 0.7.22

- 集成 AEDB parser `0.4.20`，polygon 和 void 的 raw points 读取不再先创建临时 `.NET list`，而是直接迭代 `PolygonData.Points`。
- polygon/void arc 模型现在从 raw points 单次流式构建，避免额外生成 `vertices` 和 `edge_heights` 中间列表后再二次遍历。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，polygon、void、arc、path、component、padstack、net 等字段和数量预期不变。
- 集成 Semantic parser/schema `0.5.0`；Semantic JSON 现在包含 `board_outline`、footprint/package `geometry`、via-template geometry 和 via instance geometry hints，方便后续统一模型访问。
- ODB++ 到 AuroraDB 现在会优先使用解析出的 profile 几何生成 board outline，包括 profile arc 边；有 profile 数据时不再退回 bbox outline。
- ODB++ package outline/body 记录现在会导出到 `design.part` 的 footprint geometry；drill tool metadata 在可匹配 drill symbol 时会保留到 semantic via template 和 via instance。
- 新增 `odbpp coverage` 与 `odbpp to-auroradb --coverage-output`，用于生成源 ODB++、Semantic、AAF、AuroraDB 多层对象覆盖率报告。

## 0.7.21

- 集成 AEDB parser `0.4.19`，path primitive 的 `length` 默认从已读取的 center-line raw points 和 arc-height marker 直接计算，避免为每条 path 再调用 `.NET PolygonData.GetArcData()`。
- `.NET GetArcData()` 仍保留为 raw center-line points 不可用时的回退路径。
- AEDB JSON schema 保持 `0.4.0`；输出字段不变。
- JSON 内容变化：除版本 metadata 外，path `length` 可能只出现浮点尾数级差异；path、polygon、component、padstack、net 等数量统计预期不变。

## 0.7.20

- 集成 Semantic parser `0.4.7`；ODB++ surface contour 中的 `OC` arc 记录现在会保留到 semantic polygon geometry，并导出为 Aurora/AAF 5 值 polygon arc 顶点，编译到 AuroraDB 后成为 `Parc`。
- ODB++ 独立 `A` arc feature 现在会转换为 semantic arc primitive；当源 arc 有 net 且可解析出正的圆形 symbol 线宽时，会导出为 `Larc` net geometry。
- 对私有 ODB++ 样本执行 ODB++ 到 AuroraDB 转换时，现在可得到 `polygon_primitives_with_arcs=1255`、`polygons_with_void_arcs=80`、`voids_with_arcs=1915`，生成的 AuroraDB layer 文件包含 `Parc` 曲线 polygon 边。
- Semantic JSON schema 保持 `0.4.0`；schema 默认的 `metadata.parser_version` 现在为 `0.4.7`。

## 0.7.19

- 集成 AEDB parser `0.4.18`，默认使用 component pin 绝对坐标的 bbox center 计算 `component.center`，不再为 component center 默认调用 AEDB `.NET LayoutObjInstance` 接口。
- 新增 AEDB CLI 参数 `--component-center-source {pin-bbox,layout-instance}`；默认 `pin-bbox`，需要和底层接口对照时可显式选择 `layout-instance`。
- JSON 输出结构保持 AEDB schema `0.4.0`；`component.center` 的语义仍是 component 中心坐标，计算来源从 layout instance 改为 pin bbox center。
- JSON 内容变化：默认计算版不再输出 layout-instance 得到的 `component.bounding_box`，该字段输出为 `null`；component、pin、padstack、primitive、net 等数量统计不变。

## 0.7.18

- 集成 ODB++ parser `0.4.0` 和 ODB++ JSON schema `0.4.0`。
- ODB++ 解析现在会导出选定 step 的 `drill_tools[]`（来自 layer `tools` 文件）和 `packages[]`（来自 EDA package definitions），并保留 package pins 与常见 package geometry records。
- 集成 Semantic parser `0.4.6`；ODB++ 转换现在按 drill layer + symbol 构建 via template，基于 matrix start/end layer 保留 via layer span，并使用 package pin geometry 作为 component pad 的回退来源。
- 修正 ODB++ surface polarity 与 point feature orientation 处理，surface record 不再把 polarity 当成 symbol，pad geometry 会分别保留 dcode 与 orientation。
- 使用私有 ODB++ 样本转换后，AuroraDB 输出统计为 `components=522`、`parts=86`、`shapes=119`、`vias=10`、`net_geometries=61145`；522 个 component 现在都具备 pad 绑定。

## 0.7.17

- 修正 AEDB -> AuroraDB 的 component placement rotation：Aurora/AAF 导出现在会根据 pad 拓扑反推 component 朝向，而不再直接信任 AEDB 原始 component transform rotation；在部分设计里该原始值会整板保持 `0`。
- 当同一个 AEDB `part_name` 对应到不兼容的 pin 集合或 pad 拓扑变体时，Aurora/AAF 导出现在会拆分独立的 part/footprint variant，避免 component library footprint 和实例几何错位。
- 集成 ODB++ parser `0.3.0` 和 ODB++ JSON schema `0.3.0`。
- ODB++ 解析现在会导出 `symbols[]`，来源为 `symbols/<name>/features`，用于保留非矩形 pad 的自定义 symbol surface contour。
- ODB++ EDA `FID` 记录现在保留其关联的 `SNT TOP T/B` pin 上下文，从而能把 component pin 绑定到准确的铜皮 pad feature。
- 集成 Semantic parser `0.4.5`；ODB++ 转换现在会输出 component-owned pad、footprint pad geometry，并修正 ODB++ 角度从“度”到 exporter 内部“弧度”的转换。
- 修正 polygon shape 导出，确保第一个 polygon 值保持为顶点数量，不再被当成长度做单位转换。
- 使用私有 ODB++ 样本转换后，AuroraDB 输出统计为 `components=522`、`parts=86`、`shapes=118`、`vias=5`、`net_geometries=61141`。

## 0.7.16

- 集成 AEDB parser `0.4.17`，将 component center、component bounding box、padstack/pin position 的坐标序列化精度从米单位 6 位小数提升到 9 位小数。
- 该调整用于降低通过 pin bbox center 推导 component 坐标时的舍入误差；rotation 精度保持 6 位小数。
- AEDB JSON schema 保持 `0.4.0`；字段结构和数量统计不变。
- JSON 内容变化：component 与 pin/padstack 相关坐标会输出更多小数位，旧版约 `0.039 mil` 的 pin-derived center 舍入误差可下降到更低量级。
- 集成 Semantic parser `0.4.4`，修复 ODB++ semantic adapter 中 Python 3.12 泛型函数语法导致 Python 3.10 CLI 导入失败的问题；Semantic JSON 输出结构保持 `0.4.0`。

## 0.7.15

- 集成 AEDB parser `0.4.16`，恢复 component layout geometry 提取，确保 AEDB component 的 `center` 和 `bounding_box` 继续输出。
- 修正 AEDB parser `0.4.15` 跳过 component geometry 后，许多 component 只能回退到 `[0.0, 0.0]` 的 `location`，导致 Semantic 和 AuroraDB component 坐标错误的问题。
- JSON 输出结构保持 AEDB schema `0.4.0`；新生成 AEDB payload 中，`metadata.project_version` 输出 `0.7.15`，`metadata.parser_version` 输出 `0.4.16`。
- JSON 内容变化：相比 AEDB parser `0.4.15`，`component.center` 和 `component.bounding_box` 从 `null` 恢复为 AEDB layout instance 的实际坐标；字段结构和数量统计不变。

## 0.7.14

- 集成 ODB++ parser `0.2.0` 和 ODB++ JSON schema `0.2.0`。
- ODB++ 解析现在保留 feature index/ID、feature 属性、surface contour、组件 pin、组件属性，以及 EDA net 到 feature/pin 的引用关系。
- ODB++ semantic adapter 现在可以为 AuroraDB 导出推导 shape、trace、polygon、pad、via、footprint、pin 和 net connectivity。
- 新增 `odbpp to-auroradb`，可直接把 ODB++ 目录/归档转换为 Aurora/AAF 与 AuroraDB，并可选输出中间 JSON。
- `semantic to-auroradb` 现在可以从 ODB++ 样例生成非空 AuroraDB 几何；私有 ODB++ 样本转换后为 `shapes=116`、`vias=5`、`net_geometries=60515`。
- Semantic parser 更新为 `0.4.3`；Semantic JSON schema 保持 `0.4.0`。

## 0.7.12

- 集成 AEDB parser `0.4.15`，跳过 component layout geometry 提取，避开较慢的 `.NET LayoutInstance.GetLayoutObjInstance(...)` 路径。
- 新生成的 AEDB payload 仍保留 component 记录和 pins，但所有 component 的 `center` 与 `bounding_box` 现在输出为 `null`。
- 在大型 AEDB 回归样本上，AEDB layout 解析从约 `241.294s` 降到 `144.984s`。
- AEDB JSON schema 保持 `0.4.0`；新生成的 payload 中，`metadata.project_version` 输出 `0.7.12`，AEDB payload 的 `metadata.parser_version` 输出 `0.4.15`。

## 0.7.11

- 集成 Semantic parser `0.4.2`，AEDB polygon 和 polygon void 的 arc 几何会保留到 Semantic，并在 Aurora/AAF 中输出为 polygon arc 顶点。
- polygon 和 void 的弧线方向沿用现有 AEDB->AAF 约定：AEDB arc height 为负时输出方向 `Y`，为正时输出 `N`；缺少 height 时才用 `is_ccw` 兜底。
- 新增 PowerShell 环境配置与清理脚本，便于准备本地环境和整理待推送的工作区。
- 移除重复的窄口径 board-model 访问层和 ODB++ board-summary adapter；跨格式转换统一依赖更完整的 Semantic 模型。
- 集成 AEDB parser `0.4.14`，缓存 polygon void 几何记录，让 parent polygon 面积计算和 void 序列化复用同一次底层几何提取。
- Semantic JSON schema 保持 `0.4.0`；新生成的 payload 中，`metadata.project_version` 输出 `0.7.11`，Semantic payload 的 `metadata.parser_version` 输出 `0.4.2`。

## 0.7.10

- 集成 AEDB parser `0.4.13`，polygon 和 polygon void 的 arc 几何改为从 raw `.NET PolygonData.Points` 中的 arc-height 标记推导，不再对每个 polygon 调用 `PolygonData.GetArcData()`。
- AEDB JSON 结构和数量统计不变；和 `0.4.12` 相比，arc 数值只可能存在浮点尾数级差异。
- AEDB JSON schema 保持 `0.4.0`；新生成的 AEDB payload 中，`metadata.project_version` 输出 `0.7.10`，`metadata.parser_version` 输出 `0.4.13`。

## 0.7.9

- 集成 AEDB parser `0.4.12`，raw `.NET` padstack placement layer 继续按旧版规则输出空字符串而不是 `null`。
- 新生成的 AEDB JSON payload 中，`metadata.project_version` 现在输出 `0.7.9`，`metadata.parser_version` 现在输出 `0.4.12`。
- AEDB JSON schema 保持 `0.4.0`；AuroraDB、ODB++ 和 Semantic 的 parser/schema 版本不变。

## 0.7.8

- Semantic 到 Aurora/AAF 的导出逻辑参考 AEDB->AAF 程序重新对齐：trace 宽度会转成 Circle shape，center line 中的圆弧点会转成 `Larc`，不再把线宽塞进 `Line` 参数。
- `design.layout` 现在会输出 pin pad 的铜皮 shape placement，并保留 net、layer、location、rotation 语义。
- `design.part` 现在会输出 footprint pad template、pad geometry 和 footprint pin placement，用于恢复 part/footprint/pad/pin 之间的对象关系。
- 新增跨格式语义映射表文档，说明 AEDB、Semantic、Aurora/AAF、AuroraDB 和 ODB++ 之间的对象级转换关系。
- AEDB parser 版本更新为 `0.4.11`；Semantic parser 版本保持 `0.4.1`，Semantic JSON schema 版本保持 `0.4.0`。
- 新生成的 AEDB、AuroraDB、ODB++ 和 Semantic JSON payload 中，`metadata.project_version` 现在输出 `0.7.8`。

## 0.7.7

- 集成 AEDB parser `0.4.10`，从 raw `pedb.active_layout` `.NET` 集合读取 padstack instances 和 layout primitives。
- AEDB JSON schema 保持 `0.4.0`；该版本保留为 raw 集合优化的中间回归输出。
- 该中间版本新生成的 payload 中，`metadata.project_version` 输出 `0.7.7`。

## 0.7.6

- Aurora/AAF 导出现在会把 Semantic component 写成 layout component，把 Semantic pin 写成 net pin 连接。
- Aurora/AAF 导出现在会把 Semantic trace 和 polygon primitive 写成 AuroraDB net geometry；带 void 几何的 polygon 会输出为 PolygonHole。
- AEDB 解析器新增 polygon void 几何输出，AEDB 到 Semantic primitive 转换会保留 polygon 的 `is_void`、`void_ids` 与 `voids`。
- Semantic parser 版本更新为 `0.4.1`，Semantic JSON schema 版本保持 `0.4.0`。
- AEDB parser 版本更新为 `0.4.9`，AEDB JSON schema 版本更新为 `0.4.0`。
- 新生成的 AEDB、AuroraDB、ODB++ 和 Semantic JSON payload 中，`metadata.project_version` 现在输出 `0.7.6`。

## 0.7.5

- Semantic 模型新增 AuroraDB-profile shapes 和 via templates，用于表达 AuroraDB `ShapeList` 与 `ViaList` 所需的几何语义。
- AEDB 到 Semantic 转换新增 padstack 几何归一化，Circle/Rectangle/RoundedRectangle 等 pad、antipad 和 drill hole 会转换为 semantic shape。
- Aurora/AAF 导出会把 semantic shape 写为 `layout add -g`，把 via template 写为 `layout add -via`，并输出 via instance 的 net 连接。
- 新增 AEDB 到 Semantic 转换说明文档。
- Semantic parser 和 Semantic JSON schema 版本更新为 `0.4.0`。
- 新生成的 AEDB、AuroraDB、ODB++ 和 Semantic JSON payload 中，`metadata.project_version` 现在输出 `0.7.5`。
- AEDB、AuroraDB 和 ODB++ JSON schema 版本不变。

## 0.7.4

- 集成 AEDB 解析器 `0.4.8` 优化到当前项目版本。
- Semantic 模型新增 materials 语义对象和 layer material 引用，AEDB dielectric 可携带介电常数、损耗角正切和厚度进入统一模型。
- `semantic to-aaf` / `semantic to-auroradb` 现在输出 Aurora/AAF 转换包：`design.layout`、`design.part`、`stackup.dat` 和 `stackup.json`；`to-auroradb` 会额外生成 AuroraDB 子目录。
- Semantic JSON schema 版本更新为 `0.3.0`。
- 新生成的 AEDB、AuroraDB、ODB++ 和 Semantic JSON payload 中，`metadata.project_version` 现在输出 `0.7.4`。
- AEDB、AuroraDB 和 ODB++ JSON schema 版本不变。

## 0.7.3

- 集成 AEDB 解析器 `0.4.7` 优化到当前项目版本。
- 新生成的 AEDB、AuroraDB、ODB++ 和 Semantic JSON payload 中，`metadata.project_version` 现在输出 `0.7.3`。
- 各格式 JSON schema 版本不变。

## 0.7.2

- 集成 AEDB 解析器 `0.4.6` 优化到当前项目版本。
- 新生成的 AEDB、AuroraDB、ODB++ 和 Semantic JSON payload 中，`metadata.project_version` 现在输出 `0.7.2`。
- 各格式 JSON schema 版本不变。

## 0.7.1

- 集成 AEDB 解析器 `0.4.5` 优化到当前项目版本。
- 新增 `semantic to-auroradb` 初始入口，用于从统一语义模型输出 Aurora 侧转换结果。
- Semantic parser 版本更新为 `0.3.0`，Semantic JSON schema 版本保持 `0.2.0`。
- 新生成的 AEDB、AuroraDB、ODB++ 和 Semantic JSON payload 中，`metadata.project_version` 现在输出 `0.7.1`。
- 各格式 JSON schema 版本不变。

## 0.7.0

- 集成 AEDB 解析器 `0.4.4` 优化到当前项目版本。
- 扩展 semantic 语义层，新增 footprint、pad 语义对象及 summary 计数。
- AEDB、AuroraDB 和 ODB++ semantic adapter 现在会在可追溯字段可用时建立 component-footprint、component-pad、footprint-pad、pin-pad 和 pad-net 关系。
- 新增 semantic 连接一致性诊断，用于报告已存在引用指向缺失对象的情况。
- Semantic parser 和 Semantic JSON schema 版本更新为 `0.2.0`。
- 新生成的 AEDB、AuroraDB、ODB++ 和 Semantic JSON payload 中，`metadata.project_version` 现在输出 `0.7.0`。

## 0.6.2

- 集成 AEDB 解析器 `0.4.4` 优化到项目版本。
- 新生成的 AEDB、AuroraDB、ODB++ 和 Semantic JSON payload 中，`metadata.project_version` 现在输出 `0.6.2`。
- 各格式 JSON schema 版本不变。

## 0.6.1

- 集成 AEDB 解析器 `0.4.3` 优化到项目版本。
- 新生成的 AEDB、AuroraDB、ODB++ 和 Semantic JSON payload 中，`metadata.project_version` 现在输出 `0.6.1`。
- 各格式 JSON schema 版本不变。

## 0.6.0

- 新增跨格式 semantic 语义层，提供 `SemanticBoard` 统一语义模型。
- 新增 AEDB、AuroraDB、ODB++ 到 semantic 模型的 adapter。
- 新增基础 connectivity edge 生成逻辑。
- 新增 `aurora-translator semantic from-json` 和 `aurora-translator semantic schema` CLI。
- 新增 `semantic/docs/` 下的架构说明、JSON 字段说明、变更记录和 schema 变更记录。
- 新生成的 AEDB、AuroraDB、ODB++ 和 Semantic JSON payload 中，`metadata.project_version` 现在输出 `0.6.0`。

## 0.5.4

- 新增根目录项目架构文档，并整理为当前的中英双语文件：`docs/architecture.md`。
- 明确项目级模块边界、各格式自有 schema 归属、版本职责和新格式扩展流程。
- 新生成的 AEDB、AuroraDB 和 ODB++ JSON payload 中，`metadata.project_version` 现在输出 `0.5.4`。
- 各格式 parser 版本和 JSON schema 版本不变。

## 0.5.3

- 集成 AEDB 解析器 `0.4.2` 优化到项目版本。
- 新生成的 AEDB、AuroraDB 和 ODB++ JSON payload 中，`metadata.project_version` 现在输出 `0.5.3`。
- AEDB JSON schema 不变。

## 0.5.2

- 集成 AEDB 解析器 `0.4.1` 优化到项目版本。
- 新生成的 AEDB、AuroraDB 和 ODB++ JSON payload 中，`metadata.project_version` 现在输出 `0.5.2`。
- AEDB JSON schema 不变。

## 0.5.1

- 新增与 AEDB `models.py` 风格一致的 AuroraDB Pydantic 结构化模型。
- `auroradb export-json` 现在输出结构化 AuroraDB 模型，包含 layout、layers、nets、parts、footprints、pads 和 geometry references。
- 新增 `--include-raw-blocks`，可在结构化模型旁保留原始 AuroraDB block tree。
- AuroraDB 解析器版本和 JSON schema 版本更新为 `0.2.0`。
- 新增基于 Rust `crates/odbpp_parser` CLI 的 ODB++ 解析器集成。
- 新增 ODB++ 格式级版本常量：`ODBPP_PARSER_VERSION` 和 `ODBPP_JSON_SCHEMA_VERSION`。
- 新增 ODB++ JSON metadata 字段，并通过 `aurora-translator odbpp schema` 支持 schema 导出。
- 新增机器可读 ODB++ JSON schema 文档：`odbpp/docs/odbpp_schema.json`。
- 新增窄口径共享 `board_model` 访问模型和 ODB++ adapter，为后续跨格式统一访问预留入口。
- 新生成的 AEDB、AuroraDB 和 ODB++ JSON payload 中，`metadata.project_version` 现在输出 `0.5.1`。

## 0.4.1

- 集成 AEDB 解析器 `0.4.0` 优化到项目版本。
- 新生成的 AEDB 和 AuroraDB JSON payload 中，`metadata.project_version` 现在输出 `0.4.1`。
- AEDB JSON schema 不变。

## 0.4.0

- 新增 AuroraDB 格式级版本常量：`AURORADB_PARSER_VERSION` 和 `AURORADB_JSON_SCHEMA_VERSION`。
- 新增 `auroradb/docs/` 下的 AuroraDB 解析器变更记录和 JSON schema 变更记录。
- 新增 AuroraDB JSON metadata 字段：`metadata.project_version`、`metadata.parser_version`、`metadata.output_schema_version`。
- 新增 `aurora-translator auroradb schema`，用于输出 AuroraDB JSON schema。
- 新增机器可读 AuroraDB JSON schema 文档：`auroradb/docs/auroradb_schema.json`。
- 新生成的 AEDB 和 AuroraDB JSON payload 中，`metadata.project_version` 现在输出 `0.4.0`。

## 0.3.1

- 将偏 AEDB 的历史变更记录合并到当前双语文档 `aedb/docs/CHANGELOG.md`。
- 项目级变更记录只保留项目级发布和版本管理相关内容。
- JSON 输出结构不变。
- `metadata.project_version` 现在输出 `0.3.1`；AEDB 的 `metadata.parser_version` 保持 `0.3.0`；`metadata.output_schema_version` 保持 `0.3.0`。

## 0.3.0

- 建立三层版本管理：项目整体版本、不同格式的解析器版本、不同格式的 JSON schema 版本。
- 将根级 `PARSER_VERSION` 替换为 `PROJECT_VERSION`，用于表示整个 Aurora Translator 项目版本。
- 新增 AEDB 自有的 `AEDB_PARSER_VERSION` 和 `AEDB_JSON_SCHEMA_VERSION`。
- JSON 输出发生变化：新增 `metadata.project_version`。
- JSON 输出发生变化：`metadata.parser_version` 现在表示 AEDB 解析器版本，不再表示项目版本。
- `metadata.output_schema_version` 现在表示 AEDB JSON schema 版本 `0.3.0`。
- AEDB 解析器历史记录维护在 `aedb/docs/CHANGELOG.md`。
- AEDB JSON schema 历史记录维护在 `aedb/docs/SCHEMA_CHANGELOG.md`。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

## 0.7.60

- Integrated AEDB parser `0.4.46`; heartbeat progress blocks now finish before completion logs are emitted, preventing background progress lines from interrupting an indented block.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.59` / AEDB parser `0.4.45`.

## 0.7.59

- Integrated Semantic parser `0.6.10`; Aurora/AAF export now creates footprint-specific part variants when multiple components share a part name but use different footprints.
- ODB++ inner-layer short-cline components such as `n/a` + `SHORT_CLINE-LAYER2` now reference their own exported part instead of collapsing onto the `SHORT_CLINE-TOP` part.
- Root-level `design.layout` / `design.part` compatibility copies are refreshed together with `aaf/design.layout` / `aaf/design.part`, preventing stale AAF files in reused output directories.
- Semantic JSON schema remains `0.6.0`; this release changes conversion behavior and metadata defaults without adding semantic fields.

## 0.7.58

- Integrated AEDB parser `0.4.45`; parse logs no longer emit detailed profile breakdowns and now keep only indented "parsed object + count" summaries.
- Long-running heartbeat and progress logs now use indented field blocks while retaining processed counts, percent, elapsed time, rate, and RSS.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.56` / AEDB parser `0.4.44`.

## 0.7.56

- Integrated Semantic parser `0.6.9`; ODB++ component placement layer derivation now prefers the common metal layer of its resolved pin pads, so all-`LAYER7` pin components export on `COMP_LAYER7`.
- ODB++ semantic pins now inherit the actual pad metal layer when all pads for that pin share one layer, avoiding bottom/top component-layer fallback for inner-layer-mounted pin sets.
- Semantic JSON schema remains `0.6.0`; this release changes conversion behavior and metadata defaults without adding semantic fields.

## 0.7.55

- Integrated AEDB parser `0.4.44`; padstack record profile logs now print after `Build padstack instance records` completes, preventing heartbeat messages from interrupting indented field blocks.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.54` / AEDB parser `0.4.43`.

## 0.7.54

- Integrated AEDB parser `0.4.43`; when padstack batch snapshot statistics are identical to the total snapshot statistics, the parser no longer repeats a `Batch snapshot totals` block.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.53` / AEDB parser `0.4.42`.

## 0.7.53

- Integrated AEDB parser `0.4.42`; profile statistics in parse logs now use grouped titles with indented fields, reducing repeated `Path profile`, `Polygon profile`, and `Padstack record profile` prefixes.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.52` / AEDB parser `0.4.41`.

## 0.7.52

- Integrated Semantic parser `0.6.8`; ODB++ component, pad, and package-pin rotations now follow the ODB++ Design Format Specification's clockwise-positive angle convention during Aurora/AAF export.
- ODB++ fallback footprint-pad derivation now uses the clockwise inverse transform, fixing rotated components when package pin geometry is unavailable or when absolute pin pads are emitted.
- Semantic JSON schema remains `0.6.0`; this release changes export behavior but does not add Semantic payload fields.

## 0.7.51

- Integrated AEDB parser `0.4.41`; refined long-stage progress logging on large AEDB regression samples so parent heartbeats no longer duplicate primitive progress messages.
- Primitive progress logs now use a minimum spacing while keeping `processed/total`, percent, rate, and RSS details.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.50` / AEDB parser `0.4.40`.

## 0.7.50

- Integrated AEDB parser `0.4.40`; long-running parse stages now emit heartbeat logs so large AEDB regression samples do not stay silent during blocking work.
- `log_timing` now emits an `is still running` message every 10 seconds by default, including elapsed seconds and current process RSS.
- Path, polygon, and zone primitive serialization now emit `processed/total`, percentage, rate, and RSS progress logs.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.49` / AEDB parser `0.4.39`.

## 0.7.49

- Integrated AEDB parser `0.4.39`; cleaned up AEDB parser log and analysis log layout.
- The regular parser log now has `Input configuration`, `AEDB parsing`, `Analysis output`, and `Run summary` sections to keep configuration, parsing, and output messages separate.
- The analysis log now prints a top-level stage summary first, then a detailed stage tree ordered by stage start time so parent stages appear before their child stages.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.47` / AEDB parser `0.4.38`.

## 0.7.48

- Integrated Semantic parser `0.6.7`; positive ODB++ no-net trace/arc/polygon primitives on signal/plane layers are now promoted to AuroraDB `NoNet` geometry.
- `PROFILE`/non-routable drawing and negative/cutout primitives remain coverage-only and are not mixed into `NoNet`.
- Semantic JSON schema remains `0.6.0`; this release only corrects ODB++ to AuroraDB no-net geometry mapping.

## 0.7.47

- Integrated AEDB parser `0.4.38`; after an AEDB CLI parse completes, the CLI now automatically writes a separate analysis log summarizing stage timings and process working-set memory samples.
- Added `--analysis-log-file` to override the analysis log path; by default it is written next to the JSON output as `<json_stem>_analysis.log`.
- AEDB JSON schema remains `0.4.0`; output JSON fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.46` / AEDB parser `0.4.37`.

## 0.7.46

- Integrated Semantic parser `0.6.6`; ODB++ reserved no-net names (`$NONE$`, `$NONE`, `NONE$`, and `NoNet`) now normalize to AuroraDB's `NoNet` keyword.
- Integrated AuroraDB parser `0.2.1`; Aurora/AAF to AuroraDB compilation preserves the `NoNet` keyword case instead of writing it as the ordinary uppercase net name `NONET`.
- Semantic JSON schema remains `0.6.0`; this release only corrects ODB++ no-net mapping and AuroraDB output naming.

## 0.7.45

- Integrated AEDB parser `0.4.37`, adding a `.NET` batch snapshot path for padstack instance record construction that reads all instance base fields, positions, layer ranges, and padstack definitions in one lower-level call.
- Kept the per-instance snapshot/PyEDB fallback; logs now include batch snapshot hit/fallback counts and timing to confirm whether the optimized path is active.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.44` / AEDB parser `0.4.36`.

## 0.7.44

- Integrated Semantic parser `0.6.5`; Aurora/AAF polygon-void export now supports full-circle ODB++ holes encoded as a single `OC` arc whose start point equals its end point.
- These full-circle voids are emitted as two semicircular `Parc` vertices inside `PolygonHole`, avoiding the previous skip when the contour had fewer than three polygon vertices.
- Semantic JSON schema remains `0.6.0`; this release only fixes void geometry emitted to AuroraDB.

## 0.7.43

- Integrated AEDB parser `0.4.36`, adding a `.NET` batch snapshot path for padstack definitions that reads definition base fields, hole/via data, and all three layer pad-property maps in one lower-level pass.
- Kept the PyEDB wrapper fallback; logs now include snapshot hit/fallback counts and timing to confirm whether the optimized path is active.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.42` / AEDB parser `0.4.35`.

## 0.7.42

- Integrated AEDB parser `0.4.35`, adding aggregate profiling for padstack definition serialization across field reads, layer maps, PadPropertyModel construction, and PadstackDefinitionModel construction.
- AEDB JSON schema remains `0.4.0`; this release only emits diagnostic logs and adds no JSON fields.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.41` / AEDB parser `0.4.34`.

## 0.7.41

- Integrated AEDB parser `0.4.34`, optimizing the fast `ArcModel` construction path for polygon/void arcs to reduce pure-Python object construction overhead.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.39` / AEDB parser `0.4.33`.

## 0.7.40

- Integrated Semantic parser `0.6.4`; ODB++ point-feature `orient_def` is now interpreted according to the ODB++ pad orientation rules, including legacy `4..7` mirrored rotations and `8/9 <angle>` arbitrary rotations.
- ODB++ pad mirror flags are preserved through Aurora/AAF pad and footprint-pad output, and footprint pin rotations now reflect source pad orientation instead of only component placement rotation.
- Semantic JSON schema remains `0.6.0`; this change fills existing pad geometry hints and AAF transform options without adding semantic fields.

## 0.7.39

- Integrated AEDB parser `0.4.33`, adding path-area fallback profiling by reason, corner style, end-cap style, and center-line point-count bucket.
- This release identifies the next optimization entry point for reducing path `GetPolygonData()` time; AEDB JSON schema remains `0.4.0`.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.37` / AEDB parser `0.4.32`.

## 0.7.38

- Integrated Semantic parser `0.6.3`; ODB++ component pin mapping now prefers EDA net references keyed by the real component index and pin index before falling back to component-file pin reference fields.
- ODB++ footprint pad rotations emitted into `design.part` are now normalized to the same angle range as component placements, avoiding invalid-looking `450` / `540` / `630` degree rotations.
- Semantic JSON schema remains `0.6.0`; this change fixes ODB++ conversion behavior without adding semantic fields.

## 0.7.37

- Integrated AEDB parser `0.4.32`, adding a `.NET PrimitiveWithVoidsGeometrySnapshot` batch path that reads polygon body and void geometry in one call.
- Polygon/void arc construction remains on the Python side; AEDB JSON schema remains `0.4.0`.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.35` / AEDB parser `0.4.31`.

## 0.7.36

- Integrated Semantic parser `0.6.2`; ODB++ via templates now infer layer antipads from matching negative-polarity pad features when available, including no-net negative pad primitives at the via location.
- ODB++ conversion coverage now reports semantic via templates with antipads and the total layer-antipad entry count.
- Semantic JSON schema remains `0.6.0`; this change fills existing `SemanticViaTemplateLayer.antipad_shape_id` data without adding fields.

## 0.7.35

- Integrated AEDB parser `0.4.31`, using an analytic area calculation for straight two-point paths without arcs to reduce AEDB `GetPolygonData()` calls.
- Complex paths still use AEDB's native polygon area; AEDB JSON schema remains `0.4.0`.
- JSON content changes: straight-path `area` values may differ only at floating-point tail precision; layout points, widths, lengths, bboxes, and counts are unchanged.

## 0.7.34

- Integrated Semantic parser `0.6.1`; ODB++ surface polygons now use contour polarity (`I` island / `H` hole) to split multi-island `S` features into separate semantic polygon primitives and attach hole contours to the correct island.
- ODB++ conversion coverage now reports source multi-island surface counts, source hole contour counts, semantic split-surface polygon counts, and semantic polygon void counts.
- Semantic JSON schema remains `0.6.0`; this change refines conversion behavior and coverage reporting without adding semantic model fields.

## 0.7.33

- Integrated ODB++ parser/schema `0.5.0`, adding selected-step layer `attrlist` fields and top-level drill-tools metadata such as `THICKNESS` and `USER_PARAMS`.
- Integrated Semantic parser/schema `0.6.0`; ODB++ layer attributes now populate Semantic stackup materials/thickness, via templates are refined from matched signal-layer pads, and component/package attributes are preserved for unified access and AuroraDB part export.
- ODB++ to AuroraDB now writes part attributes into `parts.db` and uses ODB++ copper/dielectric thickness values in `stackup.dat` / `stackup.json` when available.
- Integrated AEDB parser `0.4.30`, adding a `.NET PadstackInstanceSnapshot` helper that batches padstack instance field reads into one lower-level call to reduce parse time.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.32` / AEDB parser `0.4.29`.

## 0.7.32

- Integrated AEDB parser `0.4.29`, adding field-level profiling logs for padstack instance record construction to locate padstack parsing bottlenecks.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.31` / AEDB parser `0.4.28`.

## 0.7.31

- Integrated AEDB parser `0.4.28`; polygon and void arc construction now uses an AEDB-internal fast ArcModel constructor to reduce model-building overhead across roughly 1.2M arcs.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.30` / AEDB parser `0.4.27`.

## 0.7.30

- Integrated AEDB parser `0.4.27`; path primitive `bbox` is now derived from center-line bbox expanded by trace width, avoiding an additional `GetBBox()` read from path polygon data.
- Path primitive `area` still uses AEDB's original `GetPolygonData().Area()` to keep rounded cap, corner, and end-cap results unchanged; AEDB JSON schema remains `0.4.0`.
- Integrated Semantic parser `0.5.3`; ODB++ to AuroraDB now maps component parts to real package/footprint symbols instead of also emitting duplicate empty footprints named after part numbers.
- ODB++ coverage now counts component placement commands separately from component pin/net bindings.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.29` / AEDB parser `0.4.26`.

## 0.7.29

- Integrated AEDB parser `0.4.26`, adding aggregated profiling logs for path primitive serialization that split center-line reads, length calculation, base metadata, field normalization, and model construction timings.
- Profiling only emits summary logs; it adds no JSON fields and does not change parsed content.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.28` / AEDB parser `0.4.25`.

## 0.7.28

- Integrated AEDB parser `0.4.25`, adding a `.NET GeometrySnapshot` batch path for polygon and void geometry reads that returns `raw_points`, `bbox`, and `area` together to reduce Python/.NET round trips.
- Added `geometry_snapshot` to polygon profiling logs; arc construction remains on the Python side with the existing formulas to avoid last-digit floating-point differences.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.27` / AEDB parser `0.4.24`.

## 0.7.27

- Integrated AEDB parser `0.4.24`, adding a runtime-compiled and loaded `.NET` polygon point extractor that moves per-point `PolygonData.GetPoint()` and `PointData.X/Y.ToDouble()` reads into .NET and returns a batched `double[]` to Python.
- Polygon, void, and path center-line reads prefer the batched helper; if C# compilation, loading, or invocation fails, parsing automatically falls back to the previous Python `PolygonData.Points` path.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.25` / AEDB parser `0.4.23`.
- Integrated Semantic parser `0.5.2`; ODB++ no-net drawing primitives remain visible in Semantic coverage but are no longer emitted as Aurora/AAF `ODBPP_DRAWING` logic geometry by default.

## 0.7.26

- Integrated Semantic parser `0.5.1`; ODB++ package definitions now all become `SemanticFootprint` entries, including package bodies that are not instantiated by a component in the selected step.
- ODB++ no-net drawable primitives on routable layers are counted in Semantic coverage without inventing net connectivity.
- ODB++ coverage reports now count semantic drawing primitives, AAF logic geometry, source packages with outlines, and package-body export coverage separately.
- Semantic JSON schema remains `0.5.0`; no schema fields were added.

## 0.7.25

- Integrated AEDB parser `0.4.23`; polygon/void arc construction now builds ArcModel objects in one pass over the already-read raw points instead of first creating `vertices` and `edge_heights` intermediate lists and traversing them again.
- Kept the stable `.NET PolygonData.Points` materialization into a Python list to avoid repeating the slower direct `.NET Points` iteration observed in `0.4.20`.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.24` / AEDB parser `0.4.22`.

## 0.7.24

- Integrated AEDB parser `0.4.22`, adding aggregate profiling logs for polygon primitive serialization to split polygon/void `.NET` data reads, raw points, arc construction, area, bbox, metadata, and model-building time.
- Profiling only emits summary logs; it does not add JSON fields or change parsed content.
- AEDB JSON schema remains `0.4.0`.
- JSON content changes: aside from version metadata, the payload is expected to match `0.7.23` / AEDB parser `0.4.21`.

## 0.7.23

- Integrated AEDB parser `0.4.21`, reverting the `0.4.20` experiment that directly iterated polygon raw points and built arc models in one pass.
- A large AEDB regression sample showed slower polygon serialization with `0.4.20`, so the current implementation restores the stable path that materializes `.NET Points` as a list and then builds arcs through `vertices/edge_heights`.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, content is expected to match `0.4.20` and `0.4.19`; this version mainly records the performance-experiment rollback.

## 0.7.22

- Integrated AEDB parser `0.4.20`; polygon and void raw points now iterate `PolygonData.Points` directly instead of first creating a temporary `.NET list`.
- Polygon/void arc models are now built from raw points in a single streaming pass, avoiding separate `vertices` and `edge_heights` intermediate lists plus a second traversal.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, polygon, void, arc, path, component, padstack, and net fields and counts are expected to remain unchanged.
- Integrated Semantic parser and schema `0.5.0`; Semantic JSON now carries `board_outline`, footprint/package `geometry`, via-template geometry, and via instance geometry hints for unified downstream access.
- ODB++ to AuroraDB now uses parsed profile geometry for the board outline, including profile arc edges, instead of falling back to a bbox outline when profile data is available.
- ODB++ package outline/body records are now exported into `design.part` footprint geometry, and drill tool metadata is preserved on semantic via templates and via instances when matched to drill symbols.
- Added `odbpp coverage` and `odbpp to-auroradb --coverage-output` for object-level source/Semantic/AAF/AuroraDB conversion coverage reports.

## 0.7.21

- Integrated AEDB parser `0.4.19`; path primitive `length` is now computed from the already-read center-line raw points and arc-height markers by default, avoiding a per-path `.NET PolygonData.GetArcData()` call.
- `.NET GetArcData()` remains as a fallback when raw center-line points are unavailable.
- AEDB JSON schema remains `0.4.0`; output fields are unchanged.
- JSON content changes: aside from version metadata, path `length` may only differ at floating-point tail precision; path, polygon, component, padstack, and net counts are expected to remain unchanged.

## 0.7.20

- Integrated Semantic parser `0.4.7`; ODB++ surface contour `OC` arc records are now preserved through semantic polygon geometry and exported as 5-value Aurora/AAF polygon arc vertices, compiling into AuroraDB `Parc` items.
- ODB++ standalone `A` arc features now become semantic arc primitives and can export as `Larc` net geometry when the source arc has a net and a resolvable positive round-symbol width.
- On a private ODB++ sample, ODB++ to AuroraDB conversion now reports `polygon_primitives_with_arcs=1255`, `polygons_with_void_arcs=80`, `voids_with_arcs=1915`, and generated AuroraDB layer files contain `Parc` curved polygon edges.
- Semantic JSON schema remains `0.4.0`; the schema default `metadata.parser_version` now reports `0.4.7`.

## 0.7.19

- Integrated AEDB parser `0.4.18`, computing `component.center` from the bbox center of each component's absolute pin positions by default instead of calling the AEDB `.NET LayoutObjInstance` interface for component centers.
- Added the AEDB CLI option `--component-center-source {pin-bbox,layout-instance}`; the default is `pin-bbox`, while `layout-instance` remains available for comparison against the bottom-level interface.
- AEDB JSON output schema remains `0.4.0`; `component.center` keeps the same meaning, but its default source changes from layout instance geometry to pin bbox center.
- JSON content change: the default computed mode no longer emits layout-instance `component.bounding_box`, so that field is `null`; component, pin, padstack, primitive, and net counts are unchanged.

## 0.7.18

- Integrated ODB++ parser `0.4.0` and ODB++ JSON schema `0.4.0`.
- ODB++ parsing now exports selected-step `drill_tools[]` from layer `tools` files and `packages[]` from EDA package definitions, including package pins and common package geometry records.
- Integrated Semantic parser `0.4.6`; ODB++ conversion now builds via templates per drill layer and symbol, preserves via layer spans from matrix start/end layers, and uses package pin geometry as a component pad fallback.
- Corrected ODB++ surface polarity and point feature orientation handling so surface records no longer treat polarity as a symbol, and pad geometry keeps dcode/orientation separately.
- On a private ODB++ sample, the AuroraDB conversion now reports `components=522`, `parts=86`, `shapes=119`, `vias=10`, and `net_geometries=61145`; all 522 components now have pad bindings.

## 0.7.17

- Fixed AEDB-to-AuroraDB component placement rotation so Aurora/AAF export now infers component orientation from pad topology instead of trusting AEDB's raw component transform rotation, which can stay `0` across the design.
- When the same AEDB `part_name` resolves to incompatible pin sets or pad topology variants, Aurora/AAF export now emits per-variant part/footprint names so component library footprints stay aligned with the owning instance geometry.
- Integrated ODB++ parser `0.3.0` and ODB++ JSON schema `0.3.0`.
- ODB++ parsing now exports `symbols[]` from `symbols/<name>/features`, including custom symbol surface contours for non-rectangular pads.
- ODB++ EDA `FID` records now retain their associated `SNT TOP T/B` pin context so component pins can be bound to the exact copper pad feature.
- Integrated Semantic parser `0.4.5`; ODB++ conversion now emits component-owned pads, footprint pad geometry, and corrected ODB++ degree-to-radian rotation semantics for component and footprint pad placement.
- Fixed polygon shape export so the first polygon value remains a vertex count instead of being unit-converted as a length.
- On a private ODB++ sample, the AuroraDB conversion now reports `components=522`, `parts=86`, `shapes=118`, `vias=5`, and `net_geometries=61141`.

## 0.7.16

- Integrated AEDB parser `0.4.17`, increasing coordinate serialization precision for component centers, component bounding boxes, and padstack/pin positions from 6 to 9 decimal places in meter units.
- This reduces rounding error when deriving component placement from pin bbox centers; rotation precision remains 6 decimal places.
- AEDB JSON schema remains `0.4.0`; field structure and counts are unchanged.
- JSON content change: component and pin/padstack coordinate values now emit more decimal places, reducing the previous about `0.039 mil` pin-derived center rounding error to a smaller scale.
- Integrated Semantic parser `0.4.4`, fixing a Python 3.12 generic-function syntax issue in the ODB++ semantic adapter that broke CLI imports on Python 3.10; Semantic JSON output schema remains `0.4.0`.

## 0.7.15

- Integrated AEDB parser `0.4.16`, restoring component layout geometry extraction so AEDB components emit `center` and `bounding_box` again.
- Fixed incorrect downstream Semantic and AuroraDB component placement caused by AEDB parser `0.4.15`, where many components fell back to `[0.0, 0.0]` `location` values after geometry extraction was skipped.
- AEDB JSON output structure remains schema `0.4.0`; newly generated AEDB payloads report `metadata.project_version` as `0.7.15` and `metadata.parser_version` as `0.4.16`.
- JSON content change: compared with AEDB parser `0.4.15`, `component.center` and `component.bounding_box` are restored from `null` to actual AEDB layout-instance coordinates; field structure and counts are unchanged.

## 0.7.14

- Integrated ODB++ parser `0.2.0` and ODB++ JSON schema `0.2.0`.
- ODB++ parsing now preserves feature indices/IDs, feature attributes, surface contours, component pins, component properties, and EDA net feature/pin references.
- The ODB++ semantic adapter now derives shapes, traces, polygons, pads, vias, footprints, pins, and net connectivity for AuroraDB export.
- Added `odbpp to-auroradb` for direct ODB++ archive/directory to Aurora/AAF and AuroraDB conversion with optional intermediate JSON outputs.
- `semantic to-auroradb` can now produce non-empty AuroraDB geometry from a private ODB++ sample; conversion reports `shapes=116`, `vias=5`, and `net_geometries=60515`.
- Updated the Semantic parser version to `0.4.3`; the Semantic JSON schema remains `0.4.0`.

## 0.7.12

- Integrated AEDB parser `0.4.15`, skipping component layout geometry extraction to avoid the slow `.NET LayoutInstance.GetLayoutObjInstance(...)` path.
- Newly generated AEDB payloads keep component records and pins, but `component.center` and `component.bounding_box` are now `null` for all components.
- On a large AEDB regression sample, AEDB layout parsing dropped from about `241.294s` to `144.984s`.
- AEDB JSON schema remains `0.4.0`; newly generated payloads now report `metadata.project_version` as `0.7.12` and AEDB payloads report `metadata.parser_version` as `0.4.15`.

## 0.7.11

- Integrated Semantic parser `0.4.2`, preserving AEDB polygon and polygon-void arc geometry in Semantic and emitting those curved edges as Aurora/AAF polygon arc vertices.
- Polygon and void arc direction now follows the existing AEDB-to-AAF convention: negative AEDB arc height emits direction `Y`, positive height emits `N`, with `is_ccw` used only as a fallback when height is unavailable.
- Added PowerShell setup and cleanup scripts for local environment preparation and Git-ready workspace cleanup.
- Removed the redundant narrow board-model access layer and ODB++ board-summary adapter; cross-format conversion now relies on the richer Semantic model.
- Integrated AEDB parser `0.4.14`, caching polygon-void geometry records so parent polygon area calculation and void serialization reuse the same bottom-level geometry extraction.
- Semantic JSON schema remains `0.4.0`; newly generated payloads now report `metadata.project_version` as `0.7.11` and Semantic payloads report `metadata.parser_version` as `0.4.2`.

## 0.7.10

- Integrated AEDB parser `0.4.13`, which derives polygon and polygon-void arc geometry from raw `.NET PolygonData.Points` arc-height markers instead of calling `PolygonData.GetArcData()` for every polygon.
- AEDB JSON structure and counts are unchanged; arc numeric values may differ from `0.4.12` only at floating-point tail precision.
- AEDB JSON schema remains `0.4.0`; newly generated AEDB payloads now report `metadata.project_version` as `0.7.10` and `metadata.parser_version` as `0.4.13`.

## 0.7.9

- Integrated AEDB parser `0.4.12`, preserving legacy empty-string normalization for raw `.NET` padstack placement layers.
- Newly generated AEDB JSON payloads now report `metadata.project_version` as `0.7.9` and `metadata.parser_version` as `0.4.12`.
- AEDB JSON schema remains `0.4.0`; AuroraDB, ODB++, and Semantic parser/schema versions are unchanged.

## 0.7.8

- Realigned Semantic to Aurora/AAF export with the AEDB-to-AAF reference flow: trace width is emitted as a Circle shape, arc points in center lines are emitted as `Larc`, and `Line` geometry no longer carries width as an inline field.
- `design.layout` now emits pin-pad copper shape placement with net, layer, location, and rotation semantics.
- `design.part` now emits footprint pad templates, pad geometry, and footprint pin placement so part, footprint, pad, and pin object relationships are preserved.
- Added cross-format semantic mapping table documentation covering object-level conversion among AEDB, Semantic, Aurora/AAF, AuroraDB, and ODB++.
- Updated the AEDB parser version to `0.4.11`; the Semantic parser remains `0.4.1` and the Semantic JSON schema remains `0.4.0`.
- `metadata.project_version` now reports `0.7.8` for newly generated AEDB, AuroraDB, ODB++, and Semantic JSON payloads.

## 0.7.7

- Integrated AEDB parser `0.4.10`, which reads padstack instances and layout primitives from raw `pedb.active_layout` `.NET` collections.
- Kept AEDB JSON schema at `0.4.0`; this version was retained as an intermediate regression output for raw collection comparison.
- `metadata.project_version` reports `0.7.7` for newly generated payloads from this intermediate version.

## 0.7.6

- Aurora/AAF export now writes Semantic components as layout components and Semantic pins as net-pin bindings.
- Aurora/AAF export now writes Semantic trace and polygon primitives as AuroraDB net geometry; polygons with void geometry are emitted as PolygonHole.
- The AEDB parser now emits polygon void geometry, and AEDB-to-Semantic primitive conversion preserves polygon `is_void`, `void_ids`, and `voids`.
- Updated the Semantic parser version to `0.4.1`; the Semantic JSON schema version remains `0.4.0`.
- Updated the AEDB parser version to `0.4.9` and the AEDB JSON schema version to `0.4.0`.
- `metadata.project_version` now reports `0.7.6` for newly generated AEDB, AuroraDB, ODB++, and Semantic JSON payloads.

## 0.7.5

- Added AuroraDB-profile shapes and via templates to the Semantic model for geometry semantics required by AuroraDB `ShapeList` and `ViaList`.
- Added AEDB-to-Semantic padstack geometry normalization, converting Circle, Rectangle, RoundedRectangle, and related pad, antipad, and drill-hole shapes into semantic shapes.
- Aurora/AAF export now writes semantic shapes as `layout add -g`, via templates as `layout add -via`, and via instances as net-connected vias.
- Added AEDB-to-Semantic conversion documentation.
- Updated the Semantic parser and Semantic JSON schema versions to `0.4.0`.
- `metadata.project_version` now reports `0.7.5` for newly generated AEDB, AuroraDB, ODB++, and Semantic JSON payloads.
- AEDB, AuroraDB, and ODB++ JSON schema versions are unchanged.

## 0.7.4

- Integrated the AEDB parser `0.4.8` optimization into the current project release.
- Added semantic materials and layer material references so AEDB dielectric layers can carry permittivity, dielectric loss tangent, and thickness through the unified model.
- `semantic to-aaf` / `semantic to-auroradb` now emit an Aurora/AAF conversion package: `design.layout`, `design.part`, `stackup.dat`, and `stackup.json`; `to-auroradb` also writes an AuroraDB subdirectory.
- Updated the Semantic JSON schema version to `0.3.0`.
- `metadata.project_version` now reports `0.7.4` for newly generated AEDB, AuroraDB, ODB++, and Semantic JSON payloads.
- AEDB, AuroraDB, and ODB++ JSON schema versions are unchanged.

## 0.7.3

- Integrated the AEDB parser `0.4.7` optimization into the current project release.
- `metadata.project_version` now reports `0.7.3` for newly generated AEDB, AuroraDB, ODB++, and Semantic JSON payloads.
- Format JSON schema versions are unchanged.

## 0.7.2

- Integrated the AEDB parser `0.4.6` optimization into the current project release.
- `metadata.project_version` now reports `0.7.2` for newly generated AEDB, AuroraDB, ODB++, and Semantic JSON payloads.
- Format JSON schema versions are unchanged.

## 0.7.1

- Integrated the AEDB parser `0.4.5` optimization into the current project release.
- Added the initial `semantic to-auroradb` entry point for emitting Aurora-side conversion output from the unified semantic model.
- Updated the Semantic parser version to `0.3.0`; the Semantic JSON schema version remains `0.2.0`.
- `metadata.project_version` now reports `0.7.1` for newly generated AEDB, AuroraDB, ODB++, and Semantic JSON payloads.
- Format JSON schema versions are unchanged.

## 0.7.0

- Integrated the AEDB parser `0.4.4` optimization into the current project release.
- Expanded the semantic layer with footprint and pad semantic objects plus summary counts.
- AEDB, AuroraDB, and ODB++ semantic adapters now build component-footprint, component-pad, footprint-pad, pin-pad, and pad-net links when traceable source fields are available.
- Added semantic connectivity consistency diagnostics for references that point to missing objects.
- Updated the Semantic parser and Semantic JSON schema versions to `0.2.0`.
- `metadata.project_version` now reports `0.7.0` for newly generated AEDB, AuroraDB, ODB++, and Semantic JSON payloads.

## 0.6.2

- Integrated the AEDB parser `0.4.4` optimization into the project release.
- `metadata.project_version` now reports `0.6.2` for newly generated AEDB, AuroraDB, ODB++, and Semantic JSON payloads.
- Format JSON schema versions are unchanged.

## 0.6.1

- Integrated the AEDB parser `0.4.3` optimization into the project release.
- `metadata.project_version` now reports `0.6.1` for newly generated AEDB, AuroraDB, ODB++, and Semantic JSON payloads.
- Format JSON schema versions are unchanged.

## 0.6.0

- Added a cross-format semantic layer with the unified `SemanticBoard` semantic model.
- Added adapters from AEDB, AuroraDB, and ODB++ into the semantic model.
- Added basic connectivity edge generation.
- Added the `aurora-translator semantic from-json` and `aurora-translator semantic schema` CLI commands.
- Added architecture, JSON field guide, changelog, and schema changelog documentation under `semantic/docs/`.
- `metadata.project_version` now reports `0.6.0` for newly generated AEDB, AuroraDB, ODB++, and Semantic JSON payloads.

## 0.5.4

- Added the root project architecture documentation, now maintained as the bilingual file `docs/architecture.md`.
- Clarified project-level module boundaries, format-owned schema ownership, version responsibilities, and extension workflow.
- `metadata.project_version` now reports `0.5.4` for newly generated AEDB, AuroraDB, and ODB++ payloads.
- Format parser versions and JSON schema versions are unchanged.

## 0.5.3

- Integrated the AEDB parser `0.4.2` optimization into the project release.
- `metadata.project_version` now reports `0.5.3` for newly generated AEDB, AuroraDB, and ODB++ payloads.
- AEDB JSON schema is unchanged.

## 0.5.2

- Integrated the AEDB parser `0.4.1` optimization into the project release.
- `metadata.project_version` now reports `0.5.2` for newly generated AEDB, AuroraDB, and ODB++ payloads.
- AEDB JSON schema is unchanged.

## 0.5.1

- Added AEDB-style Pydantic models for AuroraDB stored data.
- `auroradb export-json` now emits a structured AuroraDB model with layout, layers, nets, parts, footprints, pads, and geometry references.
- Added `--include-raw-blocks` to retain original AuroraDB block trees alongside the structured model.
- Updated AuroraDB parser and JSON schema versions to `0.2.0`.
- Added the ODB++ parser integration backed by the Rust `crates/odbpp_parser` CLI.
- Added ODB++ format-level version constants: `ODBPP_PARSER_VERSION` and `ODBPP_JSON_SCHEMA_VERSION`.
- Added ODB++ JSON metadata fields and schema export support through `aurora-translator odbpp schema`.
- Added the first generated ODB++ JSON schema under `odbpp/docs/odbpp_schema.json`.
- Added a narrow shared `board_model` access model and an ODB++ adapter for future cross-format access.
- `metadata.project_version` now reports `0.5.1` for newly generated AEDB, AuroraDB, and ODB++ payloads.

## 0.4.1

- Integrated the AEDB parser `0.4.0` optimization into the project release.
- `metadata.project_version` now reports `0.4.1` for newly generated AEDB and AuroraDB payloads.
- AEDB JSON schema is unchanged.

## 0.4.0

- Added AuroraDB format-level version constants: `AURORADB_PARSER_VERSION` and `AURORADB_JSON_SCHEMA_VERSION`.
- Added AuroraDB parser and schema changelogs under `auroradb/docs/`.
- Added AuroraDB JSON metadata fields: `metadata.project_version`, `metadata.parser_version`, and `metadata.output_schema_version`.
- Added AuroraDB JSON schema export support through `aurora-translator auroradb schema`.
- Added generated AuroraDB JSON schema documentation at `auroradb/docs/auroradb_schema.json`.
- `metadata.project_version` now reports `0.4.0` for newly generated AEDB and AuroraDB payloads.

## 0.3.1

- Moved AEDB-focused historical changelog entries into the current bilingual file `aedb/docs/CHANGELOG.md`.
- Kept the project-level changelog focused on project-level release and version-management changes.
- JSON output schema is unchanged.
- `metadata.project_version` now reports `0.3.1`; AEDB `metadata.parser_version` remains `0.3.0`; `metadata.output_schema_version` remains `0.3.0`.

## 0.3.0

- Introduced three-level version management: project version, per-format parser version, and per-format JSON schema version.
- Replaced the root `PARSER_VERSION` with `PROJECT_VERSION` for the overall Aurora Translator release version.
- Added AEDB-owned `AEDB_PARSER_VERSION` and `AEDB_JSON_SCHEMA_VERSION`.
- JSON output changed: added `metadata.project_version`.
- JSON output changed: `metadata.parser_version` now reports the AEDB parser version instead of the project version.
- `metadata.output_schema_version` now reports AEDB JSON schema version `0.3.0`.
- AEDB parser history is maintained in `aedb/docs/CHANGELOG.md`.
- AEDB JSON schema history is maintained in `aedb/docs/SCHEMA_CHANGELOG.md`.
