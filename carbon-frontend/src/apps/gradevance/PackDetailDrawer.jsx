// Read-only pack drawer — anchors + rubric bands + KB pin (Phase C).

import React, { useEffect, useState } from 'react';
import {
  Box, Chip, Drawer, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from '@mui/material';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import { useAuth } from '../../auth/AuthContext';
import { fetchProfileDetail } from '../../api/gradevance';

export default function PackDetailDrawer({ open, onClose, packId, version = 1 }) {
  const { token } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !packId) return undefined;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchProfileDetail(token, packId, version)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e?.message || 'Failed to load pack'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open, packId, version, token]);

  return (
    <Drawer anchor="right" open={open} onClose={onClose}>
      <Box sx={{ width: { xs: 320, sm: 420 }, p: 2 }} role="dialog" aria-label="Pack detail">
        <Typography variant="subtitle1" sx={{ mb: 1 }}>
          {data?.name || packId || 'Pack'}
        </Typography>
        {data && (
          <Stack direction="row" spacing={0.75} sx={{ mb: 1.5, flexWrap: 'wrap' }}>
            <Chip size="small" label={`${data.pack_id}@v${data.version}`} />
            <Chip size="small" label={data.mode || '—'} variant="outlined" />
            <Chip size="small" label={data.discipline || '—'} variant="outlined" />
          </Stack>
        )}
        {loading && <LoadingSkeleton variant="table" />}
        {error && <ErrorAlert message={error} />}
        {data && !loading && (
          <Stack spacing={1.5}>
            <Box>
              <Typography variant="subtitle2">Brief stem</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
                {(data.brief?.stem || '—').slice(0, 400)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="subtitle2">KB pin</Typography>
              <Typography variant="caption" color="text.secondary">
                {data.kb
                  ? (typeof data.kb === 'object' ? JSON.stringify(data.kb) : String(data.kb))
                  : 'None on profile — pin via assignment brief'}
              </Typography>
            </Box>
            <Box>
              <Typography variant="subtitle2">
                LCT anchors ({data.anchors?.length || 0})
              </Typography>
              <Table size="small" aria-label="LCT anchors sample">
                <TableHead>
                  <TableRow>
                    <TableCell>Dim</TableCell>
                    <TableCell>Value</TableCell>
                    <TableCell>Span</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(data.anchors || []).slice(0, 12).map((a) => (
                    <TableRow key={a.id || `${a.dimension}-${a.value}-${a.span_text}`}>
                      <TableCell>
                        <Typography variant="caption">{a.dimension === 'semantic_density' ? 'SD' : 'SG'}</Typography>
                      </TableCell>
                      <TableCell><Chip size="small" label={a.value || '—'} /></TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {(a.span_text || '').slice(0, 48)}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!(data.anchors || []).length && (
                    <TableRow>
                      <TableCell colSpan={3}>
                        <Typography variant="caption" color="text.secondary">No anchors</Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </Box>
            <Box>
              <Typography variant="subtitle2">
                Rubric criteria ({(data.rubric_pack?.criteria || []).length})
              </Typography>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                {(data.rubric_pack?.criteria || []).map((c) => (
                  <Chip key={c} size="small" label={c} variant="outlined" />
                ))}
                {!(data.rubric_pack?.criteria || []).length && (
                  <Typography variant="caption" color="text.secondary">No rubric bands</Typography>
                )}
              </Stack>
            </Box>
          </Stack>
        )}
      </Box>
    </Drawer>
  );
}
