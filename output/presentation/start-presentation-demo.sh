#!/usr/bin/env bash
# Separate sample data with the normal shared, local Ollama runtime.
set -euo pipefail
DEMO_REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$DEMO_REPO_DIR"
mkdir -p .runtime/tmp
export TMPDIR="$DEMO_REPO_DIR/.runtime/tmp"
export COPILOT_DATA_DIR="$DEMO_REPO_DIR/.runtime/presentation-demo/data"
export COPILOT_OLLAMA_URL=http://127.0.0.1:11434
export OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NO_CLOUD=1
export OLLAMA_MODELS="$DEMO_REPO_DIR/.runtime/models"
export OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=2
if [[ ! -x .venv/bin/python || ! -x .runtime/ollama/bin/ollama ]]; then
  echo 'Run the normal Linux project setup and download the local models first.' >&2
  exit 1
fi
if .venv/bin/python - <<'PY'
import os, json, urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:8766/api/status',timeout=2) as r:
        d=json.load(r)
    assert d['app']=='LocalMind' and d['settings']['data_dir']==os.environ['COPILOT_DATA_DIR']
except Exception:
    raise SystemExit(1)
PY
then
  echo 'The prepared sample workspace is already running: http://127.0.0.1:8766'
  exit 0
fi
if ! .venv/bin/python - <<'PY'
import urllib.request
try:
    urllib.request.urlopen('http://127.0.0.1:11434/api/version',timeout=2).close()
except Exception:
    raise SystemExit(1)
PY
then
  nohup .runtime/ollama/bin/ollama serve >.runtime/ollama.log 2>&1 &
  echo $! >.runtime/ollama.pid
  .venv/bin/python - <<'PY'
import time
import urllib.request

for attempt in range(30):
    try:
        urllib.request.urlopen('http://127.0.0.1:11434/api/version', timeout=1).close()
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit('The local model runtime did not start. See .runtime/ollama.log.')
PY
fi
echo 'Open http://127.0.0.1:8766. This uses a separate presentation data folder.'
echo 'If this is a new workspace, connect examples/knowledge and create Lighthouse Presentation.'
.venv/bin/python -m copilot --port 8766
