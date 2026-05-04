param(
    [switch]$RefreshLock,
    [switch]$SkipPythonSync,
    [switch]$SkipRustBuild,
    [switch]$RunSmokeCheck
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $RepoRoot

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Warn {
    param([string]$Message)
    Write-Host "WARN: $Message" -ForegroundColor Yellow
}

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

Write-Step "Configuring Aurora Translator environment"
Write-Host "Repository: $RepoRoot"

if (-not (Test-Command "uv")) {
    Write-Step "uv was not found; installing uv for the current user"
    powershell -ExecutionPolicy ByPass -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex"
    $UvBin = Join-Path $env:USERPROFILE ".local\bin"
    if (Test-Path $UvBin) {
        $env:Path = "$UvBin;$env:Path"
    }
    if (-not (Test-Command "uv")) {
        throw "uv installation finished, but uv is still not available on PATH. Restart PowerShell and rerun this script."
    }
}

if (-not $SkipPythonSync) {
    $PythonVersionFile = Join-Path $RepoRoot ".python-version"
    if (Test-Path $PythonVersionFile) {
        $PythonVersion = (Get-Content -Path $PythonVersionFile -Encoding UTF8 | Select-Object -First 1).Trim()
        if ($PythonVersion) {
            Write-Step "Ensuring Python $PythonVersion is available through uv"
            uv python install $PythonVersion
        }
    }

    if ($RefreshLock) {
        Write-Step "Refreshing uv.lock"
        uv lock
    }

    Write-Step "Syncing Python dependencies from uv.lock"
    uv sync --locked
}

if (-not $SkipRustBuild) {
    $CargoToml = Join-Path $RepoRoot "crates\odbpp_parser\Cargo.toml"
    $VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    $VenvRoot = Join-Path $RepoRoot ".venv"
    $VenvScripts = Join-Path $VenvRoot "Scripts"
    if (Test-Path $CargoToml) {
        if (Test-Command "cargo") {
            if (-not (Test-Path $VenvPython)) {
                throw "Expected virtual environment Python at $VenvPython. Run the Python sync step first."
            }

            $env:PYO3_PYTHON = (Resolve-Path $VenvPython).Path
            $env:VIRTUAL_ENV = (Resolve-Path $VenvRoot).Path
            $env:PATH = "$VenvScripts;$env:PATH"

            Write-Step "Building Rust ODB++ parser CLI"
            cargo build --release --manifest-path $CargoToml

            Write-Step "Installing Rust ODB++ native module"
            uv tool run --from "maturin>=1.8,<2.0" maturin develop --uv --manifest-path $CargoToml --release --features python
        }
        else {
            Write-Warn "cargo was not found. ODB++ native/CLI parsing will work after Rust is installed and these commands are run:"
            Write-Host "      $env:PYO3_PYTHON = (Resolve-Path .\.venv\Scripts\python.exe).Path"
            Write-Host "      $env:VIRTUAL_ENV = (Resolve-Path .\.venv).Path"
            Write-Host "      $env:PATH = ""$env:VIRTUAL_ENV\Scripts;$env:PATH"""
            Write-Host "      cargo build --release --manifest-path .\crates\odbpp_parser\Cargo.toml"
            Write-Host "      uv tool run --from ""maturin>=1.8,<2.0"" maturin develop --uv --manifest-path .\crates\odbpp_parser\Cargo.toml --release --features python"
        }
    }
}

if ($RunSmokeCheck) {
    Write-Step "Running Python compile smoke check"
    uv run python -m compileall sources targets pipeline shared semantic cli
    Write-Step "Checking dependency lock"
    uv lock --check
    Write-Step "Checking Rust ODB++ native module import"
    uv run python -c "import aurora_odbpp_native; print(aurora_odbpp_native.__version__)"
    Write-Step "Checking semantic-centered CLI entrypoints"
    uv run python .\main.py convert --help
    uv run python .\main.py inspect --help
    uv run python .\main.py dump --help
    uv run python .\main.py schema --help
}

Write-Step "Environment setup complete"
Write-Host ""
Write-Host "Common commands:"
Write-Host "  uv run python .\main.py --help"
Write-Host "  uv run python .\main.py convert --help"
Write-Host "  uv run python .\main.py inspect --help"
Write-Host "  uv run python .\main.py dump --help"
Write-Host "  uv run python .\main.py schema --help"
Write-Host "  uv run python .\main.py odbpp --help"
Write-Host "  uv run python .\main.py semantic --help"
Write-Host "  .\scripts\clean_project.ps1"
