// src/__tests__/aiCatalog.test.js
// W3-G — AI Admin catalog API wrapper specs (admin OBSERVE + MANAGE surface).
// Asserts exact endpoint strings + options: role filter query, POST payload,
// PATCH without name, DELETE, consent-gated replay {confirm: true}, body-less
// resume. Mirrors the aiWorkspace.test.js apiFetch-mock pattern.
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../api/api', () => ({
  apiFetch: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

import { apiFetch } from '../api/api';
import {
  listAgents,
  getAgent,
  createAgent,
  updateAgent,
  deleteAgent,
  getTopology,
  listSkills,
  getFederatedIndex,
  getRunTimeline,
  resumeRun,
  replayRun,
} from '../api/aiCatalog';

const TOKEN = 'test-token';

beforeEach(() => {
  vi.clearAllMocks();
  apiFetch.mockResolvedValue({});
});

describe('aiCatalog — read wrappers', () => {
  it('listAgents hits ai/catalog/ with no query by default', async () => {
    await listAgents(TOKEN);
    expect(apiFetch).toHaveBeenCalledWith('ai/catalog/', { token: TOKEN });
  });

  it('listAgents appends ?role= when a role filter is provided', async () => {
    await listAgents(TOKEN, { role: 'researcher' });
    expect(apiFetch).toHaveBeenCalledWith('ai/catalog/?role=researcher', { token: TOKEN });
  });

  it('getAgent hits ai/catalog/{id}/', async () => {
    await getAgent(TOKEN, 'agent-1');
    expect(apiFetch).toHaveBeenCalledWith('ai/catalog/agent-1/', { token: TOKEN });
  });

  it('getTopology hits ai/catalog/topology/', async () => {
    await getTopology(TOKEN);
    expect(apiFetch).toHaveBeenCalledWith('ai/catalog/topology/', { token: TOKEN });
  });

  it('listSkills hits ai/catalog/skills/', async () => {
    await listSkills(TOKEN);
    expect(apiFetch).toHaveBeenCalledWith('ai/catalog/skills/', { token: TOKEN });
  });

  it('getFederatedIndex hits ai/catalog/index/ with role query', async () => {
    await getFederatedIndex(TOKEN, { role: 'planner' });
    expect(apiFetch).toHaveBeenCalledWith('ai/catalog/index/?role=planner', { token: TOKEN });
  });

  it('getRunTimeline hits ai/runs/{id}/timeline/ as GET', async () => {
    await getRunTimeline(TOKEN, 'run-42');
    expect(apiFetch).toHaveBeenCalledWith('ai/runs/run-42/timeline/', { token: TOKEN });
  });
});

describe('aiCatalog — write wrappers (admin-gated)', () => {
  it('createAgent POSTs the full body to ai/catalog/', async () => {
    const body = {
      name: 'Fetcher',
      role: 'researcher',
      tool_set: ['web_search'],
      max_turns: 4,
    };
    await createAgent(TOKEN, body);
    expect(apiFetch).toHaveBeenCalledWith('ai/catalog/', {
      token: TOKEN,
      method: 'POST',
      body,
    });
  });

  it('updateAgent PATCHes to ai/catalog/{id}/ and never sends name', async () => {
    const body = { role: 'critic', max_turns: 5 };
    await updateAgent(TOKEN, 'agent-9', body);
    expect(apiFetch).toHaveBeenCalledWith('ai/catalog/agent-9/', {
      token: TOKEN,
      method: 'PATCH',
      body,
    });
    expect(JSON.stringify(body)).not.toContain('name');
  });

  it('deleteAgent DELETEs ai/catalog/{id}/', async () => {
    await deleteAgent(TOKEN, 'agent-9');
    expect(apiFetch).toHaveBeenCalledWith('ai/catalog/agent-9/', {
      token: TOKEN,
      method: 'DELETE',
    });
  });
});

describe('aiCatalog — durable run actions', () => {
  it('resumeRun POSTs to ai/runs/{id}/resume/ with NO body', async () => {
    await resumeRun(TOKEN, 'run-1');
    expect(apiFetch).toHaveBeenCalledWith('ai/runs/run-1/resume/', {
      token: TOKEN,
      method: 'POST',
    });
  });

  it('replayRun POSTs {confirm: true} to ai/runs/{id}/replay/ (RULE_21 consent)', async () => {
    await replayRun(TOKEN, 'run-1');
    expect(apiFetch).toHaveBeenCalledWith('ai/runs/run-1/replay/', {
      token: TOKEN,
      method: 'POST',
      body: { confirm: true },
    });
  });
});
