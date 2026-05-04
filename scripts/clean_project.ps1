param(
    [switch]$RemoveVenv
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path

function Remove-PathUnderRepo {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $Resolved = (Resolve-Path -LiteralPath $Path).Path
    if (-not $Resolved.StartsWith($RepoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside repository: $Resolved"
    }

    Remove-Item -LiteralPath $Resolved -Recurse -Force
    Write-Host "Removed $Resolved"
}

$StaticTargets = @(
    "logs",
    "out",
    "build",
    "dist",
    "wheels",
    "aurora_translator.egg-info",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov"
)

foreach ($RelativePath in $StaticTargets) {
    Remove-PathUnderRepo (Join-Path $RepoRoot $RelativePath)
}

$PycacheDirs = Get-ChildItem -Path $RepoRoot -Recurse -Directory -Filter "__pycache__" |
    Where-Object { $_.FullName -notlike "$RepoRoot\.venv\*" }
foreach ($Dir in $PycacheDirs) {
    Remove-PathUnderRepo $Dir.FullName
}

$RustTargetDirs = Get-ChildItem -Path (Join-Path $RepoRoot "crates") -Recurse -Directory -Filter "target" -ErrorAction SilentlyContinue
foreach ($Dir in $RustTargetDirs) {
    Remove-PathUnderRepo $Dir.FullName
}

if ($RemoveVenv) {
    Remove-PathUnderRepo (Join-Path $RepoRoot ".venv")
}

Write-Host "Project cleanup complete."
