"""Ollama inference over loopback only. No cloud fallback or proxy use."""
from __future__ import annotations

import json
import re

import httpx

from .config import Settings, local_model, local_url


class OllamaUnavailable(RuntimeError):
    pass


def _clip_bytes(text: str, budget: int) -> str:
    return text.encode("utf-8")[:max(0, budget)].decode("utf-8", errors="ignore")


def fit_context(messages: list[dict], tools: list[dict] | None, context_size: int):
    """Use a conservative byte bound, keeping safety instructions and the current request.

    Byte length is an upper bound for ordinary byte-level tokenizer tokens. Reserve
    generation and protocol framing space, and include tool schemas in the bound.
    Old history is dropped first; reference/tool data may be shortened explicitly.
    """
    reserve = min(1536, context_size // 3)
    budget = context_size - reserve - 256
    first = dict(messages[0])
    latest_user = max((i for i, m in enumerate(messages) if m["role"] == "user"), default=-1)
    pinned = {0}
    if latest_user >= 0:
        pinned.add(latest_user)
    def cost(item):
        return len(json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode()) + 24
    fixed = sum(cost(messages[i]) for i in pinned)
    if fixed > budget:
        raise ValueError("This request is too long for the selected local context. Shorten it or increase the context size in Settings.")
    schema_cost = len(json.dumps(tools, ensure_ascii=False, separators=(",", ":")).encode()) if tools else 0
    if schema_cost + fixed + 500 > budget:
        tools, schema_cost = None, 0
    available = budget - fixed - schema_cost
    selected = {i: dict(messages[i]) for i in pinned}
    # Project/preferences are kept ahead of optional evidence and old history.
    personal = [i for i, m in enumerate(messages) if i not in pinned and m["role"] == "system"
                and m.get("content", "").startswith(("UNTRUSTED PERSONAL AND PROJECT", "UNTRUSTED PROJECT REFERENCE"))]
    fresh_tools = [i for i in reversed(range(len(messages))) if messages[i]["role"] == "tool"]
    priorities = personal + fresh_tools
    priorities += [i for i, m in enumerate(messages) if i not in pinned and i not in priorities and m["role"] == "system"]
    priorities += [i for i in reversed(range(len(messages))) if i not in pinned and i not in priorities]
    for i in priorities:
        item = dict(messages[i])
        if available <= 100:
            break
        if cost(item) > available:
            if item.get("tool_calls"):
                continue
            limit = available - 120
            if limit < 100:
                continue
            item["content"] = _clip_bytes(item.get("content", ""), limit) + "\n[Local context shortened.]"
        amount = cost(item)
        if amount <= available:
            selected[i] = item
            available -= amount
    selected[0] = first
    return [selected[i] for i in sorted(selected)], tools


class Ollama:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _request(self, method: str, endpoint: str, payload=None, timeout=180) -> dict:
        try:
            with httpx.Client(base_url=local_url(self.settings.ollama_url), timeout=timeout,
                              trust_env=False, follow_redirects=False) as client:
                result = client.request(method, endpoint, json=payload)
                result.raise_for_status()
                body = result.json()
                if body.get("error"):
                    raise OllamaUnavailable(body["error"])
                return body
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaUnavailable(f"Local Ollama is unavailable: {exc}") from exc

    def status(self) -> dict:
        try:
            models = self._request("GET", "/api/tags", timeout=2).get("models", [])
            names = [m["name"] for m in models if "cloud" not in m["name"].lower()
                     and not m.get("remote_host")]
            def present(name):
                return name in names or (":" not in name and name + ":latest" in names)
            return {"online": True, "models": names, "chat_ready": present(self.settings.chat_model),
                    "embedding_ready": present(self.settings.embedding_model)}
        except OllamaUnavailable as exc:
            return {"online": False, "models": [], "chat_ready": False, "embedding_ready": False,
                    "error": str(exc)}

    def _check_local(self, model: str):
        local_model(model)
        details = self._request("POST", "/api/show", {"model": model}, timeout=10)
        if details.get("remote_host") or details.get("remote_model"):
            raise OllamaUnavailable("Remote model inference is disabled. Choose a downloaded local model.")
        return details

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._check_local(self.settings.embedding_model)
        result = self._request("POST", "/api/embed", {
            "model": self.settings.embedding_model, "input": texts, "truncate": False,
            "keep_alive": "10m"})
        return result["embeddings"]

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        details = self._check_local(self.settings.chat_model)
        messages, tools = fit_context(messages, tools, self.settings.context_size)
        payload = {"model": self.settings.chat_model, "messages": messages, "stream": False,
                   "keep_alive": "10m",
                   "options": {"num_ctx": self.settings.context_size, "temperature": 0.25,
                               "num_predict": min(1536, self.settings.context_size // 3)}}
        if tools:
            payload["tools"] = tools
        if "thinking" in (details or {}).get("capabilities", []):
            payload["think"] = False
        message = self._request("POST", "/api/chat", payload)["message"]
        content = message.get("content", "")
        # Some locally installed model templates put a thinking block in content.
        # Keep only their final answer; do not store or render scratch reasoning.
        if "</think>" in content:
            content = content.rsplit("</think>", 1)[1]
        else:
            content = re.sub(r"<think>.*", "", content, flags=re.DOTALL)
        message["content"] = content.strip()
        message.pop("thinking", None)
        return message
