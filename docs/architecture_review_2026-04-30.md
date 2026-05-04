# Aurora Translator Architecture Review

## 目的

本文基于外部审查规则 `<RULES_FILE>` 对 Aurora Translator 做软件架构、数据结构、算法、依赖、运行路径和验证体系审查。

规则重点：

- `Data Structures Over Code`: 优先看数据模型和 Data Layout，不只看代码分支。
- `Extreme Minimalism`: 依赖、抽象和中间层必须证明自己的价值。
- 关注 Performance、Memory、Dispatch、Hidden State 和 Leaky Abstractions。

## 范围

已审查：

- 项目主流程：`cli/`、`pipeline/`、`sources/`、`semantic/`、`targets/`
- Python 数据模型：`sources/*/models.py`、`semantic/models.py`
- 关键转换算法：`semantic/adapters/*`、`semantic/passes.py`
- AuroraDB 导出：`targets/auroradb/exporter.py`、`targets/auroradb/direct.py`、`targets/auroradb/layout.py`、`targets/auroradb/parts.py`、`targets/auroradb/geometry.py`、`targets/auroradb/stackup.py`、`targets/auroradb/formatting.py`、`targets/auroradb/names.py`
- Rust ODB++ parser：`crates/odbpp_parser/src/*`
- 包依赖与入口：`pyproject.toml`、`main.py`、`cli/main.py`

本轮补充覆盖：

- 使用私有 AEDB / ODB++ 样本做端到端转换，输出放在样本目录同级 `<CASE_ROOT>/outputs/...`。
- 本机已安装 Rust/Cargo toolchain，并执行 `cargo test --manifest-path crates/odbpp_parser/Cargo.toml`。

本轮边界：

- 未做 Web 搜索；当前问题均能从本地代码和项目规则判断。
- 当前审查问题均已在本地闭环；后续工作仅剩随需求演进的增量维护。

## 重构执行记录

本次依据审查意见完成以下收敛：

- 已移除 AEDB source model 和 Semantic model 上的 AuroraDB 私有运行时 `NetGeom` 缓存。
- `auroradb-minimal` profile 改为保留显式 `center_line`、`raw_points` 和 void raw geometry；AuroraDB exporter 从这些可序列化几何字段生成目标格式。
- `sources/aedb/extractors/primitives.py` 的 polygon arc 热路径不再混合 AuroraDB `Pnt` / `Parc` 文本生成。
- CLI 主入口、source loader 和 inspect 分支改为懒加载，非 AEDB 路径不再提前加载 PyEDB。
- 新增 `targets/auroradb/plan.py`，集中板级导出索引，作为后续拆分 direct layout / parts / geometry exporter 的基础。
- 新增 `targets/auroradb/formatting.py`，把单位换算、数值解析、坐标解析和旋转格式化 helper 从主 exporter 中拆出，降低 exporter 的无状态工具负担。
- 新增 `targets/auroradb/names.py`，把命名规范化、net name 规范化、AAF atom quoting 和 pin sort key 从主 exporter 中拆出。
- 新增 `targets/auroradb/stackup.py`，把 stackup layer planning、generated dielectric 和 `stackup.dat` / `stackup.json` serialization 从主 exporter 中拆出。
- 新增 `targets/auroradb/direct.py`、`targets/auroradb/layout.py`、`targets/auroradb/parts.py` 和 `targets/auroradb/geometry.py`，把 direct builder 状态、`layout.db` / `design.layout`、`parts.db` / `design.part`、shape/via/trace/polygon geometry payload 分出主 exporter；`targets/auroradb/exporter.py` 已降为顶层编排文件。
- 新增 `tests/` 轻量架构护栏，覆盖私有缓存移除、Semantic JSON 显式几何、CLI lazy import 和 direct trace exporter；随后补齐 pytest/golden fixture 基座。
- 同步 `PROJECT_VERSION=1.0.42`、`AEDB_PARSER_VERSION=0.4.56`、`SEMANTIC_PARSER_VERSION=0.7.1`、`ODBPP_PARSER_VERSION=0.6.3`、changelog、版本表和 JSON schema 文件。
- 第二轮继续将 `SemanticFootprint.geometry`、`SemanticViaTemplate.geometry`、`SemanticPad.geometry`、`SemanticVia.geometry`、`SemanticPrimitive.geometry` 和 `SemanticBoard.board_outline` 收敛为 typed hint model，并同步 Semantic parser/schema 到 `0.7.0`；随后修正 AEDB arc-height 到 AuroraDB `CCW` 的方向映射，Semantic parser 更新到 `0.7.1`，schema 仍为 `0.7.0`。
- 修正 ODB++ Python 集成层的 Rust CLI binary 自动定位路径，并继续同步到 `ODBPP_PARSER_VERSION=0.6.3`。
- Rust archive reader 在 summary-only、显式 selected step 和默认 auto-step details 时跳过非必要明细文件，并新增 archive filter、entry size limit、tokenizer、matrix、feature 和 net parser 单元测试。
- 新增 GitHub Actions CI，覆盖 `ruff format --check`、`ruff check`、Python compile、`unittest`、`pytest` 和 `cargo test`。
- 批量移除项目 Markdown 文档 UTF-8 BOM，避免普通 UTF-8 工具链读取失败。
- 新增默认跳过的私有样本回归测试入口：设置 `AURORA_TRANSLATOR_RUN_CASES=1` 和 `AURORA_TRANSLATOR_CASE_ROOT` 后可复跑 AEDB minimal/full hash 对比与 ODB++ 端到端计数检查。
- 私有 ODB++ 样本验证结果：`layers=32`、`materials=2`、`shapes=253`、`via_templates=66`、`nets=655`、`components=682`、`footprints=73`、`pins=3017`、`pads=24472`、`vias=5466`、`primitives=111009`、`diagnostics=2`。
- 私有 AEDB 样本验证结果：minimal/full 两条 AuroraDB 输出路径均为 `layers=21`、`materials=13`、`shapes=33`、`via_templates=21`、`nets=325`、`components=282`、`pins=1432`、`pads=1432`、`vias=1160`、`primitives=2355`、`diagnostics=2`，14 个输出文件 SHA-256 完全一致。

