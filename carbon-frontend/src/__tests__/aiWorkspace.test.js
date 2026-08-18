// src/__tests__/aiWorkspace.test.js
// Phase 16 — findOpenConversation resume lookup filtering.
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../api/api', () => ({
  apiFetch: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

import { apiFetch } from '../api/api';
import { findOpenConversation } from '../api/aiWorkspace';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('findOpenConversation (Phase 16)', () => {
  it('returns the most recent open conversation of the requested type', async () => {
    apiFetch.mockResolvedValue([
      { id: 'a', conversation_type: 'chat', app_identifier: null, is_archived: false, updated_at: '2026-08-18T09:00:00Z' },
      { id: 'b', conversation_type: 'chat', app_identifier: null, is_archived: false, updated_at: '2026-08-18T10:00:00Z' },
    ]);

    const result = await findOpenConversation('tok', { conversation_type: 'chat' });

    expect(result.id).toBe('b');
  });

  it('skips archived conversations', async () => {
    apiFetch.mockResolvedValue([
      { id: 'a', conversation_type: 'chat', app_identifier: null, is_archived: true, updated_at: '2026-08-18T11:00:00Z' },
      { id: 'b', conversation_type: 'chat', app_identifier: null, is_archived: false, updated_at: '2026-08-18T09:00:00Z' },
    ]);

    const result = await findOpenConversation('tok', { conversation_type: 'chat' });

    expect(result.id).toBe('b');
  });

  it('filters by app_identifier when provided', async () => {
    apiFetch.mockResolvedValue([
      { id: 'a', conversation_type: 'chat', app_identifier: 'emissions', is_archived: false, updated_at: '2026-08-18T10:00:00Z' },
      { id: 'b', conversation_type: 'chat', app_identifier: null, is_archived: false, updated_at: '2026-08-18T11:00:00Z' },
    ]);

    const result = await findOpenConversation('tok', {
      conversation_type: 'chat',
      app_identifier: 'emissions',
    });

    expect(result.id).toBe('a');
  });

  it('returns null when no match exists', async () => {
    apiFetch.mockResolvedValue([]);

    const result = await findOpenConversation('tok', { conversation_type: 'chat' });

    expect(result).toBeNull();
  });
});
