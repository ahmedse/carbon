import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { Alert, Box, Button, Skeleton, Stack, Tab, Tabs, Typography } from '@mui/material';
import StairsIcon from '@mui/icons-material/Stairs';
import VisibilityRounded from '@mui/icons-material/VisibilityRounded';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../../components/layout/PageContainer';
import PageHeader from '../../../components/Page/PageHeader';
import WorkflowCard from '../../../components/Cards/WorkflowCard';
import EmptyState from '../../../components/Page/EmptyState';
import FilteredDataGrid from '../../../components/FilteredDataGrid';
import TabPanel from '../../../components/Layout/TabPanel';

const ROOM_DOMAINS = new Set(['pulse', 'nibras']);
const BUTTON_COLOR = {
  reached: 'success',
  partial: 'warning',
  fail: 'error',
  missing: 'warning',
  absent: 'inherit',
  unmeasured: 'inherit',
};

function label(t, key, fallback) {
  const value = t(key);
  return value === key ? fallback : value;
}

export default function ReadinessRoom({
  data, loading, error, onRetry, navigate, context, board, row, column, definitionId,
  apps, appsLoading, appsError, onRetryApps,
}) {
  const { t } = useTranslation('excellence');
  const domains = data?.domains || [];
  const domain = domains.find((item) => item.id === context) || null;

  if (loading) {
    return (
      <PageContainer>
        <Stack spacing={1} aria-busy="true" aria-label={t('title')}>
          <Skeleton variant="rounded" sx={{ height: 28 }} />
          <Skeleton variant="rounded" sx={{ height: 88 }} />
        </Stack>
      </PageContainer>
    );
  }
  if (error) {
    return (
      <PageContainer>
        <Alert severity="error" action={<Button color="inherit" size="small" onClick={onRetry}>{t('common:retry')}</Button>}>
          {t('loadFailed')}
        </Alert>
      </PageContainer>
    );
  }
  if (definitionId && domain) {
    return <DefinitionPage t={t} domain={domain} definitionId={definitionId} navigate={navigate} />;
  }
  if (board && row && column && domain) {
    return <CellPage t={t} data={data} domain={domain} board={board} rowId={row} columnId={column} navigate={navigate} />;
  }
  if (domain) {
    return (
      <DomainBoard
        t={t}
        data={data}
        domain={domain}
        navigate={navigate}
        apps={apps}
        appsLoading={appsLoading}
        appsError={appsError}
        onRetryApps={onRetryApps}
      />
    );
  }
  return <DomainCatalogue t={t} domains={domains} navigate={navigate} />;
}

function DomainCatalogue({ t, domains, navigate }) {
  return (
    <PageContainer>
      <PageHeader icon={StairsIcon} title={t('title')} subtitle={t('chooseDomain')} description={t('chooseDomainHint')} />
      {domains.length === 0 ? (
        <EmptyState title={t('emptyTitle')} description={t('emptyDescription')} />
      ) : (
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', lg: '1fr 1fr 1fr' }, gap: 1 }}>
          {domains.map((domain) => (
            <WorkflowCard
              key={domain.id}
              icon={domain.id === 'nibras' ? <VisibilityRounded /> : <StairsIcon />}
              title={label(t, `domains.${domain.id}.title`, domain.id)}
              description={label(t, `domains.${domain.id}.question`, domain.id)}
              onClick={() => navigate(`/admin/excellence/${domain.id}`)}
            />
          ))}
        </Box>
      )}
    </PageContainer>
  );
}

function DomainBoard({ t, data, domain, navigate, apps, appsLoading, appsError, onRetryApps }) {
  const [tab, setTab] = useState(0);
  const boards = ['readiness', 'actualization'];
  return (
    <PageContainer>
      <PageHeader
        icon={StairsIcon}
        title={label(t, `domains.${domain.id}.title`, domain.id)}
        subtitle={label(t, `domains.${domain.id}.question`, '')}
        description={label(t, `instances.${domain.instance}`, domain.instance)}
        actions={(
          <Button size="small" onClick={() => navigate('/admin/excellence')}>{t('allDomains')}</Button>
        )}
      />
      <Tabs value={tab} onChange={(_event, value) => setTab(value)} variant="scrollable" aria-label={t('title')}>
        <Tab label={t('tabs.readiness')} />
        <Tab label={t('tabs.actualization')} />
        <Tab label={t('tabs.definitions')} />
      </Tabs>
      {boards.map((board, index) => (
        <TabPanel key={board} value={tab} index={index}>
          <Scoreboard t={t} data={data} domain={domain} board={board} navigate={navigate} />
        </TabPanel>
      ))}
      <TabPanel value={tab} index={2}>
        <DefinitionList t={t} data={data} domain={domain} navigate={navigate} />
      </TabPanel>
      <EngineeringLadder
        t={t}
        domain={domain}
        navigate={navigate}
        apps={apps}
        loading={appsLoading}
        error={appsError}
        onRetry={onRetryApps}
      />
    </PageContainer>
  );
}

