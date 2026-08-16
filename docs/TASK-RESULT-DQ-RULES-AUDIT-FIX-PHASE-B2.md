# TASK-RESULT — DQ-RULES-AUDIT-FIX (Phase B2 — Frontend filters)

**Task ID:** `DQ-RULES-AUDIT-FIX` — Phase B (T8)
**Source:** `docs/TASK-DQ-RULES-AUDIT-FIX.md`
**Role:** Frontend Worker
**Date:** 2026-08-16

---

## 1. Result

✅ **T8 — forward all filter params (F4)** complete and verified end-to-end.

`carbon-frontend/src/api/dq.js` `listDQRules()` now forwards every supported filter param
(`search`, `rule_level`, `rule_type`, `dimension`, `severity`, `is_active`, `tag`,
`data_table`, `data_field`, `include_archived`), skipping `null`/`undefined`/`''`. It uses
`search` (backend SearchFilter), not `q`.

**Root cause confirmed:** `RulesTab.load()` already built the correct params object, but
`listDQRules()` only forwarded `data_table`/`data_field` and silently dropped the rest —
so search and every dropdown were dead.

---

## 2. Code change

`carbon-frontend/src/api/dq.js` — `listDQRules()`:

```js
export function listDQRules(token, filters = {}) {
  const FORWARDED = [
    'search', 'rule_level', 'rule_type', 'dimension', 'severity',
    'is_active', 'tag', 'data_table', 'data_field', 'include_archived',
  ];
  const params = new URLSearchParams();
  FORWARDED.forEach((key) => {
    const value = filters[key];
    if (value !== null && value !== undefined && value !== '') {
      params.set(key, value);
    }
  });
  const qs = params.toString();
  return apiFetch(`${API_ROUTES.dqRules}${qs ? `?${qs}` : ''}`, { token });
}
```

Reuses `apiFetch` (no raw fetch). No other files touched (RulesTab.jsx, bindings.js,
DefinitionTab.jsx, backend all untouched).

---

## 3. Gates

```bash
cd carbon-frontend && npm run lint      → 0 errors (no output)
npm run build                           → clean build
./.ai-toolkit/scripts/verify.sh frontend
```

```
Verification gate: frontend
════════════════════════════════════════
── Frontend ────────────────────────────
✓ lint
✓ build
── Routes ──────────────────────────────
✓ route audit clean: 72 referenced path(s) resolve, 16 namespace root(s) covered
✓ route/URL audit
════════════════════════════════════════
GATE PASSED
```

---

## 4. Browser smoke

Seeded three rules with distinct severities/names (ids 110–112, since deleted):

| id | name | severity |
|----|------|----------|
| 110 | Filter smoke alpha | error |
| 111 | Filter smoke beta | warn |
| 112 | Unique gamma | info |

**Search box:** typed `beta` → grid narrowed to `1–1 of 1` showing only "Filter smoke beta".

**Severity dropdown:** opened Filters → Severity "Warning" → grid narrowed to `1–1 of 1`
showing only "Filter smoke beta".

**Backend access-log proof (query strings actually forwarded):**
```
GET /carbon-api/dq/rules/?search=beta&is_active=true HTTP/1.1
GET /carbon-api/dq/rules/?severity=warn HTTP/1.1
GET /carbon-api/dq/rules/?severity=warn&is_active=true HTTP/1.1
```
Before the fix these would have been bare `?` / dropped entirely.

---

## 5. Cleanup

Test rules 110–112 hard-deleted; DB rule table empty (pre-existing smoke rules had been
removed by an earlier cleanup).