## 核心判决

- **状态**: ✅ 审查项全部闭环
- **一句话结论**: `SemanticBoard` 中轴保留，AuroraDB 私有缓存已切断，typed geometry、target pass 拆分、lazy import、Rust selected-step 读取、entry size diagnostic、pytest/golden 和 CI 均已落地。
- **级别**: 🟢 Art

## 好的部分

- `pipeline/convert.py` 很薄，职责清楚：load source、build `SemanticBoard`、export target。这个 Dispatch 方向正确。
- `sources/`、`semantic/`、`targets/` 的目录边界清楚，至少工程叙事没有散。
- Rust ODB++ parser 用 `IndexedFiles<'a>` 保存文件字节引用，解析层避免了二次复制部分内容，这个 Data Layout 有意识。
- `semantic/adapters/odbpp.py` 中 via 与 pad 匹配使用 coordinate bucket，例如 `_coord_bucket()`，这比全表距离扫描强。
- 版本规则和文档规则完整，`docs/versioning_policy.md` 对 parser、schema、project version 的分层是正确的。

## 数据结构性失误

### 1. `SemanticBoard` 不是纯 semantic，混进了 AuroraDB schema

证据：

- `semantic/models.py` 中 `SemanticShape.auroradb_type` 固定写入 AuroraDB 几何名。
- `semantic/models.py` 中 `SemanticPrimitive` 挂了 `_auroradb_netgeom_lines` 和 `_auroradb_trace_netgeom_items` PrivateAttr。
- `sources/aedb/models.py` 的 `PathPrimitiveModel` 和 `PolygonPrimitiveModel` 也挂了 AuroraDB private cache。
- `semantic/adapters/aedb.py` 会把 AEDB primitive 的 AuroraDB cache 复制到 semantic primitive。
- `targets/auroradb/exporter.py` 又读取这些 hidden cache。

这不是优化，这是抽象泄漏。`SemanticBoard` 变成了“Semantic + AuroraDB backchannel”。更坏的是 PrivateAttr 不进 JSON，所以内存转换和 JSON 中转转换可能不是同一条语义路径。

风险：

- `AEDB -> SemanticBoard -> AuroraDB` 和 `AEDB -> Semantic JSON -> AuroraDB` 可能输出不一致。
- 后续新增目标格式时，会被 `auroradb_type` 和 hidden cache 拖住。
- Debug 时看 JSON 看不到真正影响输出的 hidden state。

审查意见：

