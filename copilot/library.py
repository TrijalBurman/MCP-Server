"""Explicitly approved local folders, bounded extraction, and incremental indexing."""

from __future__ import annotations

import io
import os
import stat
import zipfile
from pathlib import Path
from typing import Callable
from xml.etree import ElementTree

from .filesystem import (
    checked_source_stat,
    has_redirects,
    is_hidden_or_system,
    read_windows_file,
    validate_native_windows_root,
    validate_windows_path,
)
from .store import Store

TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".json", ".jsonl", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".log", ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".htm",
    ".css", ".scss", ".sql", ".java", ".c", ".cc", ".cpp", ".h", ".hpp", ".rs", ".go",
    ".sh", ".bash", ".ps1", ".rb", ".php", ".swift", ".kt", ".kts", ".r", ".m", ".tex",
    ".xml", ".svelte", ".vue", ".ipynb", ".org", ".adoc",
}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | {".pdf", ".docx"}
TEXT_FILENAMES = {"readme", "license", "makefile", "dockerfile", "notes"}
IGNORED_DIRECTORIES = {
    "node_modules", "venv", "env", "__pycache__", "site-packages", "vendor", "target", "dist",
    "build", "coverage", "htmlcov", "lost+found", "$recycle.bin", "system volume information",
    "windows", "program files", "program files (x86)", "programdata", "appdata",
}
MAX_EXTRACTED_CHARACTERS = 5_000_000
MAX_PDF_PAGES = 2000


