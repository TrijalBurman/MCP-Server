# Local model profiles

The repository keeps a small default profile and supports a larger optional
profile through **Settings**. Both use local Ollama inference and
`embeddinggemma` for retrieval. Choosing a model in the UI does not download it.

| Profile | Chat model | Context | Scope |
| --- | --- | --- | --- |
| Committed default | `qwen3:4b-instruct-2507-q4_K_M` | `8192` | Lighter starting configuration in source and setup scripts |
| Optional development profile | `qwen3.5:9b-q4_K_M` | `12288` | Checked on the Linux development laptop; requires more memory and disk space |

The optional profile was selected in the development installation's saved
settings. A fresh clone still starts with the committed 4B / 8,192 defaults.
Neither this profile nor its test results establish a universally best model.

## Storage and prerequisites

Complete the edition's normal Python and model setup first. Put the checkout on
the HDD or SSD where you want the managed runtime and models before setup.
Initial downloads need internet and several gigabytes of free space; local
document processing can run offline afterward.

| Managed location, relative to the checkout | Contents |
| --- | --- |
| `.runtime/ollama` | Ollama runtime and libraries |
| `.runtime/models` | Downloaded model weights and manifests |
| `.runtime/tmp` | Launcher-managed temporary files |
| `.local-copilot` | Default database, extracted text, conversations, saved settings and project plans |

Windows uses the same directories with Windows path separators. The development
installation's active runtime, model cache, scratch directory and data directories
were verified inside its HDD-owned workspace. No weights are included in Git.
Source documents stay in their original approved folders. `COPILOT_DATA_DIR` can
place the database elsewhere; all clients sharing that memory must use the same
directory.

**Linux server ownership matters:** the Linux launchers reuse an Ollama server
already listening on `11434`. That server keeps its existing model directory and
server settings. Setting `OLLAMA_MODELS` in a client terminal does not move a
running server's cache. The commands below target `11434` explicitly; use them
after confirming it is the server you intend to use. To keep downloads inside
the checkout, start the managed server when no unrelated server occupies that
port. Stop an unrelated server through its own normal controls if needed.

The Windows launcher instead verifies and manages this checkout's private
server on `11435`, separately from an Ollama tray app on `11434`.

## Install the optional profile on Linux

From the Linux checkout, start the app and leave its terminal open:

```bash
./scripts/start.sh
```

In another terminal, download the optional chat model through that intended
local server. The server owns the destination cache; this command does not
start or reconfigure a server.

```bash
curl --noproxy '*' --fail --show-error \
  http://127.0.0.1:11434/api/pull \
  --header 'Content-Type: application/json' \
  --data '{"model":"qwen3.5:9b-q4_K_M","stream":false}'
```

Wait for a successful completion response before selecting the model. The
normal model setup already installs `embeddinggemma`; keep that embedding model.
The first load from an HDD can be slow, and the download command may remain
quiet while it waits for completion.

## Install the optional profile on Windows 11

These commands are derived from the native Windows launcher paths and port.
They are instructions for Windows users; actual Windows 11 GPU inference with
this profile has not been tested.

From a Windows-branch checkout, run the normal setup once if needed, then start
the app and leave this terminal open:

```powershell
.\scripts\setup.cmd
.\scripts\setup-models.cmd
.\scripts\start.cmd
```

In a second PowerShell terminal, change to the **same checkout**. Target its
launcher-managed server explicitly using the runtime installed by setup:

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11435"
& ".\.runtime\ollama\ollama.exe" pull qwen3.5:9b-q4_K_M
& ".\.runtime\ollama\ollama.exe" list
```

This downloads into the running managed server's `.runtime\models`, rather than
the tray app's cache. Keep the launcher running throughout the download. The
private server sets its own model and temporary directories; changing those
variables in the second terminal does not reconfigure it. The Windows branch's
`docs/windows.md` explains process ownership, port conflicts and stopping the app.

## Save or change the selection

Open the app's **Settings**, choose `qwen3.5:9b-q4_K_M` as the chat model, retain
`embeddinggemma`, set context to **12288**, and save. The selection is stored in
`settings.json` inside the active data directory, so it survives a normal
restart. Environment variables such as `COPILOT_CHAT_MODEL` and
`COPILOT_CONTEXT_SIZE` override saved settings; clear those overrides when you
want the UI selection to control startup.

Changing only the chat model or context does not require reindexing. Changing
the embedding model does require reindexing to rebuild compatible vectors.
Separate data directories, such as a presentation workspace, keep separate saved
selections even when they share one Ollama server.

To return to the lighter profile, select `qwen3:4b-instruct-2507-q4_K_M` and
context **8192**, then save. Keep both models installed if you want to switch
without downloading again. A larger context or model increases memory pressure;
watch Settings readiness and use the smaller profile if the laptop struggles.

## What was checked

On 17 October 2026, the optional profile was checked on **Linux**, with an
**RTX 5050 Laptop GPU with 8 GB VRAM, Ryzen 7 250 and 16 GB RAM**. The runtime
used partial CPU offload; these observations do not describe fully GPU-resident
inference or native Windows GPU performance.

The final small development probe contained eight answerable questions and two
unknown-answer questions. It passed **8/8 literal answer checks** and **2/2 exact
unknown abstention checks**, with no request errors or extractive fallbacks and
a median question time of about **3.27 seconds**. An additional short-summary
literal check did **not** pass. Native tool-use smoke checking also succeeded.

These were reused development questions, unseeded generation and literal checks
with manual inspection, without a semantic scoring judge or held-out validation.
They are **not general answer accuracy, a universal model ranking, or a new
research-paper benchmark**. Cold loading, available VRAM, CPU offload, document
length and concurrent applications can change latency and quality substantially.

At that model-selection snapshot, the source suites passed **135 tests on
Linux** and **172 tests with six platform-specific skips for the Windows
copy tested on Linux**. Those are historical counts. The later routing
repair passed **163 Linux tests** and **200 Windows-copy tests on Linux**,
with six native checks skipped. These local suites
use scripted inference and temporary libraries. They check metadata routing,
evidence packing, citation bounds and safe retry behavior; they do not measure
model intelligence or replace native Windows GPU testing.

## Citation handling

File inventories and exact filename checks use MCP metadata directly. Document
answers receive numbered, complete evidence records within the context budget.
An uncited answer that fails reference checks can be regenerated once when
usable document evidence exists. The retry receives freshly packed original
source material, no tools, and no copy of the uncited answer. It passes through
the same checks before display. Invalid explicit citation numbers fail directly;
failed retries retain the original safe excerpts and source cards.

These checks validate reference syntax and availability, not whether every claim
is supported by its citation. Verify important answers in the source reader.

See the [project deliverables index](../output/README.md),
[validation record](validation.md), and [privacy boundaries](privacy.md).
