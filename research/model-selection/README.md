# Small synthetic model-selection probe

These are four retained development runs from 17 October 2026, separate from
the LM-Synth manuscript experiment in `../evaluation/`. Five fictional Markdown
documents supply eight answerable questions, two absent-value questions, one
short-summary request and one direct native-tool selection smoke. The smoke
requests a tool call but does not execute that selected tool. None of the records
comes from the user's normal or presentation workspace.

| Frozen run | Model and context | Generated literal checks | Exact absent-value abstentions | Extractive fallbacks |
| --- | --- | --- | --- | --- |
| `baseline-old4b-v1` | Qwen3 4B, 8,192 | 7/8 | 2/2 | 0 |
| `candidate-qwen35-9b-v1` | Qwen3.5 9B, 8,192 | 5/8 | 1/2 | 2 |
| `candidate-qwen35-9b-12k-mapping-v1` | Qwen3.5 9B, 12,288; citation mapping | 4/8 | 1/2 | 4 |
| `candidate-qwen35-9b-12k-retry-v1` | Qwen3.5 9B, 12,288; mapping and citation retry | 8/8 | 2/2 | 0 |

The last row describes the selected configuration, not a model-only accuracy
improvement. Context size, evidence packaging, citation instructions and a
bounded citation-repair retry changed during development. The same questions
were reused. Generation was unseeded, at nonzero temperature; there are no
repeated trials or held-out confirmation. Literal matching can accept negated,
contradictory or unsupported mentions. A generated match also requires the final
response mode to be `agent`; returned exact excerpts are counted separately as
fallbacks. All four short summaries failed the complete generated-literal check,
and all four direct tool-selection smokes returned the requested tool call.
Read the raw responses before interpreting the summary counts.

`diagnostics/` contains two post-selection, two-question citation experiments.
The prefix-reminder variant skipped inference because its complete evidence
would not fit. The system-sentence replacement variant retained evidence and
returned matching literals with valid citation indices. These exploratory
conditions are separate from the four fixed runs and do not establish semantic
citation correctness or general accuracy.

## Frozen records and version boundaries

`results/<run-id>/` preserves the original JSON/JSONL bytes, including all ten
question outputs, protocol, identity, model-call payloads/responses, timings,
index metadata, short summary, tool smoke and before/after model/GPU snapshots.
The synthetic corpus is also byte-identical. Databases, caches, temporary files,
real-workspace activation records, process environments and download material
are excluded. `provenance.json` records original host paths, hashes and exported
file sizes; those absolute paths identify the original run, not required paths
on another computer. Source references in the retained answers point only to
the supplied five synthetic documents.

`original-harness/compare_models.py` is the exact harness matching the two 12K
run identities. The baseline's exact earlier script is retained as
`results/baseline-old4b-v1/executed-script.py`. The exact intermediate 8K
candidate script was not retained; its identity hash is preserved without
inventing a replacement. Each protocol records six application-module hashes.
At export, all six selected-retry hashes matched the application checkout;
earlier runs' Agent versions differed. The archive does not contain complete
snapshots of those earlier Agent revisions, so it is not a self-contained
bit-for-bit reconstruction of every historical application version.

`compare_models.py` is a clearly separated portable copy. It changes the module
description and makes the supplied corpus read-only; cases, scoring, recording
proxy and request execution are unchanged. It executes the **current** checkout
and writes fresh, uniquely named `runs/` directories and scratch files in `tmp/`.
Both are ignored by Git. It never writes `results/`, installs a model, changes
application settings or starts/stops an Ollama service. Do not execute the
archived scripts in their relocated snapshot directories. The local Ruff
configuration excludes those immutable snapshots from automated style changes.

Verify the published file checksums without inference:

```bash
(cd research/model-selection && sha256sum --check SHA256SUMS)
```

## Run a new development experiment

Install the project dependencies and required local model beforehand. Use a
dedicated, otherwise unused loopback runtime; on an 8 GB GPU, finish other model
workloads before loading a second chat-model copy. From the repository root:

```bash
mkdir -p research/model-selection/tmp
env TMPDIR="$PWD/research/model-selection/tmp" \
  OLLAMA_HOST=127.0.0.1:11439 OLLAMA_NO_CLOUD=1 \
  OLLAMA_MODELS="$PWD/.runtime/models" \
  OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=2 \
  .runtime/ollama/bin/ollama serve \
  > research/model-selection/tmp/ollama.log 2>&1 &
model_probe_pid=$!
```

Wait for that server to become ready, then run with a new ID:

```bash
.venv/bin/python research/model-selection/compare_models.py \
  --model qwen3.5:9b-q4_K_M --context-size 12288 \
  --ollama-url http://127.0.0.1:11439 --run-id fresh-local-retry-001
```

The harness refuses reused run IDs and the normal application's port 11434.
It verifies that the requested local chat model is already installed. The
recording proxy permits only local model metadata, embeddings and chat requests.
Use a fresh run ID whenever code, model, protocol or context settings change;
stochastic results may differ. Stop only the dedicated runtime you started when
the experiment is finished. GPU snapshots use `nvidia-smi` when available and
describe observed occupancy, not an isolated peak-memory experiment. This is
not native Windows GPU validation.
