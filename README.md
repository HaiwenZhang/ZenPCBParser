<a id="top"></a>
# Aurora Translator

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

当前工作区本身就是 `aurora_translator` 主包目录。项目现在以 `SemanticBoard` 为统一中轴，主流程是：

- `AEDB -> SemanticBoard -> AuroraDB / 其他目标`
- `ODB++ -> SemanticBoard -> AuroraDB / 其他目标`
- `BRD / ALG -> SemanticBoard -> AuroraDB / 其他目标`
- `AuroraDB -> SemanticBoard -> 其他目标`

AAF 仍然支持，但它现在是 `targets/auroradb` 内部使用的过渡格式，不再作为项目级主格式来组织目录和命令。

### 当前能力

- 通过 PyEDB 的本地 `.NET` 后端打开 `.aedb`。
- 导出 AEDB 的 `metadata`、`summary`、`materials`、`layers`、`nets`、`components`、`padstacks`、`primitives`。
- AEDB 直接转换 AuroraDB 且未请求中间 JSON 时，默认启用 `auroradb-minimal` 解析 profile，仅保留 AuroraDB 必需字段和运行时几何缓存以缩短 path / polygon 解析时间。
- 读取 AuroraDB 的 `layout.db`、`parts.db`、`layers/*.lyr`，并导出结构化 JSON，可选保留原始 block tree。
- 通过 Rust `odbpp_parser` 解析核心读取 ODB++ 目录或归档；Python 侧默认优先使用 PyO3 native 模块，必要时回退到 CLI；Rust 侧会在 summary-only、显式 step 和默认 auto-step details 路径中跳过非必要明细文件，并导出 `metadata`、`summary`、`matrix`、`steps`、`symbols`、`layers`、层级化 `components/pins`、`nets` 及 feature/pin 引用、`diagnostics`。
- 通过 Rust `brd_parser` 解析 Cadence Allegro `.brd` 二进制文件，通过 Rust `alg_parser` 解析 Cadence extracta `.alg` 文本文件；两者都接入统一 CLI、source JSON、SemanticBoard 和 AuroraDB 导出链路。
- 将 ASIV AAF 命令文件 `design.layout`、`design.part` 作为 `auroradb.aaf` 子模块解析，并可派生 AuroraDB。
- 将 AEDB、AuroraDB、ODB++、BRD 和 ALG 的格式对象或已导出的格式 JSON 转换成统一 `SemanticBoard`，保留 materials、stackup layer、shape、via template、component、pin、trace、arc 和 polygon 语义，生成连接图与诊断，并可直接输出 AuroraDB；AAF 只在显式请求时导出。
- 在 JSON 中分别记录项目版本 `metadata.project_version`、格式解析器版本 `metadata.parser_version` 和格式 JSON schema 版本 `metadata.output_schema_version`。

### 环境配置

在 PowerShell 中运行：

```powershell
.\scripts\setup_env.ps1 -RunSmokeCheck
```

该脚本会安装或调用 `uv`，按 `.python-version` 准备 Python，执行 `uv sync --locked`，并在检测到 Rust `cargo` 时同时构建 ODB++ CLI 和安装 PyO3 native 模块。若只需要 Python 环境，可使用：

```powershell
.\scripts\setup_env.ps1 -SkipRustBuild
```

推送到 Git 仓库前可清理本地生成物：

```powershell
.\scripts\clean_project.ps1
```

### 运行

推荐优先使用新的语义主导命令：`convert`、`inspect`、`dump`、`schema`。所有命令默认都会写日志到 `logs/aurora_translator.log`，也都支持 `--log-file` 和 `--log-level`。

推荐主流程：

```powershell
uv run python .\main.py convert --from aedb --to auroradb <path-to-board.aedb> -o .\out\board_pkg
uv run python .\main.py convert --from odbpp --to auroradb <odbpp-dir-or-archive> -o .\out\odbpp_pkg
uv run python .\main.py convert --from alg --to auroradb <path-to-extracta.alg> -o .\out\alg_pkg
uv run python .\main.py inspect source --format auroradb <auroradb-dir>
uv run python .\main.py dump semantic-json --from auroradb <auroradb-dir> -o .\out\auroradb.semantic.json
uv run python .\main.py schema --format semantic -o .\semantic\docs\semantic_schema.json
```

