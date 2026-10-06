"""Shared local-path policy and bounded Win32 reads, without POSIX emulation.

Windows handles are opened with read sharing only. Each ancestor remains open
until the file operation finishes; reparse attributes and final handle paths are
checked before using a handle. This rejects junctions, symbolic links, cloud
placeholders, alternate streams, device namespaces, and remote/mapped drives.
"""

from __future__ import annotations

import ctypes
import os
import re
import stat
from contextlib import ExitStack, contextmanager
from functools import lru_cache
from pathlib import Path, PureWindowsPath

REPARSE_ATTRIBUTE = 0x400
HIDDEN_SYSTEM_ATTRIBUTES = 0x2 | 0x4
WINDOWS_SYSTEM_FOLDERS = {
    "windows", "winnt", "program files", "program files (x86)", "programdata", "recovery",
    "$recycle.bin", "system volume information",
}


def is_redirect(path: Path) -> bool:
    """Inspect the entry itself, never just the resolved target."""
    if path.is_symlink() or path.is_junction():
        return True
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    return bool(getattr(metadata, "st_file_attributes", 0) & REPARSE_ATTRIBUTE)


def has_redirects(path: Path) -> bool:
    # Inspect from the drive/filesystem anchor down. Inspecting the leaf first
    # could already follow an ancestor junction (including one to a UNC share).
    return any(is_redirect(part) for part in (*reversed(path.parents), path))


def is_hidden_or_system(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    try:
        return bool(getattr(path.lstat(), "st_file_attributes", 0) & HIDDEN_SYSTEM_ATTRIBUTES)
    except FileNotFoundError:
        return False


def validate_windows_path(path: str | PureWindowsPath) -> PureWindowsPath:
    """Pure lexical checks can also be tested on the Linux development host."""
    raw = str(path)
    result = PureWindowsPath(raw)
    if (raw.startswith(("\\\\", "//")) or "\0" in raw
            or not re.fullmatch(r"[A-Za-z]:", result.drive) or not result.is_absolute()):
        raise ValueError("Choose an absolute folder on a local HDD or SSD; network and device paths are excluded.")
    for component in result.parts[1:]:
        if (":" in component or component.endswith((".", " ")) or component in {".", ".."}
                or re.match(r"(?i)^(?:con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(?:\.|$)", component)):
            raise ValueError("Device names, alternate streams and ambiguous Windows paths are excluded.")
    return result


def validate_windows_root(path: str | PureWindowsPath, protected: list[str] | None = None) -> None:
    source = validate_windows_path(path)
    if len(source.parts) == 1:
        raise ValueError("System folders and whole drive roots cannot be selected. Choose a documents folder.")
    if source.parts[1].lower() in WINDOWS_SYSTEM_FOLDERS:
        raise ValueError("System folders cannot be selected. Choose a documents folder on a local drive.")
    if source.name.lower() == "appdata":
        raise ValueError("System application folders cannot be selected. Choose a documents folder.")
    for folder in protected or []:
        candidate = PureWindowsPath(folder)
        if candidate.is_absolute() and (source == candidate or candidate in source.parents):
            raise ValueError("System folders cannot be selected. Choose a documents folder on a local drive.")


class _WindowsAPI:
    """Only constructed on Windows; importing this module remains portable."""

    def __init__(self):
        from ctypes import wintypes

        class FileInformation(ctypes.Structure):
            _fields_ = [
                ("attributes", wintypes.DWORD), ("creation", wintypes.FILETIME),
                ("access", wintypes.FILETIME), ("write", wintypes.FILETIME),
                ("volume", wintypes.DWORD), ("size_high", wintypes.DWORD),
                ("size_low", wintypes.DWORD), ("links", wintypes.DWORD),
                ("index_high", wintypes.DWORD), ("index_low", wintypes.DWORD),
            ]

        self.information_type = FileInformation
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                          wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(FileInformation)]
        self.kernel.GetFileInformationByHandle.restype = wintypes.BOOL
        self.kernel.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR,
                                                       wintypes.DWORD, wintypes.DWORD]
        self.kernel.GetFinalPathNameByHandleW.restype = wintypes.DWORD
        self.kernel.GetFileType.argtypes = [wintypes.HANDLE]
        self.kernel.GetFileType.restype = wintypes.DWORD
        self.kernel.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
        self.kernel.GetDriveTypeW.restype = wintypes.UINT
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.invalid_handle = ctypes.c_void_p(-1).value

    def ensure_local_drive(self, path: Path) -> None:
        if self.kernel.GetDriveTypeW(path.anchor) not in {2, 3}:  # DRIVE_REMOVABLE / DRIVE_FIXED
            raise ValueError("Choose a folder on a fixed or removable local drive; network drives are excluded.")

    def close(self, handle):
        self.kernel.CloseHandle(handle)

    def final_path(self, handle) -> PureWindowsPath:
        capacity = 512
        while capacity <= 32768:
            buffer = ctypes.create_unicode_buffer(capacity)
            count = self.kernel.GetFinalPathNameByHandleW(handle, buffer, capacity, 0)
            if not count:
                raise ctypes.WinError(ctypes.get_last_error())
            if count < capacity:
                final = buffer.value
                if not final.startswith("\\\\?\\") or final.startswith("\\\\?\\UNC\\"):
                    raise ValueError("The opened file is not on an ordinary local drive.")
                return validate_windows_path(final[4:])
            capacity = count + 1
        raise ValueError("The final file path exceeds the Windows path limit.")

    def open_checked(self, path: Path, *, directory: bool):
        # FILE_READ_ATTRIBUTES for folders, GENERIC_READ for file contents.
        desired = 0x80 if directory else 0x80000000
        # FILE_FLAG_BACKUP_SEMANTICS permits directory handles. OPEN_REPARSE_POINT
        # prevents following the final component; previously locked ancestors
        # protect all earlier components. FILE_SHARE_READ denies writes/deletes.
        flags = 0x02000000 | 0x00200000
        handle = self.kernel.CreateFileW("\\\\?\\" + str(path), desired, 1, None, 3, flags, None)
        if handle == self.invalid_handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            self.check_handle(handle, path, directory=directory)
            return handle
        except BaseException:
            self.close(handle)
            raise

    def check_handle(self, handle, path: Path, *, directory: bool):
        info = self.information_type()
        if not self.kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        if info.attributes & REPARSE_ATTRIBUTE:
            raise ValueError("Document path contains a symbolic link, junction or reparse point. Reindex its folder.")
        if not directory and info.attributes & HIDDEN_SYSTEM_ATTRIBUTES:
            raise ValueError("Hidden and system source files are excluded. Reindex its folder.")
        if bool(info.attributes & 0x10) != directory or self.kernel.GetFileType(handle) != 1:
            raise ValueError("Only ordinary local folders and regular files can be indexed.")
        if self.final_path(handle) != PureWindowsPath(str(path)):
            raise ValueError("The source path changed or was redirected while opening it. Rescan the folder.")


