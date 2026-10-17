# LocalMind project deliverables

This directory collects the research paper, blackbook, presentation material and
verification records. The Linux application is on
[`main`](https://github.com/TrijalBurman/MCP-Server/tree/main); the native Windows
edition is on [`windows`](https://github.com/TrijalBurman/MCP-Server/tree/windows).

| Deliverable | Files |
|---|---|
| IEEE-format research manuscript, 11 pages | [PDF](pdf/localmind-ieee-research-paper.pdf), [editable LaTeX](pdf/localmind-ieee-research-paper.tex) |
| Blackbook following the supplied institutional format, 60 pages | [PDF](blackbook/localmind-blackbook-60-pages.pdf), [Word](blackbook/localmind-blackbook-60-pages.docx) |
| Presentation guide and project explanation, 12 pages | [PDF](presentation/localmind-demo-and-speaking-guide.pdf), [Word](presentation/localmind-demo-and-speaking-guide.docx) |
| Current ten-minute group script and demonstration setup | [Speaking script](presentation/10-minute-group-script.md), [start here](presentation/START-HERE.md) |
| Latest local model and answer-grounding verification | [Report](verification/model-upgrade.md), [machine-readable record](verification/model-upgrade.json) |
| Frozen research data and reproduction instructions | [Research evaluation](../research/evaluation/README.md), [archived paper artifacts](pdf/localmind-research-artifacts.zip) |
| Later synthetic model-selection probes | [Protocol, raw responses and limits](../research/model-selection/README.md) |
| Complete source and deliverable package | [ZIP](localmind-final-presentation-package.zip), [SHA-256](localmind-final-presentation-package.sha256) |

Authors: Trijal Burman, Tiya Singh, Gayatri Rajesh Apotikar and Nimita Jestin.
Institution: Symbiosis Institute of Technology. Guide: Dr. Sonali Kothari.

## Versions and results

The paper, blackbook and PDF/Word presentation guide are frozen documents from
the earlier Qwen3 4B evaluation and context-fitting repair. Their reported
measurements, model names, source snapshots and test totals describe those runs.
Statements about the repair being uncommitted describe its status at that time.
The manuscript is in IEEE conference format; it has not been accepted or
published by IEEE.

The current application also includes exact file-catalog queries, complete
query-centered evidence records, and one bounded regeneration of an answer
missing required citations. The latest Linux development setup uses Qwen3.5 9B
Q4_K_M with context 12288. Installation defaults remain Qwen3 4B and context
8192; see [model profiles](../docs/model-profiles.md).

Latest local regression results are 135 Linux tests passed and 172 tests passed
for the Windows copy executed on Linux, with six native checks skipped. A small
later development probe answered eight known-fact questions with supporting
references and abstained on two unknowns. These observations are separate from
the paper benchmark and do not establish general accuracy or native Windows GPU
performance. Citation checks validate references, not the truth of every claim.

The Markdown speaking script and setup notes describe the current demonstration;
the exported PDF/Word guide remains an identified earlier snapshot. No research
results were replaced with the later development probe.

## Package contents

The complete ZIP preserves repository paths, including application source,
launchers, tests, research data and the files in this directory. It contains no
downloaded models, local databases, private indexed documents, runtime binaries
or virtual environment. Extract it and follow the root README to install the
application. A fresh installation starts with an empty library and project list.

The nested research ZIP is the earlier, immutable paper artifact. Its source
snapshots and checksums retain their original version boundary. The outer ZIP
and its checksum are rebuilt from the intended Git-staged project files with
`python scripts/package-deliverables.py`. Stage new intended publication files
before rebuilding; unstaged new files are excluded.
