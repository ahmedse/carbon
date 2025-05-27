// File: src/components/NotificationProvider.jsx

import React, { createContext, useContext, useState, useCallback } from "react";
import { Snackbar, Alert, IconButton } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";

const NotificationContext = createContext();

export function NotificationProvider({ children }) {
  const [notification, setNotification] = useState(null);

  const notify = useCallback(({ message, type = "info", duration = 4000 }) => {
    setNotification({ message, type, duration });
  }, []);

  const handleClose = (_, reason) => {
    if (reason === "clickaway") return;
    setNotification(null);
  };

  return (
    <NotificationContext.Provider value={{ notify }}>
      {children}
      <Snackbar
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

export function useNotification() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error("useNotification must be used within NotificationProvider");
  return ctx;
}