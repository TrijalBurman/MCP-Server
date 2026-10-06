# Native Windows setup

Use the repository's `windows` branch on **Windows 11 x64**, with **Python 3.12+** (3.13 recommended) and **PowerShell 5.1 or 7**. The app uses native Windows processes and filesystem APIs. It does not require WSL, Docker, a paid API, or administrator access for its setup scripts.

## Installation

Install Python for your user account and keep its launcher or executable available. Git is needed for cloning; alternatively, download the `windows` branch ZIP from GitHub and extract it into a writable local folder. Choose a modest path on a local drive, such as `C:\Users\Your Name\Projects\Local Knowledge\MCP-Server`. Paths with spaces are supported; quote them in terminal commands.

From PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\Projects\Local Knowledge" | Out-Null
Set-Location -LiteralPath "$env:USERPROFILE\Projects\Local Knowledge"
git clone --branch windows --single-branch https://github.com/TrijalBurman/MCP-Server.git MCP-Server
Set-Location -LiteralPath .\MCP-Server
.\scripts\setup.cmd
.\scripts\setup-models.cmd
.\scripts\start.cmd
```

`setup.cmd` creates `.venv` and installs the Python project and test dependencies. `setup-models.cmd` downloads and extracts the official standalone Ollama Windows ZIP, starts its private server if needed, and pulls `qwen3:4b-instruct-2507-q4_K_M` and `embeddinggemma`. It cleans up a server it started for model setup; a verified workspace server already in use can remain running.

The official standalone runtime includes the CLI and NVIDIA GPU dependencies. See [Ollama's Windows documentation](https://docs.ollama.com/windows) for its supported drivers and hardware requirements. GPU acceleration depends on a suitable driver and available memory; Windows laptop GPU behavior has not yet been validated for this edition.

Initial setup requires internet and space for the runtime, GPU libraries, models, download archives, and index. Subsequent document processing and local inference can run offline. Re-running setup does not index your personal folders.

## Script execution policy

The CMD wrappers call the matching `.ps1` scripts with `-NoProfile -ExecutionPolicy Bypass -File`. This applies to that PowerShell invocation and does **not** persist a user or machine policy change. It is not necessary to run `Set-ExecutionPolicy` permanently. [Microsoft documents process-scoped policies](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies).

If scripts are already permitted in your terminal, you can call the PowerShell versions directly:

```powershell
.\scripts\setup.ps1
.\scripts\setup-models.ps1
.\scripts\start.ps1
```

An organization's Group Policy may still control execution. The launchers do not change those managed policies. No virtual-environment activation is required; all commands use `.venv\Scripts\python.exe` explicitly.

## Start, stop, and ports

`start.cmd` runs the app in the foreground at **http://127.0.0.1:8765** and manages a private Ollama server at **http://127.0.0.1:11435**. Leave the terminal open. Press **Ctrl+C** to stop the app and any private runtime it started, or use another terminal:

```powershell
Set-Location -LiteralPath "C:\Users\Your Name\Projects\Local Knowledge\MCP-Server"
.\scripts\stop.cmd
```

Restart with `start.cmd`. To use another app port:

```powershell
.\scripts\start.cmd -Port 8766
```

The launchers use `.runtime\windows-processes.json` to track process identity and verify the checkout, executable, and creation time before stopping anything. They do not stop an unrelated process or an Ollama tray instance on **11434**. The model server is loopback-only, uses `.runtime\models`, and sets `OLLAMA_NO_CLOUD=1`. It is not installed as a Windows service or configured to start at login.

The managed launcher requires the runtime binary but accepts models that are not downloaded yet. For app-only indexing, reading, lexical search, and explicit memory after `setup.cmd`, skip runtime/model setup and run:

```powershell
& ".\.venv\Scripts\python.exe" -X utf8 -m copilot
```

This starts only the local app. It uses extractive fallback when Ollama is unavailable and stops with Ctrl+C. The Python launcher helper, `python -m copilot.windows_runtime`, uses `--port` for its own `start` command; the Windows script wrapper uses `-Port`.

## Add HDD or SSD knowledge

Add a source folder in **Library**, for example `D:\Knowledge` or `C:\Users\Your Name\Documents\Study Notes`. Add individual folders from different drives as needed, then index them. The sample library is `<checkout>\examples\knowledge`.

Only ordinary folders on fixed/removable local drives are accepted. Whole drive roots such as `C:\`, Windows/Program Files/ProgramData and other system directories, UNC/device paths, mapped network drives, symbolic links, junctions, and reparse points are excluded. A visible Explorer file may be a OneDrive placeholder or have a reparse-backed ancestor; copy its downloaded contents into an ordinary local folder if you want to index it.

Files remain in their original locations. The app stores extracted snapshots and searchable chunks. Rescan after source changes; complete-text reads reject stale or missing sources. Scanned PDFs require an external OCR workflow, which is not included.

## Data, models, and MCP

| Location | Contents |
| --- | --- |
| `.venv` | Project Python environment |
| `.local-copilot` | SQLite memory, extracted text, saved settings, conversations, project plans |
| `.runtime\ollama` | Managed official runtime and libraries |
| `.runtime\models` | Downloaded model weights |
| `.runtime\logs\app.log` / `ollama.log` | Local startup and runtime logs |

To put memory elsewhere for this terminal session:

```powershell
$env:COPILOT_DATA_DIR = "D:\Copilot Data"
.\scripts\start.cmd
```

External MCP clients must use the same data directory, an absolute executable path ending in `.venv\Scripts\python.exe`, and the Windows Ollama URL `http://127.0.0.1:11435`. JSON needs doubled backslashes; use [the sample configuration](../examples/mcp-client.json) and replace its account/check-out paths. Environment variables such as `%USERPROFILE%` are not guaranteed to expand in a client's JSON configuration.

## Troubleshooting and validation

- **Python not found:** install supported 64-bit Python for your account, reopen the terminal, and rerun `setup.cmd`. See the [Python Windows guide](https://docs.python.org/3.13/using/windows.html).
- **Download failure:** check connectivity and free disk space, then rerun `setup-models.cmd`. The managed files stay inside the checkout.
- **Port occupied:** inspect the error and use another app port if appropriate. Stop this checkout with `stop.cmd`; the scripts do not kill another application's process to reclaim a port.
- **Slow first answer:** loading weights from disk takes time. Close other GPU-heavy programs or reduce chat context to 4,096 in Settings if memory is tight.
- **Folder rejected:** choose its ordinary local path, outside system directories, without a junction/reparse ancestor. Network drives are outside this edition's local-drive scope.
- **Missing PDF text:** image-only scans need OCR before indexing.

The [validation record](validation.md) separates the existing Linux baseline from native Windows checks. Windows GitHub Actions are intended to cover Python 3.12/3.13, filesystem/API/MCP behavior, PowerShell 5.1 syntax, and launcher ownership/cleanup with a fake local runtime. They do not exercise a Windows 11 laptop GPU or downloaded language models. Until a run is confirmed, native Windows validation remains pending.
