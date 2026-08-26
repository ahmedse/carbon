import { apiFetch } from './api';

const BASE = 'accounts/notifications/';

export function getNotifications(token, page = 1) {
  return apiFetch(`${BASE}?page=${page}`, { token });
}

export function getUnreadCount(token) {
  return apiFetch(`${BASE}unread_count/`, { token });
}

export function markRead(token, id) {
  return apiFetch(`${BASE}${id}/mark_read/`, { token, method: 'POST' });
}

export function markAllRead(token) {
  return apiFetch(`${BASE}mark_all_read/`, { token, method: 'POST' });
}
