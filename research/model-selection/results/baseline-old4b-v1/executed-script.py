"""Small synthetic development probe: never a paper accuracy benchmark.

Uses the current Agent, MCP server, retrieval and Ollama client unchanged.
Every request goes through a loopback recording proxy to the explicitly named
existing Ollama server. This script never downloads models or changes settings.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
os.environ["TMPDIR"] = str(WORK / "tmp")
Path(os.environ["TMPDIR"]).mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import httpx  # noqa: E402

from copilot.agent import Agent  # noqa: E402
from copilot.config import Settings, local_url  # noqa: E402
from copilot.grounding import citation_numbers, valid_citations  # noqa: E402
from copilot.library import Library  # noqa: E402
from copilot.ollama import Ollama  # noqa: E402
from copilot.store import Store  # noqa: E402


DOCUMENTS = {
    "citrine-decisions.md": (
        "# Citrine Leaf decision record\n\n"
        + "Background discussion is not an adopted decision. Reviewers keep ordinary notes separate. " * 15
        + "\n\nApproved storage profile for Citrine Leaf: Quartz Harbor ledger. "
          "This is the adopted persistence configuration.\n"
          "The internal review date for Citrine Leaf is 18 March 2028.\n"
    ),
    "citrine-operations.md": (
        "# Citrine Leaf operations\n\n"
        "Citrine Leaf backup cadence: every 53 hours. This is the approved interval for saved records.\n"
        "The project coordinator for Citrine Leaf is Mira Sen.\n"
        "Operations notes do not specify a budget or an annual maintenance cost.\n"
    ),
    "citrine-release.md": (
        "# Citrine Leaf controlled release\n\n"
        "The approved rollout codename for Citrine Leaf is Saffron Finch pilot.\n"
        "The pilot accepts 173 records per import batch. Larger batches must be split.\n"
    ),
    "beryl-decisions.md": (
        "# Beryl Meadow\n\nBeryl Meadow is a separate project. Its storage profile is Silver Fern store. "
        "Beryl Meadow backs up every 29 hours and has coordinator Arun Das. "
        "These choices do not apply to Citrine Leaf.\n"
    ),
    "kestrel-summary.md": (
        "# Kestrel Grove project brief\n\n"
        "Kestrel Grove is a fictional offline field-notes project.\n"
        "Its adopted storage profile is Cedar Box profile.\n"
        "Its backup interval is 61 hours.\n"
        "The first review is scheduled for 11 May 2028.\n"
        "The first release supports extracted text; scanned images require a future OCR extension.\n"
    ),
}

CASES = [
    {"id": "P01", "kind": "late_fact", "question": "What approved storage profile does Citrine Leaf use?",
     "expected": ["Quartz Harbor ledger"]},
    {"id": "P02", "kind": "paraphrase", "question": "Which persistence configuration did Citrine Leaf adopt?",
     "expected": ["Quartz Harbor ledger"]},
    {"id": "P03", "kind": "literal", "question": "What is the backup cadence for Citrine Leaf?",
     "expected": ["53 hours"]},
    {"id": "P04", "kind": "paraphrase", "question": "How often should Citrine Leaf make copies of its saved records?",
     "expected": ["53 hours"]},
    {"id": "P05", "kind": "literal", "question": "What rollout codename is approved for Citrine Leaf?",
     "expected": ["Saffron Finch pilot"]},
    {"id": "P06", "kind": "literal", "question": "Who coordinates Citrine Leaf?",
     "expected": ["Mira Sen"]},
    {"id": "P07", "kind": "cross_document", "question": "Give the adopted storage profile and backup interval for Citrine Leaf.",
     "expected": ["Quartz Harbor ledger", "53 hours"]},
    {"id": "P08", "kind": "cross_document", "question": "Give Citrine Leaf's rollout codename and internal review date.",
     "expected": ["Saffron Finch pilot", "18 March 2028"]},
    {"id": "P09", "kind": "unknown", "question": "What is the approved annual maintenance cost for Citrine Leaf?",
     "expected": []},
    {"id": "P10", "kind": "unknown", "question": "What is Citrine Leaf's approved marketing slogan?",
     "expected": []},
]
SUFFIX = " Answer in at most two sentences, using document evidence. If the answer is absent, say exactly: Not in the documents."


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(value):
    return " ".join(re.findall(r"[^\W_]+", value.casefold()))


def score(response, expected):
    """Literal presence only: not a semantic truth or contradiction evaluator."""
    text = response.get("content", "")
    flags = [normalize(value) in normalize(text) for value in expected]
    unknown = not expected
    exact_abstention = normalize(text) == "not in the documents"
    delivered = exact_abstention if unknown else all(flags)
    return {"expected_literals_present": flags, "all_expected_literals_present": all(flags) if expected else None,
            "exact_abstention": exact_abstention, "delivered_literal_check_pass": delivered,
            "generated_literal_check_pass": delivered and response.get("mode") == "agent",
            "numeric_citations": citation_numbers(text),
            "citation_indices_valid": valid_citations(text, len(response.get("sources", []))),
            "warning": "Literal overlap can count contradictory or unsupported wording; inspect raw responses."}


class Recorder:
    def __init__(self, target, path):
        self.target, self.path = target, path
        self.events, self.phase, self.lock = [], "setup", threading.Lock()

    def append(self, event):
        with self.lock:
            self.events.append(event)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")

    def handler(self):
        recorder = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.forward("GET")

            def do_POST(self):
                self.forward("POST")

            def forward(self, method):
                if self.path not in {"/api/tags", "/api/show", "/api/chat", "/api/embed", "/api/ps"}:
                    self.send_error(403, "This recording proxy only permits local read/inference endpoints.")
                    return
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                payload = json.loads(body) if body else None
                phase, started = recorder.phase, time.perf_counter()
                event = {"phase": phase, "started_utc": utc_now(), "method": method,
                         "endpoint": self.path, "payload": payload}
                try:
                    with httpx.Client(base_url=recorder.target, timeout=180, trust_env=False,
                                      follow_redirects=False) as client:
                        result = client.request(method, self.path, json=payload)
                    output, status = result.content, result.status_code
                    value = result.json()
                    if self.path == "/api/chat" and isinstance(value.get("message"), dict):
                        # Final content/tool calls are recorded; hidden reasoning is not persisted.
                        value["message"].pop("thinking", None)
                    event.update(status=status, seconds=time.perf_counter() - started, response=value)
                except Exception as error:
                    status = 502
                    output = json.dumps({"error": str(error)}).encode()
                    event.update(status=status, seconds=time.perf_counter() - started, error=str(error))
                if self.path in {"/api/chat", "/api/embed"}:
                    recorder.append(event)
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(output)))
                self.end_headers()
                self.wfile.write(output)

        return Handler


def snapshot(target):
    with httpx.Client(base_url=target, trust_env=False, timeout=10) as client:
        ps = client.get("/api/ps").json()
    try:
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free",
                              "--format=csv,noheader,nounits"], cwd=WORK, capture_output=True,
                             text=True, timeout=10)
        gpu_data = {"returncode": gpu.returncode, "output": gpu.stdout.strip(), "error": gpu.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        gpu_data = {"error": str(error)}
    return {"utc": utc_now(), "ollama_ps": ps, "gpu": gpu_data}


async def execute(args, directory, recorder, proxy):
    settings = Settings(data_dir=directory / "data", ollama_url=proxy, chat_model=args.model, context_size=8192)
    ollama = Ollama(settings)
    if not ollama.status()["chat_ready"]:
        raise RuntimeError(f"{args.model} is not already installed on {args.ollama_url}; no download was attempted.")
    corpus = WORK / "synthetic-corpus-v1"
    corpus.mkdir(exist_ok=True)
    for filename, text in DOCUMENTS.items():
        path = corpus / filename
        if path.exists() and path.read_text(encoding="utf-8") != text:
            raise RuntimeError("Synthetic protocol/corpus changed; do not compare different cases.")
        path.write_text(text, encoding="utf-8")
    protocol = {"name": "LocalMind small synthetic model development probe v1", "frozen_before_inference": True,
                "purpose": "Model selection development probe; not held-out validation or paper accuracy.",
                "cases": CASES, "question_suffix": SUFFIX, "context_size": 8192,
                "corpus_sha256": {name: digest(corpus / name) for name in DOCUMENTS},
                "summary_expected": ["Cedar Box profile", "61 hours", "11 May 2028"],
                "scoring": "Case-insensitive literal presence; exact unknown abstention; raw answers require review.",
                "source_sha256": {name: digest(ROOT / name) for name in ["copilot/agent.py", "copilot/grounding.py",
                                    "copilot/ollama.py", "copilot/mcp_server.py", "copilot/store.py", "copilot/library.py"]}}
    save_json(directory / "protocol.json", protocol)
    save_json(directory / "before.json", snapshot(args.ollama_url))
    store = Store(settings.database_path)
    library = Library(settings, store, ollama.embed)
    recorder.phase = "index"
    started = time.perf_counter()
    indexing = library.scan(library.add_root(corpus, "Synthetic model probe only")["id"])
    save_json(directory / "index.json", {"seconds": time.perf_counter() - started, "result": indexing})
    save_json(directory / "after-index.json", snapshot(args.ollama_url))
    agent, rows = Agent(settings, store, library, ollama), []
    for case in CASES:
        recorder.phase = case["id"]
        request = case["question"] + SUFFIX
        session = store.create_session(case["id"] + " synthetic probe")
        store.add_message(session["id"], "user", request)
        started, error = time.perf_counter(), None
        try:
            response = await agent.respond(session["id"], request)
        except Exception as exc:
            error, response = str(exc), {"content": "", "sources": [], "mode": "error"}
        seconds = time.perf_counter() - started
        row = {"case": case, "request": request, "seconds": seconds, "error": error,
               "response": response, "scores": score(response, case["expected"]),
               "model_call_count": sum(event["phase"] == case["id"] and event["endpoint"] == "/api/chat"
                                       for event in recorder.events)}
        rows.append(row)
        save_json(directory / f"{case['id']}.json", row)
        print(json.dumps({"case": case["id"], "seconds": round(seconds, 3), "mode": response.get("mode"),
                          "generated_literal_check_pass": row["scores"]["generated_literal_check_pass"], "error": error}), flush=True)
    recorder.phase = "summary"
    summary_document = next(document for document in store.list_documents() if document["title"] == "kestrel-summary.md")
    session = store.create_session("Synthetic short summary")
    request = "Summarize this brief in at most four sentences, preserving the storage profile, backup interval and review date. Cite [1]."
    started, summary_error = time.perf_counter(), None
    try:
        summary_response = await agent.respond(session["id"], request, document_id=summary_document["id"])
    except Exception as exc:
        summary_error, summary_response = str(exc), {"content": "", "sources": [], "mode": "error"}
    summary = {"request": request, "response": summary_response, "seconds": time.perf_counter() - started,
               "error": summary_error, "scores": score(summary_response, protocol["summary_expected"])}
    save_json(directory / "short-summary.json", summary)

    recorder.phase = "native-tool-smoke"
    schema = [{"type": "function", "function": {"name": "find_documents",
              "description": "Find indexed files matching an exact filename. Use this to check whether a named file exists.",
              "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}}]
    started, tool_error = time.perf_counter(), None
    try:
        native = await asyncio.to_thread(ollama.chat, [
            {"role": "system", "content": "Call the available tool to check the exact filename requested by the user. Do not guess whether it exists."},
            {"role": "user", "content": "Check whether the indexed file citrine-decisions.md exists. Use find_documents with the exact filename."}], schema)
    except Exception as exc:
        tool_error, native = str(exc), {}
    calls = native.get("tool_calls", [])
    matched = any(call.get("function", {}).get("name") == "find_documents"
                  and call.get("function", {}).get("arguments", {}).get("name") == "citrine-decisions.md"
                  for call in calls if isinstance(call.get("function", {}).get("arguments", {}), dict))
    smoke = {"seconds": time.perf_counter() - started, "response": native, "error": tool_error,
             "returned_expected_native_tool_call": matched, "note": "Tool selection smoke only; this direct call does not execute the selected tool."}
    save_json(directory / "native-tool-smoke.json", smoke)
    save_json(directory / "after.json", snapshot(args.ollama_url))
    latencies = sorted(row["seconds"] for row in rows)
    result = {"label": protocol["purpose"], "model": args.model, "run_id": args.run_id,
              "completed_utc": utc_now(), "questions": len(rows),
              "answerable_generated_literal_checks": sum(row["scores"]["generated_literal_check_pass"] for row in rows if row["case"]["expected"]),
              "answerable_count": sum(bool(row["case"]["expected"]) for row in rows),
              "unknown_exact_abstentions": sum(row["scores"]["exact_abstention"] for row in rows if not row["case"]["expected"]),
              "unknown_count": sum(not row["case"]["expected"] for row in rows),
              "extractive_fallbacks": sum(row["response"].get("mode") == "extractive" for row in rows),
              "question_errors": sum(row["error"] is not None for row in rows),
              "median_question_seconds": (latencies[4] + latencies[5]) / 2,
              "short_summary_literal_check": summary["scores"]["generated_literal_check_pass"],
              "short_summary_seconds": summary["seconds"], "native_tool_smoke": matched,
              "native_tool_seconds": smoke["seconds"],
              "chat_model_calls": sum(event["endpoint"] == "/api/chat" for event in recorder.events),
              "embedding_model_calls": sum(event["endpoint"] == "/api/embed" for event in recorder.events),
              "warning": "Small development probe with literal scoring, unseeded generation and no semantic judge; not general accuracy."}
    save_json(directory / "summary.json", result)
    print(json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11437")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", args.run_id):
        parser.error("run-id must be a simple unique name")
    args.ollama_url = local_url(args.ollama_url)
    if args.ollama_url.endswith(":11434"):
        parser.error("Use the dedicated runtime, not the normal application's port11434")
    directory = WORK / "runs" / args.run_id
    directory.mkdir(parents=True, exist_ok=False)
    recorder = Recorder(args.ollama_url, directory / "model-calls.jsonl")
    proxy = ThreadingHTTPServer(("127.0.0.1", 0), recorder.handler())
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    save_json(directory / "identity.json", {"model": args.model, "target": args.ollama_url,
              "recording_proxy": f"http://127.0.0.1:{proxy.server_port}", "started_utc": utc_now(),
              "tmpdir": os.environ["TMPDIR"], "script_sha256": digest(Path(__file__))})
    try:
        asyncio.run(execute(args, directory, recorder, f"http://127.0.0.1:{proxy.server_port}"))
    finally:
        proxy.shutdown()
        proxy.server_close()


if __name__ == "__main__":
    main()