如果想保留中间 JSON 便于对拍或调试：

```powershell
uv run python .\main.py convert --from aedb --to auroradb <path-to-board.aedb> -o .\out\board_pkg --source-output .\out\board.aedb.json --semantic-output .\out\board.semantic.json
uv run python .\main.py convert --from odbpp --to auroradb <odbpp-dir-or-archive> -o .\out\odbpp_pkg --source-output .\out\odbpp.json --semantic-output .\out\odbpp.semantic.json --coverage-output .\out\odbpp.coverage.json
uv run python .\main.py convert --from alg --to auroradb <path-to-extracta.alg> -o .\out\alg_pkg --source-output .\out\board.alg.json --semantic-output .\out\alg.semantic.json
```

当前还保留兼容命令：

```powershell
uv run python .\main.py <path-to-board.aedb> --summary-only
uv run python .\main.py auroradb inspect <auroradb-dir>
uv run python .\main.py auroradb from-aaf --part .\out\pkg\aaf\design.part --layout .\out\pkg\aaf\design.layout -o .\out\pkg\auroradb
uv run python .\main.py odbpp parse <odbpp-dir-or-archive> -o .\out\odbpp.json
uv run python .\main.py odbpp to-auroradb <odbpp-dir-or-archive> -o .\out\odbpp_pkg
uv run python .\main.py semantic from-source aedb <path-to-board.aedb>
uv run python .\main.py semantic source-to-auroradb odbpp <odbpp-dir-or-archive> -o .\out\odbpp_pkg
```

如果想在导出 AuroraDB 的同时保留 AAF：

```powershell
uv run python .\main.py convert --from odbpp --to auroradb <odbpp-dir-or-archive> -o .\out\odbpp_pkg --export-aaf
uv run python .\main.py semantic to-auroradb .\out\board.semantic.json -o .\out\auroradb_from_semantic --export-aaf
```

如果想显式强制 ODB++ 走 Rust CLI，而不是默认的 PyO3 native 模块，可使用：

```powershell
uv run python .\main.py convert --from odbpp --to auroradb <odbpp-dir-or-archive> --rust-binary .\crates\odbpp_parser\target\release\odbpp_parser.exe -o .\out\odbpp_pkg
```

语义主流程补充说明：

- `convert` 直接走“源文件 -> SemanticBoard -> 目标格式”
- `inspect source` 用于快速核对源格式摘要
- `dump source-json` / `dump semantic-json` 只在需要调试或留档时使用
- `schema` 统一导出机器可读 schema
- `-o/--out` 只表示输出目录；除非显式传入 `--source-output` 或 `--semantic-output`，否则不会默认写中间 payload JSON
- `convert --from aedb --to auroradb` 且无中间 JSON 输出时会自动使用 AEDB `auroradb-minimal` profile；如需完整 AEDB/Semantic 中间模型，可传入 `--source-output`、`--semantic-output` 或 `--aedb-parse-profile full`
- ODB++ 默认优先使用 `aurora_odbpp_native`；传入 `--rust-binary` 时强制走 `odbpp_parser` CLI
- ALG 默认优先使用 `aurora_alg_native`；传入 `--rust-binary` 时强制走 `alg_parser` CLI

当前输出目录结构分两种：

```text
<out>/
  stackup.dat
  stackup.json
  layout.db           # 仅 auroradb 目标默认生成
  parts.db            # 仅 auroradb 目标默认生成
  layers/             # 仅 auroradb 目标默认生成
```

如果显式导出 AAF，则会额外保留：

```text
<out>/
  stackup.dat
  stackup.json
  aaf/
    design.layout
    design.part
```

其中：

