#!/bin/bash
# .ai-toolkit/scripts/verify.sh
# ONE-SHOT VERIFICATION GATE. Run before marking any task complete.
# Runs the full deterministic gate: backend check, frontend lint/build,
# and anti-pattern grep (hardcoded secrets, hex colors, MUI v5 Grid, raw fetch).
#
# Usage:
#   ./.ai-toolkit/scripts/verify.sh            # run everything relevant
#   ./.ai-toolkit/scripts/verify.sh backend    # backend only
#   ./.ai-toolkit/scripts/verify.sh frontend   # frontend only
#   ./.ai-toolkit/scripts/verify.sh antipatterns
#   ./.ai-toolkit/scripts/verify.sh intelligence  # P2-11: boundary lints + vulture + replay smoke

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLKIT_DIR="$(dirname "$SCRIPT_DIR")"
ROOT="$(dirname "$TOOLKIT_DIR")"
CONFIG="$TOOLKIT_DIR/project.config.md"

cfg() { grep "^$1=" "$CONFIG" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/ *#.*//' | xargs || true; }

BACKEND_DIR="$ROOT/$(cfg BACKEND_DIR)"
FRONTEND_DIR="$ROOT/$(cfg FRONTEND_DIR)"

GREEN=$'\033[0;32m'; RED=$'\033[0;31m'; YELLOW=$'\033[1;33m'; NC=$'\033[0m'
FAIL=0
pass() { echo "${GREEN}✓${NC} $1"; }
fail() { echo "${RED}✗${NC} $1"; FAIL=1; }
warn() { echo "${YELLOW}⚠${NC} $1"; }

# ── BACKEND ───────────────────────────────────────────────────────────────────
verify_backend() {
  echo "── Backend ─────────────────────────────"
  if [ ! -d "$BACKEND_DIR" ]; then warn "no backend dir"; return; fi
  ( cd "$BACKEND_DIR" && source venv/bin/activate 2>/dev/null
    if python manage.py check >/tmp/vb.log 2>&1; then pass "django check"; else fail "django check"; cat /tmp/vb.log; fi
    if python manage.py makemigrations --check --dry-run >/tmp/vm.log 2>&1; then pass "no missing migrations"; else warn "unmade migrations pending (review /tmp/vm.log)"; fi
  )
}

# ── TESTS ─────────────────────────────────────────────────────────────────────
verify_tests() {
  echo "── Tests ───────────────────────────────"
  if [ ! -d "$BACKEND_DIR" ]; then warn "no backend dir"; return; fi
  ( cd "$BACKEND_DIR" && source venv/bin/activate 2>/dev/null
    if python manage.py test "${TEST_ARGS:-}" >/tmp/vt.log 2>&1; then
      pass "backend tests ($(grep -oE 'Ran [0-9]+ test' /tmp/vt.log | head -1))"
    else
      fail "backend tests (see /tmp/vt.log)"; tail -25 /tmp/vt.log
    fi
  )
}

# ── FRONTEND ──────────────────────────────────────────────────────────────────
verify_frontend() {
  echo "── Frontend ────────────────────────────"
  if [ ! -d "$FRONTEND_DIR" ]; then warn "no frontend dir"; return; fi
  ( cd "$FRONTEND_DIR"
    if npm run lint >/tmp/vfl.log 2>&1; then pass "lint"; else fail "lint (see /tmp/vfl.log)"; tail -15 /tmp/vfl.log; fi
    if npm run build >/tmp/vfb.log 2>&1; then pass "build"; else fail "build (see /tmp/vfb.log)"; tail -15 /tmp/vfb.log; fi
  )
}

# ── ANTI-PATTERNS (deterministic block) ───────────────────────────────────────
verify_antipatterns() {
  echo "── Anti-patterns ───────────────────────"
  local EX="--exclude-dir=venv --exclude-dir=node_modules --exclude-dir=__pycache__ --exclude-dir=migrations --exclude-dir=.git --exclude-dir=dist --exclude-dir=build --exclude-dir=staticfiles --exclude-dir=theme"
  local m

  # 1. Hardcoded secrets in code (not env)
  m=$(grep -rniE $EX "(api[_-]?key|secret|password|token)[[:space:]]*=[[:space:]]*[\"'][A-Za-z0-9/_+-]{16,}[\"']" \
       "$BACKEND_DIR" "$FRONTEND_DIR/src" --include="*.py" --include="*.js" --include="*.jsx" 2>/dev/null \
       | grep -viE "os\.(getenv|environ)|import\.meta\.env|process\.env|getenv|example|dummy|placeholder|test" || true)
  if [ -n "$m" ]; then fail "possible hardcoded secret(s) — move to env vars:"; echo "$m" | sed "s|$ROOT/||" | head -5; else pass "no hardcoded secrets"; fi

  # 2. MUI v5 Grid syntax
  m=$(grep -rn $EX "<Grid item\b\|<Grid[^>]* xs=" "$FRONTEND_DIR/src" --include="*.jsx" --include="*.tsx" 2>/dev/null || true)
  if [ -n "$m" ]; then fail "MUI v5 Grid syntax — use <Grid size={{...}}>:"; echo "$m" | sed "s|$ROOT/||" | head -5; else pass "no MUI v5 Grid syntax"; fi

  # 3. Raw fetch() instead of apiFetch
  m=$(grep -rn $EX "[^a-zA-Z.]fetch(" "$FRONTEND_DIR/src" --include="*.jsx" --include="*.js" 2>/dev/null \
       | grep -v "apiFetch\|// " || true)
  if [ -n "$m" ]; then warn "raw fetch() — prefer the project apiFetch helper:"; echo "$m" | sed "s|$ROOT/||" | head -5; else pass "no raw fetch()"; fi

  # 4. Hardcoded hex colors in components (tokens only)
  m=$(grep -rnE $EX "#[0-9a-fA-F]{3,6}\b" "$FRONTEND_DIR/src/components" --include="*.jsx" 2>/dev/null \
       | grep -v "theme\|// " || true)
  if [ -n "$m" ]; then warn "hardcoded hex color(s) — prefer theme.palette tokens:"; echo "$m" | sed "s|$ROOT/||" | head -5; else pass "no hardcoded hex in components"; fi

  # 5. Naive datetime in backend (exclude scripts/experiments/commands)
  m=$(grep -rn $EX "datetime\.now()\|datetime\.utcnow()" "$BACKEND_DIR" --include="*.py" 2>/dev/null \
       | grep -v "timezone\|# \|/scripts/\|experiment_\|/management/\|hardening/\|walkforward" || true)
  if [ -n "$m" ]; then warn "naive datetime — use django.utils.timezone.now():"; echo "$m" | sed "s|$ROOT/||" | head -5; else pass "no naive datetime in app code"; fi

  # 6. print() left in backend app code (should be logger)
  local pc
  pc=$(grep -rn $EX "^[[:space:]]*print(" "$BACKEND_DIR" --include="*.py" 2>/dev/null \
       | grep -vc "management/commands\|/scripts/\|experiment_\|/tests/" || true)
  [ "$pc" -gt 0 ] && warn "$pc print() calls in backend app code (use logger)" || pass "no stray print()"
}

# ── INTELLIGENCE (P2-11): engine boundary + replay gates ──────────────────────
#   import-linter contract  → HARD  (engine may not import the Django host layer)
#   fail-open lint          → HARD  (no except-returns-True / no-op filters)
#   forbidden-term grep     → HARD  (engine is domain-agnostic)
#   vulture dead-code       → REPORT-ONLY (strict threshold lands in P7-10)
#   replay smoke            → HARD  (deterministic offline L1 fixtures, no DB/LLM)
verify_intelligence() {
  echo "── Intelligence (engine boundary + replay) ──"
  local PY="$ROOT/.venv/bin/python"
  [ -x "$PY" ] || PY="python3"
  local S="$SCRIPT_DIR"

  if "$S/audit-imports.sh" >/tmp/vi1.log 2>&1; then pass "import-linter contract"; else fail "import-linter contract"; cat /tmp/vi1.log; fi
  if "$PY" "$S/failopen-lint.py" >/tmp/vi2.log 2>&1; then pass "fail-open lint"; else fail "fail-open lint"; cat /tmp/vi2.log; fi
  if "$PY" "$S/forbidden-term-lint.py" >/tmp/vi3.log 2>&1; then pass "forbidden-term grep"; else fail "forbidden-term grep"; cat /tmp/vi3.log; fi

  # vulture: report-only (P0-08 report → strict P7-10). Warn + count, never fail.
  local VULTURE_BIN="$ROOT/.venv/bin/vulture"
  [ -x "$VULTURE_BIN" ] || VULTURE_BIN="$(command -v vulture || true)"
  if [ -n "$VULTURE_BIN" ] && [ -x "$VULTURE_BIN" ]; then
    local vn
    vn=$("$VULTURE_BIN" "$ROOT/backend/ai/engine" --min-confidence 80 2>/dev/null | wc -l | tr -d ' ')
    warn "vulture report-only: $vn finding(s) in engine (strict gate lands in P7-10)"
  else
    warn "vulture not installed — skipping report-only scan"
  fi

  if ( cd "$BACKEND_DIR" && "$PY" -m pytest ai/tests/test_replay_fixtures.py -q -m "not live" >/tmp/vi5.log 2>&1 ); then
    pass "replay smoke ($(grep -oE '[0-9]+ passed' /tmp/vi5.log | head -1))"
  else
    fail "replay smoke"; tail -20 /tmp/vi5.log
  fi
}

# ── MAIN ──────────────────────────────────────────────────────────────────────
TARGET="${1:-all}"
echo "Verification gate: $TARGET"
echo "════════════════════════════════════════"
case "$TARGET" in
  backend)      verify_backend ;;
  frontend)     verify_frontend ;;
  tests)        verify_tests ;;
  antipatterns) verify_antipatterns ;;
  intelligence) verify_intelligence ;;
  all)          verify_backend; verify_frontend; verify_antipatterns ;;
  full)         verify_backend; verify_tests; verify_frontend; verify_antipatterns; verify_intelligence ;;
  *) echo "Unknown: $TARGET (use backend|frontend|tests|antipatterns|intelligence|all|full)"; exit 1 ;;
esac
echo "════════════════════════════════════════"
if [ "$FAIL" -eq 0 ]; then echo "${GREEN}GATE PASSED${NC}"; else echo "${RED}GATE FAILED — fix before reporting done${NC}"; exit 1; fi
