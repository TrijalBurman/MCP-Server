# LocalMind final presentation package

Updated 17 October 2026 for the greeting, metadata, citation and source-card
fixes. The Word guide, PDF guide and [speaking script](10-minute-group-script.md)
now describe the same version. Historical research measurements are retained;
see [the deliverables index](../README.md) for the report and paper.

Guide: Dr. Sonali Kothari. Institution: Symbiosis Institute of Technology.
Programme: Bachelor of Computer Science Engineering. Academic year: 23-27. Trijal Burman's PRN is
23070123145; Tiya Singh's corrected PRN is 23070123144; Gayatri Rajesh
Apotikar's is 23070123055; Nimita Jestin's is 23070122259.

Use `localmind-demo-and-speaking-guide.pdf` for navigation, the four speaking
parts, recovery steps and 15 viva answers. Read only the regular speech
paragraphs aloud. Silent actions and viva answers are outside the timed script.
The presentation, including the two-minute demonstration, totals ten minutes.

## Final submission slides

The [final PowerPoint](localmind-final-project-presentation.pptx) and
[slide-by-slide speaking notes](final-presentation-speaking-notes.md) cover the
course's required title, objectives, problem, literature, methodology,
implementation, results, discussion, conclusion and future scope. Use those notes
for the final deck's ten-minute sequence. The guide and older speaking script
below remain a supporting navigation, viva and rehearsal reference.

The [submission checklist](../submission/SUBMISSION-CHECKLIST.md) maps all four
portal requirements. The institutional similarity report is still pending and
must show overall similarity below 10%. Obtain the guide's review and approval
before submitting the book, draft paper and presentation.

## Running order

| Time | Speaker | Topic |
| --- | --- | --- |
| 0:00-2:15 | Trijal Burman | Problem, purpose and scope |
| 2:15-4:30 | Tiya Singh | Architecture, RAG, MCP and memory |
| 4:30-6:30 | Gayatri Rajesh Apotikar | Source-linked answer and saved memory |
| 6:30-10:00 | Nimita Jestin | Historical results, repairs, limits and next steps |

## Start and prepare the demonstration

The normal application was running on **http://127.0.0.1:8765** during the latest
update. The separate demonstration address is **http://127.0.0.1:8766** when its
launcher is running; its readiness has **not** been verified for this document
update. Check the chosen workspace before presenting. A URL in this guide is
not evidence that a service is currently running.

After completing the root README's Linux setup, start the demo from the
checkout root if needed:

```bash
bash output/presentation/start-presentation-demo.sh
```

Leave that terminal open. The launcher uses existing dependencies and cached
models, shares the loopback model service on 11434, and keeps sample data
separate from the normal application. A fresh checkout has no prepared personal
or demo database. Add `examples/knowledge` in **Library**, index the two supplied
files, and create **Lighthouse Presentation** in **Projects** before the timer.
The shell launcher is for Linux. Windows users should follow their branch's
native launcher instructions and prepare the same sample workflow there.

In **Settings**, verify the selected model and readiness. The source defaults
remain **Qwen3 4B / 8192 context tokens**. The optional
[Qwen3.5 9B / 12288 profile](../../docs/model-profiles.md) was checked on the
Linux development laptop and selected in its saved settings. The paper's
historical model results used 4B. This is not a universal best-model claim or
native Windows GPU validation.

Warm the selected model **before** starting the timer. Loading it from the HDD
can take roughly a minute or longer; the demonstration's **ten-second wait
limit assumes an already loaded model**. Initial downloads and loading are not
part of the two-minute demo.

## Follow the two-minute sequence

1. In **Library**, open `lighthouse-project.md` and show **Storage decision**.
2. In **Projects**, choose **Lighthouse Presentation** and **Open project chat**.
   Ask **What storage does the Lighthouse project use?**
3. Compare the answer's source with **SQLite** in the document. If it takes more
   than ten seconds, is wrong, or abstains, show the source directly and move on.
4. Send `/remember Use only the supplied Lighthouse sample files in this presentation.`
   Open **Memory**, select **Lighthouse Presentation**, and show the saved note.
5. Reload the Memory view once and hand over to Nimita. If chat remains busy,
   use **Memory > Add memory** with the project scope instead.

A reload demonstrates persistence through that reload. Separate storage tests
cover application restart persistence. Keep downloads, scans, restarts, long
summaries and plan generation outside the timed demo.

The stored `rehearsal-record.json` and rehearsal screenshots remain **dated
prepared evidence** from the earlier session. They were not repeated for this
update and must not be described as a fresh audience demonstration.

## Explain the latest changes accurately

- Pure greetings, thanks and exact capability questions return a neutral local
  response before model access, retrieval or old conversation context. They
  produce no source cards or invented project assumptions.
- File inventories and exact filename checks use paginated MCP index metadata.
  Document evidence now carries exact filenames, paths and document identifiers;
  one long path cannot block every later fitting record.
- The interface groups excerpts from the same document while preserving their
  original citation numbers. Equal basenames at different paths remain distinct.
- Substantive document replies require citations, including imperative prompts
  such as **Explain the setup**. A missing-citation answer can receive one
  tool-free retry from freshly packed evidence. Invalid references fail directly;
  unsuccessful retries keep the original safe excerpts and cards.

These controls check evidence delivery and reference integrity. A valid citation
can still fail to support a claim, so important answers need source inspection.

| Measurement | Result and scope |
| --- | --- |
| Latest regression suites | 163 Linux tests; 200 Windows-copy tests on Linux, 6 native checks skipped |
| Greeting route smoke check | One `hello` request took 0.0931 seconds; no model or retrieval call |
| Metadata smoke checks | 7 indexed files; 1 exact api.md match; 0 matches for an absent test filename |
| Small 9B development probe | 8/8 known-fact literal checks and 2/2 unknown abstentions; post-selected, not general accuracy |
| Historical context repair replay | 64/64 requests retained evidence within budget; RAG 7/24 and agent 3/24 complete fact-value matches on reused questions |
| Historical retrieval | Lexical and hybrid evidence coverage 96/96 at five; not answer accuracy |
| Historical generation baseline | 0/24 per method before the context repair |
| Historical long summaries | 10/24 requested values across three final summaries; not rerun |

The 0.0931-second greeting result is **not model-question latency**. The small
9B check is separate from the historical research benchmark. An additional
short-summary literal check in that development run did not pass. The earlier
native Windows CI result of 178 tests on each interpreter checked a previous
commit; it does not verify this latest change. Native Windows GPU inference
remains unmeasured.

## Submission and remaining limits

The blackbook follows the supplied report format and keeps its historical
measurements distinct from software updates. The separate IEEE-format paper has 12 pages, and this practical guide has 12 pages.
They serve different purposes. Editable source files are
included through the deliverables index.

Source access covers approved supported local folders, not every binary file
on a drive. Image-only PDFs require external OCR, and the SQLite database is not
encrypted. Future work includes stronger long-document coverage, held-out
factuality evaluation and native Windows GPU checks. Required institutional
AIC, similarity and AI-plagiarism reports, signatures and submission date must
be obtained through the institution; no scores or approvals have been invented.
