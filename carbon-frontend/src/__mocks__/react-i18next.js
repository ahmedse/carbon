// src/__mocks__/react-i18next.js
// Vitest manual mock for react-i18next, registered globally in src/setupTests.js.
//
// `t` resolves keys through a STANDALONE i18next instance (English only), so
// migrated components render the SAME English copy they rendered before
// migration — existing test expectations stay green without updating assertions.
//
// IMPORTANT: this mock must NOT import ../i18n/index. That module imports
// `react-i18next` (which is mocked here), creating a circular dependency that
// deadlocks the Vitest module graph: react-i18next -> __mocks__/react-i18next.js
// -> ../i18n/index -> react-i18next. Importing i18next + the JSON catalogs
// directly keeps the mock self-contained and cycle-free.

import i18next from 'i18next';

import enCommon from '../i18n/locales/en/common.json';
import enShell from '../i18n/locales/en/shell.json';
import enAuth from '../i18n/locales/en/auth.json';
import enErrors from '../i18n/locales/en/errors.json';
import enAi from '../i18n/locales/en/ai.json';
import enCatalog from '../i18n/locales/en/catalog.json';
import enNotes from '../i18n/locales/en/notes.json';
import enEmissions from '../i18n/locales/en/emissions.json';
import enEvidence from '../i18n/locales/en/evidence.json';
import enImportExport from '../i18n/locales/en/importexport.json';
import enConnections from '../i18n/locales/en/connections.json';
import enDq from '../i18n/locales/en/dq.json';
import enDataschema from '../i18n/locales/en/dataschema.json';

const i18n = i18next.createInstance();
i18n.init({
  resources: {
    en: { common: enCommon, shell: enShell, auth: enAuth, errors: enErrors, ai: enAi, catalog: enCatalog, notes: enNotes, emissions: enEmissions, evidence: enEvidence, importexport: enImportExport, connections: enConnections, dq: enDq, dataschema: enDataschema },
  },
  lng: 'en',
  fallbackLng: 'en',
  ns: ['common', 'shell', 'auth', 'errors', 'ai', 'catalog', 'notes', 'emissions', 'evidence', 'importexport', 'connections', 'dq', 'dataschema'],
  defaultNS: 'common',
  interpolation: {
    // React already escapes — no double escaping.
    escapeValue: false,
  },
  // Bundled resources — initialize synchronously.
  initImmediate: false,
});

// Cache `t` per namespace so `useTranslation` returns a STABLE function
// reference across renders. Real react-i18next memoizes `t`; without this, any
// `useCallback`/`useEffect` that lists `t` in its deps re-fires on every render,
// causing infinite re-render loops in tests.
const tCache = new Map();

export const useTranslation = (ns) => {
  const namespaces = Array.isArray(ns) ? ns : ns ? [ns] : ['common'];
  const cacheKey = namespaces.join('|');
  let t = tCache.get(cacheKey);
  if (!t) {
    t = (key, options) => {
      if (typeof key !== 'string') return i18n.t(key, options);
      // Colon-prefixed keys (e.g. 'shell:nav.home') already carry a namespace.
      if (key.includes(':')) return i18n.t(key, options);
      return i18n.t(key, { ...options, ns: namespaces });
    };
    tCache.set(cacheKey, t);
  }
  return {
    t,
    i18n,
    ready: true,
  };
};

export const initReactI18next = { type: '3rdParty', init: () => {} };

// Trans passthrough — renders children unchanged (no interpolation in tests).
export function Trans({ children }) {
  return children;
}
