<a id="top"></a>
# odbpp_parser

[中文](#zh) | [English](#en)

<a id="zh"></a>
## 中文

[English](#en) | [返回顶部](#top)

`odbpp_parser` 是 Aurora Translator 使用的 Rust ODB++ 解析核心。

当前 crate 同时提供两条出口：

- `odbpp_parser`：独立 CLI，可输出 ODB++ JSON。
- `aurora_odbpp_native`：通过 PyO3 暴露给 Python 的 native 模块，Python 可直接拿到可校验对象结构，不必经过 CLI stdout JSON。

CLI 用法：

```powershell
cargo run --manifest-path .\crates\odbpp_parser\Cargo.toml -- <odbpp-dir-or-archive> -o .\out\odbpp.json
```

安装 PyO3 native 模块：

```powershell
$env:PYO3_PYTHON = (Resolve-Path .\.venv\Scripts\python.exe).Path
$env:VIRTUAL_ENV = (Resolve-Path .\.venv).Path
$env:PATH = "$env:VIRTUAL_ENV\Scripts;$env:PATH"
uv tool run --from "maturin>=1.8,<2.0" maturin develop --uv --manifest-path .\crates\odbpp_parser\Cargo.toml --release --features python
```

当前范围：

- 容器发现和内存归档读取
- `matrix/matrix` stack rows
- step 发现和 profile line records
- 选定 step 的 layer `features`
- ODB++ symbol library `symbols/<name>/features`
- 选定 step 的 component line records
- 来自 `eda/data` 的 net、package、FID feature 引用和 pin 引用

暂不支持的 UNIX `.Z` 压缩成员会作为 diagnostics 输出。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

`odbpp_parser` is the Rust ODB++ parsing core used by Aurora Translator.

The crate currently exposes two front doors:

- `odbpp_parser`: a standalone CLI that emits ODB++ JSON.
- `aurora_odbpp_native`: a PyO3 native module for Python so the Python side can consume a directly validated object structure instead of going through CLI stdout JSON.

CLI usage:

```powershell
cargo run --manifest-path .\crates\odbpp_parser\Cargo.toml -- <odbpp-dir-or-archive> -o .\out\odbpp.json
```

Install the PyO3 native module:

```powershell
$env:PYO3_PYTHON = (Resolve-Path .\.venv\Scripts\python.exe).Path
$env:VIRTUAL_ENV = (Resolve-Path .\.venv).Path
$env:PATH = "$env:VIRTUAL_ENV\Scripts;$env:PATH"
uv tool run --from "maturin>=1.8,<2.0" maturin develop --uv --manifest-path .\crates\odbpp_parser\Cargo.toml --release --features python
```

Current scope:

- container discovery and in-memory archive reading
- `matrix/matrix` stack rows
- step discovery and profile line records
- selected-step layer `features`
- ODB++ symbol library `symbols/<name>/features`
- selected-step component line records
- nets, packages, FID feature references, and pin references from `eda/data`

Unsupported UNIX `.Z` compressed members are reported as diagnostics.
