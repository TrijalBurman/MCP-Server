# Local Knowledge Copilot — Windows edition

A native Windows assistant for your laptop's HDD and SSD. Search local documents, summarize complete extracted contents, recover earlier conversations, keep project memories, and generate plans with local references. The web app, Ollama inference, SQLite database, and custom MCP memory server run on your computer.

This branch targets **Windows 11 x64**. The [Linux edition remains on `main`](https://github.com/TrijalBurman/MCP-Server/tree/main). No WSL, Docker, administrator account, paid API, or hosted database is required for this edition. Initial dependency, runtime, and model downloads need internet; normal processing can run offline afterward. Storage and electricity still have a cost.

## Start on Windows

Install **64-bit Python 3.12 or newer**; Python **3.13** is recommended. Use a per-user installation. Have Git available and use Windows PowerShell **5.1** or PowerShell **7**. A recent NVIDIA driver is needed for RTX acceleration. See the official [Python Windows guide](https://docs.python.org/3.13/using/windows.html) and [Ollama Windows requirements](https://docs.ollama.com/windows).

Open PowerShell and run:

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\Projects\Local Knowledge" | Out-Null
Set-Location -LiteralPath "$env:USERPROFILE\Projects\Local Knowledge"
git clone --branch windows --single-branch https://github.com/TrijalBurman/MCP-Server.git MCP-Server
Set-Location -LiteralPath .\MCP-Server
.\scripts\setup.cmd
.\scripts\setup-models.cmd
.\scripts\start.cmd
```

Open **[http://127.0.0.1:8765](http://127.0.0.1:8765)**. `setup.cmd` creates `.venv`; `setup-models.cmd` downloads the official standalone Ollama Windows runtime into `.runtime\ollama` and stores models in `.runtime\models`. The memory database and downloaded models are ignored by Git. Leave the start window open; **Ctrl+C** stops the app and the private model server it started. You can also run `scripts\stop.cmd` from another terminal.

The CMD wrappers invoke their matching PowerShell scripts with an execution policy for that invocation only. They do not change your user or machine execution policy. You can use `setup.ps1`, `setup-models.ps1`, `start.ps1`, and `stop.ps1` directly where script execution is permitted. See [Windows setup and troubleshooting](docs/windows.md) for details.

## Models and local services

| Setting | Default |
| --- | --- |
| Chat model | `qwen3:4b-instruct-2507-q4_K_M` |
| Embedding model | `embeddinggemma` |
| Chat context | 8,192 tokens; supported range 4,096–16,384 |
| App | `http://127.0.0.1:8765` |
| Managed Ollama | `http://127.0.0.1:11435` |
| Parallel model requests / maximum loaded models | 1 / 2 |

The private server uses **11435**, keeping it separate from an existing Ollama tray app on 11434. It sets `OLLAMA_NO_CLOUD=1` and keeps its own model directory. The launchers manage only processes belonging to this checkout.

The selected [Qwen3 Instruct model](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M) is approximately 2.5 GB and [EmbeddingGemma](https://ollama.com/library/embeddinggemma) is about 0.62 GB. Allow additional disk space for Ollama, its GPU libraries, downloads, and your index. The same model configuration was validated on a **Linux** laptop with an RTX 5050 with 8 GB VRAM, Ryzen 7 250, and 16 GB RAM. Native Windows testing is tracked in the [validation record](docs/validation.md); Windows GPU performance has not been established.

Search, file reading, explicit memory, and project workspaces work without a downloaded model. Generative summaries, conversational answers, and project plans require the local chat model. Semantic search uses the embedding model, with a lexical fallback when it is unavailable. The app requests ten-minute model keep-alives, subject to available memory.

The managed launcher requires the Ollama runtime binary. To use the app alone after Python setup, without installing Ollama or models, run:

```powershell
& ".\.venv\Scripts\python.exe" -X utf8 -m copilot
```

That foreground session uses lexical/extractive fallback until a local model server is available. Press Ctrl+C to stop it.

## Connect your local files

1. Open **Library** and add a folder such as `D:\Knowledge`, `C:\Users\Your Name\Documents\Study Notes`, or the checkout's `examples\knowledge` folder.
2. Index the folder. The app extracts supported contents without editing your originals.
3. Search or ask Chat a question. Open source cards to verify answers, read complete extracted text, download it, or request a full-document summary.
4. Save and edit notes in **Memory**, or send `/remember <your note>` in Chat. Link memories and conversations to a project when useful.
5. Create a project and generate a plan. Plans retrieve indexed evidence through actual MCP tool calls and append local file references when sources are found.

Folders on fixed or removable local drives are supported. Adding folders is explicit: the app does not silently scan an entire drive. Whole drive roots, Windows system directories, network/UNC paths, mapped network drives, symbolic links, junctions, and other reparse points are excluded. OneDrive placeholders and reparse-backed folders need an ordinary local copy in a folder such as `D:\Knowledge`.

Supported formats include text, Markdown, common source code, text-based PDFs, and DOCX. Hidden items, known credentials, dependencies, and the app's data folder are skipped. Limits include 20 MiB per source file and 20,000 supported files per scan. **Scanned image PDFs need OCR, which this edition does not provide.** Complete contents means complete extracted text of supported indexed files, not original images, formatting, or every binary file on disk.

Rescan after changing or deleting files. Readers reject changed or missing sources until reindexing refreshes the snapshot. Retrieval selects relevant passages; full-document summaries process all extracted sections in bounded passes. The completed response contains section traces; live section progress is not streamed.

## Persistent storage and privacy

The default database is `<checkout>\.local-copilot\memory.sqlite3`. The same directory contains saved settings and `projects\<id>\PLAN.md`. Original documents remain in their existing folders. All UI assets are bundled locally; there are no application telemetry, CDN, or cloud API requests. A hosted external MCP client can transmit returned contents, so use a local client to keep that workflow local too.

The database contains readable extracted text and conversations and **is not encrypted**. Windows file permissions and disk encryption control access outside the app. Stop the app and MCP clients before backing up the entire data directory, including any SQLite WAL files. See [privacy boundaries](docs/privacy.md).

To keep memory on another local drive, set a process environment variable before starting and use the same path in external MCP clients:

```powershell
$env:COPILOT_DATA_DIR = "D:\Copilot Data"
.\scripts\start.cmd
```

Model settings are saved locally; environment variables override them. Windows defaults are `COPILOT_OLLAMA_URL=http://127.0.0.1:11435`, `COPILOT_CHAT_MODEL=qwen3:4b-instruct-2507-q4_K_M`, `COPILOT_EMBEDDING_MODEL=embeddinggemma`, and `COPILOT_CONTEXT_SIZE=8192`. Only loopback Ollama endpoints are accepted, and remote-model metadata is rejected. Selecting a model in the UI does not download it.

## Custom MCP memory server

The assistant uses the [official Python MCP SDK v1](https://py.sdk.modelcontextprotocol.io/v1/), pinned with `mcp>=1.20,<2`. A local stdio server shares the app's SQLite memory. External clients can search documents and conversations, read complete contents through pagination, and explicitly manage project memories.

```powershell
& ".\.venv\Scripts\python.exe" -X utf8 -m copilot.mcp_server
```

The server waits for protocol input; stdout is reserved for MCP messages. The [Windows client example](examples/mcp-client.json) uses concrete escaped paths with spaces. Replace its account/check-out paths with your own and keep `COPILOT_DATA_DIR` identical to the app. See [MCP tools and resources](docs/mcp.md).

## Checks and help

```powershell
& ".\.venv\Scripts\python.exe" -X utf8 -m pytest
```

The tests use temporary libraries and require no model downloads. A [confirmed native Windows Server CI run](https://github.com/TrijalBurman/MCP-Server/actions/runs/37469076958) at commit `dcea282` passed **86 tests on each of Python 3.12 and 3.13**, lint, packaging, and PowerShell 5.1/CMD launcher checks. The checkout path included spaces and Japanese Unicode. Launcher checks used synthetic data and a fake Ollama server; Windows 11 laptop GPU inference with the actual models remains untested. See the [validation record](docs/validation.md) for scope. Logs are under `.runtime\logs\app.log` and `.runtime\logs\ollama.log`.

For setup errors, source exclusions, port conflicts, and restart instructions, see [Windows help](docs/windows.md). The [architecture](docs/architecture.md), [problem statement](docs/problem-statement.md), and [validation record](docs/validation.md) describe scope and evidence.
