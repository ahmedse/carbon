import createCarbonTheme from './carbonTheme';

export function getTheme(mode, direction = 'ltr') {
  return createCarbonTheme(mode === 'dark' ? 'dark' : 'light', direction);
}

export default getTheme;