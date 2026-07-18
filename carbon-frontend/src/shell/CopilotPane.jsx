// File: src/shell/CopilotPane.jsx
// Pulse AI Copilot widget integration for Carbon platform
// Based on Gigacast implementation pattern

import { useEffect, useRef, useState } from 'react';
import { Box, CircularProgress, Alert, IconButton, Typography } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';

// Pulse widget script URL from environment
function getPulseScriptUrls() {
  const pulseHost = import.meta.env.VITE_PULSE_HOST || 'http://127.0.0.1:9100';
  return [`${pulseHost}/widget.js`];
}

// Ensure Pulse widget script is loaded
function ensurePulseScript({ forceReload = false } = {}) {
  return new Promise((resolve, reject) => {
    // If widget is already loaded and no force reload
    if (window.PulseWidget && !forceReload) {
      resolve(window.PulseWidget);
      return;
    }

    // Remove existing script if force reload
    if (forceReload) {
      const existingScript = document.querySelector('script[data-pulse-widget]');
      if (existingScript) {
        existingScript.remove();
        delete window.PulseWidget;
      }
    }

    const urls = getPulseScriptUrls();
    let attemptIndex = 0;

    const tryLoad = (index) => {
      if (index >= urls.length) {
        reject(new Error('Failed to load Pulse widget from all attempted URLs'));
        return;
      }

      const scriptUrl = urls[index];
      const script = document.createElement('script');
      script.src = scriptUrl;
      script.async = true;
      script.setAttribute('data-pulse-widget', 'true');

      script.onload = () => {
        if (window.PulseWidget) {
          resolve(window.PulseWidget);
        } else {
          setTimeout(() => {
            if (window.PulseWidget) {
              resolve(window.PulseWidget);
            } else {
              reject(new Error('Pulse widget script loaded but PulseWidget not found'));
            }
          }, 100);
        }
      };

      script.onerror = () => {
        script.remove();
        attemptIndex++;
        tryLoad(attemptIndex);
      };

      document.head.appendChild(script);
    };

    tryLoad(0);
  });
}

export default function CopilotPane({ onClose }) {
  const containerRef = useRef(null);
  const widgetInstanceRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    let cleanup = null;

    async function initWidget() {
      try {
        setLoading(true);
        setError(null);

        // Ensure script is loaded
        const PulseWidget = await ensurePulseScript();

        if (!mounted) return;

        // Get authentication token from backend
        const response = await fetch('/carbon-api/accounts/pulse-auth/', {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
          },
        });

        if (!response.ok) {
          throw new Error(`Pulse auth failed: ${response.statusText}`);
        }

        const { pulse_token, pulse_user } = await response.json();

        if (!mounted) return;

        // Mount widget
        const el = containerRef.current;
        if (!el) return;

        const instance = PulseWidget.mount(el, {
          instanceId: import.meta.env.VITE_PULSE_INSTANCE_ID || 'carbon',
          host: import.meta.env.VITE_PULSE_HOST || 'http://127.0.0.1:9100',
          auth: {
            token: pulse_token,
            user: pulse_user,
          },
          theme: {
            mode: 'auto', // Will follow Carbon theme context
          },
        });

        widgetInstanceRef.current = instance;

        // Cleanup function
        cleanup = () => {
          if (instance && typeof instance.unmount === 'function') {
            instance.unmount();
          }
        };

        setLoading(false);
      } catch (err) {
        console.error('Failed to initialize Pulse widget:', err);
        if (mounted) {
          setError(err.message || 'Failed to load Pulse widget');
          setLoading(false);
        }
      }
    }

    initWidget();

    return () => {
      mounted = false;
      if (cleanup) cleanup();
    };
  }, []);

  return (
    <Box
      role="complementary"
      aria-label="Pulse AI Copilot"
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: 'background.paper',
        borderLeft: '1px solid',
        borderColor: 'divider',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 1.5,
          py: 1,
          borderBottom: '1px solid',
          borderColor: 'divider',
          minHeight: 40,
        }}
      >
        <Typography variant="subtitle2" component="h2" sx={{ fontWeight: 600 }}>
          Pulse
        </Typography>
        <IconButton
          size="small"
          onClick={onClose}
          aria-label="Close Pulse copilot"
          sx={{
            width: 24,
            height: 24,
            '&:hover': { bgcolor: 'action.hover' },
            '&:focus-visible': {
              outline: '2px solid',
              outlineColor: 'primary.main',
              outlineOffset: '2px',
            },
          }}
        >
          <CloseIcon sx={{ fontSize: 16 }} aria-hidden="true" />
        </IconButton>
      </Box>

      {/* Widget Container */}
      <Box sx={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {loading && (
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              bgcolor: 'background.default',
            }}
          >
            <Box sx={{ textAlign: 'center' }}>
              <CircularProgress size={32} sx={{ mb: 1.5 }} />
              <Typography variant="body2" color="text.secondary">
                Loading Pulse...
              </Typography>
            </Box>
          </Box>
        )}

        {error && (
          <Box sx={{ p: 2 }}>
            <Alert severity="error" sx={{ fontSize: '0.875rem' }}>
              {error}
            </Alert>
          </Box>
        )}

        <Box
          ref={containerRef}
          sx={{
            width: '100%',
            height: '100%',
            '& > div': {
              width: '100%',
              height: '100%',
            },
          }}
        />
      </Box>
    </Box>
  );
}
