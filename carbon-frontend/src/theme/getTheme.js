import createCarbonTheme from './carbonTheme';

export function getTheme(mode, direction = 'ltr', brandPalette = {}) {
  return createCarbonTheme(mode === 'dark' ? 'dark' : 'light', direction, brandPalette);
}

export default getTheme;