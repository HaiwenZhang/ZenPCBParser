<a id="top"></a>
# AuroraDB 解析器变更记录 / AuroraDB Parser Changelog

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

## 0.2.14

- `split_reserved()` 现在会在 parenthesized / bracketed reserved pair 内正确进入 quoted-string 状态，避免 `Attributes (PART_NAME,"..._(...)")` 这类值被误判为未闭合括号。
- 使用大型 BRD 派生 AuroraDB 输出验证：`parts.db` 可读回，`diagnostics=0`。
- AuroraDB JSON schema 保持 `0.2.0`；该版本只修正 block 文本读取兼容性。

## 0.2.13

- AuroraDB block writer 现在会为包含括号或引号的普通字段值加引号，避免 part/footprint 名称中的 `(` 被写成无法回读的保留表达式。
- `split_reserved()` 修正引号内字符处理：引号内的括号不再参与保留表达式栈，转义引号不会提前结束字符串。
- AuroraDB JSON schema 保持 `0.2.0`；该版本只修正 block 文本读写兼容性。

## 0.2.12

- AEDB direct AuroraDB exporter 现在优先消费 SemanticBoard 中的 trace 私有 `Line` / `Larc` 行缓存，并直接写出 trace `NetGeom` raw block。
- 缓存缺失时仍回退到原有 trace geometry 转换路径，兼容非 AEDB 或显式 JSON 输入。
- AuroraDB JSON schema 保持 `0.2.0`；预期 AuroraDB 文件输出不变。

## 0.2.11

- AEDB direct AuroraDB exporter 现在优先消费 SemanticBoard 中的私有 `NetGeom` 行缓存，polygon / void 不再在导出阶段重复生成 `Pnt` / `Parc` 参数。
- 缓存缺失时仍回退到原有 geometry 转换路径，兼容非 AEDB 或显式 JSON 输入。
- AuroraDB JSON schema 保持 `0.2.0`；预期 AuroraDB 文件输出不变。

## 0.2.10

- AEDB direct AuroraDB exporter 现在支持对象型 geometry 输入，可直接消费 SemanticBoard 中保留的 AEDB arc model 和 tuple points。
- 坐标解析对 numeric point tuple/list 新增更短 fast path，减少 polygon / void 输出阶段的单位转换和类型判断开销。
- AuroraDB JSON schema 保持 `0.2.0`；预期 AuroraDB 文件输出不变。

## 0.2.9

- AEDB direct AuroraDB 输出中的 polygon / void `NetGeom` 改为轻量 raw block 写出，避免为大量 `Pnt` / `Parc` 顶点创建完整 block item 对象树。
- `layers/*.lyr` 写盘新增受控并行，保持文件内容不变的同时减少大板 layer 输出阶段等待。
- AuroraDB JSON schema 保持 `0.2.0`；预期 AuroraDB 文件输出不变。

## 0.2.8

- AEDB direct AuroraDB 输出中的 polygon/void block 现在直接生成 `Pnt` / `Parc` 参数，避免字符串化顶点后再拆分。
- Footprint pad 导出复用整板 pad、pin、shape、footprint 索引，减少大板 parts 构建时的重复扫描。
- 长度单位转换新增 numeric fast path，并缓存单位比例和数值格式化结果。
- AuroraDB block 写盘改为分块 `writelines()`，减少大量小 `write()` 调用。
- AuroraDB JSON schema 保持 `0.2.0`；预期 AuroraDB 文件输出不变。

## 0.2.7

- AEDB 默认 AuroraDB 输出路径现在直接从 `SemanticBoard` 构建 `AuroraDBPackage`，跳过内存 AAF command line 生成、AAF parser 和 AAF executor。
- `layout.db`、`parts.db`、`layers/*.lyr` 和 polygon void `PolygonHole` 在默认 AEDB 路径中直接构建；显式 `--export-aaf` 时仍保留 AAF 兼容路径。
- 非 AEDB fallback 的内存 AAF 转换改为边解析边执行，减少中间 command 对象列表占用。
- AuroraDB JSON schema 保持 `0.2.0`；预期 AuroraDB 文件输出不变。

