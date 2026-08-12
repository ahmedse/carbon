// carbon-frontend/src/pages/dq/RuleDetailPage.jsx
// Rule detail — Overview | Definition | Test | Lifecycle | Usage & Data Products | Stats | Execution Log
import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Alert, Box, Chip, CircularProgress, Paper, Typography } from '@mui/material';
import RuleIcon from '@mui/icons-material/Rule';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { useAITaskTransfer } from '../../shell/useAITaskTransfer';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';
import { getDQRule } from '../../api/dq';
import { RULE_TYPE_LABELS, RULE_LEVEL_LABELS, DIMENSION_LABELS, SEVERITY_LABELS, SEVERITY_COLORS } from './constants';
import OverviewTab from './tabs/OverviewTab';
import DefinitionTab from './tabs/DefinitionTab';
import TestTab from './tabs/TestTab';
import OperationsTab from './tabs/OperationsTab';
import UsageTab from './tabs/UsageTab';
import StatsTab from './tabs/StatsTab';
import ResultsTab from './tabs/ResultsTab';

export default function RuleDetailPage() {
  useDocumentTitle('Rule Detail');
  const { id } = useParams();
  const { token } = useAuth();
  const { notify } = useNotification();
  const { transferTask } = useAITaskTransfer();
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

  const handleAnalyzeTrendWithAI = async () => {
    await transferTask(
      'nl_query',
      {
        rule_id: rule.id,
        rule_name: rule.name,
        prompt: `Analyze trend and reliability for rule "${rule.name}" over recent runs.`,
      },
      {
        title: `Trend Analysis: ${rule.name}`,
        source_page: 'dq-rule-stats',
      },
    );
  };

  const handleExplainFailuresWithAI = async () => {
    await transferTask(
      'nl_query',
      {
        rule_id: rule.id,
        rule_name: rule.name,
        prompt: `Explain recurring failure patterns for rule "${rule.name}" and suggest improvements.`,
      },
      {
        title: `Failure Analysis: ${rule.name}`,
        source_page: 'dq-rule-results',
      },
    );
  };

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: 'Overview', component: () => <OverviewTab rule={rule} /> },
        { label: 'Definition', component: () => <DefinitionTab rule={rule} onChanged={loadRule} /> },
        { label: 'Test', component: () => <TestTab rule={rule} /> },
        { label: 'Lifecycle', component: () => <OperationsTab rule={rule} onChanged={loadRule} /> },
        { label: 'Usage & Data Products', component: () => <UsageTab rule={rule} /> },
        { label: 'Stats', component: () => <StatsTab rule={rule} onAnalyzeAI={handleAnalyzeTrendWithAI} /> },
        { label: 'Execution Log', component: () => <ResultsTab rule={rule} onExplainAI={handleExplainFailuresWithAI} /> },
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
