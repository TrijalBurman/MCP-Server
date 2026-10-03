# Validation record

Verified during development on **2 October 2026**, on a Linux development laptop with an RTX 5050 with 8 GB VRAM, Ryzen 7 250, and 16 GB RAM. This is a record of checks on that machine, not a claim that every operating system or hardware configuration has been tested.

| Check | Verified evidence |
| --- | --- |
| Automated backend checks | **43 tests passed**, covering local storage, indexing, retrieval, API behavior, agent context handling, and MCP integration. |
| MCP protocol | The official SDK client started the actual stdio server, negotiated its handshake, discovered tools and resources, called tools, and read resource contents. Full-document pagination and invalid or stale-source reads were exercised. |
| Local inference | `qwen3:4b-instruct-2507-q4_K_M` and `embeddinggemma` were verified running locally with GPU acceleration. Chat used the default **8,192-token context**; the embedding model uses its own model context. |
| Browser library workflow | Connected the supplied example knowledge folder, indexed its documents, and read complete extracted contents. |
| Browser memory workflow | Saved a project memory and edited it through the app. |
| Browser assistant workflow | Generated a cited chat response and follow-up, a full-document summary, and a saved project plan through the app. |
| Grounded project planning | A live local-model integration check retrieved document evidence over MCP and generated a plan with file references. |

**Only the supplied example knowledge was indexed for these checks; personal HDD/SSD document folders were not scanned.** On your installation, add the desired folders in Library and index them to make their supported contents available to the assistant. The example folder demonstrates the workflow without silently scanning personal files.

These checks establish functional behavior on the current laptop configuration. They do not establish a fixed response-time guarantee, exhaustive accuracy across document types, or completeness of a future personal library. Model loading, context size, document length, and available GPU memory affect response time. Source citations and the complete extracted-text reader remain available for checking generated answers.
