"""Build LM-Synth v1 without models, network access, or private source material.

The corpus is deliberately templated and synthetic. It is a reproducible mechanism
study, not a representative benchmark for real users' knowledge collections.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

SEED = 20261017
NAME = "LM-Synth v1"
BASE = Path(__file__).resolve().parent
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")

PROJECTS = (
    ("Aster Vale", "a reading-group notebook", "reading lists and discussion notes"),
    ("Birch Harbor", "a laboratory sample notebook", "sample descriptions and observation records"),
    ("Cobalt Ridge", "a bicycle workshop planner", "repair requests and workshop appointments"),
    ("Drift Meadow", "a campus equipment register", "equipment descriptions and loan requests"),
    ("Ember Quay", "a field-observation organizer", "habitat observations and field annotations"),
    ("Fable Grove", "an accessibility review workspace", "review findings and remediation notes"),
    ("Garnet Hollow", "a household energy diary", "meter readings and household annotations"),
    ("Hazel Reach", "a community seed catalog", "seed descriptions and growing observations"),
    ("Indigo Marsh", "a music rehearsal organizer", "rehearsal notes and arrangement references"),
    ("Juniper Crest", "a repair-manual index", "maintenance instructions and repair references"),
    ("Kestrel Brook", "a volunteer shift planner", "shift requests and coordinator notes"),
    ("Lumen Field", "an astronomy observation log", "sky observations and instrument annotations"),
)

PROFILES = ("Alder Ledger mode", "Birch Archive mode", "Cedar Shelf mode", "Dogwood Index mode",
            "Elm Folio mode", "Fir Chronicle mode", "Ginkgo Record mode", "Hemlock Register mode",
            "Iris Journal mode", "Juniper Vault mode", "Larch Dossier mode", "Maple Catalog mode")
PILOTS = ("Copper Heron pilot", "Amber Otter pilot", "Bronze Wren pilot", "Coral Badger pilot",
          "Golden Moth pilot", "Ivory Lark pilot", "Jade Robin pilot", "Lilac Crane pilot",
          "Ochre Fox pilot", "Pearl Lynx pilot", "Teal Sparrow pilot", "Violet Hare pilot")
GUARDRAILS = ("Silver Finch checklist", "Velvet Pine checklist", "Crimson Reed checklist",
              "Saffron Fern checklist", "Indigo Birch checklist", "Cerulean Moss checklist",
              "Citrine Willow checklist", "Maroon Thistle checklist", "Viridian Ash checklist",
              "Azure Clover checklist", "Magenta Elm checklist", "Sepia Rowan checklist")
APPROVERS = ("Elin Rao", "Marta Qureshi", "Soren Malik", "Isha Laurent", "Noah Menon", "Lea Farouk",
             "Tariq Ames", "Mina Keller", "Ravi Solis", "Nora Haddad", "Devika Lin", "Omar Voss")

SENTENCES = {
    "decisions": (
        "The decision record distinguishes an adopted choice from an option that remains under discussion.",
        "The team values understandable behavior over clever shortcuts that would be difficult to explain during handover.",
        "An implementation note should describe the consequence of a choice rather than merely restating its name.",
        "Reviewers compare the proposed workflow with the ordinary tasks that a new contributor will perform.",
        "The rationale keeps assumptions visible so a later maintainer can revisit them without reconstructing the meeting.",
        "A reversible choice is preferred when the available examples do not yet justify a more complicated design.",
        "The prototype should make incomplete work visible instead of displaying an apparently finished result.",
        "A change to a binding decision needs a replacement entry that explains what changed and why it changed.",
        "Background discussion provides context but does not override the explicitly labeled decisions in this record.",
        "The group keeps the acceptance language concrete enough to support an ordinary demonstration at review time.",
        "The design avoids coupling the user-facing terminology to an incidental detail of the current implementation.",
        "A rejected option can remain in the discussion notes, provided its rejected status is stated without ambiguity.",
        "The handover should let a contributor identify the active decision without searching through unrelated correspondence.",
        "Small examples are used to reveal awkward transitions before those transitions become part of the normal workflow.",
        "A clear boundary between recorded evidence and a proposed improvement helps prevent accidental scope expansion.",
        "The record preserves the reasoning behind the chosen behavior while allowing the interface wording to evolve.",
    ),
    "specifications": (
        "The specification describes observable behavior rather than prescribing how every internal function must be written.",
        "A user should be able to distinguish an accepted entry from a draft that still requires attention.",
        "Import feedback should identify the affected input and explain how the person can correct it.",
        "The interface should preserve the context of an unfinished task when the person moves to another view.",
        "A preview is useful only when it reflects the same interpretation that will be used after confirmation.",
        "The team checks empty, ordinary, and unusually detailed examples before calling a workflow ready.",
        "A warning must describe the consequence of continuing instead of relying on an unexplained technical label.",
        "The specification treats missing information as a visible state rather than silently inventing a default answer.",
        "Sorting and filtering should have stable behavior so repeated inspection of the same records is understandable.",
        "A contributor can propose a refinement, but a proposed refinement is not an approved release requirement.",
        "The work should remain inspectable through small examples whose expected results are written down in advance.",
        "Terminology used in a form should agree with terminology used in the corresponding confirmation and help text.",
        "Acceptance depends on completing the actual user task, including the transition back to a useful working state.",
        "An incomplete entry should remain available for correction without being mistaken for a validated record.",
        "The project keeps descriptive notes separate from the fields that determine operational behavior.",
        "When an action cannot finish, the interface should retain enough context for the person to retry deliberately.",
    ),
    "operations": (
        "The operating note separates routine handling from recovery after an interrupted task.",
        "A handover is complete only when another contributor can explain the next action using the written record.",
        "The team keeps recovery examples inspectable so a successful check can be distinguished from an assumption.",
        "A warning should point to the affected work and preserve the information needed for a deliberate retry.",
        "Routine inspection should avoid changing the records that the contributor is trying to understand.",
        "A restored working copy needs to be checked for both readable content and usable links between entries.",
        "The operating record favors clear responsibility over an informal expectation that somebody will notice a problem.",
        "A failed check remains visible until a contributor records the corrective action and its observed result.",
        "The release handover includes examples of ordinary work as well as examples involving an interrupted import.",
        "An incident note should distinguish an observed symptom from a proposed explanation for that symptom.",
        "The team records what was actually checked instead of treating a successful launch as proof of complete recovery.",
        "Follow-up work should have an explicit owner in the working record, even when several people discuss it.",
        "Operational instructions need enough context for a contributor who did not attend the original planning meeting.",
        "A change to the routine procedure should be reviewed alongside the examples that previously established its behavior.",
        "The checklist should expose unfinished work without turning routine inspection into an irreversible action.",
        "A useful handover describes a recoverable next step rather than leaving a vague instruction to investigate later.",
    ),
}


def slug(name: str) -> str:
    return name.lower().replace(" ", "-")


def date_aliases(value: date) -> list[str]:
    month = MONTHS[value.month - 1]
    return [f"{value.day} {month} {value.year}", f"{month} {value.day}, {value.year}",
            value.isoformat(), f"{value.day} {month[:3]} {value.year}",
            f"{month[:3]} {value.day}, {value.year}"]


def fact(document: str, aliases: list[str]) -> dict:
    return {"document": document, "aliases": aliases}


def section(title: str, lead: str, kind: str, rng: random.Random, target: int,
            binding: str | None = None) -> str:
    """Vary sentence order and fact position while preserving all binding facts."""
    pool = list(SENTENCES[kind])
    rng.shuffle(pool)
    sentences = [lead]
    index = 0
    while sum(map(len, sentences)) + len(sentences) < target:
        sentences.append(pool[index % len(pool)])
        index += 1
    paragraphs = [" ".join(sentences[start:start + 3]) for start in range(0, len(sentences), 3)]
    if binding:
        paragraphs.insert(rng.randrange(1, max(2, len(paragraphs))), binding)
    return f"## {title}\n\n" + "\n\n".join(paragraphs)


def project_document(project: str, theme: str, records: str, kind: str, values: dict,
                     index: int) -> str:
    rng = random.Random(SEED + 100 * index + {"decisions": 1, "specifications": 2, "operations": 3}[kind])
    if kind == "decisions":
        rows = (
            ("Purpose and decision scope", f"{project} is {theme}; this record explains choices affecting {records}.", None),
            ("Adopted persistence choice", f"The {project} prototype needs a consistent way to preserve its working records.",
             f"Approved storage profile: {values['storage'][0]}. This is the adopted profile for {project}."),
            ("Alternatives and rationale", f"Contributors to {project} compare alternatives through the same representative user tasks.", None),
            ("Boundaries of the decision", f"For {project}, background suggestions remain separate from binding decisions.", None),
            ("Review arrangement", f"The {project} decision record includes a specific checkpoint for reconsidering these choices.",
             f"The internal review date for {project} is {values['review'][0]}. This is the scheduled decision review."),
            ("Handover expectations", f"The next contributor to {project} should be able to recover the active rationale from this document.", None),
        )
    elif kind == "specifications":
        rows = (
            ("User tasks and record types", f"The {project} specification concerns {records} in {theme}.", None),
            ("Pilot cohort and release boundary", f"The {project} team uses a named pilot to distinguish a controlled rollout from ordinary development.",
             f"The approved rollout codename for {project} is {values['pilot'][0]}. This exact label identifies the pilot cohort."),
            ("Interaction and feedback", f"A person working in {project} needs understandable feedback when moving between incomplete and accepted entries.", None),
            ("Import acceptance limit", f"The {project} import contract applies to one submitted batch rather than to the lifetime of the workspace.",
             f"The accepted import limit for {project} is {values['batch'][0]}. A larger batch must be split before acceptance."),
            ("Inspection and correction", f"The {project} team evaluates how contributors inspect and repair a draft before confirming it.", None),
            ("Release guardrail", f"The final {project} release check is described as a named working artifact rather than an informal conversation.",
             f"The required release guardrail for {project} is the {values['guardrail'][0]}. Completion of that checklist is required for rollout."),
        )
    else:
        rows = (
            ("Routine operation", f"This operating note describes how the {project} team maintains {records} during ordinary work.", None),
            ("Backup procedure", f"The {project} operating routine includes an explicit cadence for copying the working records.",
             f"The backup cadence for {project} is every {values['backup'][0]}. This is the interval between routine backup runs."),
            ("Interruption handling", f"When a task in {project} is interrupted, a contributor first identifies the affected work before retrying it.", None),
            ("Release authorization", f"A finished build of {project} still needs the recorded authorization before a release can proceed.",
             f"The sole release approver for {project} is {values['approver'][0]}. That person signs off before the release goes live."),
            ("Recovery rehearsal", f"The {project} team rehearses an interrupted-workstation scenario using a copy of representative records.", None),
            ("Recovery objective and handover", f"The recovery objective for {project} is measured from detection of a workstation interruption to restored useful work.",
             f"The maximum recovery time for {project} is {values['recovery'][0]}. The rehearsal must demonstrate usable work within this target."),
        )
    title = {"decisions": "Decision record", "specifications": "Functional specification", "operations": "Operations and handover"}[kind]
    text = f"# {project}: {title}\n\nAuthored fictional project record for LM-Synth v1.\n\n"
    text += "\n\n".join(section(heading, lead, kind, rng, rng.randint(510, 610), binding)
                           for heading, lead, binding in rows)
    return text + "\n"


def long_document(project: str, values: dict, index: int) -> str:
    rng = random.Random(SEED + 5000 + index)
    rows = (
        ("Persistence decision", "decisions", "storage", "Approved storage profile"),
        ("Planned review", "decisions", "review", "Internal decision review date"),
        ("Controlled rollout", "specifications", "pilot", "Approved pilot rollout codename"),
        ("Incoming records", "specifications", "batch", "Accepted import limit"),
        ("Backup routine", "operations", "backup", "Routine backup cadence"),
        ("Release authorization", "operations", "approver", "Sole release approver"),
        ("Recovery commitment", "operations", "recovery", "Maximum recovery time"),
        ("Final guardrail", "specifications", "guardrail", "Required release guardrail"),
    )
    text = f"# {project}: consolidated readiness dossier\n\nAuthored fictional long document for LM-Synth v1.\n\n"
    text += "\n\n".join(section(heading,
        f"This section of the {project} dossier records the rationale, working boundaries, and handover considerations for {heading.lower()}.",
        kind, rng, rng.randint(1750, 1900),
        f"Binding fact for {project} - {label}: {values[key][0]}. This is the active value for this dossier.")
        for heading, kind, key, label in rows)
    return text + "\n"


def build() -> tuple[dict, dict[str, str]]:
    rng = random.Random(SEED)
    profiles, pilots, guardrails, approvers = map(list, (PROFILES, PILOTS, GUARDRAILS, APPROVERS))
    for pool in (profiles, pilots, guardrails, approvers):
        rng.shuffle(pool)
    documents, queries, summaries, files = [], [], [], {}
    for index, (project, theme, records) in enumerate(PROJECTS):
        paths = {kind: f"projects/{slug(project)}/{kind}.md"
                 for kind in ("decisions", "specifications", "operations")}
        batch, backup, recovery = 137 + 19 * index, 47 + 7 * index, 31 + 4 * index
        values = {
            "storage": [profiles[index]], "review": date_aliases(date(2027, 2, 4) + timedelta(days=index * 11)),
            "pilot": [pilots[index]], "guardrail": [guardrails[index]], "approver": [approvers[index]],
            "batch": [f"{batch} items per batch", f"{batch} items", f"{batch}-item batches"],
            "backup": [f"{backup} hours", f"{backup}-hour", f"{backup} h"],
            "recovery": [f"{recovery} minutes", f"{recovery}-minute", f"{recovery} min"],
        }
        for kind, path in paths.items():
            files[path] = project_document(project, theme, records, kind, values, index)
            documents.append({"path": path, "project": project, "kind": kind})
        specifications = (
            ("lexical", f"What approved storage profile does {project} use?", [("decisions", "storage")]),
            ("lexical", f"What is the internal review date for {project}?", [("decisions", "review")]),
            ("lexical", f"Which pilot rollout codename is approved for {project}?", [("specifications", "pilot")]),
            ("lexical", f"What is the backup cadence for {project}, in hours?", [("operations", "backup")]),
            ("paraphrase", f"For {project}, how many incoming items may a person submit together in one import?", [("specifications", "batch")]),
            ("paraphrase", f"Who must give the go-ahead before a finished {project} build can go live?", [("operations", "approver")]),
            ("paraphrase", f"After a workstation interruption, how soon must the {project} team be able to do useful work again?", [("operations", "recovery")]),
            ("cross_document", f"For {project}, name the mandatory release guardrail and give the scheduled internal decision review date.",
             [("specifications", "guardrail"), ("decisions", "review")]),
        )
        for kind, question, supports in specifications:
            queries.append({"id": f"Q{len(queries) + 1:03}", "project": project, "kind": kind,
                            "query": question, "answerable": True,
                            "facts": [fact(paths[document], values[key]) for document, key in supports]})

    missing_requests = (
        "What is the signed procurement reference number for {project}?",
        "What exact per-user subscription fee was approved for {project}?",
        "On what calendar date will the external security audit of {project} take place?",
        "What is the production asset-registry identifier assigned to {project}?",
        "Which minimum mobile operating-system version is required by {project}?",
        "What is the contractually mandated legal retention period for {project} records?",
        "What is the expiry date of the vendor support contract for {project}?",
        "Which government certification identifier has been issued to {project}?",
    )
    for index, template in enumerate(missing_requests):
        project = PROJECTS[index][0]
        queries.append({"id": f"U{index + 1:03}", "project": project, "kind": "unanswerable",
                        "query": template.format(project=project), "answerable": False, "facts": []})

    long_projects = ("Morrow Annex", "Oriole Basin", "Tamarisk Span")
    long_profiles = ("Saffron Orchard mode", "Cerulean Cove mode", "Vermilion Summit mode")
    long_pilots = ("Violet Mantle pilot", "Scarlet Plover pilot", "Turquoise Newt pilot")
    long_guardrails = ("Crimson Pine checklist", "Alabaster Oak checklist", "Ultramarine Spruce checklist")
    long_approvers = ("Nila Varma", "Ravi Chen", "Tessa Noor")
    for index, project in enumerate(long_projects):
        path = f"long/{slug(project)}.md"
        batch, backup, recovery = 877 + 29 * index, 211 + 11 * index, 93 + 13 * index
        values = {
            "storage": [long_profiles[index]], "review": date_aliases(date(2028, 9, 13) + timedelta(days=index * 37)),
            "pilot": [long_pilots[index]], "guardrail": [long_guardrails[index]], "approver": [long_approvers[index]],
            "batch": [f"{batch} items per batch", f"{batch} items", f"{batch}-item batches"],
            "backup": [f"{backup} hours", f"{backup}-hour", f"{backup} h"],
            "recovery": [f"{recovery} minutes", f"{recovery}-minute", f"{recovery} min"],
        }
        files[path] = long_document(project, values, index)
        documents.append({"path": path, "project": project, "kind": "long_summary"})
        summaries.append({"id": f"S{index + 1:03}", "document": path,
            "request": (f"Summarize the full {project} dossier. Explicitly report all eight binding facts: "
                        "the approved storage profile, internal review date, pilot rollout codename, import item limit, "
                        "backup cadence in hours, sole release approver, maximum recovery time in minutes, and required "
                        "release guardrail. Keep the relationships clear and cite this document. Do not omit facts from later sections."),
            "facts": [{"aliases": values[key]} for key in
                      ("storage", "review", "pilot", "batch", "backup", "approver", "recovery", "guardrail")]})

    dataset = {"name": NAME, "seed": SEED,
        "description": ("Authored English synthetic mechanism-study corpus: twelve fictional project families "
                        "with decisions, specifications, and operations records, plus three long readiness dossiers. "
                        "Gold values and document labels are defined before model execution. Not a representative "
                        "sample of real personal files or an external accuracy benchmark."),
        "documents": documents, "queries": queries, "summaries": summaries}
    validate(dataset, files)
    return dataset, files


def validate(dataset: dict, files: dict[str, str]) -> None:
    assert len(dataset["documents"]) == len(files) == 39
    assert len(dataset["queries"]) == 104 and len(dataset["summaries"]) == 3
    assert Counter(query["kind"] for query in dataset["queries"]) == {
        "lexical": 48, "paraphrase": 36, "cross_document": 12, "unanswerable": 8}
    assert len({query["id"] for query in dataset["queries"]}) == 104
    for document in dataset["documents"]:
        text = files[document["path"]]
        lower, upper = (14000, 18000) if document["kind"] == "long_summary" else (3500, 5500)
        assert lower <= len(text) <= upper, (document["path"], len(text))
    for query in dataset["queries"]:
        assert bool(query["facts"]) == query["answerable"]
        for item in query["facts"]:
            assert item["aliases"][0] in files[item["document"]], (query["id"], item)
        if query["kind"] == "cross_document":
            assert len(query["facts"]) == len({item["document"] for item in query["facts"]}) == 2
    for summary in dataset["summaries"]:
        text = files[summary["document"]]
        assert len(summary["facts"]) == 8
        positions = [text.index(item["aliases"][0]) / len(text) for item in summary["facts"]]
        assert positions[0] < 0.2 and positions[-1] > 0.8
        assert positions == sorted(positions)


def corpus_readme(dataset: dict, files: dict[str, str]) -> str:
    ordinary = [len(text) for path, text in files.items() if path.startswith("projects/")]
    long_sizes = [(entry["path"], len(files[entry["path"]])) for entry in dataset["documents"]
                  if entry["kind"] == "long_summary"]
    return f"""# LM-Synth v1: authored synthetic corpus specification

