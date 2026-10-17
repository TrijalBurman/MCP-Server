from pathlib import Path

import pytest

from copilot.library import chunk_text
from copilot.store import Store, _document_name_matcher


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


def test_metadata_catalog_pages_are_complete_filtered_and_persistent(store, tmp_path):
    first = store.add_root(tmp_path / "first")
    second = store.add_root(tmp_path / "second")
    for number in range(7):
        insert_document(store, first, tmp_path / "first" / f"api-{number}.md", "Repeated shared passage")
    insert_document(store, second, tmp_path / "second" / "api-extra.md", "Another source")
    reopened = Store(store.database_path)
    offset, collected = 0, []
    while True:
        page = reopened.page_documents("api", limit=3, offset=offset, root_id=first["id"])
        assert page["total"] == 7 and page["offset"] == offset and page["scope"] == "indexed"
        assert all("text" not in row and row["root_id"] == first["id"] for row in page["documents"])
        collected.extend(row["id"] for row in page["documents"])
        if page["next_offset"] is None:
            break
        assert page["next_offset"] > offset
        offset = page["next_offset"]
    assert len(set(collected)) == len(collected) == 7
    assert reopened.count_documents("api", first["id"]) == 7
    assert len(reopened.list_documents("api", root_id=second["id"])) == 1
    assert reopened.page_documents("api", root_id=999)["total"] == 0
    empty = reopened.page_documents(offset=100)
    assert empty["total"] == 8 and empty["documents"] == [] and empty["next_offset"] is None


def test_exact_document_names_paths_duplicates_and_index_scope(store, tmp_path):
    root = store.add_root(tmp_path / "knowledge")
    first = insert_document(store, root, tmp_path / "knowledge" / "api.md", "Source body")
    second = store.upsert_document(root["id"], tmp_path / "knowledge" / "nested" / "api.md",
                                   "A display title", "Different body", 1234, 14, chunk_text("Different body"))
    insert_document(store, root, tmp_path / "knowledge" / "api.md.md", "Not the exact filename")
    insert_document(store, root, tmp_path / "knowledge" / "notes.md", "The contents mention api.md")
    special = insert_document(store, root, tmp_path / "knowledge" / "100%_[1].md", "Literal wildcards")
    first_page = store.find_documents("api.md", limit=1)
    assert first_page["total"] == 2 and first_page["next_offset"] == 1
    last_page = store.find_documents("api.md", limit=1, offset=1)
    assert last_page["next_offset"] is None
    ids = {row["id"] for row in first_page["documents"] + last_page["documents"]}
    assert ids == {first["id"], second["id"]}
    assert all("text" not in row for row in first_page["documents"] + last_page["documents"])
    assert store.find_documents(str(second["path"]))["documents"][0]["id"] == second["id"]
    assert store.find_documents("nested/api.md")["documents"][0]["id"] == second["id"]
    assert store.find_documents("100%_[1].md")["documents"][0]["id"] == special["id"]
    assert store.find_documents("api")["total"] == 0
    assert store.find_documents("*.md")["total"] == 0
    assert store.find_documents("api.md", root_id=root["id"] + 1)["total"] == 0
    # These are index records even though no source files were created by this test.
    assert first_page["scope"] == "indexed"
    assert store.remove_root(root["id"])
    assert store.find_documents("api.md")["total"] == 0


def test_native_exact_name_policy_and_no_path_resolution():
    windows = _document_name_matcher("CAFÉ.MD", windows=True)
    assert windows(r"C:\Knowledge\café.md", r"C:\Knowledge") == 1
    relative = _document_name_matcher(r"Nested\API.md", windows=True)
    assert relative(r"C:\Knowledge\nested\api.md", r"c:\knowledge") == 1
    assert relative(r"C:\Other\nested\api.md", r"C:\Knowledge") == 0
    absolute = _document_name_matcher("C:/Knowledge/API.md", windows=True)
    assert absolute(r"c:\knowledge\api.md", r"C:\Knowledge") == 1
    linux = _document_name_matcher("api.md", windows=False)
    assert linux("/knowledge/API.md", "/knowledge") == 0
    assert linux("/knowledge/api.md", "/knowledge") == 1
    assert _document_name_matcher(r"api\notes.md", windows=False)(r"/knowledge/api\notes.md", "/knowledge") == 1
    for name, native_windows in [("", False), ("../api.md", False), (r"..\api.md", True),
                                 (r"C:api.md", True), ("api\x00.md", False)]:
        with pytest.raises(ValueError):
            _document_name_matcher(name, windows=native_windows)


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
