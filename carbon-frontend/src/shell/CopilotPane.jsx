// File: src/shell/CopilotPane.jsx
// Embeds the Pulse AI copilot using the window.PulseWidget.mount() API.
// Copied from Gigacast implementation.

import { useEffect, useRef, useState } from 'react';
import { ensurePulseKey } from '../auth/pulseAuth';

const PULSE_HOST = import.meta.env.VITE_PULSE_HOST || 'http://127.0.0.1:9100';
const PULSE_SCRIPT_PATHS = ['/widget/pulse.js', '/dist/pulse.js'];

function getPulseScriptUrls() {
  const host = PULSE_HOST.replace(/\/$/, '');
  return PULSE_SCRIPT_PATHS.map((path) => `${host}${path}`);
}

function ensurePulseScript({ forceReload = false } = {}) {
  if (!PULSE_HOST) return Promise.resolve(false);
  if (window.PulseWidget?.mount) return Promise.resolve(true);

  const existing = document.querySelector(`script[data-pulse-host="${PULSE_HOST}"]`);
  if (forceReload && existing) {
    existing.remove();
    delete window.PulseWidget;
  }

  const activeScript = forceReload ? null : document.querySelector(`script[data-pulse-host="${PULSE_HOST}"]`);
  if (activeScript) {
    return new Promise((resolve) => {
      activeScript.addEventListener('load', () => resolve(true), { once: true });
      activeScript.addEventListener('error', () => resolve(false), { once: true });
      setTimeout(() => resolve(!!window.PulseWidget?.mount), 1000);
    });
  }

  return new Promise((resolve) => {
    const urls = getPulseScriptUrls();

    const tryLoad = (index) => {
      if (index >= urls.length) {
        resolve(false);
        return;
      }

      const script = document.createElement('script');
      script.src = urls[index];
      script.defer = true;
      script.dataset.instance = 'carbon';
      script.dataset.host = PULSE_HOST;
      script.dataset.pulseHost = PULSE_HOST;
      script.onload = () => resolve(true);
      script.onerror = () => {
        script.remove();
        tryLoad(index + 1);
      };
      document.body.appendChild(script);
    };

    tryLoad(0);
  });
}

export default function CopilotPane({ onClose }) {
  const mountRef = useRef(null);
  const [status, setStatus] = useState('loading');
  const [retryNonce, setRetryNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let mountedCleanup = null;
    let fallbackTimer = null;

    const el = mountRef.current;
    if (!el) return undefined;

    if (!PULSE_HOST) {
      setStatus('unavailable');
      return undefined;
    }

    setStatus('loading');
    fallbackTimer = window.setTimeout(() => {
      if (!cancelled) setStatus('unavailable');
    }, 4000);

    // Guarantee a per-user identity BEFORE the widget connects so it never opens
    // as "Anonymous". ensurePulseKey provisions the key from the live JWT.
    const liveToken = localStorage.getItem('token');
    Promise.resolve(ensurePulseKey(liveToken))
      .catch(() => null)
      .then(() => ensurePulseScript({ forceReload: retryNonce > 0 }))
      .then((ready) => {
        if (cancelled) return;
        window.clearTimeout(fallbackTimer);
        if (!ready || !window.PulseWidget?.mount) {
          setStatus('unavailable');
          return;
        }
        // Suppress the standalone floating FAB — the shell drawer is the only trigger
        if (!document.getElementById('_pulse_standalone_hide')) {
          const s = document.createElement('style');
          s.id = '_pulse_standalone_hide';
          s.textContent = '#pulse-widget-root{display:none!important}';
          document.head.appendChild(s);
        }
        // Pass the resolved per-user identity explicitly
        const instance = window.PulseWidget.mount(el, {
          onClose,
          pulseHost: PULSE_HOST,
          instanceId: 'carbon',
          pulseKey: localStorage.getItem('pulse_key') || undefined,
          carbonToken: localStorage.getItem('token') || undefined,
        });
        mountedCleanup = () => instance?.unmount?.();
        setStatus('ready');
      });

    return () => {
      cancelled = true;
      window.clearTimeout(fallbackTimer);
      mountedCleanup?.();
    };
  }, [onClose, retryNonce]);

  const handleRetry = () => {
    setRetryNonce((value) => value + 1);
  };

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div
        ref={mountRef}
        style={{ width: '100%', height: '100%', overflow: 'hidden', visibility: status === 'ready' ? 'visible' : 'hidden' }}
      />

      {status !== 'ready' && (
        <div style={{ position: 'absolute', inset: 0, padding: 16, color: '#71717a', fontSize: 12, lineHeight: 1.6, background: '#fff' }}>
          <div style={{ marginBottom: 10 }}>
            {status === 'loading' ? 'Connecting AI Copilot...' : 'AI Copilot is currently offline.'}
          </div>
          <button
            type="button"
            onClick={handleRetry}
            style={{
              border: '1px solid #d4d4d8',
              borderRadius: 4,
              padding: '4px 12px',
              background: '#fff',
              color: '#18181b',
              fontSize: 11,
              cursor: 'pointer',
            }}
          >
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
