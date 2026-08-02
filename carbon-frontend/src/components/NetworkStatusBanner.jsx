// src/components/NetworkStatusBanner.jsx
// Offline/online detection banner + context for API call awareness.
// Listens to window online/offline events and persists state via a simple context.

import React, { createContext, useContext, useState, useEffect } from "react";
import { Box, Typography, Snackbar, Alert } from "@mui/material";
import WifiOffIcon from "@mui/icons-material/WifiOff";

const NetworkStatusContext = createContext({ online: true });

/** Hook for components/API calls to check online state before firing. */
export function useNetworkStatus() {
  return useContext(NetworkStatusContext);
}

/**
 * Provider that listens to online/offline events and exposes current state.
 * Wrap near the root (in App.jsx) so the entire tree can check before API calls.
 */
export function NetworkStatusProvider({ children }) {
  const [online, setOnline] = useState(navigator.onLine);
  const [showBackBanner, setShowBackBanner] = useState(false);

  useEffect(() => {
    const go = () => {
      setOnline(true);
      setShowBackBanner(true);
      // Auto-hide the "back online" toast
      setTimeout(() => setShowBackBanner(false), 3000);
    };
    const goff = () => setOnline(false);
    window.addEventListener("online", go);
    window.addEventListener("offline", goff);
    return () => {
      window.removeEventListener("online", go);
      window.removeEventListener("offline", goff);
    };
  }, []);

  return (
    <NetworkStatusContext.Provider value={{ online }}>
      {children}

      {/* Offline banner — slim, warning color, fixed at top */}
      {!online && (
        <Box
          sx={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            zIndex: (theme) => theme.zIndex.tooltip + 1,
            bgcolor: "warning.main",
            color: "warning.contrastText",
            py: 0.5,
            px: 2,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 1,
          }}
        >
          <WifiOffIcon fontSize="small" />
          <Typography variant="body2" fontWeight={500}>
            You are offline. Changes will be saved locally.
          </Typography>
        </Box>
      )}

      {/* "Back online" toast */}
      <Snackbar
        open={showBackBanner}
        autoHideDuration={3000}
        onClose={() => setShowBackBanner(false)}
        anchorOrigin={{ vertical: "top", horizontal: "center" }}
      >
        <Alert severity="success" variant="filled" sx={{ width: "100%" }}>
          Back online
        </Alert>
      </Snackbar>
    </NetworkStatusContext.Provider>
  );
}
