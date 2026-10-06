import errno
import os
import zipfile

import pytest

from copilot.config import Settings
from copilot.library import Library, chunk_text
from copilot.store import Store


def symlink_or_skip(path, target, *, target_is_directory=False):
    try:
        path.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as exc:
        if os.name == "nt" and (getattr(exc, "winerror", None) in {50, 1314}
                                or exc.errno in {errno.ENOSYS, errno.EOPNOTSUPP}):
            pytest.skip("This Windows account/filesystem does not support creating symbolic links.")
        raise


@pytest.fixture
def setup(tmp_path):
    folder = tmp_path / "documents"
    folder.mkdir()
    settings = Settings(data_dir=tmp_path / "state")
    store = Store(settings.database_path)
    library = Library(settings, store)
    root = library.add_root(folder, "Documents")
    return folder, settings, store, library, root


def test_incremental_scan_preserves_full_text_and_prunes_deleted_files(setup):
    folder, _, store, library, root = setup
    note = folder / "research.md"
    original = "Bayesian inference " + "long research paragraph. " * 200
    note.write_text(original)
    first = library.scan(root["id"])
    assert first["indexed"] == 1
    document = store.list_documents()[0]
    assert store.get_document(document["id"])["text"] == original
    assert document["chunk_count"] > 1
    assert library.retrieve("Bayesian inference")
    second = library.scan(root["id"])
    assert second["unchanged"] == 1 and second["indexed"] == 0
    note.write_text("Changed research conclusion: quantum computing")
    os.utime(note, ns=(note.stat().st_atime_ns, note.stat().st_mtime_ns + 1_000_000))
    changed = library.scan(root["id"])
    assert changed["indexed"] == 1
    assert store.get_document(document["id"])["text"].startswith("Changed research")
    assert not store.search("Bayesian")
    note.unlink()
    assert library.scan(root["id"])["removed"] == 1
    assert not store.list_documents()


def test_changed_deleted_and_symlink_sources_excluded_before_rescan(setup, tmp_path):
    folder, _, store, library, root = setup
    note = folder / "note.md"
    note.write_text("Historical protected project information")
    library.scan(root["id"])
    assert library.retrieve("Historical")
    note.write_text("Replacement content")
    assert not library.retrieve("Historical")
    # The snapshot remains in SQLite until a successful rescan.
    assert store.search("Historical")
    note.unlink()
    assert not library.retrieve("Historical")
    target = tmp_path / "external.md"
    target.write_text("External information")
    symlink_or_skip(note, target)
    assert not library.retrieve("Historical")


def test_symlinks_secrets_dependencies_and_data_folder_excluded(setup, tmp_path):
    folder, settings, store, library, root = setup
    (folder / "readme.md").write_text("Approved useful content")
    (folder / ".env").write_text("secret password")
    (folder / "credentials.json").write_text('{"password":"secret"}')
    (folder / "service-account.json").write_text('{"private_key":"secret"}')
    dependencies = folder / "node_modules"
    dependencies.mkdir()
    (dependencies / "vendor.js").write_text("Secret dependency content")
    hidden = folder / ".private"
    hidden.mkdir()
    (hidden / "notes.md").write_text("Hidden secrets")
    external = tmp_path / "external"
    external.mkdir()
    (external / "notes.md").write_text("Out of approved scope")
    symlink_or_skip(folder / "linked-file.md", external / "notes.md")
    symlink_or_skip(folder / "linked-folder", external, target_is_directory=True)
    library.scan(root["id"])
    assert [doc["title"] for doc in store.list_documents()] == ["readme.md"]
    with pytest.raises(ValueError, match="symbolic-link"):
        library.add_root(folder / "linked-folder")
    with pytest.raises(ValueError, match="data directory"):
        library.add_root(settings.data_dir)
    with pytest.raises(ValueError, match="System folders"):
        library.add_root("/")
    with pytest.raises(ValueError, match="overlaps"):
        library.add_root(folder / "node_modules")


def test_project_base_can_be_selected_while_runtime_and_state_are_skipped(tmp_path):
    base = tmp_path / "project"
    base.mkdir()
    settings = Settings(data_dir=base / "state")
    store = Store(settings.database_path)
    library = Library(settings, store)
    for directory in (settings.data_dir, base / ".runtime", base / ".venv"):
        directory.mkdir(exist_ok=True)
        (directory / "internal.md").write_text("Internal data")
    (base / "plan.md").write_text("Project goals")
    root = library.add_root(base)
    library.scan(root["id"])
    assert [doc["title"] for doc in store.list_documents()] == ["plan.md"]


def test_local_embedding_fallback_and_unchanged_backfill(setup):
    folder, settings, store, library, root = setup
    (folder / "notes.txt").write_text("A practical database design")

    def unavailable(_):
        raise RuntimeError("Ollama is not running")

    library.embedder = unavailable
    first = library.scan(root["id"])
    assert first["indexed"] == 1 and first["embedded"] == 0
    assert "keyword search" in first["embedding_warning"]
    assert library.retrieve("database")
    library.embedder = lambda texts: [[1.0, 0.0] for _ in texts]
    second = library.scan(root["id"])
    assert second["unchanged"] == 1 and second["embedded"] > 0
    signature = store.document_signature(folder / "notes.txt")
    assert signature["embedded_count"] == signature["chunk_count"]
    assert signature["embedding_model"] == settings.embedding_model
    assert library.retrieve("unknown synonym")


