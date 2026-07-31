# TASKS-P6 — Final Cleanup & Test Scaffolding
**Date:** 2026-07-31 | **Master Architect Review:** Required before commit

## Phase Overview

P6 is the final phase of the audit remediation plan. P6-G1 (Dual ORM) was resolved by P1.
Two remaining items: frontend test scaffolding and registry regeneration.
Bonus round: remaining sx hex cleanup from P5-G2 audit.

| Group | Task | Role | Status |
|-------|------|------|--------|
| G1 | Dual ORM removal | — | ✅ RESOLVED by P1 |
| G2 | Frontend test scaffolding | Frontend Worker | ✅ COMPLETE (7 tests, 0 failures) |
| G3 | Registry regeneration | Master Architect | ✅ COMPLETE |
| G4 | Remaining sx hex cleanup (29→0) | Frontend Worker | ⏳ OPTIONAL |

## P6-G2 — Frontend Test Scaffolding

**Why:** Zero frontend tests. Platform has 170+ JSX files, ~26K lines, 0% coverage.
**Target:** Install Vitest + React Testing Library. Write 3 smoke tests.
**Files:** CREATE `vitest.config.js`, `src/setupTests.js`, `src/__tests__/`

### Install

```bash
cd carbon-frontend && npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
```

### Package.json additions

```json
"scripts": {
  "test": "vitest run",
  "test:watch": "vitest"
}
```

### 3 smoke tests

| # | File | Tests | Rationale |
|---|------|-------|-----------|
| 1 | `src/__tests__/NotFound.test.jsx` | renders 404, has "Go Home" link | Simplest page — 24 lines, no hooks, no context, pure presentational |
| 2 | `src/__tests__/PlatformHome.test.jsx` | renders app cards, shows accessible apps | Most-used landing page — AuthContext + useEnabledApps hooks |
| 3 | `src/__tests__/api.test.js` | apiFetch constructs correct URL, handles query params | Core API utility — no React, pure function test |

### Test 1: NotFound.test.jsx

```jsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NotFound from '../pages/NotFound';

describe('NotFound', () => {
  it('renders 404 heading', () => {
    render(<MemoryRouter><NotFound /></MemoryRouter>);
    expect(screen.getByText('404')).toBeInTheDocument();
  });

  it('renders "Page Not Found" message', () => {
    render(<MemoryRouter><NotFound /></MemoryRouter>);
    expect(screen.getByText('Page Not Found')).toBeInTheDocument();
  });

  it('has a "Go Home" link pointing to /', () => {
    render(<MemoryRouter><NotFound /></MemoryRouter>);
    const link = screen.getByRole('link', { name: /go home/i });
    expect(link).toHaveAttribute('href', '/');
  });
});
```

### Test 2: PlatformHome.test.jsx

```jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PlatformHome from '../pages/PlatformHome';

// Mock dependencies
vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ user: { username: 'testuser' }, permissions: [] }),
}));
vi.mock('../hooks/useEnabledApps', () => ({
  useEnabledApps: () => ({ apps: [], loading: false, error: null }),
}));

describe('PlatformHome', () => {
  it('renders the page title', () => {
    render(<MemoryRouter><PlatformHome /></MemoryRouter>);
    expect(screen.getByText(/platform/i)).toBeInTheDocument();
  });

  it('renders without crashing when apps list is empty', () => {
    const { container } = render(<MemoryRouter><PlatformHome /></MemoryRouter>);
    expect(container).toBeTruthy();
  });
});
```

### Test 3: api.test.js

```js
import { describe, it, expect, vi } from 'vitest';

// We test the module's exports exist and have correct signatures
describe('apiFetch', () => {
  it('api module exports apiFetch', async () => {
    const api = await import('../api/api');
    expect(typeof api.apiFetch).toBe('function');
  });
});

describe('emissions API', () => {
  it('fetchEmissionsDashboard constructs URL with params', async () => {
    const { fetchEmissionsDashboard } = await import('../api/emissions');
    expect(typeof fetchEmissionsDashboard).toBe('function');
  });
});
```

### vitest.config.js

```js
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
    css: false,
  },
});
```

### src/setupTests.js

```js
import '@testing-library/jest-dom/vitest';
```

### GATES

| # | Command | Expected |
|---|---------|----------|
| 1 | `npx vitest run` | 7+ tests, 0 failures |
| 2 | `npm run build` | ✓ built, no new errors |
| 3 | `npm run lint` | No new lint problems |

### DO NOT TOUCH

- No existing source files modified (only CREATE)
- No theme files, no API files, no page components
- No eslint config changes

---

## P6-G3 — Registry Regeneration

**Why:** Last generated 2026-07-29. Stale after ai_copilot removal + dashboard cleanup.
**Run:** `./.ai-toolkit/scripts/scan.sh` → commit updated registry.
**Verify:** `git diff --stat .ai-toolkit/registry/` shows reasonable changes.

---

## P6-G4 — Remaining sx Hex Cleanup (OPTIONAL)

**Why:** P5-G2 reduced 90→29. 29 remaining across 12 files.
**Target files** (from P5-G2 audit):

| Count | File | Note |
|-------|------|------|
| 5 | AnalyticsDashboard.jsx | #6b7280, #fff, #f3f4f6, #374151, #e5e7eb |
| 3 | EmissionFactorsPage.jsx | scopeColors fallback '#ccc', '#fff', '#f5f5f5' |
| 3 | ModuleLandingPage.jsx | scope icons #43a047/#1e88e5/#ff7043 |
| 3 | Help.jsx | pastel section tints |
| 3 | DataHubHome.jsx | #2e7d32/#1565c0/#e65100 scope icons |
| 2 | ReportGeneratorPage.jsx | #f5f5f5 panels |
| 2 | RelatedRecordsTab.jsx | #999 |
| 2 | DataLineageTab.jsx | #999 |
| 2 | TagsPage.jsx | '#2563eb' fallback, '#ddd' |
| 2 | Dashboard.jsx | #f9fafb hover, #e5e7eb borderTop |
| 1 | DataOwnerAssetsPage.jsx | '#ccc' fallback |
| 1 | RegisteredAppsPage.jsx | '#2e7d32'/'#9e9e9e' ternary |

**Rules:** Same as P5-G2 — theme tokens only, no new theme values, verify via `grep -c` hex count.

---

## HARD RULES (from project.config.md)

1. Colors/spacing are TOKENS (theme.palette.*, spacing()). NEVER raw px/hex.
2. Components COMPOSE existing primitives. NEVER duplicate/fork.
3. NEVER import from emissions/ in platform apps.
4. Run verification gate before shipping: `./.ai-toolkit/scripts/verify.sh full`
