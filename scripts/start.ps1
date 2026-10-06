[CmdletBinding()]
param([ValidateRange(1024, 65535)][int]$Port = 8765)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

try {
    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
        throw "Run scripts\setup.cmd first, then scripts\setup-models.cmd."
    }
    Push-Location -LiteralPath $ProjectRoot
    try {
        & $VenvPython -X utf8 -m copilot.windows_runtime --workspace $ProjectRoot start --port $Port
        $Result = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    exit $Result
} catch {
    [Console]::Error.WriteLine("LocalMind start: " + $_.Exception.Message)
    exit 1
}
