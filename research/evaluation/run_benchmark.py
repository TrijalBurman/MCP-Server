"""Reproduce the paper's synthetic evaluation without changing the application.

Run from the repository root with its virtual-environment Python. A downloaded
local Ollama server must already be listening on --ollama-url. No downloads,
personal files, or hosted inference are used. Raw outputs are retained, including
failures. Generation is not retried or tuned against the reference answers.
"""
# ruff: noqa: E402
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import statistics
import subprocess
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS = Path(__file__).resolve().parent / "corpus"
sys.path.insert(0, str(ROOT))

import numpy as np

from copilot.agent import SYSTEM, Agent, _text_budget
from copilot.config import Settings
from copilot.library import Library
from copilot.ollama import Ollama
from copilot.store import Store


def normalized(value):
    return re.sub(r"[^\w]+", "", value.casefold(), flags=re.UNICODE)


def match_fact(text, fact):
    haystack = normalized(text)
    return any(normalized(alias) in haystack for alias in fact["aliases"])


def evidence_path(path):
    value = Path(path)
    return value.relative_to(CORPUS).as_posix() if value.is_absolute() else value.as_posix()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path, value):
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        handle.flush()


def load_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class MeasuredOllama(Ollama):
    def __init__(self, settings):
        super().__init__(settings)
        self.calls = []

    def _request(self, method, endpoint, payload=None, timeout=180):
        started = time.perf_counter()
        response = {}
        error = None
        try:
            response = super()._request(method, endpoint, payload, timeout)
            return response
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            if endpoint == "/api/chat":
                self.calls.append({
                "wall_seconds": time.perf_counter() - started,
                **{k: response.get(k) for k in ("total_duration", "load_duration", "prompt_eval_count",
                                               "prompt_eval_duration", "eval_count", "eval_duration")},
                "tools_sent": bool(payload.get("tools")), "error": error,
                })


class ResourceMonitor:
    """Whole-device GPU memory and summed RSS for explicitly selected descendants.

    RSS double-counts shared pages; this is an observational upper-sum, not PSS or
    whole-system incremental memory. Other desktop GPU users are included in GPU
    memory. No process command lines are written into the results.
    """
    def __init__(self, runtime_pid=None):
        self.runtime_pid = runtime_pid
        self.stop_event = threading.Event()
        self.rows = []
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=5)

    def _run(self):
        while not self.stop_event.is_set():
            try:
                all_processes = {}
                for item in Path("/proc").iterdir():
                    if not item.name.isdigit():
                        continue
                    try:
                        status = (item / "status").read_text()
                        parent = int(re.search(r"^PPid:\s+(\d+)", status, re.M).group(1))
                        rss = re.search(r"^VmRSS:\s+(\d+)", status, re.M)
                        all_processes[int(item.name)] = (parent, int(rss.group(1)) if rss else 0)
                    except (OSError, AttributeError, ValueError):
                        continue
                wanted = {os.getpid()}
                if self.runtime_pid:
                    wanted.add(self.runtime_pid)
                while True:
                    more = {pid for pid, (parent, _) in all_processes.items() if parent in wanted}
                    if more.issubset(wanted):
                        break
                    wanted |= more
                rss_sum = sum(all_processes.get(pid, (0, 0))[1] for pid in wanted)
                gpu = subprocess.check_output([
                    "nvidia-smi", "--query-gpu=memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits"], text=True, timeout=3).strip().splitlines()[0]
                memory, utilization = [float(x.strip()) for x in gpu.split(",")]
                self.rows.append({"time": time.time(), "rss_sum_mib": rss_sum / 1024,
                                  "gpu_total_used_mib": memory, "gpu_utilization_percent": utilization})
            except (OSError, subprocess.SubprocessError, ValueError):
                pass
            self.stop_event.wait(1)


def stats(values):
    if not values:
        return {}
    return {"n": len(values), "mean": statistics.mean(values), "median": statistics.median(values),
            "p95": float(np.percentile(values, 95)), "min": min(values), "max": max(values)}


def wilson(successes, total):
    if not total:
        return [0, 0]
    z = 1.95996398454
    p = successes / total
    denominator = 1 + z * z / total
    middle = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0, middle - radius), min(1, middle + radius)]


