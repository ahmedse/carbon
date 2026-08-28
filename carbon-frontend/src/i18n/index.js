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
import enAi from './locales/en/ai.json';
import arAi from './locales/ar/ai.json';
import enCatalog from './locales/en/catalog.json';
import arCatalog from './locales/ar/catalog.json';
import enNotes from './locales/en/notes.json';
import arNotes from './locales/ar/notes.json';
import enEmissions from './locales/en/emissions.json';
import arEmissions from './locales/ar/emissions.json';
import enEvidence from './locales/en/evidence.json';
import arEvidence from './locales/ar/evidence.json';
import enImportExport from './locales/en/importexport.json';
import arImportExport from './locales/ar/importexport.json';
import enConnections from './locales/en/connections.json';
import arConnections from './locales/ar/connections.json';
import enDq from './locales/en/dq.json';
import arDq from './locales/ar/dq.json';
import enDataschema from './locales/en/dataschema.json';
import arDataschema from './locales/ar/dataschema.json';

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
    en: { common: enCommon, shell: enShell, auth: enAuth, errors: enErrors, ai: enAi, catalog: enCatalog, notes: enNotes, emissions: enEmissions, evidence: enEvidence, importexport: enImportExport, connections: enConnections, dq: enDq, dataschema: enDataschema },
    ar: { common: arCommon, shell: arShell, auth: arAuth, errors: arErrors, ai: arAi, catalog: arCatalog, notes: arNotes, emissions: arEmissions, evidence: arEvidence, importexport: arImportExport, connections: arConnections, dq: arDq, dataschema: arDataschema },
  },
  lng: getInitialLanguage(),
  fallbackLng: 'en',
  supportedLngs: SUPPORTED_LANGS,
  ns: ['common', 'shell', 'auth', 'errors', 'ai', 'catalog', 'notes', 'emissions', 'evidence', 'importexport', 'connections', 'dq', 'dataschema'],
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
