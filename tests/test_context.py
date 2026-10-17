"""Regression checks for evidence retained within the serialized context budget."""

import copy
import json

import pytest

from copilot.agent import SYSTEM
from copilot.config import Settings
from copilot.ollama import Ollama, fit_context

SHORTENED = "\n[Local context shortened.]"
TOOLS = [{"type": "function", "function": {
    "name": "read_document", "description": "Read an approved local document.",
    "parameters": {"type": "object", "properties": {"document_id": {"type": "integer"}},
                   "required": ["document_id"]},
}}]


def serialized_cost(messages, tools=None):
    """Account for the final payload values, including escaping and schema bytes."""
    def encoded(value):
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    return sum(encoded(message) + 24 for message in messages) + (encoded(tools) if tools else 0)


def input_budget(context_size):
    return context_size - min(1536, context_size // 3) - 256


def pinned_messages_leaving(remaining):
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Explain the stored fact. "}]
    padding = input_budget(4096) - serialized_cost(messages) - remaining
    assert padding >= 0
    messages[1]["content"] += "x" * padding
    assert input_budget(4096) - serialized_cost(messages) == remaining
    return messages


@pytest.mark.parametrize("context_size", [4096, 8192, 16384])
@pytest.mark.parametrize("document", [
    json.dumps({"documents": [{"path": r"C:\notes\project.txt", "text": 'A "quoted" fact.\n' * 3000}]}),
    r'C:\notes\project.txt \ "quoted" ' * 3000,
    "line\n\ttab\rcarriage\x00end " * 3000,
    '日本語 नमस्ते 😀 "quoted" \\ ' * 3000,
], ids=["nested-json", "backslashes", "control-characters", "unicode"])
def test_escaped_evidence_survives_with_longest_fitting_prefix(context_size, document):
    evidence = "UNTRUSTED DOCUMENT EVIDENCE:\n" + document
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Give the requested fact and cite its document."},
                {"role": "system", "content": evidence}]
    original, original_tools = copy.deepcopy(messages), copy.deepcopy(TOOLS)

    fitted, schemas = fit_context(messages, TOOLS, context_size)

    assert messages == original and TOOLS == original_tools
    assert fitted[:2] == original[:2]
    assert schemas == TOOLS
    assert len(fitted) == 3, "Escaping must not make the entire evidence block disappear"
    assert serialized_cost(fitted, schemas) <= input_budget(context_size)
    shortened = fitted[2]["content"]
    assert shortened.startswith("UNTRUSTED DOCUMENT EVIDENCE:\n")
    assert shortened.endswith(SHORTENED)
    prefix = shortened[:-len(SHORTENED)]
    assert evidence.startswith(prefix)
    # Adding even one complete Unicode character must exceed the same budget.
    one_more = copy.deepcopy(fitted)
    one_more[2]["content"] = evidence[:len(prefix) + 1] + SHORTENED
    assert serialized_cost(one_more, schemas) > input_budget(context_size)


def test_preferences_and_fresh_tool_result_keep_priority_over_history():
    current_request = {"role": "user", "content": "Which database was selected?"}
    preference = {"role": "system", "content": "UNTRUSTED PERSONAL AND PROJECT REFERENCE DATA: concise answers"}
    fresh_tool = {"role": "tool", "tool_name": "read_document",
                  "content": 'DATABASE: SQLite. ' + r'C:\notes\file "value" ' * 2000}
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Past question " * 2000},
                {"role": "assistant", "content": "Past answer " * 2000},
                current_request,
                {"role": "system", "content": "UNTRUSTED DOCUMENT EVIDENCE:" + "old " * 4000},
                preference, fresh_tool]
    original = copy.deepcopy(messages)

    fitted, schemas = fit_context(messages, TOOLS, 4096)

    assert fitted[0] == original[0]
    assert current_request in fitted and preference in fitted
    retained_tool = next(item for item in fitted if item["role"] == "tool")
    assert retained_tool["tool_name"] == "read_document"
    assert retained_tool["content"].startswith("DATABASE: SQLite.")
    assert retained_tool["content"].endswith(SHORTENED)
    assert serialized_cost(fitted, schemas) <= input_budget(4096)
    assert messages == original