def retrieval_metrics(hits, facts):
    found = []
    for hit in hits:
        path = evidence_path(hit["path"])
        found.append([i for i, fact in enumerate(facts)
                      if evidence_path(fact["document"]) == path and match_fact(hit["text"], fact)])
    output = {}
    for k in (1, 3, 5, 10):
        covered = set(i for row in found[:k] for i in row)
        output[f"recall@{k}"] = len(covered) / len(facts)
        output[f"all_facts@{k}"] = float(len(covered) == len(facts))
    output["mrr@10"] = next((1 / (i + 1) for i, row in enumerate(found) if row), 0)
    return output


def score_answer(response, question):
    text = response["content"]
    matched = [match_fact(text, fact) for fact in question["facts"]]
    citations = [int(x) for group in re.findall(r"\[([\d,\s]+)\]", text) for x in re.findall(r"\d+", group)]
    sources = response.get("sources", [])
    cited_paths = {evidence_path(sources[number - 1]["path"])
                   for number in citations if 1 <= number <= len(sources)}
    gold_paths = {evidence_path(fact["document"]) for fact in question["facts"]}
    return {"facts_matched": matched,
            "fact_recall": sum(matched) / len(matched) if matched else None,
            "all_facts_correct": bool(matched and all(matched)),
            "explicit_abstention": "notinthedocuments" in normalized(text),
            "citation_present": bool(citations),
            "citation_indices_valid": bool(citations and all(1 <= n <= len(sources) for n in citations)),
            "all_gold_documents_cited": bool(gold_paths and gold_paths.issubset(cited_paths))}


