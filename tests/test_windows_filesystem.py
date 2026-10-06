"""Portable path-policy checks plus genuine Win32 reader/junction regressions."""

import os
import subprocess
from pathlib import Path, PureWindowsPath

import pytest

from copilot.config import Settings
from copilot.filesystem import (
    _locked_windows_file,
    checked_source_stat,
    has_redirects,
    read_windows_file,
    validate_windows_path,
    validate_windows_root,
)
from copilot.library import Library
from copilot.mcp_server import _document_snapshot
from copilot.store import Store

native_windows = pytest.mark.skipif(os.name != "nt", reason="Requires real Windows filesystem/Win32 handles")


@pytest.mark.parametrize("path", [r"C:\Users\Student\Documents", r"D:\Knowledge", r"E:\研究 notes\Plan"])
def test_local_drive_document_path_policy(path):
    assert validate_windows_path(path) == PureWindowsPath(path)
    validate_windows_root(path)


@pytest.mark.parametrize("path", [
    "C:\\", "D:\\", r"C:\Windows\System32", r"C:\Program Files\Application",
    r"D:\ProgramData\App", r"C:\Recovery", r"D:\System Volume Information", r"C:\Users\Student\AppData",
    r"\\server\share\documents", r"\\?\C:\Knowledge", r"\\.\PhysicalDrive0", r"C:relative",
    r"C:\Knowledge\note.txt:secret", r"C:\Knowledge\NUL.txt", r"C:\Knowledge\COM1", "D:\\Ambiguous.\\Notes",
])
def test_system_network_device_and_ambiguous_paths_are_rejected(path):
    with pytest.raises(ValueError):
        validate_windows_root(path)


def test_custom_windows_system_directory_is_protected():
    with pytest.raises(ValueError, match="System folders"):
        validate_windows_root(r"D:\OS\System32", [r"D:\OS"])
    # Explicit temporary project folders under a user's AppData remain usable;
    # AppData itself is skipped when a broader user folder is scanned.
    validate_windows_root(r"C:\Users\runner\AppData\Local\Temp\knowledge")


def test_redirect_guards_check_ancestors_before_leaf(monkeypatch, tmp_path):
    from copilot import filesystem

    ancestor = tmp_path / "redirected"
    child = ancestor / "private.md"
    checked = []

    def is_redirect(path):
        checked.append(path)
        return path == ancestor

    monkeypatch.setattr(filesystem, "is_redirect", is_redirect)
    assert has_redirects(child)
    assert checked[0] == Path(child.anchor)
    assert ancestor in checked and child not in checked


def make_library(tmp_path):
    settings = Settings(data_dir=tmp_path / "state")
    store = Store(settings.database_path)
    library = Library(settings, store)
    folder = tmp_path / "研究 Knowledge Space"
    folder.mkdir()
    root = library.add_root(folder)
    return folder, library, store, root


def junction(path: Path, target: Path):
    result = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(path), str(target)],
                            capture_output=True, check=False)
    assert result.returncode == 0, (result.stdout + result.stderr).decode(errors="replace")
    assert path.is_junction()


@native_windows
def test_windows_unicode_space_paths_full_read_and_freshness(tmp_path):
    folder, library, store, root = make_library(tmp_path)
    path = folder / "नोट्स research.md"
    content = "Résumé and नमस्ते: Windows local knowledge.\n" * 1200
    raw = content.encode("utf-8")
    path.write_bytes(raw)
    data, metadata = read_windows_file(path, folder, len(raw))
    assert data == raw and metadata.st_size == len(raw)
    assert metadata.st_mtime_ns == path.stat().st_mtime_ns
    result = library.scan(root["id"])
    assert result["indexed"] == 1 and not result["errors"]
    document = store.list_documents()[0]
    assert _document_snapshot(store, document["id"])["text"] == content
    assert library.retrieve("Windows local knowledge")
    assert library.add_root(str(folder).upper())["id"] == root["id"]
    assert library.scan(root["id"])["unchanged"] == 1
    path.write_text("The source has changed.", encoding="utf-8")
    assert not library.retrieve("Windows local knowledge")
    with pytest.raises(ValueError, match="changed since indexing"):
        _document_snapshot(store, document["id"])
    path.unlink()
    with pytest.raises(ValueError, match="unavailable"):
        _document_snapshot(store, document["id"])


