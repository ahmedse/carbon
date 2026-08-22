// src/__tests__/findOpenConversation.test.js
// Phase 16 — unit tests for the resume helper: returns the most recent open
// (non-archived) conversation of a type, optionally scoped to an app, and
// null when only archived/other threads exist.
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../api/api', () => ({
  apiFetch: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

import { findOpenConversation } from '../api/aiWorkspace';
import { apiFetch } from '../api/api';

beforeEach(() => {
  vi.clearAllMocks();
});

const threads = [
  { id: 'c1', conversation_type: 'chat', updated_at: '2024-01-01T00:00:00Z', is_archived: false },
  { id: 'c2', conversation_type: 'chat', updated_at: '2024-06-01T00:00:00Z', is_archived: false },
  { id: 'c3', conversation_type: 'chat', updated_at: '2024-08-01T00:00:00Z', is_archived: true },
  { id: 'c4', conversation_type: 'chat', updated_at: '2024-05-01T00:00:00Z', is_archived: false, app_identifier: 'emissions' },
];

describe('findOpenConversation (Phase 16)', () => {
  it('returns the most recent open conversation and skips archived ones', async () => {
    apiFetch.mockResolvedValue(threads);

    const found = await findOpenConversation('test-token', { conversation_type: 'chat' });

    // c3 has the newest updated_at but is archived → skipped; c2 wins.
    expect(found.id).toBe('c2');
  });

  it('scopes results to app_identifier when provided', async () => {
    apiFetch.mockResolvedValue(threads);

    const found = await findOpenConversation('test-token', {
      conversation_type: 'chat',
      app_identifier: 'emissions',
    });

    expect(found.id).toBe('c4');
  });

  it('scopes results to an entity (table_id) when provided', async () => {
    apiFetch.mockResolvedValue([
      { id: 'w', conversation_type: 'chat', updated_at: '2024-07-01T00:00:00Z', is_archived: false, task_payload_json: {} },
      { id: 't', conversation_type: 'chat', updated_at: '2024-06-01T00:00:00Z', is_archived: false, task_payload_json: { table_id: 35, table_name: 'Electricity' } },
    ]);

    const found = await findOpenConversation('test-token', {
      conversation_type: 'chat',
      entityScope: { table_id: 35 },
    });

    // The newest thread (id 'w') has no table payload → skipped; the one
    // bound to table 35 wins.
    expect(found.id).toBe('t');
  });

  it('returns null when no open thread is bound to the entity', async () => {
    apiFetch.mockResolvedValue([
      { id: 'w', conversation_type: 'chat', updated_at: '2024-07-01T00:00:00Z', is_archived: false, task_payload_json: {} },
    ]);

    const found = await findOpenConversation('test-token', {
      conversation_type: 'chat',
      entityScope: { table_id: 35 },
    });

    expect(found).toBeNull();
  });

  it('returns null when only archived conversations exist', async () => {
    apiFetch.mockResolvedValue([
      { id: 'a1', conversation_type: 'chat', updated_at: '2024-08-01T00:00:00Z', is_archived: true },
    ]);

    const found = await findOpenConversation('test-token', { conversation_type: 'chat' });

    expect(found).toBeNull();
  });

  it('returns null when no conversations exist', async () => {
    apiFetch.mockResolvedValue([]);

    const found = await findOpenConversation('test-token', { conversation_type: 'chat' });

    expect(found).toBeNull();
  });

  it('falls back to last_message_at/created_at for ordering', async () => {
    apiFetch.mockResolvedValue([
      { id: 'a', conversation_type: 'chat', last_message_at: '2024-02-01T00:00:00Z', is_archived: false },
      { id: 'b', conversation_type: 'chat', created_at: '2024-03-01T00:00:00Z', is_archived: false },
    ]);

    const found = await findOpenConversation('test-token', { conversation_type: 'chat' });

    // b has a newer created_at and no last_message_at/updated_at.
    expect(found.id).toBe('b');
  });
});
