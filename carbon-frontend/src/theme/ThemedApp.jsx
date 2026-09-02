import React from 'react';
import { CssBaseline, ThemeProvider } from '@mui/material';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import { NotificationProvider } from '../components/NotificationProvider';
import { useThemeMode } from './useThemeMode';
import getTheme from './getTheme';
import LanguageProvider from '../i18n/LanguageProvider';
import RtlProvider from '../i18n/RtlProvider';
import { useLanguage } from '../i18n/useLanguage';
import { BRAND_PALETTE, INSTANCE_FAVICON } from '../config/branding';

// Inner component consumes the language context (direction) so the theme can
// be built direction-aware; provider order stays: LanguageProvider (outer) →
// RtlProvider → ThemeProvider → existing providers (ADR-0018).
function ThemedAppContent() {
  const { mode } = useThemeMode();
  const { isRtl } = useLanguage();
  const theme = getTheme(mode, isRtl ? 'rtl' : 'ltr', BRAND_PALETTE);

  React.useEffect(() => {
    console.debug('ThemedApp mounted. Theme mode:', mode);
  }, [mode]);

  // Wire the per-brand favicon at runtime (single-switch branding; the static
  // /favicon.svg in index.html is the no-env fallback).
  React.useEffect(() => {
    const link = document.querySelector("link[rel='icon'][type='image/svg+xml']");
    if (link && INSTANCE_FAVICON) link.href = INSTANCE_FAVICON;
  }, []);

  return (
    <ThemeProvider theme={theme}>
      <NotificationProvider>
        <CssBaseline />
        <AuthProvider>
          <App />
        </AuthProvider>
      </NotificationProvider>
    </ThemeProvider>
  );
}

export default function ThemedApp() {
  return (
    <LanguageProvider>
      <RtlProvider>
        <ThemedAppContent />
      </RtlProvider>
    </LanguageProvider>
  );
}