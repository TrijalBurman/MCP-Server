[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RuntimeDirectory = Join-Path $ProjectRoot ".runtime"
$RuntimeExecutable = Join-Path $RuntimeDirectory "ollama\ollama.exe"
$RuntimeArchive = Join-Path $RuntimeDirectory "ollama-windows-amd64.zip"
$PartialArchive = $RuntimeArchive + ".download"

try {
    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
        throw "Run scripts\setup.cmd first to create the local Python environment."
    }
    & $VenvPython -X utf8 -c "import sys,platform,struct; sys.exit(0 if sys.platform == 'win32' and platform.machine().lower() in ('amd64','x86_64') and struct.calcsize('P') == 8 and sys.version_info >= (3,12) else 1)"
    if ($LASTEXITCODE -ne 0) { throw "The standalone runtime requires native x64 Windows and Python 3.12+." }
    Push-Location -LiteralPath $ProjectRoot
    try {
        if (-not (Test-Path -LiteralPath $RuntimeExecutable -PathType Leaf)) {
            [void](New-Item -ItemType Directory -Path $RuntimeDirectory -Force)
            if (-not (Test-Path -LiteralPath $RuntimeArchive -PathType Leaf)) {
                Write-Host "Downloading the official standalone Ollama runtime into this project."
                Write-Host "This needs several GB of free disk space. No administrator rights or PATH changes are needed."
                $PreviousProtocol = [Net.ServicePointManager]::SecurityProtocol
                try {
                    [Net.ServicePointManager]::SecurityProtocol = $PreviousProtocol -bor [Net.SecurityProtocolType]::Tls12
                    Invoke-WebRequest -UseBasicParsing -Uri "https://ollama.com/download/ollama-windows-amd64.zip" -OutFile $PartialArchive
                    Move-Item -LiteralPath $PartialArchive -Destination $RuntimeArchive -Force
                } finally {
                    [Net.ServicePointManager]::SecurityProtocol = $PreviousProtocol
                }
            }
            & $VenvPython -X utf8 -m copilot.windows_runtime --workspace $ProjectRoot install-runtime $RuntimeArchive
            if ($LASTEXITCODE -ne 0) { throw "Could not install the runtime. Check the message above; the ZIP was kept for retry." }
            Remove-Item -LiteralPath $RuntimeArchive -Force
        }
        & $VenvPython -X utf8 -m copilot.windows_runtime --workspace $ProjectRoot setup-models
        if ($LASTEXITCODE -ne 0) { throw "Model setup did not finish. Rerun setup-models.cmd to resume model downloads." }
        Write-Host "Ready. Run scripts\start.cmd to open your private local workspace."
    } finally {
        Pop-Location
    }
    exit 0
} catch {
    [Console]::Error.WriteLine("LocalMind model setup: " + $_.Exception.Message)
    exit 1
}
