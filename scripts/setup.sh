#!/usr/bin/env bash
set -euo pipefail
TASK_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TASK_DIR"
python3 -m venv --without-pip .venv
if python3 -m pip --version >/dev/null 2>&1; then
  python3 -m pip --python "$TASK_DIR/.venv/bin/python" install 'pip>=26,<27' -e '.[dev]'
else
  echo 'Python pip is required. Install python3-pip from your OS package manager, then rerun setup.' >&2
  exit 1
fi
echo 'Ready. Run ./scripts/setup-models.sh once, then ./scripts/start.sh.'
