// src/__tests__/logger.test.js
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { createLogger } from '../utils/logger';

describe('createLogger', () => {
  beforeEach(() => {
    vi.spyOn(console, 'debug').mockImplementation(() => {});
    vi.spyOn(console, 'info').mockImplementation(() => {});
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it('gates debug and info at the default warn level', () => {
    const logger = createLogger('gated');
    logger.debug('hidden debug');
    logger.info('hidden info');
    logger.warn('shown warn');
    expect(console.debug).not.toHaveBeenCalled();
    expect(console.info).not.toHaveBeenCalled();
    expect(console.warn).toHaveBeenCalled();
  });

  it('silent level gates every method', () => {
    vi.stubEnv('VITE_LOG_LEVEL', 'silent');
    const logger = createLogger('silent');
    logger.warn('w');
    logger.error('e');
    expect(console.warn).not.toHaveBeenCalled();
    expect(console.error).not.toHaveBeenCalled();
  });

  it('prefixes messages with the module tag', () => {
    vi.stubEnv('VITE_LOG_LEVEL', 'info');
    const logger = createLogger('mymodule');
    logger.info('hello');
    expect(console.info).toHaveBeenCalledTimes(1);
    expect(console.info.mock.calls[0][0]).toContain('[mymodule]');
    expect(console.info.mock.calls[0][0]).toContain('hello');
    expect(logger.getBuffer()[0].message).toContain('[mymodule]');
  });

  it('redacts secret keys and sk- / bearer tokens', () => {
    vi.stubEnv('VITE_LOG_LEVEL', 'warn');
    const logger = createLogger('secure');
    logger.warn(
      'auth',
      { token: 'secret-token-123', mode: 'test' },
      'key sk-abc123xyz here and Bearer eyJhbGciOiJIUzI1NiJ9.signature'
    );
    const message = logger.getBuffer()[0].message;
    expect(message).toContain('[REDACTED]');
    expect(message).not.toContain('secret-token-123');
    expect(message).not.toContain('sk-abc123xyz');
    expect(message).not.toContain('eyJhbGciOiJIUzI1NiJ9.signature');
  });

  it('caps the ring buffer at 100 entries', () => {
    vi.stubEnv('VITE_LOG_LEVEL', 'warn');
    const logger = createLogger('ring');
    for (let i = 0; i < 150; i += 1) logger.warn(`msg${i}`);
    const buffer = logger.getBuffer();
    expect(buffer).toHaveLength(100);
    expect(buffer[0].message).toContain('msg50');
    expect(buffer[99].message).toContain('msg149');
  });
});
