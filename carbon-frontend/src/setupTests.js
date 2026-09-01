import '@testing-library/jest-dom/vitest';
import { vi, beforeEach } from 'vitest';

// Mock react-i18next globally. The mock resolves keys through the real i18n
// singleton (initialized to `en`), so migrated components keep rendering the
// same English copy as before migration.
vi.mock('react-i18next', () => import('./__mocks__/react-i18next.js'));

// Isolate per-test browser storage. Hooks like `useDraftPersistence` write
// drafts to localStorage (and flush on unmount), so without this a draft from
// one test leaks into the next and makes assertions order-dependent.
beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});
