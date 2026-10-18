# LocalMind local routing and file reference verification

Verified on 17 October 2026 on the Linux development laptop: RTX 5050 Laptop GPU
with 8 GB VRAM, Ryzen 7 250 and 16 GB nominal RAM. These checks cover application
behavior and reference integrity; they do not establish general answer accuracy.

## Corrected behavior

A complete greeting previously triggered embedding retrieval and a chat-model
load. Retrieved project context could then produce an unsolicited project summary.
Complete greetings, thanks and capability questions now use neutral deterministic
responses before model readiness, MCP, file retrieval or conversation history.
Mixed inputs such as “Hi, summarize api.md” still reach the normal document flow.
A greeting does not select a project from search results.

File inventory and exact filename lookup continue to read index metadata through
MCP without generation. Model evidence now includes exact titles, document IDs
and paths when available. Complete JSON records remain inside the serialized
context budget. If an exact path cannot fit, a later usable record can still be
selected and its citation number is reassigned consistently. Final synthesis
repacks the original evidence pool without tool schemas.

Several retrieved passages can come from one document. The interface groups those
passages under one file card while retaining all original references, for example
[1, 4, 5]. Equal basenames with different document identities remain distinct.
Cards identify actual excerpts and PDF pages when available, and disclose the
12-card display limit. Metadata-only catalog cards are labeled as files.

The document-reference guard now also applies to sourced imperative requests,
such as “Explain the setup.” A missing citation can trigger one tool-free retry
with fresh evidence; an unsuccessful retry returns labeled exact excerpts.
Explicit invalid reference numbers still fail immediately. These checks validate
reference integrity, not the truth of each generated statement. An uncited
proposal in Chat may also receive that retry when documents were retrieved;
the separate Projects planning workflow is unchanged.

## Automated results

| Check | Result |
|---|---|
| Linux suite | 163 passed in 27.65 s |
| Windows copy executed on Linux | 200 passed, 6 native-platform checks skipped, in 27.48 s |
| Added regression cases | 28; all earlier 135 Linux cases retained |
| Lint and whitespace | Passed in both copies |
| JavaScript syntax and grouped-card checks | Passed in both copies |

Tests use temporary synthetic data and scripted model responses, including the
actual MCP subprocess and outgoing request fitter. The two-source refresh test
uses a 12,288-token fixture so native Windows
temporary paths and schemas leave room for both records; its two-record and
payload/card assertions remain intact. Production defaults and the separate
4K/8K stress cases are unchanged. The two-source refresh test uses a 12,288-token fixture so native Windows
temporary paths and schemas leave room for both records; its two-record and
payload/card assertions remain intact. Production defaults and the separate
4K/8K stress cases are unchanged. No model accuracy percentage
can be inferred from the test pass count. Both suites reported the existing
Starlette/httpx deprecation warning, with no failed test.

## Live application checks

Each input below was measured once through the running Linux HTTP API. Local
responses include message persistence; catalog requests include MCP metadata
access. Neither path uses language-model inference.

| Input | Route and checked outcome | Elapsed |
|---|---|---:|
| hello | Local; no sources or tool actions | 0.0931 s |
| HI THERE!! | Local; no sources or tool actions | 0.0305 s |
| what can you do? | Local; no sources or tool actions | 0.0314 s |
| Thanks! | Local; no sources or tool actions | 0.0672 s |
| Greeting plus indexed-file list request | Catalog; all 7 indexed metadata records matched | 1.0497 s |
| Exact api.md existence check | Catalog; 1 exact metadata match | 1.4243 s |
| Deliberately absent filename | Catalog; 0 matches | 1.3488 s |

These are single development observations, not latency percentiles or model
speed measurements. Browser verification confirmed a grouped [1, 4, 5] card
opened the document identified by its original metadata. The application was
restarted with the saved 9B/12,288 profile preserved. Original conversations,
indexed documents and saved data counts were preserved; verification sessions
were deleted. Existing saved replies remain historical; the repair governs new
responses. Model loading from HDD can still delay a substantive model request.

## Version boundaries

The frozen paper benchmark used Qwen3 4B and an 8,192 context setting. Its 96/96
retrieval coverage, original 0/24 generation baseline, repaired 64-request replay
with 7/24 RAG and 3/24 agent complete matches, and historical 10/24 summary-value
retention remain unchanged. The [later 9B probe](model-upgrade.md) recorded 8/8
known checks and 2/2 unknown abstentions on a small postselected corpus; it is
separate from the paper benchmark and predates this routing repair. The current
local profile is optional Qwen3.5 9B Q4_K_M / 12,288; installation defaults remain
Qwen3 4B / 8,192. Native Windows GPU inference remains unmeasured.

The [machine-readable record](local-routing-fix.json) contains hashes of the
production and test files checked in each platform copy. Raw suite logs are in
[regressions](regressions/README.md). The earlier records and immutable research
archive retain their original source versions and measurements.

## Native Windows publication checks

[GitHub Actions run 39056375542](https://github.com/TrijalBurman/MCP-Server/actions/runs/39056375542)
at Windows commit `da05653` passed **206 tests on each of Python 3.12 and 3.13**
on native Windows Server runners. Lint, package verification, PowerShell syntax
and native CMD setup/start/stop smoke checks passed. The smoke tests used
synthetic data and a fake local model service; actual MCP retrieval and memory
persistence were exercised. This does not establish Windows 11 laptop GPU
performance or model-answer accuracy.

The first CI attempt at `9c280b2` passed on Python 3.13 but failed one Python 3.12
two-source test because its longer temporary paths exhausted the 8K fixture
budget. The corrected fixture uses 12K without changing its assertions or
production defaults. The successful run above checks that correction. These
native checks were confirmed after the document export; the rendered documents
retain their explicitly scoped Linux and Windows-copy-on-Linux measurements.
