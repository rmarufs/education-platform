#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON:-python3}"

log() {
    printf '\n[smoke] %s\n' "$1"
}

require_path() {
    if [ ! -e "$1" ]; then
        printf '[smoke] Missing required path: %s\n' "$1" >&2
        exit 1
    fi
}

log "Checking Python interpreter"
"$PYTHON_BIN" --version

log "Checking project layout"
require_path "main.py"
require_path "app"
require_path "app/routers"
require_path "app/models"
require_path "templates"
require_path "static"
require_path "tests"

log "Checking Python syntax"
"$PYTHON_BIN" -m compileall -q main.py app tests scripts/check_i18n.py

log "Running unit tests"
"$PYTHON_BIN" -m unittest discover -s tests -p "test*.py"

log "Smoke test passed"
