"""Real-MCP regressions for evidence packing and answer reference checks.

Inference is scripted at the HTTP transport boundary. The tests still exercise
the production Ollama request fitter and parse the payload it would send.
Citation checks establish reference integrity, not semantic entailment.
"""

import copy
import json
from types import SimpleNamespace

import pytest

from copilot.agent import Agent, _catalog_request
from copilot.config import Settings
from copilot.grounding import EVIDENCE_PREFIX
from copilot.library import Library
from copilot.ollama import Ollama, OllamaUnavailable, fit_context
from copilot.store import Store


class ScriptedOllama(Ollama):
    def __init__(self, settings, responses):
        super().__init__(settings)
        self.responses = iter(responses)
        self.sent = []

    def status(self):
        return {"chat_ready": True}

    def _request(self, method, endpoint, payload=None, timeout=180):
        if endpoint == "/api/show":
            return {"capabilities": ["completion", "tools"]}
        assert method == "POST" and endpoint == "/api/chat"
        self.sent.append(copy.deepcopy(payload))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        if callable(response):
            response = response(payload)
        return {"message": {"role": "assistant", **response}}


@pytest.fixture
def knowledge(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", ollama_url="http://127.0.0.1:9")
    store = Store(settings.database_path)
    folder = tmp_path / "knowledge"
    folder.mkdir()
    root = store.add_root(folder)
    session = store.create_session("Grounding regression")
    return SimpleNamespace(settings=settings, store=store, folder=folder, root=root,
                           session=session, library=Library(settings, store))


def add_document(knowledge, filename, text, chunks=None):
    path = knowledge.folder / filename
    path.write_text(text, encoding="utf-8")
    stat = path.stat()
    if chunks is None:
        chunks = [{"text": text, "start": 0, "end": len(text), "page": None}]
    return knowledge.store.upsert_document(knowledge.root["id"], path, path.name, text,
                                           stat.st_mtime_ns, stat.st_size, chunks)


async def ask(knowledge, question, responses):
    model = ScriptedOllama(knowledge.settings, responses)
    knowledge.store.add_message(knowledge.session["id"], "user", question)
    answer = await Agent(knowledge.settings, knowledge.store, knowledge.library, model).respond(
        knowledge.session["id"], question)
    return answer, model


def document_records(payload):
    evidence = [message["content"] for message in payload["messages"]
                if message.get("content", "").startswith(EVIDENCE_PREFIX)]
    assert len(evidence) == 1, "Each round needs one complete, refreshed evidence block"
    records = json.loads(evidence[0][len(EVIDENCE_PREFIX):])
    assert isinstance(records, list) and records
    core = {"source_number", "title", "text"}
    allowed = core | {"document_id", "path"}
    assert all(core <= set(record) <= allowed for record in records)
    assert [record["source_number"] for record in records] == list(range(1, len(records) + 1))
    fitted, schemas = fit_context(payload["messages"], payload.get("tools"), payload["options"]["num_ctx"])
    assert fitted == payload["messages"], "Packed evidence must survive the actual inference fitter intact"
    assert schemas == payload.get("tools")
    return records


def assert_sources_match_payload(knowledge, answer, payload):
    records = document_records(payload)
    sources = answer["sources"]
    assert len(sources) == len(records)
    for source, record in zip(sources, records, strict=True):
        assert {key: source[key] for key in record} == record
        assert record["document_id"] == source["document_id"]
        assert record["path"] == source["path"]
        document = knowledge.store.get_document(source["document_id"])
        assert source["path"] == document["path"]
        assert document["text"][source["start"]:source["end"]] == source["text"]
    return records


@pytest.mark.parametrize("context_size", [4096, 8192])
async def test_relevant_fact_after_old_prefix_limit_reaches_actual_fitted_request(knowledge, context_size):
    knowledge.settings.context_size = context_size
    fact = "Silverpine storage protocol is SQLite WAL."
    text = ('Routine "quoted" background \\ ' * 55) + fact + (" More background." * 80)
    assert text.index(fact) > 1000
    add_document(knowledge, "silverpine.md", text)

    def answer_from_supplied_evidence(payload):
        records = document_records(payload)
        assert any(fact in record["text"] for record in records)
        return {"content": "Silverpine uses SQLite WAL [1]."}

    answer, model = await ask(knowledge, "Which storage protocol does Silverpine use?",
                              [answer_from_supplied_evidence])
    assert answer["mode"] == "agent"
    assert len(model.sent) == 1
    records = assert_sources_match_payload(knowledge, answer, model.sent[0])
    assert fact in records[0]["text"]


@pytest.mark.parametrize("generated", [
    "Aurora uses the ImaginaryCloud service [99].",
    "Aurora uses the ImaginaryCloud service [0].",
    "Aurora uses the ImaginaryCloud service.",
])
async def test_invalid_or_absent_document_citations_return_exact_excerpts(knowledge, generated):
    text = "Aurora uses SQLite for its local database."
    add_document(knowledge, "aurora.md", text)
    responses = [{"content": generated}]
    if "[" not in generated:
        responses.append({"content": "The retry is still missing a document reference."})
    answer, model = await ask(knowledge, "Which database does Aurora use?", responses)
    assert answer["mode"] == "extractive"
    assert len(model.sent) == len(responses)
    assert "ImaginaryCloud" not in answer["content"]
    assert any(step["tool"] == "grounding_check" for step in answer["trace"])
    records = assert_sources_match_payload(knowledge, answer, model.sent[0])
    for record in records:
        assert record["text"] in answer["content"]


async def test_fabricated_document_answer_without_any_evidence_is_rejected(knowledge):
    answer, model = await ask(knowledge, "According to my documents, what is Nebula's launch date?", [
        {"content": "Nebula launches on 31 February 2040."},
    ])
    assert answer["mode"] == "extractive"
    assert len(model.sent) == 1
    assert answer["sources"] == []
    assert "31 February" not in answer["content"]
    assert any(step["tool"] == "grounding_check" for step in answer["trace"])
    assert not any(message.get("content", "").startswith(EVIDENCE_PREFIX)
                   for message in model.sent[0]["messages"])


async def test_empty_conversation_search_does_not_bypass_document_reference_guard(knowledge):
    add_document(knowledge, "aurora.md", "Aurora uses SQLite for its local database.")

    def fabricated_followup(payload):
        replies = [json.loads(message["content"]) for message in payload["messages"]
                   if message.get("tool_name") == "search_conversations"]
        assert replies == [{"messages": []}]
        return {"content": "We decided Aurora uses ImaginaryCloud."}

    answer, model = await ask(knowledge, "What did we decide about Aurora's database?", [
        {"content": "", "tool_calls": [{"function": {"name": "search_conversations", "arguments": {
            "query": "absentconversationtokenxyz"}}}]},
        fabricated_followup,
        {"content": "We still chose ImaginaryCloud without a reference."},
    ])
    assert len(model.sent) == 3
    assert answer["mode"] == "extractive"
    assert "ImaginaryCloud" not in answer["content"]
    assert {step["tool"] for step in answer["trace"]} >= {"search_conversations", "grounding_check"}
    assert_sources_match_payload(knowledge, answer, model.sent[1])


async def test_another_search_refreshes_complete_numbered_records_and_visible_sources(knowledge):
    # Exercise refresh rather than budget starvation with longer Windows temp paths.
    knowledge.settings.context_size = 12288
    first = add_document(knowledge, "aurora.md", "Aurora database uses SQLite.")
    second = add_document(knowledge, "cobalt.md", "Cobalt ledger: HarborBridge.")

    def answer_after_search(payload):
        records = document_records(payload)
        assert len(records) == 2
        assert {record["title"] for record in records} == {"aurora.md", "cobalt.md"}
        assert any("HarborBridge" in record["text"] for record in records)
        return {"content": "Aurora uses SQLite [1]. Cobalt records HarborBridge [2]."}

    answer, model = await ask(knowledge, "Which database does Aurora use?", [
        {"content": "", "tool_calls": [{"function": {"name": "knowledge_search", "arguments": {
            "query": "Cobalt", "limit": 3}}}]},
        answer_after_search,
    ])
    assert len(document_records(model.sent[0])) == 1
    assert answer["mode"] == "agent"
    assert {source["document_id"] for source in answer["sources"]} == {first["id"], second["id"]}
    assert_sources_match_payload(knowledge, answer, model.sent[-1])


async def test_document_read_replaces_prefix_with_relevant_complete_record(knowledge):
    prefix = "Brief overview. " + ("Routine context. " * 125)
    fact = "Aurora database selection is SQLite WAL."
    text = prefix + fact + (" More details." * 80)
    document = add_document(knowledge, "aurora.md", text, [
        {"text": prefix, "start": 0, "end": len(prefix), "page": None},
    ])

    def answer_after_read(payload):
        records = document_records(payload)
        assert len(records) == 1
        assert fact in records[0]["text"]
        return {"content": "Aurora selected SQLite WAL [1]."}

    answer, model = await ask(knowledge, "Which database does Aurora use?", [
        {"content": "", "tool_calls": [{"function": {"name": "read_document", "arguments": {
            "document_id": document["id"], "offset": 0, "length": 5000}}}]},
        answer_after_read,
    ])
    assert fact not in json.dumps(document_records(model.sent[0]))
    assert answer["mode"] == "agent"
    assert any(step["tool"] == "read_document" for step in answer["trace"])
    records = assert_sources_match_payload(knowledge, answer, model.sent[-1])
    assert fact in records[0]["text"]


async def test_old_generated_claims_are_removed_when_fresh_document_evidence_exists(knowledge):
    add_document(knowledge, "aurora.md", "Aurora uses SQLite for its local database.")
    knowledge.store.add_message(knowledge.session["id"], "user", "What did you find for Aurora?")
    knowledge.store.add_message(knowledge.session["id"], "assistant", "Aurora uses ImaginaryCloud [1].")

    def answer_current_evidence(payload):
        assert "ImaginaryCloud" not in json.dumps(payload["messages"])
        assert any("What did you find" in message.get("content", "") for message in payload["messages"])
        return {"content": "Aurora uses SQLite [1]."}

    answer, model = await ask(knowledge, "Which database does Aurora use?", [answer_current_evidence])
    assert answer["mode"] == "agent"
    assert_sources_match_payload(knowledge, answer, model.sent[0])


def add_large_source_pool(knowledge):
    """Tool schemas constrain the initial excerpts; a tool-free retry has more room."""
    knowledge.settings.context_size = 8192
    documents = []
    for number in range(5):
        text = ((f"Routine material from section {number}. " * 65)
                + f"Aurora database choice in record {number} is SQLite WAL. "
                + (f"Further background from section {number}. " * 65))
        documents.append(add_document(knowledge, f"aurora-{number}.md", text))
    return documents


def assert_clean_retry(payload, draft):
    assert "tools" not in payload, "The citation repair must have no tool schemas"
    assert all(message["role"] in {"system", "user"} for message in payload["messages"])
    assert not any("tool_calls" in message or "tool_name" in message for message in payload["messages"])
    assert draft not in json.dumps(payload["messages"]), "Do not recirculate the uncited answer"
    return document_records(payload)


async def test_uncited_answer_retry_repacks_original_sources_and_returns_matching_cards(knowledge):
    documents = add_large_source_pool(knowledge)
    draft = "UNCITED_DRAFT: Aurora database is SQLite WAL."

    def repaired_answer(payload):
        records = assert_clean_retry(payload, draft)
        assert len(records) == len(documents)
        assert all("SQLite WAL" in record["text"] for record in records)
        return {"content": "Aurora uses SQLite WAL [1, 2, 3, 4, 5]."}

    answer, model = await ask(knowledge, "Which database does Aurora use?", [
        {"content": draft}, repaired_answer,
    ])
    assert len(model.sent) == 2, "At most one citation repair call is allowed"
    assert answer["mode"] == "agent"
    assert {source["document_id"] for source in answer["sources"]} == {doc["id"] for doc in documents}
    original = document_records(model.sent[0])
    retry = assert_sources_match_payload(knowledge, answer, model.sent[1])
    assert sum(len(record["text"]) for record in retry) > sum(len(record["text"]) for record in original), \
        "A retry must repack the full source pool, not recycle already-shortened excerpts"
    assert sum(step["tool"] == "citation_retry" for step in answer["trace"]) == 1
    assert not any(step["tool"] == "grounding_check" for step in answer["trace"])


@pytest.mark.parametrize("failure", [
    {"content": "RETRY_FICTION: Aurora uses ImaginaryCloud."},
    {"content": "RETRY_FICTION: Aurora uses ImaginaryCloud [99]."},
    {"content": ""},
    {"content": "Aurora uses SQLite [1].", "tool_calls": [{"function": {
        "name": "read_document", "arguments": {"document_id": 1}}}]},
    OllamaUnavailable("Scripted local runtime unavailable"),
    ValueError("Scripted invalid local inference response"),
], ids=["still-uncited", "invalid-reference", "empty", "tool-call", "runtime-error", "value-error"])
async def test_failed_citation_retry_keeps_original_safe_excerpts_and_stops(knowledge, failure):
    add_large_source_pool(knowledge)
    draft = "UNCITED_DRAFT: Aurora uses ImaginaryCloud."

    def failed_retry(payload):
        assert_clean_retry(payload, draft)
        if isinstance(failure, Exception):
            raise failure
        return failure

    answer, model = await ask(knowledge, "Which database does Aurora use?", [
        {"content": draft}, failed_retry,
    ])
    assert len(model.sent) == 2, "Failure must not start a second repair attempt"
    assert answer["mode"] == "extractive"
    assert "ImaginaryCloud" not in answer["content"]
    assert "UNCITED_DRAFT" not in answer["content"] and "RETRY_FICTION" not in answer["content"]
    original = assert_sources_match_payload(knowledge, answer, model.sent[0])
    retry = document_records(model.sent[1])
    assert original != retry, "This case must distinguish the original and enlarged retry excerpts"
    for record in original:
        assert record["text"] in answer["content"]
    assert sum(step["tool"] == "citation_retry" for step in answer["trace"]) == 1
    assert any(step["tool"] == "grounding_check" for step in answer["trace"])


@pytest.mark.parametrize("has_sources", [True, False])
async def test_unknown_abstention_is_accepted_without_citation_retry(knowledge, has_sources):
    if has_sources:
        add_document(knowledge, "aurora.md", "Aurora uses SQLite for its local database.")
    answer, model = await ask(knowledge, "What is Aurora's launch date according to documents?", [
        {"content": "Not in documents."},
    ])
    assert answer["content"] == "Not in documents."
    assert answer["mode"] == "agent"
    assert len(model.sent) == 1
    assert bool(answer["sources"]) is has_sources
    assert not any(step["tool"] == "citation_retry" for step in answer["trace"])


async def test_accepted_conversation_recall_with_documents_does_not_trigger_retry(knowledge):
    add_document(knowledge, "aurora.md", "Aurora uses SQLite for its local database.")
    previous = knowledge.store.create_session("Approved architecture")
    knowledge.store.add_message(previous["id"], "user", "The approved Aurora database is SQLite.")

    def answer_conversation(payload):
        memories = [message["content"] for message in payload["messages"]
                    if message.get("tool_name") == "search_conversations"]
        assert len(memories) == 1 and "approved Aurora database is SQLite" in memories[0]
        return {"content": "We decided Aurora uses SQLite."}

    answer, model = await ask(knowledge, "What did we decide for Aurora?", [
        {"content": "", "tool_calls": [{"function": {"name": "search_conversations", "arguments": {
            "query": "approved"}}}]},
        answer_conversation,
    ])
    assert answer["mode"] == "agent" and answer["sources"]
    assert len(model.sent) == 2
    assert not any(step["tool"] == "citation_retry" for step in answer["trace"])


@pytest.mark.parametrize("tool_count", [1, 6], ids=["normal-synthesis", "forced-final-synthesis"])
async def test_citation_retry_after_tool_use_removes_all_tool_and_assistant_envelopes(knowledge, tool_count):
    add_document(knowledge, "aurora.md", "Aurora uses SQLite for its local database.")
    draft = "UNCITED_DRAFT: Aurora uses SQLite."
    calls = [{"function": {"name": "search_conversations", "arguments": {
        "query": f"absenttoolenvelopetoken{index}"}}} for index in range(tool_count)]

    def final_uncited(payload):
        assert any(message["role"] == "tool" for message in payload["messages"])
        if tool_count == 6:
            assert "tools" not in payload
        return {"content": draft}

    def repaired(payload):
        assert_clean_retry(payload, draft)
        assert "absenttoolenvelopetoken" not in json.dumps(payload)
        return {"content": "Aurora uses SQLite [1]."}

    answer, model = await ask(knowledge, "Which database does Aurora use?", [
        {"content": "", "tool_calls": calls}, final_uncited, repaired,
    ])
    assert len(model.sent) == 3
    assert answer["mode"] == "agent"
    assert sum(step["tool"] == "search_conversations" for step in answer["trace"]) == tool_count
    assert sum(step["tool"] == "citation_retry" for step in answer["trace"]) == 1
    assert_sources_match_payload(knowledge, answer, model.sent[2])


@pytest.mark.parametrize("question", [
    "Explain the setup.", "Describe the architecture.", "Summarize this configuration.",
])
def test_substantive_imperative_with_sources_still_requires_citations(question):
    source = {"document_id": 1, "title": "setup.md", "text": "The setup uses local Python and SQLite."}
    answer = Agent(None, None, None, None).grounded_response(
        "The setup uses ImaginaryCloud.", [source], [], question)
    assert answer["mode"] == "extractive"
    assert "ImaginaryCloud" not in answer["content"]
    assert source["text"] in answer["content"]


@pytest.mark.parametrize("retry_succeeds", [True, False])
async def test_substantive_imperative_uses_the_same_single_citation_retry(knowledge, retry_succeeds):
    add_document(knowledge, "setup.md", "The setup uses local Python and SQLite.")
    retried = {"content": "The setup uses local Python and SQLite [1]."} if retry_succeeds else {
        "content": "The setup still uses ImaginaryCloud without a reference."}
    answer, model = await ask(knowledge, "Explain the setup.", [
        {"content": "The setup uses ImaginaryCloud."}, retried,
    ])
    assert len(model.sent) == 2
    assert sum(step["tool"] == "citation_retry" for step in answer["trace"]) == 1
    assert answer["mode"] == ("agent" if retry_succeeds else "extractive")
    assert "ImaginaryCloud" not in answer["content"]
    assert_sources_match_payload(knowledge, answer, model.sent[1 if retry_succeeds else 0])


@pytest.mark.parametrize("question", [
    "Tell me how to index files",
    "Does api.md have auth?",
])
def test_content_and_how_to_questions_are_not_catalog_commands(question):
    assert _catalog_request(question) is None


@pytest.mark.parametrize("question", [
    "List PDF files",
    "List all files in the project folder",
    "Do I have a file named api.md and notes.md?",
    "Does api.md exist and does docs.md exist?",
])
def test_filtered_or_multiple_filename_queries_request_clarification(question):
    assert _catalog_request(question)[0] == "clarify"


@pytest.mark.parametrize("question,name", [
    ("Is there a file named Study Guide.md?", "Study Guide.md"),
    ("Do I have a file called Project Notes?", "Project Notes"),
])
def test_unquoted_filenames_with_spaces_are_kept_whole(question, name):
    assert _catalog_request(question) == ("lookup", name)
