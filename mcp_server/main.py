from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

MODULE_DIR = Path(__file__).resolve().parent
# In Docker this file lives at /app/main.py; locally it lives in mcp_server/.
PROJECT_ROOT = MODULE_DIR.parent if MODULE_DIR.name == "mcp_server" else MODULE_DIR
DATA = Path(__import__("os").environ.get("DATA_DIR", PROJECT_ROOT / "data"))
MEMORY, NOTES, DOCS = DATA / "memory", DATA / "memory" / "notes", DATA / "documents"
STATUS, DECISIONS = MEMORY / "project_status.md", MEMORY / "decisions.yaml"
for folder in (MEMORY, NOTES, DOCS): folder.mkdir(parents=True, exist_ok=True)
if not STATUS.exists(): STATUS.write_text("# Project Status\n", encoding="utf-8")
if not DECISIONS.exists(): DECISIONS.write_text("decisions: []\n", encoding="utf-8")

app = FastAPI(title="Local Knowledge Copilot MCP Server")

class ToolCall(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)

TOOLS = [
 {"name":"read_memory","description":"Read project status, optionally one section.","parameters":{"section":"string?"}},
 {"name":"write_memory","description":"Create or replace a project status section.","parameters":{"section":"string","content":"string"}},
 {"name":"log_decision","description":"Persist an architectural decision.","parameters":{"title":"string","rationale":"string","outcome":"string?"}},
 {"name":"read_decisions","description":"Read recent decisions.","parameters":{"limit":"integer?"}},
 {"name":"add_note","description":"Save a tagged Markdown note.","parameters":{"title":"string","body":"string","tags":"string[]?"}},
 {"name":"list_notes","description":"List saved knowledge notes.","parameters":{}},
 {"name":"delete_note","description":"Delete a note by title.","parameters":{"title":"string"}},
 {"name":"list_project_status","description":"Read the full project status.","parameters":{}},
 {"name":"ingest_documents","description":"Index local PDF, DOCX, Markdown, and TXT files.","parameters":{}},
 {"name":"search_documents","description":"Search indexed local documents.","parameters":{"query":"string","top_k":"integer?"}},
]

def _slug(value: str) -> str: return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "note"
def _read_decisions() -> list[dict]: return (yaml.safe_load(DECISIONS.read_text()) or {}).get("decisions", [])
def _save_decisions(items: list[dict]) -> None: DECISIONS.write_text(yaml.safe_dump({"decisions":items}, sort_keys=False), encoding="utf-8")

def _read_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        import fitz
        return "\n".join(page.get_text() for page in fitz.open(path))
    if path.suffix.lower() == ".docx":
        from docx import Document
        return "\n".join(p.text for p in Document(path).paragraphs)
    return path.read_text(encoding="utf-8", errors="ignore")

def _chunks(text: str, size: int = 500, overlap: int = 100) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size - overlap) if text[i:i + size].strip()]

def _collection():
    import chromadb
    return chromadb.PersistentClient(path=str(DATA / "vector_db")).get_or_create_collection("documents", metadata={"hnsw:space":"cosine"})

@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/mcp/tools/list")
def list_tools(): return {"tools": TOOLS}

@app.post("/mcp/tools/call")
def call_tool(call: ToolCall):
    a, tool = call.arguments, call.tool
    if tool in {"read_memory", "list_project_status"}:
        text = STATUS.read_text(encoding="utf-8")
        if tool == "read_memory" and a.get("section"):
            pattern = rf"(?ms)^## {re.escape(a['section'])}\s*$\n?(.*?)(?=^## |\Z)"
            match = re.search(pattern, text)
            return {"section": a["section"], "content": match.group(1).strip() if match else ""}
        return {"content": text}
    if tool == "write_memory":
        section, content = a["section"].strip(), a["content"].strip()
        text = STATUS.read_text(encoding="utf-8"); block = f"## {section}\n{content}\n"
        pattern = rf"(?ms)^## {re.escape(section)}\s*$\n?.*?(?=^## |\Z)"
        STATUS.write_text(re.sub(pattern, block, text).rstrip() + "\n" if re.search(pattern, text) else text.rstrip()+"\n\n"+block, encoding="utf-8")
        return {"success": True, "section": section}
    if tool == "log_decision":
        rows = _read_decisions(); entry = {"id": max([x.get("id",0) for x in rows], default=0)+1, "timestamp":datetime.now(timezone.utc).isoformat(), "title":a["title"], "rationale":a["rationale"], "outcome":a.get("outcome","")}
        rows.append(entry); _save_decisions(rows); return {"success":True,"entry":entry}
    if tool == "read_decisions": return {"decisions": _read_decisions()[-int(a.get("limit",20)):][::-1]}
    if tool == "add_note":
        title, tags = a["title"], a.get("tags", [])
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        path = NOTES / f"{stamp}_{_slug(title)}.md"
        path.write_text(f"---\ntitle: {title}\ntags: {yaml.safe_dump(tags, default_flow_style=True).strip()}\ncreated: {datetime.now(timezone.utc).isoformat()}\n---\n\n{a['body'].strip()}\n", encoding="utf-8")
        return {"success":True,"filename":path.name}
    if tool == "list_notes":
        notes=[]
        for path in NOTES.glob("*.md"):
            raw=path.read_text(encoding="utf-8"); front=re.match(r"(?s)^---\n(.*?)\n---",raw)
            notes.append({"filename":path.name, **(yaml.safe_load(front.group(1)) if front else {})})
        return {"notes":sorted(notes,key=lambda x:x["filename"],reverse=True)}
    if tool == "delete_note":
        candidates=list(NOTES.glob(f"*_{_slug(a['title'])}.md"))
        if not candidates: raise HTTPException(404,"Note not found")
        candidates[0].unlink(); return {"success":True}
    if tool == "ingest_documents":
        try: collection=_collection()
        except Exception as exc: return {"error":f"Vector store unavailable: {exc}"}
        count=0
        for path in DOCS.iterdir():
            if path.suffix.lower() not in {".pdf",".docx",".md",".txt"}: continue
            collection.delete(where={"source":path.name})
            chunks=_chunks(_read_text(path))
            if chunks:
                ids=[f"{path.name}:{i}" for i in range(len(chunks))]
                collection.add(ids=ids, documents=chunks, metadatas=[{"source":path.name,"chunk":i} for i in range(len(chunks))]); count+=len(chunks)
        return {"success":True,"chunks_indexed":count}
    if tool == "search_documents":
        try:
            result=_collection().query(query_texts=[a["query"]], n_results=int(a.get("top_k",5)), include=["documents","metadatas","distances"])
            return {"results":[{"text":d,"source":m["source"],"score":round(1-float(s),3)} for d,m,s in zip(result["documents"][0],result["metadatas"][0],result["distances"][0])]}
        except Exception: return {"results":[],"message":"No documents indexed yet. Use ingest_documents first."}
    raise HTTPException(404, f"Unknown tool: {tool}")