@lru_cache(maxsize=1)
def _windows_api():
    if os.name != "nt":
        raise RuntimeError("The native Windows reader is only available on Windows.")
    return _WindowsAPI()


def validate_native_windows_root(path: Path) -> None:
    protected = [os.environ[name] for name in ("SystemRoot", "WINDIR", "ProgramFiles", "ProgramFiles(x86)",
                                               "ProgramW6432", "ProgramData") if os.environ.get(name)]
    validate_windows_root(str(path), protected)
    _windows_api().ensure_local_drive(path)


@contextmanager
def _locked_windows_file(path: Path, root: Path):
    import msvcrt

    validate_native_windows_root(root)
    validate_windows_path(str(path))
    if path == root or not path.is_relative_to(root):
        raise ValueError("The source lies outside its approved folder.")
    api = _windows_api()
    with ExitStack() as stack:
        ancestors = []
        # Lock and verify from the drive anchor down, including ancestors outside
        # the approved root, to detect replacements of C:\Users\... as well.
        for ancestor in reversed(path.parents):
            handle = api.open_checked(ancestor, directory=True)
            stack.callback(api.close, handle)
            ancestors.append((handle, ancestor))
        handle = api.open_checked(path, directory=False)
        transferred = False
        try:
            descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
            transferred = True  # The CRT descriptor now owns the file handle.
            with os.fdopen(descriptor, "rb") as source:
                yield source, handle, api
                for ancestor_handle, ancestor in ancestors:
                    api.check_handle(ancestor_handle, ancestor, directory=True)
        finally:
            if not transferred:
                api.close(handle)


def read_windows_file(path: Path, root: Path, maximum: int) -> tuple[bytes, os.stat_result]:
    with _locked_windows_file(path, root) as (source, handle, api):
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Only regular files can be indexed.")
        if before.st_size > maximum:
            raise ValueError("File exceeds the configured size limit.")
        content = source.read(maximum + 1)
        after = os.fstat(source.fileno())
        api.check_handle(handle, path, directory=False)
        if len(content) > maximum:
            raise ValueError("File exceeds the configured size limit.")
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("The file changed during indexing; rescan after saving it.")
        return content, after


def checked_source_stat(path: Path, root: Path) -> os.stat_result:
    """Apply the same redirect/scope policy for retrieval and MCP snapshot reads."""
    if os.name == "nt":
        with _locked_windows_file(path, root) as (source, _, _):
            return os.fstat(source.fileno())
    if has_redirects(path):
        raise ValueError("Document path contains a symbolic link. Reindex its folder.")
    resolved_root = root.resolve(strict=True)
    resolved_source = path.resolve(strict=True)
    if not resolved_source.is_relative_to(resolved_root):
        raise ValueError("Document path is outside its approved folder.")
    metadata = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("The indexed source is no longer a regular file. Reindex its folder.")
    return metadata
