// src/components/ChunkLoadError.jsx
// Recovery surface for dynamic import / chunk-load failures.
// Renders when a lazy-loaded route module fails to download (e.g. network drop during code-split).

import React, { useState, useEffect } from "react";
import { Box, Typography, Button, Paper, Stack, Chip } from "@mui/material";
import CloudOffIcon from "@mui/icons-material/CloudOff";
import WifiIcon from "@mui/icons-material/Wifi";
import RefreshIcon from "@mui/icons-material/Refresh";
import HomeIcon from "@mui/icons-material/Home";

/**
 * Displays a friendly recovery UI when a code chunk fails to load.
 * "Human sentence + retry, log detail for debugger — not the user."
 */
export default function ChunkLoadError({ error, onRetry }) {
  const [online, setOnline] = useState(navigator.onLine);

  useEffect(() => {
    const go = () => setOnline(true);
    const goff = () => setOnline(false);
    window.addEventListener("online", go);
    window.addEventListener("offline", goff);
    return () => {
      window.removeEventListener("online", go);
      window.removeEventListener("offline", goff);
    };
  }, []);

  const handleRetry = () => {
    if (onRetry) {
      onRetry();
    } else {
      window.location.reload();
    }
  };

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
        bgcolor: "background.default",
        p: 3,
      }}
    >
      <Paper
        elevation={2}
        sx={{
          maxWidth: 520,
          p: 4,
          textAlign: "center",
        }}
      >
        <CloudOffIcon
          sx={{ fontSize: 56, color: "warning.main", mb: 2 }}
        />
        <Typography variant="h6" gutterBottom fontWeight={600}>
          Failed to load this page
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          A required part of the application couldn't be loaded. This usually
          happens when the network connection is unstable.
        </Typography>

        {/* Network status indicator */}
        <Stack direction="row" spacing={1} justifyContent="center" sx={{ mb: 3 }}>
          <Chip
            icon={online ? <WifiIcon /> : <CloudOffIcon />}
            label={online ? "Online" : "Offline"}
            size="small"
            color={online ? "success" : "warning"}
            variant="outlined"
          />
        </Stack>

        <Stack direction="row" spacing={2} justifyContent="center">
          <Button
            variant="contained"
            startIcon={<RefreshIcon />}
            onClick={handleRetry}
          >
            Retry
          </Button>
          <Button
            variant="outlined"
            startIcon={<HomeIcon />}
            component="a"
            href="/"
          >
            Go to Dashboard
          </Button>
        </Stack>

        {/* Dev mode: show error detail */}
        {import.meta.env.DEV && error && (
          <Box
            sx={{
              mt: 3,
              p: 1.5,
              bgcolor: "grey.100",
              borderRadius: 1,
              textAlign: "left",
              maxHeight: 160,
              overflow: "auto",
            }}
          >
            <Typography
              variant="caption"
              component="pre"
              sx={{
                fontFamily: "monospace",
                fontSize: "0.6875rem",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                m: 0,
              }}
            >
              {error.message || String(error)}
            </Typography>
          </Box>
        )}
      </Paper>
    </Box>
  );
}
