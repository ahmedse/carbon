// E2E fixtures: user personas, authentication helpers, and API utilities.
// Models the actual RBAC roles: admin, dataowner, analyst, viewer, auditor, domain leads.
import { test as base, expect, Page, APIRequestContext } from '@playwright/test';

// ── User Personas ────────────────────────────────────────────────────────

export interface UserPersona {
  username: string;
  password: string;
  role: string;
  branch?: string;          // alamien | smart_village
  isGlobalAdmin: boolean;
  expectations: {
    canAccessAdmin: boolean;
    canSeeDashboard: boolean;
    canEnterData: boolean;
    canSeeDQ: boolean;
    canSeeGovernance: boolean;
    visibleBranches: string[];    // Branches this user should see in dropdowns
  };
}

export const PERSONAS: Record<string, UserPersona> = {
  // ── Platform admin (sees everything) ──
  admin: {
    username: 'admin',
    password: 'admin123',
    role: 'admins_group',
    isGlobalAdmin: true,
    expectations: {
      canAccessAdmin: true,
      canSeeDashboard: true,
      canEnterData: true,
      canSeeDQ: true,
      canSeeGovernance: true,
      visibleBranches: ['Alamein Campus', 'Smart Village Campus'],
    },
  },

  // ── Alamein branch users ──
  alamien_dataowner: {
    username: 'alamien_dataowner',
    password: 'data123',
    role: 'dataowners_group',
    branch: 'alamien',
    isGlobalAdmin: false,
    expectations: {
      canAccessAdmin: false,
      canSeeDashboard: true,
      canEnterData: true,
      canSeeDQ: true,
      canSeeGovernance: false,
      visibleBranches: ['Alamein Campus'],
    },
  },

  alamien_analyst: {
    username: 'alamien_analyst',
    password: 'analyst123',
    role: 'analysts_group',
    branch: 'alamien',
    isGlobalAdmin: false,
    expectations: {
      canAccessAdmin: false,
      canSeeDashboard: true,
      canEnterData: false,
      canSeeDQ: true,
      canSeeGovernance: false,
      visibleBranches: ['Alamein Campus'],
    },
  },

  alamien_viewer: {
    username: 'alamien_viewer',
    password: 'viewer123',
    role: 'viewers_group',
    branch: 'alamien',
    isGlobalAdmin: false,
    expectations: {
      canAccessAdmin: false,
      canSeeDashboard: true,
      canEnterData: false,
      canSeeDQ: true,
      canSeeGovernance: false,
      visibleBranches: ['Alamein Campus'],
    },
  },

  // ── Smart Village branch users ──
  sv_dataowner: {
    username: 'sv_dataowner',
    password: 'data123',
    role: 'dataowners_group',
    branch: 'smart_village',
    isGlobalAdmin: false,
    expectations: {
      canAccessAdmin: false,
      canSeeDashboard: true,
      canEnterData: true,
      canSeeDQ: true,
      canSeeGovernance: false,
      visibleBranches: ['Smart Village Campus'],
    },
  },

  sv_analyst: {
    username: 'sv_analyst',
    password: 'analyst123',
    role: 'analysts_group',
    branch: 'smart_village',
    isGlobalAdmin: false,
    expectations: {
      canAccessAdmin: false,
      canSeeDashboard: true,
      canEnterData: false,
      canSeeDQ: true,
      canSeeGovernance: false,
      visibleBranches: ['Smart Village Campus'],
    },
  },

  // ── Domain leads ──
  carbon_lead_user: {
    username: 'carbon_lead_user',
    password: 'lead123',
    role: 'carbon_lead',
    isGlobalAdmin: false,
    expectations: {
      canAccessAdmin: true,       // Can access carbon admin (domain lead)
      canSeeDashboard: true,
      canEnterData: true,
      canSeeDQ: true,
      canSeeGovernance: true,
      visibleBranches: ['Alamein Campus', 'Smart Village Campus'],
    },
  },

  // ── Auditor ──
  auditor_user: {
    username: 'auditor_user',
    password: 'audit123',
    role: 'auditors_group',
    isGlobalAdmin: false,
    expectations: {
      canAccessAdmin: false,
      canSeeDashboard: true,
      canEnterData: false,
      canSeeDQ: true,
      canSeeGovernance: true,
      visibleBranches: ['Alamein Campus', 'Smart Village Campus'],
    },
  },
};