This corpus is a reproducible mechanism study for LocalMind. Every project, person,
decision, date, and quantity is fictional evaluation material. No private files,
conversations, third-party documents, evaluated-model outputs, or evaluated-model
feedback were used to create or revise its gold values. Template and builder-code
drafting used AI assistance; the tested Qwen3 and EmbeddingGemma models did not
create the gold labels or act as judges. The builder uses only Python's
standard library, fixed English month names, UTF-8/LF output, and seed {SEED}.

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
  operations records: 36 ordinary Markdown files, {min(ordinary):,}–{max(ordinary):,}
  Python characters each. Six sections contain contextual rationale and spread
  binding facts through the document. Reusable prose templates are varied by a
  deterministic sentence order and insertion position.
* Three long Markdown readiness dossiers, each with eight sections and one unique
  checkable binding fact in every section. Their lengths are:
""" + "\n".join(f"  * `{path}`: {size:,} characters." for path, size in long_sizes) + """
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
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BASE)
    parser.add_argument("--check", action="store_true", help="Verify existing artifacts without rewriting them")
    arguments = parser.parse_args()
    dataset, files = build()
    root = arguments.output.resolve()
    artifacts = {root / "corpus" / path: text for path, text in files.items()}
    artifacts[root / "dataset.json"] = json.dumps(dataset, ensure_ascii=False, indent=2) + "\n"
    artifacts[root / "README-corpus.md"] = corpus_readme(dataset, files)
    existing = set((root / "corpus").rglob("*.md")) if (root / "corpus").exists() else set()
    expected = {root / "corpus" / path for path in files}
    unexpected = existing - expected
    if unexpected:
        raise SystemExit("Unexpected Markdown files would contaminate the corpus: " + ", ".join(map(str, unexpected)))
    for path, content in artifacts.items():
        if arguments.check:
            if not path.is_file() or path.read_bytes() != content.encode("utf-8"):
                raise SystemExit(f"Artifact differs or is missing: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    print(f"{NAME}: 39 documents; 96 answerable + 8 unanswerable queries; 3 eight-fact summary tasks.")
    print("Artifacts verified byte-for-byte." if arguments.check else f"Artifacts written to {root}.")


if __name__ == "__main__":
    main()
