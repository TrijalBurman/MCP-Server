# LocalMind project deliverables

Submission files updated on 22 October 2026. The 38-page blackbook follows
the supplied sample, uses Bachelor of Computer Science Engineering, and includes
34 numbered references with linked in-text citations.
The application and research updates below retain their recorded scope. The Linux application is on
[`main`](https://github.com/TrijalBurman/MCP-Server/tree/main); the native Windows
edition is on [`windows`](https://github.com/TrijalBurman/MCP-Server/tree/windows).

| Deliverable | Files |
|---|---|
| Updated IEEE-format research manuscript, 12 pages | [PDF](pdf/localmind-ieee-research-paper.pdf), [editable LaTeX](pdf/localmind-ieee-research-paper.tex) |
| Blackbook following the new sample layout, 38 pages; 34 references | [PDF](blackbook/localmind-blackbook.pdf), [Word](blackbook/localmind-blackbook.docx) |
| Final project PowerPoint and timed slide notes | [PPTX](presentation/localmind-final-project-presentation.pptx), [PDF](presentation/localmind-final-project-presentation.pdf), [speaking notes](presentation/final-presentation-speaking-notes.md) |
| Updated presentation guide and project explanation, 12 pages | [PDF](presentation/localmind-demo-and-speaking-guide.pdf), [Word](presentation/localmind-demo-and-speaking-guide.docx) |
| Ten-minute group script and demonstration setup | [Speaking script](presentation/10-minute-group-script.md), [start here](presentation/START-HERE.md) |
| University submission requirements and outstanding steps | [Submission checklist](submission/SUBMISSION-CHECKLIST.md), [document verification](verification/submission-refresh-2026-10-22.json) |
| Recorded local-drive demonstration | [Video](video/localmind-local-drive-demo.mp4), [chapters and limitations](video/localmind-local-drive-demo.README.md) |
| Latest routing and file-reference verification | [Report](verification/local-routing-fix.md), [machine-readable record](verification/local-routing-fix.json) |
| Earlier model-selection development probe | [Report](verification/model-upgrade.md), [protocol and raw responses](../research/model-selection/README.md) |
| Frozen research evaluation and readings | [Evaluation](../research/evaluation/README.md), [literature readings](../research/literature-reading-list.md), [historical research archive](pdf/localmind-research-artifacts.zip) |
| Current blackbook format and reference verification | [Layout, page count and checksums](verification/blackbook-format-refresh.json) |
| Earlier document export verification | [Dated page counts and checksums](verification/document-refresh-2026-10-17.json) |
| Complete current source and deliverable package | [ZIP](localmind-final-presentation-package.zip), [SHA-256](localmind-final-presentation-package.sha256) |

Authors: Trijal Burman, Tiya Singh, Gayatri Rajesh Apotikar and Nimita Jestin.
Institution: Symbiosis Institute of Technology. Guide: Dr. Sonali Kothari.
Programme: Bachelor of Computer Science Engineering. Academic year: 23-27.

The supplied course notices require the final book, a research draft or other
qualifying research document, an official plagiarism report with overall
similarity strictly below 10%, and the final PPT. The group confirmed that the
institutional similarity check is still pending. Guide review and approval must
be obtained before submission. No similarity score, approval or portal submission
is claimed here. The shown deadline is 23 October 2026 at 12:00 AM, the start of
23 October; see the checklist for the exact files and remaining actions.

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
excluded from its inputs, except for the explicitly included current submission
exports, speaking notes, checklist and verification records.
