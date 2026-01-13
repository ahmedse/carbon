/**
 * AI Copilot API Service
 * Handles communication with AI backend endpoints
 * 
 * IMPORTANT: Uses centralized API_ROUTES from config.js
 * DO NOT hardcode URLs here - always use API_ROUTES
 */

import { apiFetch } from './api';
import { API_ROUTES } from '../config';

/**
 * Chat API
 */
export const sendMessage = async (message, projectId = null) => {
  const token = localStorage.getItem('access');
  const response = await apiFetch(API_ROUTES.aiChat, {
    method: 'POST',
    token,
    body: {
      message,
      project_id: projectId,
    },
  });
  return response;
};

export const getChatHistory = async (projectId = null, limit = 20) => {
  const token = localStorage.getItem('access');
  const params = {};
  if (projectId) params.project_id = projectId;
  if (limit) params.limit = limit;
  
  const queryString = new URLSearchParams(params).toString();
  const url = `${API_ROUTES.aiChatHistory}${queryString ? '?' + queryString : ''}`;
  
  const response = await apiFetch(url, { token });
  return response;
};

export const clearChatHistory = async (projectId = null) => {
  const token = localStorage.getItem('access');
  const response = await apiFetch(API_ROUTES.aiChatClear, {
    method: 'DELETE',
    token,
    body: { project_id: projectId },
  });
  return response;
};

/**
 * Insights API
 */
export const getInsights = async (acknowledged = null) => {
  const token = localStorage.getItem('access');
  const params = {};
  if (acknowledged !== null) params.acknowledged = acknowledged;
  
  const queryString = new URLSearchParams(params).toString();
  const url = `${API_ROUTES.aiInsights}${queryString ? '?' + queryString : ''}`;
  
  const response = await apiFetch(url, { token });
  return response;
};

export const acknowledgeInsight = async (insightId) => {
  const token = localStorage.getItem('access');
  const route = API_ROUTES.aiInsightAck.replace('{id}', insightId);
  const response = await apiFetch(route, {
    method: 'POST',
    token,
  });
  return response;
};

/**
 * Preferences API
 */
export const getPreferences = async () => {
  const token = localStorage.getItem('access');
  const response = await apiFetch(API_ROUTES.aiPreferences, { token });
  return response;
};

export const updatePreferences = async (preferences) => {
  const token = localStorage.getItem('access');
  const response = await apiFetch(API_ROUTES.aiPreferencesUpdate, {
    method: 'PATCH',
    token,
    body: preferences,
  });
  return response;
};

/**
 * Helper: Format message for display
 */
export const formatMessage = (message) => ({
  id: message.id,
  role: message.role,
  content: message.content,
  timestamp: new Date(message.created_at),
  metadata: message.metadata || {},
});

/**
 * Helper: Format insight for display
 */
export const formatInsight = (insight) => ({
  id: insight.id,
  type: insight.type,
  urgency: insight.urgency,
  title: insight.title,
  description: insight.description,
  actionLabel: insight.action_label,
  actionUrl: insight.action_url,
  metadata: insight.metadata || {},
  acknowledged: insight.acknowledged,
  createdAt: new Date(insight.created_at),
  expiresAt: insight.expires_at ? new Date(insight.expires_at) : null,
});

export default {
  sendMessage,
  getChatHistory,
  clearChatHistory,
  getInsights,
  acknowledgeInsight,
  getPreferences,
  updatePreferences,
  formatMessage,
  formatInsight,
};
