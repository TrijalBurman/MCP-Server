from __future__ import annotations

import json
import os
import socket
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from copilot.windows_runtime import (
    MODELS,
    OLLAMA_PORT,
    OLLAMA_URL,
    ProcessIdentity,
    Runtime,
    RuntimeSafetyError,
    WindowsInspector,
)


class FakeInspector:
    def __init__(self, workspace):
        self.processes = {os.getpid(): ProcessIdentity(os.getpid(), str(workspace / "Base Python" / "python.exe"), 10)}
        self.listeners = {}
        self.children = {}
        self.terminated = []

    def identity(self, pid):
        return self.processes.get(pid)

    def listener_pids(self, port):
        return set(self.listeners.get(port, set()))

    def terminate(self, identity):
        if not identity.matches(self.identity(identity.pid)):
            return False
        self.terminated.append(identity.pid)
        self.processes.pop(identity.pid, None)
        for listeners in self.listeners.values():
            listeners.discard(identity.pid)
        if identity.pid in self.children:
            self.children[identity.pid].returncode = 0
        return True


class FakeHealth:
    def __init__(self):
        self.calls = []
        self.closed = False
        self.online = True

    def get(self, url):
        self.calls.append(url)
        if not self.online:
            raise httpx.ConnectError("fixture offline")
        return httpx.Response(200, json={"version": "fixture"}, request=httpx.Request("GET", url))

    def close(self):
        self.closed = True


class FakeChild:
    def __init__(self, pid, inspector):
        self.pid = pid
        self.inspector = inspector
        self.returncode = None

    def poll(self):
        return self.returncode

    def wait(self, timeout):
        return self.returncode

    def terminate(self):
        identity = self.inspector.identity(self.pid)
        if identity:
            self.inspector.terminate(identity)


class FakeJob:
    def __init__(self, child):
        self.child = child
        self.closed = False

    def close(self):
        self.closed = True
        self.child.terminate()


@pytest.fixture
def fixture_runtime(tmp_path):
    workspace = tmp_path / "Knowledge space café 日本"
    workspace.mkdir()
    inspector = FakeInspector(workspace)
    health = FakeHealth()
    calls, jobs, pulls = [], [], []

    def popen(command, **arguments):
        calls.append((command, arguments))
        child = FakeChild(4242, inspector)
        inspector.children[child.pid] = child
        inspector.processes[child.pid] = ProcessIdentity(child.pid, str(runtime.ollama), 20)
        inspector.listeners[OLLAMA_PORT] = {child.pid}
        return child

    def job_factory(child):
        job = FakeJob(child)
        jobs.append(job)
        return job

    def run(command, **arguments):
        pulls.append((command, arguments))
        return SimpleNamespace(returncode=0)

    runtime = Runtime(workspace, inspector=inspector, health_client=health, popen=popen,
                      job_factory=job_factory, run=run, sleep=lambda _: None, startup_timeout=0.1)
    runtime.ollama.parent.mkdir()
    runtime.ollama.write_bytes(b"fixture only")
    fixture = SimpleNamespace(runtime=runtime, inspector=inspector, health=health,
                              calls=calls, jobs=jobs, pulls=pulls)
    yield fixture
    runtime.cleanup()


def record(runtime, role, identity, port):
    runtime._record(role, identity, port)


def test_process_identity_requires_executable_and_creation_time():
    identity = ProcessIdentity(100, sys.executable, 123)
    assert identity.matches(ProcessIdentity(100, sys.executable, 123))
    assert not identity.matches(ProcessIdentity(100, sys.executable, 124))
    assert not identity.matches(ProcessIdentity(100, str(Path(sys.executable).parent / "other.exe"), 123))
    assert not identity.matches(None)


def test_private_environment_overrides_remote_and_keeps_global_environment(fixture_runtime, monkeypatch):
    runtime = fixture_runtime.runtime
    inherited = {"OLLAMA_HOST": "0.0.0.0:11434", "OLLAMA_NO_CLOUD": "0",
                 "COPILOT_OLLAMA_URL": "https://example.invalid", "OLLAMA_MODELS": "other-models"}
    for name, value in inherited.items():
        monkeypatch.setenv(name, value)
    environment = runtime.environment()
    assert environment["OLLAMA_HOST"] == "127.0.0.1:11435"
    assert environment["COPILOT_OLLAMA_URL"] == OLLAMA_URL
    assert environment["OLLAMA_NO_CLOUD"] == "1"
    assert environment["OLLAMA_MODELS"] == str(runtime.models)
    assert environment["OLLAMA_NUM_PARALLEL"] == "1"
    assert environment["OLLAMA_MAX_LOADED_MODELS"] == "2"
    assert environment["PYTHONUTF8"] == "1"
    assert environment["PYTHONIOENCODING"] == "utf-8"
    assert environment["PATH"] == os.environ["PATH"]
    for name, value in inherited.items():
        assert os.environ[name] == value


