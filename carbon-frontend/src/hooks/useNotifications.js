import { useState, useEffect, useCallback } from 'react';
import { getNotifications, getUnreadCount, markRead as markReadApi, markAllRead as markAllReadApi } from '../api/notifications';
import { useAuth } from '../auth/AuthContext';

const sharedStore = {
  alerts: [],
  unreadCount: 0,
  total: 0,
  loading: true,
  page: 1,
  token: null,
};

const subscribers = new Set();
let pollIntervalId = null;
let fetchInFlight = false;

function notifySubscribers() {
  subscribers.forEach((setState) => setState({
    alerts: sharedStore.alerts,
    unreadCount: sharedStore.unreadCount,
    total: sharedStore.total,
    loading: sharedStore.loading,
    page: sharedStore.page,
  }));
}

function updateStore(partial) {
  Object.assign(sharedStore, partial);
  notifySubscribers();
}

async function refreshStore(token) {
  if (!token) return;
  fetchInFlight = true;
  updateStore({ loading: true });
  try {
    const [notificationData, unreadData] = await Promise.all([
      getNotifications(token, 1),
      getUnreadCount(token),
    ]);
    updateStore({
      alerts: notificationData.results || [],
      total: notificationData.count || 0,
      page: 1,
      unreadCount: unreadData.unread_count || 0,
      loading: false,
      token,
    });
  } catch (_) {
    updateStore({ loading: false, token });
  } finally {
    fetchInFlight = false;
  }
}

function startPolling(token) {
  if (!token || pollIntervalId) return;
  pollIntervalId = window.setInterval(() => {
    getUnreadCount(token)
      .then((data) => {
        updateStore({ unreadCount: data.unread_count || 0 });
      })
      .catch(() => {});
  }, 30000);
}

function stopPolling() {
  if (pollIntervalId) {
    window.clearInterval(pollIntervalId);
    pollIntervalId = null;
  }
}

export function useNotifications() {
  const { token } = useAuth();
  const [state, setState] = useState({
    alerts: sharedStore.alerts,
    unreadCount: sharedStore.unreadCount,
    total: sharedStore.total,
    loading: sharedStore.loading,
    page: sharedStore.page,
  });

  useEffect(() => {
    subscribers.add(setState);
    setState({
      alerts: sharedStore.alerts,
      unreadCount: sharedStore.unreadCount,
      total: sharedStore.total,
      loading: sharedStore.loading,
      page: sharedStore.page,
    });

    if (token && token !== sharedStore.token && !fetchInFlight) {
      refreshStore(token).catch(() => {});
    }

    if (token) {
      startPolling(token);
    }

    return () => {
      subscribers.delete(setState);
      if (!subscribers.size) {
        stopPolling();
        sharedStore.alerts = [];
        sharedStore.unreadCount = 0;
        sharedStore.total = 0;
        sharedStore.loading = true;
        sharedStore.page = 1;
        sharedStore.token = null;
      }
    };
  }, [token]);

  const refresh = useCallback(async () => {
    if (!token) return;
    await refreshStore(token);
  }, [token]);

  const markRead = useCallback(
    async (id) => {
      updateStore({
        alerts: sharedStore.alerts.map((item) =>
          item.id === id ? { ...item, is_read: true } : item,
        ),
        unreadCount: Math.max(sharedStore.unreadCount - 1, 0),
      });
      try {
        await markReadApi(token, id);
      } catch (_) {
        await refresh();
      }
    },
    [refresh, token],
  );

  const markAllRead = useCallback(
    async () => {
      updateStore({
        alerts: sharedStore.alerts.map((item) => ({ ...item, is_read: true })),
        unreadCount: 0,
      });
      try {
        await markAllReadApi(token);
      } catch (_) {
        await refresh();
      }
    },
    [refresh, token],
  );

  const loadMore = useCallback(async () => {
    if (!token) return;
    if (sharedStore.alerts.length >= sharedStore.total) return;
    const nextPage = sharedStore.page + 1;
    try {
      const notificationData = await getNotifications(token, nextPage);
      updateStore({
        alerts: [...sharedStore.alerts, ...(notificationData.results || [])],
        page: nextPage,
      });
    } catch (_) {
      // Keep existing store on failure.
    }
  }, [token]);

  return {
    ...state,
    markRead,
    markAllRead,
    refresh,
    loadMore,
  };
}
