#!/usr/bin/env bash
set -euo pipefail
source "$HOME/cquirrel-repro/activate.sh"
export REPRO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$REPRO_ROOT/tools/python${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
export PIP_CACHE_DIR="$REPRO_ROOT/cache/pip"
export TMPDIR="$REPRO_ROOT/tmp"
export TZ=UTC
mkdir -p "$TMPDIR" "$REPRO_ROOT/logs" "$REPRO_ROOT/results"
