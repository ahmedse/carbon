// src/__tests__/errorNormalizer.test.js
// I18N-5 — verifies normalizeError attaches a stable machine-readable
// `errorCode` plus a namespace-relative `messageKey` (errors namespace) for
// every error branch, so UI can resolve a translated message per locale.
import { describe, it, expect } from 'vitest';
import { normalizeError } from '../utils/errorNormalizer';

describe('normalizeError — errorCode / messageKey wiring (I18N-5)', () => {
  it('maps timeout/abort to errorCode=timeout + messageKey=timeout', () => {
    const out = normalizeError(new Error('Request timed out'));
    expect(out.errorCode).toBe('timeout');
    expect(out.messageKey).toBe('timeout');
    expect(out.canRetry).toBe(true);
  });

  it('maps fetch failure to errorCode=network_error + messageKey=network', () => {
    const out = normalizeError(new Error('Failed to fetch'));
    expect(out.errorCode).toBe('network_error');
    expect(out.messageKey).toBe('network');
  });

  it('maps 401 to errorCode=authentication_failed + messageKey=sessionExpired', () => {
    const out = normalizeError({ status: 401 });
    expect(out.errorCode).toBe('authentication_failed');
    expect(out.messageKey).toBe('sessionExpired');
  });

  it('maps 403 to errorCode=permission_denied + messageKey=permissionDenied', () => {
    const out = normalizeError({ status: 403 });
    expect(out.errorCode).toBe('permission_denied');
    expect(out.messageKey).toBe('permissionDenied');
  });

  it('maps 404 to errorCode=not_found + messageKey=notFound', () => {
    const out = normalizeError({ status: 404 });
    expect(out.errorCode).toBe('not_found');
    expect(out.messageKey).toBe('notFound');
  });

  it('maps 422/400 to errorCode=validation_error + messageKey=validation', () => {
    expect(normalizeError({ status: 422 }).errorCode).toBe('validation_error');
    expect(normalizeError({ status: 422 }).messageKey).toBe('validation');
    expect(normalizeError({ status: 400 }).errorCode).toBe('validation_error');
  });

  it('maps 5xx to errorCode=server_error + messageKey=server', () => {
    const out = normalizeError({ status: 500 });
    expect(out.errorCode).toBe('server_error');
    expect(out.messageKey).toBe('server');
  });

  it('maps anything else to errorCode=unknown_error + messageKey=generic', () => {
    const out = normalizeError({ status: 418 });
    expect(out.errorCode).toBe('unknown_error');
    expect(out.messageKey).toBe('generic');
  });
});
