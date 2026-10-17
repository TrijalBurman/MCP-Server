# LocalMind context-fitting repair

Historical verification snapshot: publication status, test totals and performance
below refer to the recorded context-repair step. Later grounding/model changes
are documented in [model-upgrade.md](model-upgrade.md); see also the
[deliverables index](../README.md). The raw research runs remain unchanged.

Verified locally on 17 October 2026. The repair is applied to the Linux checkout
and the separate Windows checkout. It has not been committed or pushed.

## What changed

The old fitter estimated a raw text prefix and then checked its JSON size.
Quotes, backslashes, control characters and Unicode could make the actual message
larger than that estimate. The fitter consequently discarded the whole message.

The repaired fitter searches for the longest complete-character prefix whose
actual serialized UTF-8 message fits. Accounting includes escaping, metadata,
the shortening marker and tool schemas. Pinned system instructions and the
current user request retain their original protection. Tool-call metadata remains
whole. Small remaining budgets are checked exactly instead of rejected by a
fixed heuristic.

## Validation

- Linux: **62 tests passed**.
- Windows checkout tested on Linux: **99 passed; 6 native Windows checks skipped**.
- **19 new regression cases** cover escaping, multilingual text, exact boundaries,
  tiny remaining budgets, input immutability, tool metadata and the actual outgoing
  chat payload. Fourteen of the initial fifteen cases failed before the repair.
- Independent review exercised 3,000 deterministic randomized budget cases.
- Lint and whitespace checks passed. Both platform copies contain identical
  repaired inference code and regression tests.

The live verification used the installed local Qwen3 4B model, the existing
synthetic corpus and the same 32 questions under two methods. It exercised
production code directly, with actual MCP calls and no diagnostic fitter
substitution. All **64/64 requests retained initial reference evidence** and all
model requests stayed within the configured serialized-input budget. There were
no request errors.

| Condition | Complete factual answers | Macro fact-value match |
|---|---:|---:|
| Original single-pass RAG | 0/24 | 0% |
| Repaired single-pass RAG | 7/24 | 37.50% |
| Original MCP agent | 0/24 | 0% |
| Repaired MCP agent | 3/24 | 27.08% |

These alias-based scores are a replay on reused synthetic questions, not
held-out confirmation or general accuracy. The separate 1,000-character passage
prefix limitation remains: preserving a message does not ensure that every
requested fact was included in that message. This repair addresses evidence
being discarded after serialization, rather than redesigning retrieval or
summarization.

The paper, blackbook and presentation materials now describe this applied repair.
Their historical measurements remain labeled and unchanged; new replay outcomes
are reported separately. New raw records and
the exact source hashes are in
`research/evaluation/results/2026-10-17-production-context-fix-v1/`.
The machine-readable summary is `output/verification/context-fitting-fix.json`.

## Use the repair

Restart any LocalMind process that was already running when the code changed.
Use the same normal or presentation launcher and browser address as before.
Newly started processes import the repaired code automatically. No model change,
dependency installation or reindexing is required for this fix.


## Restart and documentation update

The normal application at http://127.0.0.1:8765 and isolated demonstration at
http://127.0.0.1:8766 were restarted and reported both local models ready.
Existing demo documents, projects and saved memories were preserved. A fresh
post-restart request returned SQLite with source [1] and actual MCP search/recall
trace entries. The prepared sample result is rehearsal evidence only.

The updated submission contains a 60-page blackbook, 11-page IEEE-format paper,
12-page demo/speaking guide and revised ten-minute group script. The original
benchmark result files were preserved; the documents distinguish those historical
measurements from the new production replay.
