#!/bin/bash
# .ai-toolkit/scripts/scan.sh
# THE ANTI-DUPLICATION ENGINE.
# Auto-generates the registry from the live codebase so workers reuse by NAME
# instead of rebuilding what already exists. Run this before planning any feature,
# and after any structural change. Never hand-maintain the registry — regenerate it.
#
# Usage:
#   ./.ai-toolkit/scripts/scan.sh            # regenerate the full registry
#   ./.ai-toolkit/scripts/scan.sh components # one section only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLKIT_DIR="$(dirname "$SCRIPT_DIR")"
ROOT="$(dirname "$TOOLKIT_DIR")"
CONFIG="$TOOLKIT_DIR/project.config.md"
REG_DIR="$TOOLKIT_DIR/registry"
mkdir -p "$REG_DIR"

cfg() { grep "^$1=" "$CONFIG" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/ *#.*//' | xargs || true; }

BACKEND_DIR="$ROOT/$(cfg BACKEND_DIR)"
FRONTEND_DIR="$ROOT/$(cfg FRONTEND_DIR)"
STAMP="$(date '+%Y-%m-%d %H:%M')"

# Directories to NEVER scan (vendored / generated code pollutes the registry)
EXCLUDES="venv .venv node_modules __pycache__ migrations .git dist build staticfiles static media archive archived_apps simulations catboost_info"

# grep exclude flags
GREP_EX=""
for d in $EXCLUDES; do GREP_EX="$GREP_EX --exclude-dir=$d"; done

# find prune expression
find_src() {
  # $1 = base dir, remaining args = find predicates
  local base="$1"; shift
  local prune=""
  for d in $EXCLUDES; do prune="$prune -path '*/$d/*' -o"; done
  eval "find \"$base\" \\( $prune -false \\) -prune -o \\( $* \\) -print" 2>/dev/null || true
}

# ── API ENDPOINTS ─────────────────────────────────────────────────────────────
scan_api() {
  echo "# Registry: API Endpoints  (auto-generated $STAMP — DO NOT EDIT)" > "$REG_DIR/api.md"
  echo "" >> "$REG_DIR/api.md"
  echo "> Before adding an endpoint, search here. Reuse or extend — never duplicate a route." >> "$REG_DIR/api.md"
  echo "" >> "$REG_DIR/api.md"
  if [ -d "$BACKEND_DIR" ]; then
    echo "## DRF Routers & url paths" >> "$REG_DIR/api.md"
    echo '```' >> "$REG_DIR/api.md"
    grep -rn $GREP_EX "router.register\|path(\|re_path(" "$BACKEND_DIR" --include="urls.py" 2>/dev/null \
      | sed "s|$ROOT/||" | head -300 >> "$REG_DIR/api.md" || true
    echo '```' >> "$REG_DIR/api.md"
    echo "" >> "$REG_DIR/api.md"
    echo "## @action custom endpoints (ViewSet extra routes)" >> "$REG_DIR/api.md"
    echo '```' >> "$REG_DIR/api.md"
    grep -rn $GREP_EX "@action" "$BACKEND_DIR" --include="*.py" -A1 2>/dev/null \
      | grep -E "@action|def " | sed "s|$ROOT/||" | head -200 >> "$REG_DIR/api.md" || true
    echo '```' >> "$REG_DIR/api.md"
  fi
  echo "  ✓ registry/api.md"
}

# ── BACKEND SERVICES ──────────────────────────────────────────────────────────
scan_services() {
  echo "# Registry: Backend Services & Utilities  (auto-generated $STAMP — DO NOT EDIT)" > "$REG_DIR/services.md"
  echo "" >> "$REG_DIR/services.md"
  echo "> Business logic lives in services. Before writing a new one, check this list — extend, don't duplicate." >> "$REG_DIR/services.md"
  echo "" >> "$REG_DIR/services.md"
  if [ -d "$BACKEND_DIR" ]; then
    echo "## Service classes" >> "$REG_DIR/services.md"
    echo '```' >> "$REG_DIR/services.md"
    grep -rn $GREP_EX "^class .*Service" "$BACKEND_DIR" --include="*.py" 2>/dev/null \
      | sed "s|$ROOT/||" | sort >> "$REG_DIR/services.md" || true
    echo '```' >> "$REG_DIR/services.md"
    echo "" >> "$REG_DIR/services.md"
    echo "## Management commands" >> "$REG_DIR/services.md"
    echo '```' >> "$REG_DIR/services.md"
    find_src "$BACKEND_DIR" "-path '*/management/commands/*.py' ! -name '__init__.py'" \
      | sed "s|$ROOT/||" | sort >> "$REG_DIR/services.md" || true
    echo '```' >> "$REG_DIR/services.md"
  fi
  echo "  ✓ registry/services.md"
}

# ── DB MODELS ─────────────────────────────────────────────────────────────────
scan_models() {
  echo "# Registry: Data Models  (auto-generated $STAMP — DO NOT EDIT)" > "$REG_DIR/models.md"
  echo "" >> "$REG_DIR/models.md"
  echo "> The data schema. Before adding a model or field, check here. Reuse existing models where possible." >> "$REG_DIR/models.md"
  echo "" >> "$REG_DIR/models.md"
  if [ -d "$BACKEND_DIR" ]; then
    echo '```' >> "$REG_DIR/models.md"
    grep -rn $GREP_EX "^class .*(models.Model)\|^class .*(TimeStampedModel)\|^class .*(Abstract"  "$BACKEND_DIR" --include="*.py" 2>/dev/null \
      | sed "s|$ROOT/||" | sort >> "$REG_DIR/models.md" || true
    echo '```' >> "$REG_DIR/models.md"
  fi
  echo "  ✓ registry/models.md"
}

# ── FRONTEND COMPONENTS ───────────────────────────────────────────────────────
scan_components() {
  echo "# Registry: Frontend Components  (auto-generated $STAMP — DO NOT EDIT)" > "$REG_DIR/components.md"
  echo "" >> "$REG_DIR/components.md"
  echo "> REUSE BEFORE CREATE. Before building any component, search here first." >> "$REG_DIR/components.md"
  echo "" >> "$REG_DIR/components.md"
  if [ -d "$FRONTEND_DIR/src" ]; then
    echo "## Components (src/components)" >> "$REG_DIR/components.md"
    echo '```' >> "$REG_DIR/components.md"
    find_src "$FRONTEND_DIR/src/components" "-name '*.jsx' -o -name '*.tsx'" \
      | sed "s|$ROOT/||" | sort >> "$REG_DIR/components.md" || true
    echo '```' >> "$REG_DIR/components.md"
    echo "" >> "$REG_DIR/components.md"
    echo "## Hooks (src/hooks)" >> "$REG_DIR/components.md"
    echo '```' >> "$REG_DIR/components.md"
    find_src "$FRONTEND_DIR/src/hooks" "-name '*.js' -o -name '*.ts'" \
      | sed "s|$ROOT/||" | sort >> "$REG_DIR/components.md" || true
    echo '```' >> "$REG_DIR/components.md"
    echo "" >> "$REG_DIR/components.md"
    echo "## API modules (src/api)" >> "$REG_DIR/components.md"
    echo '```' >> "$REG_DIR/components.md"
    find_src "$FRONTEND_DIR/src/api" "-name '*.js' -o -name '*.ts'" \
      | sed "s|$ROOT/||" | sort >> "$REG_DIR/components.md" || true
    echo '```' >> "$REG_DIR/components.md"
  fi
  echo "  ✓ registry/components.md"
}

# ── ENV / CONFIG KEYS ─────────────────────────────────────────────────────────
scan_config() {
  echo "# Registry: Configuration Keys  (auto-generated $STAMP — DO NOT EDIT)" > "$REG_DIR/config-keys.md"
  echo "" >> "$REG_DIR/config-keys.md"
  echo "> Every env var the app reads. NEVER hardcode these — always read from env with a safe default." >> "$REG_DIR/config-keys.md"
  echo "" >> "$REG_DIR/config-keys.md"
  if [ -d "$BACKEND_DIR" ]; then
    echo "## Backend env vars (os.getenv / os.environ)" >> "$REG_DIR/config-keys.md"
    echo '```' >> "$REG_DIR/config-keys.md"
    grep -rhoE $GREP_EX "os\.(getenv|environ(\.get)?)\(?\[?[\"'][A-Z_]+[\"']" "$BACKEND_DIR" --include="*.py" 2>/dev/null \
      | grep -oE "[\"'][A-Z_]+[\"']" | tr -d "\"'" | sort -u >> "$REG_DIR/config-keys.md" || true
    echo '```' >> "$REG_DIR/config-keys.md"
  fi
  if [ -d "$FRONTEND_DIR/src" ]; then
    echo "" >> "$REG_DIR/config-keys.md"
    echo "## Frontend env vars (import.meta.env)" >> "$REG_DIR/config-keys.md"
    echo '```' >> "$REG_DIR/config-keys.md"
    grep -rhoE $GREP_EX "import\.meta\.env\.[A-Z_]+" "$FRONTEND_DIR/src" 2>/dev/null \
      | sort -u >> "$REG_DIR/config-keys.md" || true
    echo '```' >> "$REG_DIR/config-keys.md"
  fi
  echo "  ✓ registry/config-keys.md"
}

# ── INDEX ─────────────────────────────────────────────────────────────────────
write_index() {
  cat > "$REG_DIR/README.md" <<EOF
# Registry — Auto-Generated Codebase Inventory

Generated: $STAMP
Command: \`./.ai-toolkit/scripts/scan.sh\`

**Purpose:** the single source of truth for WHAT ALREADY EXISTS.
Consult before building anything. This is how we prevent duplicate work.

| File | What it lists |
|------|---------------|
| [api.md](api.md) | All API endpoints & custom @action routes |
| [services.md](services.md) | Backend service classes + management commands |
| [models.md](models.md) | All data models |
| [components.md](components.md) | Frontend components, hooks, API modules |
| [config-keys.md](config-keys.md) | Every env/config key (no-hardcoding reference) |

**Workflow:** Master runs \`scan.sh\` before planning. Workers grep the registry
before creating anything new. Regenerate after any structural change.
EOF
  echo "  ✓ registry/README.md"
}

# ── MAIN ──────────────────────────────────────────────────────────────────────
TARGET="${1:-all}"
echo "Scanning codebase → registry ..."
case "$TARGET" in
  api)        scan_api ;;
  services)   scan_services ;;
  models)     scan_models ;;
  components) scan_components ;;
  config)     scan_config ;;
  all)        scan_api; scan_services; scan_models; scan_components; scan_config; write_index ;;
  *) echo "Unknown target: $TARGET (use: api|services|models|components|config|all)"; exit 1 ;;
esac
echo "Done. Registry at: .ai-toolkit/registry/"
