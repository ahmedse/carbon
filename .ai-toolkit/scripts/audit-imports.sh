#!/bin/bash
# .ai-toolkit/scripts/audit-imports.sh
# Import-linter contract (P2-11).
#
# Enforces the engine portability boundary: code under backend/ai/engine/ may
# only import engine internals (ai.engine.*), the Python standard library, and
# third-party SDKs — NEVER the Django host layer (ai.command_boundary,
# ai.pdp, ai.protocol, ai.adapters, ai.models, django.*, ...).
#
# This is the named `audit-imports` gate referenced across the pulse plan. It is
# a thin wrapper over import-boundary-lint.py (the P2-04 contract) so CI and
# `verify.sh intelligence` share ONE canonical implementation.
#
# Usage:
#   ./.ai-toolkit/scripts/audit-imports.sh
#
# Exit 0 = clean; exit 1 = boundary violation(s).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" "$SCRIPT_DIR/import-boundary-lint.py"
