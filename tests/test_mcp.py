"""Protocol-level coverage: a real SDK client launches the stdio server."""

import json
import os
import sys
from contextlib import asynccontextmanager

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from copilot.config import Settings
from copilot.library import Library
from copilot.store import Store


@pytest.fixture
def indexed_library(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", ollama_url="http://127.0.0.1:1")
    source = tmp_path / "knowledge"
    source.mkdir()
    text = ("The lighthouse project uses a local SQLite memory database.\n" * 500).rstrip()
    document_path = source / "lighthouse.md"
    document_path.write_text(text, encoding="utf-8")
    store = Store(settings.database_path)
    library = Library(settings, store)
    root = library.add_root(str(source), label="Test knowledge")
    result = library.scan(root["id"])
    assert result["indexed"] == 1
    document = store.list_documents()[0]
    return settings, store, document, document_path, text


@asynccontextmanager
async def open_mcp(indexed_library):
    settings = indexed_library[0]
    env = dict(os.environ)
    env.update({"COPILOT_DATA_DIR": str(settings.data_dir), "COPILOT_OLLAMA_URL": settings.ollama_url})
    params = StdioServerParameters(command=sys.executable, args=["-m", "copilot.mcp_server"], env=env)
    async with stdio_client(params) as (reader, writer), ClientSession(reader, writer) as session:
        initialized = await session.initialize()
        assert initialized.serverInfo.name == "Local Knowledge Copilot Memory"
        yield session


def result_data(result):
    assert not result.isError, result.content
    if result.structuredContent is not None:
        return result.structuredContent
    return json.loads(result.content[0].text)


async def test_stdio_discovery_search_and_complete_document(indexed_library):
    async with open_mcp(indexed_library) as mcp_session:
        _, _, document, _, original = indexed_library
        tools = {tool.name: tool for tool in (await mcp_session.list_tools()).tools}
        assert set(tools) == {
            "knowledge_search", "list_documents", "read_document", "remember", "recall", "forget",
            "list_projects", "create_project", "list_sources", "search_conversations",
        }
        assert tools["read_document"].annotations.readOnlyHint is True
        assert tools["forget"].annotations.destructiveHint is True

        sources = result_data(await mcp_session.call_tool("list_sources", {}))
        assert sources["roots"][0]["label"] == "Test knowledge"
        listed = result_data(await mcp_session.call_tool("list_documents", {"query": "lighthouse", "limit": 1}))
        assert listed["documents"][0]["id"] == document["id"]
        search = result_data(await mcp_session.call_tool("knowledge_search", {"query": "lighthouse", "limit": 3}))
        assert search["results"]
        assert all(hit["document_id"] == document["id"] for hit in search["results"])

        pieces = []
        offset = 0
        while True:
            part = result_data(await mcp_session.call_tool("read_document", {
                "document_id": document["id"], "offset": offset, "length": 12000,
            }))
            assert part["total"] == len(original)
            assert part["snapshot"] is True
            pieces.append(part["text"])
            if part["next_offset"] is None:
                break
            assert part["next_offset"] > offset
            offset = part["next_offset"]
        assert "".join(pieces) == original
        empty = result_data(await mcp_session.call_tool("read_document", {
            "document_id": document["id"], "offset": len(original), "length": 10,
        }))
        assert empty["text"] == "" and empty["next_offset"] is None


async def test_stdio_memory_writes_persist_and_resources(indexed_library):
    async with open_mcp(indexed_library) as mcp_session:
        store = indexed_library[1]
        project = result_data(await mcp_session.call_tool("create_project", {
            "name": "Lighthouse", "description": "An offline project",
        }))
        memory = result_data(await mcp_session.call_tool("remember", {
            "content": "Use a local SQLite memory database.", "kind": "decision", "project_id": project["id"],
        }))
        assert store.get_project(project["id"])["name"] == "Lighthouse"
        assert store.list_memories(project_id=project["id"])[0]["id"] == memory["id"]
        recalled = result_data(await mcp_session.call_tool("recall", {"project_id": project["id"], "query": "SQLite"}))
        assert recalled["memories"][0]["content"] == memory["content"]
        projects = result_data(await mcp_session.call_tool("list_projects", {}))
        assert projects["projects"][0]["id"] == project["id"]
        conversation = store.create_session("Earlier project context", project_id=project["id"])
        store.add_message(conversation["id"], "user", "The lighthouse project has a review on Friday.")
        history = result_data(await mcp_session.call_tool("search_conversations", {
            "query": "lighthouse", "project_id": project["id"],
        }))
        assert history["messages"][0]["session_id"] == conversation["id"]

        resources = await mcp_session.list_resources()
        assert "memory://overview" in {str(resource.uri) for resource in resources.resources}
        templates = await mcp_session.list_resource_templates()
        assert "memory://projects/{project_id}" in {str(resource.uriTemplate) for resource in templates.resourceTemplates}
        overview = await mcp_session.read_resource("memory://overview")
        assert json.loads(overview.contents[0].text)["stats"]["memories"] == 1
        context = await mcp_session.read_resource(f"memory://projects/{project['id']}")
        assert json.loads(context.contents[0].text)["memories"][0]["id"] == memory["id"]

        deleted = result_data(await mcp_session.call_tool("forget", {"memory_id": memory["id"]}))
        assert deleted["deleted"] is True
        assert store.list_memories(project_id=project["id"]) == []


async def test_stdio_document_bounds_and_source_changes(indexed_library):
    async with open_mcp(indexed_library) as mcp_session:
        _, store, document, document_path, original = indexed_library
        for arguments in (
            {"document_id": document["id"], "offset": -1},
            {"document_id": document["id"], "length": 0},
            {"document_id": document["id"], "length": 50001},
            {"document_id": document["id"], "offset": len(original) + 1},
        ):
            assert (await mcp_session.call_tool("read_document", arguments)).isError

        document_path.write_text("The source changed after indexing.", encoding="utf-8")
        stale = await mcp_session.call_tool("read_document", {"document_id": document["id"]})
        assert stale.isError and "changed since indexing" in stale.content[0].text
        document_path.unlink()
        missing = await mcp_session.call_tool("read_document", {"document_id": document["id"]})
        assert missing.isError and "unavailable" in missing.content[0].text
        # No tool reads arbitrary paths, and an unapproved document cannot be returned.
        store.remove_root(document["root_id"])
        assert (await mcp_session.call_tool("read_document", {"document_id": document["id"]})).isError


async def test_stdio_rejects_root_replaced_by_symlink(indexed_library):
    async with open_mcp(indexed_library) as mcp_session:
        _, _, document, document_path, _ = indexed_library
        source_root = document_path.parent
        moved_root = source_root.with_name("knowledge-moved")
        source_root.rename(moved_root)
        source_root.symlink_to(moved_root, target_is_directory=True)
        result = await mcp_session.call_tool("read_document", {"document_id": document["id"]})
        assert result.isError and "symbolic link" in result.content[0].text