## 0.2.6

- 导出器生成的 AAF fast parser 现在按 option 类型拆分 payload，仅 `-layerstack` 保留多值拆分；`-g`、`-location`、`-via` 等单值 payload 不再调用通用 `split_reserved()` 扫描。
- AAF executor 在组合导出器生成的 polygon void 时直接移动临时容器节点，避免 `PolygonHole` 组装阶段重复深拷贝大量 polygon 点。
- AuroraDB block 写盘改为流式写入，降低大文件输出时的中间字符串内存峰值。
- AuroraDB JSON schema 保持 `0.2.0`；预期 AuroraDB 文件输出不变。

## 0.2.5

- 默认 AuroraDB target 输出路径现在对本项目生成的 AAF command lines 使用轻量 parser，避免通用 tokenizer 对整行进行完整保留分隔解析。
- AAF geometry 执行新增快速 block 构建路径，常见 `Line`、`Larc`、`Polygon`、`PolygonHole` 直接构建 AuroraDB geometry block，复杂几何仍回退到原通用解析器。
- AuroraDB block 写盘格式化增加名称和值缓存，并把 quote 判断合并为单次扫描，降低大输出文件格式化成本。
- AuroraDB JSON schema 保持 `0.2.0`；预期 AuroraDB 文件输出不变。

## 0.2.4

- 默认 AuroraDB target 输出路径现在直接传递内存中的 AAF command lines，不再把 `design.layout` / `design.part` 内容先拼接成大字符串再拆分解析。
- 新增 `parse_command_lines()` 和 `translate_aaf_lines_to_auroradb()`；旧的文本入口与文件入口保留，用于兼容 `--export-aaf`、`auroradb from-aaf` 和人工回归。
- AuroraDB JSON schema 保持 `0.2.0`；预期 AuroraDB 文件输出不变。

## 0.2.3

- 默认 AuroraDB target 输出路径现在通过内存中的 AAF command text 调用转换器，不再为 `export_aaf: false` 的默认路径创建临时 `design.layout` / `design.part` 文件。
- 新增 `parse_command_text()` 和 `translate_aaf_text_to_auroradb()`，保留原有文件型 AAF 入口用于 `--export-aaf`、`auroradb from-aaf` 和人工回归检查。
- AuroraDB JSON schema 保持 `0.2.0`。

## 0.2.2

- 优化 AAF 到 AuroraDB 编译路径的命令执行性能：`AAFCommand` 现在缓存命令词和 option 查询结果，减少重复扫描。
- AuroraDB AAF executor 现在为 layer、net、component layer、net pin/via block 和 layer 内 net geometry 建立索引，降低大板中几十万条 AAF 命令执行时的线性查找成本。
- AuroraDB JSON schema 保持 `0.2.0`。

## 0.2.1

- AAF 到 AuroraDB 编译器现在会保留 `NoNet` keyword 的大小写，用于 ODB++ 无网络映射输出。
- AuroraDB JSON schema 保持 `0.2.0`。

## 0.2.0

- 新增与 AEDB `models.py` 风格一致的 Pydantic 模型，用于表达 AuroraDB 直接存储的数据。
- 新增结构化提取：layout units、stackup、shapes、via templates、nets、net pins、net vias、components、layer geometries、parts、pins、footprints、pad templates、footprint pads。
- `AuroraDBPackage.to_model(...)` 和 `to_model_dict(...)` 现在输出结构化模型。
- `auroradb export-json` 现在导出结构化模型，并可通过 `--include-raw-blocks` 同时包含原始 block tree。

## 0.1.0

