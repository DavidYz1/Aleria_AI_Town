#!/usr/bin/env sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

if [ -x "$repo_root/.venv/bin/python" ]; then
    python_command="$repo_root/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    python_command=$(command -v python3)
elif command -v python >/dev/null 2>&1; then
    python_command=$(command -v python)
else
    echo "Python was not found. Install Python 3.11+ or create .venv first." >&2
    exit 1
fi

cd "$repo_root"
exec "$python_command" -m scripts.start_dev "$@"
