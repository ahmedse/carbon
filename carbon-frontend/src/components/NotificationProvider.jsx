// File: src/components/NotificationProvider.jsx
//
// Unified feedback mechanism for the whole app.
//
// Two surfaces, one entry point:
//   - notify({ message, type })            -> lightweight snackbar (toast)
//   - showFeedback(feedbackEnvelope)        -> rich dialog with reasons + remediation
//   - notifyFromError(error, fallbackMsg)   -> smart router: picks the right surface
//                                              based on the structured `feedback`
//                                              envelope attached by the API layer.
//
// The backend returns a canonical envelope:
//   { code, severity, title, detail, reasons[], remediation[], context{} }
// (see backend/core/feedback.py). Any blocked/failed action anywhere in the
// platform flows through here so the user always sees WHAT happened and WHAT
// TO DO next.

import React, { createContext, useContext, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  Snackbar,
  Alert,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import BlockIcon from "@mui/icons-material/Block";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";

const NotificationContext = createContext(undefined);

const SEVERITY_META = {
  error: { color: "error.main", bg: "error.light", icon: ErrorOutlineIcon },
  warning: { color: "warning.main", bg: "warning.light", icon: WarningAmberIcon },
  info: { color: "info.main", bg: "info.light", icon: InfoOutlinedIcon },
  success: { color: "success.main", bg: "success.light", icon: CheckCircleOutlineIcon },
};

function getMeta(severity) {
  return SEVERITY_META[severity] || SEVERITY_META.info;
}

export function NotificationProvider({ children }) {
  const { t } = useTranslation('common');
  const { t: tErrors } = useTranslation('errors');
  const [notification, setNotification] = useState(null);
  const [feedback, setFeedbackState] = useState(null);

  // Lightweight toast
  const notify = useCallback(
    ({ message, type = "info", duration = 4000 }) => {
      setNotification({ message, type, duration, key: Date.now() });
    },
    []
  );

  // Rich, blocking feedback dialog (reasons + remediation)
  const showFeedback = useCallback((fb) => {
    if (!fb) return;
    setFeedbackState({
      severity: fb.severity || "error",
      title: fb.title || t('notice'),
      detail: fb.detail || "",
      reasons: Array.isArray(fb.reasons) ? fb.reasons : [],
      remediation: Array.isArray(fb.remediation) ? fb.remediation : [],
      context: fb.context || {},
      key: Date.now(),
    });
  }, [t]);

  // Smart router: choose dialog vs toast based on structured content.
  const notifyFromError = useCallback(
    (error, fallbackMessage = tErrors('somethingWentWrong')) => {
      // If the error was normalized by errorNormalizer, check for auth type
      const normalized = error?.normalized;
      if (normalized?.type === "auth" && normalized?.status === 401) {
        // Session expired — trigger re-login instead of a toast
        setNotification({
          message: tErrors('sessionExpiredRedirecting'),
          type: "warning",
          duration: 2500,
          key: Date.now(),
        });
        localStorage.clear();
        setTimeout(() => {
          window.location.href = `${
            import.meta.env.VITE_BASE || "/"
          }login?expired=1`;
        }, 1500);
        return;
      }

      const fb = error?.feedback;
      const hasRichContent =
        fb && ((fb.reasons && fb.reasons.length) || (fb.remediation && fb.remediation.length));

      if (hasRichContent) {
        showFeedback(fb);
        return;
      }

      const message = fb?.detail || error?.message || fallbackMessage;
      const type = fb?.severity || "error";
      setNotification({ message, type, duration: 5000, key: Date.now() });
    },
    [showFeedback, tErrors]
  );

  const handleCloseSnackbar = (_, reason) => {
    if (reason === "clickaway") return;
    setNotification(null);
  };

  const handleCloseFeedback = () => setFeedbackState(null);

  const meta = feedback ? getMeta(feedback.severity) : getMeta("info");
  const HeaderIcon = feedback?.severity === "error" ? BlockIcon : meta.icon;

  return (
    <NotificationContext.Provider value={{ notify, showFeedback, notifyFromError }}>
      {children}

      {/* Lightweight toast */}
      <Snackbar
        key={notification?.key}
        open={!!notification}
        autoHideDuration={notification?.duration}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: "top", horizontal: "center" }}
      >
        {notification && (
          <Alert
            onClose={handleCloseSnackbar}
            severity={notification.type}
            sx={{ width: "100%" }}
            action={
              <IconButton
                aria-label={t('close')}
                color="inherit"
                size="small"
                onClick={handleCloseSnackbar}
              >
                <CloseIcon fontSize="inherit" />
              </IconButton>
            }
          >
            {notification.message}
          </Alert>
        )}
      </Snackbar>

      {/* Rich feedback dialog */}
      <Dialog
        open={!!feedback}
        onClose={handleCloseFeedback}
        maxWidth="sm"
        fullWidth
        PaperProps={{ sx: { borderRadius: 2 } }}
      >
        {feedback && (
          <>
            <DialogTitle sx={{ pb: 1 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                <Box
                  sx={{
                    width: 40,
                    height: 40,
                    borderRadius: "50%",
                    bgcolor: meta.bg,
                    color: meta.color,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <HeaderIcon />
                </Box>
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="h6" fontWeight={700} sx={{ lineHeight: 1.2 }}>
                    {feedback.title}
                  </Typography>
                  {feedback.detail && feedback.detail !== feedback.title && (
                    <Typography variant="body2" color="text.secondary">
                      {feedback.detail}
                    </Typography>
                  )}
                </Box>
              </Box>
            </DialogTitle>

            <DialogContent dividers>
              {feedback.reasons.length > 0 && (
                <Box sx={{ mb: feedback.remediation.length ? 2 : 0 }}>
                  <Typography
                    variant="overline"
                    color="text.secondary"
                    fontWeight={700}
                  >
                    {t('why')}
                  </Typography>
                  <List dense disablePadding>
                    {feedback.reasons.map((reason, i) => (
                      <ListItem key={i} disableGutters sx={{ alignItems: "flex-start" }}>
                        <ListItemIcon sx={{ minWidth: 30, mt: 0.5, color: meta.color }}>
                          <ErrorOutlineIcon fontSize="small" />
                        </ListItemIcon>
                        <ListItemText primary={reason} />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              )}

              {feedback.reasons.length > 0 && feedback.remediation.length > 0 && (
                <Divider sx={{ my: 1 }} />
              )}

              {feedback.remediation.length > 0 && (
                <Box>
                  <Typography
                    variant="overline"
                    color="text.secondary"
                    fontWeight={700}
                  >
                    {t('whatYouCanDo')}
                  </Typography>
                  <List dense disablePadding>
                    {feedback.remediation.map((step, i) => (
                      <ListItem key={i} disableGutters sx={{ alignItems: "flex-start" }}>
                        <ListItemIcon sx={{ minWidth: 30, mt: 0.5, color: "success.main" }}>
                          <ArrowForwardIcon fontSize="small" />
                        </ListItemIcon>
                        <ListItemText primary={step} />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              )}
            </DialogContent>

            <DialogActions>
              <Button onClick={handleCloseFeedback} variant="contained">
                {t('gotIt')}
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>
    </NotificationContext.Provider>
  );
}

// Robust: never throw, just warn if out of context, and always provide a safe fallback
// eslint-disable-next-line react-refresh/only-export-components
export function useNotification() {
  const ctx = useContext(NotificationContext);
  if (!ctx || typeof ctx.notify !== "function") {
     
    console.warn(
      "useNotification called outside of NotificationProvider! Fallback to alert."
    );
    const fallbackNotify = (msg) => {
      const message =
        typeof msg === "string"
          ? msg
          : msg?.message || "Notification (but NotificationProvider is missing)";
      window.alert(message);
    };
    return {
      notify: fallbackNotify,
      showFeedback: (fb) => window.alert(fb?.detail || fb?.title || "Notice"),
      notifyFromError: (err, fallback) =>
        window.alert(err?.feedback?.detail || err?.message || fallback || "Error"),
    };
  }
  return ctx;
}