# 🧠 Local-First Agentic Knowledge Copilot

> A fully offline, zero-cost AI assistant with persistent project memory, local RAG over documents, and a custom Model Context Protocol (MCP) server — powered by **Qwen2.5:7b** + **ChromaDB** + **Streamlit**.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Streamlit Frontend                 │
│              (Web UI at localhost:8501)             │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP REST (httpx)
┌──────────────────────▼──────────────────────────────┐
│               Agentic AI Layer (ReAct)               │
│   - Multi-turn conversation state                   │
│   - Tool planning & calling via ReAct loop          │
│   - Local Ollama LLM (Qwen2.5:7b on NVIDIA GPU)     │
└──────────────────────┬──────────────────────────────┘
                       │ MCP Protocol / REST
┌──────────────────────▼──────────────────────────────┐
│         Custom MCP Memory + Document Server         │
│  Memory: Markdown/YAML files (Human-Readable)       │
│  RAG: ChromaDB + sentence-transformers (local)      │
│  Tools: read/write memory, decisions, notes, search │
└─────────────────────────────────────────────────────┘
```

---

## ⚡ Quick Start

```bash
# 1. Enter the project directory
cd ~/AI/local-knowledge-copilot

# 2. Start the entire stack with Docker Compose
docker compose up --build -d

# 3. Open the UI in your browser
http://localhost:8501
```

---

## 📦 Services

| Service | Port | Description |
|---|---|---|
| **Streamlit UI** | `8501` | Interactive chat interface with sidebar memory & doc tools |
| **Agent API** | `8001` | FastAPI ReAct agent backend interacting with MCP + Ollama |
| **MCP Server** | `8000` | Custom MCP memory + RAG document server |
| **Ollama** | `11434` | Local LLM server (GPU-accelerated on RTX 5050) |

---

## 🛠️ MCP Tools

| Tool | Purpose |
|---|---|
| `read_memory` | Read project status (full or by section) |
| `write_memory` | Write/update a section in `project_status.md` |
| `log_decision` | Append structured decision entry to `decisions.yaml` |
| `read_decisions` | Retrieve past project decisions |
| `add_note` | Save a knowledge note with markdown and tags |
| `list_notes` | List all saved knowledge notes |
| `list_project_status` | Retrieve full project status overview |
| `search_documents` | Semantic RAG search over ingested documents |
| `ingest_documents` | Index all PDF/Markdown/TXT/DOCX files into ChromaDB |
| `delete_note` | Delete a knowledge note |

---

## 🧪 Evaluation Suite

To run automated evaluation against the live stack:
```bash
python3 evaluation/eval_retrieval.py
```
This tests:
1. System Health endpoints
2. Persistent memory write/read round-trip
3. Decision log append & retrieval
4. Knowledge notes creation & listing
5. Live ReAct loop with Qwen2.5:7b tool execution
