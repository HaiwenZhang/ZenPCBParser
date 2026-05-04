<a id="top"></a>
# ODB++ 解析器变更记录 / ODB++ Parser Changelog

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

## 0.6.3

- Rust archive reader 默认跳过超过 512 MiB 的单个 ODB++ entry，并写入 non-fatal diagnostic，避免异常归档成员放大 peak memory；ODB++ JSON schema 保持 `0.6.0`。
- 新增 parser-level Rust 单元测试，覆盖 tokenizer、matrix row、feature records、surface arc、net pin/feature refs 和 archive entry size limit。
- Rust parser crate 版本现在报告为 `0.6.3`。

## 0.6.2

- Python 集成层现在会从项目根目录自动定位 Rust CLI binary：`crates/odbpp_parser/target/release/odbpp_parser(.exe)`。
- Rust archive reader 在 `--summary-only`、显式 `--step` 和默认 auto-step details 路径中会跳过非必要明细文件：summary-only 只载入 `matrix/matrix` 和 step `profile`，显式 step 只载入选定 step 的 layer/net/component/EDA 明细和全局 symbols；默认 details 会先 summary pass 选 step，再只读取选中 step 的明细文件。
- ODB++ JSON schema 保持 `0.6.0`；本次只修正 parser binary 解析路径和集成可靠性。
- 使用私有 ODB++ archive 样本验证：Rust CLI 解析 `steps=1`、`layers=32`、`features=111009`、`components=682`、`nets=656`、`diagnostics=2`，并可继续完成 Semantic/AuroraDB 输出。
- 已在本机安装并验证 Rust toolchain，`cargo test --manifest-path crates/odbpp_parser/Cargo.toml` 可执行通过。

## 0.6.1

- Rust ODB++ parser 改进了 `.tgz` 流式读取、文件索引复用、分层并行解析和若干字符串/数值解析热路径。
- 大型 ODB++ 回归样本在解析阶段的耗时明显下降，同时保持 native / CLI 输出统计一致。
- Rust parser crate 版本现在报告为 `0.6.1`。

## 0.6.0

- Rust 解析器现在共享同一套核心，并同时暴露 `odbpp_parser` CLI 和 `aurora_odbpp_native` PyO3 模块。
- Python 集成层默认优先调用 native 模块；显式传入 `--rust-binary` 时会强制走 CLI。
- Rust parser crate 版本现在报告为 `0.6.0`。

## 0.5.0

- 新增选定 step 的 layer `attrlist` 提取，写入 `layers[].layer_attributes`，供 Semantic adapter 生成 stackup 和 material hint。
- 保留 drill/rout `tools` 顶层 metadata，例如 `THICKNESS`、`USER_PARAMS`，以及未识别字段 `drill_tools[].raw_fields`。
- Rust parser crate 版本现在报告为 `0.5.0`。

## 0.4.0

- 新增从 layer `tools` 文件提取选定 step 的 `drill_tools[]`。
- 新增从 `steps/<step>/eda/data` 提取选定 step 的 `packages[]`，包含 package index、package properties、package pins、outline 和常见 package geometry records（`RC`、`CR`、`SQ` 与 contour）。
- 修正 `S` surface feature 的 polarity 解析，并将 point feature 的 dcode/orientation 与 pad symbol/polarity 分开保留。
- 改进 feature record 中分号/逗号属性的解析。
- Rust parser crate 版本现在报告为 `0.4.0`。

## 0.3.0

- 新增从 ODB++ `symbols/<name>/features` 文件提取 `symbols[]`。
- symbol definition 会保留解析后的 feature records 和 surface contours，使自定义 pad shape 可以转换为 semantic polygon shape。
- EDA `FID` feature 引用现在保留当前 `SNT` 类型以及关联的 `SNT TOP T/B` component-pin key。
- Rust parser crate 版本现在报告为 `0.3.0`。

## 0.2.0

- 为选定 step 的 layer `features` 文件新增 feature index、feature ID、分号属性和 surface contour 提取。
- 组件现在按层级输出：`CMP`/`COMP` 放置记录拥有子 `TOP`/`BOT` pin 和 `PRP` 属性，不再把 pin 展平成独立 component。
- `eda/data` 的 net 解析现在保留 `FID` feature 引用和 `SNT TOP T/B` pin 引用，用于 semantic connectivity。
- 新增 `odbpp to-auroradb` CLI 编排入口，用于执行 parse -> SemanticBoard -> Aurora/AAF/AuroraDB 转换。
- Rust parser crate 版本现在报告为 `0.2.0`。

## 0.1.0

- 新增 `ODBPP_PARSER_VERSION`，用于记录 ODB++ 解析器实现版本。
- 新增 Rust `crates/odbpp_parser` CLI，作为第一版 ODB++ 解析后端。
- 新增 ODB++ 目录、`.zip`、`.tgz`、`.tar.gz` 和 `.tar` 归档的内存读取能力。
- 新增 `matrix/matrix`、step 发现、profile、选定 step 的 layer `features`、component 记录和 net 名称的一阶段提取。
- 对不支持的 UNIX `.Z` 压缩成员文件输出非致命 diagnostics。
- 新增 `aurora_translator.odbpp.parse_odbpp(...)` 和 `aurora-translator odbpp parse` Python 集成入口。
- 新增第一版 ODB++ 解析集成链路和结构化 JSON 导出。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

