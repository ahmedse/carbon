import { describe, it, expect } from 'vitest';
import { useTheme } from '@mui/material/styles';
import { renderRtl } from '../test/renderRtl';
import { ChevronStart, ChevronEnd } from '../i18n/DirectionalIcons';

function ThemeDirProbe({ onDir }) {
  const theme = useTheme();
  onDir(theme.direction);
  return null;
}

describe('renderRtl + DirectionalIcons', () => {
  it('renderRtl supplies theme.direction=rtl by default', () => {
    let dir = null;
    renderRtl(<ThemeDirProbe onDir={(d) => { dir = d; }} />);
    expect(dir).toBe('rtl');
  });

  it('renderRtl can force LTR', () => {
    let dir = null;
    renderRtl(<ThemeDirProbe onDir={(d) => { dir = d; }} />, { direction: 'ltr' });
    expect(dir).toBe('ltr');
  });

  it('RTL: ChevronStart is mirrored toward the start edge', () => {
    const { container } = renderRtl(<ChevronStart />);
    const svg = container.querySelector('[data-chevron="start"]');
    expect(svg).toBeTruthy();
    expect(svg.getAttribute('data-mirrored')).toBe('1');
  });

  it('LTR: ChevronStart is not mirrored', () => {
    const { container } = renderRtl(<ChevronStart />, { direction: 'ltr' });
    const svg = container.querySelector('[data-chevron="start"]');
    expect(svg.getAttribute('data-mirrored')).toBe('0');
  });

  it('RTL: ChevronEnd is mirrored', () => {
    const { container } = renderRtl(<ChevronEnd />);
    expect(container.querySelector('[data-chevron="end"]').getAttribute('data-mirrored')).toBe('1');
  });
});
