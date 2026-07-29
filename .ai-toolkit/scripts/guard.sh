#!/usr/bin/env bash
# .ai-toolkit/scripts/guard.sh
# Deterministic PreToolUse guard. Reads the tool-use JSON on stdin and BLOCKS
# (permissionDecision: deny) if an edit/write introduces a hardcoded secret.
# This is ENFORCEMENT, not guidance — it cannot be talked out of.
#
# Wired via .github/hooks/*.json (Copilot) — see that file.
# Exit 0 = allow. Exit 2 = block. Never crash the agent: on any parse issue, allow.

set -uo pipefail

INPUT="$(cat 2>/dev/null || true)"

allow() { printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}\n'; exit 0; }
deny()  {
  local reason="$1"
  # JSON-escape the reason minimally
  reason="${reason//\\/\\\\}"; reason="${reason//\"/\\\"}"
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$reason"
  exit 2
}

# No python or no input → don't block anything.
command -v python3 >/dev/null 2>&1 || allow
[ -n "$INPUT" ] || allow

RESULT="$(GUARD_INPUT="$INPUT" python3 - <<'PY' 2>/dev/null || true
import os, json, re

raw = os.environ.get("GUARD_INPUT", "")
try:
    data = json.loads(raw)
except Exception:
    print("ALLOW"); raise SystemExit(0)

# Tool name lives under different keys depending on host; check the common ones.
tool = (data.get("toolName") or data.get("tool") or
        data.get("hookSpecificOutput", {}).get("toolName") or "")
tool_l = str(tool).lower()

# Only guard edit/write tools; reads/searches are always allowed.
EDIT_HINTS = ("edit", "create_file", "write", "replace_string", "insert", "apply_patch", "patch")
is_edit = any(h in tool_l for h in EDIT_HINTS)

# Gather any text payload we can find (file content / new strings).
blob_parts = []
def walk(o):
    if isinstance(o, str):
        blob_parts.append(o)
    elif isinstance(o, dict):
        for v in o.values(): walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)

ti = data.get("toolInput") or data.get("input") or data.get("arguments") or data
walk(ti)
blob = "\n".join(blob_parts)

if not is_edit or not blob:
    print("ALLOW"); raise SystemExit(0)

# Hardcoded secret pattern: key = "long-literal", excluding env reads and placeholders.
secret_re = re.compile(
    r'(?i)(api[_-]?key|secret[_-]?key|secret|password|passwd|token|access[_-]?key)'
    r'\s*[:=]\s*["\']([A-Za-z0-9_\-/+]{16,})["\']'
)
SAFE = ("getenv", "environ", "import.meta.env", "process.env", "example", "dummy",
        "placeholder", "changeme", "your-", "xxxx", "<", "test", "sample", "os.getenv")

for m in secret_re.finditer(blob):
    line = m.group(0)
    low = line.lower()
    if any(s in low for s in SAFE):
        continue
    # Looks like a real hardcoded secret.
    key = m.group(1)
    print("DENY::Hardcoded secret detected (%s=...). Move it to an environment variable "
          "(os.getenv / import.meta.env) — see .ai-toolkit/shared/security.md." % key)
    raise SystemExit(0)

print("ALLOW")
PY
)"

case "$RESULT" in
  DENY::*) deny "${RESULT#DENY::}" ;;
  *)       allow ;;
esac