def summarize(out, dataset):
    retrieval = load_jsonl(out / "retrieval.jsonl")
    generation = load_jsonl(out / "generation.jsonl")
    summaries = load_jsonl(out / "summaries.jsonl")
    result = {"dataset": dataset["name"], "retrieval": {}, "generation": {}, "summaries": summaries}
    for method in ("lexical", "dense", "hybrid"):
        rows = [r for r in retrieval if r["method"] == method]
        result["retrieval"][method] = {
            "n": len(rows), "metrics": {k: statistics.mean(r["metrics"][k] for r in rows)
                                         for k in rows[0]["metrics"]} if rows else {},
            "ranking_ms": stats([r["ranking_ms"] for r in rows]),
            "by_kind": {kind: {"n": len([r for r in rows if r["kind"] == kind]),
                               "all_facts@5": statistics.mean(r["metrics"]["all_facts@5"]
                                                             for r in rows if r["kind"] == kind)}
                        for kind in sorted({r["kind"] for r in rows})}}
        # Resample projects, not the correlated questions within a project.
        grouped = defaultdict(list)
        for row in rows:
            grouped[row["project"]].append(row["metrics"]["all_facts@5"])
        groups = list(grouped.values())
        if groups:
            rng = np.random.default_rng(20261017)
            means = [np.mean([v for index in rng.integers(0, len(groups), len(groups))
                              for v in groups[index]]) for _ in range(2000)]
            result["retrieval"][method]["all_facts@5_cluster_bootstrap_ci95"] = np.percentile(means, [2.5, 97.5]).tolist()
    for method in ("single_pass_rag", "mcp_agent"):
        rows = [r for r in generation if r["method"] == method]
        positives = [r for r in rows if r["answerable"]]
        negatives = [r for r in rows if not r["answerable"]]
        success = sum(r["scores"]["all_facts_correct"] for r in positives)
        result["generation"][method] = {
            "answerable_n": len(positives), "complete_correct": success,
            "complete_accuracy": success / len(positives) if positives else None,
            "complete_accuracy_wilson_ci95": wilson(success, len(positives)),
            "fact_recall": statistics.mean(r["scores"]["fact_recall"] for r in positives) if positives else None,
            "negative_n": len(negatives), "explicit_abstention_n": sum(r["scores"]["explicit_abstention"] for r in negatives),
            "all_gold_documents_cited_n": sum(r["scores"]["all_gold_documents_cited"] for r in positives),
            "all_citation_indices_valid_n": sum(r["scores"]["citation_indices_valid"] for r in positives),
            "wall_seconds": stats([r["wall_seconds"] for r in rows]),
            "model_calls": stats([len(r["model_calls"]) for r in rows]),
            "extra_tool_calls_n": sum(r.get("extra_tool_calls", 0) for r in rows),
            "errors_n": sum(bool(r.get("error")) for r in rows),
            "by_kind": {kind: {"n": len([r for r in positives if r["kind"] == kind]),
                               "complete_correct": sum(r["scores"]["all_facts_correct"] for r in positives if r["kind"] == kind)}
                        for kind in sorted({r["kind"] for r in positives})}}
        if positives:
            grouped = defaultdict(list)
            for row in positives:
                grouped[row["project"]].append(float(row["scores"]["all_facts_correct"]))
            groups = list(grouped.values())
            rng = np.random.default_rng(20261017)
            means = [np.mean([v for index in rng.integers(0, len(groups), len(groups))
                              for v in groups[index]]) for _ in range(2000)]
            result["generation"][method]["complete_accuracy_cluster_bootstrap_ci95"] = np.percentile(means, [2.5, 97.5]).tolist()
    write_json(out / "summary.json", result)
    return result


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11437")
    parser.add_argument("--runtime-pid", type=int, help="PID of this experiment's Ollama server, for RSS attribution")
    parser.add_argument("--run-id", default="2026-10-17-main-v1", help="Fresh name for a scientifically distinct run")
    parser.add_argument("--phase", choices=["all", "retrieval", "generation", "summary", "aggregate"], default="all")
    args = parser.parse_args()
    home = Path(__file__).resolve().parent
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.run_id):
        raise ValueError("Use a simple run ID containing only letters, digits, underscores, or hyphens.")
    out = home / "results" / args.run_id
    out.mkdir(parents=True, exist_ok=True)
    dataset_path = home / "dataset.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    if args.phase == "aggregate":
        print(json.dumps(summarize(out, dataset), indent=2))
        return
    settings = Settings(data_dir=ROOT / ".runtime/research/index" / args.run_id, ollama_url=args.ollama_url)
    store = Store(settings.database_path)
    model = MeasuredOllama(settings)
    library = Library(settings, store, model.embed)
    status = model.status()
    if not status["chat_ready"] or not status["embedding_ready"]:
        raise RuntimeError(f"Both downloaded local models are required: {status}")
    import httpx
    with httpx.Client(base_url=args.ollama_url, trust_env=False, timeout=20) as client:
        tags = client.get("/api/tags").json()
        version = client.get("/api/version").json()
    corpus_files = {d["path"]: hashlib.sha256((home / "corpus" / d["path"]).read_bytes()).hexdigest()
                    for d in dataset["documents"]}
    identity = {"dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
                "engine_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "corpus_files_sha256": corpus_files,
                "models": {m["name"]: m["digest"] for m in tags["models"]},
                "ollama": version, "settings": settings.public(),
                "temperature": 0.25, "seed": None, "qa_selection": "rotating pairs (0,4),(4,7),(0,7)"}
    identity_path = out / "identity.json"
    if identity_path.exists():
        if json.loads(identity_path.read_text(encoding="utf-8")) != identity:
            raise RuntimeError("Run identity changed. Use a NEW --run-id; earlier outputs must remain separate.")
    elif any(out.iterdir()):
        raise RuntimeError("Existing outputs have no verified identity. Use a NEW --run-id.")
    else:
        write_json(identity_path, identity)
    protocol = {"corpus_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
                "engine_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "date_local": "2026-10-17", "phase": args.phase,
                "linux_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "platform": platform.platform(), "python": sys.version, "settings": settings.public(),
                "ollama": version, "models": tags, "temperature": 0.25, "seed": "not fixed (production default)",
                "packages": {p: importlib.metadata.version(p) for p in ("numpy", "mcp", "fastapi", "httpx", "pypdf")},
                "definition": "Frozen synthetic templates; no prompt tuning, no output selection, no model training.",
                "retrieval_candidates_per_list": 60, "retrieval_saved_top_k": 10,
                "resource_runtime_pid": args.runtime_pid,
                "rss_scope": "Benchmark plus specified runtime PID and their descendants; shared pages can be double-counted",
                "qa_selection": "Two queries/project with rotating pairs (0,4), (4,7), (0,7), plus all 8 unanswerables.",
                "qa_prompt_suffix": "Answer in at most two sentences, using local document evidence. If the answer is absent, say: Not in the documents."}
    write_json(out / ("protocol-" + args.phase + ".json"), protocol)
    monitor = ResourceMonitor(args.runtime_pid)
    monitor.start()
    try:
        if args.phase in {"all", "retrieval"}:
            root = library.add_root(home / "corpus", "LM-Synth v1 (synthetic research corpus)")
            started = time.perf_counter()
            indexed = library.scan(root["id"])
            write_json(out / "index.json", {"result": indexed, "wall_seconds": time.perf_counter() - started,
                                            "counts": store.stats()})
            print("INDEX", json.dumps(indexed), flush=True)
            if indexed.get("errors") or indexed.get("embedding_warning"):
                raise RuntimeError(f"Corpus indexing/embedding failed: {indexed}")
            with store._connection() as db:
                vectors = [(row["id"], np.frombuffer(row["embedding"], dtype="<f4").copy())
                           for row in db.execute("SELECT id,embedding FROM chunks WHERE embedding IS NOT NULL "
                                                 "AND embedding_model=? ORDER BY id", (settings.embedding_model,))]
                all_hits = {row["chunk_id"]: dict(row) for row in db.execute(
                    "SELECT c.id AS chunk_id,c.text,c.start,c.end,c.page,d.id AS document_id,d.title,d.path "
                    "FROM chunks c JOIN documents d ON d.id=c.document_id")}
            matrix = np.stack([v for _, v in vectors])
            if (len(vectors) != len(all_hits) or matrix.shape[1] != 768 or not np.isfinite(matrix).all()
                    or not (np.linalg.norm(matrix, axis=1) > 0).all()):
                raise RuntimeError("All indexed chunks must have valid, model-compatible 768-dimensional vectors.")
            matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
            done = {(r["id"], r["method"]) for r in load_jsonl(out / "retrieval.jsonl")}
            embed_rows = []
            for question in [q for q in dataset["queries"] if q["answerable"]]:
                started = time.perf_counter()
                vector = np.asarray(model.embed([question["query"]])[0], dtype=np.float32)
                embedding_ms = (time.perf_counter() - started) * 1000
                embed_rows.append({"id": question["id"], "embedding_ms": embedding_ms})
                for method in ("lexical", "dense", "hybrid"):
                    if (question["id"], method) in done:
                        continue
                    started = time.perf_counter()
                    if method == "dense":
                        similarity = matrix @ (vector / np.linalg.norm(vector))
                        order = sorted(range(len(vectors)), key=lambda i: (-float(similarity[i]), -vectors[i][0]))
                        hits = [all_hits[vectors[i][0]] for i in order[:10] if similarity[i] > 0]
                    else:
                        hits = store.search(question["query"], limit=15,
                                            query_embedding=vector if method == "hybrid" else None,
                                            embedding_model=settings.embedding_model if method == "hybrid" else "")[:10]
                    ranking_ms = (time.perf_counter() - started) * 1000
                    row = {"id": question["id"], "project": question["project"], "kind": question["kind"],
                           "method": method, "embedding_ms": embedding_ms, "ranking_ms": ranking_ms,
                           "metrics": retrieval_metrics(hits, question["facts"]),
                           "hits": [{"chunk_id": h["chunk_id"], "document": evidence_path(h["path"]),
                                     "start": h["start"], "end": h["end"], "text": h["text"]} for h in hits]}
                    append_jsonl(out / "retrieval.jsonl", row)
                print("RETRIEVAL", question["id"], flush=True)
            write_json(out / "query-embedding-times.json", embed_rows)
        if args.phase in {"all", "generation"}:
            # Warm-up is explicitly excluded; no answer-bearing evaluation facts.
            await asyncio.to_thread(model.chat, [{"role": "system", "content": SYSTEM},
                                                {"role": "user", "content": "Reply with the word ready."}])
            projects = list(dict.fromkeys(q["project"] for q in dataset["queries"] if q["answerable"]))
            chosen = []
            for i, project in enumerate(projects):
                questions = [q for q in dataset["queries"] if q["answerable"] and q["project"] == project]
                chosen.extend(questions[n] for n in ((0, 4), (4, 7), (0, 7))[i % 3])
            chosen.extend(q for q in dataset["queries"] if not q["answerable"])
            done = {(r["id"], r["method"]) for r in load_jsonl(out / "generation.jsonl")}
            agent = Agent(settings, store, library, model)
            for question in chosen:
                methods = ("single_pass_rag", "mcp_agent")
                if int(hashlib.sha256(question["id"].encode()).hexdigest(), 16) % 2:
                    methods = tuple(reversed(methods))
                for method in methods:
                    if (question["id"], method) in done:
                        continue
                    prompt = question["query"] + " " + protocol["qa_prompt_suffix"]
                    model.calls.clear()
                    started = time.perf_counter()
                    error = None
                    try:
                        if method == "mcp_agent":
                            session = store.create_session("Synthetic benchmark " + question["id"])
                            response = await agent.respond(session["id"], prompt)
                        else:
                            hits = library.retrieve(prompt, limit=5)
                            budget = max(4000, settings.context_size * 2)
                            messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt},
                                {"role": "system", "content": "UNTRUSTED PERSONAL AND PROJECT REFERENCE DATA:\n" +
                                 _text_budget({"saved_memories": []}, min(1600, budget // 4))},
                                {"role": "system", "content": "UNTRUSTED DOCUMENT EVIDENCE:\n" + _text_budget([
                                    {"source_number": i + 1, "title": h["title"], "text": h["text"][:1000]}
                                    for i, h in enumerate(hits)], budget // 3)}]
                            answer = await asyncio.to_thread(model.chat, messages)
                            response = {"content": answer["content"], "sources": hits, "trace": [], "mode": "single_pass_rag"}
                    except Exception as exc:
                        error = f"{type(exc).__name__}: {exc}"
                        response = {"content": "", "sources": [], "trace": [], "mode": method}
                    row = {"id": question["id"], "project": question["project"], "kind": question["kind"],
                           "answerable": question["answerable"], "method": method, "prompt": prompt,
                           "wall_seconds": time.perf_counter() - started, "model_calls": list(model.calls),
                           "error": error, "response": response, "scores": score_answer(response, question),
                           "extra_tool_calls": sum(t.get("detail") == "Completed locally via MCP" for t in response["trace"])}
                    append_jsonl(out / "generation.jsonl", row)
                    print("GENERATION", question["id"], method, json.dumps(row["scores"]), round(row["wall_seconds"], 2), error, flush=True)
            with store._connection() as db:
                assert db.execute("SELECT count(*) FROM messages").fetchone()[0] == 0, "Cross-query conversation leakage"
                assert db.execute("SELECT count(*) FROM memories").fetchone()[0] == 0, "Unexpected persistent memory write"
        if args.phase in {"all", "summary"}:
            agent = Agent(settings, store, library, model)
            done = {row["id"] for row in load_jsonl(out / "summaries.jsonl")}
            documents = {evidence_path(d["path"]): d for d in store.list_documents(limit=500)}
            for item in dataset["summaries"]:
                if item["id"] in done:
                    continue
                document = documents[evidence_path(item["document"])]
                model.calls.clear()
                started = time.perf_counter()
                session = store.create_session("Synthetic summary " + item["id"])
                error = None
                try:
                    response = await agent.respond(session["id"], item["request"], document_id=document["id"])
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    response = {"content": "", "sources": [], "trace": [], "mode": "agent"}
                full = store.get_document(document["id"])
                read_parts = [t for t in response["trace"] if t["detail"].startswith("Read extracted section")]
                expected_sections = math.ceil(len(full["text"]) / min(4000, settings.context_size - 3200))
                row = {"id": item["id"], "document": item["document"], "wall_seconds": time.perf_counter() - started,
                       "characters": len(full["text"]), "expected_sections": expected_sections,
                       "sections_processed": len(read_parts), "model_calls": list(model.calls),
                       "fact_matches": [match_fact(response["content"], fact) for fact in item["facts"]],
                       "response": response, "error": error}
                append_jsonl(out / "summaries.jsonl", row)
                print("SUMMARY", item["id"], row["fact_matches"], round(row["wall_seconds"], 2), flush=True)
    finally:
        monitor.stop()
        write_json(out / ("resources-" + args.phase + ".json"), monitor.rows)
        summarize(out, dataset)


if __name__ == "__main__":
    asyncio.run(main())
