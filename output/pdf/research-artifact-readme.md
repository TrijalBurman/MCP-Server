# LocalMind research manuscript and reproducibility artifacts

Authors: Trijal Burman, Tiya Singh, Gayatri Rajesh Apotikar, and Nimita Jestin.
Institution: Symbiosis Institute of Technology. Guide: Dr. Sonali Kothari.
Revised after later grounding, routing, and model-profile checks on 17 October 2026.

The existing editable manuscript is `localmind-ieee-research-paper.tex`, a
**12-page IEEE conference-format document** using IEEEtran with 26 references,
two figures, six tables, methods, results, limitations, and an artifact appendix.
The source includes its figures and bibliography. This is not a claim of IEEE
acceptance or publication. The updated PDF compiled successfully with the cached
bundled Tectonic command-line compiler and all 12 rendered pages were visually
reviewed. The editor's separate compiler could not fetch its uncached package
bundle; this is an environment limitation rather than a source compilation error.

Frozen research results remain unchanged. The original 4B generation baseline
matches 0/24 complete answers. Its later production-repair replay retains initial
evidence on 64/64 requests and yields 7/24 RAG and 3/24 MCP complete fact-value
matches on reused synthetic questions. The evaluation-only diagnostic is also
reported separately. These are not held-out confirmation or general accuracy.
Historical retrieval (96/96 lexical and hybrid CES@5), summary retention (10/24
requested values), and resource measurements were not rerun. The historical
generation runs still use passage prefixes; current query-centered whole-record
packaging is a later implementation change.

The current implementation adds model-free full-match greeting/help routes,
exact indexed-catalog lookup, complete title/identifier/path evidence records,
grouped source cards retaining original citation numbers, and bounded citation
regeneration with extractive fallback. Citation checks establish reference
integrity, not claim entailment. Current tests pass 163 cases on Linux and 200
for the Windows copy on Linux, with six native checks skipped. Earlier 43/62/99
local counts and the cited 86-case-per-interpreter native Windows workflow are
historical snapshots; they do not substitute for the current scope or establish
Windows 11 laptop GPU performance.

Setup defaults remain Qwen3 4B at 8,192 tokens. The optional current local profile
uses `qwen3.5:9b-q4_K_M` at 12,288 tokens with thinking disabled. A separate small
development probe under `research/model-selection/` records 8/8 answerable
literal-value matches and 2/2 requested unknown responses for its final
configuration. Its reused questions, unseeded outputs, postselection, and changed
model/context/integration prevent a general accuracy claim or an isolated model
comparison. Its short-summary diagnostic is not a rerun of the historical
summary experiment. The single model-free greeting and exact-catalog checks in
the manuscript are functional observations, not inference-speed benchmarks.

**The ZIP is frozen and contains an earlier paper.**
`localmind-research-artifacts.zip` has not been rebuilt for this revision. It
retains the earlier manuscript/source, annotated literature readings, frozen
corpus and labels, original harness, historical raw QA results, production
verification summaries, exact repair snapshots under `production-repair/`, and
its original `SHA256SUMS` manifest. Those snapshots were uncommitted at capture;
later published application snapshots are Linux `4a3533a` and Windows `b377ac6`.
Neither changes the frozen baseline retroactively. The ZIP is not a copy of this
current manuscript or every current application file. See
`research/evaluation/README.md` for experiment reproduction and version boundaries.

The historical archive excludes private databases, personal conversations, model
weights, virtual environments, credentials, and runtime binaries. Research probes
use synthetic documents. Nonzero-temperature generation is unseeded and may
differ on rerun; retain the supplied observations and configuration identities.
