import React from 'react';
import { CssBaseline, ThemeProvider } from '@mui/material';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import { NotificationProvider } from '../components/NotificationProvider';
import { useThemeMode } from './useThemeMode';
import getTheme from './getTheme';

export default function ThemedApp() {
  const { mode } = useThemeMode();
  const theme = getTheme(mode);

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