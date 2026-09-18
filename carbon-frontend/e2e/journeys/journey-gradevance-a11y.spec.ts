/**
 * GradeVance a11y smoke — landmarks + skip link on each studio route.
 * Not a full VPAT; writes a JSON summary under docs/eduos/vpat-evidence when
 * GRADEVANCE_A11Y_WRITE_EVIDENCE=1.
 */
import { test, expect } from '@playwright/test';
import { PERSONAS, login } from '../fixtures/users';
import * as fs from 'fs';
import * as path from 'path';

const ADMIN = { ...PERSONAS.admin, password: 'dev-admin-5c' };

const ROUTES = [
  '/apps/gradevance',
  '/apps/gradevance/library',
  '/apps/gradevance/authoring',
  '/apps/gradevance/student',
  '/apps/gradevance/marking',
  '/apps/gradevance/proposals',
];

test.describe('GradeVance a11y smoke', () => {
  test('each studio has main landmark and skip link', async ({ page }) => {
    const ok = await login(page, ADMIN);
    test.skip(!ok, 'login failed — skip a11y smoke');

    const results: Array<{ route: string; main: boolean; skip: boolean }> = [];

    for (const route of ROUTES) {
      await page.goto(route);
      await page.waitForLoadState('networkidle').catch(() => {});
      const main = await page.locator('main').count();
      const skip = await page.getByRole('link', { name: /skip to main content/i }).count();
      results.push({ route, main: main > 0, skip: skip > 0 });
      expect(main, `${route} missing <main>`).toBeGreaterThan(0);
      expect(skip, `${route} missing skip link`).toBeGreaterThan(0);
    }

    if (process.env.GRADEVANCE_A11Y_WRITE_EVIDENCE === '1') {
      const outDir = path.resolve(__dirname, '../../../docs/eduos/vpat-evidence');
      fs.mkdirSync(outDir, { recursive: true });
      const out = path.join(outDir, 'playwright-landmarks.json');
      fs.writeFileSync(
        out,
        JSON.stringify(
          {
            generated_at: new Date().toISOString(),
            standard: 'WCAG 2.2 AA (landmarks smoke)',
            results,
          },
          null,
          2,
        ),
      );
    }
  });
});
