#!/usr/bin/env bash
set -euo pipefail
TASK_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TASK_DIR"
mkdir -p .runtime/ollama .runtime/models
if command -v ollama >/dev/null 2>&1; then
  OLLAMA_BIN="$(command -v ollama)"
else
  OLLAMA_BIN="$TASK_DIR/.runtime/ollama/bin/ollama"
  if [[ ! -x "$OLLAMA_BIN" ]]; then
    if [[ "$(uname -m)" != "x86_64" ]]; then
      echo 'Install Ollama for your architecture, then run this script again.' >&2; exit 1
    fi
    echo 'Downloading the official Ollama Linux runtime into this workspace (no sudo).'
    curl -fL --retry 3 --continue-at - --output .runtime/ollama-linux-amd64.tar.zst https://ollama.com/download/ollama-linux-amd64.tar.zst
    tar --zstd -xf .runtime/ollama-linux-amd64.tar.zst -C .runtime/ollama
    rm .runtime/ollama-linux-amd64.tar.zst
  fi
fi
export OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NO_CLOUD=1
export OLLAMA_MODELS="$TASK_DIR/.runtime/models"
export OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=2
if ! curl -fsS --max-time 2 http://127.0.0.1:11434/api/version >/dev/null; then
  nohup "$OLLAMA_BIN" serve >.runtime/ollama.log 2>&1 &
  echo $! >.runtime/ollama.pid
  for attempt in $(seq 1 30); do
    if curl -fsS --max-time 1 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then break; fi
    sleep 1
  done
fi
"$OLLAMA_BIN" pull qwen3:4b-instruct-2507-q4_K_M
"$OLLAMA_BIN" pull embeddinggemma
echo 'Local models downloaded. Inference can now run without internet.'