function Scoreboard({ t, data, domain, board, navigate }) {
  const columns = data?.boards?.[board]?.columns || [];
  const rows = data?.rows?.[domain.id] || [];
  return (
    <Stack spacing={1}>
      <Typography variant="body2" color="text.secondary">{t(`boards.${board}`)}</Typography>
      <Box sx={{ overflowX: 'auto' }}>
      <Box sx={{ display: 'grid', gridTemplateColumns: `minmax(8rem, 11rem) repeat(${columns.length}, minmax(5.5rem, 1fr))`, gap: 0.5, alignItems: 'center', minWidth: 720 }}>
        <Box />
        {columns.map((column) => (
          <Typography key={column} variant="caption" align="center" color="text.secondary">
            {label(t, `columns.${column}.title`, column)}
          </Typography>
        ))}
        {rows.map((item) => (
          <React.Fragment key={item.id}>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="body2">{label(t, `rows.${item.id}.title`, item.id)}</Typography>
              <Typography variant="caption" color="text.secondary">{label(t, `rows.${item.id}.question`, '')}</Typography>
            </Box>
            {columns.map((column) => {
              const cell = data?.cells?.[domain.id]?.[board]?.[item.id]?.[column] || { state: 'unmeasured' };
              const state = cell.state || 'unmeasured';
              const rowTitle = label(t, `rows.${item.id}.title`, item.id);
              const columnTitle = label(t, `columns.${column}.title`, column);
              const stateTitle = label(t, `states.${state}`, state);
              return (
                <Button
                  key={column}
                  size="small"
                  variant="outlined"
                  color={BUTTON_COLOR[state] || 'inherit'}
                  aria-label={`${rowTitle} ${columnTitle} ${stateTitle}`}
                  onClick={() => navigate(`/admin/excellence/${domain.id}/cells/${board}/${item.id}/${column}`)}
                  sx={{ minWidth: 0, px: 0.5 }}
                >
                  {stateTitle}
                </Button>
              );
            })}
          </React.Fragment>
        ))}
      </Box>
      </Box>
    </Stack>
  );
}

function EngineeringLadder({ t, domain, navigate, apps, loading, error, onRetry }) {
  if (!loading && !error && !(apps || []).length) return null;
  return (
    <Stack spacing={1} sx={{ mt: 2 }}>
      <Typography variant="subtitle2">{t('engineeringLadder')}</Typography>
      <Typography variant="body2" color="text.secondary">{t('ladderHint')}</Typography>
      {loading && <Skeleton variant="rounded" sx={{ height: 88 }} />}
      {error && !loading && (
        <Alert severity="warning" action={<Button color="inherit" size="small" onClick={onRetry}>{t('common:retry')}</Button>}>
          {t('ladderUnavailable')}
        </Alert>
      )}
      {!loading && !error && (
        <FilteredDataGrid
          embedded
          title={t('engineeringLadder')}
          rows={apps}
          getRowId={(item) => item.id}
          onRowClick={(params) => navigate(`/admin/excellence/${domain.id}/${encodeURIComponent(params.row.id)}`)}
          columns={[
            { field: 'title', headerName: t('component'), flex: 1, minWidth: 180 },
            { field: 'level_name', headerName: t('progress'), width: 160 },
          ]}
          emptyMessage={t('emptyTitle')}
        />
      )}
    </Stack>
  );
}

function CellPage({ t, data, domain, board, rowId, columnId, navigate }) {
  const columns = data?.boards?.[board]?.columns || [];
  const known = columns.includes(columnId) && (data?.rows?.[domain.id] || []).some((item) => item.id === rowId);
  const cell = data?.cells?.[domain.id]?.[board]?.[rowId]?.[columnId];
  const owner = (data?.rows?.[domain.id] || []).find((item) => item.id === rowId)?.owner || '';
  if (!known || !cell) {
    return (
      <PageContainer>
        <EmptyState title={rowId} description={columnId} actionLabel={t('allDomains')} onAction={() => navigate(`/admin/excellence/${domain.id}`)} />
      </PageContainer>
    );
  }
  const fields = [
    [t('cell.means'), label(t, `columns.${columnId}.means`, '')],
    [t('cell.reading'), cell.reading || t('cell.unmeasuredReading')],
    [t('cell.proof'), cell.proof || '—'],
    [t('cell.limit'), cell.limit || '—'],
    [t('cell.action'), cell.action || '—'],
    [t('cell.owner'), owner || '—'],
    [t('cell.observed'), cell.observed_at || '—'],
  ];
  return (
    <PageContainer>
      <PageHeader
        icon={StairsIcon}
        title={`${label(t, `rows.${rowId}.title`, rowId)} · ${label(t, `columns.${columnId}.title`, columnId)}`}
        subtitle={label(t, `states.${cell.state}`, cell.state)}
        description={label(t, `rows.${rowId}.question`, '')}
        actions={<Button size="small" onClick={() => navigate(`/admin/excellence/${domain.id}`)}>{label(t, `domains.${domain.id}.title`, domain.id)}</Button>}
      />
      <Stack spacing={1}>
        {fields.map(([name, value]) => (
          <Box key={name}>
            <Typography variant="caption" color="text.secondary">{name}</Typography>
            <Typography variant="body2">{value}</Typography>
          </Box>
        ))}
        <Alert severity="info">{t('cell.neighbor')}</Alert>
      </Stack>
    </PageContainer>
  );
}

