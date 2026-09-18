// src/api/aiPromptGovernance.js — PromptVersion activate/rollback (ADR-0036 Phase 7)
import { apiFetch } from './api';

const BASE = 'ai/pulse/control/prompts/';

export function listPromptVersions(token, { instanceId } = {}) {
  const params = new URLSearchParams();
  if (instanceId) params.set('instance_id', instanceId);
  const qs = params.toString();
  return apiFetch(qs ? `${BASE}versions/?${qs}` : `${BASE}versions/`, { token });
}

export function activatePromptVersion(token, versionId) {
  return apiFetch(`${BASE}versions/${encodeURIComponent(versionId)}/activate/`, {
    token,
    method: 'POST',
    body: {},
  });
}

export function rollbackPromptVersion(token, versionId) {
  return apiFetch(`${BASE}versions/${encodeURIComponent(versionId)}/rollback/`, {
    token,
    method: 'POST',
    body: {},
  });
}