- 删除 semantic 层和 source 层的 AuroraDB private cache。
- 引入中立几何 IR，把 `Pnt`、`Larc`、`Parc` 这类 AuroraDB token 留在 target 层。
- 如果必须缓存解析结果，缓存 typed geometry，不缓存 target-format lines。

### 2. `geometry: dict[str, Any]` 是当前最大的数据模型债务

证据：

- `SemanticViaTemplate.geometry`
- `SemanticFootprint.geometry`
- `SemanticPad.geometry`
- `SemanticVia.geometry`
- `SemanticPrimitive.geometry`
- `SemanticBoard.board_outline`

这些字段都用 `dict[str, Any]`。这让 Pydantic schema 只剩壳，真正协议藏在字符串 key 和各 target 的 `if` 里。

后果：

- 算法到处写 `geometry.get("shape_id")`、`geometry.get("rotation")`、`geometry.get("raw_points")`。
- 单位换算分散在 adapter 和 exporter。
- 字段拼写错误不会被 schema 抓住。
- shape、trace、arc、polygon、pad、via 的数据布局不明确，导致 target 层必须猜。

审查意见：

- 用 discriminated union 替代 `dict[str, Any]`。
- 统一坐标和长度单位，进入 `SemanticBoard` 时完成 canonicalization。
- 保留 `raw` 字段作为调试逃生口，但不能让 exporter 依赖 `raw`。

建议骨架：

```python
class Length(SchemaModel):
    value: float
    unit: Literal["mil", "mm", "meter"]


class TraceGeometry(SchemaModel):
    kind: Literal["trace"] = "trace"
    width: Length
    vertices: list[SemanticPoint]
    segments: list[Literal["line", "arc"]]


class PolygonGeometry(SchemaModel):
    kind: Literal["polygon"] = "polygon"
    contour: list[SemanticPoint]
    arcs: list[ArcSegment] = Field(default_factory=list)
    voids: list["PolygonGeometry"] = Field(default_factory=list)
    polarity: Literal["positive", "negative"] = "positive"


class SemanticPrimitive(SchemaModel):
    id: str
    layer_name: str | None = None
    net_id: str | None = None
    geometry: Annotated[
        TraceGeometry | PolygonGeometry | PadGeometry | ViaGeometry | RawFeatureGeometry,
        Field(discriminator="kind"),
    ]
```

### 3. Summary 是缓存字段，容易陈旧

`SemanticBoard.with_computed_summary()` 直接改 `self.summary`。这比复制整板省内存，但 summary 仍然是派生数据。只要后续有人直接 append `board.primitives`，summary 就失真。

审查意见：

- 内部算法使用 `len(board.primitives)` 等真实集合，不依赖 summary。
- 输出 JSON 时再 materialize summary。
- 如保留 summary，所有 mutating pass 必须统一通过 `BoardBuilder.finalize()`。

## 抽象泄漏

### 1. Source 层知道 target 细节

`sources/aedb/extractors/primitives.py` 中大量 `_auroradb_*` helper 直接生成 AuroraDB item lines。source parser 的职责应该是“忠实解析 AEDB”，不是“提前替 AuroraDB 导出铺路”。

审查意见：

- AEDB source 只输出 typed primitive geometry。
- AuroraDB 输出优化放在 `targets/auroradb/`。
- 若 AEDB 专用 fast path 必须保留，也要命名为 `AedbGeometryCache`，字段结构仍然 target-neutral。

### 2. Target exporter 同时在做 converter、compiler、writer

审查时 `targets/auroradb/exporter.py` 约 4670 行，里面同时处理：

- stackup material
- layer name mapping
- AAF text generation
- direct AuroraDB block generation
- part/footprint variant planning
- AEDB placement rotation correction
- polygon/arc serialization
- net/via/component binding
- output cleanup

这不是一个 exporter，这是一个小型编译器塞进一个文件。问题不是文件长，而是 pass 没有边界。

审查意见：

- 拆出稳定 pass：
  - `stackup_plan.py`
  - `geometry_plan.py`
  - `part_plan.py`
  - `layout_plan.py`
  - `auroradb_blocks.py`
  - `aaf_writer.py`
- 每个 pass 输入输出都是 dataclass，不直接写文件。
- 最后一个 writer pass 才碰文件系统。

建议骨架：