- 新增 `AURORADB_PARSER_VERSION`，用于记录 AuroraDB 读取器和 ASIV AAF 命令转换实现的版本。
- 新增 `AURORADB_JSON_SCHEMA_VERSION`；schema 相关变更维护在 `SCHEMA_CHANGELOG.md`。
- 新增 AuroraDB block 读写能力，覆盖 `layout.db`、`parts.db` 和 `layers/*.lyr`。
- 新增 `auroradb.aaf` 子模块，用于解析 ASIV AAF 命令文件，并从 `design.layout`、`design.part` 命令集合生成 AuroraDB。
- 新增 AuroraDB JSON metadata 字段：`metadata.project_version`、`metadata.parser_version`、`metadata.output_schema_version`。
- AAF 命令执行路径会记录 unsupported diagnostics，便于按格式能力持续补齐。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

## 0.2.14

- `split_reserved()` now enters quoted-string state correctly inside parenthesized / bracketed reserved pairs, so values such as `Attributes (PART_NAME,"..._(...)")` are no longer misread as unclosed parentheses.
- Verified with AuroraDB output derived from a large BRD sample: `parts.db` reads back with `diagnostics=0`.
- AuroraDB JSON schema remains `0.2.0`; this release only fixes block text read compatibility.

## 0.2.13

- AuroraDB block writing now quotes ordinary field values containing parentheses or quotes, preventing part/footprint names with `(` from being written as unreadable reserved expressions.
- `split_reserved()` now treats quoted text as opaque for nested reserved pairs, and escaped quotes no longer terminate the quoted token.
- AuroraDB JSON schema remains `0.2.0`; this release only fixes block text read/write compatibility.

## 0.2.12

- AEDB direct AuroraDB export now consumes the private trace `Line` / `Larc` item-line cache on SemanticBoard first and writes trace `NetGeom` raw blocks directly.
- When the cache is absent, export still falls back to the existing trace geometry conversion path for non-AEDB and explicit JSON inputs.
- AuroraDB JSON schema remains `0.2.0`; AuroraDB file output is expected to remain unchanged.

## 0.2.11

- AEDB direct AuroraDB export now consumes the private `NetGeom` line cache on SemanticBoard first, so polygon / void export no longer rebuilds `Pnt` / `Parc` arguments in the export phase.
- When the cache is absent, export still falls back to the existing geometry conversion path for non-AEDB and explicit JSON inputs.
- AuroraDB JSON schema remains `0.2.0`; AuroraDB file output is expected to remain unchanged.

## 0.2.10

- AEDB direct AuroraDB exporter now accepts object-shaped geometry input, directly consuming AEDB arc models and tuple points preserved in SemanticBoard.
- Coordinate parsing adds a shorter fast path for numeric point tuple/list values, reducing unit-conversion and type-check overhead during polygon / void output.
- AuroraDB JSON schema remains `0.2.0`; AuroraDB file output is expected to remain unchanged.

## 0.2.9

- AEDB direct AuroraDB polygon / void `NetGeom` output now uses lightweight raw blocks, avoiding full block-item object trees for large `Pnt` / `Parc` vertex lists.
- `layers/*.lyr` writing now uses bounded parallelism, reducing large-board layer-output wait time while preserving file contents.
- AuroraDB JSON schema remains `0.2.0`; AuroraDB file output is expected to remain unchanged.

## 0.2.8

- AEDB direct AuroraDB polygon/void blocks now build `Pnt` / `Parc` values directly, avoiding vertex string formatting followed by value splitting.
- Footprint-pad export now reuses board-wide pad, pin, shape, and footprint indexes, reducing repeated scans during large parts construction.
- Length conversion adds a numeric fast path and caches unit scales plus formatted numeric values.
- AuroraDB block writing now uses chunked `writelines()` to reduce many small `write()` calls.
- AuroraDB JSON schema remains `0.2.0`; AuroraDB file output is expected to remain unchanged.

## 0.2.7

- The default AEDB to AuroraDB path now builds `AuroraDBPackage` directly from `SemanticBoard`, bypassing in-memory AAF command-line generation, the AAF parser, and the AAF executor.
- `layout.db`, `parts.db`, `layers/*.lyr`, and polygon-void `PolygonHole` blocks are built directly on the default AEDB path; the AAF compatibility path remains available when `--export-aaf` is requested explicitly.
- The non-AEDB in-memory AAF fallback now parses and executes exported commands incrementally, reducing intermediate command-object storage.
- AuroraDB JSON schema remains `0.2.0`; AuroraDB file output is expected to remain unchanged.

