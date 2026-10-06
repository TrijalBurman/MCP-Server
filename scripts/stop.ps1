[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

try {
    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
        throw "The local Python environment is missing. No processes were stopped. Run scripts\setup.cmd to restore it."
    }
    Push-Location -LiteralPath $ProjectRoot
    try {
        & $VenvPython -X utf8 -m copilot.windows_runtime --workspace $ProjectRoot stop
        $Result = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    exit $Result
} catch {
    [Console]::Error.WriteLine("LocalMind stop: " + $_.Exception.Message)
    exit 1
}
