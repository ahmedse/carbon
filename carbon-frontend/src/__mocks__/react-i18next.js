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

const i18n = i18next.createInstance();
i18n.init({
  resources: {
    en: { common: enCommon, shell: enShell, auth: enAuth, errors: enErrors },
  },
  lng: 'en',
  fallbackLng: 'en',
  ns: ['common', 'shell', 'auth', 'errors'],
  defaultNS: 'common',
  interpolation: {
    // React already escapes — no double escaping.
    escapeValue: false,
  },
  // Bundled resources — initialize synchronously.
  initImmediate: false,
});

export const useTranslation = (ns) => {
  const namespaces = Array.isArray(ns) ? ns : ns ? [ns] : ['common'];
  return {
    t: (key, options) => {
      if (typeof key !== 'string') return i18n.t(key, options);
      // Colon-prefixed keys (e.g. 'shell:nav.home') already carry a namespace.
      if (key.includes(':')) return i18n.t(key, options);
      return i18n.t(key, { ...options, ns: namespaces });
    },
    i18n,
    ready: true,
  };
};

export const initReactI18next = { type: '3rdParty', init: () => {} };

// Trans passthrough — renders children unchanged (no interpolation in tests).
export function Trans({ children }) {
  return children;
}
