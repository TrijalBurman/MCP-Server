# LM-Synth v1: authored synthetic corpus specification

This corpus is a reproducible mechanism study for LocalMind. Every project, person,
decision, date, and quantity is fictional evaluation material. No private files,
conversations, third-party documents, evaluated-model outputs, or evaluated-model
feedback were used to create or revise its gold values. Template and builder-code
drafting used AI assistance; the tested Qwen3 and EmbeddingGemma models did not
create the gold labels or act as judges. The builder uses only Python's
standard library, fixed English month names, UTF-8/LF output, and seed 20261017.

## Reproduce

From the repository root, run `python research/evaluation/build_corpus.py`.
Run `python research/evaluation/build_corpus.py --check` to verify byte-identical
generated artifacts without rewriting them. Python 3.11+ is sufficient to build
the corpus; the application's own environment requirements are separate.

Only `research/evaluation/corpus/` is a source folder for indexing. Keep
`dataset.json`, this specification, scorer code, and generated answers outside
approved source folders to prevent gold-label or prior-answer leakage.

## Composition and gold labels

* 12 fictional project families, each with decisions, specifications, and
  operations records: 36 ordinary Markdown files, 3,953–4,528
  Python characters each. Six sections contain contextual rationale and spread
  binding facts through the document. Reusable prose templates are varied by a
  deterministic sentence order and insertion position.
* Three long Markdown readiness dossiers, each with eight sections and one unique
  checkable binding fact in every section. Their lengths are:
  * `long/morrow-annex.md`: 16,214 characters.
  * `long/oriole-basin.md`: 16,214 characters.
  * `long/tamarisk-span.md`: 16,224 characters.
* 96 answerable retrieval questions: 48 lexical, 36 paraphrase, and 12 requiring
  two facts from different files. Every family has four lexical questions, three
  paraphrases, and one two-document question. All gold facts name their correct
  relative document path; a matching string in another file is insufficient.
* Eight missing-value questions request absent metadata. The corresponding
  `answerable` value is false and `facts` is empty. Internal review dates do not
  establish an external security-audit date; backup cadence does not establish a
  contractual legal-retention period.
* Three summary requests explicitly ask for all eight binding categories. Their
  gold values occur from early to late source positions. These tasks measure
  coverage of requested facts, not exhaustive semantic completeness of the prose.

The schema is `documents:[{path,project,kind}]`,
`queries:[{id,project,kind,query,answerable,facts:[{document,aliases}]}]`, and
`summaries:[{id,document,request,facts:[{aliases}]}]`. All document paths are
relative to `corpus/`. The first alias of every fact is literal source text.
Additional date and numeric-unit aliases allow common answer renderings; they
are not additional facts. Bare unqualified numbers are deliberately excluded.
The builder checks counts, length bounds, literal gold support, cross-file
requirements, and early/late summary positions before writing any artifacts.

## Interpretation and limits

This is authored, templated, English, text-only data with a small set of fields.
It does not represent the diversity of real personal libraries, PDF layouts,
OCR, code understanding, multilingual queries, or human tasks. Artificial labels
are easy to check but can make lexical matching unusually useful. The paraphrase
questions retain the project name and sometimes share other vocabulary with the
source, so they do not isolate pure semantic retrieval. Three-document project
families create useful wrong-file distractors but not a realistic large archive.

The 12 project families are dependence clusters. Repeated questions and template
variants are not independent user samples. Eight missing-value cases and three
summary documents are diagnostic cases with wide uncertainty. Report denominators,
per-category results, failures, and paired cluster-level uncertainty. Do not infer
general real-world factual accuracy, production security, or universal model
superiority from this dataset. No corpus or gold-value changes based on evaluated
model responses belong to the frozen v1 benchmark.

Exact alias matching is an auditable proxy, not a complete factuality judgment:
negated values, wrong relationships, and answers containing both correct and
conflicting values require additional review. A present citation index is not
proof that its passage supports a claim. Genuine abstention requires admitting
that the requested value is absent without inventing a replacement.
