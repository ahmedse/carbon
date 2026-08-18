// src/__tests__/aiWorkspace.operations.test.js
// Phase 19-B — deleteMessage / editMessage / retryMessageStream API surface.
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../config', () => ({
  API_BASE_URL: 'http://test.local/carbon-api/',
}));
vi.mock('../jwt', () => ({
  isJwtExpired: () => false,
}));
vi.mock('../api/api', () => ({
  apiFetch: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

import { apiFetch } from '../api/api';
import { deleteMessage, editMessage, retryMessageStream } from '../api/aiWorkspace';

// Build a fake fetch stream that yields one encoded chunk per read.
function makeStreamReader(chunks) {
  const encoder = new TextEncoder();
  const encoded = chunks.map((c) => encoder.encode(c));
  let i = 0;
  return {
    read: vi.fn(async () => {
      if (i < encoded.length) {
        return { done: false, value: encoded[i++] };
      }
      return { done: true, value: undefined };
    }),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  global.fetch = vi.fn();
});

describe('deleteMessage (Phase 19-B)', () => {
  it('issues a DELETE for the message id', async () => {
    apiFetch.mockResolvedValue({ deleted: 'm1' });

    await deleteMessage('tok', 'conv-1', 'm1');

    expect(apiFetch).toHaveBeenCalledWith(
      'ai/workspace/conversations/conv-1/messages/m1/',
      { token: 'tok', method: 'DELETE' },
    );
  });
});

describe('editMessage (Phase 19-B)', () => {
  it('PATCHes content with regenerate flag', async () => {
    apiFetch.mockResolvedValue({ id: 'conv-1' });

    await editMessage('tok', 'conv-1', 'm1', 'revised');

    expect(apiFetch).toHaveBeenCalledWith(
      'ai/workspace/conversations/conv-1/messages/m1/',
      { token: 'tok', method: 'PATCH', body: { content: 'revised', regenerate: true } },
    );
  });
});

describe('retryMessageStream (Phase 19-B)', () => {
  it('POSTs to the retry endpoint and parses SSE frames', async () => {
    const reader = makeStreamReader([
      'data: {"type":"chunk","content":"Hi "}\n\n',
      'data: {"type":"chunk","content":"there"}\n\n',
      'data: {"type":"done","conversation":{"id":"conv-1"}}\n\n',
    ]);
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      body: { getReader: () => reader },
    });

    const onChunk = vi.fn();
    const onDone = vi.fn();
    await retryMessageStream('tok', 'conv-1', 'm1', {
      content: 'revised',
      model: 'gpt-4o',
      onChunk,
      onDone,
    });

    expect(global.fetch).toHaveBeenCalledWith(
      'http://test.local/carbon-api/ai/workspace/conversations/conv-1/messages/m1/retry/',
      expect.objectContaining({ method: 'POST' }),
    );
    const [, options] = global.fetch.mock.calls[0];
    expect(JSON.parse(options.body)).toEqual({ content: 'revised', model: 'gpt-4o' });

    expect(onChunk).toHaveBeenCalledTimes(2);
    expect(onChunk.mock.calls.map((c) => c[0])).toEqual(['Hi ', 'there']);
    expect(onDone).toHaveBeenCalledWith({ id: 'conv-1' });
  });

  it('omits content and model from the body when not supplied', async () => {
    const reader = makeStreamReader(['data: {"type":"done","conversation":{}}\n\n']);
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      body: { getReader: () => reader },
    });

    await retryMessageStream('tok', 'conv-1', 'm1', { onDone: vi.fn() });

    const [, options] = global.fetch.mock.calls[0];
    expect(JSON.parse(options.body)).toEqual({});
  });
});
