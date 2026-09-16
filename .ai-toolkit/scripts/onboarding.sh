#!/usr/bin/env bash
# QUARANTINED for this Carbon monorepo (2026-09-16 toolkit audit).
# Requires ~/ai-toolkit central + multi-project layout — not applicable here.
# Use scan.sh / retro.sh / activate.sh / verify.sh instead.
# Original script body retained below for reference / future central-toolkit use.
if [[ "${ALLOW_CENTRAL_TOOLKIT_SCRIPTS:-}" != "1" ]]; then
  echo "quarantined: $0 is disabled in this monorepo (set ALLOW_CENTRAL_TOOLKIT_SCRIPTS=1 to override)" >&2
  exit 2
fi

# onboarding.sh — Wire a project into the central AI toolkit with the full agent team.
#
# Usage:
#   ~/ai-toolkit/scripts/onboarding.sh <project-dir> [--from <template-project-dir>]
#
#   <project-dir>        target project root (a .ai-toolkit/ will be created inside it)
#   --from <dir>         copy the 8 project-specific role starters from this existing
#                        project (pick one with the SAME backend framework).
#                        Default: ~/clearturn/turnkey (FastAPI). For Django, pass a
#                        Django project, e.g. --from ~/clearturn/gigacast
#
# What it does (idempotent — safe to re-run):
#   - symlinks the shared layers from ~/ai-toolkit  (edit once, all projects see it)
#   - copies project-specific role starters you then adapt
#   - generates a project.config.md template to fill in
#   - seeds the project-local "brain": troubleshooting/ decisions/ registry/
#   - leaves NOTHING from another project leaking in (name is sed-replaced; you adapt paths)

set -euo pipefail

CENTRAL="$HOME/ai-toolkit"
PROJECT="${1:-}"
TEMPLATE="$HOME/clearturn/turnkey"

# ── parse args ────────────────────────────────────────────────────────────────
shift || true
while [ $# -gt 0 ]; do
  case "$1" in
    --from) TEMPLATE="$2"; shift 2;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

if [ -z "$PROJECT" ]; then
  echo "Usage: onboarding.sh <project-dir> [--from <template-project-dir>]"
  exit 1
fi
[ -d "$CENTRAL" ] || { echo "Central toolkit not found at $CENTRAL"; exit 1; }
[ -d "$PROJECT" ] || { echo "Project dir not found: $PROJECT"; exit 1; }

D="$PROJECT/.ai-toolkit"
name=$(basename "$PROJECT")
echo "→ Onboarding '$name' at $D"
echo "  shared layers from: $CENTRAL"
echo "  role starters from:  $TEMPLATE"
echo ""

# ── 1. local skeleton ─────────────────────────────────────────────────────────
mkdir -p "$D/shared" "$D/scripts" "$D/roles" "$D/troubleshooting" "$D/decisions" "$D/registry"

