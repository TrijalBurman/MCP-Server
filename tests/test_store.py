from pathlib import Path

import pytest

from copilot.library import chunk_text
from copilot.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "state" / "memory.sqlite3")


def insert_document(store, root, path, text, embedding=None, model=""):
    chunks = chunk_text(text)
    if embedding is not None:
        for chunk in chunks:
            chunk["embedding"] = embedding
    return store.upsert_document(root["id"], path, Path(path).name, text, 1234, len(text), chunks, model)


def test_document_persistence_fts_update_and_root_removal(store, tmp_path):
    root = store.add_root(tmp_path / "notes", "Study notes")
    document = insert_document(store, root, tmp_path / "notes" / "lesson.md", "SQLite transaction isolation lecture")
    reopened = Store(store.database_path)
    assert reopened.get_document(document["id"])["text"] == "SQLite transaction isolation lecture"
    assert reopened.search("transaction isolation")[0]["document_id"] == document["id"]
    changed = insert_document(reopened, root, tmp_path / "notes" / "lesson.md", "Probability distribution lecture")
    assert changed["id"] == document["id"]
    assert not reopened.search("transaction")
    assert reopened.search("probability")
    assert reopened.remove_root(root["id"])
    assert not reopened.search("probability")
    assert reopened.stats()["chunks"] == 0


def test_semantic_retrieval_model_isolation_and_reciprocal_rank(store, tmp_path):
    root = store.add_root(tmp_path / "notes")
    first = insert_document(store, root, tmp_path / "notes" / "a.md", "Project bicycle transport plan", [1, 0], "local-v1")
    second = insert_document(store, root, tmp_path / "notes" / "b.md", "Database storage design", [0, 1], "local-v1")
    insert_document(store, root, tmp_path / "notes" / "c.md", "Unrelated topic", [1, 0], "local-v2")
    results = store.search("commuting", query_embedding=[1, 0], embedding_model="local-v1")
    assert [item["document_id"] for item in results] == [first["id"]]
    assert not store.search("commuting", query_embedding=[1, 0], embedding_model="missing")
    fused = store.search("storage", query_embedding=[0, 1], embedding_model="local-v1")
    assert fused[0]["document_id"] == second["id"]
    assert fused[0]["score"] > results[0]["score"]
    assert not store.search("commuting", query_embedding=[float("nan"), 0], embedding_model="local-v1")
    assert not store.search("commuting", query_embedding=[1, 0, 0], embedding_model="local-v1")


def test_chunk_offsets_and_invalid_upsert_roll_back(store, tmp_path):
    root = store.add_root(tmp_path / "notes")
    path = tmp_path / "notes" / "a.md"
    existing = insert_document(store, root, path, "A saved original note")
    with pytest.raises(ValueError, match="offsets"):
        store.upsert_document(root["id"], path, "a.md", "Changed note", 999, 12,
                              [{"text": "wrong text", "start": 0, "end": 5, "page": None}])
    assert store.get_document(existing["id"])["text"] == "A saved original note"
    assert store.search("original")


def test_project_memory_sessions_and_cross_conversation_persistence(store):
    project = store.create_project("Research", "Study compiler design")
    memory = store.add_memory("Prefer Rust examples", "preference", project["id"])
    conversation = store.create_session("Compiler discussion", project["id"])
    source = [{"document_id": 1, "page": 2}]
    trace = [{"tool": "knowledge_search", "detail": "compiler"}]
    store.add_message(conversation["id"], "user", "What is compiler optimization?")
    store.add_message(conversation["id"], "assistant", "Compiler optimization preserves semantics.", source, trace)
    reopened = Store(store.database_path)
    assert reopened.list_memories(project["id"], "Rust")[0]["id"] == memory["id"]
    assert reopened.get_messages(conversation["id"])[1]["sources"] == source
    assert reopened.get_messages(conversation["id"])[1]["trace"] == trace
    recalled = reopened.search_messages("optimization", project_id=project["id"])
    assert len(recalled) == 2
    assert recalled[0]["session_title"] == "Compiler discussion"
    assert not reopened.search_messages("optimization", project_id=project["id"] + 1)
    assert reopened.delete_session(conversation["id"])
    assert not reopened.search_messages("optimization")
    assert not reopened.get_messages(conversation["id"])
    assert reopened.delete_memory(memory["id"])
    assert not reopened.list_memories()


