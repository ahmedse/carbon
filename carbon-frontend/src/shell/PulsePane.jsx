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

  // Watch the global flag set by index.html and poll for PulseWidget.
  // Transition LOADING → READY (widget found) or OFFLINE (script never arrived).
  useEffect(() => {
    if (window.PulseWidget) {
      setState(STATE.READY);
      return;
    }

    // Pulse script may still be downloading (async)
    const startedAt = Date.now();
    const poll = setInterval(() => {
      if (window.PulseWidget) {
        clearInterval(poll);
        setState(STATE.READY);
        return;
      }
      if (Date.now() - startedAt > LOAD_TIMEOUT_MS) {
        clearInterval(poll);
        setState(STATE.OFFLINE);
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(poll);
  }, []);

  // Mount PulseWidget into its DEDICATED container (no React children ever
  // live inside it, so external DOM mutation cannot orphan React nodes).
  // Leaving READY (retry / reload) unmounts the widget so the container is clean.
  useEffect(() => {
    if (state !== STATE.READY) {
      if (pulseRef.current?.unmount) {
        try { pulseRef.current.unmount(); } catch { /* best-effort */ }
        pulseRef.current = null;
      }
      return;
    }
    if (!mountRef.current) return;

    const timer = setTimeout(() => {
      try {
        pulseRef.current = window.PulseWidget.mount(mountRef.current, {
          instanceId: PULSE_INSTANCE,
          pulseHost: PULSE_HOST,
        });
      } catch (err) {
        console.error("Pulse mount failed:", err);
        setErrorMsg(err.message || "Failed to initialize copilot");
        setState(STATE.ERROR);
      }
    }, 150); // let DOM settle

    return () => clearTimeout(timer);
  }, [state]);

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

    // Re-attempt: if PulseWidget already on window, re-enter READY to re-mount
    if (window.PulseWidget) {
      setTimeout(() => setState(STATE.READY), 100);
      return;
    }

    // Otherwise wait for script
    const startedAt = Date.now();
    const poll = setInterval(() => {
      if (window.PulseWidget) {
        clearInterval(poll);
        setState(STATE.READY);
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
      {/* READY state: PulseWidget mounts into this DEDICATED container.
          It is always empty from React's perspective — no React children,
          so React never tries to remove DOM nodes the widget injected. */}
      {state === STATE.READY && (
        <Box ref={mountRef} sx={{ flex: 1, minHeight: 0, overflow: "hidden" }} />
      )}
    </Box>
  );
}
