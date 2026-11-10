#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"
cd "$REPRO_ROOT"
exec > >(tee -a "$REPRO_ROOT/logs/action-${1:-all}-$(date -u +%Y%m%dT%H%M%SZ).log") 2>&1
case "${1:-all}" in
  bootstrap)
    mkdir -p vendor tools/python generated queries configs data cache/wheels provenance patches
    python "$REPRO_ROOT/../setup/materialize-source.py" "$REPRO_ROOT/../setup/cquirrel-source-manifest.json" "$REPRO_ROOT/../tmp/cquirrel-source-cache" "$REPRO_ROOT/vendor/Cquirrel-release"
    cp "$HOME/cquirrel-repro/src/Cquirrel-release/codegen/target/codegen-1.0-SNAPSHOT.jar" tools/codegen-1.0-SNAPSHOT.jar
    cp "$REPRO_ROOT/../setup/cquirrel-source-manifest.json" provenance/
    cp "$REPRO_ROOT/../setup/evidence/environment.txt" provenance/setup-environment.txt
    python -m pip download --only-binary=:all: --dest cache/wheels 'duckdb==1.1.3' 2>&1 | tee logs/python-download.log
    python -m pip install --no-index --find-links cache/wheels --target tools/python 'duckdb==1.1.3' 2>&1 | tee logs/python-install.log
    ;;
  benchmark)
    python scripts/benchmark.py
    ;;
  prepare|prepare-tpch|build|micro|tpch|all|report|test)
    python scripts/experiment.py "$@"
    ;;
  *) printf 'Usage: %s {bootstrap|prepare|prepare-tpch|build|micro|tpch|all|report|test|benchmark}\n' "$0" >&2; exit 2 ;;
esac
