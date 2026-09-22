// CertExpiryChip — urgency tiers for certification expiry.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import CertExpiryChip from '../apps/people/components/CertExpiryChip';

describe('CertExpiryChip', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-09-22T12:00:00Z'));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows Expired for past dates', () => {
    render(<CertExpiryChip expiryDate="2026-09-01" />);
    expect(screen.getByText(/Expired/i)).toBeInTheDocument();
  });

  it('shows days left for critical window', () => {
    render(<CertExpiryChip expiryDate="2026-09-25" />);
    expect(screen.getByText(/\d+d left/i)).toBeInTheDocument();
  });

  it('shows Valid when no expiry or far out', () => {
    render(<CertExpiryChip expiryDate={null} />);
    expect(screen.getByText(/Valid/i)).toBeInTheDocument();
  });
});
