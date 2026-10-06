# Validation record

The Windows edition targets native Windows 11 x64. Its validation is separate from the earlier Linux edition; a passing Linux test does not prove the Windows filesystem or launcher behavior.

## Native Windows status

As of **6 October 2026**, native Windows CI has been prepared for the following checks, but **no successful run is claimed yet**:

| Check | Intended coverage / current status |
| --- | --- |
| Windows GitHub Actions | Windows Server runner (`windows-latest`), Python 3.12 and 3.13; results pending confirmation. |
| File, API, and MCP tests | Ordinary local paths, paths with spaces, source exclusions, persistence, API behavior, actual SDK stdio handshake/tools/resources, and complete-document pagination; native results pending. |
| Windows launchers | PowerShell 5.1 syntax, CMD wrappers, owned-process start/stop and cleanup using a fake local Ollama runtime; native results pending. |
| Windows 11 laptop / GPU | Not tested. CI does not download the language models or provide the target laptop's GPU. |

The planned launcher checks validate process ownership and cleanup without paid services or model downloads. They are not a Windows GPU benchmark or a live local-model compatibility result. This record should be updated with the actual workflow result once available.

## Earlier Linux baseline

Verified on **2 October 2026**, on a Linux development laptop with an RTX 5050 with 8 GB VRAM, Ryzen 7 250, and 16 GB RAM:

| Check | Recorded evidence |
| --- | --- |
| Automated backend checks | 43 tests passed for the earlier Linux edition, covering storage, indexing, retrieval, API behavior, context handling, and MCP integration. |
| MCP protocol | The official SDK client started the actual stdio server, negotiated its handshake, discovered and called tools, and read resources. Full-document pagination and invalid or stale-source reads were exercised. |
| Local inference | `qwen3:4b-instruct-2507-q4_K_M` and `embeddinggemma` ran locally with GPU acceleration. Chat used an 8,192-token context; embeddings used their own model context. |
| Browser workflows | Connected the supplied example knowledge folder, read complete extracted contents, saved and edited project memory, generated cited chat and a follow-up, summarized a complete document, and saved a project plan. |
| Grounded project planning | A separate live local-model check retrieved evidence over MCP and generated a plan with local file references. |

Only supplied example knowledge was indexed for those checks; personal HDD/SSD folders were not scanned. New installations require explicit source-folder selection in Library.

The recorded checks establish behavior for their stated environment and scope. They do not establish a fixed response-time guarantee, accuracy across every document format, or completeness of a personal library. Model loading, context, document length, driver support, and available GPU memory affect results. Use source citations and the complete extracted-text reader to check generated answers.
