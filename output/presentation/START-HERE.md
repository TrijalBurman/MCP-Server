# LocalMind final presentation package

Current repository setup notes, updated for the grounding repair and model upgrade
on 17 October 2026. The exported PDF/Word guide is the earlier context-repair
snapshot; the current [Markdown script](10-minute-group-script.md) includes the
later application changes. See [the deliverables index](../README.md) for versions.
Guide: Dr. Sonali Kothari. Department: Minors in AIML. Academic year: 23–27.
Tiya Singh's corrected PRN is 23070123144; Trijal Burman's is 23070123145.

Read `localmind-demo-and-speaking-guide.pdf` first. It contains the project
explanation, exact navigation, four speaking parts, recovery steps and 15 viva
answers. The speech and demonstration together take ten minutes.

## Running order

| Time | Speaker | Topic |
|---|---|---|
| 0:00–2:15 | Trijal Burman | Problem, purpose and scope |
| 2:15–4:30 | Tiya Singh | Architecture, RAG, MCP and memory |
| 4:30–6:30 | Gayatri Rajesh Apotikar | Source-linked answer and saved memory |
| 6:30–10:00 | Nimita Jestin | Historical baseline, repaired replay, limits and next steps |

## Open the app

- Normal application: http://127.0.0.1:8765
- Prepared demonstration: http://127.0.0.1:8766

Both applications were restarted with the repaired code and checked for model
readiness. Their data directories are separate; normal project data was preserved.
If the demo stops, run `bash output/presentation/start-presentation-demo.sh` from
the project root. The launcher uses existing dependencies and cached models.

The Linux demo shares the model service on 11434 with the normal application.
Its sample database remains separate on port 8766. On a fresh checkout, add
`examples/knowledge` in Library, index it, and create **Lighthouse Presentation**
in Projects before starting the timed presentation; prepared local databases are
not published. Start the launcher after completing the root README setup.

Warm the selected model before the timer starts. Loading the 9B profile from
the HDD took roughly a minute in the latest check; the ten-second demonstration
cutoff assumes the model is already loaded. The installation default is still
4B; the tested optional [9B profile](../../docs/model-profiles.md) is described
separately. Windows users should follow the Windows branch's native launcher
instructions; this demo shell script is for Linux.

Use only `examples/knowledge`. In **Library**, open `lighthouse-project.md` and
show **Storage decision**. In **Projects**, choose **Lighthouse Presentation** and
**Open project chat**. Ask **What storage does the Lighthouse project use?**
Open the source card and compare the answer with **SQLite** in the document.
Then send `/remember Use only the supplied Lighthouse sample files in this presentation.`
Open **Memory**, select **Lighthouse Presentation**, and reload to show the saved
record. Use the source reader or manual memory form if inference takes over ten seconds.

The post-restart rehearsal returned SQLite with source [1], showed local search
and recall in the trace, and confirmed existing project memory remained available.
This is a single sample rehearsal, not an accuracy benchmark. The screenshots
are labeled prepared rehearsal evidence; the JSON record distinguishes the new
post-restart API check from the earlier browser reload check.

## Explain the repair accurately

The old fitter could discard an evidence block because JSON escaping made it
larger than its raw-prefix estimate. The repaired fitter measures the actual
serialized UTF-8 cost and retains a complete-character prefix that fits.

| Measurement | Result and scope |
|---|---|
| Repaired evidence delivery | 64/64 replay requests retained initial references and stayed within budget |
| Repaired complete fact-value matching | RAG 7/24; MCP 3/24, on reused synthetic questions |
| Context-repair snapshot functional checks | Linux 62 passed; Windows copy on Linux 99 passed, 6 native checks skipped |
| Historical retrieval | Lexical and hybrid coverage 96/96 at five; not answer accuracy |
| Historical generation | 0/24 per method before repair |
| Historical summaries | 10/24 requested values; not rerun after repair |

These rows are frozen observations from the context-repair step, before the
later grounding changes and repository publication. Current file listings use
index metadata, and document evidence uses complete query-centered records
instead of fixed prefixes. An uncited document answer receives one bounded
tool-free retry, followed by the same reference guard and source-excerpt fallback.
The current local suites passed 135 Linux tests and 172 tests for the Windows
copy on Linux, with six native checks skipped. The later 9B development probe
answered eight known-fact questions and abstained on two unknowns; it is not a
rerun of the paper benchmark. See [the latest verification](../verification/model-upgrade.md).
There is no claim of perfect accuracy or native Windows GPU validation.

## Submission files

The blackbook PDF has **60 total pages**, follows `report format.docx`, and uses
the template's APA references. The separate **11-page IEEE-format manuscript**
acknowledges Dr. Sonali Kothari and includes the new production repair evidence.
The speaking guide has **12 pages**. Editable DOCX/LaTeX sources are included;
later edits may change pagination.

The research archive contains frozen original results, the historical diagnostic,
new production replay, exact repaired-source snapshots and checksums. It excludes
personal databases, model weights and credentials. Required institutional AIC,
similarity and AI-plagiarism reports, signatures and submission date remain to be
obtained through the institution; no scores or approvals have been invented.
