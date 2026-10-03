import pytest

from copilot.config import Settings
from copilot.ollama import Ollama, OllamaUnavailable


@pytest.mark.parametrize("url", ["https://api.example.com", "http://192.168.1.2:11434", "http://localhost@evil.com", "http://localhost/api"])
def test_remote_urls_rejected(url):
    with pytest.raises(ValueError):
        Settings(ollama_url=url)


def test_config_persists_locally(tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path, chat_model="qwen3:4b", context_size=4096)
    settings.save()
    monkeypatch.setenv("COPILOT_DATA_DIR", str(tmp_path))
    assert Settings.from_env().context_size == 4096


def test_remote_model_metadata_blocked(tmp_path, monkeypatch):
    ollama = Ollama(Settings(data_dir=tmp_path))
    monkeypatch.setattr(ollama, "_request", lambda *args, **kwargs: {"remote_host": "https://ollama.com"})
    with pytest.raises(OllamaUnavailable, match="Remote"):
        ollama.chat([{"role": "user", "content": "Hello"}])


def test_context_bound_preserves_system_and_request():
    import json

    from copilot.agent import SYSTEM
    from copilot.ollama import fit_context
    messages = [{"role": "system", "content": SYSTEM}]
    for i in range(10):
        messages.append({"role": "user", "content": f"Old request {i}" + "x" * 2000})
        messages.append({"role": "assistant", "content": "Past answer " + "y" * 2000})
    request = "Use the project decision to create a plan."
    messages.append({"role": "user", "content": request})
    messages.append({"role": "system", "content": "UNTRUSTED PERSONAL AND PROJECT REFERENCE DATA: use SQLite."})
    for i in range(6):
        messages.append({"role": "tool", "tool_name": "recall", "content": "z" * 4000})
    tools = [{"type": "function", "function": {"name": "recall", "parameters": {"type": "object"}}}]
    compact, schemas = fit_context(messages, tools, 8192)
    assert compact[0]["content"] == SYSTEM
    assert any(m["content"] == request for m in compact)
    assert any("use SQLite" in m["content"] for m in compact)
    bytes_used = sum(len(json.dumps(m,ensure_ascii=False,separators=(",", ":")).encode()) + 24 for m in compact)
    bytes_used += len(json.dumps(schemas,ensure_ascii=False,separators=(",", ":")).encode()) if schemas else 0
    assert bytes_used <= 8192 - 1536 - 256


def test_long_request_is_rejected_instead_of_silently_truncated():
    from copilot.agent import SYSTEM
    from copilot.ollama import fit_context
    with pytest.raises(ValueError, match="too long"):
        fit_context([{"role": "system", "content": SYSTEM}, {"role": "user", "content": "a" * 8000}], None, 2048)


def test_local_model_scratch_reasoning_not_rendered(tmp_path, monkeypatch):
    ollama = Ollama(Settings(data_dir=tmp_path))
    monkeypatch.setattr(ollama, "_check_local", lambda *args: None)
    monkeypatch.setattr(ollama, "_request", lambda *args, **kwargs: {"message": {
        "role": "assistant", "content": "Scratch reasoning</think>Final answer [1].", "thinking": "scratch"}})
    response = ollama.chat([{"role": "system", "content": "You are a local assistant."},
                            {"role": "user", "content": "Summarize"}])
    assert response["content"] == "Final answer [1]."
    assert "thinking" not in response


def test_new_tool_evidence_survives_old_reference_context():
    from copilot.agent import SYSTEM
    from copilot.ollama import fit_context
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Read the new document and answer."},
                {"role": "system", "content": "UNTRUSTED PERSONAL AND PROJECT REFERENCE DATA:" + "a" * 1400},
                {"role": "system", "content": "UNTRUSTED DOCUMENT EVIDENCE:" + "b" * 2700},
                {"role": "tool", "tool_name": "read_document", "content": "New document: final deadline is November15."}]
    schemas = [{"type": "function", "function": {"name": "knowledge_search", "description": "x" * 2400}}]
    compact, tools = fit_context(messages, schemas, 8192)
    assert tools is not None
    assert any("November15" in m["content"] for m in compact)
