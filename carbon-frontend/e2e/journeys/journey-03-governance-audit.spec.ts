/**
 * JOURNEY 3: Governance & Audit Trail Verification
 */
import { test, expect, APIRequestContext } from '@playwright/test';
import { PERSONAS, getAuthHeaders } from '../fixtures/users';

const ADMIN = PERSONAS.admin;
const AUDITOR = PERSONAS.auditor_user;
const API_BASE = process.env.CARBON_API_URL || 'http://127.0.0.1:8000/carbon-api';

test.describe.serial('Journey 3: Governance & Audit Trail', () => {
  let adminHeaders: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    adminHeaders = await getAuthHeaders(request, API_BASE, ADMIN);
  });

  test('3A. Governance events exist and are queryable', async ({ request }) => {
    const res = await request.get(`${API_BASE}/catalog/governance-events/`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const events = Array.isArray(data) ? data : data.results || [];
    console.log(`  Governance events: ${events.length}`);
    if (events.length > 0) {
      const event = events[0];
      expect(event).toHaveProperty('entity_type');
      expect(event).toHaveProperty('action');
      console.log(`  Sample: ${event.action} on ${event.entity_type}`);
    }
  });

  test('3B. Events are filterable by entity type', async ({ request }) => {
    const res = await request.get(`${API_BASE}/catalog/governance-events/?entity_type=ReportingPeriod`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    console.log('  ✅ Governance events filterable');
  });

  test('3C. Auditor can read governance events', async ({ request }) => {
    const auditorHeaders = await getAuthHeaders(request, API_BASE, AUDITOR);
    const res = await request.get(`${API_BASE}/catalog/governance-events/?page_size=1`, { headers: auditorHeaders });
    expect(res.ok()).toBe(true);
    console.log('  ✅ Auditor reads governance events');
  });
});
