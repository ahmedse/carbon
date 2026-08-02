# TASKS-P10a-FIX-title — Add Page-Specific Document Titles (P1-01)

**Phase:** P10a-FIX | **Role:** frontend-worker | **Model:** Kimi K3
**Source:** `TASK-RESULTS-P10a.md` finding P1-01

---

## PROBLEM

Every page shows `document.title = "AAST Carbon Platform"` (the static `<title>` in `index.html`).
No page updates the title dynamically. This causes:
- No browser history differentiation (every tab shows same title)
- Accessibility issue for screen readers
- Poor UX

---

## SOLUTION: Create a `useDocumentTitle` hook, apply to 11 core routes

### Step 1: Create the hook

**File:** `carbon-frontend/src/hooks/useDocumentTitle.js`

```js
import { useEffect } from "react";

const APP_NAME = "Carbon Platform";

export default function useDocumentTitle(title) {
  useEffect(() => {
    const prev = document.title;
    document.title = title ? `${title} — ${APP_NAME}` : APP_NAME;
    return () => { document.title = prev; };
  }, [title]);
}
```

### Step 2: Apply to these 11 files

For each file below, add `import useDocumentTitle from "../hooks/useDocumentTitle";` (adjust relative path) and call `useDocumentTitle("Page Name");` at the top of the component.

| # | File | Title string | Import path from hooks |
|---|------|-------------|----------------------|
| 1 | `src/pages/Login.jsx` | `"Sign In"` | `"../hooks/useDocumentTitle"` |
| 2 | `src/pages/NotFound.jsx` | `"Page Not Found"` | `"../hooks/useDocumentTitle"` |
| 3 | `src/pages/SettingsPage.jsx` | `"Settings"` | `"../hooks/useDocumentTitle"` |
| 4 | `src/pages/Help.jsx` | `"Help"` | `"../hooks/useDocumentTitle"` |
| 5 | `src/pages/Feedback.jsx` | `"Feedback"` | `"../hooks/useDocumentTitle"` |
| 6 | `src/pages/EmissionsDashboard.jsx` | `"Emissions"` | `"../hooks/useDocumentTitle"` |
| 7 | `src/pages/EmissionsReport.jsx` | `"Emissions Report"` | `"../hooks/useDocumentTitle"` |
| 8 | `src/pages/carbon/CarbonConsolePage.jsx` | `"Console"` | `"../../hooks/useDocumentTitle"` |
| 9 | `src/pages/carbon/MyDataPage.jsx` | `"My Data"` | `"../../hooks/useDocumentTitle"` |
| 10 | `src/shell/Shell.jsx` | `"Home"` | `"../hooks/useDocumentTitle"` |

For `Shell.jsx` (the landing page `/`), add it near the top of the component body, before the return statement.

The `useDocumentTitle` hook already handles:
- Setting title on mount: `"Page Name — Carbon Platform"`
- Restoring previous title on unmount (cleanup)
- No title = default: `"Carbon Platform"`

### Step 3: Verify

After applying, verify:
```bash
cd carbon-frontend && npm run build
```
Must pass with 0 errors. Then verify in browser that each page shows a unique tab title.

---

## DO NOT TOUCH

- `index.html` — the static fallback `<title>` stays as-is (it's the default before JS loads)
- Any backend files
- Any other pages not listed above (those are for P10b+)
- `App.jsx` route definitions

---

## CONTRACTS

| Contract | File |
|----------|------|
| Base rules | `.ai-toolkit/shared/base-rules.md` |
| Design patterns | `.ai-toolkit/shared/design-patterns.md` |
| Project config | `.ai-toolkit/project.config.md` |

---

## VERIFICATION GATE

```bash
cd /home/ahmed/aast/carbon && .ai-toolkit/scripts/verify.sh full
cd /home/ahmed/aast/carbon/carbon-frontend && npm run build
```
Both must pass. Write `TASK-RESULTS-P10a-FIX-title.md` with terminal output.
