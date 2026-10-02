#!/usr/bin/env bash
# Build a People-only source archive (no Pulse, no Data Trust product).
# Does not start, stop, or touch the running stack.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST_DIR="$ROOT/shipping/people-slice"
INCLUDE="$MANIFEST_DIR/include.txt"
EXCLUDE_GLOBS="$MANIFEST_DIR/exclude-globs.txt"
LEAK="$MANIFEST_DIR/leak-paths.txt"
STAMP="$(date +%Y%m%d)"
OUT_DIR="${OUT_DIR:-$ROOT/dist/people-slice}"
ARCHIVE="${ARCHIVE:-$ROOT/dist/people-slice-${STAMP}.tar.gz}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--out DIR] [--archive FILE.tar.gz]

Copies the People partner slice defined in shipping/people-slice/.
Fails if Pulse or Data Trust product paths leak into the destination.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT_DIR="$2"; shift 2 ;;
    --archive) ARCHIVE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

for f in "$INCLUDE" "$EXCLUDE_GLOBS" "$LEAK"; do
  [[ -f "$f" ]] || { echo "Missing manifest: $f" >&2; exit 1; }
done

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

copy_one() {
  local rel="$1"
  local src="$ROOT/$rel"
  local dest="$OUT_DIR/$rel"
  if [[ -d "$src" ]]; then
    mkdir -p "$dest"
    rsync -a --delete \
      --exclude '__pycache__/' \
      --exclude '*.pyc' \
      --exclude '.git/' \
      --exclude '.env' \
      --exclude '.env.*' \
      "$src/" "$dest/"
  elif [[ -f "$src" ]]; then
    mkdir -p "$(dirname "$dest")"
    rsync -a "$src" "$dest"
  else
    echo "Skip (missing in repo): $rel" >&2
  fi
}

while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%%#*}"
  line="$(echo "$line" | sed 's/[[:space:]]*$//')"
  [[ -z "$line" ]] && continue
  copy_one "$line"
done < "$INCLUDE"

# Drop Pulse / Data Trust / other-product trees if an include was too broad.
prune_if_present() {
  local p
  for p in "$@"; do
    [[ -e "$p" ]] && rm -rf "$p"
  done
}
prune_if_present \
  "$OUT_DIR/backend/ai" \
  "$OUT_DIR/docs/pulse" \
  "$OUT_DIR/assurance" \
  "$OUT_DIR/backend/catalog" \
  "$OUT_DIR/backend/dq" \
  "$OUT_DIR/backend/mdm" \
  "$OUT_DIR/backend/dataschema" \
  "$OUT_DIR/backend/connections" \
  "$OUT_DIR/backend/importexport" \
  "$OUT_DIR/backend/inbound" \
  "$OUT_DIR/backend/evidence" \
  "$OUT_DIR/backend/gradevance" \
  "$OUT_DIR/backend/healthy" \
  "$OUT_DIR/backend/emissions" \
  "$OUT_DIR/backend/guide" \
  "$OUT_DIR/backend/excellence" \
  "$OUT_DIR/domain_packs" \
  "$OUT_DIR/.ai-toolkit" \
  "$OUT_DIR/carbon-frontend/src/pages/catalog" \
  "$OUT_DIR/carbon-frontend/src/pages/dq" \
  "$OUT_DIR/carbon-frontend/src/pages/admin/ai" \
  "$OUT_DIR/carbon-frontend/src/pages/admin/catalog" \
  "$OUT_DIR/carbon-frontend/src/pages/admin/migration" \
  "$OUT_DIR/carbon-frontend/src/pages/embed" \
  "$OUT_DIR/carbon-frontend/src/components/ai" \
  "$OUT_DIR/carbon-frontend/src/components/dq" \
  "$OUT_DIR/carbon-frontend/src/components/CatalogRoute.jsx" \
  "$OUT_DIR/carbon-frontend/src/apps/people/OpsCanvasAttachButton.jsx"

find "$OUT_DIR" -type f \( -name '.env' -o -name '.env.*' -o -name '*.pem' -o -name '*.key' \) -delete 2>/dev/null || true
find "$OUT_DIR/carbon-frontend/src" -type f \( -name 'AI*' -o -name 'Pulse*' -o -name 'Agent*' -o -name 'OpsCanvas*' \) \
  \( -path '*/shell/*' -o -path '*/api/*' \) -delete 2>/dev/null || true
find "$OUT_DIR/carbon-frontend/src/api" -type f \( -name 'ai*.js' -o -name 'catalog*' -o -name 'dq.js' -o -name 'orgUnits.js' -o -name 'inbound.js' \) \
  -delete 2>/dev/null || true

# Extra Pulse tests that import host_executor (filename may vary).
if [[ -d "$OUT_DIR/backend/people/tests" ]]; then
  grep -rl 'ai\.host_executor\|from ai ' "$OUT_DIR/backend/people/tests" 2>/dev/null \
    | while read -r t; do rm -f "$t"; done || true
fi

# Strip leftover empty dirs from prune.
find "$OUT_DIR" -type d -empty -delete 2>/dev/null || true

cp "$MANIFEST_DIR/README.md" "$OUT_DIR/README.md"
cp "$INCLUDE" "$OUT_DIR/SLICE-include.txt"
{
  echo "exported_at: $(date -Iseconds)"
  echo "source_root: $ROOT"
  echo "profile: people-slice"
  echo "pulse: excluded"
  echo "data_trust_product: excluded"
  echo "runnable: no"
} > "$OUT_DIR/SLICE-META.txt"

fail=0
while IFS= read -r p || [[ -n "$p" ]]; do
  p="${p%%#*}"
  p="$(echo "$p" | sed 's/[[:space:]]*$//')"
  [[ -z "$p" ]] && continue
  if [[ -e "$OUT_DIR/$p" ]]; then
    echo "LEAK: $p" >&2
    fail=1
  fi
done < "$LEAK"

# Content scan for leftover Pulse / Data Trust product trees.
if grep -RIl --exclude-dir='.git' -E 'backend/ai/engine|docs/pulse|Pulse Control Plane' \
    "$OUT_DIR/carbon-frontend/src/apps" "$OUT_DIR/docs" 2>/dev/null | head -1 | grep -q .; then
  echo "LEAK: Pulse product text in People apps/docs" >&2
  fail=1
fi

if [[ "$fail" -ne 0 ]]; then
  echo "Export aborted: Pulse or Data Trust paths leaked. Fix the manifest." >&2
  exit 1
fi

mkdir -p "$(dirname "$ARCHIVE")"
tar -czf "$ARCHIVE" -C "$(dirname "$OUT_DIR")" "$(basename "$OUT_DIR")"

file_count="$(find "$OUT_DIR" -type f | wc -l | tr -d ' ')"
echo "People slice ready (review only, not runnable):"
echo "  files:    $file_count"
echo "  folder:   $OUT_DIR"
echo "  archive:  $ARCHIVE"
