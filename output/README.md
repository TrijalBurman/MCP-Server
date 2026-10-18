# LocalMind project deliverables

Updated on 17 October 2026 for the current local-routing and file-reference
repair. The Linux application is on
[`main`](https://github.com/TrijalBurman/MCP-Server/tree/main); the native Windows
edition is on [`windows`](https://github.com/TrijalBurman/MCP-Server/tree/windows).

| Deliverable | Files |
|---|---|
| Updated IEEE-format research manuscript, 12 pages | [PDF](pdf/localmind-ieee-research-paper.pdf), [editable LaTeX](pdf/localmind-ieee-research-paper.tex) |
| Updated blackbook following the institutional format, 60 pages | [PDF](blackbook/localmind-blackbook-60-pages.pdf), [Word](blackbook/localmind-blackbook-60-pages.docx) |
| Updated presentation guide and project explanation, 12 pages | [PDF](presentation/localmind-demo-and-speaking-guide.pdf), [Word](presentation/localmind-demo-and-speaking-guide.docx) |
| Ten-minute group script and demonstration setup | [Speaking script](presentation/10-minute-group-script.md), [start here](presentation/START-HERE.md) |
| Latest routing and file-reference verification | [Report](verification/local-routing-fix.md), [machine-readable record](verification/local-routing-fix.json) |
| Earlier model-selection development probe | [Report](verification/model-upgrade.md), [protocol and raw responses](../research/model-selection/README.md) |
| Frozen research evaluation and readings | [Evaluation](../research/evaluation/README.md), [literature readings](../research/literature-reading-list.md), [historical research archive](pdf/localmind-research-artifacts.zip) |
| Current document export verification | [Page counts and checksums](verification/document-refresh-2026-10-17.json) |
| Complete current source and deliverable package | [ZIP](localmind-final-presentation-package.zip), [SHA-256](localmind-final-presentation-package.sha256) |

Authors: Trijal Burman, Tiya Singh, Gayatri Rajesh Apotikar and Nimita Jestin.
Institution: Symbiosis Institute of Technology. Guide: Dr. Sonali Kothari.

## Current implementation and verification

The current exports explain neutral model-free greetings, exact indexed-file
metadata, complete numbered evidence with file identities, grouped source cards,
and one bounded retry for a missing document reference. A live greeting took
0.0931 seconds without retrieval or inference. That single observation is not a
language-model speed benchmark. Exact catalog checks matched all seven indexed
metadata records, one existing filename and no deliberately absent filename.

The current suites passed **163 Linux tests** and **200 Windows-copy tests on
Linux**, with **six native checks skipped**. These establish tested application
behavior, not general semantic accuracy. Citation checks validate references,
not the truth of every claim. Native Windows 11 GPU inference remains unmeasured.

The subsequent [native Windows CI run](https://github.com/TrijalBurman/MCP-Server/actions/runs/39056375542)
passed **206 tests on each of Python 3.12 and 3.13**, plus packaging and launcher
checks, at Windows commit `da05653`. It uses a fake local model server and does
not measure Windows laptop GPU inference. That confirmation supplements the
rendered documents' local-platform test counts.

The latest local development setup uses optional Qwen3.5 9B Q4_K_M with context
12288. Installation defaults remain Qwen3 4B with context 8192; see
[model profiles](../docs/model-profiles.md). Warm model requests and initial HDD
loading have different costs. New installations start with empty local data.

## Research version boundaries

The paper retains its original Qwen3 4B experiments and reports later application
verification separately. Lexical and hybrid retrieval covered 96/96 answerable
synthetic questions at five results. The original generation baseline matched
0/24 complete answers per method. The context-repair replay retained initial
evidence in 64/64 requests and matched 7/24 complete answers for RAG and 3/24 for
the MCP agent on reused questions. Historical summaries retained 10/24 requested
values and were not rerun. None of these counts is replaced by the later tests.

The small later 9B development probe produced eight known-fact checks with
supporting references and two unknown abstentions. It was unseeded and
postselected, and changed context and integration logic as well as model size.
It is not a new general accuracy score or a held-out rerun of the paper benchmark.
The manuscript uses IEEE conference format; it has not been accepted or
published by IEEE.

The nested research ZIP is an **immutable earlier artifact**. It contains the
manuscript and source snapshots from the context-repair export, not the current
paper or later routing code. Its checksums and all raw scientific records remain
unchanged. Earlier document-export and model-probe records retain their original
source hashes and measurements; the current export record identifies refreshed
documents. See [artifact notes](pdf/research-artifact-readme.md).

## Package contents

The complete current ZIP preserves repository paths, including application
source, launchers, tests, research data and updated deliverables. It contains no
downloaded models, local databases, private indexed documents, runtime binaries
or virtual environment. Extract it and follow the root README to install the
application. Its nested frozen research ZIP retains the historical boundary above.

Rebuild the outer ZIP after staging intended publication files with
`python scripts/package-deliverables.py`. It includes a SHA256SUMS manifest and
has a separate outer checksum. Unstaged new files and the archive itself are
excluded from its inputs.
