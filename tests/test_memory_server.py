import importlib
from pathlib import Path
from fastapi.testclient import TestClient

def test_memory_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    import mcp_server.main as server
    importlib.reload(server)
    client=TestClient(server.app)
    assert client.get("/health").json()["status"] == "ok"
    assert client.post("/mcp/tools/call",json={"tool":"write_memory","arguments":{"section":"Testing","content":"Working"}}).json()["success"]
    assert client.post("/mcp/tools/call",json={"tool":"read_memory","arguments":{"section":"Testing"}}).json()["content"] == "Working"
    saved=client.post("/mcp/tools/call",json={"tool":"log_decision","arguments":{"title":"Storage","rationale":"Local-first"}}).json()
    assert saved["entry"]["id"] == 1
    assert client.post("/mcp/tools/call",json={"tool":"read_decisions","arguments":{}}).json()["decisions"][0]["title"] == "Storage"