```python
@dataclass(slots=True)
class ExportPlan:
    stackup: StackupPlan
    layers: list[LayerPlan]
    parts: list[PartPlan]
    nets: list[NetPlan]
    diagnostics: list[ExportDiagnostic]


def plan_auroradb(board: SemanticBoard) -> ExportPlan:
    index = BoardIndex.from_board(board)
    return ExportPlan(
        stackup=plan_stackup(index),
        layers=plan_layers(index),
        parts=plan_parts(index),
        nets=plan_nets(index),
        diagnostics=index.diagnostics,
    )


def write_auroradb_plan(plan: ExportPlan, output: Path) -> None:
    write_stackup(plan.stackup, output)
    write_layout_blocks(plan, output)
    write_part_blocks(plan, output)
```

## 算法与 Performance

### 1. Rust ODB++ parser 把整个输入包读进内存

证据：

- `OdbSource.files: BTreeMap<String, Vec<u8>>`
- `read_directory()` 对每个文件 `fs::read(file_path)`
- `read_zip()` 和 `read_tar_stream()` 对每个 entry `read_to_end()`

这个设计简单，但对大 ODB++ archive 不友好。真实 PCB 数据可能很大，全部读入内存再解析，会放大 peak RSS。规则里的 8GB Reality Check 在这里是实打实的问题。

审查意见：

- 第一阶段只建立 file index，不读全部内容。
- 只读取当前 selected step 需要的文件。
- 对 archive entry 加大小上限和 allowlist。
- summary-only 模式不应读取 feature bodies。

建议骨架：

```rust
struct OdbLocator {
    path: String,
    size: u64,
}

trait OdbFileReader {
    fn read(&mut self, locator: &OdbLocator) -> Result<Cow<'_, [u8]>, ArchiveError>;
}

struct OdbIndex {
    matrix: Option<OdbLocator>,
    steps: BTreeMap<String, StepIndex>,
    symbols: Vec<OdbLocator>,
}

fn parse_odb<R: OdbFileReader>(
    index: &OdbIndex,
    reader: &mut R,
    options: &ParseOptions,
) -> ParsedOdb {
    // read matrix first, select step, then read only that step's files
}
```

### 2. ODB++ token model保留大量 `Vec<String>`

Rust model 中很多 record 都保存 `tokens: Vec<String>`。这对调试有用，但生产解析会多一份字符串内存。

审查意见：

- `include_details=false` 时不要保存 tokens。
- full 模式也应区分 `raw_tokens` debug profile 和 semantic-needed profile。
- 可以用 enum + numeric fields 替代热路径里的 string tokens。

### 3. `semantic/passes.py` 是重复规则堆叠

`build_connectivity_diagnostics()` 是一个长函数，逻辑正确但重复高。它本质上是 ref validation table，不需要手写 300 多行。

审查意见：

- 用 data-driven rule table 做引用校验。
- `SourceRef`、owner id、target id 通过 accessor 函数取。
- 新增 semantic 字段时加一行 rule，不加一段循环。

## 依赖与启动路径

### 1. CLI 顶层 import 太重

证据：

- `cli/main.py` 顶层 import `aurora_translator.sources.aedb`。
- `sources/aedb/parser.py` 顶层 import `pyedb`。
- `pipeline/loaders.py` 顶层 import `parse_aedb`、`parse_odbpp`、`read_auroradb`。

后果：

- 执行 `schema --format semantic`、`odbpp parse` 这种不需要 AEDB 的命令，也会走到 PyEDB import 链。
- 非 AEDB 用户被迫承受 AEDB runtime coupling。

审查意见：

- CLI dispatch 使用 lazy import。
- `pipeline.loaders` 在分支内 import 对应 parser。
- 将 `pyedb` 变成 AEDB extra，至少不要污染 ODB++ 和 AuroraDB-only 路径。

建议骨架：

```python
def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "convert":
        from .convert import main as convert_main
        return convert_main(argv[1:])
    if argv and argv[0] == "schema":
        from .schema import main as schema_main
        return schema_main(argv[1:])
    return _legacy_aedb_main(argv)
```

### 2. `ruff` 是 runtime dependency

`pyproject.toml` 把 `ruff>=0.15.12` 放进 `[project].dependencies`。这是开发工具，不是运行依赖。

审查意见：

- 移到 optional dependency 或 dependency group。
- runtime dependencies 只保留用户执行转换必须需要的包。

## 错误处理与 Diagnostics

