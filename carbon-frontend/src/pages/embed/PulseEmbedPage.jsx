// The Moodle page iframes this route. It is the same AIWorkspace as Carbon,
// with the dial locked to Ask and the open course attached.
import React, { useEffect, useMemo, useState } from 'react';
import { Box, Typography } from '@mui/material';
import { API_BASE_URL } from '../../config';
import { useAuth } from '../../auth/AuthContext';
import { AIWorkspace } from '../../shell/AIWorkspace';
import { PulseHostContext } from '../../shell/pulseHostContext';

const sessionByTicket = new Map();

function redeemTicket(ticket) {
  if (!sessionByTicket.has(ticket)) {
    sessionByTicket.set(
      ticket,
      fetch(`${API_BASE_URL}ai/moodle/embed/session/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticket }),
      }).then(async (response) => {
        const data = await response.json().catch(() => null);
        if (!response.ok || !data?.access) {
          throw new Error(data?.error || 'session');
        }
        return data;
      }),
    );
  }
  return sessionByTicket.get(ticket);
}

export default function PulseEmbedPage() {
  const { user, loading, acceptHostSession } = useAuth();
  const [pageContext, setPageContext] = useState('');
  const [error, setError] = useState('');
  const [exchanging, setExchanging] = useState(false);

  const ticket = new URLSearchParams(window.location.search).get('ticket') || '';

  useEffect(() => {
    if (!ticket) return undefined;
    let cancelled = false;
    setExchanging(true);
    redeemTicket(ticket)
      .then((data) => {
        if (cancelled) return;
        setPageContext(data.page_context || '');
        // The ticket is the session Moodle just issued. A token already in
        // sessionStorage can be an expired access from an earlier pane.
        return acceptHostSession({
          access: data.access,
          refresh: data.refresh,
          username: data.username,
        });
      })
      .catch(() => {
        if (!cancelled) setError('Pulse could not open this session.');
      })
      .finally(() => {
        if (!cancelled) setExchanging(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ticket, acceptHostSession]);

  const hostValue = useMemo(
    () => ({
      dialLock: 'ask',
      appIdentifier: 'moodle',
      pageContext,
    }),
    [pageContext],
  );

  if (!user?.token || (ticket && exchanging && !pageContext)) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          {error || (loading || exchanging ? 'Opening Pulse…' : 'This Pulse pane is opened from Moodle.')}
        </Typography>
      </Box>
    );
  }

  return (
    <PulseHostContext.Provider value={hostValue}>
      <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
        <AIWorkspace
          onClose={() => {
            window.parent?.postMessage({ source: 'pulse-embed', type: 'close' }, '*');
          }}
        />
      </Box>
    </PulseHostContext.Provider>
  );
}
