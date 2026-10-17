# LocalMind local-model upgrade verification

Completed 17 October 2026 on the user's RTX 5050 Laptop GPU (8 GB VRAM), Ryzen 7 250 and 16 GB RAM laptop.

LocalMind is running with **Qwen3.5 9B, Q4_K_M**, a **12,288 context setting** and thinking disabled. The installed model comes from the [official Ollama model entry](https://ollama.com/library/qwen3.5:9b-q4_K_M). Its approximately 6.6 GB download is stored on the HDD. The older Qwen3 4B model remains available in Settings.

## What was corrected

File inventory and exact filename questions now use indexed metadata directly, rather than asking a language model to infer an exhaustive list from search snippets. The live main workspace correctly returned seven indexed files, one exact `api.md` match, and zero matches for a deliberately absent filename.

Document evidence is packaged as complete numbered records within the actual request budget. The tested larger context setting retained a coordinator fact that the earlier smaller excerpts omitted. The prompt explicitly maps a record's source number to its citation.

An answer missing required document citations is regenerated at most once, with refreshed complete evidence and no tools or earlier generated draft. The existing citation checks inspect the retry. Invalid explicit citation numbers and unsuccessful retries return the original exact excerpts. Successful retries return source cards matching the evidence actually sent for that retry.

Both workspaces share one loopback-only model service, while keeping their separate databases. EmbeddingGemma is retained, allowing the existing document vectors to remain usable without rebuilding the index.

## Download and storage

- Model files: `/run/media/trijal/HDD/SpecialisationBySol/.runtime/models`
- Temporary runtime files: `/run/media/trijal/HDD/SpecialisationBySol/.runtime/tmp`
- Download and probe records: `/run/media/trijal/HDD/SpecialisationBySol/.runtime/model-upgrade`
- Verified physical mount: `/run/media/trijal/HDD`, device `/dev/sda1`.
- Official model digest: `56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`.

The main weight blob was checked against the official manifest's SHA-256 digest. Ollama subsequently verified the completed download and registered the manifest successfully. Runtime environment and filesystem-device checks confirmed the model cache and scratch directories are on the HDD. The private test service was stopped; both apps now use port 11434 with cloud inference disabled.

## Small development probe

A fixed synthetic corpus contained five documents, eight answerable questions, two unknown questions, a short summary and a native tool-selection smoke test. Requests went through the real Agent, MCP server, retrieval and Ollama client; payloads and responses were recorded locally.

| Configuration | Generated expected-fact checks | Exact unknown abstentions | Citation fallbacks | Median question time |
|---|---:|---:|---:|---:|
| Earlier Qwen3 4B, 8K context | 7/8 | 2/2 | 0 | 1.114 s |
| Qwen3.5 9B, same earlier 8K protocol | 5/8 | 1/2 | 2 | 2.176 s |
| Selected 9B, 12K context and bounded retry | 8/8 | 2/2 | 0 | 3.268 s |

Manual review found the requested facts and supporting references in all eight final answerable responses. Both unknowns returned exactly “Not in the documents.” The final native tool-selection smoke passed. Three extra model calls were used by bounded citation retries across the ten questions.

The earlier 9B citation fallbacks contained the correct facts without references; one longer valid abstention failed the strict exact-phrase check. Both models' summaries retained the requested storage profile, backup interval and review date semantically, but changed wording, causing literal summary checks to fail. The final summary also added a generic data-integrity rationale absent from the source.

**These are development observations, not general accuracy results.** Generation was unseeded and diagnostics were postselected. The selected configuration changes context and integration logic as well as the model, so its result cannot be attributed solely to model size. Citation checks establish reference format and bounds; they do not prove every generated claim is supported. No new paper accuracy percentage is derived from this probe.

## Hardware and live checks

The 9B model and embedding model remained resident together with partial CPU offload. The 9B runtime reported approximately 5.28 GB of model VRAM allocation at the selected context setting. This is a shared GPU/CPU configuration, rather than a claim of full GPU offload.

The first request after restarting the shared service took 56.2 seconds, including model loading. Filesystem cache was uncontrolled, so this is not a controlled cold-disk benchmark. A subsequent embedding reload took about 12 seconds; the next warm live answer took about 4.7 seconds. Both models were resident after those requests.

Live demo answers correctly identified SQLite storage, original files staying in their existing folders, the scanned-PDF limitation and future OCR option, and an unspecified advertising budget as unknown. Verification conversations were removed afterward. Document, chunk, memory, project, root and session counts matched their earlier values in both workspaces.

## Regression verification

- Linux: **135 passed**.
- Windows copy tested on Linux: **172 passed, 6 native Windows checks skipped**.
- All 30 answer-grounding cases passed, including retry limits, failed retries, exact source-card matching, and both synthesis paths.
- Both copies passed lint and whitespace checks; launcher syntax and JavaScript syntax checks passed.

Native Windows execution was not tested on this Linux host. The existing Starlette/httpx deprecation warning did not cause failures.

The final [regression logs and source hashes](regressions/README.md) are included.

## Use the selected model

Open [LocalMind](http://127.0.0.1:8765) or the [presentation workspace](http://127.0.0.1:8766) and refresh the page. The saved selection is Qwen3.5 9B with context 12288. Choose the older installed 4B model in Settings if desired.

The normal and presentation launchers restore the saved model selection on later starts. The first model load from the HDD is slower than later warm answers.

Full machine-readable results: [model-upgrade.json](model-upgrade.json). Curated synthetic protocols and raw responses are published under [research/model-selection](../../research/model-selection/README.md). Original development probes and regression logs are retained locally under `/run/media/trijal/HDD/SpecialisationBySol/.runtime/model-upgrade`.