AEDB extractor 中有大量 `except Exception: pass` 或吞异常 fallback。考虑到 PyEDB/.NET 对象确实脆弱，这不是完全错误。但现在缺一个统一 `DiagnosticSink`，导致数据缺失很难追踪。

审查意见：

- 每个 silent fallback 至少计数。
- 输出 source payload 和 semantic payload 时带 diagnostic summary。
- 关键字段缺失不应只靠 log，应该进入 model diagnostics。

建议骨架：

```python
@dataclass(slots=True)
class DiagnosticSink:
    counts: Counter[str] = field(default_factory=Counter)
    examples: dict[str, str] = field(default_factory=dict)

    def record(self, code: str, message: str) -> None:
        self.counts[code] += 1
        self.examples.setdefault(code, message)
```

## 测试与验证

当前未发现项目级 `tests/`、`pytest` 配置或 CI 配置。对格式转换器来说，这是硬伤，不是小瑕疵。

已执行轻量验证：

- `python -m compileall -q sources targets pipeline shared semantic cli`
- `python -m ruff check sources targets pipeline shared semantic cli main.py __init__.py`
- `python main.py schema --format semantic --log-file NUL`

结果：

- Python compile 通过。
- Ruff 通过。
- Semantic schema 命令通过。
- `cargo test --manifest-path crates/odbpp_parser/Cargo.toml` 未执行成功，本机缺少 `cargo`。

审查意见：

- 先补 golden regression，不要先写一堆 mock。
- 每个格式至少保留一个脱敏最小样本。
- 必须覆盖这些不变量：
  - source component count == semantic component count
  - semantic net references 不悬空
  - AuroraDB component placement count == semantic component count
  - `PartPad` pin id 可解析
  - polygon arc count 在 source、semantic、AuroraDB 间不丢
  - JSON 中转路径和内存直转路径输出一致
- Rust parser 增加 unit tests：tokenizer、matrix、features、nets、archive root strip。

## 优先级清单

### P0: 给转换链加回归测试

没有测试，架构审查只能停在“看起来合理”。格式转换器的正确性必须靠样本和不变量压住。

状态：已新增 `tests/` 轻量架构护栏、pytest/golden fixture、可选私有样本回归入口和 CI；Rust crate 已能在本机执行 `cargo test`，并包含 tokenizer / matrix / feature / net / archive size-limit 单测。

具体指令：

- [x] 新增 `tests/`。
- [x] 加最小回归入口：当前采用 `unittest` 架构护栏和默认跳过的私有样本回归。
- [x] 补正式 pytest/golden fixture 体系。
- [x] 给 Rust crate 加 tokenizer、matrix、features、nets 等 parser-level unit tests。
- [x] CI 至少跑 compile、`ruff format --check`、`ruff check`、Python tests、`cargo test`。

### P1: 清掉 AuroraDB hidden cache

具体指令：

- [x] 移除 `SemanticPrimitive._auroradb_*`。
- [x] 移除 `PathPrimitiveModel._auroradb_*` 和 `PolygonPrimitiveModel._auroradb_*`。
- [x] 用 typed geometry IR 保留 arc、polygon、void 信息。
- [x] 写回归测试覆盖可序列化 geometry，并用私有样本验证 AEDB minimal/full AuroraDB 输出 SHA-256 等价。

状态：已完成 hidden cache 移除；AEDB minimal/full direct AuroraDB 输出已用私有样本做 14 文件 SHA-256 等价验证。

### P1: 替换 `dict[str, Any]` geometry

具体指令：

- [x] `SemanticPrimitive.geometry` 收敛为 typed hint model。
- [x] `SemanticPad.geometry`、`SemanticVia.geometry` 改成 typed hint model，并保留 `extra` metadata escape hatch。
- [x] footprint、via template、board outline geometry 同步收敛为 typed hint model。
- [x] exporter 改为读取声明字段和兼容 `.get()` metadata，不再依赖 hidden cache。
- [x] 明确当前稳定契约为 typed hint model + `extra` escape hatch；严格 discriminated union 不作为本轮剩余事项，待源格式 metadata 完成进一步收敛后再独立评估。

状态：已完成当前阶段 typed hint model 收敛，覆盖 footprint、via template、pad、via、primitive 和 board outline geometry；为了兼容现有源格式 metadata，保留 `extra` escape hatch，而不是一次性切到严格 discriminated union。

### P1: ODB++ archive streaming

具体指令：

