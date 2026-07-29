# TASK-ANTIPATTERNS-FRONTEND — Fix Pre-existing Frontend Antipatterns

## Summary
Fix the pre-existing frontend antipatterns flagged by `verify.sh antipatterns`. Three categories: MUI v5 Grid syntax → v7, raw `fetch()` → `apiFetch()`, hardcoded hex colors → theme tokens.

---

## Fix 1 — MUI Grid v5 → v7 `size` prop (3 files, 5 instances)

MUI v7 deprecates `item` + `xs={N}` / `sm={N}` syntax on `<Grid>`. Replace with `size={{ xs: N, sm: N, md: N }}`.

### 1a. `src/components/Layout/ResponsiveGrid.jsx:9`

**Current:**
```jsx
<Grid item xs={12} sm={6} md={4}>
  {child}
</Grid>
```
**Fix:**
```jsx
<Grid size={{ xs: 12, sm: 6, md: 4 }}>
  {child}
</Grid>
```

### 1b. `src/components/entity/EntityDetailShell.jsx:331`

**Current:**
```jsx
<Grid item xs={12} sm={6} md={3} key={card.title}>
```
**Fix:**
```jsx
<Grid size={{ xs: 12, sm: 6, md: 3 }} key={card.title}>
```

### 1c. `src/components/entity/EntityDetailShell.jsx:343`

**Current:**
```jsx
<Grid item xs={12} lg={9}>
```
**Fix:**
```jsx
<Grid size={{ xs: 12, lg: 9 }}>
```

### 1d. `src/components/entity/EntityDetailShell.jsx:358`

**Current:**
```jsx
<Grid item xs={12} lg={3}>
```
**Fix:**
```jsx
<Grid size={{ xs: 12, lg: 3 }}>
```

### 1e. `src/components/dq/DQMetricsPanel.jsx:102`

**Current:**
```jsx
<Grid item xs={12} sm={6}>
```
**Fix:**
```jsx
<Grid size={{ xs: 12, sm: 6 }}>
```

---

## Fix 2 — raw `fetch()` → `apiFetch()` (3 files, 3 instances)

The project has `src/api/api.js` → `apiFetch(url, options)` which handles JWT tokens, refresh, base URL, and unified error feedback. Use it instead of raw `fetch()` + manual Authorization header.

### 2a. `src/config.js:30` — API reachability health check

**Current:**
```js
const res = await fetch(url, { method: 'GET' });
```
**Fix:** This is a startup health-check without auth. `apiFetch` adds auth headers. Two options:
- Use `fetch(url, { method: 'GET' })` but extract to a named helper `checkApiReachable(url)` with a comment explaining the exemption.
- Or leave as-is with a `// gate-exempt: pre-auth health check` comment.

**Recommended:** Add comment exemption — `apiFetch` requires auth context that may not exist at this point.

### 2b. `src/components/TableDataPage.jsx:251` — template download

**Current (approximate):**
```js
const response = await fetch(url, {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${token}`,
    'X-Project-ID': project_id,
    'X-Module-ID': module_id,
  },
});
```
**Fix:** Replace with `apiFetch`. Check if `apiFetch` supports custom headers passthrough. If it does, pass `{ headers: { 'X-Module-ID': module_id } }`. If the template download is a blob/binary response, `apiFetch` may need adjustment — verify it handles non-JSON responses.

### 2c. `src/components/import/BulkImportWizard.jsx:246` — file upload

**Current:**
```js
const response = await fetch(`${API_BASE_URL}datarows/bulk-import/`, {
  method: 'POST',
  headers: { 'Authorization': `Token ${token}` },
  body: formData,
});
```
**Fix:** Replace with `apiFetch`. Note: `FormData` uploads must NOT set `Content-Type` header (browser auto-sets with boundary). Ensure `apiFetch` doesn't force `application/json` when body is `FormData`.

---

### Files EXEMPT from fetch → apiFetch (document in code with comment)

| File | Reason |
|------|--------|
| `src/api/api.js` | This IS the apiFetch implementation |
| `src/auth/AuthContext.jsx` | Auth bootstrap — runs before user is authenticated |
| `src/auth/pulseAuth.js` | Pulse is a different host, not the Django API |
| `src/pages/SettingsPage.jsx` | Pulse API calls (different host) |

---

## Fix 3 — Hardcoded hex colors → theme tokens (1 file)

### 3a. `src/components/HeaderEnhanced.jsx:57-95`

**Current `RoleBadge`:**
```jsx
function RoleBadge({ role }) {
  const ROLE_COLOR = {
    admins_group: { bg: "rgba(220,38,38,0.1)", text: "#dc2626" },
    dataowners_group: { bg: "rgba(37,99,235,0.1)", text: "#2563eb" },
    auditors_group: { bg: "rgba(245,158,11,0.1)", text: "#d97706" },
  };
  const s = ROLE_COLOR[role] || { bg: "rgba(113,113,122,0.1)", text: "#71717a" };
```
**Fix:** Map roles to theme palette colors:
- `admins_group` → `error.main` (#dc2626 is red)
- `dataowners_group` → `primary.main` (#2563eb is blue = Carbon's primary)
- `auditors_group` → `warning.main` (#d97706 is amber)
- Default → `text.disabled` or `grey.500`

Use `useTheme()` or `sx` with theme-aware values.

**Current AppBar:**
```jsx
sx={{
  bgcolor: "#fff",
  borderBottom: "1px solid #e5e7eb",
  color: "#111827",
}}
```
**Fix:**
```jsx
sx={{
  bgcolor: "background.paper",
  borderBottom: 1,
  borderColor: "divider",
  color: "text.primary",
}}
```

---

## DO-NOT-TOUCH

- ❌ `src/api/api.js` — the apiFetch implementation itself
- ❌ `src/auth/AuthContext.jsx` — auth bootstrap
- ❌ `src/auth/pulseAuth.js` — Pulse integration (different host)
- ❌ `src/pages/SettingsPage.jsx` — Pulse API calls
- ❌ Backend files (`backend/`)
- ❌ No package.json changes, no new dependencies
- ❌ No route changes

---

## Verification Checklist

```bash
# 1. Build must pass
cd carbon-frontend && npm run build

# 2. AI Toolkit antipatterns gate — should show FEWER violations
cd .. && bash .ai-toolkit/scripts/verify.sh antipatterns

# 3. After fixes, expected remaining gate output:
#    - 0 MUI v5 Grid violations (was 3 files / 5 instances)
#    - 2 raw fetch() violations (SettingsPage Pulse calls — exempt)
#    - 0 hardcoded hex color violations (was 1 file)
#    - Backend violations unchanged (separate task)
```

## Success Criteria

- [ ] `npm run build` — no errors
- [ ] `verify.sh antipatterns` — zero "MUI v5 Grid syntax" violations
- [ ] `verify.sh antipatterns` — zero "hardcoded hex color" violations
- [ ] `verify.sh antipatterns` — at most 2 "raw fetch()" violations (SettingsPage Pulse, exempt)
- [ ] No files outside the listed files were changed