@native_windows
def test_windows_junction_root_ancestor_and_scanned_directory_are_excluded(tmp_path):
    folder, library, store, root = make_library(tmp_path)
    (folder / "approved.md").write_text("Approved local knowledge", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private.md").write_text("Unapproved external knowledge", encoding="utf-8")
    linked = folder / "external junction"
    junction(linked, outside)
    try:
        assert has_redirects(linked / "private.md")
        with pytest.raises(ValueError, match="junction|reparse"):
            library.add_root(linked)
        with pytest.raises(ValueError, match="junction|reparse"):
            library.add_root(linked / "child")
        with pytest.raises(ValueError, match="junction|reparse"):
            read_windows_file(linked / "private.md", folder, 10000)
        result = library.scan(root["id"])
        assert result["indexed"] == 1
        assert [doc["title"] for doc in store.list_documents()] == ["approved.md"]
    finally:
        linked.rmdir()  # Remove the junction itself without touching its target.


@native_windows
def test_windows_replaced_approved_root_rejected_by_mcp_and_retrieval(tmp_path):
    folder, library, store, root = make_library(tmp_path)
    (folder / "record.md").write_text("Stored approved project decision", encoding="utf-8")
    library.scan(root["id"])
    document = store.list_documents()[0]
    moved = tmp_path / "moved knowledge"
    folder.rename(moved)
    junction(folder, moved)
    try:
        assert not library.retrieve("Stored approved")
        with pytest.raises(ValueError, match="junction|reparse"):
            _document_snapshot(store, document["id"])
        with pytest.raises(ValueError, match="junction|reparse"):
            library.scan(root["id"])
    finally:
        folder.rmdir()


@native_windows
def test_windows_read_bounds_scope_and_busy_source_locks(tmp_path):
    folder, _, _, _ = make_library(tmp_path)
    path = folder / "notes.txt"
    path.write_bytes(b"Readable project content")
    with pytest.raises(ValueError, match="size limit"):
        read_windows_file(path, folder, 2)
    outside = tmp_path / "other.txt"
    outside.write_bytes(b"Other content")
    with pytest.raises(ValueError, match="outside"):
        read_windows_file(outside, folder, 1000)
    with _locked_windows_file(path, folder):
        with pytest.raises(OSError):
            path.write_bytes(b"Concurrent modification")
        with pytest.raises(OSError):
            path.unlink()
        with pytest.raises(OSError):
            folder.rename(tmp_path / "replaced")
    assert checked_source_stat(path, folder).st_size == len(b"Readable project content")
    path.write_bytes(b"Unlocked again")


@native_windows
def test_windows_hidden_attributes_are_not_indexed(tmp_path):
    import ctypes
    from ctypes import wintypes

    folder, library, store, root = make_library(tmp_path)
    hidden = folder / "hidden-note.md"
    hidden.write_text("A hidden note", encoding="utf-8")
    visible = folder / "visible.md"
    visible.write_text("Visible approved note", encoding="utf-8")
    setter = ctypes.WinDLL("kernel32", use_last_error=True).SetFileAttributesW
    setter.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    setter.restype = wintypes.BOOL
    assert setter(str(hidden), 0x2)
    try:
        library.scan(root["id"])
        assert [doc["title"] for doc in store.list_documents()] == ["visible.md"]
        document = store.list_documents()[0]
        assert library.retrieve("Visible approved")
        assert setter(str(visible), 0x2)
        try:
            assert not library.retrieve("Visible approved")
            with pytest.raises(ValueError, match="Hidden"):
                _document_snapshot(store, document["id"])
        finally:
            assert setter(str(visible), 0x80)
    finally:
        assert setter(str(hidden), 0x80)
