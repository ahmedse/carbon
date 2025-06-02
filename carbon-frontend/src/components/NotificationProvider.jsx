// File: src/components/NotificationProvider.jsx

import React, { createContext, useContext, useState, useCallback } from "react";
import { Snackbar, Alert, IconButton } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";

const NotificationContext = createContext(undefined);

export function NotificationProvider({ children }) {
  const [notification, setNotification] = useState(null);

  // Robust: always allows stacking or fast replacement
  const notify = useCallback(
    ({ message, type = "info", duration = 4000 }) => {
      setNotification({ message, type, duration, key: Date.now() });
    },
    []
  );

  const handleClose = (_, reason) => {
    if (reason === "clickaway") return;
    setNotification(null);
  };

  // Debug: log when provider mounts
  React.useEffect(() => {
    // eslint-disable-next-line no-console
    console.debug("NotificationProvider mounted.");
  }, []);

  return (
    <NotificationContext.Provider value={{ notify }}>
      {children}
      <Snackbar
        key={notification?.key}
        open={!!notification}
        autoHideDuration={notification?.duration}
        onClose={handleClose}
        anchorOrigin={{ vertical: "top", horizontal: "center" }}
      >
        {notification && (
          <Alert
            onClose={handleClose}
            severity={notification.type}
            sx={{ width: "100%" }}
            action={
              <IconButton
                aria-label="close"
                color="inherit"
                size="small"
                onClick={handleClose}
              >
                <CloseIcon fontSize="inherit" />
              </IconButton>
            }
          >
            {notification.message}
          </Alert>
        )}
      </Snackbar>
    </NotificationContext.Provider>
  );
}

// Robust: never throw, just warn if out of context, and always provide a safe fallback
export function useNotification() {
  const ctx = useContext(NotificationContext);
  if (!ctx || typeof ctx.notify !== "function") {
    // eslint-disable-next-line no-console
    console.warn(
      "useNotification called outside of NotificationProvider! Fallback to alert."
    );
    return {
      notify: (msg) => {
        const message =
          typeof msg === "string"
            ? msg
            : msg?.message || "Notification (but NotificationProvider is missing)";
        window.alert(message);
      },
    };
  }
  return ctx;
}