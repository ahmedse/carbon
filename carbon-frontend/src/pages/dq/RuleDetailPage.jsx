// carbon-frontend/src/pages/dq/RuleDetailPage.jsx
// Rule detail — Definition | Operations | Usage & Data Products | Stats | Results
import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Alert, Box, Chip, CircularProgress, Paper, Typography } from '@mui/material';
import RuleIcon from '@mui/icons-material/Rule';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';
import { getDQRule, runDQRule } from '../../api/dq';
import { RULE_TYPE_LABELS, RULE_LEVEL_LABELS, DIMENSION_LABELS, SEVERITY_LABELS, SEVERITY_COLORS } from './constants';
import DefinitionTab from './tabs/DefinitionTab';
import OperationsTab from './tabs/OperationsTab';
import UsageTab from './tabs/UsageTab';
import StatsTab from './tabs/StatsTab';
import ResultsTab from './tabs/ResultsTab';

export default function RuleDetailPage() {
  useDocumentTitle('Rule Detail');
  const { id } = useParams();
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const navigate = useNavigate();

  const [rule, setRule] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadRule = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDQRule(token, id);
      setRule(data);
    } catch (err) {
      const msg = err.message || 'Rule not found';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [id, token, notify]);

  useEffect(() => {
    loadRule();
  }, [loadRule]);

  const handleClose = () => navigate(-1);

  const handleRun = async (target) => {
    try {
      const job = await runDQRule(token, target.id);
      notify({
        message: `"${target.name}" queued as job #${job.id} — tracking on the Jobs tab`,
        type: 'success',
      });
      navigate('/dq#jobs');
    } catch (err) {
      notifyFromError(err, 'Could not run rule');
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!rule) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error || 'Rule not found'}</Alert>
      </Box>
    );
  }

  const RuleSummaryMetrics = () => (
    <Box sx={{ p: 2 }}>
      <Box sx={{ display: 'grid', gap: 1.5 }}>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Version</Typography>
          <Typography variant="h6">{rule.version ?? 1}</Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Results</Typography>
          <Typography variant="h6">{rule.results_count ?? 0}</Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Dimension</Typography>
          <Typography variant="body2" sx={{ mt: 0.5 }}>
            {DIMENSION_LABELS[rule.dimension] || rule.dimension || '—'}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Severity</Typography>
          <Box sx={{ mt: 0.5 }}>
            <Chip
              size="small"
              color={SEVERITY_COLORS[rule.severity] || 'default'}
              label={SEVERITY_LABELS[rule.severity] || rule.severity}
            />
          </Box>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Type</Typography>
          <Typography variant="body2" sx={{ mt: 0.5 }}>
            {RULE_TYPE_LABELS[rule.rule_type] || rule.rule_type}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Level</Typography>
          <Typography variant="body2" sx={{ mt: 0.5 }}>
            {RULE_LEVEL_LABELS[rule.rule_level] || rule.rule_level}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Created</Typography>
          <Typography variant="body2" sx={{ mt: 0.5 }}>
            {rule.created_at ? new Date(rule.created_at).toLocaleDateString() : '—'}
            {rule.created_by_name ? ` by ${rule.created_by_name}` : ''}
          </Typography>
        </Paper>
      </Box>
    </Box>
  );

  const headerComponent = (
    <DetailHeader
      title={rule.name || 'Rule'}
      description={rule.description || 'Data quality rule'}
      icon={RuleIcon}
      onClose={handleClose}
    />
  );

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: 'Definition', component: () => <DefinitionTab rule={rule} onChanged={loadRule} /> },
        { label: 'Operations', component: () => <OperationsTab rule={rule} onChanged={loadRule} onRun={handleRun} /> },
        { label: 'Usage & Data Products', component: () => <UsageTab rule={rule} /> },
        { label: 'Stats', component: () => <StatsTab rule={rule} /> },
        { label: 'Results', component: () => <ResultsTab rule={rule} /> },
      ]}
      metricsTabs={[{ label: 'Summary', component: RuleSummaryMetrics }]}
      loading={false}
      error={null}
      onClose={handleClose}
      storageKey="carbonRuleDetail"
      entityData={{ rule }}
    />
  );
}
