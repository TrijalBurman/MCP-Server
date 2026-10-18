"""Small talk must not infer private context or read the knowledge library."""

import pytest

import copilot.agent as agent_module
from copilot.agent import Agent
from copilot.config import Settings
from copilot.library import Library
from copilot.store import Store


class ForbiddenAccess:
    def __getattr__(self, name):
        raise AssertionError(f"A local greeting must not access {name}")


def forbidden_mcp(*args, **kwargs):
    raise AssertionError("A local greeting must not open MCP or retrieve documents")


@pytest.mark.parametrize("message", [
    "hello", "  HI THERE!!  ", "Hey, LocalMind.", "Greetings!",
    "Good morning LocalMind!", "good afternoon", "Good evening there...",
    "Thanks!", "thank you", "help", "what can you do?", "How can you help me?", "Who are you?",
])
def test_complete_small_talk_dispatch_is_neutral_and_local(message):
    content = agent_module._local_response(message)
    assert isinstance(content, str) and content.strip()
    assert "[1]" not in content
    assert ".md" not in content, "A greeting must not introduce invented file identities"


@pytest.mark.parametrize("message,project_id,document_id", [
    ("Hello!", 987, 654),
    ("Thank you.", 987, None),
    ("What can you do?", None, 654),
])
async def test_local_response_precedes_all_history_model_and_document_access(
        monkeypatch, message, project_id, document_id):
    monkeypatch.setattr(agent_module, "KnowledgeClient", forbidden_mcp)
    monkeypatch.setattr(agent_module, "stdio_client", forbidden_mcp)
    inaccessible = ForbiddenAccess()
    agent = Agent(inaccessible, inaccessible, inaccessible, inaccessible)

    answer = await agent.respond(123, message, project_id=project_id, document_id=document_id)

    assert answer["mode"] == "local"
    assert answer["sources"] == [] and answer["trace"] == []
    assert answer["content"] == agent_module._local_response(message)


@pytest.mark.parametrize("message", [
    "Hi, summarize api.md", "hello, what files are indexed?", "thanks, explain the setup",
])
def test_greeting_followed_by_a_request_is_not_swallowed(message):
    assert agent_module._local_response(message) is None


@pytest.fixture
def library_document(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", ollama_url="http://127.0.0.1:9")
    store = Store(settings.database_path)
    folder = tmp_path / "knowledge"
    folder.mkdir()
    path = folder / "api.md"
    text = "The route-proof API stores local project decisions in SQLite."
    path.write_text(text, encoding="utf-8")
    root = store.add_root(folder)
    stat = path.stat()
    document = store.upsert_document(root["id"], path, path.name, text, stat.st_mtime_ns, stat.st_size,
                                     [{"text": text, "start": 0, "end": len(text), "page": None}])
    session = store.create_session("Mixed greeting and request")
    return settings, store, Library(settings, store), session, document


async def test_mixed_greeting_and_inventory_still_uses_real_mcp_metadata(library_document):
    settings, store, library, session, document = library_document
    answer = await Agent(settings, store, library, ForbiddenAccess()).respond(
        session["id"], "hello, what files are indexed?")
    assert answer["mode"] == "catalog"
    assert [source["document_id"] for source in answer["sources"]] == [document["id"]]
    assert "api.md" in answer["content"]
    assert {step["tool"] for step in answer["trace"]} == {"list_documents"}


async def test_mixed_greeting_and_document_request_still_reads_the_document(library_document):
    settings, store, library, session, document = library_document

    class Offline:
        def status(self):
            return {"chat_ready": False}

    answer = await Agent(settings, store, library, Offline()).respond(
        session["id"], "Hi, summarize api.md", document_id=document["id"])
    assert answer["mode"] == "extractive"
    assert "route-proof API" in answer["content"]
    assert [source["document_id"] for source in answer["sources"]] == [document["id"]]
    assert answer["trace"][0]["tool"] == "read_document"
