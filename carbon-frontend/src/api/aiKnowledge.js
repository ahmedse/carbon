// src/api/aiKnowledge.js — KnowledgeItem CRUD (ADR-0036 Phase 7)
import { apiFetch } from './api';

const BASE = 'ai/knowledge/';

export function listKnowledgeItems(token, { knowledgeClass, reviewStatus } = {}) {
  const params = new URLSearchParams();
  if (knowledgeClass) params.set('knowledge_class', knowledgeClass);
  if (reviewStatus) params.set('review_status', reviewStatus);
  const qs = params.toString();
  return apiFetch(qs ? `${BASE}items/?${qs}` : `${BASE}items/`, { token });
}

export function createKnowledgeItem(token, body) {
  return apiFetch(`${BASE}items/`, { token, method: 'POST', body });
}

export function updateKnowledgeItem(token, id, body) {
  return apiFetch(`${BASE}items/${encodeURIComponent(id)}/`, {
    token,
    method: 'PATCH',
    body,
  });
}

export function revokeKnowledgeItem(token, id, reason = '') {
  return apiFetch(`${BASE}items/${encodeURIComponent(id)}/revoke/`, {
    token,
    method: 'POST',
    body: { reason },
  });
}
