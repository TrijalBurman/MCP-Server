# Validation record

The Windows edition targets native Windows 11 x64. Its validation is separate from the earlier Linux edition; a passing Linux test does not prove the Windows filesystem or launcher behavior.

## Native Windows status

On **6 October 2026**, [GitHub Actions run 37469076958](https://github.com/TrijalBurman/MCP-Server/actions/runs/37469076958) at commit `dcea282` passed on native **Windows Server** runners with **Python 3.12 and 3.13**. Each Python job passed **86 tests**, lint, packaging, and the launcher smoke checks.

| Check | Confirmed coverage / result |
| --- | --- |
| Automated checks | 86 tests passed on each Python version, plus lint and package verification. |
| Paths and filesystem | Checkout `LocalMind Windows Space 東京` exercised spaces and Japanese Unicode; tests covered source policy, persistence, native file/API behavior, and complete-text reads. |
| MCP protocol | Actual official SDK stdio handshake, tool/resource discovery and calls, resource reads, and full-document pagination were exercised on Windows. |
| Windows launchers | PowerShell 5.1 syntax and CMD setup, model-setup, start, and stop smoke checks passed using synthetic knowledge and a fake local Ollama runtime. |
| Windows 11 laptop / GPU | Not tested. These Windows Server jobs did not run the actual language models or the target laptop's GPU. |

These results apply to the stated run and commit. The launcher checks exercised managed-process behavior with a fake server; they are not a GPU benchmark or a live Windows model-inference result. Later changes require their own confirmed checks.

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
