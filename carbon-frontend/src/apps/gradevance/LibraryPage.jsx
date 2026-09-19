// Pack / profile library (filesystem SoT mirrored via API catalog).

import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button, Chip, Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from '@mui/material';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchProfiles } from '../../api/gradevance';
import SkipToMain from './SkipToMain';
import PackDetailDrawer from './PackDetailDrawer';

export default function LibraryPage() {
  useDocumentTitle('GradeVance · Library');
  const { token } = useAuth();
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [detailPack, setDetailPack] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    fetchProfiles(token)
      .then((data) => setRows(data.results || []))
      .catch((err) => setError(err?.message || 'Failed to load profiles'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={MenuBookIcon} title="Pack library" subtitle="AssignmentProfiles from domain_packs/eduos" />
        <LoadingSkeleton variant="table" />
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <PageHeader icon={MenuBookIcon} title="Pack library" subtitle="AssignmentProfiles from domain_packs/eduos" />
        <ErrorAlert message={error} onRetry={load} />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <SkipToMain targetId="gradevance-library" />
      <main id="gradevance-library" tabIndex={-1} aria-label="Pack library">
        <PageHeader
          icon={MenuBookIcon}
          title="Pack library"
          subtitle="Config-pluggable profiles — NAA reflective gold, medicine OSCE draft, more via packs only."
        />
        <Typography component="h2" variant="h6" sx={{ mb: 1 }} id="library-catalog-heading">
          Assignment profile catalog
        </Typography>
        <Paper component="section" aria-labelledby="library-catalog-heading">
          <Table size="small" aria-label="GradeVance pack library">
            <caption style={{ captionSide: 'top', textAlign: 'left', padding: '8px 16px' }}>
              AssignmentProfiles from domain_packs/eduos
            </caption>
            <TableHead>
              <TableRow>
                <TableCell scope="col">Profile</TableCell>
                <TableCell scope="col">Discipline</TableCell>
                <TableCell scope="col">Genre</TableCell>
                <TableCell scope="col">Mode</TableCell>
                <TableCell scope="col">LCT</TableCell>
                <TableCell scope="col">Status</TableCell>
                <TableCell scope="col" />
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={`${r.pack_id}@${r.version}`}>
                  <TableCell>
                    <Typography variant="body2" fontWeight={600}>{r.name || r.pack_id}</Typography>
                    <Typography variant="caption" color="text.secondary">{r.pack_id}@v{r.version}</Typography>
                  </TableCell>
                  <TableCell>{r.discipline}</TableCell>
                  <TableCell>{r.genre}</TableCell>
                  <TableCell>{r.mode}</TableCell>
                  <TableCell>
                    <Chip size="small" label={r.lct_enabled ? 'on' : 'off'} color={r.lct_enabled ? 'success' : 'default'} />
                  </TableCell>
                  <TableCell>{r.status}</TableCell>
                  <TableCell>
                    <Button size="small" onClick={() => setDetailPack(r)}>Detail</Button>
                    <Button
                      size="small"
                      onClick={() => navigate(`/teach/stems?tab=author&pack=${encodeURIComponent(r.pack_id)}`)}
                    >
                      Use in stem
                    </Button>
                    <Button
                      size="small"
                      onClick={() => navigate(`/teach/calibration?profile_pack_id=${encodeURIComponent(r.pack_id)}`)}
                    >
                      Calibrate
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      </main>
      <PackDetailDrawer
        open={Boolean(detailPack)}
        onClose={() => setDetailPack(null)}
        packId={detailPack?.pack_id}
        version={detailPack?.version || 1}
      />
    </PageContainer>
  );
}
