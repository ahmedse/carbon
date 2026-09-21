// RTL render harness for Vitest — theme.direction=rtl + LanguageContext isRtl.
// Emotion stylis RTL is optional; most layout assertions only need theme.direction.
import React from 'react';
import { render } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import createCarbonTheme from '../theme/carbonTheme';
import { LanguageContext } from '../i18n/languageContext';

const rtlTheme = createCarbonTheme('light', 'rtl');
const ltrTheme = createCarbonTheme('light', 'ltr');

const rtlLanguage = {
  lang: 'ar',
  isRtl: true,
  setLanguage: () => {},
  ready: true,
};

const ltrLanguage = {
  lang: 'en',
  isRtl: false,
  setLanguage: () => {},
  ready: true,
};

/**
 * @param {React.ReactElement} ui
 * @param {{ direction?: 'rtl'|'ltr' } & import('@testing-library/react').RenderOptions} [options]
 */
export function renderRtl(ui, { direction = 'rtl', ...options } = {}) {
  const theme = direction === 'rtl' ? rtlTheme : ltrTheme;
  const language = direction === 'rtl' ? rtlLanguage : ltrLanguage;
  return render(
    <LanguageContext.Provider value={language}>
      <ThemeProvider theme={theme}>{ui}</ThemeProvider>
    </LanguageContext.Provider>,
    options,
  );
}

export default renderRtl;
