// src/pages/admin/ai/AIConversationsPage.jsx
// Admin conversation browser — lists AI conversations and lets admins inspect
// the full message history. Reuses the aiWorkspace API client + AIMessageBubble.
// Route /admin/ai/conversations.
import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Chip, CircularProgress, IconButton, List, ListItemButton,
  ListItemText, Paper, Stack, Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ChatIcon from '@mui/icons-material/Chat';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { listConversations, getConversation } from '../../../api/aiWorkspace';
import AIMessageBubble from '../../../shell/AIMessageBubble';

const STATUS_COLORS = {
  pending: 'default',
  working: 'primary',
  completed: 'success',
  failed: 'error',
  partial: 'warning',
  needs_input: 'warning',
};

const TYPE_LABELS = {
  chat: 'Chat',
  dq_validate: 'DQ Check',
  dq_suggest: 'DQ Suggest',
  nl_query: 'NL Query',
  anomaly: 'Anomaly',
  report_draft: 'Report',
};

function formatDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString();
}

export default function AIConversationsPage() {
  useDocumentTitle('AI Conversations');
  const { token } = useAuth();
  const { notifyFromError } = useNotification();

  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listConversations(token, { limit: 100 });
      setConversations(Array.isArray(data) ? data : []);
    } catch (err) {
      notifyFromError(err, 'Could not load conversations');
    } finally {
      setLoading(false);
    }
  }, [token, notifyFromError]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const openConversation = useCallback(async (conv) => {
    setSelectedId(conv.id);
    setMessages([]);
    setLoadingDetail(true);
    try {
      const data = await getConversation(token, conv.id);
      const canonical = data?.conversation || data;
      setMessages(Array.isArray(canonical?.messages) ? canonical.messages : []);
    } catch (err) {
      notifyFromError(err, 'Could not load conversation');
    } finally {
      setLoadingDetail(false);
    }
  }, [token, notifyFromError]);

  const handleBack = useCallback(() => {
    setSelectedId(null);
    setMessages([]);
  }, []);

  const selected = conversations.find((c) => c.id === selectedId) || null;

  return (
    <PageContainer>
      {selectedId ? (
        <Stack spacing={1} sx={{ flex: 1, minHeight: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <IconButton size="small" onClick={handleBack} aria-label="Back to conversations">
              <ArrowBackIcon fontSize="small" />
            </IconButton>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, flex: 1 }} noWrap>
              {selected?.title || 'Conversation'}
            </Typography>
            {selected && (
              <Chip
                size="small"
                label={selected.status || 'unknown'}
                color={STATUS_COLORS[selected.status] || 'default'}
              />
            )}
          </Box>

          {loadingDetail ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
              <CircularProgress size={24} />
            </Box>
          ) : messages.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
              No messages in this conversation.
            </Typography>
          ) : (
            <Paper variant="outlined" sx={{ flex: 1, minHeight: 0, overflow: 'auto', py: 1 }}>
              <Stack spacing={0.5}>
                {messages.map((m, i) => (
                  <AIMessageBubble
                    key={m.id || i}
                    message={{ ...m, content: m.content || '' }}
                  />
                ))}
              </Stack>
            </Paper>
          )}
        </Stack>
      ) : (
        <Stack spacing={1} sx={{ flex: 1, minHeight: 0 }}>
          <Box>
            <Typography variant="h5" fontWeight={700}>AI Conversations</Typography>
            <Typography variant="body2" color="text.secondary">
              Browse and inspect AI Workspace conversations.
            </Typography>
          </Box>

          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
              <CircularProgress size={24} />
            </Box>
          ) : conversations.length === 0 ? (
            <Alert severity="info">No conversations yet.</Alert>
          ) : (
            <Paper variant="outlined" sx={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
              <List dense disablePadding>
                {conversations.map((c) => (
                  <ListItemButton key={c.id} onClick={() => openConversation(c)} divider>
                    <ChatIcon sx={{ fontSize: 16, color: 'text.secondary', mr: 1 }} />
                    <ListItemText
                      primary={c.title || `${TYPE_LABELS[c.conversation_type] || 'Conversation'} #${String(c.id).slice(0, 6)}`}
                      secondary={formatDate(c.created_at)}
                      primaryTypographyProps={{ variant: 'body2', fontWeight: 600 }}
                      secondaryTypographyProps={{ variant: 'caption' }}
                    />
                    {c.conversation_type && (
                      <Chip
                        size="small"
                        variant="outlined"
                        label={TYPE_LABELS[c.conversation_type] || c.conversation_type}
                      />
                    )}
                    <Chip
                      size="small"
                      label={c.status || 'unknown'}
                      color={STATUS_COLORS[c.status] || 'default'}
                      sx={{ ml: 1 }}
                    />
                  </ListItemButton>
                ))}
              </List>
            </Paper>
          )}
        </Stack>
      )}
    </PageContainer>
  );
}
