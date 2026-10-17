"""Post-benchmark diagnostic; never changes released app or primary-run results."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from copilot.agent import SYSTEM, _text_budget  # noqa: E402
from copilot.config import Settings  # noqa: E402
from copilot.ollama import Ollama  # noqa: E402


class Capture(Ollama):
    def _request(self, method, endpoint, payload=None, timeout=180):
        if endpoint == "/api/chat":
            self.payload = payload
        body = super()._request(method, endpoint, payload, timeout)
        if endpoint == "/api/chat":
            self.metadata = {k: body.get(k) for k in ("prompt_eval_count", "eval_count", "total_duration")}
        return body


home = Path(__file__).resolve().parent
raw = [json.loads(line) for line in (home / "results/2026-10-17-main-v1/generation.jsonl").read_text().splitlines()]
case = next(r for r in raw if r["id"] == "Q005" and r["method"] == "single_pass_rag")
evidence = "UNTRUSTED DOCUMENT EVIDENCE:\n" + _text_budget([
    {"source_number": i + 1, "title": h["title"], "text": h["text"][:1000]}
    for i, h in enumerate(case["response"]["sources"])], 16384 // 3)
system = {"role": "system", "content": SYSTEM}
user = {"role": "user", "content": case["prompt"]}
reference = {"role": "system", "content": evidence}
variants = {
    "late_system": [system, user, reference],
    "early_system": [system, reference, user],
    "single_system": [{"role": "system", "content": SYSTEM + "\n" + evidence}, user],
    "user_evidence": [system, {"role": "user", "content": evidence + "\n\nCURRENT REQUEST:\n" + case["prompt"]}],
}
model = Capture(Settings(ollama_url="http://127.0.0.1:11437"))
rows = []
for name, messages in variants.items():
    started = time.perf_counter()
    response = model.chat(messages)
    row = {"diagnostic": name, "question_id": "Q005", "answer": response["content"],
           "seconds": time.perf_counter() - started, "metadata": model.metadata,
           "actual_payload": model.payload}
    rows.append(row)
    print(name, response["content"], model.metadata, flush=True)
(home / "results/prompt-diagnostic-20261017.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