def _inside(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _is_secret(name: str) -> bool:
    lowered = name.lower()
    stem = Path(lowered).stem.replace("-", "_")
    return (
        lowered.startswith(".")
        or stem in {"id_rsa", "id_ed25519", "id_dsa", "authorized_keys", "known_hosts", "credentials",
                    "credential", "secrets", "secret", "tokens", "token", "passwords", "password"}
        or stem.startswith(("credentials_", "secrets_", "service_account", "serviceaccount"))
        or stem.endswith(("_credentials", "_secrets", "_private_key"))
        or Path(lowered).suffix in {".pem", ".key", ".p12", ".pfx", ".kdbx", ".keystore"}
    )


def _has_symlink(path: Path) -> bool:
    # Includes Windows junctions and all reparse-point types.
    return has_redirects(path)


def chunk_text(text: str, pages: list[tuple[int, int, int | None]] | None = None,
               chunk_size: int = 1800, overlap: int = 200) -> list[dict]:
    """Keep exact offsets and never combine separate PDF pages into one chunk."""
    if chunk_size < 100 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Invalid chunk bounds.")
    chunks = []
    for page_start, page_end, page in pages or [(0, len(text), None)]:
        start = page_start
        while start < page_end:
            end = min(start + chunk_size, page_end)
            if end < page_end:
                lower = start + chunk_size // 2
                boundary = max(text.rfind("\n", lower, end), text.rfind(". ", lower, end))
                if boundary >= lower:
                    end = boundary + 1
            content = text[start:end]
            if content.strip():
                chunks.append({"text": content, "start": start, "end": end, "page": page})
            if end == page_end:
                break
            start = max(start + 1, end - overlap)
    return chunks


class Library:
    def __init__(self, settings, store: Store, embedder: Callable | None = None):
        self.settings = settings
        self.store = store
        self.embedder = embedder
        self.data_dir = Path(settings.data_dir).expanduser().resolve()

    def _validate_root(self, path: str | Path) -> Path:
        if os.name == "nt":
            # Reject UNC/device namespaces before any filesystem query can
            # contact a network share. Drive-relative C:folder is ambiguous.
            raw = os.fspath(path)
            if raw.startswith(("\\\\", "//")) or (len(raw) >= 2 and raw[1] == ":" and raw[2:3] not in {"\\", "/"}):
                validate_windows_path(raw)
        source = Path(path).expanduser().absolute()
        if os.name == "nt":
            validate_native_windows_root(source)
        if _has_symlink(source):
            raise ValueError("Choose the actual folder path; symbolic-link folders, junctions and reparse points are excluded.")
        canonical = source.resolve()
        if not canonical.is_dir():
            raise ValueError("Choose an existing local folder.")
        if _inside(canonical, self.data_dir):
            raise ValueError("The copilot's own data directory cannot be indexed.")
        if os.name != "nt":
            protected = ("/bin", "/sbin", "/usr", "/etc", "/lib", "/lib64", "/proc", "/sys", "/dev", "/boot")
            if canonical == Path("/") or any(_inside(canonical, Path(p)) for p in protected):
                raise ValueError("System folders cannot be selected. Choose a documents folder or mounted drive.")
            if _inside(canonical, Path("/run")) and not _inside(canonical, Path("/run/media")):
                raise ValueError("Choose a documents folder or mounted drive, rather than a system runtime folder.")
        return canonical

    def add_root(self, path: str | Path, label: str = "") -> dict:
        canonical = self._validate_root(path)
        for existing in self.store.list_roots():
            other = Path(existing["path"])
            if canonical == other:
                return existing
            if _inside(canonical, other) or _inside(other, canonical):
                raise ValueError("This folder overlaps an approved folder. Remove that folder before changing the scope.")
        return self.store.add_root(canonical, label or canonical.name)

    def _ignore_directory(self, path: Path) -> bool:
        return (path.name.startswith(".") or path.name.lower() in IGNORED_DIRECTORIES
                or _has_symlink(path) or is_hidden_or_system(path) or _inside(path.resolve(), self.data_dir))

    def _read_file(self, path: Path, root: Path) -> tuple[bytes, os.stat_result]:
        """Open each path component without following links, including concurrent replacements."""
        if os.name == "nt":
            return read_windows_file(path, root, self.settings.max_file_bytes)
        relative = path.relative_to(root)
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        directory_flag = getattr(os, "O_DIRECTORY", 0)
        directory_fd = os.open(root, os.O_RDONLY | directory_flag | nofollow)
        try:
            for component in relative.parts[:-1]:
                child_fd = os.open(component, os.O_RDONLY | directory_flag | nofollow, dir_fd=directory_fd)
                os.close(directory_fd)
                directory_fd = child_fd
            file_fd = os.open(relative.name, os.O_RDONLY | nofollow, dir_fd=directory_fd)
            with os.fdopen(file_fd, "rb") as source:
                before = os.fstat(source.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise ValueError("Only regular files can be indexed.")
                if before.st_size > self.settings.max_file_bytes:
                    raise ValueError("File exceeds the configured size limit.")
                content = source.read(self.settings.max_file_bytes + 1)
                after = os.fstat(source.fileno())
                if len(content) > self.settings.max_file_bytes:
                    raise ValueError("File exceeds the configured size limit.")
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError("The file changed during indexing; rescan after saving it.")
                return content, after
        finally:
            os.close(directory_fd)

    @staticmethod
    def _extract_text(path: Path, data: bytes) -> tuple[str, list[tuple[int, int, int | None]]]:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted and not reader.decrypt(""):
                raise ValueError("Password-protected PDF; export an unlocked local copy to index it.")
            if len(reader.pages) > MAX_PDF_PAGES:
                raise ValueError(f"PDF exceeds the {MAX_PDF_PAGES:,}-page extraction limit.")
            parts, pages, position = [], [], 0
            for number, page in enumerate(reader.pages, 1):
                content = page.extract_text() or ""
                if position + len(content) > MAX_EXTRACTED_CHARACTERS:
                    raise ValueError("Extracted document text exceeds the 5-million-character limit.")
                parts.append(content)
                pages.append((position, position + len(content), number))
                position += len(content) + 2
            text = "\n\n".join(parts)
            if not text.strip():
                raise ValueError("PDF has no extractable text. Scanned images require local OCR before indexing.")
            return text, pages
        if suffix == ".docx":
            namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            paragraphs = []
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = archive.namelist()
                if "word/document.xml" not in names:
                    raise ValueError("DOCX is missing its document body.")
                members = ["word/document.xml"] + sorted(
                    name for name in names if name.startswith(("word/header", "word/footer")) and name.endswith(".xml"))
                members += [name for name in ("word/footnotes.xml", "word/endnotes.xml") if name in names]
                extracted = 0
                for name in members:
                    if archive.getinfo(name).file_size > MAX_EXTRACTED_CHARACTERS:
                        raise ValueError("DOCX XML exceeds the safe extraction limit.")
                    document = ElementTree.fromstring(archive.read(name))
                    for paragraph in document.iter(namespace + "p"):
                        pieces = []
                        for element in paragraph.iter():
                            if element.tag == namespace + "t":
                                pieces.append(element.text or "")
                            elif element.tag == namespace + "tab":
                                pieces.append("\t")
                            elif element.tag in {namespace + "br", namespace + "cr"}:
                                pieces.append("\n")
                        content = "".join(pieces)
                        extracted += len(content) + 1
                        if extracted > MAX_EXTRACTED_CHARACTERS:
                            raise ValueError("Extracted document text exceeds the 5-million-character limit.")
                        paragraphs.append(content)
            text = "\n".join(paragraphs)
        else:
            if data.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
                text = data.decode("utf-32")
            elif data.startswith((b"\xff\xfe", b"\xfe\xff")):
                text = data.decode("utf-16")
            else:
                if b"\x00" in data[:8192]:
                    raise ValueError("This file contains binary data, rather than readable text.")
                try:
                    text = data.decode("utf-8-sig")
                except UnicodeDecodeError:
                    text = data.decode("cp1252")
            sample = text[:8192]
            if sample and sum(ord(char) < 32 and char not in "\t\n\r\f" for char in sample) / len(sample) > .01:
                raise ValueError("This file contains binary control characters.")
            text = text.replace("\r\n", "\n")
        if len(text) > MAX_EXTRACTED_CHARACTERS:
            raise ValueError("Extracted document text exceeds the 5-million-character limit.")
        return text, [(0, len(text), None)]

    def scan(self, root_id: int, progress: Callable | None = None) -> dict:
        selected = next((item for item in self.store.list_roots() if item["id"] == root_id), None)
        if selected is None:
            raise ValueError("Approved folder not found.")
        root = self._validate_root(selected["path"])
        result = {"indexed": 0, "unchanged": 0, "removed": 0, "skipped": 0, "errors": [], "embedded": 0}
        seen: set[str] = set()
        complete, examined = True, 0
        embed_available = self.embedder is not None
        model = str(self.settings.embedding_model)

        def error(path, message):
            if len(result["errors"]) < 100:
                result["errors"].append({"path": str(path), "error": str(message)[:500]})
            result["error_count"] = result.get("error_count", 0) + 1

        def notify(path=None):
            if progress:
                progress({"root_id": root_id, "current_path": str(path or root), **result,
                          "errors": list(result["errors"])})

        def traversal_error(exc):
            nonlocal complete
            complete = False
            error(exc.filename or root, f"Folder could not be read: {exc.strerror or exc}")

        def embed(chunks):
            nonlocal embed_available
            if not embed_available or not chunks:
                return ""
            try:
                vectors = []
                for offset in range(0, len(chunks), 16):
                    batch = chunks[offset:offset + 16]
                    returned = self.embedder([chunk["text"] for chunk in batch])
                    if len(returned) != len(batch):
                        raise RuntimeError("The embedding model returned an unexpected number of vectors.")
                    vectors.extend(returned)
                import numpy as np

                dimensions = set()
                for vector in vectors:
                    values = np.asarray(vector, dtype="<f4")
                    if values.ndim != 1 or not 0 < values.size <= 8192 or not np.isfinite(values).all():
                        raise RuntimeError("The embedding model returned an invalid vector.")
                    dimensions.add(values.size)
                if len(dimensions) > 1:
                    raise RuntimeError("The embedding model returned inconsistent vector sizes.")
                # Do not retain a partially embedded file on an interrupted model call.
                for chunk, vector in zip(chunks, vectors):
                    chunk["embedding"] = vector
                return model
            except Exception as exc:
                embed_available = False
                result["embedding_warning"] = f"Local embeddings unavailable; keyword search remains available. {str(exc)[:300]}"
                return ""

        notify()
        for current, folders, files in os.walk(root, topdown=True, followlinks=False, onerror=traversal_error):
            current_path = Path(current)
            folders[:] = sorted(name for name in folders if not self._ignore_directory(current_path / name))
            for name in sorted(files):
                path = current_path / name
                if _is_secret(name) or (path.suffix.lower() not in SUPPORTED_EXTENSIONS and name.lower() not in TEXT_FILENAMES):
                    result["skipped"] += 1
                    continue
                if examined >= self.settings.max_files:
                    complete = False
                    result["incomplete"] = True
                    error(root, f"The {self.settings.max_files:,}-file scan limit was reached. Select smaller folders.")
                    break
                examined += 1
                try:
                    if _has_symlink(path) or not _inside(path.resolve(), root):
                        result["skipped"] += 1
                        continue
                    if is_hidden_or_system(path):
                        result["skipped"] += 1
                        continue
                    metadata = checked_source_stat(path, root) if os.name == "nt" else path.stat(follow_symlinks=False)
                    if not stat.S_ISREG(metadata.st_mode):
                        result["skipped"] += 1
                        continue
                    canonical = str(path.resolve())
                    seen.add(canonical)
                    if metadata.st_size > self.settings.max_file_bytes:
                        result["skipped"] += 1
                        error(path, f"File exceeds the {self.settings.max_file_bytes // (1024 * 1024):,} MB limit.")
                        continue
                    previous = self.store.document_signature(canonical)
                    unchanged = previous and (previous["mtime_ns"], previous["size"]) == (metadata.st_mtime_ns, metadata.st_size)
                    if unchanged:
                        result["unchanged"] += 1
                        needs_embeddings = (previous["embedding_model"] != model
                                            or previous["embedded_count"] < previous["chunk_count"])
                        if needs_embeddings and embed_available:
                            document = self.store.get_document(previous["id"])
                            chunks = self.store.get_document_chunks(previous["id"])
                            used_model = embed(chunks)
                            if used_model:
                                self.store.upsert_document(root_id, canonical, document["title"], document["text"],
                                                          metadata.st_mtime_ns, metadata.st_size, chunks, used_model)
                                result["embedded"] += len(chunks)
                        notify(path)
                        continue
                    data, metadata = self._read_file(path, root)
                    text, pages = self._extract_text(path, data)
                    chunks = chunk_text(text, pages)
                    used_model = embed(chunks)
                    self.store.upsert_document(root_id, canonical, path.name, text, metadata.st_mtime_ns,
                                               metadata.st_size, chunks, used_model)
                    result["indexed"] += 1
                    result["embedded"] += len(chunks) if used_model else 0
                except Exception as exc:
                    error(path, exc)
                notify(path)
            if result.get("incomplete"):
                break
        if complete:
            result["removed"] = self.store.prune_documents(root_id, seen)
        else:
            result["incomplete"] = True
        notify()
        return result

    def retrieve(self, query: str, limit: int = 8) -> list[dict]:
        vector = None
        if self.embedder is not None and str(query).strip():
            try:
                returned = self.embedder([str(query)[:4000]])
                vector = returned[0] if returned else None
            except Exception:
                pass
        wanted = max(1, min(int(limit), 40))
        candidates = self.store.search(query, limit=min(40, wanted * 3), query_embedding=vector,
                                       embedding_model=self.settings.embedding_model if vector is not None else "")
        approved = {item["id"]: Path(item["path"]) for item in self.store.list_roots()}
        fresh = {}
        results = []
        for hit in candidates:
            document_id = hit["document_id"]
            if document_id not in fresh:
                fresh[document_id] = False
                try:
                    signature = self.store.document_signature(hit["path"])
                    if signature is None or signature["root_id"] not in approved:
                        continue
                    root = self._validate_root(approved[signature["root_id"]])
                    source = Path(hit["path"])
                    metadata = checked_source_stat(source, root)
                    fresh[document_id] = (stat.S_ISREG(metadata.st_mode)
                                          and (metadata.st_mtime_ns, metadata.st_size)
                                          == (signature["mtime_ns"], signature["size"]))
                except (OSError, ValueError):
                    pass
            if fresh[document_id]:
                results.append(hit)
                if len(results) >= wanted:
                    break
        return results
