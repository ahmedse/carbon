import createCarbonTheme from './carbonTheme';

export function getTheme(mode) {
  return createCarbonTheme(mode === 'dark' ? 'dark' : 'light');
}

export default getTheme;