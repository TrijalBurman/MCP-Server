[CmdletBinding()]
param([string]$PythonExecutable = "")

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Test-PythonExecutable {
    param([string]$Executable)
    try {
        # JSON keeps native output ASCII even when the Python install path contains Unicode.
        $Result = & $Executable -X utf8 -c "import sys,struct,json; print(json.dumps(sys.executable,ensure_ascii=True)); sys.exit(0 if sys.version_info >= (3,12) and struct.calcsize('P') == 8 else 1)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $Result) {
            return [string](([string]($Result | Select-Object -Last 1)) | ConvertFrom-Json)
        }
    } catch { }
    return ""
}

try {
    if ($PythonExecutable) {
        $SelectedPython = Test-PythonExecutable $PythonExecutable
        if (-not $SelectedPython) {
            throw "The selected executable must be 64-bit Python 3.12 or newer (3.13 recommended)."
        }
    } else {
        $SelectedPython = ""
        $Launcher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($Launcher) {
            foreach ($Version in @("-3.13", "-3.12", "-3")) {
                try {
                    $Candidate = & $Launcher.Source $Version -c "import sys,json; print(json.dumps(sys.executable,ensure_ascii=True))" 2>$null
                    if ($LASTEXITCODE -eq 0 -and $Candidate) {
                        $CandidatePath = [string](([string]($Candidate | Select-Object -Last 1)) | ConvertFrom-Json)
                        $SelectedPython = Test-PythonExecutable $CandidatePath
                        if ($SelectedPython) { break }
                    }
                } catch { }
            }
        }
        if (-not $SelectedPython) {
            $Command = Get-Command python.exe -ErrorAction SilentlyContinue
            if ($Command) { $SelectedPython = Test-PythonExecutable $Command.Source }
        }
        if (-not $SelectedPython) {
            throw "Install 64-bit Python 3.13 from python.org, then rerun setup.cmd. Python 3.12+ is supported."
        }
    }

    Push-Location -LiteralPath $ProjectRoot
    try {
        Write-Host "Setting up LocalMind with $SelectedPython"
        $VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
            & $SelectedPython -X utf8 -m venv (Join-Path $ProjectRoot ".venv")
            if ($LASTEXITCODE -ne 0) { throw "Could not create the local Python environment." }
        }
        if (-not (Test-PythonExecutable $VenvPython)) {
            throw "The existing .venv uses an unsupported Python. Remove that virtual environment and rerun setup.cmd."
        }
        & $VenvPython -X utf8 -m pip install --upgrade "pip>=26,<27"
        if ($LASTEXITCODE -ne 0) { throw "Could not install pip. Check your internet connection and retry." }
        & $VenvPython -X utf8 -m pip install -e ".[dev]"
        if ($LASTEXITCODE -ne 0) { throw "Could not install LocalMind's dependencies. Check the errors above." }
        Write-Host "LocalMind is ready. Run scripts\setup-models.cmd once, then scripts\start.cmd."
    } finally {
        Pop-Location
    }
    exit 0
} catch {
    [Console]::Error.WriteLine("LocalMind setup: " + $_.Exception.Message)
    exit 1
}
