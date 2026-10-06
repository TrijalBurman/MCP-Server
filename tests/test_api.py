import time
from pathlib import Path

from fastapi.testclient import TestClient

from copilot.api import create_app
from copilot.config import Settings


def client_at(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "data"))
    app.state.library.embedder = None
    return TestClient(app, base_url="http://127.0.0.1:8000"), app


def test_library_flow_and_persistence(tmp_path):
    folder = tmp_path / "notes"
    folder.mkdir()
    source = folder / "architecture.md"
    source.write_text("Project Atlas uses SQLite to preserve project decisions. The deadline is December.")
    client, app = client_at(tmp_path)
    with client:
        root = client.post("/api/roots", json={"path": str(folder)}).json()
        assert client.post("/api/index", json={"root_id": root["id"]}).status_code == 202
        for _ in range(100):
            if not app.state.store.stats()["documents"]:
                time.sleep(0.02)
            else:
                break
        docs = client.get("/api/documents").json()["documents"]
        assert len(docs) == 1
        doc_id = docs[0]["id"]
        assert "SQLite" in client.get(f"/api/documents/{doc_id}").json()["text"]
        assert "SQLite" in client.get(f"/api/documents/{doc_id}/download").text
        assert client.post("/api/search", json={"query": "Atlas"}).json()["results"]
        source.write_text("Updated: Atlas uses Python.")
        assert client.get(f"/api/documents/{doc_id}").status_code == 400
        assert client.get("/api/documents/9999").status_code == 404
    restored, _ = client_at(tmp_path)
    assert restored.get("/api/roots").json()["roots"][0]["path"] == str(folder)


def test_memory_project_and_session_flow(tmp_path):
    client, app = client_at(tmp_path)
    project = client.post("/api/projects", json={"name": "Local research", "description": "Offline RAG"}).json()
    memory = client.post("/api/memories", json={"content": "Prefer Python", "project_id": project["id"]}).json()
    assert client.get(f"/api/memories?project_id={project['id']}").json()["memories"] == [memory]
    session = client.post("/api/sessions", json={"title": "Project planning", "project_id": project["id"]}).json()
    response = client.post("/api/chat", json={"session_id": session["id"], "message": "remember that use SQLite"})
    assert response.status_code == 200, response.text
    assert "Saved" in response.json()["content"]
    messages = client.get(f"/api/sessions/{session['id']}/messages").json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert app.state.store.search_messages("SQLite")
    assert client.delete(f"/api/memories/{memory['id']}").json()["deleted"]
    assert client.delete(f"/api/sessions/{session['id']}").json()["deleted"]
    assert client.get(f"/api/sessions/{session['id']}/messages").status_code == 404


def test_memory_edits_and_filtered_document_counts(tmp_path):
    client, app = client_at(tmp_path)
    memory = client.post("/api/memories", json={"content": "Old preference"}).json()
    updated = client.put(f"/api/memories/{memory['id']}", json={"content": "Prefer concise explanations", "kind": "preference"})
    assert updated.status_code == 200
    assert client.get("/api/memories?q=concise").json()["memories"][0]["content"] == "Prefer concise explanations"
    assert client.put("/api/memories/9999", json={"content": "No memory"}).status_code == 404
    assert client.get("/api/documents?q=nonexistent").json()["total"] == 0


def test_browser_access_and_cloud_config_rejected(tmp_path):
    client, _ = client_at(tmp_path)
    assert client.post("/api/projects", json={"name": "Bad origin"},
                       headers={"Origin": "https://malicious.example"}).status_code == 403
    assert client.get("/api/status", headers={"Host": "malicious.example"}).status_code == 400
    assert client.post("/api/projects", content='{"name":"bad"}',
                       headers={"Content-Type": "text/plain"}).status_code == 415
    assert client.put("/api/settings", json={"chat_model": "qwen3:cloud"}).status_code == 400
    assert client.post("/api/memories", json={"content": "   "}).status_code == 400
    assert client.post("/api/projects", json={"name": "   "}).status_code == 400
    assert client.post("/api/index", json={}).status_code == 400
    assert client.put("/api/settings", json={"context_size": 9999999}).status_code == 422
    assert client.put("/api/settings", json={"context_size": 2048}).status_code == 422


def test_plan_written_inside_project_directory(tmp_path, monkeypatch):
    client, app = client_at(tmp_path)
    project = client.post("/api/projects", json={"name": "Plan"}).json()
    async def make_plan(*args):
        return "# Plan\n\nBuild and validate local search."
    monkeypatch.setattr(app.state.agent, "project_plan", make_plan)
    response = client.post(f"/api/projects/{project['id']}/plan", json={"prompt": "Create milestones"})
    assert response.status_code == 200, response.text
    path = Path(response.json()["path"])
    assert path.is_relative_to(tmp_path / "data" / "projects")
    assert path.read_text().startswith("# Plan")
    assert client.get(f"/api/projects/{project['id']}").json()["plan"] == path.read_text()


def test_unicode_project_plan_round_trip(tmp_path, monkeypatch):
    client, app = client_at(tmp_path / "Research space 東京")
    project = client.post("/api/projects", json={"name": "योजना 東京"}).json()
    content = "# योजना 東京\n\nRésumé: use SQLite — café."

    async def make_plan(*args):
        return content

    monkeypatch.setattr(app.state.agent, "project_plan", make_plan)
    response = client.post(f"/api/projects/{project['id']}/plan", json={"prompt": "Create a plan"})
    assert response.status_code == 200, response.text
    path = Path(response.json()["path"])
    assert path.read_bytes() == content.encode("utf-8")
    assert client.get(f"/api/projects/{project['id']}").json()["plan"] == content
