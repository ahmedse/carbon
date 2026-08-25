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

// Inner component consumes the language context (direction) so the theme can
// be built direction-aware; provider order stays: LanguageProvider (outer) →
// RtlProvider → ThemeProvider → existing providers (ADR-0018).
function ThemedAppContent() {
  const { mode } = useThemeMode();
  const { isRtl } = useLanguage();
  const theme = getTheme(mode, isRtl ? 'rtl' : 'ltr');

  React.useEffect(() => {
    console.debug('ThemedApp mounted. Theme mode:', mode);
  }, [mode]);

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