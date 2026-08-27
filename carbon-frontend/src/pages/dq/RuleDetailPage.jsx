// carbon-frontend/src/pages/dq/RuleDetailPage.jsx
// Rule detail — Overview | Definition | Test | Lifecycle | Usage & Data Products | Stats | Execution Log
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Alert, Box, CircularProgress } from '@mui/material';
import RuleIcon from '@mui/icons-material/Rule';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { useAITaskTransfer } from '../../shell/useAITaskTransfer';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';
import { getDQRule } from '../../api/dq';
import { useNotes } from '../../notes/NotesContext';
import { registerRuleInspectorTabs } from '../../inspector/tabs/ruleTabs';
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

  // ── Contextual Inspector (global drawer) ────────────────────────────
  const { setContexts } = useNotes();

  useEffect(() => registerRuleInspectorTabs(), []);

  const inspectorContext = useMemo(
    () => [{
      entityType: 'rule',
      entityId: id,
      label: rule?.name,
      payload: { entityData: { rule } },
    }],
    [id, rule],
  );
  useEffect(() => {
    setContexts(inspectorContext);
    return () => setContexts(null);
  }, [inspectorContext, setContexts]);

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

  const headerComponent = (
    <DetailHeader
      title={rule.name || 'Rule'}
      description={rule.description || 'Data quality rule'}
      icon={RuleIcon}
      onClose={handleClose}
    />
  );

  // WorkspaceContext emitted with every AI transfer from the rule detail page.
  const workspaceContext = {
    workspace: 'dq',
    current_view: 'rule_detail',
    entity_type: 'rule',
    entity_id: rule?.id ?? null,
    entity_name: rule?.name ?? null,
    intent_signal: 'debug',
    recent_actions: [],
  };

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
        workspaceContext,
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
        workspaceContext,
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
      loading={false}
      error={null}
      onClose={handleClose}
      storageKey="carbonRuleDetail"
    />
  );
}
