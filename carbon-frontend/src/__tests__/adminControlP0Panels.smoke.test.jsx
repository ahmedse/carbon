// L1 smoke — P0 Control Plane panels still PARTIAL in PULSE-ADMIN-QA-GATE.
// Knowledge · Memory · Prompts · Spend · Roles · Policy dry-run.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({
    token: 'test-token',
    userCapabilities: ['ai:publisher', 'ai:manage_console'],
  }),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({
    notify: vi.fn(),
    notifyFromError: vi.fn(),
    showFeedback: vi.fn(),
  }),
}));

const listKnowledgeItems = vi.fn();
vi.mock('../api/aiKnowledge', () => ({
  listKnowledgeItems: (...a) => listKnowledgeItems(...a),
  createKnowledgeItem: vi.fn(),
  revokeKnowledgeItem: vi.fn(),
}));

const listFacts = vi.fn();
vi.mock('../api/aiWorkspace', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    listFacts: (...a) => listFacts(...a),
    revokeMemoryFact: vi.fn(),
    forgetFact: vi.fn(),
  };
});

const listPromptVersions = vi.fn();
vi.mock('../api/aiPromptGovernance', () => ({
  listPromptVersions: (...a) => listPromptVersions(...a),
  activatePromptVersion: vi.fn(),
  rollbackPromptVersion: vi.fn(),
}));

const getBudgetControl = vi.fn();
const patchBudgetControl = vi.fn();
const pdpDryRun = vi.fn();
vi.mock('../api/aiControlPlane', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    getBudgetControl: (...a) => getBudgetControl(...a),
    patchBudgetControl: (...a) => patchBudgetControl(...a),
    pdpDryRun: (...a) => pdpDryRun(...a),
  };
});

const getUsage = vi.fn();
vi.mock('../api/aiPulse', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    getUsage: (...a) => getUsage(...a),
  };
});

const fetchCapabilityMatrix = vi.fn();
vi.mock('../api/accessControl', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    fetchCapabilityMatrix: (...a) => fetchCapabilityMatrix(...a),
  };
});

vi.mock('../pages/admin/ai/EngineSettingsPanel', () => ({
  default: () => <div>Engine settings stub</div>,
}));

import KnowledgeBasePanel from '../pages/admin/ai/KnowledgeBasePanel';
import MemoryGovernancePanel from '../pages/admin/ai/control/MemoryGovernancePanel';
import PromptsPanel from '../pages/admin/ai/PromptsPanel';
import PlatformHubPage from '../pages/admin/ai/control/PlatformBudgetPanel';
import RolesMatrixPanel from '../pages/admin/ai/control/RolesMatrixPanel';
import PolicyDryRunPanel from '../pages/admin/ai/control/PolicyDryRunPanel';

beforeEach(() => {
  vi.clearAllMocks();
  listKnowledgeItems.mockResolvedValue({ results: [] });
  listFacts.mockResolvedValue({ results: [] });
  listPromptVersions.mockResolvedValue({ results: [], note: '' });
  getBudgetControl.mockResolvedValue({
    spend: {
      spent_today_usd: 1.25,
      budget_usd: 50,
      budget_exceeded: false,
      override_active: false,
    },
    containment: { daily_budget_usd: null },
  });
  getUsage.mockResolvedValue({
    spent_today_usd: 1.25,
    budget_usd: 50,
    budget_exceeded: false,
    calls_today: 3,
    tokens_today: 100,
    by_model: [],
    last_7_days: [],
  });
  fetchCapabilityMatrix.mockResolvedValue({
    domains: [
      {
        domain: 'ai',
        capabilities: [{ key: 'ai:publisher' }, { key: 'ai:view_console' }],
      },
    ],
    matrix: [
      {
        group: 'ai_publishers',
        capabilities: [{ key: 'ai:publisher' }],
      },
    ],
  });
  pdpDryRun.mockResolvedValue({ decision: 'allow', reason: 'dry_run ok' });
});

describe('L1 P0 panel smoke', () => {
  it('Knowledge — heading + New item gated control', async () => {
    render(<KnowledgeBasePanel />);
    expect(await screen.findByText('Curated knowledge')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /New item/i })).toBeEnabled();
    expect(screen.getByText(/No curated knowledge items/i)).toBeInTheDocument();
  });

  it('Memory — heading + empty provenance copy', async () => {
    render(<MemoryGovernancePanel />);
    expect(await screen.findByText('Memory')).toBeInTheDocument();
    expect(
      screen.getByText(/Revoke stops future use while keeping the row for audit/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/No memory facts/i)).toBeInTheDocument();
  });

  it('Prompts — title + PEC-7A disclaimer', async () => {
    render(<PromptsPanel />);
    expect(await screen.findByText('Prompt versions')).toBeInTheDocument();
    expect(
      screen.getByText(/Live chat uses instance\.yaml \(PEC-7A\)/i),
    ).toBeInTheDocument();
  });

  it('Spend — budget override surface + today spend', async () => {
    render(
      <MemoryRouter>
        <PlatformHubPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText('Spend & caps')).toBeInTheDocument();
    expect(screen.getByLabelText(/Daily budget USD override/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Save$/i })).toBeInTheDocument();
    expect(screen.getByText(/Today: \$1\.25 \/ \$50\.00/i)).toBeInTheDocument();
  });

  it('Roles — AI matrix + Access Control link', async () => {
    render(
      <MemoryRouter>
        <RolesMatrixPanel />
      </MemoryRouter>,
    );
    expect(await screen.findByText('Roles & AI capabilities')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Assign users/i })).toHaveAttribute(
      'href',
      '/admin/access',
    );
    expect(await screen.findByText('ai_publishers')).toBeInTheDocument();
    expect(screen.getByText('publisher')).toBeInTheDocument();
  });

  it('Policy dry-run — simulate returns decision chip', async () => {
    render(<PolicyDryRunPanel />);
    expect(await screen.findByText('Policy dry-run')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Simulate/i }));
    await waitFor(() => {
      expect(pdpDryRun).toHaveBeenCalled();
    });
    expect(await screen.findByText('allow')).toBeInTheDocument();
    expect(screen.getByText('dry_run ok')).toBeInTheDocument();
  });
});
