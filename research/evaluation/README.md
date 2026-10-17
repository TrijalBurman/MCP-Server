# LocalMind paper: evaluation and reproduction

This is the frozen Qwen3 4B paper evaluation. Source-status statements and test
counts below describe those recorded runs, before the subsequent GitHub
publication and grounding changes. The later Qwen3.5 9B development probes are
separate under [model-selection](../model-selection/README.md); they do not
replace these measurements. See [the deliverables index](../../output/README.md).

This package accompanies the IEEE-format manuscript by Trijal Burman, Tiya Singh,
Gayatri Rajesh Apotikar, and Nimita Jestin, Symbiosis Institute of Technology.
Measurements were collected on 17 October 2026. It is an engineering research
manuscript, not a claim of IEEE acceptance or publication.

## What was measured

- Released Linux source: `ddbbbb7be35a83c6ebc32706bb0aaf41ff379ff8`.
- Separate Windows source: `0e0bbf6f944bc6f2534f882c858ca4cdd22e6443`.
- LM-Synth v1: 39 authored English Markdown files, 201,518 characters, indexed as
  141 chunks. There are 96 answerable retrieval queries, eight absent-value
  queries, and three eight-fact long-document summary tasks.
- Primary generation: 24 answerable queries (eight per category), all eight
  absent-value queries, and two conditions. All 64 raw responses are retained.
- Primary summaries: three actual MCP/map/merge executions, 15 sections total.
- A **post hoc diagnostic**, in a separate directory, replays the same 64
  generation conditions with an exact serialized-cost context fitter. It changes
  the fitter only in memory and does not modify either released application.

The corpus is synthetic, templated, small, text-only, and not a representative
personal library. See [the corpus specification](README-corpus.md). No personal
documents or private conversations were indexed. Model inference was local;
literature lookup and prior installation downloads required internet.

## Results and their limits

The primary run is in `results/2026-10-17-main-v1/`. Its records are never replaced
by the diagnostic. `summary.json` aggregates the raw files, `identity.json`
identifies source files/models/options, and `context-audit.json` explains the
observed evidence loss before generation. `retrieval.jsonl`, `generation.jsonl`,
and `summaries.jsonl` contain individual outcomes, including failures.

Lexical and hybrid CES@5 were 96/96; dense was 91/96. This is **operational
alias/path evidence coverage**, not 100% answer accuracy or semantic relevance.
Both released generation conditions matched 0/24 complete answers and abstained
on every question. The context fitter discarded evidence blocks because its raw
prefix estimate did not account for JSON escaping. The original full passages
covered all 32 positive fact slots; 1,000-character prefixes covered 15, and
fitted messages covered none. A separate prefix-loss bottleneck remains after
the exact-cost correction. Summaries retained 10/24 requested values despite
visiting all 15 sections; some outputs also made contradictory absence claims.

`results/2026-10-17-context-diagnostic-v1/` retains all diagnostic responses,
actual fitted messages, bounds checks, model-call metadata, parent hashes, and
post-selection alias audits. This intervention was designed after inspecting
primary failures. It is mechanism/development evidence, not held-out confirmation
or a production repair by itself. The later applied repair is recorded separately below. Neither corpus nor prompt
was tuned against model responses, and no gold labels select context content.

FVM and AFVM are normalized substring/alias proxies. They can miss valid
paraphrases and accept negated or contradictory mentions. Citation measurements
check indices and gold document paths, not claim entailment. Strict abstention
means the requested phrase occurs; an always-abstaining system can score 8/8 on
the negative cases while failing all positive ones. Inspect raw responses before
making a semantic accuracy claim.

Primary summary intervals for CES@5 and AFVM use project-cluster bootstrap where
reported in the paper. Raw aggregation also retains descriptive Wilson intervals
for transparency; these assume independent questions and are **not** the paper's
primary generation intervals. Degenerate empirical bootstrap intervals at all
successes/failures do not imply population certainty. The diagnostic helper's
summary includes Wilson values too; cluster intervals used in the paper are
computed from its retained per-project rows in `paper-statistics.json`.

Times are one-device, one-run observations. Primary QA times mostly measure
short false abstentions. They are not successful-answer throughput or isolated
MCP overhead. RSS sums can double-count shared pages; GPU memory includes the
desktop. Resource samples and model counters are included for audit.

## Reproduce on Linux

Use the Linux source commit above and install its environment with the existing
setup instructions. Python and model dependencies are not bundled in this
research artifact. The experiment used Python 3.14.4, Ollama 0.35.0, Qwen3 4B
Instruct 2507 Q4_K_M, and EmbeddingGemma BF16 (768 dimensions). Exact digests and
package versions are in each protocol. Changed runtime/model versions require
a distinct run ID and must not be pooled with the original measurements.

