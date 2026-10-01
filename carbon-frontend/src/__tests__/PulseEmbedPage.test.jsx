// Ticket redeem must not re-accept the host session on every Auth render.
// That loop kept empty Ask clickable and froze Moodle on Start a conversation.
import React, { useEffect, useRef } from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api/modules', () => ({
  fetchModules: vi.fn(() => Promise.resolve([])),
}));

vi.mock('../shell/AIWorkspace', () => ({
  AIWorkspace: function MockWorkspace() {
    return <div data-testid="pulse-workspace">workspace</div>;
  },
}));

import { AuthProvider, useAuth } from '../auth/AuthContext';
import PulseEmbedPage from '../pages/embed/PulseEmbedPage';
import { API_BASE_URL } from '../config';
import { fetchModules } from '../api/modules';

function embedUrl(ticket) {
  return `/embed/pulse?ticket=${ticket}`;
}

beforeEach(() => {
  vi.clearAllMocks();
  window.history.replaceState({}, '', embedUrl(`t-${Math.random().toString(16).slice(2)}`));
});

describe('acceptHostSession (Moodle embed)', () => {
  it('keeps the same function and user object when the ticket is accepted twice', async () => {
    window.history.replaceState({}, '', '/embed/pulse');
    const seen = [];
    function Probe() {
      const { user, acceptHostSession } = useAuth();
      const fns = useRef([]);
      fns.current.push(acceptHostSession);
      useEffect(() => {
        seen.push(acceptHostSession);
      }, [acceptHostSession]);
      useEffect(() => {
        acceptHostSession({ access: 'acc', refresh: 'ref', username: 'moodle' }).then(() =>
          acceptHostSession({ access: 'acc', refresh: 'ref', username: 'moodle' }),
        );
      }, [acceptHostSession]);
      return <span data-testid="who">{user?.username || ''}</span>;
    }

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('who')).toHaveTextContent('moodle');
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 40));
    });
    expect(seen.length).toBeLessThanOrEqual(2);
    expect(fetchModules).not.toHaveBeenCalled();
  });
});

describe('PulseEmbedPage ticket effect', () => {
  it('redeems the ticket once and leaves the workspace mounted', async () => {
    const ticket = `once-${Date.now()}`;
    window.history.replaceState({}, '', embedUrl(ticket));
    const fetchMock = vi.fn(async (url) => {
      if (String(url).includes('ai/moodle/embed/session/')) {
        return {
          ok: true,
          json: async () => ({
            access: 'embed-access',
            refresh: 'embed-refresh',
            username: 'moodle.user',
            page_context: 'Open course NMD1000: Introduction to Medical School id=4',
          }),
        };
      }
      return { ok: false, json: async () => ({}) };
    });
    vi.stubGlobal('fetch', fetchMock);

    render(
      <AuthProvider>
        <PulseEmbedPage />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('pulse-workspace')).toBeInTheDocument();
    });
    const sessionCalls = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes('ai/moodle/embed/session/'),
    );
    expect(sessionCalls).toHaveLength(1);
    expect(String(sessionCalls[0][0])).toContain(`${API_BASE_URL}ai/moodle/embed/session/`);
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 80));
    });
    expect(
      fetchMock.mock.calls.filter(([url]) => String(url).includes('ai/moodle/embed/session/')),
    ).toHaveLength(1);
    expect(screen.getByTestId('pulse-workspace')).toBeInTheDocument();
    expect(fetchModules).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});
