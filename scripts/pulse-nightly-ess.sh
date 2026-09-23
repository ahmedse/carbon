#!/usr/bin/env bash
# PV2-6B local entry. Default dry-run. Live mutation needs all four:
#   PULSE_NIGHTLY_LIVE=1, --live, --i-have-stack-hold, emp_1067.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi
if [[ "${1:-}" == "--live" ]]; then
  exec "$PY" -m ai.eval.nightly_ess_smoke "$@"
fi
exec "$PY" -m ai.eval.nightly_ess_smoke --dry-run "$@"
