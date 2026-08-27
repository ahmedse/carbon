// src/components/panel/PanelTable.jsx
// Reusable MUI Table wrapper for right-panel tabs.
// Gold standard: DQRulesTab in catalog. All 10+ panel tabs must use this.
//
// Props:
//   title        — section header text
//   subtitle     — optional secondary text (e.g., "3 rules, 2 passing")
//   actions      — optional JSX for header actions (e.g., <Button>Add Rule</Button>)
//   columns      — Array<{ key, header, width?, align?, render }>
//   rows         — Array of data objects
//   emptyText    — text when rows.length === 0
//   loading      — show spinner
//   error        — show alert
//   pagination   — { page, pageSize, total, onChange } or null
//   dense        — extra compact mode (default true)

import React from 'react';
import {
  Box,
  Typography,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  CircularProgress,
  Alert,
  IconButton,
} from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';

export default function PanelTable({
  title,
  subtitle,
  actions,
  columns = [],
  rows = [],
  emptyText = 'No data available.',
  loading = false,
  error = null,
  pagination = null,
  dense = true,
}) {
  // ── Loading state ──
  if (loading) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <CircularProgress size={20} />
      </Box>
    );
  }

  // ── Error state ──
  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="error" sx={{ fontSize: '0.75rem' }}>
          {typeof error === 'string' ? error : 'Failed to load data.'}
        </Alert>
      </Box>
    );
  }

  // ── Header ──
  const hasHeader = title || subtitle || actions;

  return (
    <Box>
      {hasHeader && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            mb: 1.5,
            gap: 1,
          }}
        >
          <Box>
            {title && (
              <Typography
                sx={{
                  fontSize: '0.68rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  color: 'text.secondary',
                }}
              >
                {title}
              </Typography>
            )}
            {subtitle && (
              <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mt: 0.25 }}>
                {subtitle}
              </Typography>
            )}
          </Box>
          {actions && <Box sx={{ flexShrink: 0 }}>{actions}</Box>}
        </Box>
      )}

      {/* ── Table ── */}
      {rows.length === 0 ? (
        <Alert severity="info" sx={{ fontSize: '0.75rem', borderRadius: 0.5 }}>
          {emptyText}
        </Alert>
      ) : (
        <Table size={dense ? 'small' : 'medium'} sx={{ tableLayout: 'fixed' }}>
          <TableHead>
            <TableRow sx={{ bgcolor: 'grey.100' }}>
              {columns.map((col, ci) => (
                <TableCell
                  key={col.key || ci}
                  align={col.align || 'left'}
                  sx={{
                    width: col.width,
                    fontWeight: 600,
                    fontSize: '0.68rem',
                    color: 'text.secondary',
                    py: 0.75,
                    borderBottom: 'none',
                  }}
                >
                  {col.header}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row, ri) => (
              <TableRow
                key={row.id || ri}
                sx={{
                  '&:hover': { bgcolor: 'grey.50' },
                  '&:last-child td': { borderBottom: 0 },
                }}
              >
                {columns.map((col, ci) => (
                  <TableCell
                    key={col.key || ci}
                    align={col.align || 'left'}
                    sx={{
                      py: dense ? 0.75 : 1,
                      px: 1.5,
                      fontSize: '0.75rem',
                      borderBottom: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    {col.render ? col.render(row[col.key], row) : String(row[col.key] ?? '')}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* ── Pagination ── */}
      {pagination && rows.length > 0 && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            mt: 1,
            px: 0.5,
          }}
        >
          <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>
            {((pagination.page - 1) * pagination.pageSize) + 1}–{Math.min(pagination.page * pagination.pageSize, pagination.total)} of {pagination.total}
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            <IconButton
              size="small"
              disabled={pagination.page <= 1}
              onClick={() => pagination.onChange(pagination.page - 1)}
            >
              <ChevronLeftIcon sx={{ fontSize: '1.125rem' }} />
            </IconButton>
            <IconButton
              size="small"
              disabled={pagination.page * pagination.pageSize >= pagination.total}
              onClick={() => pagination.onChange(pagination.page + 1)}
            >
              <ChevronRightIcon sx={{ fontSize: '1.125rem' }} />
            </IconButton>
          </Box>
        </Box>
      )}
    </Box>
  );
}
