# Local-First Knowledge Copilot

An offline, privacy-first knowledge assistant with durable Markdown/YAML memory and document retrieval.

## Run

1. Install Docker with Docker Compose (and NVIDIA Container Toolkit if using an NVIDIA GPU).
2. From this folder, run `docker compose up --build`.
3. Open `http://localhost:8501`.

The first startup downloads `qwen2.5:7b` into the local Docker volume. All uploaded documents, notes, decisions, and vector data remain under `data/` in this folder.

## Services

| Service | Address | Purpose |
| --- | --- | --- |
| Frontend | http://localhost:8501 | Chat, ingestion, memory inspection |
| Agent | http://localhost:8001 | ReAct orchestration and Ollama client |
| MCP server | http://localhost:8000 | Memory and RAG tool API |
| Ollama | http://localhost:11434 | Local Qwen inference |

## Local development

Create a virtual environment, install either service's requirements, then run `uvicorn mcp_server.main:app --port 8000`, `uvicorn agent.main:app --port 8001`, and `streamlit run frontend/app.py` in separate terminals. Set `MCP_URL`, `OLLAMA_URL`, and `AGENT_URL` only when services are not on their Docker defaults.