def test_starts_owned_server_and_removes_it_on_cleanup(fixture_runtime):
    fixture = fixture_runtime
    runtime = fixture.runtime
    assert runtime.ensure_ollama() is True
    command, arguments = fixture.calls[0]
    assert command == [str(runtime.ollama), "serve"]
    assert arguments["cwd"] == str(runtime.workspace)
    assert arguments["env"]["OLLAMA_HOST"] == "127.0.0.1:11435"
    assert fixture.health.calls == [f"{OLLAMA_URL}/api/version"]
    saved = json.loads(runtime.state_path.read_text(encoding="utf-8"))
    assert saved["workspace"] == str(runtime.workspace)
    assert saved["processes"]["ollama"]["created"] == 20
    runtime.cleanup()
    assert fixture.inspector.terminated == [4242]
    assert fixture.jobs[0].closed
    assert not runtime._read()["processes"]


def test_unrelated_tray_server_is_never_queried_reused_or_stopped(fixture_runtime):
    fixture = fixture_runtime
    fixture.inspector.listeners[11434] = {9999}
    assert fixture.runtime.ensure_ollama()
    fixture.runtime.cleanup()
    assert fixture.inspector.listeners[11434] == {9999}
    assert 9999 not in fixture.inspector.terminated
    assert all("11435" in url for url in fixture.health.calls)


def test_refuses_unknown_private_port_without_connecting_or_killing(fixture_runtime):
    fixture = fixture_runtime
    fixture.inspector.listeners[OLLAMA_PORT] = {9999}
    with pytest.raises(RuntimeSafetyError, match="unverified process"):
        fixture.runtime.ensure_ollama()
    assert not fixture.calls
    assert not fixture.health.calls
    assert not fixture.inspector.terminated


def test_known_server_is_reused_but_not_cleaned_up_by_a_new_invocation(fixture_runtime):
    fixture = fixture_runtime
    identity = ProcessIdentity(9000, str(fixture.runtime.ollama), 500)
    fixture.inspector.processes[identity.pid] = identity
    fixture.inspector.listeners[OLLAMA_PORT] = {identity.pid}
    record(fixture.runtime, "ollama", identity, OLLAMA_PORT)
    assert fixture.runtime.ensure_ollama() is False
    fixture.runtime.cleanup()
    assert not fixture.calls
    assert not fixture.inspector.terminated
    assert fixture.runtime._read()["processes"]["ollama"]["pid"] == identity.pid


def test_reused_pid_cannot_authorize_port_reuse_or_termination(fixture_runtime):
    fixture = fixture_runtime
    stale = ProcessIdentity(9000, str(fixture.runtime.ollama), 500)
    record(fixture.runtime, "ollama", stale, OLLAMA_PORT)
    fixture.inspector.processes[stale.pid] = ProcessIdentity(stale.pid, stale.executable, 501)
    fixture.inspector.listeners[OLLAMA_PORT] = {stale.pid}
    with pytest.raises(RuntimeSafetyError, match="unverified process"):
        fixture.runtime.ensure_ollama()
    assert not fixture.inspector.terminated
    assert not fixture.health.calls
    assert "ollama" not in fixture.runtime._read()["processes"]


def test_stop_ignores_stale_pid_and_other_workspace_state(fixture_runtime):
    fixture = fixture_runtime
    stale = ProcessIdentity(9000, str(fixture.runtime.ollama), 500)
    record(fixture.runtime, "ollama", stale, OLLAMA_PORT)
    fixture.inspector.processes[stale.pid] = ProcessIdentity(stale.pid, "/unrelated/application.exe", 501)
    fixture.runtime.stop()
    assert not fixture.inspector.terminated
    assert not fixture.runtime._read()["processes"]
    fixture.runtime.state_path.write_text(json.dumps({"version": 1, "workspace": str(fixture.runtime.workspace.parent),
                                                      "processes": {}}), encoding="utf-8")
    with pytest.raises(RuntimeSafetyError, match="another workspace"):
        fixture.runtime.stop()
    fixture.runtime.state_path.unlink()


def test_actual_base_python_image_is_recorded_separately_from_venv_launcher(fixture_runtime):
    fixture = fixture_runtime
    assert fixture.runtime.prepare_app(8765)
    entry = fixture.runtime._read()["processes"]["app"]
    assert entry["executable"] == fixture.inspector.identity(os.getpid()).executable
    assert entry["launch_executable"] == sys.executable
    assert entry["executable"] != entry["launch_executable"]
    # Simulate a separate stop invocation: no current-process OS termination occurs in this mock.
    fixture.runtime.stop()
    assert os.getpid() in fixture.inspector.terminated
    fixture.inspector.processes[os.getpid()] = ProcessIdentity(os.getpid(), entry["executable"], 10)


