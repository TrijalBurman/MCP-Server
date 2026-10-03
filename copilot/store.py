"""Local, durable knowledge storage. No network or model calls live here."""

from __future__ import annotations

import heapq
import json
import math
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _bounded_limit(value: int, maximum: int = 100) -> int:
    return max(1, min(int(value), maximum))


class Store:
    """SQLite connections are short lived so API and MCP processes can share it."""

    def __init__(self, database_path: Path | str):
        self.database_path = Path(database_path).expanduser().resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS roots (
                    id INTEGER PRIMARY KEY, path TEXT NOT NULL UNIQUE,
                    label TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY, root_id INTEGER NOT NULL REFERENCES roots(id) ON DELETE CASCADE,
                    path TEXT NOT NULL UNIQUE, title TEXT NOT NULL, extension TEXT NOT NULL,
                    text TEXT NOT NULL, mtime_ns INTEGER NOT NULL, size INTEGER NOT NULL,
                    embedding_model TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    text TEXT NOT NULL, start INTEGER NOT NULL, end INTEGER NOT NULL, page INTEGER,
                    embedding BLOB, embedding_model TEXT NOT NULL DEFAULT '', embedding_dim INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
                CREATE INDEX IF NOT EXISTS chunks_model ON chunks(embedding_model);
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, title, path, tokenize='unicode61');
                CREATE TRIGGER IF NOT EXISTS chunks_insert AFTER INSERT ON chunks BEGIN
                    INSERT INTO chunks_fts(rowid, text, title, path)
                    SELECT new.id, new.text, title, path FROM documents WHERE id = new.document_id;
                END;
                CREATE TRIGGER IF NOT EXISTS chunks_delete AFTER DELETE ON chunks BEGIN
                    DELETE FROM chunks_fts WHERE rowid = old.id;
                END;
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY, content TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'note',
                    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY, title TEXT NOT NULL, project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL, content TEXT NOT NULL, sources TEXT NOT NULL DEFAULT '[]',
                    trace TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS messages_session ON messages(session_id, id);
                CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(content, tokenize='unicode61');
                CREATE TRIGGER IF NOT EXISTS messages_insert AFTER INSERT ON messages BEGIN
                    INSERT INTO messages_fts(rowid,content) VALUES(new.id,new.content);
                END;
                CREATE TRIGGER IF NOT EXISTS messages_delete AFTER DELETE ON messages BEGIN
                    DELETE FROM messages_fts WHERE rowid=old.id;
                END;
                PRAGMA user_version=1;
            """)
            if not db.execute("SELECT 1 FROM messages_fts LIMIT 1").fetchone():
                db.execute("INSERT INTO messages_fts(rowid,content) SELECT id,content FROM messages")

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(str(self.database_path), timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=30000")
        try:
            with db:
                yield db
        finally:
            db.close()

    def stats(self) -> dict:
        with self._connection() as db:
            return {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                    for table in ("documents", "chunks", "memories", "projects", "roots", "sessions")}

    def list_roots(self) -> list[dict]:
        with self._connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM roots ORDER BY id")]

    def add_root(self, path: Path | str, label: str = "") -> dict:
        canonical = str(Path(path).expanduser().resolve())
        with self._connection() as db:
            db.execute("INSERT OR IGNORE INTO roots(path,label,created_at) VALUES(?,?,?)",
                       (canonical, str(label).strip()[:200], _now()))
            return dict(db.execute("SELECT * FROM roots WHERE path=?", (canonical,)).fetchone())

    def remove_root(self, root_id: int) -> bool:
        with self._connection() as db:
            return db.execute("DELETE FROM roots WHERE id=?", (root_id,)).rowcount > 0

    @staticmethod
    def _document_select() -> str:
        return """SELECT d.id,d.root_id,d.path,d.title,d.extension,d.size,d.mtime_ns,d.updated_at,
                         count(c.id) AS chunk_count
                  FROM documents d LEFT JOIN chunks c ON c.document_id=d.id"""

    @staticmethod
    def _document_filter(query: str) -> tuple[str, list[str]]:
        if query.strip():
            # Escape LIKE wildcards: entering '%' should search for a literal percent sign.
            term = query.strip()[:512].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            return " WHERE d.title LIKE ? ESCAPE '\\' OR d.path LIKE ? ESCAPE '\\'", [f"%{term}%", f"%{term}%"]
        return "", []

    def count_documents(self, query: str = "") -> int:
        clause, params = self._document_filter(query)
        with self._connection() as db:
            return db.execute("SELECT count(*) FROM documents d" + clause, params).fetchone()[0]

    def list_documents(self, query: str = "", limit: int = 100, offset: int = 0) -> list[dict]:
        clause, filters = self._document_filter(query)
        sql = self._document_select() + clause
        params: list[Any] = list(filters)
        sql += " GROUP BY d.id ORDER BY d.title COLLATE NOCASE,d.id LIMIT ? OFFSET ?"
        params.extend([_bounded_limit(limit, 500), max(0, int(offset))])
        with self._connection() as db:
            return [dict(row) for row in db.execute(sql, params)]

    def get_document(self, document_id: int) -> dict | None:
        with self._connection() as db:
            row = db.execute(self._document_select() + " WHERE d.id=? GROUP BY d.id", (document_id,)).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["text"] = db.execute("SELECT text FROM documents WHERE id=?", (document_id,)).fetchone()[0]
            return result

    def get_document_chunks(self, document_id: int) -> list[dict]:
        """Offsets used to backfill embeddings without re-extracting an unchanged file."""
        with self._connection() as db:
            return [dict(row) for row in db.execute(
                "SELECT text,start,end,page FROM chunks WHERE document_id=? ORDER BY id", (document_id,))]

    def document_signature(self, path: Path | str) -> dict | None:
        with self._connection() as db:
            row = db.execute("""SELECT d.id,d.root_id,d.path,d.mtime_ns,d.size,d.embedding_model,
                       count(c.id) AS chunk_count,
                       count(c.embedding) AS embedded_count
                       FROM documents d LEFT JOIN chunks c ON c.document_id=d.id
                       WHERE d.path=? GROUP BY d.id""", (str(path),)).fetchone()
            return dict(row) if row else None

    def upsert_document(self, root_id: int, path: Path | str, title: str, text: str,
                        mtime_ns: int, size: int, chunks: list[dict], embedding_model: str = "") -> dict:
        import numpy as np

        canonical = str(Path(path).resolve())
        with self._connection() as db:
            if db.execute("SELECT 1 FROM roots WHERE id=?", (root_id,)).fetchone() is None:
                raise ValueError("The selected folder no longer exists in the library.")
            existing = db.execute("SELECT id,root_id FROM documents WHERE path=?", (canonical,)).fetchone()
            if existing and existing["root_id"] != root_id:
                raise ValueError("This file already belongs to another indexed folder.")
            db.execute("""INSERT INTO documents(root_id,path,title,extension,text,mtime_ns,size,embedding_model,updated_at)
                          VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET
                          title=excluded.title,extension=excluded.extension,text=excluded.text,
                          mtime_ns=excluded.mtime_ns,size=excluded.size,
                          embedding_model=excluded.embedding_model,updated_at=excluded.updated_at""",
                       (root_id, canonical, str(title), Path(canonical).suffix.lower(), str(text),
                        int(mtime_ns), int(size), str(embedding_model), _now()))
            document_id = db.execute("SELECT id FROM documents WHERE path=?", (canonical,)).fetchone()[0]
            db.execute("DELETE FROM chunks WHERE document_id=?", (document_id,))
            rows = []
            vector_dim = None
            for chunk in chunks:
                start, end = int(chunk["start"]), int(chunk["end"])
                if not 0 <= start <= end <= len(text) or chunk["text"] != text[start:end]:
                    raise ValueError("Document chunks must match their stored text offsets.")
                vector_blob, dim = None, 0
                if chunk.get("embedding") is not None:
                    vector = np.asarray(chunk["embedding"], dtype="<f4")
                    if vector.ndim != 1 or not 0 < vector.size <= 8192 or not np.isfinite(vector).all():
                        raise ValueError("An embedding must be a finite one-dimensional vector.")
                    dim = int(vector.size)
                    if vector_dim not in (None, dim):
                        raise ValueError("Embedding dimensions must agree within a document.")
                    vector_dim = dim
                    vector_blob = vector.tobytes()
                rows.append((document_id, chunk["text"], start, end, chunk.get("page"), vector_blob,
                             str(embedding_model) if vector_blob is not None else "", dim))
            db.executemany("""INSERT INTO chunks(document_id,text,start,end,page,embedding,embedding_model,embedding_dim)
                              VALUES(?,?,?,?,?,?,?,?)""", rows)
            row = db.execute(self._document_select() + " WHERE d.id=? GROUP BY d.id", (document_id,)).fetchone()
            return dict(row)

    def prune_documents(self, root_id: int, seen_paths: Iterable[str]) -> int:
        # A temporary table avoids SQLite's argument-count limit on large libraries.
        with self._connection() as db:
            db.execute("CREATE TEMP TABLE seen_paths(path TEXT PRIMARY KEY)")
            db.executemany("INSERT OR IGNORE INTO seen_paths(path) VALUES(?)", ((str(p),) for p in seen_paths))
            return db.execute("""DELETE FROM documents WHERE root_id=? AND
                                 NOT EXISTS(SELECT 1 FROM seen_paths WHERE seen_paths.path=documents.path)""",
                              (root_id,)).rowcount

    def search(self, query: str, limit: int = 8, query_embedding=None, embedding_model: str = "") -> list[dict]:
        limit = _bounded_limit(limit, 40)
        query = str(query).strip()[:1024]
        if not query:
            return []
        tokens = list(dict.fromkeys(re.findall(r"[^\W_]+", query, flags=re.UNICODE)))[:24]
        match = " OR ".join('"' + token.replace('"', '""') + '"' for token in tokens)
        candidates: dict[int, float] = {}
        ranking_depth = min(160, max(40, limit * 4))
        with self._connection() as db:
            if match:
                lexical = db.execute("""SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ?
                                      ORDER BY bm25(chunks_fts,1.0,2.0,0.3),rowid LIMIT ?""",
                                     (match, ranking_depth)).fetchall()
                for rank, row in enumerate(lexical, 1):
                    candidates[row[0]] = 1.0 / (60 + rank)
            if query_embedding is not None and embedding_model:
                import numpy as np

                vector = np.asarray(query_embedding, dtype="<f4")
                norm = float(np.linalg.norm(vector)) if vector.ndim == 1 else 0
                if 0 < vector.size <= 8192 and norm > 0 and math.isfinite(norm) and np.isfinite(vector).all():
                    best: list[tuple[float, int]] = []
                    cursor = db.execute("""SELECT id,embedding FROM chunks WHERE embedding_model=?
                                          AND embedding_dim=? AND embedding IS NOT NULL""",
                                        (embedding_model, int(vector.size)))
                    while True:
                        batch = cursor.fetchmany(128)
                        if not batch:
                            break
                        # Stream vectors; keep only a bounded heap of the best candidates.
                        for row in batch:
                            other = np.frombuffer(row["embedding"], dtype="<f4")
                            other_norm = float(np.linalg.norm(other))
                            if other.size != vector.size or other_norm <= 0:
                                continue
                            similarity = float(np.dot(vector, other) / (norm * other_norm))
                            if not math.isfinite(similarity) or similarity <= 0:
                                continue
                            item = (similarity, row["id"])
                            if len(best) < ranking_depth:
                                heapq.heappush(best, item)
                            elif item > best[0]:
                                heapq.heapreplace(best, item)
                    for rank, (_, chunk_id) in enumerate(sorted(best, reverse=True), 1):
                        candidates[chunk_id] = candidates.get(chunk_id, 0) + 1.0 / (60 + rank)
            selected = sorted(candidates, key=lambda key: (-candidates[key], key))[:limit]
            if not selected:
                return []
            placeholders = ",".join("?" for _ in selected)
            rows = db.execute(f"""SELECT d.id AS document_id,c.id AS chunk_id,d.title,d.path,
                                  c.text,c.start,c.end,c.page FROM chunks c JOIN documents d ON d.id=c.document_id
                                  WHERE c.id IN ({placeholders})""", selected).fetchall()
            found = {row["chunk_id"]: dict(row) for row in rows}
            return [{**found[key], "score": round(candidates[key], 6)} for key in selected if key in found]

    def list_memories(self, project_id: int | None = None, query: str = "") -> list[dict]:
        clauses, params = [], []
        if project_id is not None:
            clauses.append("project_id=?")
            params.append(project_id)
        if query.strip():
            clauses.append("instr(lower(content),lower(?))>0")
            params.append(query.strip()[:512])
        sql = "SELECT * FROM memories" + (" WHERE " + " AND ".join(clauses) if clauses else "")
        with self._connection() as db:
            return [dict(row) for row in db.execute(sql + " ORDER BY id DESC LIMIT 1000", params)]

    def _validate_project(self, db, project_id):
        if project_id is not None and db.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone() is None:
            raise ValueError("Project not found.")

    def add_memory(self, content: str, kind: str = "note", project_id: int | None = None) -> dict:
        content = str(content).strip()
        if not content or len(content) > 20000:
            raise ValueError("Memory must contain between 1 and 20,000 characters.")
        with self._connection() as db:
            self._validate_project(db, project_id)
            cursor = db.execute("INSERT INTO memories(content,kind,project_id,created_at) VALUES(?,?,?,?)",
                                (content, str(kind).strip()[:80] or "note", project_id, _now()))
            return dict(db.execute("SELECT * FROM memories WHERE id=?", (cursor.lastrowid,)).fetchone())

    def update_memory(self, id: int, content: str, kind: str = "note",
                      project_id: int | None = None) -> dict | None:
        content = str(content).strip()
        if not content or len(content) > 20000:
            raise ValueError("Memory must contain between 1 and 20,000 characters.")
        with self._connection() as db:
            self._validate_project(db, project_id)
            cursor = db.execute("UPDATE memories SET content=?,kind=?,project_id=? WHERE id=?",
                                (content, str(kind).strip()[:80] or "note", project_id, id))
            if not cursor.rowcount:
                return None
            return dict(db.execute("SELECT * FROM memories WHERE id=?", (id,)).fetchone())

    def delete_memory(self, id: int) -> bool:
        with self._connection() as db:
            return db.execute("DELETE FROM memories WHERE id=?", (id,)).rowcount > 0

    def list_projects(self) -> list[dict]:
        with self._connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM projects ORDER BY id DESC")]

    def create_project(self, name: str, description: str = "") -> dict:
        name = str(name).strip()
        if not name or len(name) > 200:
            raise ValueError("Project name must contain between 1 and 200 characters.")
        with self._connection() as db:
            cursor = db.execute("INSERT INTO projects(name,description,created_at) VALUES(?,?,?)",
                                (name, str(description)[:20000], _now()))
            return dict(db.execute("SELECT * FROM projects WHERE id=?", (cursor.lastrowid,)).fetchone())

    def get_project(self, id: int) -> dict | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM projects WHERE id=?", (id,)).fetchone()
            return dict(row) if row else None

    def list_sessions(self) -> list[dict]:
        with self._connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM sessions ORDER BY id DESC")]

    def create_session(self, title: str = "New conversation", project_id: int | None = None) -> dict:
        with self._connection() as db:
            self._validate_project(db, project_id)
            cursor = db.execute("INSERT INTO sessions(title,project_id,created_at) VALUES(?,?,?)",
                                (str(title).strip()[:200] or "New conversation", project_id, _now()))
            return dict(db.execute("SELECT * FROM sessions WHERE id=?", (cursor.lastrowid,)).fetchone())

    @staticmethod
    def _message(row) -> dict:
        result = dict(row)
        result["sources"] = json.loads(result["sources"])
        result["trace"] = json.loads(result["trace"])
        return result

    def get_messages(self, session_id: int) -> list[dict]:
        with self._connection() as db:
            return [self._message(row) for row in db.execute(
                "SELECT id,role,content,sources,trace,created_at FROM messages WHERE session_id=? ORDER BY id", (session_id,))]

    def search_messages(self, query: str, limit: int = 6, project_id: int | None = None) -> list[dict]:
        tokens = list(dict.fromkeys(re.findall(r"[^\W_]+", str(query)[:1024], flags=re.UNICODE)))[:24]
        if not tokens:
            return []
        match = " OR ".join('"' + token.replace('"', '""') + '"' for token in tokens)
        sql = """SELECT s.id AS session_id,s.title AS session_title,m.role,m.content,m.created_at
                 FROM messages_fts JOIN messages m ON m.id=messages_fts.rowid
                 JOIN sessions s ON s.id=m.session_id
                 WHERE messages_fts MATCH ? AND m.role IN ('user','assistant')"""
        params: list[Any] = [match]
        if project_id is not None:
            sql += " AND s.project_id=?"
            params.append(project_id)
        sql += " ORDER BY bm25(messages_fts),m.id DESC LIMIT ?"
        params.append(_bounded_limit(limit, 40))
        with self._connection() as db:
            return [dict(row) for row in db.execute(sql, params)]

    def add_message(self, session_id: int, role: str, content: str, sources=None, trace=None) -> dict:
        if role not in {"user", "assistant", "system", "tool"}:
            raise ValueError("Unknown message role.")
        with self._connection() as db:
            if db.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone() is None:
                raise ValueError("Conversation not found.")
            cursor = db.execute("""INSERT INTO messages(session_id,role,content,sources,trace,created_at)
                                   VALUES(?,?,?,?,?,?)""",
                                (session_id, role, str(content), json.dumps(sources or [], ensure_ascii=False),
                                 json.dumps(trace or [], ensure_ascii=False), _now()))
            return self._message(db.execute("SELECT id,role,content,sources,trace,created_at FROM messages WHERE id=?",
                                            (cursor.lastrowid,)).fetchone())

    def delete_session(self, id: int) -> bool:
        with self._connection() as db:
            return db.execute("DELETE FROM sessions WHERE id=?", (id,)).rowcount > 0
