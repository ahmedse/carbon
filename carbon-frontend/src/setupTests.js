import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

// Mock react-i18next globally. The mock resolves keys through the real i18n
// singleton (initialized to `en`), so migrated components keep rendering the
// same English copy as before migration.
vi.mock('react-i18next', () => import('./__mocks__/react-i18next.js'));
