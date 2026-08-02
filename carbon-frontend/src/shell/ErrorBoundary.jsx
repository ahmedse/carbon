// File: src/shell/ErrorBoundary.jsx
// Error boundary for catching and displaying component errors gracefully.
// Enterprise-grade: correlation ID, copy details, "never a dead end."

import React from 'react';
import { Box, Typography, Button, Paper, Stack, Snackbar, Alert } from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import RefreshIcon from '@mui/icons-material/Refresh';
import HomeIcon from '@mui/icons-material/Home';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';

let _correlationCounter = 0;
function generateId() {
  _correlationCounter += 1;
  return `${Date.now().toString(36)}-${_correlationCounter}`;
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null, correlationId: null, copied: false };
  }

  static getDerivedStateFromError(_error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    const correlationId = generateId();
    console.error(`ErrorBoundary [${correlationId}]:`, error, errorInfo);
    this.setState({
      error,
      errorInfo,
      correlationId,
    });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null, correlationId: null, copied: false });
  };

  handleCopyDetails = () => {
    const { error, errorInfo, correlationId } = this.state;
    const details = [
      `Correlation ID: ${correlationId}`,
      `Time: ${new Date().toISOString()}`,
      `Error: ${error?.message || 'Unknown'}`,
      `Stack: ${error?.stack || 'N/A'}`,
      `Component Stack: ${errorInfo?.componentStack || 'N/A'}`,
    ].join('\n');
    navigator.clipboard.writeText(details).then(() => {
      this.setState({ copied: true });
      setTimeout(() => this.setState({ copied: false }), 2500);
    }).catch(() => {});
  };

  render() {
    const isDev = import.meta.env.DEV;

    if (this.state.hasError) {
      return (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '100vh',
            bgcolor: 'background.default',
            p: 3,
          }}
        >
          <Paper
            elevation={3}
            sx={{
              maxWidth: 600,
              p: 4,
              textAlign: 'center',
            }}
          >
            <ErrorOutlineIcon
              sx={{
                fontSize: 64,
                color: 'error.main',
                mb: 2,
              }}
            />
            <Typography variant="h5" sx={{ mb: 2, fontWeight: 600 }}>
              Something went wrong
            </Typography>

            {isDev ? (
              <>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  {this.state.error?.message || 'An unexpected error occurred'}
                </Typography>
                {this.state.errorInfo && (
                  <Box
                    sx={{
                      textAlign: 'left',
                      p: 2,
                      bgcolor: 'background.default',
                      borderRadius: 1,
                      mb: 2,
                      maxHeight: 200,
                      overflow: 'auto',
                    }}
                  >
                    <Typography
                      variant="caption"
                      component="pre"
                      sx={{
                        fontFamily: 'monospace',
                        fontSize: '0.6875rem',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                      }}
                    >
                      {this.state.errorInfo.componentStack}
                    </Typography>
                  </Box>
                )}
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 2 }}>
                  Correlation ID: {this.state.correlationId}
                </Typography>
              </>
            ) : (
              <>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  An unexpected error occurred. Our team has been notified.
                </Typography>
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 3 }}>
                  Reference: {this.state.correlationId}
                </Typography>
              </>
            )}

            <Stack direction="row" spacing={2} justifyContent="center" flexWrap="wrap">
              <Button
                variant="contained"
                startIcon={<RefreshIcon />}
                onClick={this.handleReset}
              >
                Try Again
              </Button>
              <Button
                variant="outlined"
                startIcon={<HomeIcon />}
                onClick={() => { window.location.href = '/'; }}
              >
                Go to Dashboard
              </Button>
              <Button
                variant="text"
                size="small"
                startIcon={<ContentCopyIcon />}
                onClick={this.handleCopyDetails}
              >
                Copy error details
              </Button>
            </Stack>
          </Paper>

          {/* Copy confirmation toast */}
          <Snackbar
            open={this.state.copied}
            autoHideDuration={2500}
            onClose={() => this.setState({ copied: false })}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
          >
            <Alert severity="success" variant="filled" sx={{ width: '100%' }}>
              Error details copied to clipboard
            </Alert>
          </Snackbar>
        </Box>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
