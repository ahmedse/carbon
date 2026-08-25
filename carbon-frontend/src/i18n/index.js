// src/i18n/index.js — i18next init (ADR-0018, I18N-1 foundation)
// English is the default; Arabic is the second language. No navigator-language
// auto-detect — the initial language comes from localStorage `carbon.lang`.
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import enCommon from './locales/en/common.json';
import arCommon from './locales/ar/common.json';
import enShell from './locales/en/shell.json';
import arShell from './locales/ar/shell.json';
import enAuth from './locales/en/auth.json';
import arAuth from './locales/ar/auth.json';
import enErrors from './locales/en/errors.json';
import arErrors from './locales/ar/errors.json';

const STORAGE_KEY = 'carbon.lang';
const SUPPORTED_LANGS = ['en', 'ar'];

function getInitialLanguage() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && SUPPORTED_LANGS.includes(stored)) return stored;
  } catch {
    // localStorage unavailable — fall back to the default.
  }
  return 'en';
}

i18n.use(initReactI18next).init({
  resources: {
    en: { common: enCommon, shell: enShell, auth: enAuth, errors: enErrors },
    ar: { common: arCommon, shell: arShell, auth: arAuth, errors: arErrors },
  },
  lng: getInitialLanguage(),
  fallbackLng: 'en',
  supportedLngs: SUPPORTED_LANGS,
  ns: ['common', 'shell', 'auth', 'errors'],
  defaultNS: 'common',
  interpolation: {
    // React already escapes — no double escaping.
    escapeValue: false,
  },
  react: {
    // Never suspend rendering on missing translations — the `ready` flag in
    // LanguageProvider covers readiness instead.
    useSuspense: false,
  },
  // Resources are bundled (JSON imports) — initialize synchronously so
  // `i18n.isInitialized` is true immediately after this module evaluates.
  initImmediate: false,
});

export default i18n;
