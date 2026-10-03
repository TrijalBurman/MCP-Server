"""Local-only settings shared by the HTTP app and stdio memory server."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent


def local_url(value: str) -> str:
    parsed = urlparse(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise ValueError("Ollama must use an HTTP loopback address on this computer.")
    return value.rstrip("/")


def local_model(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 160 or "cloud" in value.lower() or any(c.isspace() for c in value):
        raise ValueError("Choose an installed local model; cloud models are disabled.")
    return value


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: BASE_DIR / ".local-copilot")
    ollama_url: str = "http://127.0.0.1:11434"
    chat_model: str = "qwen3:4b-instruct-2507-q4_K_M"
    embedding_model: str = "embeddinggemma"
    context_size: int = 8192
    max_file_bytes: int = 20 * 1024 * 1024
    max_files: int = 20000

    def __post_init__(self):
        self.data_dir = Path(self.data_dir).expanduser().resolve()
        self.ollama_url = local_url(self.ollama_url)
        self.chat_model = local_model(self.chat_model)
        self.embedding_model = local_model(self.embedding_model)
        if not 4096 <= self.context_size <= 16384:
            raise ValueError("Context size must be between 4096 and 16384.")

    @property
    def database_path(self) -> Path:
        return self.data_dir / "memory.sqlite3"

    @classmethod
    def from_env(cls) -> Settings:
        data_dir = Path(os.environ.get("COPILOT_DATA_DIR", BASE_DIR / ".local-copilot")).expanduser().resolve()
        saved = {}
        path = data_dir / "settings.json"
        if path.is_file():
            saved = json.loads(path.read_text())
        return cls(data_dir=data_dir,
                   ollama_url=os.environ.get("COPILOT_OLLAMA_URL", "http://127.0.0.1:11434"),
                   chat_model=os.environ.get("COPILOT_CHAT_MODEL", saved.get("chat_model", "qwen3:4b-instruct-2507-q4_K_M")),
                   embedding_model=os.environ.get("COPILOT_EMBEDDING_MODEL", saved.get("embedding_model", "embeddinggemma")),
                   context_size=int(os.environ.get("COPILOT_CONTEXT_SIZE", saved.get("context_size", 8192))))

    def public(self) -> dict:
        return {"chat_model": self.chat_model, "embedding_model": self.embedding_model,
                "context_size": self.context_size, "data_dir": str(self.data_dir)}

    def save(self) -> None:
        self.__post_init__()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / "settings.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.public(), indent=2))
        temporary.replace(path)
