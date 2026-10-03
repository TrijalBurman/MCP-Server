#!/usr/bin/env bash
set -euo pipefail
TASK_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TASK_DIR"
mkdir -p .runtime
export COPILOT_DATA_DIR="${COPILOT_DATA_DIR:-$TASK_DIR/.local-copilot}"
export OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NO_CLOUD=1
export OLLAMA_MODELS="$TASK_DIR/.runtime/models"
export OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=2
OLLAMA_BIN="$TASK_DIR/.runtime/ollama/bin/ollama"
if command -v ollama >/dev/null 2>&1; then OLLAMA_BIN="$(command -v ollama)"; fi
if [[ -x "$OLLAMA_BIN" ]] && ! curl -fsS --max-time 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
  nohup "$OLLAMA_BIN" serve >.runtime/ollama.log 2>&1 &
  echo $! >.runtime/ollama.pid
fi
if [[ ! -x .venv/bin/python ]]; then echo 'Run ./scripts/setup.sh first.' >&2; exit 1; fi
echo 'Open http://127.0.0.1:8765 in your browser. Press Ctrl+C to stop the app.'
exec .venv/bin/python -m copilot "$@"
