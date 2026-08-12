import { useContext } from 'react';
import { ThemeModeContext } from './themeModeContext';

export function useThemeMode() {
  const context = useContext(ThemeModeContext);
  if (!context) {
    return { mode: 'light', toggle: () => {} };
  }
  return context;
}