"""Evidence packaging and numeric citation checks without model inference."""
import copy
import json

import pytest

from copilot.grounding import EVIDENCE_PREFIX, citation_numbers, prepare_evidence, valid_citations
from copilot.ollama import fit_context


def base_messages(question="Which storage profile was approved?"):
    return [{"role": "system", "content": "Answer from evidence and cite the source numbers."},
            {"role": "user", "content": question}]


def records(messages):
    evidence = [message["content"] for message in messages
                if message.get("content", "").startswith(EVIDENCE_PREFIX)]
    assert len(evidence) == 1
    return json.loads(evidence[0][len(EVIDENCE_PREFIX):])


def serialized_cost(messages, schemas=None):
    def size(value):
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())
    return sum(size(message) + 24 for message in messages) + (size(schemas) if schemas else 0)


def test_query_relevant_fact_after_prefix_is_sent_with_exact_offsets():
    text = "General introduction. " * 70 + "Approved storage profile: Juniper Vault mode. " + "Appendix. " * 80
    sources = [{"document_id": 7, "title": "decisions.md", "text": text, "start": 800, "end": 9000}]
    messages = base_messages()
    original = copy.deepcopy((messages, sources))

    fitted, schemas, visible = prepare_evidence(messages, sources, messages[-1]["content"], None, 4096)

    packed = records(fitted)
    assert "Juniper Vault mode" in packed[0]["text"]
    assert packed[0]["text"] == visible[0]["text"]
    assert len(visible[0]["text"]) <= 1000
    offset = visible[0]["start"] - 800
    assert visible[0]["text"] == text[offset:offset + len(visible[0]["text"])]
    assert visible[0]["end"] - visible[0]["start"] == len(visible[0]["text"])
    assert (messages, sources) == original
    assert fit_context(fitted, schemas, 4096) == (fitted, schemas)


@pytest.mark.parametrize("context_size", [4096, 8192])
def test_escaping_unicode_and_competing_sources_stay_whole(context_size):
    sources = [{"document_id": i, "title": f'文書{i} "quoted" \\ filename',
                "text": '日本語 नमस्ते 😀 "quoted" \\ \n' * 120 +
                        f"Storage profile {i}: SQLite."} for i in range(1, 6)]
    messages = base_messages("What storage profile uses SQLite?")
    messages.insert(1, {"role": "assistant", "content": "Old irrelevant history. " * 2000})
    schemas = [{"type": "function", "function": {"name": "read_document", "description": "Read locally.",
                "parameters": {"type": "object", "properties": {"document_id": {"type": "integer"}}}}}]

    fitted, fitted_schemas, visible = prepare_evidence(messages, sources, "Storage profile SQLite", schemas, context_size)

    packed = records(fitted)
    assert len(packed) == len(visible) == 5, "Shrink fairly before dropping a source"
    assert [record["source_number"] for record in packed] == list(range(1, 6))
    assert all(record["text"] == source["text"] for record, source in zip(packed, visible))
    assert all(source["text"] in original["text"] for source, original in zip(visible, sources))
    assert all(len(record["text"]) <= 1000 for record in packed)
    assert "[Local context shortened.]" not in json.dumps(packed)
    budget = context_size - min(1536, context_size // 3) - 256
    assert serialized_cost(fitted, fitted_schemas) <= budget
    assert fit_context(fitted, fitted_schemas, context_size) == (fitted, fitted_schemas)


def test_small_remaining_budget_omits_records_instead_of_breaking_json():
    messages = base_messages()
    budget = 4096 - 4096 // 3 - 256
    # Leave enough for one small record but too little for all three.
    messages[1]["content"] += "x" * (budget - serialized_cost(messages) - 300)
    sources = [{"document_id": i, "title": "document.md", "text": "SQLite storage. " * 100}
               for i in range(1, 4)]

    fitted, schemas, visible = prepare_evidence(messages, sources, "SQLite", None, 4096)

    packed = records(fitted)
    assert 0 < len(packed) < len(sources)
    assert len(packed) == len(visible)
    assert [source["source_number"] for source in visible] == list(range(1, len(visible) + 1))
    assert fit_context(fitted, schemas, 4096) == (fitted, schemas)


def test_insufficient_budget_returns_no_visible_sources_or_partial_evidence():
    messages = base_messages()
    budget = 4096 - 4096 // 3 - 256
    messages[1]["content"] += "x" * (budget - serialized_cost(messages) - 80)
    sources = [{"document_id": 1, "title": "notes.md", "text": "SQLite storage."}]

    fitted, schemas, visible = prepare_evidence(messages, sources, "SQLite", None, 4096)

    assert visible == []
    assert not any(message.get("content", "").startswith(EVIDENCE_PREFIX) for message in fitted)
    assert fit_context(fitted, schemas, 4096) == (fitted, schemas)


def test_empty_sources_do_not_invent_references():
    messages = base_messages("Help me plan a small project.")
    fitted, schemas, visible = prepare_evidence(messages, [], messages[-1]["content"], None, 4096)
    assert fitted == messages and schemas is None and visible == []


@pytest.mark.parametrize("text,numbers", [
    ("SQLite [1]. Backups [2, 3].", [1, 2, 3]),
    ("Recorded in [Source: 2, 1] and [Sources: 3].", [2, 1, 3]),
    ("No document citation here.", []),
])
def test_numeric_citation_formats(text, numbers):
    assert citation_numbers(text) == numbers
    assert valid_citations(text, 3)


@pytest.mark.parametrize("text", [
    "Invented source [99].", "Zero source [0].", "Mixed [1, 99].", "Bad [Source: 0].",
    "Unverified range [1-99].", "Descending [3–1].", "Malformed [1, two].",
    "Malformed [Source: unknown].",
])
def test_invalid_citation_bounds_and_syntax(text):
    assert not valid_citations(text, 3)


def test_no_citation_is_distinct_from_invalid_citation():
    assert valid_citations("A proposed project plan without document claims.", 0)
    assert citation_numbers("A proposed project plan without document claims.") == []
    assert not valid_citations("A false reference [1].", 0)


@pytest.mark.parametrize("text", [
    "Read `values[0]` to access the first element.",
    "Read ``values[0] and `literal` rows[99]`` to access elements.",
    "```python\nfirst = values[0]\nlast = rows[99]\n```\nUse their values.",
    "~~~python\nrows[5] = values[0]\n~~~~\nUse their values.",
    "```python\nrows[5] = values[0]\n",  # An unfinished fence still renders as code.
])
def test_code_indexes_are_not_document_citations(text):
    assert citation_numbers(text) == []
    assert valid_citations(text, 0)


def test_real_citations_outside_code_are_still_checked():
    text = "Use `values[0]` [1].\n```python\nrows[99]\n```\nRecorded in [Source: 2]."
    assert citation_numbers(text) == [1, 2]
    assert valid_citations(text, 2)
    assert not valid_citations(text + " Invalid [99].", 2)


def test_unmatched_inline_backtick_does_not_hide_invalid_prose_citation():
    assert citation_numbers("A stray ` token does not hide [99].") == [99]
    assert not valid_citations("A stray ` token does not hide [99].", 1)
