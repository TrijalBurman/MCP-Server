import pytest

from copilot.agent import Agent
from copilot.config import Settings
from copilot.library import Library
from copilot.store import Store


class Offline:
    def status(self):
        return {"chat_ready": False}


@pytest.mark.asyncio
async def test_agent_calls_real_mcp_and_preserves_grounding(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", ollama_url="http://127.0.0.1:9")
    store = Store(settings.database_path)
    library = Library(settings, store)
    folder = tmp_path / "notes"
    folder.mkdir()
    (folder / "meeting.md").write_text("Nimbus milestone: ship the offline search prototype in November.")
    library.scan(library.add_root(folder)["id"])
    session = store.create_session("Nimbus")
    store.add_message(session["id"], "user", "What is the Nimbus milestone?")
    agent = Agent(settings, store, library, Offline())
    answer = await agent.respond(session["id"], "What is the Nimbus milestone?")
    assert answer["mode"] == "extractive"
    assert "November" in answer["content"]
    assert answer["sources"][0]["title"] == "meeting.md"
    assert {t["tool"] for t in answer["trace"]} >= {"knowledge_search", "recall"}


@pytest.mark.asyncio
async def test_full_document_reads_all_pages_over_mcp(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", ollama_url="http://127.0.0.1:9")
    store = Store(settings.database_path)
    library = Library(settings, store)
    folder = tmp_path / "notes"
    folder.mkdir()
    text = "Beginning " + "local project details " * 2800 + " Final milestone: launch."
    (folder / "long.md").write_text(text)
    library.scan(library.add_root(folder)["id"])
    doc = store.list_documents()[0]
    session = store.create_session()
    class Capture(Agent):
        async def summarize_document(self, document, *args):
            assert document["text"] == text
            return "Complete document received [1]."
    class Ready:
        def status(self):
            return {"chat_ready": True}
    result = await Capture(settings, store, library, Ready()).respond(session["id"], "Summarize", document_id=doc["id"])
    assert result["content"] == "Complete document received [1]."
    assert result["trace"][0]["tool"] == "read_document"


@pytest.mark.asyncio
async def test_agent_tool_loop_can_recall_previous_conversation(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", ollama_url="http://127.0.0.1:9")
    store = Store(settings.database_path)
    library = Library(settings, store)
    previous = store.create_session("Design decision")
    store.add_message(previous["id"], "user", "Aurora uses SQLite instead of a server database.")
    session = store.create_session("Recall")
    store.add_message(session["id"], "user", "What did we decide for Aurora?")
    class ToolModel:
        calls = 0
        def status(self):
            return {"chat_ready": True}
        def chat(self, messages, tools=None):
            self.calls += 1
            if self.calls == 1:
                assert "remember" not in {t["function"]["name"] for t in tools}
                return {"role": "assistant", "content": "", "tool_calls": [{"function": {
                    "name": "search_conversations", "arguments": {"query": "Aurora"}}}]}
            assert any("SQLite" in m["content"] for m in messages if m["role"] == "tool")
            return {"role": "assistant", "content": "Your saved conversation says Aurora uses SQLite."}
    answer = await Agent(settings, store, library, ToolModel()).respond(session["id"], "What did we decide for Aurora?")
    assert "SQLite" in answer["content"]
    assert answer["trace"][-1]["tool"] == "search_conversations"


@pytest.mark.asyncio
async def test_project_plan_uses_real_mcp_sources_and_global_preferences(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", ollama_url="http://127.0.0.1:9")
    store = Store(settings.database_path)
    library = Library(settings, store)
    folder = tmp_path / "notes"
    folder.mkdir()
    (folder / "aurora.md").write_text("Aurora architecture: SQLite is the approved database.")
    library.scan(library.add_root(folder)["id"])
    project = store.create_project("Aurora", "Create an offline study assistant.")
    store.add_memory("Keep plans concise.", kind="preference")
    class PlanModel:
        def chat(self, messages, tools=None):
            joined = "\n".join(m["content"] for m in messages)
            assert "SQLite" in joined and "Keep plans concise" in joined
            assert "Two milestones" in joined
            return {"content": "# Aurora plan\n\nUse SQLite [1]."}
    plan = await Agent(settings, store, library, PlanModel()).project_plan(project, "Two milestones")
    assert "## Local references" in plan
    assert "aurora.md" in plan
