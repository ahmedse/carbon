// carbon-frontend/src/pages/dq/RuleDetailPage.jsx
// Rule detail — Overview | Definition | Test | Lifecycle | Usage & Data Products | Stats | Execution Log
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation('dq');
  useDocumentTitle(t('ruleDetail.title'));
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
      const msg = err.message || t('ruleDetail.notFound');
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [id, token, notify, t]);

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
        <Alert severity="error">{error || t('ruleDetail.notFound')}</Alert>
      </Box>
    );
  }

  const headerComponent = (
    <DetailHeader
      title={rule.name || t('ruleDetail.fallbackName')}
      description={rule.description || t('ruleDetail.fallbackDescription')}
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
        title: t('stats.trendAnalysisTitle', { name: rule.name }),
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
        title: t('results.failureAnalysisTitle', { name: rule.name }),
        source_page: 'dq-rule-results',
        workspaceContext,
      },
    );
  };

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: t('tab.overview'), component: () => <OverviewTab rule={rule} /> },
        { label: t('tab.definition'), component: () => <DefinitionTab rule={rule} onChanged={loadRule} /> },
        { label: t('tab.test'), component: () => <TestTab rule={rule} /> },
        { label: t('tab.lifecycle'), component: () => <OperationsTab rule={rule} onChanged={loadRule} /> },
        { label: t('tab.usageDataProducts'), component: () => <UsageTab rule={rule} /> },
        { label: t('tab.stats'), component: () => <StatsTab rule={rule} onAnalyzeAI={handleAnalyzeTrendWithAI} /> },
        { label: t('tab.executionLog'), component: () => <ResultsTab rule={rule} onExplainAI={handleExplainFailuresWithAI} /> },
      ]}
      loading={false}
      error={null}
      onClose={handleClose}
      storageKey="carbonRuleDetail"
    />
  );
}