- `semantic to-aaf` 只生成 `stackup.dat`、`stackup.json` 和 `aaf/`
- `semantic to-auroradb` 默认直接把 `layout.db`、`parts.db` 和 `layers/` 写到 `-o` 指定目录，AAF 只作为内部过渡步骤，不默认保留
- 只有显式传入 `--export-aaf` 时，AuroraDB 目标才会额外保留 `aaf/`
- `semantic from-source` / `semantic source-to-aaf` / `semantic source-to-auroradb` 以及 `odbpp to-auroradb` 默认不会写中间 payload JSON；只有显式传入 `--semantic-output`、`--odbpp-output` 或 `--coverage-output` 时才会额外写文件

### 文档索引

- Agent 入口地图：[AGENTS.md](AGENTS.md)
- 根架构地图：[ARCHITECTURE.md](ARCHITECTURE.md)
- 设计约束：[docs/DESIGN.md](docs/DESIGN.md)
- 计划规则：[docs/PLANS.md](docs/PLANS.md)
- 产品判断：[docs/PRODUCT_SENSE.md](docs/PRODUCT_SENSE.md)
- 质量评分：[docs/QUALITY_SCORE.md](docs/QUALITY_SCORE.md)
- 可靠性规则：[docs/RELIABILITY.md](docs/RELIABILITY.md)
- 安全规则：[docs/SECURITY.md](docs/SECURITY.md)
- 项目架构：[中英双语](docs/architecture.md)
- 项目变更记录：[中英双语](docs/CHANGELOG.md)
- AEDB JSON 字段说明：[中英双语](sources/aedb/docs/aedb_json_schema.md)
- AEDB 变更记录：[中英双语](sources/aedb/docs/CHANGELOG.md)
- AEDB schema 变更记录：[中英双语](sources/aedb/docs/SCHEMA_CHANGELOG.md)
- AuroraDB 架构：[中英双语](sources/auroradb/docs/architecture.md)
- AuroraDB 与 AAF 支持说明：[中英双语](sources/auroradb/docs/auroradb.md)
- AuroraDB JSON 字段说明：[中英双语](sources/auroradb/docs/auroradb_json_schema.md)
- AuroraDB 变更记录：[中英双语](sources/auroradb/docs/CHANGELOG.md)
- AuroraDB schema 变更记录：[中英双语](sources/auroradb/docs/SCHEMA_CHANGELOG.md)
- ODB++ JSON 字段说明：[中英双语](sources/odbpp/docs/odbpp_json_schema.md)
- ODB++ 变更记录：[中英双语](sources/odbpp/docs/CHANGELOG.md)
- ODB++ schema 变更记录：[中英双语](sources/odbpp/docs/SCHEMA_CHANGELOG.md)
- ODB++ 官方规范：ODB++Design Format Specification Release 8.1 Update 4, August 2024 ([PDF](https://odbplusplus.com//wp-content/uploads/sites/2/2024/08/odb_spec_user.pdf)，[Resources](https://odbplusplus.com/design/our-resources/))
- ODB++ 官方规范工程总结：[中英双语](sources/odbpp/docs/odbpp_design_spec_summary.md)
- Semantic 架构：[中英双语](semantic/docs/architecture.md)
- AEDB 到 Semantic 转换说明：[中英双语](semantic/docs/aedb_to_semantic.md)
- 跨格式语义映射表：[中英双语](semantic/docs/format_mapping.md)
- Semantic JSON 字段说明：[中英双语](semantic/docs/semantic_json_schema.md)
- Semantic 变更记录：[中英双语](semantic/docs/CHANGELOG.md)
- Semantic schema 变更记录：[中英双语](semantic/docs/SCHEMA_CHANGELOG.md)
- 机器可读 schema：[AEDB](sources/aedb/docs/aedb_schema.json)、[AuroraDB](sources/auroradb/docs/auroradb_schema.json)、[ODB++](sources/odbpp/docs/odbpp_schema.json)、[Semantic](semantic/docs/semantic_schema.json)

### 项目结构

- [docs](docs)：项目级架构文档和项目级变更记录。
- [sources/aedb](sources/aedb)：AEDB 源解析、PyEDB 会话、extractor、schema 和格式级文档。
- [sources/auroradb](sources/auroradb)：AuroraDB 源读取、block/model、inspect/diff、schema 和格式级文档。
- [sources/odbpp](sources/odbpp)：ODB++ Python 集成、Pydantic 模型、coverage、schema 和格式级文档。
- [sources/brd](sources/brd)：Cadence Allegro BRD Python 集成、Pydantic 模型和 schema。
- [sources/alg](sources/alg)：Cadence extracta ALG Python 集成、Pydantic 模型和 schema。
- [semantic](semantic)：统一 `SemanticBoard`、格式 adapter、连接图和语义诊断。
- [targets/auroradb](targets/auroradb)：`SemanticBoard -> AuroraDB` 目标导出链路；AAF 只作为内部中间层或显式导出产物，主 exporter 只负责编排，导出索引、direct builder、layout、parts、geometry、stackup、格式化 helper 和命名 helper 已拆到独立模块。
- [pipeline](pipeline)：`source -> semantic -> target` 主流程编排。
- [shared](shared)：日志、性能统计、JSON 输出等共享工具。
- [crates/odbpp_parser](crates/odbpp_parser)：Rust ODB++ 解析核心、CLI 和 PyO3 native 模块。
- [crates/brd_parser](crates/brd_parser)：Rust Cadence Allegro BRD 二进制解析核心、CLI 和 PyO3 native 模块。
- [crates/alg_parser](crates/alg_parser)：Rust Cadence extracta ALG 文本解析核心、CLI 和 PyO3 native 模块。
- [scripts](scripts)：环境配置与本地生成物清理脚本。
- [cli](cli)：新的 `convert / inspect / dump / schema` 入口，以及保留的兼容命令。
旧的 `layout_parser` 兼容包装已移到上一层目录的 [layout_parser](../layout_parser)，当前项目只保留 `aurora_translator` 主包。

### 代码风格

- Python 代码统一使用 Ruff formatter，配置维护在 `pyproject.toml` 的 `[tool.ruff]` 和 `[tool.ruff.format]`。
- 提交前先运行 `uv run ruff format .`，再运行 `uv run ruff check .`。
- CI 或只读检查应使用 `uv run ruff format --check .` 确认格式没有漂移。

### 版本规则

- `PROJECT_VERSION`：整个 Aurora Translator 项目版本，对应 `metadata.project_version` 和 `pyproject.toml`。
- `AEDB_PARSER_VERSION` / `AURORADB_PARSER_VERSION` / `ODBPP_PARSER_VERSION` / `BRD_PARSER_VERSION` / `ALG_PARSER_VERSION`：格式解析器版本，对应各格式 JSON 的 `metadata.parser_version`。
- `AEDB_JSON_SCHEMA_VERSION` / `AURORADB_JSON_SCHEMA_VERSION` / `ODBPP_JSON_SCHEMA_VERSION` / `BRD_JSON_SCHEMA_VERSION` / `ALG_JSON_SCHEMA_VERSION`：格式 JSON schema 版本，对应各格式 JSON 的 `metadata.output_schema_version`。
- `SEMANTIC_PARSER_VERSION` / `SEMANTIC_JSON_SCHEMA_VERSION`：语义层转换逻辑版本和 semantic JSON schema 版本。
- 格式解析逻辑、性能、集成方式变化时，更新对应格式 parser version，并记录到该格式 `docs/CHANGELOG.md`。
- JSON 字段、字段含义或结构变化时，更新对应格式 JSON schema version，并记录到该格式 `docs/SCHEMA_CHANGELOG.md`。
- 项目发布或集成格式级变更时，更新 `PROJECT_VERSION`，并记录到 [docs/CHANGELOG.md](docs/CHANGELOG.md)。

当前版本：

- Project version: `1.0.44`
- AEDB parser version: `0.4.56`
- AEDB JSON schema version: `0.5.0`
- AuroraDB parser version: `0.2.14`
- AuroraDB JSON schema version: `0.2.0`
- ODB++ parser version: `0.6.3`
- ODB++ JSON schema version: `0.6.0`
- BRD parser version: `0.1.9`
- BRD JSON schema version: `0.5.0`
- ALG parser version: `0.1.1`
- ALG JSON schema version: `0.2.0`
- Semantic parser version: `0.7.13`
- Semantic JSON schema version: `0.7.2`

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

This workspace is the `aurora_translator` main package directory. The project now uses `SemanticBoard` as its single conversion hub. The main supported flows are:

- `AEDB -> SemanticBoard -> AuroraDB / other targets`
- `ODB++ -> SemanticBoard -> AuroraDB / other targets`
- `BRD / ALG -> SemanticBoard -> AuroraDB / other targets`
- `AuroraDB -> SemanticBoard -> other targets`

AAF is still supported, but it now lives inside `targets/auroradb` as the transitional format used by the AuroraDB target path instead of as a top-level project format.

### Capabilities

- Opens `.aedb` directories through PyEDB's local `.NET` backend.
- Exports AEDB `metadata`, `summary`, `materials`, `layers`, `nets`, `components`, `padstacks`, and `primitives`.
- AEDB direct AuroraDB conversion automatically uses the `auroradb-minimal` parse profile when no intermediate JSON is requested, keeping only AuroraDB-required fields and runtime geometry caches to reduce path / polygon parse time.
- Reads AuroraDB `layout.db`, `parts.db`, and `layers/*.lyr`, exporting structured JSON with optional raw block trees.
- Reads ODB++ directories or archives through the Rust `odbpp_parser` parser core; Python prefers the PyO3 native module and can fall back to the CLI; Rust skips unnecessary detail files for summary-only, explicit-step, and default auto-step detail runs while exporting `metadata`, `summary`, `matrix`, `steps`, `layers`, `components`, `nets`, and `diagnostics`.
- Reads Cadence Allegro `.brd` binary files through the Rust `brd_parser`, and Cadence extracta `.alg` text files through the Rust `alg_parser`; both are integrated with the unified CLI, source JSON, SemanticBoard, and AuroraDB export paths.
- Parses ASIV AAF command files `design.layout` and `design.part` as the `auroradb.aaf` submodule and can generate AuroraDB.
- Converts AEDB, AuroraDB, ODB++, BRD, and ALG format objects or exported format JSON payloads into a unified `SemanticBoard` with material, stackup-layer, shape, via-template, component, pin, trace, arc, and polygon semantics, connectivity diagnostics, and direct AuroraDB output; AAF is exported only when requested explicitly.
- Records `metadata.project_version`, `metadata.parser_version`, and `metadata.output_schema_version` in generated JSON.

### Environment Setup

Run this in PowerShell:

```powershell
.\scripts\setup_env.ps1 -RunSmokeCheck
```

The script installs or uses `uv`, prepares Python from `.python-version`, runs `uv sync --locked`, and when Rust `cargo` is available it both builds the ODB++ CLI and installs the PyO3 native module. For Python-only setup:

```powershell
.\scripts\setup_env.ps1 -SkipRustBuild
```

Before pushing to Git, clean local generated files with:

```powershell
.\scripts\clean_project.ps1
```

### Usage

Prefer the new semantic-centered commands first: `convert`, `inspect`, `dump`, and `schema`. Every command writes logs to `logs/aurora_translator.log` by default and also supports `--log-file` and `--log-level`.

Recommended workflow:

```powershell
uv run python .\main.py convert --from aedb --to auroradb <path-to-board.aedb> -o .\out\board_pkg
uv run python .\main.py convert --from odbpp --to auroradb <odbpp-dir-or-archive> -o .\out\odbpp_pkg
uv run python .\main.py convert --from alg --to auroradb <path-to-extracta.alg> -o .\out\alg_pkg
uv run python .\main.py inspect source --format auroradb <auroradb-dir>
uv run python .\main.py dump semantic-json --from auroradb <auroradb-dir> -o .\out\auroradb.semantic.json
uv run python .\main.py schema --format semantic -o .\semantic\docs\semantic_schema.json
```

If you want intermediate JSON for debugging or comparison:

```powershell
uv run python .\main.py convert --from aedb --to auroradb <path-to-board.aedb> -o .\out\board_pkg --source-output .\out\board.aedb.json --semantic-output .\out\board.semantic.json
uv run python .\main.py convert --from odbpp --to auroradb <odbpp-dir-or-archive> -o .\out\odbpp_pkg --source-output .\out\odbpp.json --semantic-output .\out\odbpp.semantic.json --coverage-output .\out\odbpp.coverage.json
uv run python .\main.py convert --from alg --to auroradb <path-to-extracta.alg> -o .\out\alg_pkg --source-output .\out\board.alg.json --semantic-output .\out\alg.semantic.json
```

Compatibility commands are still available:

```powershell
uv run python .\main.py <path-to-board.aedb> --summary-only
uv run python .\main.py auroradb inspect <auroradb-dir>
uv run python .\main.py auroradb from-aaf --part .\out\pkg\aaf\design.part --layout .\out\pkg\aaf\design.layout -o .\out\pkg\auroradb
uv run python .\main.py odbpp parse <odbpp-dir-or-archive> -o .\out\odbpp.json
uv run python .\main.py odbpp to-auroradb <odbpp-dir-or-archive> -o .\out\odbpp_pkg
uv run python .\main.py semantic from-source aedb <path-to-board.aedb>
uv run python .\main.py semantic source-to-auroradb odbpp <odbpp-dir-or-archive> -o .\out\odbpp_pkg
```

If you also want to keep the AAF files while exporting AuroraDB:

```powershell
uv run python .\main.py convert --from odbpp --to auroradb <odbpp-dir-or-archive> -o .\out\odbpp_pkg --export-aaf
uv run python .\main.py semantic to-auroradb .\out\board.semantic.json -o .\out\auroradb_from_semantic --export-aaf
```

To force ODB++ to use the Rust CLI instead of the default PyO3 native module:

```powershell
uv run python .\main.py convert --from odbpp --to auroradb <odbpp-dir-or-archive> --rust-binary .\crates\odbpp_parser\target\release\odbpp_parser.exe -o .\out\odbpp_pkg
```

In practice:

- `convert` runs `source -> SemanticBoard -> target`
- `inspect source` is the fast source-summary path
- `dump source-json` / `dump semantic-json` are for debugging and archiving
- `schema` exports the machine-readable schemas
- `-o/--out` only specifies the output directory; no intermediate payload JSON is written unless you pass `--source-output` or `--semantic-output`
- `convert --from aedb --to auroradb` automatically uses the AEDB `auroradb-minimal` profile when no intermediate JSON is requested; pass `--source-output`, `--semantic-output`, or `--aedb-parse-profile full` when you need the complete AEDB/Semantic intermediate model
- ODB++ prefers `aurora_odbpp_native` by default; passing `--rust-binary` forces the `odbpp_parser` CLI
- ALG prefers `aurora_alg_native` by default; passing `--rust-binary` forces the `alg_parser` CLI

There are now two output shapes:

```text
<out>/
  stackup.dat
  stackup.json
  layout.db           # generated by the auroradb target by default
  parts.db            # generated by the auroradb target by default
  layers/             # generated by the auroradb target by default
```

When AAF export is requested explicitly, the output also keeps:

```text
<out>/
  stackup.dat
  stackup.json
  aaf/
    design.layout
    design.part
```

In practice:

- `semantic to-aaf` only writes `stackup.dat`, `stackup.json`, and `aaf/`
- `semantic to-auroradb` writes `layout.db`, `parts.db`, and `layers/` directly under `-o` by default; AAF remains an internal transition step and is not kept unless requested
- AuroraDB-target commands keep `aaf/` only when `--export-aaf` is passed explicitly
- `semantic from-source` / `semantic source-to-aaf` / `semantic source-to-auroradb` and `odbpp to-auroradb` do not write intermediate payload JSON unless you explicitly pass `--semantic-output`, `--odbpp-output`, or `--coverage-output`

### Documentation Index

- Agent entry map: [AGENTS.md](AGENTS.md)
- Root architecture map: [ARCHITECTURE.md](ARCHITECTURE.md)
- Design invariants: [docs/DESIGN.md](docs/DESIGN.md)
- Planning rules: [docs/PLANS.md](docs/PLANS.md)
- Product sense: [docs/PRODUCT_SENSE.md](docs/PRODUCT_SENSE.md)
- Quality score: [docs/QUALITY_SCORE.md](docs/QUALITY_SCORE.md)
- Reliability rules: [docs/RELIABILITY.md](docs/RELIABILITY.md)
- Security rules: [docs/SECURITY.md](docs/SECURITY.md)
- Project architecture: [Bilingual](docs/architecture.md)
- Project changelog: [Bilingual](docs/CHANGELOG.md)
- AEDB JSON field guide: [Bilingual](sources/aedb/docs/aedb_json_schema.md)
- AEDB changelog: [Bilingual](sources/aedb/docs/CHANGELOG.md)
- AEDB schema changelog: [Bilingual](sources/aedb/docs/SCHEMA_CHANGELOG.md)
- AuroraDB architecture: [Bilingual](sources/auroradb/docs/architecture.md)
- AuroraDB and AAF support: [Bilingual](sources/auroradb/docs/auroradb.md)
- AuroraDB JSON field guide: [Bilingual](sources/auroradb/docs/auroradb_json_schema.md)
- AuroraDB changelog: [Bilingual](sources/auroradb/docs/CHANGELOG.md)
- AuroraDB schema changelog: [Bilingual](sources/auroradb/docs/SCHEMA_CHANGELOG.md)
- ODB++ JSON field guide: [Bilingual](sources/odbpp/docs/odbpp_json_schema.md)
- ODB++ changelog: [Bilingual](sources/odbpp/docs/CHANGELOG.md)
- ODB++ schema changelog: [Bilingual](sources/odbpp/docs/SCHEMA_CHANGELOG.md)
- ODB++ official specification: ODB++Design Format Specification Release 8.1 Update 4, August 2024 ([PDF](https://odbplusplus.com//wp-content/uploads/sites/2/2024/08/odb_spec_user.pdf), [Resources](https://odbplusplus.com/design/our-resources/))
- ODB++ official specification engineering summary: [Bilingual](sources/odbpp/docs/odbpp_design_spec_summary.md)
- Semantic architecture: [Bilingual](semantic/docs/architecture.md)
- AEDB to Semantic conversion guide: [Bilingual](semantic/docs/aedb_to_semantic.md)
- Cross-format semantic mapping table: [Bilingual](semantic/docs/format_mapping.md)
- Semantic JSON field guide: [Bilingual](semantic/docs/semantic_json_schema.md)
- Semantic changelog: [Bilingual](semantic/docs/CHANGELOG.md)
- Semantic schema changelog: [Bilingual](semantic/docs/SCHEMA_CHANGELOG.md)
- Machine-readable schemas: [AEDB](sources/aedb/docs/aedb_schema.json), [AuroraDB](sources/auroradb/docs/auroradb_schema.json), [ODB++](sources/odbpp/docs/odbpp_schema.json), [Semantic](semantic/docs/semantic_schema.json)

### Project Structure

- [docs](docs): project-level architecture documentation and project-level changelogs.
- [sources/aedb](sources/aedb): AEDB source parsing, PyEDB session management, extractors, schema, and format docs.
- [sources/auroradb](sources/auroradb): AuroraDB source reading, block/model handling, inspect/diff, schema, and format docs.
- [sources/odbpp](sources/odbpp): ODB++ Python integration, Pydantic models, coverage, schema, and format docs.
- [sources/brd](sources/brd): Cadence Allegro BRD Python integration, Pydantic models, and schema.
- [sources/alg](sources/alg): Cadence extracta ALG Python integration, Pydantic models, and schema.
- [semantic](semantic): the unified `SemanticBoard`, format adapters, connectivity graph, and diagnostics.
- [targets/auroradb](targets/auroradb): the `SemanticBoard -> AuroraDB` target export path, with AAF kept only as an internal or explicitly exported intermediate; the main exporter now only orchestrates, while export indexes, direct builders, layout, parts, geometry, stackup handling, formatting helpers, and naming helpers live in focused modules.
- [pipeline](pipeline): the `source -> semantic -> target` orchestration layer.
- [shared](shared): shared logging, runtime metrics, and JSON output helpers.
- [crates/odbpp_parser](crates/odbpp_parser): Rust ODB++ parser core, CLI, and PyO3 native module.
- [crates/brd_parser](crates/brd_parser): Rust Cadence Allegro BRD binary parser core, CLI, and PyO3 native module.
- [crates/alg_parser](crates/alg_parser): Rust Cadence extracta ALG text parser core, CLI, and PyO3 native module.
- [scripts](scripts): environment setup and local generated-file cleanup scripts.
- [cli](cli): the new `convert / inspect / dump / schema` entrypoints plus compatibility commands.
The old `layout_parser` compatibility wrapper has moved to [layout_parser](../layout_parser). This project now keeps only the main `aurora_translator` package.

### Code Style

- Python code uses the Ruff formatter, configured in `pyproject.toml` under `[tool.ruff]` and `[tool.ruff.format]`.
- Before committing, run `uv run ruff format .`, then `uv run ruff check .`.
- CI or read-only validation should run `uv run ruff format --check .` to catch formatting drift.

### Version Rules

- `PROJECT_VERSION`: overall Aurora Translator project version, mapped to `metadata.project_version` and `pyproject.toml`.
- `AEDB_PARSER_VERSION` / `AURORADB_PARSER_VERSION` / `ODBPP_PARSER_VERSION` / `BRD_PARSER_VERSION` / `ALG_PARSER_VERSION`: format parser versions, mapped to each format JSON payload's `metadata.parser_version`.
- `AEDB_JSON_SCHEMA_VERSION` / `AURORADB_JSON_SCHEMA_VERSION` / `ODBPP_JSON_SCHEMA_VERSION` / `BRD_JSON_SCHEMA_VERSION` / `ALG_JSON_SCHEMA_VERSION`: format JSON schema versions, mapped to each format JSON payload's `metadata.output_schema_version`.
- `SEMANTIC_PARSER_VERSION` / `SEMANTIC_JSON_SCHEMA_VERSION`: semantic conversion logic version and semantic JSON schema version.
- When parsing logic, performance, or integration behavior changes, update the corresponding parser version and record the change in that format's `docs/CHANGELOG.md`.
- When JSON fields, field meanings, or structure change, update the corresponding JSON schema version and record the change in that format's `docs/SCHEMA_CHANGELOG.md`.
- For project releases or integrated format-level changes, update `PROJECT_VERSION` and record the change in [docs/CHANGELOG.md](docs/CHANGELOG.md).

Current versions:

- Project version: `1.0.44`
- AEDB parser version: `0.4.56`
- AEDB JSON schema version: `0.5.0`
- AuroraDB parser version: `0.2.14`
- AuroraDB JSON schema version: `0.2.0`
- ODB++ parser version: `0.6.3`
- ODB++ JSON schema version: `0.6.0`
- BRD parser version: `0.1.9`
- BRD JSON schema version: `0.5.0`
- ALG parser version: `0.1.1`
- ALG JSON schema version: `0.2.0`
- Semantic parser version: `0.7.13`
- Semantic JSON schema version: `0.7.2`
