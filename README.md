# Local Knowledge Copilot

A local assistant for your laptop's HDD and SSD: search your documents, summarize them, recover earlier conversation context, keep project decisions, and generate project plans. The web app, model inference, search index, conversations, and custom MCP memory server run on your computer.

This project uses local Ollama models and has no paid API dependency. Initial package, runtime, and model downloads need internet; normal use after setup can run offline. Hardware, electricity, and disk space still have a cost.

## Local setup

The supplied scripts target **Linux x86-64** with Python 3.11 or newer. Have `python3-pip`, `curl`, `tar`, and `zstd` available. NVIDIA acceleration needs a working, recent driver; verify the GPU with `nvidia-smi`. Ollama selects supported acceleration automatically; see its [hardware support documentation](https://docs.ollama.com/gpu).

```bash
git clone https://github.com/TrijalBurman/MCP-Server.git
cd MCP-Server
./scripts/setup.sh
./scripts/setup-models.sh
./scripts/start.sh
```

Open **[http://127.0.0.1:8765](http://127.0.0.1:8765)**. The first setup installs Python dependencies into `.venv`. The optional model setup installs the official Ollama runtime into `.runtime/ollama` if Ollama is absent and downloads the two local models. It needs no administrator access. Skip model setup if you already have these models; search, file reading, memory, and projects also work before model installation.

The following defaults were validated on a development laptop with an **RTX 5050 with 8 GB VRAM, Ryzen 7 250, and 16 GB RAM**. That validation describes one machine; memory use and response time depend on your hardware and workload.

| Setting | Default | Purpose |
| --- | --- | --- |
| Chat model | `qwen3:4b-instruct-2507-q4_K_M` | Local summaries, answers, tool selection, project plans |
| Embedding model | `embeddinggemma` | Semantic document search |
| Chat context | 8,192 tokens | Bounds model context; reduce it if available memory is tight |
| Parallel model requests | 1 | Reduces memory pressure |
| Maximum loaded models | 2 | Lets the small chat and embedding models remain resident together |

Ollama lists the selected [Qwen3 4B Instruct model](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M) at approximately 2.5 GB and [EmbeddingGemma](https://ollama.com/library/embeddinggemma) at about 0.62 GB (approximately 621 MB in the installed runtime). Runtime memory also includes context and other overhead. These defaults are a hardware sizing choice, not a measured speed guarantee. Larger models can be selected in Settings after you install them yourself.

## Use your local drive

1. Open **Library**, enter a local folder path, and add it. For example, `~/Documents` or a folder on a mounted drive. Add separate folders from both your HDD and SSD as needed.
2. Index the folder. The app extracts supported text, stores full extracted contents, and creates searchable chunks. It does not alter your source documents.
3. Search the library or ask Chat a question. Source cards point back to the indexed files. Open a document to read or download its complete extracted text, or summarize it.
4. Save and edit explicit notes, preferences, and decisions in **Memory**, or send `/remember <your note>` in Chat. Associate them with a project when useful.
5. Create a workspace in **Projects**, select that project in Chat, and generate a project plan from your local context. Plans retrieve indexed evidence through MCP and append local file references when relevant sources are found.

Try the supplied `examples/knowledge` folder as a small first library. Example questions: “What are the goals of the Lighthouse project?”, “Find the decision about storage”, and “Create a project plan for an offline study assistant using these notes.”

“Access my drive” means reading folders you explicitly add. The app does not silently scan your entire machine. A drive can contain unsupported formats, credentials, operating-system files, and scanned images, so “complete contents” means the complete **extracted text of supported indexed documents**. Retrieval selects useful passages; it does not load an entire hard disk into the model's limited context window.

Supported formats include text, Markdown, common source code, text-based PDFs, and DOCX. Hidden items, symbolic links, known credential files, dependency directories, and the app's own data folder are skipped. Files over 20 MiB and scans over 20,000 files are bounded. **Scanned image PDFs need OCR, which this version does not provide.** See [format and indexing details](docs/architecture.md).

Rescan after adding, modifying, or removing files. Indexing preserves complete extracted text as a snapshot; MCP document reads refuse unavailable or changed sources until you rescan.

## What works without the model

Folder indexing, full extracted document reading, lexical search, saved memory, and projects work without Ollama. Chat clearly labels an extractive fallback that returns matched source passages. Generative summaries, reasoned multi-turn responses, and generated project plans require the local chat model. Semantic retrieval requires the embedding model; search falls back to SQLite full-text search if embeddings are unavailable.

## Persistent data and privacy

The default data directory is `.local-copilot` inside your project checkout. It contains `memory.sqlite3`, saved model settings, and generated project plans under `projects/<id>/PLAN.md`. Original documents remain in their existing folders. The managed runtime lives in `.runtime/ollama`; a server started by the scripts stores models in `.runtime/models`. An existing Ollama server keeps its own configured model location.

The app sends model requests only to a loopback Ollama address. It includes no cloud API, CDN assets, or application telemetry. Setup scripts use `OLLAMA_NO_CLOUD=1`; if you run your own Ollama server, apply that setting to the server process too. A cloud-connected external MCP client can send returned contents elsewhere, so use a local client to keep your workflow local.

The database contains readable document text and conversations; **it is not encrypted**. Use your operating system's disk encryption and file permissions if you need protection from other people with access to the machine. This app serves only on `127.0.0.1` by default and is intended for a trusted local user. See [privacy boundaries](docs/privacy.md).

To place the database on a particular drive, replace the example below with your chosen absolute directory. Use the same directory for the app and all MCP clients:

```bash
COPILOT_DATA_DIR=/absolute/path/to/CopilotData ./scripts/start.sh
```

To back up your memory, stop the app and any MCP clients first, then copy the entire data directory. Source files and model downloads are separate and need their own backup if desired.

## Custom MCP memory server

The assistant uses a real local MCP stdio connection for retrieval. External local MCP clients can use the same memory server and database. It uses the [official Python MCP SDK v1](https://py.sdk.modelcontextprotocol.io/v1/), pinned with `mcp>=1.20,<2`.

Start the standalone server with:

```bash
.venv/bin/python -m copilot.mcp_server
```

It communicates over stdin/stdout, so a blank terminal waiting for a client is expected. It does not start a second web listener. See [MCP tools and connection details](docs/mcp.md) and the [client configuration example](examples/mcp-client.json).

## Configuration

| Environment variable | Default |
| --- | --- |
| `COPILOT_DATA_DIR` | `<project-checkout>/.local-copilot` |
| `COPILOT_OLLAMA_URL` | `http://127.0.0.1:11434` |
| `COPILOT_CHAT_MODEL` | `qwen3:4b-instruct-2507-q4_K_M` |
| `COPILOT_EMBEDDING_MODEL` | `embeddinggemma` |
| `COPILOT_CONTEXT_SIZE` | `8192` |

Settings also stores model names and context size locally. Environment variables override saved values. Only HTTP loopback Ollama endpoints are accepted; cloud model names are blocked. Selecting a model never downloads it from the UI.

The supported context range is 4,096–16,384 tokens, with 8,192 as the default. When the scripts start Ollama, they configure one parallel request and up to two loaded models. The app requests a ten-minute keep-alive for both models so they can stay resident between requests, subject to available memory. An already-running Ollama server retains the settings with which it was started. Loading model weights from a hard disk can make the first request slow; later requests benefit from resident models.

`requirements.lock` records the exact Python dependency versions verified on the development machine. The setup script resolves compatible versions from `pyproject.toml` for the active Python version.

## Optional: run independently on Linux

On Linux with a systemd user session, you can start a transient service from the project checkout directory:

```bash
systemd-run --user --unit=localmind-copilot --collect \
  --working-directory="$(pwd)" "$(pwd)/scripts/start.sh"
```

This service runs independently of the terminal and is not enabled at login. Check or stop it with:

```bash
systemctl --user status localmind-copilot
systemctl --user stop localmind-copilot
```

After stopping it, run the same `systemd-run` command to start it again, or run `./scripts/start.sh` normally. A foreground session ends when you press Ctrl+C.

## Verification and troubleshooting

```bash
.venv/bin/python -m pytest
```

Tests use temporary data directories and require no model downloads. MCP coverage starts the actual stdio subprocess, negotiates the protocol, calls tools, reads resources, and fetches a full document over multiple pages. The [validation record](docs/validation.md) describes checks completed on the development laptop. New installations begin without an indexed personal library; choose your folders in Library.

If models are unavailable, inspect the Settings readiness panel. For the managed runtime, inspect `.runtime/ollama.log`; run model setup again to resume a failed download. If GPU memory is tight, close other GPU applications or reduce context to 4,096 in Settings. If a PDF shows no useful text, it may contain scanned images. If indexing reports skipped files or errors, inspect those results and choose a smaller accessible folder.

The implementation and tradeoffs are described in [architecture](docs/architecture.md), the [problem statement](docs/problem-statement.md), and [privacy](docs/privacy.md).