def test_unknown_app_port_does_not_start_or_kill_ollama(fixture_runtime):
    fixture = fixture_runtime
    fixture.inspector.listeners[8765] = {9999}
    with pytest.raises(RuntimeSafetyError, match="Application port 8765"):
        fixture.runtime.prepare_app(8765)
    assert not fixture.calls
    assert not fixture.inspector.terminated


def test_stale_and_active_operation_locks(fixture_runtime):
    fixture = fixture_runtime
    runtime = fixture.runtime
    runtime.lock_path.write_text(json.dumps({"pid": 2000, "executable": sys.executable, "created": 10}),
                                 encoding="utf-8")
    with runtime.lock():
        assert runtime.lock_path.exists()
        with pytest.raises(RuntimeSafetyError, match="still running"):
            with runtime.lock():
                pytest.fail("A live lock was reused")
    assert not runtime.lock_path.exists()


def test_failed_readiness_closes_only_its_own_job(fixture_runtime):
    fixture = fixture_runtime
    fixture.health.online = False
    fixture.runtime.startup_timeout = 0.005
    with pytest.raises(RuntimeSafetyError, match="did not become ready"):
        fixture.runtime.ensure_ollama()
    assert fixture.jobs[0].closed
    assert fixture.inspector.terminated == [4242]
    fixture.runtime.cleanup()
    assert not fixture.runtime._read()["processes"]


def test_unknown_port_race_cleans_created_child_and_preserves_unknown_listener(fixture_runtime):
    fixture = fixture_runtime
    original = fixture.runtime.popen

    def racing_popen(*arguments, **options):
        child = original(*arguments, **options)
        fixture.inspector.listeners[OLLAMA_PORT] = {9999}
        return child

    fixture.runtime.popen = racing_popen
    with pytest.raises(RuntimeSafetyError, match="took the private Ollama port"):
        fixture.runtime.ensure_ollama()
    assert fixture.inspector.listeners[OLLAMA_PORT] == {9999}
    assert fixture.inspector.terminated == [4242]
    assert not fixture.health.calls


def test_pulls_only_exact_local_models_with_private_environment(fixture_runtime):
    fixture = fixture_runtime
    fixture.runtime.pull_models()
    assert [command[-1] for command, _ in fixture.pulls] == list(MODELS)
    assert all(command[:2] == [str(fixture.runtime.ollama), "pull"] for command, _ in fixture.pulls)
    assert all(options["env"]["OLLAMA_NO_CLOUD"] == "1" for _, options in fixture.pulls)
    assert all(options["env"]["OLLAMA_MODELS"] == str(fixture.runtime.models) for _, options in fixture.pulls)


def test_zip_install_handles_unicode_workspace_and_rejects_traversal(fixture_runtime, tmp_path):
    fixture = fixture_runtime
    fixture.runtime.ollama.unlink()
    archive = tmp_path / "runtime.zip"
    with zipfile.ZipFile(archive, "w") as file:
        file.writestr("ollama.exe", b"fixture")
        file.writestr("lib/ollama/example.dll", b"fixture dependency")
    fixture.runtime.install_runtime(archive)
    assert fixture.runtime.ollama.read_bytes() == b"fixture"
    assert (fixture.runtime.ollama.parent / "lib/ollama/example.dll").is_file()
    fixture.runtime.ollama.unlink()
    (fixture.runtime.ollama.parent / "lib/ollama/example.dll").unlink()
    (fixture.runtime.ollama.parent / "lib/ollama").rmdir()
    (fixture.runtime.ollama.parent / "lib").rmdir()
    with zipfile.ZipFile(archive, "w") as file:
        file.writestr("../../escaped.exe", b"unsafe")
        file.writestr("ollama.exe", b"fixture")
    with pytest.raises(RuntimeSafetyError, match="unsafe path"):
        fixture.runtime.install_runtime(archive)
    assert not (fixture.runtime.workspace / "escaped.exe").exists()
    assert not list(fixture.runtime.directory.glob("ollama-unpack-*"))


@pytest.mark.skipif(os.name != "nt", reason="Uses native Windows process handles and TCP ownership tables")
def test_native_inspector_identifies_current_process_and_its_listener():
    inspector = WindowsInspector()
    first = inspector.identity(os.getpid())
    assert first is not None and first.created > 0 and Path(first.executable).is_file()
    assert first.matches(inspector.identity(os.getpid()))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        assert os.getpid() in inspector.listener_pids(server.getsockname()[1])
