"""Own a workspace-local Windows runtime without touching a user's Ollama tray app.

The command line is called by the PowerShell launchers. Process identities are
checked with Windows handles, executable paths, and creation times; a PID alone
never authorizes termination. A kill-on-close Job Object contains a server this
launcher starts, including the GPU runners it subsequently creates.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import httpx

OLLAMA_PORT = 11435
OLLAMA_URL = f"http://127.0.0.1:{OLLAMA_PORT}"
MODELS = ("qwen3:4b-instruct-2507-q4_K_M", "embeddinggemma")
BASE_DIR = Path(__file__).resolve().parent.parent


class RuntimeSafetyError(RuntimeError):
    """An operation would risk an unrelated process or unverified installation."""


def path_key(path: str | Path) -> str:
    return os.path.normcase(str(Path(path).resolve()))


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    executable: str
    created: int

    def matches(self, other: ProcessIdentity | None) -> bool:
        return bool(other and self.pid == other.pid and self.created == other.created
                    and path_key(self.executable) == path_key(other.executable))


class WindowsInspector:
    """Query and terminate through handles to prevent PID-reuse races."""

    QUERY = 0x1000
    TERMINATE = 0x0001
    SYNCHRONIZE = 0x00100000

    def __init__(self) -> None:
        if os.name != "nt":
            raise RuntimeSafetyError("This launcher requires native 64-bit Windows 11.")
        from ctypes import wintypes

        self.types = wintypes
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.network = ctypes.WinDLL("iphlpapi", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
        ]
        self.kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        self.kernel.GetProcessTimes.restype = wintypes.BOOL
        self.kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.GetExitCodeProcess.restype = wintypes.BOOL
        self.kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel.TerminateProcess.restype = wintypes.BOOL
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.network.GetExtendedTcpTable.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL,
            wintypes.ULONG, ctypes.c_int, wintypes.ULONG,
        ]
        self.network.GetExtendedTcpTable.restype = wintypes.DWORD

    def _identity_from_handle(self, pid: int, handle) -> ProcessIdentity | None:
        exit_code = self.types.DWORD()
        if not self.kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            raise RuntimeSafetyError(f"Cannot inspect process {pid}; no process was stopped.")
        if exit_code.value != 259:  # STILL_ACTIVE
            return None
        size = self.types.DWORD(32768)
        name = ctypes.create_unicode_buffer(size.value)
        created, exited, kernel, user = (self.types.FILETIME() for _ in range(4))
        if not self.kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)):
            raise RuntimeSafetyError(f"Cannot inspect executable for process {pid}.")
        if not self.kernel.GetProcessTimes(handle, *(ctypes.byref(item) for item in
                                                   (created, exited, kernel, user))):
            raise RuntimeSafetyError(f"Cannot inspect creation time for process {pid}.")
        stamp = (created.dwHighDateTime << 32) | created.dwLowDateTime
        return ProcessIdentity(pid, name.value, stamp)

    def identity(self, pid: int) -> ProcessIdentity | None:
        handle = self.kernel.OpenProcess(self.QUERY, False, pid)
        if not handle:
            if ctypes.get_last_error() in {87, 1168}:  # Already exited / missing PID.
                return None
            raise RuntimeSafetyError(f"Windows denied inspection of process {pid}. No process was stopped.")
        try:
            return self._identity_from_handle(pid, handle)
        finally:
            self.kernel.CloseHandle(handle)

    def terminate(self, expected: ProcessIdentity) -> bool:
        handle = self.kernel.OpenProcess(self.QUERY | self.TERMINATE | self.SYNCHRONIZE, False, expected.pid)
        if not handle:
            if ctypes.get_last_error() in {87, 1168}:
                return False
            raise RuntimeSafetyError(f"Windows denied stopping owned process {expected.pid}.")
        try:
            if not expected.matches(self._identity_from_handle(expected.pid, handle)):
                return False
            if not self.kernel.TerminateProcess(handle, 0):
                raise RuntimeSafetyError(f"Could not stop owned process {expected.pid}.")
            if self.kernel.WaitForSingleObject(handle, 10000) != 0:
                raise RuntimeSafetyError(f"Owned process {expected.pid} did not stop within 10 seconds.")
            return True
        finally:
            self.kernel.CloseHandle(handle)

    def listener_pids(self, port: int) -> set[int]:
        types = self.types

        class IPv4Row(ctypes.Structure):
            _fields_ = [(name, types.DWORD) for name in
                        ("state", "local_address", "local_port", "remote_address", "remote_port", "pid")]

        class IPv6Row(ctypes.Structure):
            _fields_ = [
                ("local_address", ctypes.c_ubyte * 16), ("local_scope", types.DWORD),
                ("local_port", types.DWORD), ("remote_address", ctypes.c_ubyte * 16),
                ("remote_scope", types.DWORD), ("remote_port", types.DWORD),
                ("state", types.DWORD), ("pid", types.DWORD),
            ]

        result: set[int] = set()
        for family, row_type in ((socket.AF_INET, IPv4Row), (socket.AF_INET6, IPv6Row)):
            size = types.DWORD()
            status = self.network.GetExtendedTcpTable(None, ctypes.byref(size), False, family, 3, 0)
            if status not in {0, 122}:  # TCP_TABLE_OWNER_PID_LISTENER / insufficient buffer.
                raise RuntimeSafetyError(f"Windows could not inspect listening ports (error {status}).")
            for _ in range(3):
                buffer = ctypes.create_string_buffer(size.value)
                status = self.network.GetExtendedTcpTable(buffer, ctypes.byref(size), False, family, 3, 0)
                if status != 122:
                    break
            if status != 0:
                raise RuntimeSafetyError(f"Windows could not inspect listening ports (error {status}).")
            count = types.DWORD.from_buffer(buffer).value
            offset = ctypes.sizeof(types.DWORD)
            if offset + count * ctypes.sizeof(row_type) > len(buffer):
                raise RuntimeSafetyError("Windows returned an unreadable listening-port table.")
            for index in range(count):
                row = row_type.from_buffer(buffer, offset + index * ctypes.sizeof(row_type))
                if row.state == 2 and socket.ntohs(row.local_port & 0xFFFF) == port:
                    result.add(row.pid)
        return result


class WindowsJob:
    """Closing this private handle stops only the child assigned to this job."""

    def __init__(self, process: subprocess.Popen) -> None:
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IOCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimits), ("IoInfo", IOCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                       ctypes.c_void_p, wintypes.DWORD]
        self.kernel.SetInformationJobObject.restype = wintypes.BOOL
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise RuntimeSafetyError("Could not create the private runtime process container.")
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise RuntimeSafetyError("Could not configure private runtime cleanup.")
        if not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            self.close()
            raise RuntimeSafetyError("Could not isolate the private runtime process. It was not reused.")

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class Runtime:
    def __init__(self, workspace: Path, *, inspector=None, health_client=None,
                 popen: Callable = subprocess.Popen, run: Callable = subprocess.run,
                 job_factory: Callable = WindowsJob, sleep: Callable = time.sleep,
                 startup_timeout: float = 60.0, ollama_command: list[str] | None = None) -> None:
        self.workspace = workspace.resolve()
        self.directory = self.workspace / ".runtime"
        self.logs = self.directory / "logs"
        self.models = self.directory / "models"
        self.ollama = self.directory / "ollama" / "ollama.exe"
        self.state_path = self.directory / "windows-processes.json"
        self.lock_path = self.directory / "windows-launch.lock"
        self.inspector = inspector if inspector is not None else WindowsInspector()
        self.health = health_client if health_client is not None else httpx.Client(timeout=1.5, trust_env=False)
        self.popen, self.run = popen, run
        self.job_factory, self.sleep, self.startup_timeout = job_factory, sleep, startup_timeout
        # Injectable only by Python tests, never exposed by the production CLI.
        self.ollama_command = ollama_command or [str(self.ollama), "serve"]
        self.created: dict[str, ProcessIdentity] = {}
        self.job = None
        self.child = None
        self.child_log = None
        self.directory.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(exist_ok=True)
        self.models.mkdir(exist_ok=True)

    def environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update({
            "OLLAMA_HOST": f"127.0.0.1:{OLLAMA_PORT}", "OLLAMA_NO_CLOUD": "1",
            "OLLAMA_MODELS": str(self.models), "OLLAMA_NUM_PARALLEL": "1",
            "OLLAMA_MAX_LOADED_MODELS": "2", "COPILOT_OLLAMA_URL": OLLAMA_URL,
            "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
        })
        environment.setdefault("COPILOT_DATA_DIR", str(self.workspace / ".local-copilot"))
        # Never use an inherited remote endpoint, cloud flag, or public bind address.
        return environment

    def _read(self) -> dict:
        if not self.state_path.exists():
            return {"version": 1, "workspace": str(self.workspace), "processes": {}}
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("The process record is not a JSON object.")
            if (data.get("version") != 1 or path_key(data.get("workspace", "")) != path_key(self.workspace)
                    or not isinstance(data.get("processes"), dict)):
                raise ValueError("The process record belongs to another workspace.")
            return data
        except (ValueError, TypeError, OSError) as error:
            raise RuntimeSafetyError(f"Cannot verify {self.state_path}: {error}. No process was stopped.") from error

    def _write(self, data: dict) -> None:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", dir=self.directory, prefix="processes-", suffix=".tmp",
                                             encoding="utf-8", delete=False) as file:
                temporary = Path(file.name)
                json.dump(data, file, indent=2, ensure_ascii=False)
            temporary.replace(self.state_path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _decode_identity(record: dict) -> ProcessIdentity:
        try:
            identity = ProcessIdentity(int(record["pid"]), str(record["executable"]), int(record["created"]))
            if identity.pid <= 0 or identity.created <= 0 or not identity.executable:
                raise ValueError("Missing process identity")
            return identity
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeSafetyError("An ownership record is incomplete. No process was stopped.") from error

    def _owned(self, role: str, record: dict) -> ProcessIdentity | None:
        if not isinstance(record, dict):
            raise RuntimeSafetyError(f"The {role} ownership record is unreadable. No process was stopped.")
        expected_launch = self.ollama if role == "ollama" else Path(sys.executable)
        expected_port = OLLAMA_PORT if role == "ollama" else record.get("port")
        if (record.get("role") != role or record.get("port") != expected_port
                or path_key(record.get("launch_executable", "")) != path_key(expected_launch)):
            raise RuntimeSafetyError(f"Cannot verify the {role} ownership record. No process was stopped.")
        identity = self._decode_identity(record)
        return identity if identity.matches(self.inspector.identity(identity.pid)) else None

    def _record(self, role: str, identity: ProcessIdentity, port: int) -> None:
        data = self._read()
        data["processes"][role] = {
            **asdict(identity), "role": role, "port": port,
            "launch_executable": str(self.ollama if role == "ollama" else Path(sys.executable)),
        }
        self._write(data)

    @contextmanager
    def lock(self):
        current = self.inspector.identity(os.getpid())
        if current is None:
            raise RuntimeSafetyError("Could not verify this launcher's own identity.")
        for _ in range(2):
            try:
                with self.lock_path.open("x", encoding="utf-8") as file:
                    json.dump(asdict(current), file)
                break
            except FileExistsError:
                try:
                    locked = self._decode_identity(json.loads(self.lock_path.read_text(encoding="utf-8")))
                except (ValueError, OSError) as error:
                    raise RuntimeSafetyError("Another launcher is starting, or its lock is unreadable. Try again.") from error
                if locked.matches(self.inspector.identity(locked.pid)):
                    raise RuntimeSafetyError("Another setup, start, or stop operation is still running. Try again.")
                self.lock_path.unlink(missing_ok=True)
        else:
            raise RuntimeSafetyError("Could not acquire the workspace launch lock. Try again.")
        try:
            yield
        finally:
            # Do not remove a replacement lock created by another process.
            try:
                saved = self._decode_identity(json.loads(self.lock_path.read_text(encoding="utf-8")))
                if current.matches(saved):
                    self.lock_path.unlink(missing_ok=True)
            except (RuntimeSafetyError, ValueError, OSError):
                pass

    def _healthy(self) -> bool:
        try:
            response = self.health.get(f"{OLLAMA_URL}/api/version")
            response.raise_for_status()
            return bool(response.json().get("version"))
        except (httpx.HTTPError, ValueError, AttributeError):
            return False

    def _ensure_ollama(self) -> bool:
        data = self._read()
        record = data["processes"].get("ollama")
        existing = self._owned("ollama", record) if record else None
        if record and existing is None:
            data["processes"].pop("ollama")
            self._write(data)
        listeners = self.inspector.listener_pids(OLLAMA_PORT)
        if listeners:
            if not existing or listeners != {existing.pid}:
                raise RuntimeSafetyError(f"Port {OLLAMA_PORT} belongs to an unverified process. Nothing was stopped. "
                                         "Free this private port before starting LocalMind.")
            if not self._healthy():
                raise RuntimeSafetyError("The owned Ollama server is not responding. Check .runtime/logs/ollama.log "
                                         "or use scripts/stop.cmd before retrying.")
            return False
        if existing:
            raise RuntimeSafetyError("The owned Ollama process is running but has not opened its private port. "
                                     "Check its log or run scripts/stop.cmd before retrying.")
        if not self.ollama.exists() and self.ollama_command == [str(self.ollama), "serve"]:
            raise RuntimeSafetyError("Local Ollama is not installed. Run scripts/setup-models.cmd first.")
        self.child_log = (self.logs / "ollama.log").open("ab", buffering=0)
        arguments = {"cwd": str(self.workspace), "env": self.environment(), "stdin": subprocess.DEVNULL,
                     "stdout": self.child_log, "stderr": subprocess.STDOUT}
        if os.name == "nt":
            arguments["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        try:
            self.child = self.popen(self.ollama_command, **arguments)
            # The Popen handle is direct evidence of a child created by this invocation.
            self.job = self.job_factory(self.child)
            identity = self.inspector.identity(self.child.pid)
            if identity is None:
                raise RuntimeSafetyError("The local runtime exited during startup. Read .runtime/logs/ollama.log.")
            self.created["ollama"] = identity
            self._record("ollama", identity, OLLAMA_PORT)
            deadline = time.monotonic() + self.startup_timeout
            while time.monotonic() < deadline:
                if self.child.poll() is not None:
                    raise RuntimeSafetyError("The local runtime exited during startup. Read .runtime/logs/ollama.log.")
                listeners = self.inspector.listener_pids(OLLAMA_PORT)
                if listeners and listeners != {identity.pid}:
                    raise RuntimeSafetyError("Another process took the private Ollama port during startup. "
                                             "Only LocalMind's own child will be stopped.")
                if listeners == {identity.pid} and self._healthy():
                    return True
                self.sleep(0.2)
            raise RuntimeSafetyError("The local runtime did not become ready within 60 seconds. "
                                     "Read .runtime/logs/ollama.log and retry.")
        except BaseException:
            if self.job:
                self.job.close()
                self.job = None
            elif self.child and self.child.poll() is None:
                # Uses the exact Popen handle, never a process found by PID/name.
                self.child.terminate()
                self.child.wait(timeout=10)
            if self.child_log:
                self.child_log.close()
                self.child_log = None
            raise

    def ensure_ollama(self) -> bool:
        with self.lock():
            return self._ensure_ollama()

    def prepare_app(self, port: int) -> bool:
        if not 1024 <= port <= 65535 or port == OLLAMA_PORT:
            raise RuntimeSafetyError("Choose an application port between 1024 and 65535, except 11435.")
        with self.lock():
            data = self._read()
            record = data["processes"].get("app")
            existing = self._owned("app", record) if record else None
            if existing:
                print(f"LocalMind is already running at http://127.0.0.1:{record['port']}. "
                      "Use scripts/stop.cmd to stop it.", flush=True)
                return False
            if record:
                data["processes"].pop("app")
                self._write(data)
            if self.inspector.listener_pids(port):
                raise RuntimeSafetyError(f"Application port {port} is already in use. Nothing was stopped. "
                                         "Try scripts/start.cmd -Port 8766.")
            self._ensure_ollama()
            current = self.inspector.identity(os.getpid())
            if current is None:
                raise RuntimeSafetyError("Cannot verify the application launcher's identity.")
            self.created["app"] = current
            self._record("app", current, port)
        return True

    def cleanup(self) -> None:
        try:
            if self.created:
                with self.lock():
                    data = self._read()
                    for role, identity in self.created.items():
                        record = data["processes"].get(role)
                        if not record or not identity.matches(self._decode_identity(record)):
                            continue
                        if role == "ollama":
                            owned = self._owned(role, record)
                            if owned:
                                self.inspector.terminate(owned)
                        data["processes"].pop(role, None)
                    self._write(data)
        finally:
            if self.job:
                self.job.close()
                self.job = None
            if self.child:
                try:
                    self.child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
            if self.child_log:
                self.child_log.close()
                self.child_log = None
            self.health.close()

    def stop(self) -> None:
        with self.lock():
            data = self._read()
            for role in ("app", "ollama"):
                record = data["processes"].get(role)
                if not record:
                    continue
                identity = self._owned(role, record)
                if identity:
                    self.inspector.terminate(identity)
                    print(f"Stopped workspace-owned {role} process {identity.pid}.", flush=True)
                else:
                    print(f"Removed stale {role} record; no unrelated process was stopped.", flush=True)
                data["processes"].pop(role, None)
            self._write(data)
        print("LocalMind's owned processes are stopped. Other Ollama apps were not touched.", flush=True)

    def install_runtime(self, archive_path: Path) -> None:
        with self.lock():
            records = self._read()["processes"]
            if records.get("ollama") and self._owned("ollama", records["ollama"]):
                raise RuntimeSafetyError("Stop this workspace runtime before installing its binaries.")
            if self.inspector.listener_pids(OLLAMA_PORT):
                raise RuntimeSafetyError("The private Ollama port is occupied. No existing process was stopped.")
            if self.ollama.is_file():
                print("The workspace runtime is already installed.", flush=True)
                return
            target = self.ollama.parent
            if target.is_symlink() or (target.exists() and any(target.iterdir())):
                raise RuntimeSafetyError(f"An incomplete runtime is present at {target}. "
                                         "Inspect that folder before removing it and retrying setup.")
            staging = Path(tempfile.mkdtemp(prefix="ollama-unpack-", dir=self.directory))
            try:
                with zipfile.ZipFile(archive_path) as archive:
                    members = archive.infolist()
                    if sum(member.file_size for member in members) > 20 * 1024 ** 3:
                        raise RuntimeSafetyError("The runtime ZIP is unexpectedly large.")
                    for member in members:
                        name = member.filename.replace("\\", "/")
                        parts = name.split("/")
                        if (name.startswith("/") or ".." in parts or any(":" in part for part in parts)
                                or stat.S_ISLNK(member.external_attr >> 16)):
                            raise RuntimeSafetyError("The runtime ZIP contains an unsafe path.")
                        destination = staging.joinpath(*parts)
                        if member.is_dir():
                            destination.mkdir(parents=True, exist_ok=True)
                        else:
                            destination.parent.mkdir(parents=True, exist_ok=True)
                            with archive.open(member) as source, destination.open("wb") as output:
                                shutil.copyfileobj(source, output)
                if not (staging / "ollama.exe").is_file():
                    raise RuntimeSafetyError("The official runtime ZIP did not contain ollama.exe at its root.")
                if target.exists():
                    target.rmdir()
                staging.replace(target)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
        print(f"Installed standalone Ollama in {self.ollama.parent}.", flush=True)

    def pull_models(self) -> None:
        self.ensure_ollama()
        for model in MODELS:
            print(f"Downloading local model: {model}", flush=True)
            completed = self.run([str(self.ollama), "pull", model], cwd=str(self.workspace),
                                 env=self.environment(), check=False)
            if completed.returncode:
                raise RuntimeSafetyError(f"Download failed for {model}. Run setup-models.cmd again to resume.")
        print("Local models are ready. Inference can now run without an internet connection.", flush=True)


def configure_app_logging(path: Path) -> dict:
    from copy import deepcopy

    from uvicorn.config import LOGGING_CONFIG

    config = deepcopy(LOGGING_CONFIG)
    config["formatters"]["file"] = {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}
    config["handlers"]["file"] = {
        "class": "logging.FileHandler", "filename": str(path), "encoding": "utf-8", "formatter": "file",
    }
    config["loggers"]["uvicorn"]["handlers"].append("file")
    config["loggers"]["uvicorn.access"]["handlers"].append("file")
    return config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage LocalMind's private Windows runtime")
    parser.add_argument("--workspace", type=Path, default=BASE_DIR)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start", help="Run the local app in the foreground")
    start.add_argument("--port", type=int, default=8765)
    commands.add_parser("stop", help="Stop only verified workspace-owned processes")
    commands.add_parser("setup-models", help="Pull the two required local models")
    install = commands.add_parser("install-runtime", help="Safely unpack the official standalone ZIP")
    install.add_argument("archive", type=Path)
    arguments = parser.parse_args(argv)
    if os.name != "nt" or sys.maxsize <= 2 ** 32 or platform.machine().lower() not in {"amd64", "x86_64"}:
        print("This launcher requires native x64 Windows and 64-bit Python 3.12 or newer.", file=sys.stderr)
        return 1
    if sys.version_info < (3, 12):
        print("Install 64-bit Python 3.12 or newer (3.13 recommended) and run setup.cmd.", file=sys.stderr)
        return 1
    runtime = None
    try:
        runtime = Runtime(arguments.workspace)
        if arguments.command == "stop":
            runtime.stop()
        elif arguments.command == "install-runtime":
            runtime.install_runtime(arguments.archive)
        elif arguments.command == "setup-models":
            runtime.pull_models()
        elif runtime.prepare_app(arguments.port):
            import uvicorn

            os.environ.update(runtime.environment())
            print(f"Open http://127.0.0.1:{arguments.port} in your browser. Press Ctrl+C to stop LocalMind.\n"
                  "Private model runtime: 127.0.0.1:11435. No existing Ollama tray app is reused.\n"
                  f"Local logs: {runtime.logs}", flush=True)
            uvicorn.run("copilot.api:app", host="127.0.0.1", port=arguments.port, log_level="info",
                        log_config=configure_app_logging(runtime.logs / "app.log"))
        return 0
    except KeyboardInterrupt:
        print("\nStopping this workspace's local processes...", flush=True)
        return 0
    except (RuntimeSafetyError, OSError, zipfile.BadZipFile) as error:
        print(f"LocalMind: {error}", file=sys.stderr, flush=True)
        return 1
    finally:
        if runtime is not None:
            try:
                runtime.cleanup()
            except (RuntimeSafetyError, OSError) as error:
                print(f"Cleanup could not verify every process: {error}\n"
                      "Use scripts/stop.cmd to retry verified cleanup.", file=sys.stderr, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
