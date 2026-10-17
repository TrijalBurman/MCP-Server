"""Post-hoc context-fitting diagnostic, not independent confirmation.

This replays the primary run's exact 32 question pairs and prompts. Only the
in-memory fit_context implementation used during a measured chat call changes.
The released application, frozen primary engine, corpus, and outputs stay intact.
"""
# ruff: noqa: E402
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import inspect
import json
import platform
import sqlite3
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_benchmark as primary

from copilot.agent import SYSTEM, Agent, _text_budget
from copilot.config import Settings
from copilot.library import Library
from copilot.ollama import fit_context as released_fit_context
from copilot.store import Store

MARKER = "\n[Local context shortened.]"
METHODS = {"single_pass_rag": "single_pass_rag_exact", "mcp_agent": "mcp_agent_exact"}
DEFAULT_PRIMARY = "2026-10-17-main-v1"
DEFAULT_RUN = "2026-10-17-context-diagnostic-v1"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def message_cost(item):
    return len(json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) + 24


def input_budget(context_size):
    return context_size - min(1536, context_size // 3) - 256


def exact_json_fit(messages, tools, context_size):
    """Released policy with exact prefix fitting instead of an estimated byte clip.

Gold labels never enter this function. A shortened item's longest character
prefix is chosen solely by the cost of its actual serialized representation.
"""
    budget = input_budget(context_size)
    first = dict(messages[0])
    latest_user = max((i for i, item in enumerate(messages) if item["role"] == "user"), default=-1)
    pinned = {0}
    if latest_user >= 0:
        pinned.add(latest_user)
    fixed = sum(message_cost(messages[i]) for i in pinned)
    if fixed > budget:
        raise ValueError("This request is too long for the selected local context. Shorten it or increase the context size in Settings.")
    schema_cost = len(json.dumps(tools, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) if tools else 0
    if schema_cost + fixed + 500 > budget:
        tools, schema_cost = None, 0
    available = budget - fixed - schema_cost
    selected = {i: dict(messages[i]) for i in pinned}
    personal = [i for i, item in enumerate(messages) if i not in pinned and item["role"] == "system"
                and item.get("content", "").startswith(("UNTRUSTED PERSONAL AND PROJECT", "UNTRUSTED PROJECT REFERENCE"))]
    fresh_tools = [i for i in reversed(range(len(messages))) if messages[i]["role"] == "tool"]
    priorities = personal + fresh_tools
    priorities += [i for i, item in enumerate(messages)
                   if i not in pinned and i not in priorities and item["role"] == "system"]
    priorities += [i for i in reversed(range(len(messages))) if i not in pinned and i not in priorities]
    for i in priorities:
        item = dict(messages[i])
        if available <= 100:
            break
        if message_cost(item) > available:
            if item.get("tool_calls") or available - 120 < 100:
                continue
            content = item.get("content", "")
            minimum = {**item, "content": MARKER}
            if message_cost(minimum) > available:
                continue
            low, high = 0, len(content)
            while low < high:
                middle = (low + high + 1) // 2
                candidate = {**item, "content": content[:middle] + MARKER}
                if message_cost(candidate) <= available:
                    low = middle
                else:
                    high = middle - 1
            item["content"] = content[:low] + MARKER
        amount = message_cost(item)
        if amount <= available:
            selected[i] = item
            available -= amount
    selected[0] = first
    return [selected[i] for i in sorted(selected)], tools


def invariant_checks():
    """CPU-only checks; no model, server, database, or gold labels are used."""
    checks = []
    for context in (4096, 8192, 16384):
        for label, content in (
            ("nested_quotes", "UNTRUSTED DOCUMENT EVIDENCE:\n" + json.dumps({"text": 'A "quoted" value\\path\n' * 1800})),
            ("backslashes", "UNTRUSTED DOCUMENT EVIDENCE:\n" + "C:\\folder\\file \\\" " * 2200),
            ("unicode", "UNTRUSTED DOCUMENT EVIDENCE:\n" + "日本語の資料と記録 नमस्ते \\" * 2200),
        ):
            original = [{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": "Give the requested fact, with a source."},
                        {"role": "system", "content": content}]
            saved = copy.deepcopy(original)
            fitted, schemas = exact_json_fit(original, None, context)
            # Independent accounting of the actual fitted serialized representation.
            measured = sum(len(json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                           + 24 for item in fitted)
            assert measured <= context - min(1536, context // 3) - 256
            assert original == saved and fitted[0] == saved[0] and fitted[1] == saved[1]
            assert schemas is None and len(fitted) == 3
            clipped = fitted[2]["content"]
            assert clipped.endswith(MARKER)
            prefix = clipped[:-len(MARKER)]
            assert content.startswith(prefix)
            candidate = {**fitted[2], "content": content[:len(prefix) + 1] + MARKER}
            remainder = input_budget(context) - sum(message_cost(item) for item in fitted[:2])
            assert message_cost(candidate) > remainder, "The selected prefix was not maximal"
            checks.append({"case": label, "context_size": context, "serialized_cost": measured,
                           "budget": input_budget(context), "retained_characters": len(prefix)})
    simple = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Hello"},
              {"role": "system", "content": "Small reference."}]
    assert exact_json_fit(simple, None, 8192) == released_fit_context(simple, None, 8192)
    tools = [{"type": "function", "function": {"name": "read", "description": "small"}}]
    assert exact_json_fit(simple, tools, 8192)[1] == tools
    oversized_tools = [{"type": "function", "function": {"name": "read", "description": "x" * 10000}}]
    assert exact_json_fit(simple, oversized_tools, 4096)[1] is None
    priority = simple[:2] + [
        {"role": "system", "content": "UNTRUSTED DOCUMENT EVIDENCE:" + "old" * 4000},
        {"role": "system", "content": "UNTRUSTED PERSONAL AND PROJECT REFERENCE DATA: preference"},
        {"role": "tool", "tool_name": "read_document", "content": "NEW_EVIDENCE " + '"\\' * 12000},
    ]
    fitted, _ = exact_json_fit(priority, None, 4096)
    assert any("preference" in item.get("content", "") for item in fitted)
    assert any(item.get("content", "").startswith("NEW_EVIDENCE") for item in fitted)
    try:
        exact_json_fit([simple[0], {"role": "user", "content": "x" * 20000}], None, 4096)
    except ValueError:
        pass
    else:
        raise AssertionError("An oversized pinned request must be rejected")
    return {"passed": True, "prefix_cases": checks,
            "additional_checks": ["unmodified inputs", "pinned system/current user", "maximal serialized prefix",
                                  "unchanged fully fitting input", "schema keep/drop policy",
                                  "personal/fresh-tool priority", "oversized pinned request rejected"]}


def reference_messages(messages):
    return [item for item in messages if item.get("role") == "tool"
            or (item.get("role") == "system" and item.get("content", "").startswith("UNTRUSTED DOCUMENT EVIDENCE:"))]


def reference_text(messages):
    return "\n".join(item.get("content", "") for item in reference_messages(messages))


def evidence_block(hits, context_size):
    budget = max(4000, context_size * 2)
    return "UNTRUSTED DOCUMENT EVIDENCE:\n" + _text_budget([
        {"source_number": i + 1, "title": hit["title"], "text": hit["text"][:1000]}
        for i, hit in enumerate(hits)], budget // 3)


class ExactMeasuredOllama(primary.MeasuredOllama):
    def __init__(self, settings):
        super().__init__(settings)
        self.context_fits = []
        self.audit_facts = []
        self.expected_initial_evidence = None
        self.before_references = ""

    def chat(self, messages, tools=None):
        self.before_references = reference_text(messages)
        if self.expected_initial_evidence is not None and not self.context_fits:
            actual = [item["content"] for item in messages if item.get("role") == "system"
                      and item.get("content", "").startswith("UNTRUSTED DOCUMENT EVIDENCE:")]
            if actual != [self.expected_initial_evidence]:
                raise RuntimeError("Initial evidence differs from the primary run; diagnostic isolation would be invalid.")
        # This is the only application substitution; it is restored after every call,
        # including failures. Gold labels are used only for subsequent audit metrics.
        with patch("copilot.ollama.fit_context", exact_json_fit):
            return super().chat(messages, tools)

    def _request(self, method, endpoint, payload=None, timeout=180):
        audit = None
        if endpoint == "/api/chat":
            messages, tools = payload["messages"], payload.get("tools")
            schema_cost = len(json.dumps(tools, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) if tools else 0
            cost = sum(message_cost(item) for item in messages) + schema_cost
            assert cost <= input_budget(self.settings.context_size), "Diagnostic violated its serialized context bound"
            retained = reference_text(messages)
            audit = {"input_reference_characters": len(self.before_references),
                     "fitted_reference_characters": len(retained),
                     "fitted_reference_messages": len(reference_messages(messages)),
                     "fitted_serialized_cost": cost, "input_budget": input_budget(self.settings.context_size),
                     "tools_sent": bool(tools),
                     "retained_fact_alias_matches": [primary.match_fact(retained, fact) for fact in self.audit_facts],
                     "fitted_messages": copy.deepcopy(messages)}
            self.context_fits.append(audit)
        count_before = len(self.calls)
        try:
            return super()._request(method, endpoint, payload, timeout)
        finally:
            if audit is not None and len(self.calls) > count_before:
                self.calls[-1]["context_fit"] = audit


def frozen_inputs(primary_run):
    home = HERE / "results" / primary_run
    identity_path = home / "identity.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    dataset = json.loads((HERE / "dataset.json").read_text(encoding="utf-8"))
    if sha256(HERE / "dataset.json") != identity["dataset_sha256"]:
        raise RuntimeError("The corpus dataset differs from the frozen primary run.")
    if sha256(HERE / "run_benchmark.py") != identity["engine_sha256"]:
        raise RuntimeError("The primary benchmark engine differs from its frozen identity.")
    for path, digest in identity["corpus_files_sha256"].items():
        if sha256(HERE / "corpus" / path) != digest:
            raise RuntimeError(f"Frozen corpus file changed: {path}")
    rows = primary.load_jsonl(home / "generation.jsonl")
    if len(rows) != 64 or len({row["id"] for row in rows}) != 32:
        raise RuntimeError("The primary run must contain exactly 32 completed question pairs.")
    if set(Counter(row["id"] for row in rows).values()) != {2}:
        raise RuntimeError("The primary question pairs are incomplete.")
    for identifier in {row["id"] for row in rows}:
        pair = [row for row in rows if row["id"] == identifier]
        if {row["method"] for row in pair} != set(METHODS) or len({row["prompt"] for row in pair}) != 1:
            raise RuntimeError("Primary methods/prompts do not form matching pairs.")
    return identity, dataset, rows, home


def clone_index(source, destination):
    database = destination / "memory.sqlite3"
    marker = destination / "diagnostic-snapshot.json"
    if database.exists():
        if not marker.exists():
            raise RuntimeError("Diagnostic data already exists without snapshot provenance; choose a new run ID.")
        return json.loads(marker.read_text(encoding="utf-8"))
    destination.mkdir(parents=True, exist_ok=True)
    original = source / "memory.sqlite3"
    with sqlite3.connect(original.as_uri() + "?mode=ro", uri=True) as reader, sqlite3.connect(database) as writer:
        reader.backup(writer)
    provenance = {"source_index": str(source), "source_database_sha256": sha256(original),
                  "initial_backup_sha256": sha256(database),
                  "method": "SQLite backup API; primary source database is never written"}
    primary.write_json(marker, provenance)
    return provenance


def aggregate(out):
    rows = primary.load_jsonl(out / "generation.jsonl")
    result = {"description": "Post-hoc context-fitting diagnostic, not independent confirmation.",
              "independent_confirmation": False, "generation": {}}
    for method in METHODS.values():
        selected = [row for row in rows if row["method"] == method]
        positive = [row for row in selected if row["answerable"]]
        negative = [row for row in selected if not row["answerable"]]
        correct = sum(row["scores"]["all_facts_correct"] for row in positive)
        result["generation"][method] = {
            "n": len(selected), "answerable_n": len(positive), "complete_correct": correct,
            "complete_accuracy": correct / len(positive) if positive else None,
            "complete_accuracy_wilson_ci95": primary.wilson(correct, len(positive)),
            "fact_recall": statistics.mean(row["scores"]["fact_recall"] for row in positive) if positive else None,
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
    primary.write_json(out / "summary.json", result)
    return result


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-run", default=DEFAULT_PRIMARY)
    parser.add_argument("--run-id", default=DEFAULT_RUN)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11437")
    parser.add_argument("--runtime-pid", type=int)
    parser.add_argument("--check-only", action="store_true", help="CPU-only invariants; no inference or services")
    parser.add_argument("--aggregate-only", action="store_true", help="Aggregate existing diagnostic rows without inference")
    args = parser.parse_args()
    for value in (args.primary_run, args.run_id):
        if not primary.re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
            raise ValueError("Run IDs may contain only letters, digits, underscores, and hyphens.")
    if args.primary_run == args.run_id:
        raise ValueError("A diagnostic must never use the primary output run ID.")
    checks = invariant_checks()
    if args.check_only:
        print(json.dumps(checks, indent=2, ensure_ascii=False))
        return
    out = HERE / "results" / args.run_id
    if args.aggregate_only:
        print(json.dumps(aggregate(out), indent=2))
        return
    frozen, dataset, replay, parent = frozen_inputs(args.primary_run)
    original_index = primary.ROOT / ".runtime/research/index" / args.primary_run
    diagnostic_index = primary.ROOT / ".runtime/research/context-diagnostic-index" / args.run_id
    snapshot = clone_index(original_index, diagnostic_index)
    if snapshot["source_index"] != str(original_index):
        raise RuntimeError("The diagnostic snapshot belongs to a different primary index.")
    chosen = {item["id"]: item for item in dataset["queries"]}
    original_settings = frozen["settings"]
    settings = Settings(data_dir=diagnostic_index, ollama_url=args.ollama_url,
                        chat_model=original_settings["chat_model"], embedding_model=original_settings["embedding_model"],
                        context_size=original_settings["context_size"])
    store = Store(settings.database_path)
    with store._connection() as connection:
        assert connection.execute("SELECT count(*) FROM messages").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM memories").fetchone()[0] == 0
    model = ExactMeasuredOllama(settings)
    library = Library(settings, store, model.embed)
    agent = Agent(settings, store, library, model)
    import httpx

    with httpx.Client(base_url=args.ollama_url, trust_env=False, timeout=20) as client:
        version = client.get("/api/version").raise_for_status().json()
        tags = client.get("/api/tags").raise_for_status().json()
    current_models = {item["name"]: item["digest"] for item in tags["models"]}
    if any(current_models.get(name) != digest for name, digest in frozen["models"].items()) or version != frozen["ollama"]:
        raise RuntimeError("Model digests or Ollama version differ from the primary run.")
    identity = {
        "description": "Post-hoc mechanism diagnostic after inspecting primary failures; not independent confirmation.",
        "independent_confirmation": False, "primary_identity": frozen,
        "primary_identity_sha256": sha256(parent / "identity.json"),
        "primary_generation_sha256": sha256(parent / "generation.jsonl"),
        "parent_engine_sha256": sha256(HERE / "run_benchmark.py"),
        "diagnostic_engine_sha256": sha256(__file__),
        "released_ollama_module_sha256": sha256(primary.ROOT / "copilot/ollama.py"),
        "released_fitter_source_sha256": hashlib.sha256(inspect.getsource(released_fit_context).encode()).hexdigest(),
        "index_snapshot": snapshot, "settings": settings.public(), "ollama_url": args.ollama_url,
        "models": current_models, "ollama": version, "temperature": 0.25, "seed": None,
        "source_prefix_characters": 1000,
        "selection": "Exact primary generation row prompts and method-pair order; no selection from outcomes or gold labels.",
        "change": "Longest actual-JSON-cost-fitting character prefix; released policy thresholds/order/pinning unchanged.",
        "runtime_pid": args.runtime_pid,
        "replay_order": [{"id": row["id"], "primary_method": row["method"], "method": METHODS[row["method"]],
                          "prompt_sha256": hashlib.sha256(row["prompt"].encode()).hexdigest()} for row in replay],
    }
    out.mkdir(parents=True, exist_ok=True)
    identity_path = out / "identity.json"
    if identity_path.exists():
        if json.loads(identity_path.read_text(encoding="utf-8")) != identity:
            raise RuntimeError("Diagnostic identity changed. Use a new diagnostic run ID; never overwrite previous outputs.")
    elif any(out.iterdir()):
        raise RuntimeError("Output directory contains unverified artifacts. Choose a new diagnostic run ID.")
    else:
        primary.write_json(identity_path, identity)
    primary.write_json(out / "invariant-checks.json", checks)
    primary.write_json(out / "protocol.json", {**identity, "platform": platform.platform(), "python": sys.version,
        "summaries": "Not repeated: the three primary summary tasks remain unchanged and separate.",
        "resource_scope": "Same ResourceMonitor as primary: benchmark/runtime descendants RSS sum and whole-GPU memory, sampled each second.",
        "retained_fact_alias_matches": "Post-selection audit only; gold labels never influence fit_context or evidence ordering."})
    existing = primary.load_jsonl(out / "generation.jsonl")
    planned = [(row["id"], METHODS[row["method"]]) for row in replay]
    completed = [(row["id"], row["method"]) for row in existing]
    if completed != planned[:len(completed)]:
        raise RuntimeError("Existing diagnostic rows do not match the original pair order.")
    monitor = primary.ResourceMonitor(args.runtime_pid)
    monitor.start()
    try:
        if not existing:
            model.expected_initial_evidence = None
            await asyncio.to_thread(model.chat, [{"role": "system", "content": SYSTEM},
                                                {"role": "user", "content": "Reply with the word ready."}])
        for original in replay[len(existing):]:
            question = chosen[original["id"]]
            method = METHODS[original["method"]]
            prompt = original["prompt"]
            expected_hits = original["response"]["sources"][:5]
            model.expected_initial_evidence = evidence_block(expected_hits, settings.context_size)
            model.audit_facts = question["facts"]
            model.calls.clear()
            model.context_fits.clear()
            started = time.perf_counter()
            error = None
            try:
                if original["method"] == "mcp_agent":
                    session = store.create_session("Post-hoc diagnostic " + question["id"])
                    response = await agent.respond(session["id"], prompt)
                else:
                    hits = library.retrieve(prompt, limit=5)
                    if [(hit["chunk_id"], hit["text"]) for hit in hits] != [(hit["chunk_id"], hit["text"]) for hit in expected_hits]:
                        raise RuntimeError("Initial retrieved passages differ from the frozen primary sources.")
                    budget = max(4000, settings.context_size * 2)
                    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt},
                        {"role": "system", "content": "UNTRUSTED PERSONAL AND PROJECT REFERENCE DATA:\n" +
                         _text_budget({"saved_memories": []}, min(1600, budget // 4))},
                        {"role": "system", "content": evidence_block(hits, settings.context_size)}]
                    answer = await asyncio.to_thread(model.chat, messages)
                    response = {"content": answer["content"], "sources": hits, "trace": [], "mode": method}
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                response = {"content": "", "sources": [], "trace": [], "mode": method}
            row = {"id": question["id"], "project": question["project"], "kind": question["kind"],
                   "answerable": question["answerable"], "method": method, "primary_method": original["method"],
                   "prompt": prompt, "post_hoc": True, "independent_confirmation": False,
                   "wall_seconds": time.perf_counter() - started, "model_calls": list(model.calls),
                   "context_fits": list(model.context_fits), "error": error, "response": response,
                   "scores": primary.score_answer(response, question),
                   "extra_tool_calls": sum(item.get("detail") == "Completed locally via MCP" for item in response["trace"])}
            primary.append_jsonl(out / "generation.jsonl", row)
            print("DIAGNOSTIC", question["id"], method, json.dumps(row["scores"]), round(row["wall_seconds"], 2), error, flush=True)
        with store._connection() as connection:
            assert connection.execute("SELECT count(*) FROM messages").fetchone()[0] == 0, "Cross-question conversation leakage"
            assert connection.execute("SELECT count(*) FROM memories").fetchone()[0] == 0, "Unexpected persistent memory write"
    finally:
        monitor.stop()
        timestamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
        primary.write_json(out / f"resources-{timestamp}.json", monitor.rows)
        aggregate(out)


if __name__ == "__main__":
    asyncio.run(main())