def test_invalid_embedding_vectors_still_allow_keyword_indexing(setup):
    folder, _, store, library, root = setup
    (folder / "notes.txt").write_text("Useful document content")
    library.embedder = lambda texts: [[float("nan"), 0] for _ in texts]
    result = library.scan(root["id"])
    assert result["indexed"] == 1 and result["embedded"] == 0
    assert result["embedding_warning"]
    assert store.search("Useful")


def test_scan_limit_never_prunes_unvisited_documents(setup):
    folder, settings, store, library, root = setup
    for name in ("a.md", "b.md"):
        (folder / name).write_text("Searchable project notes")
    library.scan(root["id"])
    settings.max_files = 1
    result = library.scan(root["id"])
    assert result["incomplete"] and result["removed"] == 0
    assert store.stats()["documents"] == 2


def test_traversal_failure_does_not_prune_existing_documents(setup, monkeypatch):
    folder, _, store, library, root = setup
    (folder / "notes.md").write_text("Research notes")
    library.scan(root["id"])

    def cannot_read(top, *, topdown, followlinks, onerror):
        onerror(PermissionError(13, "Permission denied", str(folder)))
        yield str(top), [], []

    monkeypatch.setattr("copilot.library.os.walk", cannot_read)
    result = library.scan(root["id"])
    assert result["incomplete"] and result["removed"] == 0
    assert store.stats()["documents"] == 1


def test_parse_failure_preserves_prior_snapshot_and_reports_error(setup):
    folder, _, store, library, root = setup
    note = folder / "notes.txt"
    note.write_text("Original content")
    library.scan(root["id"])
    note.write_bytes(b"\0binary\0")
    result = library.scan(root["id"])
    assert result["errors"] and result["removed"] == 0
    assert store.get_document(store.list_documents()[0]["id"])["text"] == "Original content"
    assert not library.retrieve("Original")


def test_unicode_text_native_docx_and_pdf_page_offsets(setup):
    folder, _, store, library, root = setup
    (folder / "unicode.txt").write_bytes("नमस्ते UTF sixteen notes".encode("utf-16"))
    document_xml = '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>DOCX paragraph</w:t><w:tab/><w:t>with tab</w:t></w:r></w:p>
      <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Table cell text</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body>
      </w:document>'''
    with zipfile.ZipFile(folder / "word.docx", "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    (folder / "pages.pdf").write_bytes(make_pdf(["Page one retrieval", "Page two knowledge"]))
    result = library.scan(root["id"])
    assert result["indexed"] == 3 and not result["errors"]
    documents = {doc["title"]: doc for doc in store.list_documents()}
    assert "नमस्ते" in store.get_document(documents["unicode.txt"]["id"])["text"]
    word = store.get_document(documents["word.docx"]["id"])["text"]
    assert "DOCX paragraph\twith tab" in word and "Table cell text" in word
    pdf_id = documents["pages.pdf"]["id"]
    pdf_text = store.get_document(pdf_id)["text"]
    chunks = store.get_document_chunks(pdf_id)
    assert {chunk["page"] for chunk in chunks} == {1, 2}
    assert all(chunk["text"] == pdf_text[chunk["start"]:chunk["end"]] for chunk in chunks)
    assert any(hit["page"] == 2 for hit in store.search("knowledge"))


def make_pdf(page_texts):
    """A tiny valid PDF fixture with real text and a standard local font."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    page_ids = []
    for text in page_texts:
        page_id = len(objects) + 1
        stream_id = page_id + 1
        page_ids.append(page_id)
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {stream_id} 0 R >>".encode())
        content = f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode()
        objects.append(f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream")
    objects[1] = ("<< /Type /Pages /Kids [" + " ".join(f"{number} 0 R" for number in page_ids)
                  + f"] /Count {len(page_ids)} >>").encode()
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, value in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode() + value + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(data)


def test_chunk_overlap_is_bounded_and_does_not_cross_pages():
    text = "First-page content. " * 200 + "\n\n" + "Second-page content. " * 200
    boundary = text.index("\n\n")
    chunks = chunk_text(text, [(0, boundary, 1), (boundary + 2, len(text), 2)])
    assert len(chunks) > 4
    assert all(len(chunk["text"]) <= 1800 for chunk in chunks)
    assert all(chunk["text"] == text[chunk["start"]:chunk["end"]] for chunk in chunks)
    assert all("Second-page" not in chunk["text"] for chunk in chunks if chunk["page"] == 1)
    for previous, following in zip(chunks, chunks[1:]):
        if previous["page"] == following["page"]:
            assert previous["end"] - following["start"] == 200
