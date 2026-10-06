"""Loopback-only HTTP interface for local knowledge, memory and chat."""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .agent import Agent
from .config import Settings, local_model
from .library import Library
from .ollama import Ollama, OllamaUnavailable
from .store import Store


class RootInput(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    label: str = Field(default="", max_length=100)


class IndexInput(BaseModel):
    root_id: int | None = None


class SearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=8, ge=1, le=30)


class MemoryInput(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    kind: str = Field(default="note", max_length=40)
    project_id: int | None = None


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=6000)


class PlanInput(BaseModel):
    prompt: str = Field(default="", max_length=6000)


class SessionInput(BaseModel):
    title: str = Field(default="New conversation", max_length=120)
    project_id: int | None = None


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: int | None = None
    project_id: int | None = None
    document_id: int | None = None


class SettingsInput(BaseModel):
    chat_model: str | None = None
    embedding_model: str | None = None
    context_size: int | None = Field(default=None, ge=4096, le=16384)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = Store(settings.database_path)
    ollama = Ollama(settings)
    library = Library(settings, store, ollama.embed)
    agent = Agent(settings, store, library, ollama)
    app = FastAPI(title="LocalMind", version="0.1.0", docs_url="/api/docs", redoc_url=None)
    app.state.settings, app.state.store = settings, store
    app.state.ollama, app.state.library, app.state.agent = ollama, library, agent
    indexing = {"running": False, "root_id": None, "progress": {}, "result": None, "error": None}
    index_lock = threading.Lock()
    inference_lock = asyncio.Lock()
    static = Path(__file__).parent / "static"
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"])

    @app.middleware("http")
    async def protect_local_browser(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin:
            parsed = urlparse(origin)
            if parsed.scheme != "http" or parsed.netloc != request.headers.get("host"):
                return JSONResponse(status_code=403, content={"detail": "Only this app's local page may access its API."})
        if request.method in {"POST", "PUT", "PATCH"} and not request.headers.get("content-type", "").startswith("application/json"):
            return JSONResponse(status_code=415, content={"detail": "Use application/json for local API requests."})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        return response

    @app.exception_handler(ValueError)
    async def invalid_value(request, exc):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(OllamaUnavailable)
    async def unavailable(request, exc):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    def require_project(project_id):
        if project_id and not store.get_project(project_id):
            raise HTTPException(404, "Project not found")

    def require_session(session_id):
        session = next((s for s in store.list_sessions() if s["id"] == session_id), None)
        if session is None:
            raise HTTPException(404, "Conversation not found")
        return session

    def require_document(document_id):
        doc = store.get_document(document_id)
        if not doc:
            raise HTTPException(404, "Document not found")
        # Indexed snapshots can be read only while their source is still approved and unchanged.
        from .mcp_server import _document_snapshot
        return _document_snapshot(store, document_id)

    @app.get("/api/status")
    def status():
        with index_lock:
            index_status = dict(indexing)
        return {"app": "LocalMind", "version": "0.1.0", "edition": "windows", "local_only": True,
                "ollama": ollama.status(), "settings": settings.public(),
                "stats": store.stats(), "indexing": index_status}

    @app.get("/api/roots")
    def roots():
        return {"roots": store.list_roots()}

    @app.post("/api/roots", status_code=201)
    def add_root(body: RootInput):
        with index_lock:
            if indexing["running"]:
                raise HTTPException(409, "Wait for indexing to finish before changing folders.")
            return library.add_root(body.path, body.label)

    @app.delete("/api/roots/{root_id}")
    def remove_root(root_id: int):
        with index_lock:
            if indexing["running"]:
                raise HTTPException(409, "Wait for indexing to finish before removing a folder.")
            if not store.remove_root(root_id):
                raise HTTPException(404, "Folder not found")
        return {"deleted": True}

    def run_index(root_ids):
        results = []
        try:
            for root_id in root_ids:
                with index_lock:
                    indexing["root_id"] = root_id
                def progress(value):
                    with index_lock:
                        indexing["progress"] = value
                results.append(library.scan(root_id, progress))
            with index_lock:
                if len(results) == 1:
                    indexing["result"] = results[0]
                else:
                    indexing["result"] = {"indexed": sum(r.get("indexed", 0) for r in results),
                                          "unchanged": sum(r.get("unchanged", 0) for r in results),
                                          "errors": [e for r in results for e in r.get("errors", [])],
                                          "roots": results}
        except Exception as exc:
            with index_lock:
                indexing["error"] = str(exc)
        finally:
            with index_lock:
                indexing["running"] = False

    @app.post("/api/index", status_code=202)
    def index(body: IndexInput):
        root_ids = [r["id"] for r in store.list_roots()]
        if body.root_id:
            if body.root_id not in root_ids:
                raise HTTPException(404, "Folder not found")
            root_ids = [body.root_id]
        if not root_ids:
            raise HTTPException(400, "Add a folder first")
        with index_lock:
            if indexing["running"]:
                raise HTTPException(409, "Indexing is already running")
            indexing.update(running=True, root_id=body.root_id, progress={}, result=None, error=None)
        threading.Thread(target=run_index, args=(root_ids,), daemon=True).start()
        return {"started": True}

    @app.get("/api/documents")
    def documents(q: str = "", limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
        return {"documents": store.list_documents(q, limit, offset), "total": store.count_documents(q)}

    @app.get("/api/documents/{document_id}")
    def document(document_id: int):
        return require_document(document_id)

    @app.get("/api/documents/{document_id}/download")
    def download(document_id: int):
        doc = require_document(document_id)
        return Response(doc["text"], media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="document.txt"'})

    @app.post("/api/search")
    def search(body: SearchInput):
        return {"results": library.retrieve(body.query, body.limit)}

    @app.get("/api/memories")
    def memories(project_id: int | None = None, q: str = ""):
        return {"memories": store.list_memories(project_id, q)}

    @app.post("/api/memories", status_code=201)
    def add_memory(body: MemoryInput):
        require_project(body.project_id)
        if not body.content.strip():
            raise ValueError("Memory content must not be empty")
        return store.add_memory(body.content.strip(), body.kind, body.project_id)

    @app.delete("/api/memories/{memory_id}")
    def delete_memory(memory_id: int):
        if not store.delete_memory(memory_id):
            raise HTTPException(404, "Memory not found")
        return {"deleted": True}

    @app.put("/api/memories/{memory_id}")
    def update_memory(memory_id: int, body: MemoryInput):
        require_project(body.project_id)
        memory = store.update_memory(memory_id, body.content, body.kind, body.project_id)
        if not memory:
            raise HTTPException(404, "Memory not found")
        return memory

    @app.get("/api/projects")
    def projects():
        return {"projects": store.list_projects()}

    @app.post("/api/projects", status_code=201)
    def add_project(body: ProjectInput):
        if not body.name.strip():
            raise ValueError("Project name must not be empty")
        return store.create_project(body.name.strip(), body.description)

    @app.get("/api/projects/{project_id}")
    def project(project_id: int):
        require_project(project_id)
        data = store.get_project(project_id)
        plan = settings.data_dir / "projects" / str(project_id) / "PLAN.md"
        if plan.is_file():
            data = {**data, "plan": plan.read_text(encoding="utf-8"), "plan_path": str(plan)}
        return data

    @app.post("/api/projects/{project_id}/plan")
    async def plan(project_id: int, body: PlanInput):
        require_project(project_id)
        if inference_lock.locked():
            raise HTTPException(409, "The local model is busy. Wait for the current request to finish.")
        async with inference_lock:
            content = await agent.project_plan(store.get_project(project_id), body.prompt)
        if not content:
            raise HTTPException(503, "The local model returned an empty plan")
        path = settings.data_dir / "projects" / str(project_id) / "PLAN.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"content": content, "path": str(path)}

    @app.get("/api/sessions")
    def sessions():
        return {"sessions": store.list_sessions()}

    @app.post("/api/sessions", status_code=201)
    def add_session(body: SessionInput):
        require_project(body.project_id)
        return store.create_session(body.title, body.project_id)

    @app.get("/api/sessions/{session_id}/messages")
    def messages(session_id: int):
        require_session(session_id)
        return {"messages": store.get_messages(session_id)}

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(session_id: int):
        if inference_lock.locked():
            raise HTTPException(409, "Wait for the current conversation request to finish.")
        if not store.delete_session(session_id):
            raise HTTPException(404, "Conversation not found")
        return {"deleted": True}

    @app.post("/api/chat")
    async def chat(body: ChatInput):
        if not body.message.strip():
            raise ValueError("Message must not be empty")
        if inference_lock.locked():
            raise HTTPException(409, "The local model is busy. Wait for the current request to finish.")
        require_project(body.project_id)
        if body.document_id:
            require_document(body.document_id)
        if body.session_id:
            session = require_session(body.session_id)
            project_id = session.get("project_id")
        else:
            project_id = body.project_id
            session = store.create_session(body.message[:70], project_id)
        async with inference_lock:
            store.add_message(session["id"], "user", body.message)
            try:
                result = await agent.respond(session["id"], body.message, project_id, body.document_id)
            except ValueError:
                raise
            except OllamaUnavailable:
                raise
            except Exception as exc:
                # Preserve the user message, but never silently substitute cloud inference.
                raise HTTPException(503, f"Local assistant could not complete this request: {exc}") from exc
            store.add_message(session["id"], "assistant", result["content"], result.get("sources"), result.get("trace"))
        return {"session_id": session["id"], **result}

    @app.get("/api/settings")
    def get_settings():
        return settings.public()

    @app.put("/api/settings")
    async def update_settings(body: SettingsInput):
        if inference_lock.locked() or indexing["running"]:
            raise HTTPException(409, "Wait for the current request or indexing to finish before changing models.")
        changes = body.model_dump(exclude_none=True)
        for name in ("chat_model", "embedding_model"):
            if name in changes:
                changes[name] = local_model(changes[name])
        for name, value in changes.items():
            setattr(settings, name, value)
        settings.save()
        return settings.public()

    @app.get("/")
    def home():
        return FileResponse(static / "index.html")

    app.mount("/static", StaticFiles(directory=static, check_dir=False), name="static")
    return app


app = create_app()