function DefinitionList({ t, data, domain, navigate }) {
  const rows = (data?.definitions || []).map((item) => ({
    id: item.id,
    group: label(t, `groups.${item.group}`, item.group),
    term: label(t, `definitions.${item.id}.title`, item.id),
  }));
  return (
    <FilteredDataGrid
      embedded
      title={t('tabs.definitions')}
      rows={rows}
      getRowId={(item) => item.id}
      onRowClick={(params) => navigate(`/admin/excellence/${domain.id}/definitions/${params.row.id}`)}
      columns={[
        { field: 'group', headerName: t('definitions.group'), width: 140 },
        { field: 'term', headerName: t('definitions.term'), flex: 1, minWidth: 180 },
      ]}
      emptyMessage={t('emptyTitle')}
    />
  );
}

function DefinitionPage({ t, domain, definitionId, navigate }) {
  const title = label(t, `definitions.${definitionId}.title`, '');
  if (!title) {
    return (
      <PageContainer>
        <EmptyState title={definitionId} actionLabel={t('allDomains')} onAction={() => navigate(`/admin/excellence/${domain.id}`)} />
      </PageContainer>
    );
  }
  return (
    <PageContainer>
      <PageHeader
        icon={StairsIcon}
        title={title}
        subtitle={t('tabs.definitions')}
        actions={<Button size="small" onClick={() => navigate(`/admin/excellence/${domain.id}`)}>{label(t, `domains.${domain.id}.title`, domain.id)}</Button>}
      />
      <Typography variant="body2">{t(`definitions.${definitionId}.body`)}</Typography>
    </PageContainer>
  );
}

ReadinessRoom.propTypes = {
  data: PropTypes.object,
  loading: PropTypes.bool,
  error: PropTypes.string,
  onRetry: PropTypes.func,
  navigate: PropTypes.func.isRequired,
  context: PropTypes.string,
  board: PropTypes.string,
  row: PropTypes.string,
  column: PropTypes.string,
  definitionId: PropTypes.string,
  apps: PropTypes.array,
  appsLoading: PropTypes.bool,
  appsError: PropTypes.string,
  onRetryApps: PropTypes.func,
};

DomainCatalogue.propTypes = { t: PropTypes.func.isRequired, domains: PropTypes.array.isRequired, navigate: PropTypes.func.isRequired };
DomainBoard.propTypes = {
  t: PropTypes.func.isRequired, data: PropTypes.object, domain: PropTypes.object.isRequired, navigate: PropTypes.func.isRequired,
  apps: PropTypes.array, appsLoading: PropTypes.bool, appsError: PropTypes.string, onRetryApps: PropTypes.func,
};
EngineeringLadder.propTypes = {
  t: PropTypes.func.isRequired, domain: PropTypes.object.isRequired, navigate: PropTypes.func.isRequired,
  apps: PropTypes.array, loading: PropTypes.bool, error: PropTypes.string, onRetry: PropTypes.func,
};
Scoreboard.propTypes = { t: PropTypes.func.isRequired, data: PropTypes.object, domain: PropTypes.object.isRequired, board: PropTypes.string.isRequired, navigate: PropTypes.func.isRequired };
CellPage.propTypes = { t: PropTypes.func.isRequired, data: PropTypes.object, domain: PropTypes.object.isRequired, board: PropTypes.string.isRequired, rowId: PropTypes.string.isRequired, columnId: PropTypes.string.isRequired, navigate: PropTypes.func.isRequired };
DefinitionList.propTypes = { t: PropTypes.func.isRequired, data: PropTypes.object, domain: PropTypes.object.isRequired, navigate: PropTypes.func.isRequired };
DefinitionPage.propTypes = { t: PropTypes.func.isRequired, domain: PropTypes.object.isRequired, definitionId: PropTypes.string.isRequired, navigate: PropTypes.func.isRequired };

export { ROOM_DOMAINS };