## 0.2.6

- The fast parser for exporter-generated AAF now splits payloads by option type and only keeps multi-value splitting for `-layerstack`; single-value payloads such as `-g`, `-location`, and `-via` no longer call the generic `split_reserved()` scanner.
- The AAF executor now moves temporary exported polygon-void container nodes into the final `PolygonHole`, avoiding repeated deep copies of large polygon point trees.
- AuroraDB block files now stream directly to disk, lowering intermediate string memory peaks during large-file writes.
- AuroraDB JSON schema remains `0.2.0`; AuroraDB file output is expected to remain unchanged.

## 0.2.5

- The default AuroraDB target output path now uses a lighter parser for AAF command lines generated by this project, avoiding full generic reserved-token parsing for entire lines.
- AAF geometry execution now has a fast block-building path for common `Line`, `Larc`, `Polygon`, and `PolygonHole` geometries, while complex geometries still fall back to the generic parser.
- AuroraDB block write formatting now caches formatted names and values and combines quote checks into a single scan to reduce formatting overhead on large outputs.
- AuroraDB JSON schema remains `0.2.0`; AuroraDB file output is expected to remain unchanged.

## 0.2.4

- The default AuroraDB target output path now passes in-memory AAF command lines directly instead of joining `design.layout` / `design.part` content into large strings and splitting them again for parsing.
- Added `parse_command_lines()` and `translate_aaf_lines_to_auroradb()` while keeping the existing text and file entry points for `--export-aaf`, `auroradb from-aaf`, and manual regression checks.
- AuroraDB JSON schema remains `0.2.0`; AuroraDB file output is expected to remain unchanged.

## 0.2.3

- The default AuroraDB target output path now feeds in-memory AAF command text into the translator instead of creating temporary `design.layout` / `design.part` files when `export_aaf: false`.
- Added `parse_command_text()` and `translate_aaf_text_to_auroradb()` while keeping the existing file-based AAF entry points for `--export-aaf`, `auroradb from-aaf`, and manual regression checks.
- AuroraDB JSON schema remains `0.2.0`.

## 0.2.2

- Optimized AAF-to-AuroraDB command execution: `AAFCommand` now caches command words and option lookups to avoid repeated scans.
- The AuroraDB AAF executor now indexes layers, nets, component layers, net pin/via blocks, and per-layer net geometry blocks, reducing linear lookup overhead for large boards with hundreds of thousands of AAF commands.
- AuroraDB JSON schema remains `0.2.0`.

## 0.2.1

- The AAF to AuroraDB compiler now preserves the `NoNet` keyword case for ODB++ no-net mapping output.
- AuroraDB JSON schema remains `0.2.0`.

## 0.2.0

- Added AEDB-style Pydantic models for direct AuroraDB stored data.
- Added structured extraction for layout units, stackup, shapes, via templates, nets, net pins, net vias, components, layer geometries, parts, pins, footprints, pad templates, and footprint pads.
- `AuroraDBPackage.to_model(...)` and `to_model_dict(...)` now expose the structured model.
- `auroradb export-json` now exports the structured model and can include raw block trees with `--include-raw-blocks`.

## 0.1.0

- Added `AURORADB_PARSER_VERSION` for AuroraDB reader and ASIV AAF command translation changes.
- Added `AURORADB_JSON_SCHEMA_VERSION`; schema-specific history is maintained in `SCHEMA_CHANGELOG.md`.
- Added AuroraDB block reader/writer support for `layout.db`, `parts.db`, and `layers/*.lyr`.
- Added ASIV AAF command parsing under `auroradb.aaf` and AAF-to-AuroraDB generation for the `design.layout` and `design.part` command surface.
- Added AuroraDB JSON metadata fields: `metadata.project_version`, `metadata.parser_version`, and `metadata.output_schema_version`.
- AAF command execution records unsupported diagnostics so format coverage can be expanded incrementally.