## 0.6.3

- The Rust archive reader now skips individual ODB++ entries larger than 512 MiB by default and records a non-fatal diagnostic, preventing unusual archive members from inflating peak memory; the ODB++ JSON schema remains `0.6.0`.
- Added parser-level Rust unit tests covering tokenization, matrix rows, feature records, surface arcs, net pin/feature refs, and archive entry size limits.
- The Rust parser crate version now reports `0.6.3`.

## 0.6.2

- The Python integration now resolves the Rust CLI binary from the project root: `crates/odbpp_parser/target/release/odbpp_parser(.exe)`.
- The Rust archive reader skips unnecessary detail files for `--summary-only`, explicit `--step`, and default auto-step detail runs: summary-only loads only `matrix/matrix` and step `profile` files, explicit-step runs load only that step's layer/net/component/EDA details plus global symbols, and default detail parsing first selects a step through a summary pass before loading only the selected step's detail files.
- ODB++ JSON schema remains `0.6.0`; this release only fixes parser-binary path resolution and integration reliability.
- Verified a private ODB++ archive sample: Rust CLI parsing reports `steps=1`, `layers=32`, `features=111009`, `components=682`, `nets=656`, `diagnostics=2`, and the flow continues through Semantic/AuroraDB output.
- Installed and validated the local Rust toolchain; `cargo test --manifest-path crates/odbpp_parser/Cargo.toml` runs successfully.

## 0.6.1

- Improved the Rust ODB++ parser with streamed `.tgz` loading, shared file indexing, per-layer parallel parsing, and several hot-path string / numeric parsing reductions.
- Large ODB++ regression inputs now parse noticeably faster while keeping native and CLI summary results aligned.
- The Rust parser crate version now reports `0.6.1`.

## 0.6.0

- The Rust parser now shares one core and exposes both the `odbpp_parser` CLI and the `aurora_odbpp_native` PyO3 module.
- The Python integration now prefers the native module by default; passing `--rust-binary` explicitly forces the CLI.
- The Rust parser crate version now reports `0.6.0`.

## 0.5.0

- Added selected-step layer `attrlist` extraction as `layers[].layer_attributes` so stackup and material hints can be consumed by the Semantic adapter.
- Preserved top-level drill/rout `tools` metadata such as `THICKNESS`, `USER_PARAMS`, and unrecognized fields in `drill_tools[].raw_fields`.
- The Rust parser crate version now reports `0.5.0`.

## 0.4.0

- Added selected-step `drill_tools[]` extraction from layer `tools` files.
- Added selected-step `packages[]` extraction from `steps/<step>/eda/data`, including package indices, package properties, package pins, outlines, and common package geometry records (`RC`, `CR`, `SQ`, and contours).
- Corrected surface feature polarity parsing for `S` records and separated point-feature dcode/orientation values from pad symbol and polarity.
- Improved semicolon/comma attribute parsing for feature records.
- The Rust parser crate version now reports `0.4.0`.

## 0.3.0

- Added `symbols[]` extraction from ODB++ `symbols/<name>/features` files.
- Symbol definitions preserve parsed feature records and surface contours so custom pad shapes can be converted to semantic polygon shapes.
- EDA `FID` feature references now retain the current `SNT` type and associated `SNT TOP T/B` component-pin keys.
- The Rust parser crate version now reports `0.3.0`.

## 0.2.0

- Added feature indices, feature IDs, semicolon attributes, and surface contour extraction for selected-step layer `features` files.
- Components are now hierarchical: `CMP`/`COMP` placement records own child `TOP`/`BOT` pins and `PRP` properties instead of flattening pins as standalone components.
- EDA `eda/data` net parsing now preserves `FID` feature references and `SNT TOP T/B` pin references for semantic connectivity.
- Added `odbpp to-auroradb` CLI orchestration for parse -> SemanticBoard -> Aurora/AAF/AuroraDB conversion.
- The Rust parser crate version now reports `0.2.0`.

## 0.1.0

- Added `ODBPP_PARSER_VERSION` for the ODB++ parser implementation version.
- Added the Rust `crates/odbpp_parser` CLI as the first ODB++ backend.
- Added in-memory reading for ODB++ directories, `.zip`, `.tgz`, `.tar.gz`, and `.tar` archives.
- Added first-pass extraction for `matrix/matrix`, step discovery, profiles, selected-step layer `features`, component records, and net names.
- Added diagnostics for unsupported UNIX `.Z` compressed member files.
- Added Python integration through `aurora_translator.odbpp.parse_odbpp(...)` and `aurora-translator odbpp parse`.
- Added the first ODB++ parser integration path and structured JSON export.
