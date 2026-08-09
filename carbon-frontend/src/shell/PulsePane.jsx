// src/shell/PulsePane.jsx
// Pulse AI Copilot pane — non-blocking loading with graceful degradation.
// Carbon never waits on Pulse. Three states: loading → ready | offline | error.

import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  Box,
  Typography,
  Button,
  CircularProgress,
  LinearProgress,
} from "@mui/material";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import CloudOffIcon from "@mui/icons-material/CloudOff";
import RefreshIcon from "@mui/icons-material/Refresh";

const PULSE_HOST = import.meta.env.VITE_PULSE_HOST || "http://localhost:9100";
const PULSE_INSTANCE =
  import.meta.env.VITE_PULSE_INSTANCE_ID || "carbon";
const MAX_RETRIES = 3;
const POLL_INTERVAL_MS = 300;
const LOAD_TIMEOUT_MS = 8000;

// ── states ────────────────────────────────────────────────────
const STATE = { LOADING: "loading", READY: "ready", OFFLINE: "offline", ERROR: "error" };

// ── sub-components ────────────────────────────────────────────

function LoadingState() {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        gap: 2,
        px: 3,
        textAlign: "center",
        color: "text.secondary",
      }}
    >
      <SmartToyIcon sx={{ fontSize: 40, color: "primary.light", opacity: 0.6 }} />
      <Box sx={{ width: "70%" }}>
        <LinearProgress sx={{ borderRadius: 1 }} />
      </Box>
      <Typography variant="body2">Loading AI Copilot…</Typography>
    </Box>
  );
}

function OfflineState({ onRetry }) {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        gap: 2,
        px: 3,
        textAlign: "center",
        color: "text.secondary",
      }}
    >
      <CloudOffIcon sx={{ fontSize: 48, color: "grey.400" }} />
      <Box>
        <Typography variant="subtitle2" color="text.primary" gutterBottom>
          AI Copilot Unavailable
        </Typography>
        <Typography variant="caption" color="text.disabled">
          The Pulse service is not running. Start it with{" "}
          <Box component="code" sx={{ fontFamily: "monospace", bgcolor: "action.hover", px: 0.5, borderRadius: 0.5 }}>
            ./manage.sh pulse
          </Box>
        </Typography>
      </Box>
      {onRetry && (
        <Button
          size="small"
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={onRetry}
        >
          Retry
        </Button>
      )}
    </Box>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        gap: 2,
        px: 3,
        textAlign: "center",
        color: "text.secondary",
      }}
    >
      <CloudOffIcon sx={{ fontSize: 48, color: "warning.main" }} />
      <Box>
        <Typography variant="subtitle2" color="text.primary" gutterBottom>
          Copilot Error
        </Typography>
        <Typography variant="caption" color="text.disabled">
          {message || "An unexpected error occurred while loading the copilot."}
        </Typography>
      </Box>
      {onRetry && (
        <Button
          size="small"
          variant="outlined"
          color="warning"
          startIcon={<RefreshIcon />}
          onClick={onRetry}
        >
          Retry
        </Button>
      )}
    </Box>
  );
}

// ── main component ────────────────────────────────────────────

export default function PulsePane() {
  const mountRef = useRef(null);
  const pulseRef = useRef(null);
  const retriesRef = useRef(0);
  const [state, setState] = useState(STATE.LOADING);
  const [errorMsg, setErrorMsg] = useState("");
  const [pulseLoaded, setPulseLoaded] = useState(false);

  // Watch the global flag set by index.html and poll for PulseWidget
  useEffect(() => {
    if (window.PulseWidget) {
      setPulseLoaded(true);
      return;
    }

    // Pulse script may still be downloading (async)
    const startedAt = Date.now();
    const poll = setInterval(() => {
      if (window.PulseWidget) {
        setPulseLoaded(true);
        clearInterval(poll);
        return;
      }
      if (Date.now() - startedAt > LOAD_TIMEOUT_MS) {
        clearInterval(poll);
        setState(STATE.OFFLINE);
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(poll);
  }, []);

  // Mount PulseWidget when copilot opens AND script is loaded
  useEffect(() => {
    if (!pulseLoaded || !mountRef.current) return;

    const timer = setTimeout(() => {
      try {
        pulseRef.current = window.PulseWidget.mount(mountRef.current, {
          instanceId: PULSE_INSTANCE,
          pulseHost: PULSE_HOST,
        });
        setState(STATE.READY);
      } catch (err) {
        console.error("Pulse mount failed:", err);
        setErrorMsg(err.message || "Failed to initialize copilot");
        setState(STATE.ERROR);
      }
    }, 150); // let DOM settle

    return () => {
      clearTimeout(timer);
    };
  }, [pulseLoaded]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pulseRef.current?.unmount) {
        try { pulseRef.current.unmount(); } catch { /* best-effort */ }
      }
    };
  }, []);

  const handleRetry = useCallback(() => {
    if (retriesRef.current >= MAX_RETRIES) {
      setState(STATE.OFFLINE);
      return;
    }
    retriesRef.current += 1;
    setState(STATE.LOADING);
    setErrorMsg("");

    // Re-attempt: if PulseWidget already on window, mount directly
    if (window.PulseWidget) {
      setPulseLoaded(false); // force re-mount
      setTimeout(() => setPulseLoaded(true), 100);
      return;
    }

    // Otherwise wait for script
    const startedAt = Date.now();
    const poll = setInterval(() => {
      if (window.PulseWidget) {
        setPulseLoaded(false);
        setTimeout(() => setPulseLoaded(true), 100);
        clearInterval(poll);
        return;
      }
      if (Date.now() - startedAt > LOAD_TIMEOUT_MS) {
        clearInterval(poll);
        setState(STATE.OFFLINE);
      }
    }, POLL_INTERVAL_MS);
  }, []);

  return (
    <Box
      ref={mountRef}
      sx={{
        height: "100%",
        width: "100%",
        display: "flex",
        flexDirection: "column",
        bgcolor: "background.paper",
      }}
    >
      {state === STATE.LOADING && <LoadingState />}
      {state === STATE.OFFLINE && <OfflineState onRetry={handleRetry} />}
      {state === STATE.ERROR && <ErrorState message={errorMsg} onRetry={handleRetry} />}
      {/* READY state: PulseWidget fills this container via mountRef */}
      {state === STATE.READY && <Box sx={{ flex: 1 }} />}
    </Box>
  );
}