def test_tool_call_metadata_is_kept_whole_or_omitted():
    call = {"role": "assistant", "content": "Read the document.", "tool_calls": [{
        "id": "local-call-1", "type": "function",
        "function": {"name": "read_document", "arguments": {"document_id": 7}},
    }]}
    large_call = {"role": "assistant", "content": "Large request", "tool_calls": [{
        "id": "local-call-2", "type": "function",
        "function": {"name": "knowledge_search", "arguments": {"query": '"\\' * 10000}},
    }]}
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Read document 7."}, call, large_call]
    original = copy.deepcopy(messages)

    fitted, schemas = fit_context(messages, TOOLS, 4096)

    assert call in fitted and large_call not in fitted
    assert [item for item in fitted if item.get("tool_calls")] == [call]
    assert serialized_cost(fitted, schemas) <= input_budget(4096)
    assert messages == original


def test_chat_sends_document_evidence_within_budget(tmp_path, monkeypatch):
    ollama = Ollama(Settings(data_dir=tmp_path, context_size=8192))
    sent = []

    def fake_request(method, endpoint, payload=None, timeout=180):
        if endpoint == "/api/show":
            return {"capabilities": ["completion", "tools"]}
        assert method == "POST" and endpoint == "/api/chat"
        sent.append(copy.deepcopy(payload))
        return {"message": {"role": "assistant", "content": "SQLite [1]."}}

    monkeypatch.setattr(ollama, "_request", fake_request)
    documents = [{"source_number": 1, "title": "Lighthouse project", "text":
                  'The selected database is SQLite. ' + 'A "quoted" fact at C:\\notes\\project.\n' * 1000}]
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Which database does Lighthouse use?"},
                {"role": "system", "content": "UNTRUSTED DOCUMENT EVIDENCE:\n" + json.dumps(documents)}]
    original = copy.deepcopy(messages)

    response = ollama.chat(messages, TOOLS)

    assert response["content"] == "SQLite [1]."
    assert len(sent) == 1
    payload = sent[0]
    references = [item["content"] for item in payload["messages"]
                  if item["content"].startswith("UNTRUSTED DOCUMENT EVIDENCE:")]
    assert len(references) == 1 and "The selected database is SQLite." in references[0]
    assert references[0].endswith(SHORTENED)
    assert payload["tools"] == TOOLS
    assert payload["options"]["num_ctx"] == 8192
    assert serialized_cost(payload["messages"], payload["tools"]) <= input_budget(8192)
    assert messages == original


@pytest.mark.parametrize("remaining", [180, 90])
def test_small_remaining_budget_still_retains_evidence_prefix(remaining):
    evidence = "SQLite. " + '"\\\n' * 1000
    messages = pinned_messages_leaving(remaining) + [{"role": "system", "content": evidence}]
    original = copy.deepcopy(messages)

    fitted, schemas = fit_context(messages, None, 4096)

    assert len(fitted) == 3
    assert fitted[:2] == original[:2]
    assert fitted[2]["content"].startswith("SQLite.")
    assert fitted[2]["content"].endswith(SHORTENED)
    assert serialized_cost(fitted, schemas) <= input_budget(4096)
    prefix = fitted[2]["content"][:-len(SHORTENED)]
    one_more = copy.deepcopy(fitted)
    one_more[2]["content"] = evidence[:len(prefix) + 1] + SHORTENED
    assert serialized_cost(one_more, schemas) > input_budget(4096)
    assert messages == original


def test_oversized_metadata_is_skipped_when_even_marker_cannot_fit():
    unreadable = {"role": "tool", "tool_name": "read_document_" + "x" * 1000,
                  "content": "SQLite. " * 1000}
    small_reference = {"role": "system", "content": "SQLite."}
    messages = pinned_messages_leaving(180) + [unreadable, small_reference]
    original = copy.deepcopy(messages)
    assert serialized_cost([{**unreadable, "content": SHORTENED}]) > 180

    fitted, schemas = fit_context(messages, None, 4096)

    assert unreadable not in fitted
    assert small_reference in fitted
    assert fitted[:2] == original[:2]
    assert serialized_cost(fitted, schemas) <= input_budget(4096)
    assert messages == original


def test_exactly_fitting_evidence_is_unchanged():
    reference = {"role": "system", "content": 'SQLite. "quoted" \\ नमस्ते'}
    messages = pinned_messages_leaving(serialized_cost([reference])) + [reference]
    original = copy.deepcopy(messages)
    assert serialized_cost(messages) == input_budget(4096)

    fitted, schemas = fit_context(messages, None, 4096)

    assert fitted == original and messages == original
    assert schemas is None