// ── Auth helpers ─────────────────────────────────────────────────────────

export async function login(page: Page, persona: UserPersona) {
  await page.goto('/login');
  await page.waitForLoadState('networkidle');

  // MUI TextField renders <input> with label — use getByLabel for reliability
  const usernameField = page.getByLabel('Username');
  const passwordField = page.getByLabel('Password');

  await usernameField.waitFor({ state: 'visible', timeout: 10000 });
  await usernameField.fill(persona.username);
  await passwordField.fill(persona.password);

  // MUI Button with "Sign in" text
  const signInBtn = page.getByRole('button', { name: /sign in/i });
  await signInBtn.click();

  // Wait for navigation away from login page
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(1500);

  // Check we're on a dashboard/page — should NOT be on login anymore
  return !page.url().includes('/login');
}

export async function apiLogin(request: APIRequestContext, baseURL: string, persona: UserPersona): Promise<string | null> {
  const res = await request.post(`${baseURL}/token/`, {
    data: { username: persona.username, password: persona.password },
  });
  if (res.ok()) {
    const body = await res.json();
    return body.access;
  }
  return null;
}

// Rate-limit-aware version: retries with backoff, handles the 5/min login throttle
export async function apiLoginWithRetry(
  request: APIRequestContext, baseURL: string, persona: UserPersona, maxRetries = 5
): Promise<string> {
  for (let i = 0; i < maxRetries; i++) {
    const token = await apiLogin(request, baseURL, persona);
    if (token) return token;
    // Wait with increasing backoff: 3s, 10s, 20s, 30s, 45s — enough to slide the 1-min window
    const delay = [3000, 10000, 20000, 30000, 45000][i] || 30000;
    console.log(`  ⏳ Rate-limited for ${persona.username}, retrying in ${delay / 1000}s (attempt ${i + 1}/${maxRetries})...`);
    await new Promise(r => setTimeout(r, delay));
  }
  throw new Error(`Failed to authenticate ${persona.username} after ${maxRetries} retries`);
}

// Get auth headers with rate-limit handling
export async function getAuthHeaders(
  request: APIRequestContext, baseURL: string, persona: UserPersona
): Promise<Record<string, string>> {
  const token = await apiLoginWithRetry(request, baseURL, persona);
  return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
}

// ── Navigation helpers ───────────────────────────────────────────────────

export async function navigateTo(page: Page, path: string) {
  await page.goto(path);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(500);
}

export async function clickSidebarItem(page: Page, label: string) {
  const sidebar = page.locator('[data-testid="sidebar"], nav, .MuiDrawer-root').first();
  const item = sidebar.locator(`a, button, [role="menuitem"]`).filter({ hasText: label }).first();
  if (await item.isVisible({ timeout: 3000 }).catch(() => false)) {
    await item.click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
  }
}

// ── Assertion helpers ────────────────────────────────────────────────────

export async function assertVisible(page: Page, text: string, timeout = 5000) {
  await expect(page.getByText(text).first()).toBeVisible({ timeout });
}

export async function assertNotVisible(page: Page, text: string, timeout = 3000) {
  await expect(page.getByText(text).first()).not.toBeVisible({ timeout });
}

export async function assertURL(page: Page, contains: string) {
  await expect(page).toHaveURL(new RegExp(contains));
}

// ── Fixture extensions ──────────────────────────────────────────────────

export type CarbonFixture = {
  persona: UserPersona;
  apiToken: string | null;
};

export const testWithPersona = (personaKey: string) => {
  const persona = PERSONAS[personaKey];
  if (!persona) throw new Error(`Unknown persona: ${personaKey}`);

  return base.extend<CarbonFixture>({
    persona: async ({}, use) => {
      await use(persona);
    },
    apiToken: async ({ request, baseURL }, use) => {
      const apiBase = process.env.CARBON_API_URL || 'http://127.0.0.1:8000';
      const token = await apiLogin(request, apiBase, persona);
      await use(token);
    },
  });
};
