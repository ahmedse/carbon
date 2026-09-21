// src/pages/admin/ai/control/hubPages.jsx
// Pulse Control Plane destinations (ADR-0036).
import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { shellLabel } from '../../../../i18n/shellLabels';
import ControlHub from './ControlHub';
import CommandCenterPage from './CommandCenterPage';
import EvidenceExplorerPanel from './EvidenceExplorerPanel';
import LearningCandidatesPanel from './LearningCandidatesPanel';
import PolicyDryRunPanel from './PolicyDryRunPanel';
import PlatformHubPage from './PlatformBudgetPanel';
import ProcessRegistry from '../ProcessRegistry';
import CapabilitiesPanel from '../CapabilitiesPanel';
import AgentsPanel from '../AgentsPanel';
import ToolsPanel from '../ToolsPanel';
import AgentTopologyPanel from '../AgentTopologyPanel';
import PulseArchetypesPanel from '../PulseArchetypesPanel';
import KnowledgeBasePanel from '../KnowledgeBasePanel';
import MemoryGovernancePanel from './MemoryGovernancePanel';
import KnowledgeGraphPanel from '../KnowledgeGraphPanel';
import SkillsPanel from '../SkillsPanel';
import PromptsPanel from '../PromptsPanel';
import AuditPanel from '../AuditPanel';
import RunTimelinePanel from '../RunTimelinePanel';
import HumanTaskInbox from '../HumanTaskInbox';
import WatchesPanel from '../WatchesPanel';
import AILogsPanel from '../AILogsPanel';
import OutputQualityPanel from '../OutputQualityPanel';
import ReviewQueue from '../ReviewQueue';
import FeedbackPanel from '../FeedbackPanel';
import LearningJobsPanel from '../LearningJobsPanel';
import LearningFlywheelPanel from '../LearningFlywheelPanel';
import SkillLearningPanel from '../SkillLearningPanel';

export { CommandCenterPage, PlatformHubPage };

function useShellNavLabel() {
  const { t } = useTranslation('shell');
  return (english) => shellLabel(t, english);
}

export function DomainHubPage() {
  const label = useShellNavLabel();
  const { t } = useTranslation('shell');
  const tabs = useMemo(
    () => [
      { id: 'processes', label: label('Processes'), element: <ProcessRegistry /> },
      { id: 'capabilities', label: label('Capabilities'), element: <CapabilitiesPanel /> },
      { id: 'policy', label: label('Policy'), element: <PolicyDryRunPanel /> },
      { id: 'agents', label: label('Agents'), element: <AgentsPanel /> },
      { id: 'tools', label: label('Tools'), element: <ToolsPanel /> },
      { id: 'topology', label: label('Topology'), element: <AgentTopologyPanel /> },
      { id: 'archetypes', label: label('Archetypes'), element: <PulseArchetypesPanel /> },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t],
  );
  return <ControlHub title={label('Domain')} defaultTab="processes" tabs={tabs} />;
}

export function AssetsHubPage() {
  const label = useShellNavLabel();
  const { t } = useTranslation('shell');
  const tabs = useMemo(
    () => [
      { id: 'knowledge', label: label('Knowledge Base'), element: <KnowledgeBasePanel /> },
      { id: 'memory', label: label('Memory'), element: <MemoryGovernancePanel /> },
      { id: 'graph', label: label('Graph'), element: <KnowledgeGraphPanel /> },
      { id: 'skills', label: label('Skills'), element: <SkillsPanel /> },
      { id: 'prompts', label: label('Prompts'), element: <PromptsPanel /> },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t],
  );
  return <ControlHub title={label('Assets')} defaultTab="knowledge" tabs={tabs} />;
}

export function EvidenceHubPage() {
  const label = useShellNavLabel();
  const { t } = useTranslation('shell');
  const tabs = useMemo(
    () => [
      { id: 'explorer', label: label('Explorer'), element: <EvidenceExplorerPanel /> },
      { id: 'audit', label: label('Audit'), element: <AuditPanel /> },
      { id: 'runs', label: label('Runs'), element: <RunTimelinePanel /> },
      { id: 'inbox', label: label('Inbox'), element: <HumanTaskInbox /> },
      { id: 'watches', label: label('Watches'), element: <WatchesPanel /> },
      { id: 'logs', label: label('Logs'), element: <AILogsPanel /> },
      { id: 'quality', label: label('Quality'), element: <OutputQualityPanel /> },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t],
  );
  return <ControlHub title={label('Evidence')} defaultTab="explorer" tabs={tabs} />;
}

export function LearningHubPage() {
  const label = useShellNavLabel();
  const { t } = useTranslation('shell');
  const tabs = useMemo(
    () => [
      { id: 'review', label: label('Review Queue'), element: <ReviewQueue /> },
      { id: 'candidates', label: label('Candidates'), element: <LearningCandidatesPanel /> },
      { id: 'feedback', label: label('Feedback'), element: <FeedbackPanel /> },
      { id: 'jobs', label: label('Jobs'), element: <LearningJobsPanel /> },
      { id: 'flywheel', label: label('Flywheel'), element: <LearningFlywheelPanel /> },
      { id: 'skills', label: label('Skill Learning'), element: <SkillLearningPanel /> },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t],
  );
  return <ControlHub title={label('Learning')} defaultTab="review" tabs={tabs} />;
}
