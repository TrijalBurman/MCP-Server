"""Validate frozen raw records and reproduce paper-statistics.json without inference.

Only the optional final JSON write changes an artifact. --check-only validates all
raw scores and compares the four data sections with an existing statistics file.
"""
# ruff: noqa: E402
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_benchmark as primary

CORE_KEYS = ("primary", "diagnostic", "diagnostic_additional", "diagnostic_resource")
DIAGNOSTIC_METHODS = ("single_pass_rag_exact", "mcp_agent_exact")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def relative_source(value, document_paths):
    """Permit analysis after relocation without editing a frozen raw response."""
    value = str(value).replace("\\", "/")
    marker = "/research/evaluation/corpus/"
    relative = value.rsplit(marker, 1)[-1] if marker in value else value
    if relative not in document_paths:
        raise AssertionError(f"Source path is not a declared corpus document: {value}")
    return relative


def scoring_response(response, document_paths):
    return {**response, "sources": [{**source, "path": relative_source(source["path"], document_paths)}
                                   for source in response.get("sources", [])]}


def validate_generation(rows, questions, document_paths, methods):
    assert len(rows) == 64 and len({row["id"] for row in rows}) == 32
    assert len({(row["id"], row["method"]) for row in rows}) == 64
    for method in methods:
        selected = [row for row in rows if row["method"] == method]
        assert len(selected) == 32 and sum(row["answerable"] for row in selected) == 24
    for row in rows:
        question = questions[row["id"]]
        for field in ("project", "kind", "answerable"):
            assert row[field] == question[field], (row["id"], field)
        calculated = primary.score_answer(scoring_response(row["response"], document_paths), question)
        assert row["scores"] == calculated, (row["id"], row["method"], "stored answer score differs")


def validate_retrieval(rows, questions, document_paths):
    assert len(rows) == 288 and len({(row["id"], row["method"]) for row in rows}) == 288
    assert {row["method"] for row in rows} == {"lexical", "dense", "hybrid"}
    for method in ("lexical", "dense", "hybrid"):
        assert len([row for row in rows if row["method"] == method]) == 96
    for row in rows:
        question = questions[row["id"]]
        assert question["answerable"] and row["project"] == question["project"] and row["kind"] == question["kind"]
        hits = [{**hit, "path": relative_source(hit["document"], document_paths)} for hit in row["hits"]]
        assert primary.retrieval_metrics(hits, question["facts"]) == row["metrics"], (row["id"], row["method"])


def diagnostic_summary(rows):
    result = {"description": "Post-hoc context-fitting diagnostic, not independent confirmation.",
              "independent_confirmation": False, "generation": {}}
    for method in DIAGNOSTIC_METHODS:
        selected = [row for row in rows if row["method"] == method]
        positive = [row for row in selected if row["answerable"]]
        negative = [row for row in selected if not row["answerable"]]
        correct = sum(row["scores"]["all_facts_correct"] for row in positive)
        result["generation"][method] = {
            "n": len(selected), "answerable_n": len(positive), "complete_correct": correct,
            "complete_accuracy": correct / len(positive),
            "complete_accuracy_wilson_ci95": primary.wilson(correct, len(positive)),
            "fact_recall": statistics.mean(row["scores"]["fact_recall"] for row in positive),
            "unanswerable_n": len(negative),
            "explicit_abstention_n": sum(row["scores"]["explicit_abstention"] for row in negative),
            "all_gold_documents_cited_n": sum(row["scores"]["all_gold_documents_cited"] for row in positive),
            "errors_n": sum(bool(row.get("error")) for row in selected),
            "extra_tool_calls_n": sum(row["extra_tool_calls"] for row in selected),
            "wall_seconds": primary.stats([row["wall_seconds"] for row in selected]),
            "model_calls": primary.stats([len(row["model_calls"]) for row in selected]),
            "rows_with_retained_reference_n": sum(any(call["fitted_reference_characters"] > 0
                                                    for call in row["context_fits"]) for row in selected),
        }
    return result


def diagnostic_additional(rows, questions):
    result = {}
    for method in sorted(DIAGNOSTIC_METHODS):
        positives = [row for row in rows if row["method"] == method and row["answerable"]]
        grouped = defaultdict(list)
        slots, complete, total = 0, 0, 0
        for row in positives:
            grouped[row["project"]].append(float(row["scores"]["all_facts_correct"]))
            facts = questions[row["id"]]["facts"]
            masks = []
            for invocation in row["context_fits"]:
                messages = invocation["fitted_messages"]
                reference = "\n".join(message.get("content", "") for message in messages
                    if message.get("role") == "tool" or (message.get("role") == "system"
                    and message.get("content", "").startswith("UNTRUSTED DOCUMENT EVIDENCE:")))
                recalculated = [primary.match_fact(reference, fact) for fact in facts]
                assert recalculated == invocation["retained_fact_alias_matches"], (row["id"], method)
                assert len(reference) == invocation["fitted_reference_characters"]
                masks.append(recalculated)
            covered = [any(mask[index] for mask in masks) for index in range(len(facts))]
            slots += sum(covered)
            complete += all(covered)
            total += len(facts)
        groups = list(grouped.values())
        assert len(groups) == 12 and all(len(group) == 2 for group in groups)
        rng = primary.np.random.default_rng(20261017)
        means = [primary.np.mean([value for index in rng.integers(0, len(groups), len(groups))
                                 for value in groups[index]]) for _ in range(2000)]
        result[method] = {
            "cluster_bootstrap_afvm_ci95": primary.np.percentile(means, [2.5, 97.5]).tolist(),
            "post_fit_fact_slots": int(slots), "post_fit_complete": int(complete), "post_fit_slots_total": total,
            "citation_indices_valid_positive_n": sum(row["scores"]["citation_indices_valid"] for row in positives),
            "by_kind": {kind: {"n": sum(row["kind"] == kind for row in positives),
                               "afvm_n": sum(row["scores"]["all_facts_correct"] for row in positives if row["kind"] == kind)}
                        for kind in sorted({row["kind"] for row in positives})},
        }
    return result


