import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';

import renderRtl from '../test/renderRtl';
import getTheme from '../theme/getTheme';
import InboundStatRow from '../components/inbound/InboundStatRow';

describe('InboundStatRow — typography comes from variants (Defect 10)', () => {
  it('renders label and value with variant-driven type, not inline font sizes', () => {
    renderRtl(
      <InboundStatRow items={[
        { key: 'insert', label: 'Insert', value: 12 },
        { key: 'reject', label: 'Reject', value: 3, tone: 'error' },
      ]} />,
    );

    const label = screen.getByText('Insert');
    const value = screen.getByText('12');
    // MUI emits one typography class per variant; no raw `font-size` style.
    expect(label.className).toContain('MuiTypography-caption');
    // Numbers use the theme's `mono` token variant — never an inline fontFamily.
    expect(value.className).toContain('MuiTypography-mono');
    expect(label.getAttribute('style')).toBeNull();
    expect(value.getAttribute('style')).toBeNull();

    // The `mono` token is a real theme variant, and it actually resolves to the
    // monospace stack (design-system RULE 3/8) rather than being a bare class.
    const theme = getTheme('light', 'ltr');
    expect(theme.typography.mono.fontFamily).toContain('Roboto Mono');
    expect(window.getComputedStyle(value).fontFamily).toContain('Roboto Mono');
  });

  it('tones the reject value with the error token, not a hardcoded color', () => {
    renderRtl(
      <InboundStatRow items={[{ key: 'reject', label: 'Reject', value: 3, tone: 'error' }]} />,
    );

    const value = screen.getByText('3');
    // Semantic palette token resolved by the theme — rgb(239, 68, 68) = error.main.
    expect(window.getComputedStyle(value).color).toBe('rgb(239, 68, 68)');
  });

  it('matches the compact stat-row markup snapshot', () => {
    const { container } = renderRtl(
      <InboundStatRow items={[
        { key: 'insert', label: 'Insert', value: 12 },
        { key: 'update', label: 'Update', value: 0 },
        { key: 'skip', label: 'Skip', value: 0 },
        { key: 'reject', label: 'Reject', value: 3, tone: 'error' },
      ]} />,
    );

    expect(container.firstChild).toMatchSnapshot();
  });
});