- [x] Rust archive reader 在 summary-only 跳过 feature body。
- [x] 显式 selected step 只读取选中 step 的明细文件。
- [x] 默认 auto-step details 先 summary pass 选 step，再读取选中 step 明细。
- [x] entry size 加限制和 diagnostic。

状态：已完成 summary-only、显式 selected step 和默认 auto-step details 的按需读取。默认 details 采用 summary pass 选 step 后再读取选中 step 明细的二阶段路径；单个 archive entry 默认超过 512 MiB 会跳过并写入 non-fatal diagnostic。

### P2: 拆分 AuroraDB exporter

具体指令：

- [x] 先抽 `BoardExportIndex` 和 export plan 数据结构。
- [x] 把 stackup、geometry、parts、layout、direct builder state、formatting、names 和 writer 边界分出去。
- [x] 每次拆一个 pass，并用私有样本保持输出回归。

状态：已完成。主 exporter 已收敛为顶层编排；`plan.py`、`direct.py`、`layout.py`、`parts.py`、`geometry.py`、`stackup.py`、`formatting.py`、`names.py` 和 `writer.py` 分别承载索引、builder state、layout pass、parts pass、geometry payload、stackup、格式化、命名和文件写出。

### P2: CLI lazy import 和依赖瘦身

具体指令：

- [x] `cli/main.py` 分支内 import。
- [x] `pipeline/loaders.py` 分支内 import source parser。
- [x] `ruff` 移出 runtime dependencies，并保留在 dev dependency group。
- [x] AEDB/PyEDB 已 lazy import；后续如需安装层隔离，可再拆 optional extra。

状态：已完成主入口、loader 和 PyEDB lazy import；`ruff` 已从 runtime dependency 移到 dev dependency group。

### P3: 统一编码与工具链细节

多个文档文件带 UTF-8 BOM。运行时不受影响，但普通 UTF-8 工具链读取会失败或产生脏 diff。

具体指令：

- [x] 批量去 BOM。
- [x] 添加 formatting policy：Ruff formatter 已纳入项目标准。

状态：已将 Ruff formatter 纳入项目标准，配置写入 `pyproject.toml`，日常流程为先执行 `uv run ruff format .`，再执行 `uv run ruff check .`；CI/read-only 检查使用 `uv run ruff format --check .`。项目 Markdown 文档已批量移除 UTF-8 BOM。

## 模块评分

| 模块 | 评分 | 判决 |
| --- | --- | --- |
| `pipeline/` | 🟢 Art | 薄，职责清楚，保留。 |
| `semantic/models.py` | 🟢 Art | 主要 geometry 字段已收敛为 typed hint model，并保留 metadata escape hatch。 |
| `semantic/adapters/odbpp.py` | 🟢 Art | 算法有亮点，typed geometry 已补齐；文件仍偏大，但已由 golden/fixture 与私有样本回归压住，后续拆分可按功能演进增量进行。 |
| `sources/aedb/extractors/primitives.py` | 🟢 Art | target line 私货已移除，source 层保留可序列化几何。 |
| `targets/auroradb/exporter.py` | 🟢 Art | 已降为约 240 行顶层编排；layout、parts、geometry、stackup、direct state 和 helper 已拆分。 |
| `crates/odbpp_parser` | 🟢 Art | Rust 放在正确位置，archive 已支持 selected-step/auto-step 按需读取，并补 entry size diagnostic 与 parser-level 单测。 |
| `cli/` | 🟢 Art | 主入口和 loader 已 lazy import，非 AEDB 命令不再提前加载 PyEDB。 |
| 测试体系 | 🟢 Art | 已补架构护栏、pytest/golden fixture、默认跳过的私有样本回归、Rust parser 单测和 CI。 |

## 最终指令

1. 不要先重写全项目。先建立 golden regression，否则任何“重构”都是赌博。
2. 先切断 AuroraDB hidden cache，再拆 exporter。
3. 把 geometry 变成 typed IR，这是后续所有复杂度下降的唯一正路。
4. ODB++ parser 已改为 summary/selected-step 二阶段读取，并补 entry size 限制与 diagnostic。
5. lazy import PyEDB，`ruff` 从 runtime dependencies 移走。

## 结论

这个项目不是烂项目。它的问题更具体：主轴是对的，数据布局开始腐烂。现在必须停止把 target-format shortcut 往 source 和 semantic 里塞。否则每增加一个格式，复杂度都会按格式数平方增长。
