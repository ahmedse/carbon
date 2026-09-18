// src/pages/admin/ai/control/hubPages.jsx
// Pulse Control Plane destinations (ADR-0036).
import React from 'react';
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

export function DomainHubPage() {
  return (
    <ControlHub
      title="Domain"
      defaultTab="processes"
      tabs={[
        { id: 'processes', label: 'Processes', element: <ProcessRegistry /> },
        { id: 'capabilities', label: 'Capabilities', element: <CapabilitiesPanel /> },
        { id: 'policy', label: 'Policy', element: <PolicyDryRunPanel /> },
        { id: 'agents', label: 'Agents', element: <AgentsPanel /> },
        { id: 'tools', label: 'Tools', element: <ToolsPanel /> },
        { id: 'topology', label: 'Topology', element: <AgentTopologyPanel /> },
        { id: 'archetypes', label: 'Archetypes', element: <PulseArchetypesPanel /> },
      ]}
    />
  );
}

export function AssetsHubPage() {
  return (
    <ControlHub
      title="Assets"
      defaultTab="knowledge"
      tabs={[
        { id: 'knowledge', label: 'Knowledge', element: <KnowledgeBasePanel /> },
        { id: 'memory', label: 'Memory', element: <MemoryGovernancePanel /> },
        { id: 'graph', label: 'Graph', element: <KnowledgeGraphPanel /> },
        { id: 'skills', label: 'Skills', element: <SkillsPanel /> },
        { id: 'prompts', label: 'Prompts', element: <PromptsPanel /> },
      ]}
    />
  );
}

export function EvidenceHubPage() {
  return (
    <ControlHub
      title="Evidence"
      defaultTab="explorer"
      tabs={[
        { id: 'explorer', label: 'Explorer', element: <EvidenceExplorerPanel /> },
        { id: 'audit', label: 'Audit', element: <AuditPanel /> },
        { id: 'runs', label: 'Runs', element: <RunTimelinePanel /> },
        { id: 'inbox', label: 'Inbox', element: <HumanTaskInbox /> },
        { id: 'watches', label: 'Watches', element: <WatchesPanel /> },
        { id: 'logs', label: 'Logs', element: <AILogsPanel /> },
        { id: 'quality', label: 'Quality', element: <OutputQualityPanel /> },
      ]}
    />
  );
}

export function LearningHubPage() {
  return (
    <ControlHub
      title="Learning"
      defaultTab="review"
      tabs={[
        { id: 'review', label: 'Review Queue', element: <ReviewQueue /> },
        { id: 'candidates', label: 'Candidates', element: <LearningCandidatesPanel /> },
        { id: 'feedback', label: 'Feedback', element: <FeedbackPanel /> },
        { id: 'jobs', label: 'Jobs', element: <LearningJobsPanel /> },
        { id: 'flywheel', label: 'Flywheel', element: <LearningFlywheelPanel /> },
        { id: 'skills', label: 'Skill Learning', element: <SkillLearningPanel /> },
      ]}
    />
  );
}
