import { useContext } from 'react';
import { LanguageContext } from './languageContext';

// Hook for consuming the language context: { lang, isRtl, setLanguage, ready }.
// Safe default mirrors useThemeMode: components rendered outside the provider
// (e.g., isolated tests) fall back to English/LTR instead of crashing on null.
export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    return { lang: 'en', isRtl: false, setLanguage: () => {}, ready: true };
  }
  return context;
}
