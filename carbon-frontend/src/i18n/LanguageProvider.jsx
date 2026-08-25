// src/i18n/LanguageProvider.jsx — ADR-0018 locale provider.
// Persists the language choice to localStorage (`carbon.lang`), drives
// i18next, and keeps <html lang/dir> in sync (index.html is hardcoded en/ltr).
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import i18n from './index';
import { LanguageContext } from './languageContext';
import { apiFetch } from '../api/api';

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

function applyDocumentLanguage(lang) {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
}

export default function LanguageProvider({ children }) {
  const [lang, setLang] = useState(getInitialLanguage);
  const [ready, setReady] = useState(() => i18n.isInitialized);

  // Reflect i18next initialization (bundled resources make this effectively
  // synchronous — the listener is a safety net for async init paths).
  useEffect(() => {
    if (i18n.isInitialized) {
      setReady(true);
      return undefined;
    }
    const markReady = () => setReady(true);
    i18n.on('initialized', markReady);
    return () => {
      i18n.off('initialized', markReady);
    };
  }, []);

  const setLanguage = useCallback((nextLang) => {
    const target = SUPPORTED_LANGS.includes(nextLang) ? nextLang : 'en';
    setLang(target);
    try {
      localStorage.setItem(STORAGE_KEY, target);
    } catch {
      // Ignore storage failures — the in-memory language still applies.
    }
    if (i18n.language !== target) {
      i18n.changeLanguage(target).catch(() => {
        // Non-blocking — React state already switched the UI.
      });
    }
    applyDocumentLanguage(target);

    // I18N-5 write-through: keep the server `User.language` preference in sync
    // so the reconciliation effect on the next full reload doesn't revert to a
    // stale server default ('en'). Best-effort — localStorage stays
    // authoritative for the current session if the PATCH fails.
    if (localStorage.getItem('access')) {
      apiFetch('accounts/me/preferences/', {
        method: 'PATCH',
        body: { language: target },
      }).catch(() => {
        // Silent — the next reconciliation keeps using localStorage until the
        // server is reachable again.
      });
    }
  }, []);

  // Sync <html lang/dir> on mount and whenever the language changes.
  useEffect(() => {
    applyDocumentLanguage(lang);
  }, [lang]);

  // Best-effort server reconciliation (the `language` field arrives in I18N-5;
  // until then this silently no-ops). Only runs when authenticated — the
  // server preference wins for logged-in users, localStorage wins pre-login.
  useEffect(() => {
    let cancelled = false;
    if (!localStorage.getItem('access')) return undefined;

    (async () => {
      try {
        const data = await apiFetch('accounts/me/context/', { method: 'GET' });
        if (cancelled) return;
        const serverLang = data?.user?.language || data?.language;
        if (serverLang && SUPPORTED_LANGS.includes(serverLang)) {
          setLanguage(serverLang);
        }
      } catch {
        // Silent — server field may not exist yet; localStorage stays
        // authoritative.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [setLanguage]);

  const value = useMemo(
    () => ({ lang, isRtl: lang === 'ar', setLanguage, ready }),
    [lang, setLanguage, ready]
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}