From the repository root:

```bash
.venv/bin/python research/evaluation/build_corpus.py --check
.venv/bin/python research/evaluation/run_context_diagnostic.py --check-only
.venv/bin/python research/evaluation/analyse_results.py --check-only
```

Choose a free loopback port. With the downloaded official runtime and model
weights already present, start a dedicated server from this checkout:

```bash
mkdir -p .runtime/research
env OLLAMA_HOST=127.0.0.1:11437 OLLAMA_NO_CLOUD=1 \
  OLLAMA_MODELS="$PWD/.runtime/models" \
  OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=2 \
  .runtime/ollama/bin/ollama serve > .runtime/research/reproduction-ollama.log 2>&1 &
research_ollama_pid=$!
```

Wait for that server's readiness message. Keep its PID for correct resource
attribution. Then run a fresh experiment, preserving the supplied results:

```bash
.venv/bin/python -u research/evaluation/run_benchmark.py \
  --run-id reproduction-001 --runtime-pid "$research_ollama_pid"

.venv/bin/python -u research/evaluation/run_context_diagnostic.py \
  --primary-run reproduction-001 --run-id reproduction-001-exact \
  --runtime-pid "$research_ollama_pid"
```

The harness refuses identity-changing resume. Use a new run ID after changing
the corpus, engine, model, or settings. Existing completed outputs are retained,
not resampled to select a better response. Nonzero temperature without a fixed
seed means generation may differ across runs. The resource sampler uses Linux
`/proc` and NVIDIA tooling; the Windows application is validated separately and
this benchmark is not a native Windows GPU experiment. Stop only the dedicated
server you started after your experiment finishes.

## Artifact map

| Artifact | Purpose |
| --- | --- |
| `build_corpus.py`, `corpus/`, `dataset.json` | Frozen corpus, labels and byte-identical builder |
| `run_benchmark.py` | Primary retrieval, generation, summary and resource evaluation |
| `run_context_diagnostic.py` | Exact-cost adapter, CPU invariants and isolated diagnostic replay |
| `analyse_results.py` | Recompute/check raw scores, project-cluster intervals and manuscript statistics without inference |
| `prompt_diagnostic.py`, `results/exploratory-prompt-placement.log` | Earlier exploratory placement probe, including its oversized-pinned-request failure; not a completed benchmark |
| `results/2026-10-17-main-v1/` | Original observed results, identities, telemetry and context audit |
| `results/2026-10-17-context-diagnostic-v1/` | Separate post hoc correction results and fitted payloads |
| `results/paper-statistics.json` | Auditable values/intervals used by the manuscript |
| `results/functional-validation.json` | Functional test and native Windows CI evidence |
| `results/linux-tests.log`, `linux-tests.xml` | Fresh Linux test evidence, separate from model effectiveness |

No model weights, private database, virtual environment, credentials, personal
corpus, or application runtime is included in the research archive. Historical result files remain frozen. The subsequent local production repair is identified separately below.


## Applied production repair and replay (17 October 2026)

The later repair changes the actual `copilot/ollama.py` in both local platform
checkouts. It is uncommitted and unpublished; the historical commit references
above do not contain it. `results/2026-10-17-production-context-fix-v1/` retains the
separate direct-production generation replay, with no diagnostic fitter substitution.
Its `repair-verification.json` records exact source hashes and all outgoing
serialized-budget checks. All 64 initial reference inputs were retained, all
model calls stayed within budget, and no request failed. Complete fact-value
matches were 7/24 RAG and 3/24 MCP; macro FVM was 37.50% and 27.08%. These are
reused-question development results, not held-out accuracy. No additional
model-selected tool executed. Retrieval and summary experiments were not rerun.

Current checks passed 62 Linux tests and 99 tests for the Windows copy executed
on Linux, with six native checks skipped. Historical native Windows CI does not
validate this new repair on Windows or establish Windows 11 GPU performance.

The accompanying archive includes exact snapshots under `production-repair/`:
`copilot/ollama.py`, `tests/test_context.py`, and
`.runtime/context-fix/verify_repair.py`. Copy these paths into a separate checkout
of the recorded Linux base to inspect/reproduce the repaired implementation.
The verifier expects the primary index at
`.runtime/research/index/2026-10-17-main-v1/memory.sqlite3`, a dedicated local
runtime at port 11438, and a fresh run/index directory. Rebuild the primary index
using the frozen harness if necessary. Select a NEW run ID in the copied verifier
before rerunning; it refuses to overwrite existing results. Its class wrapper
observes actual outgoing requests and does not replace production fitting.
The exact supplied verifier hash is retained for auditing the observed run.
Do not run both the historical and repaired studies in one modified checkout
and then describe them as the same source version.
