import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import InboundStatRow from '../components/inbound/InboundStatRow';

describe('InboundStatRow — typography comes from variants (Defect 10)', () => {
  it('renders label and value with variant-driven type, not inline font sizes', () => {
    render(
      <InboundStatRow items={[
        { key: 'insert', label: 'Insert', value: 12 },
        { key: 'reject', label: 'Reject', value: 3, tone: 'error' },
      ]} />,
    );

    const label = screen.getByText('Insert');
    const value = screen.getByText('12');
    // MUI emits one typography class per variant; no raw `font-size` style.
    expect(label.className).toContain('MuiTypography-caption');
    expect(value.className).toContain('MuiTypography-subtitle1');
    expect(label.getAttribute('style')).toBeNull();
    expect(value.getAttribute('style')).toBeNull();
  });
});