# ── 2. symlink shared contracts (individual files → local files coexist) ──────
for f in "$CENTRAL"/shared/*.md; do
  ln -sfn "$f" "$D/shared/$(basename "$f")"
done
echo "  ✓ shared/ — $(ls "$CENTRAL"/shared/*.md | wc -l) contracts symlinked"

# ── 3. symlink shared scripts (promote.sh is central-run only) ───────────────
for s in activate verify guard new-task retro; do
  [ -f "$CENTRAL/scripts/$s.sh" ] && ln -sfn "$CENTRAL/scripts/$s.sh" "$D/scripts/$s.sh"
done
echo "  ✓ scripts/ — activate,verify,guard,new-task,retro symlinked"

# ── 4. symlink whole shared dirs ─────────────────────────────────────────────
for dir in frameworks universal patterns; do
  [ -L "$D/$dir" ] || ln -s "$CENTRAL/$dir" "$D/$dir"
done
echo "  ✓ frameworks/ universal/ patterns/ symlinked"

# ── 5. symlink the generic central role (product-designer) ───────────────────
ln -sfn "$CENTRAL/roles/product-designer.md" "$D/roles/product-designer.md"
echo "  ✓ roles/product-designer.md (generic, central)"

# ── 6. copy project-specific role starters (adapt after) ─────────────────────
copied=0
for r in master-architect backend-worker frontend-worker devops-worker \
         debugger-fixer researcher data-ml-worker curator; do
  src="$TEMPLATE/.ai-toolkit/roles/$r.md"
  dst="$D/roles/$r.md"
  if [ -f "$src" ] && [ ! -e "$dst" ]; then
    sed "s/$(basename "$TEMPLATE")/$name/g" "$src" > "$dst"
    copied=$((copied+1))
  fi
done
echo "  ✓ roles/ — $copied project-role starters copied from $(basename "$TEMPLATE") (ADAPT paths/framework)"

# ── 7. project-local scan.sh placeholder ─────────────────────────────────────
if [ ! -f "$D/scripts/scan.sh" ]; then
  cat > "$D/scripts/scan.sh" <<'EOF'
#!/usr/bin/env bash
# scan.sh — project-specific inventory generator. Adapt to this project's layout.
# Regenerates registry/ files the agents grep before building (anti-duplication).
echo "TODO: implement scan for this project (see another project's scan.sh)."
EOF
  chmod +x "$D/scripts/scan.sh"
fi

# ── 8. seed the project brain ────────────────────────────────────────────────
[ -f "$D/troubleshooting/playbook.md" ] || cat > "$D/troubleshooting/playbook.md" <<EOF
# $name — Playbook (bugs fixed, never twice)

Append an entry per fixed bug. Curator promotes cross-project ones to ~/ai-toolkit/patterns/.

### PB-0001 — <symptom>
- First seen: $(date +%Y-%m-%d)
- Root cause: <cause>
- Fix: <fix>
- Detectable: <grep or n/a>
EOF
[ -f "$D/decisions/README.md" ] || echo "# $name — Architecture Decision Records (ADRs)" > "$D/decisions/README.md"
[ -f "$D/registry/.gitkeep" ] || touch "$D/registry/.gitkeep"

# ── 9. project.config.md template ────────────────────────────────────────────
if [ ! -f "$D/project.config.md" ]; then
  cat > "$D/project.config.md" <<EOF
# $name — Project Config (the ONLY project-specific brain the agents read)
# Fill every TODO. Agents read this on activation; leaving TODOs causes wrong behavior.

PROJECT_NAME=$name
PROJECT_TYPE=TODO            # e.g. web-app | ml-platform | api
WORKSPACE_ROOT=$PROJECT
DESCRIPTION=TODO

# ── Ops script (anti-hang: agents never run servers directly) ──
OPS_SCRIPT=./manage.sh
OPS_START=./manage.sh start
OPS_STOP=./manage.sh stop
OPS_RESTART=./manage.sh restart
OPS_STATUS=./manage.sh status
OPS_LOGS=./manage.sh logs
OPS_TEST=./manage.sh test

# ── Backend ──
BACKEND_DIR=TODO
BACKEND_FRAMEWORK=TODO        # FastAPI | Django  → selects frameworks/<x>.md
BACKEND_PORT=TODO
BACKEND_VENV=TODO
BACKEND_ACTIVATE=TODO
BACKEND_CHECK_CMD=TODO
BACKEND_DB=TODO

# ── Frontend ──
FRONTEND_DIR=TODO
FRONTEND_FRAMEWORK=TODO
FRONTEND_PORT=TODO
FRONTEND_LINT_CMD=TODO
FRONTEND_BUILD_CMD=TODO

# ── Design / UX ──
DESIGN_LANGUAGE=TODO          # e.g. enterprise-dense (Palantir/Ataccama)
DESIGN_REFERENCE=TODO         # a reference component for this project's look
NAVIGATION_PATTERN=TODO       # sidebar | top-tabs
DEFAULT_TIMEZONE=UTC

# ── Deploy ──
DEPLOY_TYPE=TODO
DEPLOY_PORT=TODO
DEPLOY_DB=TODO

# ── Docs ──
ARCHITECTURE_DOC=TODO
TASKS=TASKS.md

# ── HARD RULES (project-specific non-negotiables the agents must never break) ──
# - TODO: e.g. "No Redis. No Celery." / "Port 8007 only." / "API keys hashed."
EOF
fi
echo "  ✓ project.config.md template written (fill the TODOs)"

# ── done ─────────────────────────────────────────────────────────────────────
cat <<EOF

────────────────────────────────────────────────────────────
✅ '$name' onboarded. Next steps:
  1. Fill $D/project.config.md (all TODOs — esp. BACKEND_FRAMEWORK)
  2. Adapt the copied role starters in $D/roles/ (paths, layer rules)
  3. Implement $D/scripts/scan.sh for this project's layout
  4. Register the project in $CENTRAL/AGENTS.md (Projects table)
  5. Verify:  cd $PROJECT && ./.ai-toolkit/scripts/activate.sh
────────────────────────────────────────────────────────────
EOF