def test_fts_input_is_literal_and_pagination_limits(store, tmp_path):
    root = store.add_root(tmp_path / "notes")
    for name in ["a.md", "b.md", "c.md"]:
        insert_document(store, root, tmp_path / "notes" / name, 'Words OR MATCH "quoted" notes')
    assert len(store.search('" OR ( MATCH * NEAR(', limit=1)) == 1
    assert not store.search("***")
    assert len(store.list_documents(limit=1, offset=1)) == 1
    assert not store.list_documents(query="%")
    assert not store.get_document(999999)


def test_filtered_document_count_matches_listing_for_pagination(store, tmp_path):
    root = store.add_root(tmp_path / "library")
    for name in ["Study Guide.md", "study-plan.md", "100%_Complete.md", "other.txt"]:
        insert_document(store, root, tmp_path / "library" / name, "Sample extracted content")
    for query in ["", "Study", " study ", ".md", "%", "_Complete", "missing"]:
        assert store.count_documents(query) == len(store.list_documents(query, limit=500))
    assert store.count_documents("Study") == 2
    assert len(store.list_documents("Study", limit=1, offset=1)) == 1
    assert store.count_documents("%") == 1
    assert store.count_documents("missing") == 0
    assert store.count_documents() == store.stats()["documents"] == 4


def test_safe_prune_handles_more_than_sql_variable_limit(store, tmp_path):
    root = store.add_root(tmp_path / "notes")
    keep = insert_document(store, root, tmp_path / "notes" / "keep.md", "Keep this")
    gone = insert_document(store, root, tmp_path / "notes" / "gone.md", "Delete this")
    seen = [keep["path"]] + [str(tmp_path / "notes" / f"missing-{number}.md") for number in range(3000)]
    assert store.prune_documents(root["id"], seen) == 1
    assert store.get_document(keep["id"])
    assert store.get_document(gone["id"]) is None


def test_memory_and_session_project_references_validated(store):
    with pytest.raises(ValueError, match="Project not found"):
        store.add_memory("Example", project_id=999)
    with pytest.raises(ValueError, match="Project not found"):
        store.create_session(project_id=999)
    with pytest.raises(ValueError, match="Conversation not found"):
        store.add_message(999, "user", "Example")
    with pytest.raises(ValueError, match="Memory must"):
        store.add_memory(" ")


def test_memory_edit_persists_preserves_creation_and_moves_project_scope(store):
    first = store.create_project("First project")
    second = store.create_project("Second project")
    original = store.add_memory("Use Java examples", "preference", first["id"])
    updated = store.update_memory(original["id"], "  Use Rust examples  ", " coding ", second["id"])
    assert updated["id"] == original["id"]
    assert updated["created_at"] == original["created_at"]
    reopened = Store(store.database_path)
    assert not reopened.list_memories(first["id"])
    assert not reopened.list_memories(second["id"], "Java")
    assert reopened.list_memories(second["id"], "Rust") == [updated]
    assert updated["content"] == "Use Rust examples" and updated["kind"] == "coding"
    with pytest.raises(ValueError, match="Project not found"):
        reopened.update_memory(original["id"], "Must not be saved", project_id=999)
    with pytest.raises(ValueError, match="Memory must"):
        reopened.update_memory(original["id"], " ", project_id=second["id"])
    assert reopened.list_memories(second["id"])[0] == updated
    assert reopened.update_memory(999, "Missing memory") is None
    global_note = reopened.update_memory(original["id"], "Now a general note")
    assert global_note["project_id"] is None
    assert not reopened.list_memories(second["id"])
    assert reopened.list_memories(query="general") == [global_note]
