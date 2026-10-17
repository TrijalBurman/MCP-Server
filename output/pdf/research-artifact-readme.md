# LocalMind research manuscript and reproducibility artifacts

Authors: Trijal Burman, Tiya Singh, Gayatri Rajesh Apotikar, and Nimita Jestin.
Institution: Symbiosis Institute of Technology. Guide: Dr. Sonali Kothari.
Updated after the production context repair on 17 October 2026.

The PDF is an **11-page IEEE conference-format manuscript**, using IEEEtran,
with 26 references, two figures, six tables, methods, results, limitations and an
artifact appendix. It is not a claim of IEEE acceptance or publication.
The editable standalone LaTeX includes figures and bibliography.

The original 0/24 generation baseline, earlier evaluation-only diagnostic and
new applied-production replay are reported separately. The repaired replay
retains initial evidence on 64/64 requests and yields 7/24 RAG and 3/24 MCP
complete fact-value matches on reused synthetic questions. It is not held-out
confirmation or general accuracy. Historical retrieval, summary and resource
measurements were not rerun. The separate passage-prefix limitation remains.

The archive includes the manuscript and source; annotated literature readings;
frozen corpus, labels and original harness; all three sets of raw QA results;
production verification summaries; exact repaired source/test/verifier snapshots
under `production-repair/`; and a `SHA256SUMS` manifest. The snapshots are local
uncommitted code, not files claimed to be present in historical GitHub commits.
See `research/evaluation/README.md` for reproduction and version boundaries.

Current tests pass 62 cases on Linux and 99 for the Windows copy on Linux, with
six native checks skipped. Earlier native Windows CI is historical; native
Windows repair validation and Windows 11 GPU inference remain unmeasured.

No private database, personal conversations, model weights, virtual environment,
credentials or runtime binaries are bundled. Nonzero-temperature generation is
unseeded and may differ on rerun; retain the supplied observations.

The PDF was compiled successfully with the cached bundled Tectonic executable
and visually reviewed. The editor's separate compiler could not retrieve its
uncached package bundle; the supplied PDF is complete and the source editable.
