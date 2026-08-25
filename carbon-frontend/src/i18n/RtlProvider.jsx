// src/i18n/RtlProvider.jsx — ADR-0018 dual Emotion cache provider.
// Swaps the Emotion cache when the active language is RTL (Arabic), applying
// the stylis RTL plugin so MUI styles mirror automatically.
import React from 'react';
import createCache from '@emotion/cache';
import { CacheProvider } from '@emotion/react';
import rtlPluginModule from 'stylis-plugin-rtl';
import { useLanguage } from './useLanguage';

// stylis-plugin-rtl v2 ships a default export (a plugin function). Normalize
// defensively in case the installed build exposes `{ default }` interop instead.
const rtlPlugin =
  typeof rtlPluginModule === 'function' ? rtlPluginModule : rtlPluginModule?.default;

// MUI's conventional cache keys: `muil` (LTR) and `muirtl` (RTL).
const ltrCache = createCache({ key: 'muil' });
const rtlCache = createCache({ key: 'muirtl', stylisPlugins: [rtlPlugin] });

export default function RtlProvider({ children }) {
  const { isRtl } = useLanguage();
  return <CacheProvider value={isRtl ? rtlCache : ltrCache}>{children}</CacheProvider>;
}
