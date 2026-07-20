// src/pages/catalog/tabs/AssetAuditTab.jsx
// Asset Audit Tab: Timeline of governance events for the asset

import React, { useMemo } from 'react';
import {
  Box, Table, TableHead, TableBody, TableRow, TableCell, Typography, Chip,
  Accordion, AccordionSummary, AccordionDetails, Alert,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';

const ACTION_COLOR = {
  add: 'success',
  create: 'success',
  edit: 'info',
  update: 'info',
  delete: 'error',
  archive: 'warning',
  restore: 'default',
};

function JsonDiff({ before, after }) {
  if (before == null && after == null) {
    return <Typography variant="caption">No details</Typography>;
  }
  return (
    <Box sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
      {before != null && (
        <Box sx={{ mb: 1 }}>
          <Typography variant="caption" color="error.main" fontWeight={600}>
            Before
          </Typography>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {JSON.stringify(before, null, 2)}
          </pre>
        </Box>
      )}
      {after != null && (
        <Box>
          <Typography variant="caption" color="success.main" fontWeight={600}>
            After
          </Typography>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {JSON.stringify(after, null, 2)}
          </pre>
        </Box>
      )}
    </Box>
  );
}

export default function AssetAuditTab({ additionalProps = {} }) {
  const { events = [] } = additionalProps;

  // Sort events by timestamp, most recent first
  const sortedEvents = useMemo(() => {
    if (!Array.isArray(events)) return [];
    return [...events].sort((a, b) => {
      const timeA = new Date(a.timestamp).getTime();
      const timeB = new Date(b.timestamp).getTime();
      return timeB - timeA;
    });
  }, [events]);

  if (sortedEvents.length === 0) {
    return (
      <DetailTabContent>
        <Alert severity="info">No governance events recorded for this asset.</Alert>
      </DetailTabContent>
    );
  }

  return (
    <DetailTabContent>
      <Typography variant="h6" gutterBottom>Governance Event Timeline</Typography>
      <Box sx={{ overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ bgcolor: 'grey.100' }}>
              <TableCell sx={{ fontWeight: 600 }}>Date & Time</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Action</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Entity Type</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>User</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Details</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sortedEvents.map((event) => (
              <TableRow key={event.id} sx={{ verticalAlign: 'top' }}>
                <TableCell sx={{ fontSize: '0.875rem' }}>
                  {new Date(event.timestamp).toLocaleString()}
                </TableCell>
                <TableCell>
                  <Chip
                    label={event.action || 'unknown'}
                    size="small"
                    color={ACTION_COLOR[event.action] || 'default'}
                    variant="outlined"
                  />
                </TableCell>
                <TableCell sx={{ fontSize: '0.875rem' }}>
                  {event.entity_type || '—'}
                </TableCell>
                <TableCell sx={{ fontSize: '0.875rem' }}>
                  {event.user_name || event.user || '—'}
                </TableCell>
                <TableCell sx={{ minWidth: 250 }}>
                  <Accordion
                    disableGutters
                    elevation={0}
                    sx={{ '&:before': { display: 'none' } }}
                  >
                    <AccordionSummary
                      expandIcon={<ExpandMoreIcon />}
                      sx={{ px: 0, minHeight: 0 }}
                    >
                      <Typography variant="caption">
                        {event.notes || 'View changes'}
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails sx={{ px: 0, pt: 1 }}>
                      <JsonDiff before={event.before} after={event.after} />
                    </AccordionDetails>
                  </Accordion>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
    </DetailTabContent>
  );
}