def analyse(primary_run, diagnostic_run):
    parent = HERE / "results" / primary_run
    diagnostic = HERE / "results" / diagnostic_run
    dataset_path = HERE / "dataset.json"
    dataset = read_json(dataset_path)
    questions = {question["id"]: question for question in dataset["queries"]}
    document_paths = {document["path"] for document in dataset["documents"]}
    primary_rows = primary.load_jsonl(parent / "generation.jsonl")
    diagnostic_rows = primary.load_jsonl(diagnostic / "generation.jsonl")
    retrieval = primary.load_jsonl(parent / "retrieval.jsonl")
    summary_rows = primary.load_jsonl(parent / "summaries.jsonl")
    validate_generation(primary_rows, questions, document_paths, ("single_pass_rag", "mcp_agent"))
    validate_generation(diagnostic_rows, questions, document_paths, DIAGNOSTIC_METHODS)
    assert [(row["id"], row["method"] + "_exact", row["prompt"]) for row in primary_rows] == [
        (row["id"], row["method"], row["prompt"]) for row in diagnostic_rows]
    validate_retrieval(retrieval, questions, document_paths)
    summary_gold = {item["id"]: item for item in dataset["summaries"]}
    assert len(summary_rows) == 3 and {row["id"] for row in summary_rows} == set(summary_gold)
    for row in summary_rows:
        item = summary_gold[row["id"]]
        assert row["document"] == item["document"]
        assert row["fact_matches"] == [primary.match_fact(row["response"]["content"], fact) for fact in item["facts"]]
    cached_primary = read_json(parent / "summary.json")
    assert cached_primary["dataset"] == dataset["name"] and cached_primary["summaries"] == summary_rows
    calculated_diagnostic = diagnostic_summary(diagnostic_rows)
    assert calculated_diagnostic == read_json(diagnostic / "summary.json"), "Diagnostic cached summary differs from raw rows"
    resource_files = sorted(diagnostic.glob("resources-*.json"))
    resource_rows = [row for path in resource_files for row in read_json(path)]
    assert resource_rows, "No diagnostic resource samples"
    result = {"primary": cached_primary, "diagnostic": calculated_diagnostic,
              "diagnostic_additional": diagnostic_additional(diagnostic_rows, questions),
              "diagnostic_resource": {"samples": len(resource_rows),
                  "rss_sum_mib": max(row["rss_sum_mib"] for row in resource_rows),
                  "gpu_total_used_mib": max(row["gpu_total_used_mib"] for row in resource_rows)}}
    files = [dataset_path, HERE / "run_benchmark.py", HERE / "run_context_diagnostic.py", Path(__file__),
             parent / "identity.json", parent / "generation.jsonl", parent / "retrieval.jsonl",
             parent / "summaries.jsonl", parent / "summary.json", diagnostic / "identity.json",
             diagnostic / "generation.jsonl", diagnostic / "summary.json", *resource_files]
    parent_identity = read_json(parent / "identity.json")
    diagnostic_identity = read_json(diagnostic / "identity.json")
    assert parent_identity["dataset_sha256"] == digest(dataset_path)
    assert parent_identity["engine_sha256"] == digest(HERE / "run_benchmark.py")
    assert diagnostic_identity["primary_generation_sha256"] == digest(parent / "generation.jsonl")
    assert diagnostic_identity["primary_identity_sha256"] == digest(parent / "identity.json")
    assert diagnostic_identity["diagnostic_engine_sha256"] == digest(HERE / "run_context_diagnostic.py")
    result["provenance"] = {
        "primary_run": primary_run, "diagnostic_run": diagnostic_run,
        "input_sha256": {path.relative_to(HERE).as_posix(): digest(path) for path in files},
        "validation": {"primary_generation_rows": len(primary_rows), "diagnostic_generation_rows": len(diagnostic_rows),
                       "retrieval_rows": len(retrieval), "summary_rows": len(summary_rows),
                       "stored_scores_recomputed": True, "paired_prompts_and_order_identical": True},
        "cluster_bootstrap": {"unit": "project", "projects": 12, "draws": 2000, "seed": 20261017,
                              "metric": "all-facts value match (string-alias proxy)", "interval": "95% percentile"},
        "path_normalization": "Frozen source paths are resolved against declared corpus-relative document names for portable analysis.",
        "diagnostic_scope": "Post-hoc mechanism diagnostic, not independent confirmation; no inference or new observations.",
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-run", default="2026-10-17-main-v1")
    parser.add_argument("--diagnostic-run", default="2026-10-17-context-diagnostic-v1")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    for value in (args.primary_run, args.diagnostic_run):
        if not primary.re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
            raise ValueError("Use a simple run ID with letters, digits, underscores, and hyphens.")
    result = analyse(args.primary_run, args.diagnostic_run)
    destination = HERE / "results/paper-statistics.json"
    if args.check_only:
        if destination.exists():
            existing = read_json(destination)
            assert all(result[key] == existing[key] for key in CORE_KEYS), "Recomputed paper data differ from existing statistics"
        print("Validated 64 primary + 64 diagnostic QA scores, 288 retrieval records, and 3 summary fact sets.")
        print("Existing four paper-statistics sections match exactly. No output files were changed.")
    else:
        primary.write_json(destination, result)
        print(f"Validated and wrote {destination}")


if __name__ == "__main__":
    main()
